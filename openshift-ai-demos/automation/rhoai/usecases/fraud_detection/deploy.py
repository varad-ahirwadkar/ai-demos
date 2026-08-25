"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1-3. prepare.bootstrap_platform — validate cluster, operator, DSC/DSCI
         Each phase is shown as a live sub-step so the user sees progress
         during the bootstrap (which can take ~2 minutes on a cold cluster).
    4.   configure storage — S3 secret applied once if any model uses an S3 URI
    5.   for each model in deployment.models:
         a. Triton ServingRuntime (via Template)
         b. InferenceService (deploy + wait until Ready)
         c. smoke test
    6.   apply TrustyAI service + prerequisites
    7.   for each model with bias_monitoring configured:
         a. send observations → wait for ingestion
         b. apply name mapping (optional)
         c. validate + schedule SPD monitors (optional)
         d. schedule identity monitors (optional)
    8.   print deployment summary

model_uri behaviour (per model entry in deployment.models):
    pvc://, hf://, oci:// — set storageUri, remove storage block + S3 annotation,
                            skip S3 secret (model is self-contained)
    any other string      — treat as S3 path; update storage.path, apply S3 secret

bias_monitoring behaviour (per model entry in deployment.models):
    absent / null         — model is deployed without any TrustyAI monitoring
    present               — full monitoring workflow is executed after TrustyAI is ready
"""

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rhoai.ocp import resources as ocp_resources
from rhoai.platform import dsc, inference, manifests, operators, prepare, request_generator, storage, trustyai, trustyai_client
from rhoai.platform.inference import EndpointUnreachable
from rhoai.usecases.fraud_detection import assets
from rhoai.usecases.fraud_detection.assets import (
    ModelResult,
    render_curl_command,
    render_curl_command_file,
    resolve_inference_dataset,
    resolve_inference_request,
)
from rhoai.utils import yaml_io
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import elapsed_timer, header_step, step, sub_step

log = get_logger(__name__)
_console = Console(stderr=False, highlight=False)

_NON_S3_SCHEMES = ("pvc://", "hf://", "oci://")

# Display names for DSC component identifiers.
# Entries here override the default .title() capitalisation.
_COMPONENT_DISPLAY: dict[str, str] = {
    "aipipelines":        "AI Pipelines",
    "dashboard":          "Dashboard",
    "feastoperator":      "Feast",
    "kserve":             "KServe",
    "kueue":              "Kueue",
    "llamastackoperator": "LlamaStack",
    "mlflowoperator":     "MLflow",
    "modelregistry":      "Model Registry",
    "ogx":                "OGX",
    "ray":                "Ray",
    "sparkoperator":      "Spark",
    "trainer":            "Trainer",
    "trainingoperator":   "Training",
    "trustyai":           "TrustyAI",
    "workbenches":        "Workbenches",
}


def _resolve_request_artifacts(
    model: dict[str, Any],
    repo_root: str,
) -> tuple[Path, Path | None, dict[str, Any], str]:
    """Resolve request path, schema source, payload, and reproducible curl command.

    Precedence:
      1. user-provided inference_request
      2. generated request from inference_dataset + config_path
    """
    name = model["name"]
    request_path = resolve_inference_request(model, repo_root)
    schema_source = _resolve_schema_source(model, repo_root)
    input_name, datatype = inference._read_tensor_schema(schema_source)

    if request_path is not None:
        if request_path.suffix.lower() == ".json":
            payload = inference._load_request_payload(request_path)
        else:
            payload = inference._load_request_payload(
                request_path,
                input_name=input_name,
                datatype=datatype,
            )
    else:
        dataset_path = resolve_inference_dataset(model, repo_root)
        config_path = model.get("config_path", "")
        if not config_path:
            raise ValueError(
                f"Model '{name}' requires config_path when inference_dataset is used without inference_request."
            )
        _, payload = request_generator.build_request_from_csv_file(
            Path(config_path),
            dataset_path,
        )
        inputs_dir = Path(repo_root) / "automation" / "rhoai" / "usecases" / "fraud_detection" / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        request_path = inputs_dir / f"{name}_generated_request.json"
        request_path.write_text(json.dumps(payload, indent=2))

    curl_cmd = render_curl_command(
        inference._TRITON_INFER_PATH.format(model_name=name),
        payload,
    )
    return request_path, schema_source, payload, curl_cmd



def _resolve_schema_source(model: dict[str, Any], repo_root: str) -> Path | None:
    """Return the schema source path for a model's CSV conversions.

    Resolution order:

    1. ``csv_config`` present in model config — write its ``input_name`` and
       ``datatype`` into a temporary JSON file so ``_read_tensor_schema`` can
       read them uniformly.  (Not used here — callers pass ``csv_config`` values
       directly when overriding.)
    2. ``inference_request`` is a ``.json`` — return it as the schema source.
    3. No usable source — return ``None`` (safe when all files are JSON).

    In practice this returns the resolved ``inference_request`` JSON path when
    it exists, which covers the common case.  ``csv_config`` override is handled
    directly by passing a pre-built ``Path`` from the caller when needed.

    Args:
        model:     Model config dict.
        repo_root: Absolute repo root path.

    Returns:
        Absolute path to a KServe v2 JSON file, or ``None``.
    """
    # csv_config explicit override — build a temporary file on the fly so that
    # _read_tensor_schema gets a Path as expected.
    csv_cfg = model.get("csv_config")
    if csv_cfg:
        import tempfile, json as _json
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(_json.dumps({
            "inputs": [{
                "name":     csv_cfg.get("input_name", "input"),
                "datatype": csv_cfg.get("datatype",   "FP64"),
                "shape":    [1, 1],
                "data":     [[0]],
            }]
        }))
        return tmp

    # Fall back to inference_request JSON.
    req = model.get("inference_request", "")
    if req and Path(req).suffix.lower() == ".json":
        return Path(repo_root) / req

    return None


def _deploy_model(
    model: dict[str, Any],
    repo_root: str,
    platform_namespace: str,
    namespace: str,
    inference_timeout: int,
    staging_timeout: int = 120,
) -> ModelResult:
    """Deploy a single model: ServingRuntime, InferenceService, smoke test.

    Accepts two mutually exclusive model source configurations:

    ``model_uri`` — existing path on S3, PVC, Hugging Face, or OCI; used as-is.
    ``model_path`` + ``config_path`` — local artifact files; the framework stages
        them onto a PVC in the Triton repository layout and derives the URI.

    Returns a ModelResult that records whether validation was skipped.
    The caller is responsible for surfacing any warnings in the summary.
    """
    name         = model["name"]
    model_uri    = model.get("model_uri", "")
    model_path   = model.get("model_path", "")
    config_path  = model.get("config_path", "")
    runtime_name = assets.serving_runtime_name(name)

    # --- Validate mutual exclusivity -----------------------------------------
    if model_uri and (model_path or config_path):
        raise ValueError(
            f"Model '{name}': model_uri and model_path/config_path are mutually "
            "exclusive. Provide either model_uri or both model_path and config_path."
        )
    if bool(model_path) != bool(config_path):
        raise ValueError(
            f"Model '{name}': model_path and config_path must both be provided together."
        )

    # --- Stage local artifacts onto PVC (Option 2) ---------------------------
    if model_path and config_path:
        pvc_name = model.get("pvc_name") or f"{name}-pvc"
        pvc_size = model.get("pvc_size", "1Gi")
        storage_class = model.get("storage_class", "")

        with step("Validating local model artifacts"):
            storage.validate_local_artifacts(Path(model_path), Path(config_path))

        with step(f"Ensuring PVC '{pvc_name}'"):
            pvc_created = storage.create_pvc(pvc_name, namespace, pvc_size,
                                             storage_class=storage_class)

        if pvc_created:
            with step("Staging model repository on PVC"):
                storage.copy_files_to_pvc(
                    pvc_name=pvc_name,
                    namespace=namespace,
                    files=assets.triton_file_map(
                        name, Path(model_path), Path(config_path)
                    ),
                    timeout=staging_timeout,
                )
        else:
            log.info("PVC '%s' already populated — skipping file staging", pvc_name)

        model_uri = assets.triton_pvc_uri(pvc_name, name)
        log.debug("Derived model URI: %s", model_uri)

    with step("Ensuring serving runtime"):
        log.debug("ServingRuntime name: %s", runtime_name)
        inference.apply_serving_runtime_from_template(
            assets.get_serving_runtime_template(repo_root), platform_namespace, namespace,
            model_name=name,
            runtime_name=runtime_name,
        )

    model_dict = yaml_io.load(assets.get_model_manifest(repo_root))
    model_dict["metadata"]["name"] = name
    # Point this ISVC at its own dedicated ServingRuntime.
    model_dict["spec"]["predictor"]["model"]["runtime"] = runtime_name
    if model_uri:
        model_spec = model_dict["spec"]["predictor"]["model"]
        if model_uri.startswith(_NON_S3_SCHEMES):
            model_spec.pop("storage", None)
            model_spec["storageUri"] = model_uri
            model_dict["metadata"]["annotations"].pop(
                "opendatahub.io/connection-type-ref", None
            )
        else:
            model_spec.setdefault("storage", {})["path"] = model_uri

    with step("Ensuring inference service") as s:
        ocp_resources.apply_dict(model_dict, namespace)
        inference.wait_until_ready(
            name, namespace, inference_timeout,
            on_tick=s.tick,
        )

    endpoint = inference.get_inference_url(name, namespace)
    result = ModelResult(name=name, model_uri=model_uri, endpoint=endpoint)
    with step("Smoke-testing model endpoint") as s:
        request_path, schema_source, payload, curl_cmd = _resolve_request_artifacts(model, repo_root)
        result.request_path    = request_path
        result.inference_input = payload
        result.curl_cmd = render_curl_command_file(
            endpoint.rstrip("/") + inference._TRITON_INFER_PATH.format(model_name=name),
            request_path,
        )
        try:
            payload, response, _ = inference.verify_triton_inference(
                name, namespace, name, request_path,
                schema_source=schema_source,
            )
            result.inference_input  = payload
            result.inference_output = response
        except EndpointUnreachable as exc:
            s.skip()
            result.validation_skipped = True
            result.unreachable        = exc
            log.debug("Endpoint unreachable for '%s': %s", name, exc)

    return result


def _resolve_observation_files(obs_cfg: dict[str, Any], repo_root: str) -> list[Path]:
    """Resolve the list of observation file paths from the bias_monitoring.observations config.

    Accepts two mutually exclusive forms:

    ``path`` — a single file or a directory.  If a directory, all ``*.json``
    and ``*.csv`` files are returned in lexical filename order (JSON and CSV
    files may be mixed; each is converted to a KServe v2 payload at send time).
    An empty directory raises ``ValueError``.

    ``files`` — an explicit ordered list of file paths (relative to repo_root).

    ``path`` and ``files`` must not both be set.

    Args:
        obs_cfg:   The ``bias_monitoring.observations`` sub-dict from the model config.
        repo_root: Absolute path to the repo root (used to resolve relative paths).

    Returns:
        Non-empty ordered list of absolute Path objects.

    Raises:
        ValueError: If the config is invalid (both keys set, neither key set,
                    directory is empty or contains no supported files).
    """
    has_path  = "path"  in obs_cfg
    has_files = "files" in obs_cfg

    if has_path and has_files:
        raise ValueError(
            "bias_monitoring.observations: 'path' and 'files' are mutually exclusive. "
            "Use one or the other."
        )
    if not has_path and not has_files:
        raise ValueError(
            "bias_monitoring.observations: either 'path' or 'files' must be set."
        )

    if has_files:
        paths = [Path(repo_root) / f for f in obs_cfg["files"]]
        if not paths:
            raise ValueError("bias_monitoring.observations.files must not be empty.")
        return paths

    # --- path form ---
    resolved = Path(repo_root) / obs_cfg["path"]
    if resolved.is_dir():
        paths = sorted(
            [p for p in resolved.iterdir() if p.suffix.lower() in (".json", ".csv")],
            key=lambda p: p.name,
        )
        if not paths:
            raise ValueError(
                f"Observation directory contains no .json or .csv files: {resolved}"
            )
        return paths
    return [resolved]


def _configure_bias_monitoring(
    model: dict[str, Any],
    route: str,
    token: str,
    namespace: str,
    repo_root: str,
    ingestion_timeout: int,
) -> None:
    """Configure TrustyAI bias monitoring for a single model.

    Reads ``model["bias_monitoring"]`` and returns immediately if absent or null.

    Workflow:
        1. Resolve and validate observation files locally.
        2. Send observations to the model endpoint.
        3. Wait until TrustyAI has ingested >= 90% of sent rows.
        4. Apply feature/output name mapping (optional).
        5. For each SPD monitor: validate via compute_spd (result shown to user),
           then schedule recurring monitoring.
        6. Schedule identity monitors.

    Args:
        model:             Model config dict (from deployment.models).
        route:             TrustyAI service base URL.
        token:             Bearer token for authentication.
        namespace:         Namespace where the model is deployed.
        repo_root:         Absolute path to the repo root.
        ingestion_timeout: Maximum seconds to wait for TrustyAI ingestion.
    """
    cfg = model.get("bias_monitoring")
    if not cfg:
        return

    model_id = model["name"]

    # 1+2 — resolve files, validate locally, send to model endpoint.
    with step("Sending observations") as s:
        obs_files  = _resolve_observation_files(cfg["observations"], repo_root)
        total_sent = inference.send_observations(
            model_id, namespace, obs_files,
            schema_source=_resolve_schema_source(model, repo_root),
        )

    # 3 — wait for TrustyAI to ingest the observations.
    with step(f"Waiting for ingestion ({total_sent} rows)") as s:
        trustyai.wait_for_ingestion(route, token, model_id, expected=total_sent,
                                    timeout=ingestion_timeout, on_tick=s.tick)

    # 4 — optional name mapping.
    if nm := cfg.get("name_mapping"):
        with step("Mapping feature names"):
            trustyai_client.apply_name_mapping(
                route, token, model_id,
                nm.get("inputs", {}),
                nm.get("outputs", {}),
            )

    # 5 — SPD monitors: evaluate (compute + print result), then schedule.
    # Compute and schedule are separate steps so each outcome is visible.
    # The SPD result line is printed after the step context exits so it appears
    # on its own line below the ✔ outcome, never interleaved with the spinner.
    spd_monitors      = cfg.get("spd_monitors", [])
    identity_monitors = cfg.get("identity_monitors", [])

    for monitor in spd_monitors:
        kwargs  = dict(monitor)
        attr    = monitor.get("protected_attribute", "")
        outside = False
        spd_val = "n/a"

        with step(f"Evaluating fairness ({attr})"):
            result   = trustyai_client.compute_spd(route, token, model_id, **kwargs)
            spd_val  = result.get("value", "n/a")
            spd_defn = result.get("specificDefinition", "")
            outside  = result.get("thresholds", {}).get("outsideBounds", False)
            log.debug("SPD definition for '%s': %s", attr, spd_defn)

        # Print the metric result on its own line after the ✔ / ✖ outcome.
        verdict = "outside bounds  \u26a0" if outside else "within bounds  \u2714"
        _console.print(f"     SPD {spd_val:.4f}  \u2014  {verdict}")

        with step(f"Scheduling SPD monitor ({attr})"):
            trustyai_client.schedule_spd(route, token, model_id, **kwargs)

    # 6 — identity monitors: one step per monitor so the column name is visible.
    for monitor in identity_monitors:
        col = monitor["column_name"]
        log.debug("Identity monitor: column=%s batch_size=%s", col,
                  monitor.get("batch_size", 5000))
        with step(f"Scheduling identity monitor ({col})"):
            trustyai_client.schedule_identity(
                route, token, model_id,
                column_name=col,
                batch_size=monitor.get("batch_size", 5000),
            )


def _verify_cmd(use_case: str, config_file: str) -> str:
    """Return the copy-pasteable verify command, including -c if a config was used."""
    if config_file:
        return f"rhoai usecase verify {use_case} \\\n      -c {config_file}"
    return f"rhoai usecase verify {use_case}"


def _console_host(trustyai_route: str) -> str:
    """Derive the OpenShift console hostname from a TrustyAI route URL.

    OpenShift generates route hostnames as::

        <route-name>-<namespace>.apps.<cluster-domain>

    So for service ``trustyai-service`` in namespace ``test-fraud`` the URL is::

        https://trustyai-service-test-fraud.apps.rdr-varad-421.ocp-rhoai.com

    The console always lives at::

        console-openshift-console.apps.<cluster-domain>

    We find the first ``.apps.`` boundary in the host and prepend the fixed
    console hostname — this works regardless of the route name or namespace.

    Returns an empty string if the route is empty or ``.apps.`` is absent
    (non-standard or locally-routed cluster).

    Args:
        trustyai_route: Full TrustyAI service base URL.
    """
    if not trustyai_route:
        return ""
    try:
        from urllib.parse import urlparse
        host = urlparse(trustyai_route).hostname or ""
        idx = host.find(".apps.")
        if idx == -1:
            return ""
        return "console-openshift-console" + host[idx:]
    except Exception:  # noqa: BLE001
        return ""


def _metrics_url(trustyai_route: str, metric: str) -> str:
    """Return the OpenShift console query-browser URL pre-loaded with *metric*.

    Args:
        trustyai_route: Full TrustyAI service base URL.
        metric:         Prometheus expression, e.g. ``trustyai_spd``.
    """
    host = _console_host(trustyai_route)
    if not host:
        return ""
    from urllib.parse import urlencode
    return f"https://{host}/monitoring/query-browser?{urlencode({'query0': metric})}"


def _metrics_dashboard_url(trustyai_route: str) -> str:
    """Return the OpenShift console Observe → Metrics landing page URL.

    Links directly to the metrics query browser without pre-loading any
    expression so the user can explore freely.

    Args:
        trustyai_route: Full TrustyAI service base URL.
    """
    host = _console_host(trustyai_route)
    if not host:
        return ""
    return f"https://{host}/monitoring/query-browser"


def print_summary(
    results: list[ModelResult],
    use_case: str,
    namespace: str,
    config_file: str = "",
    trustyai_route: str = "",
    mode: str = "deploy",
    total: str = "",
    show_identity: bool = True,
) -> None:
    """Print the end-of-command summary for a fraud-detection deploy or verify run.

    Called by both deploy() and verify() — the output structure is identical in
    both cases; the ``mode`` parameter controls the heading and the "Next steps"
    content shown.

    Per-model block order:
        Endpoint → Smoke test → Inference request → Invoke manually → Inference response

    The request/response/curl sections are suppressed when the smoke test was
    skipped (endpoint unreachable) — there is nothing to show in that case.

    Args:
        results:        Per-model outcomes collected during the run.
        use_case:       Use case name (e.g. "fraud-detection").
        namespace:      Workload namespace.
        config_file:    Path to the --config file used, for the verify/cleanup hints.
        trustyai_route: TrustyAI service URL; omitted from output when empty.
        mode:           "deploy" — prints "Deployment complete." heading.
                        "verify" — prints "Verification complete." heading.
        total:          Formatted total duration string, e.g. "3m 42s".  When non-empty,
                        appended to the heading line as "  Total: <value>".
        show_identity:  Whether to include TrustyAI identity metric hints.
    """
    cleanup_cmd = (
        f"rhoai usecase cleanup {use_case} \\\n      -c {config_file}"
        if config_file
        else f"rhoai usecase cleanup {use_case}"
    )
    verify_cmd = _verify_cmd(use_case, config_file)

    heading = "Deployment complete." if mode == "deploy" else "Verification complete."
    duration_str = f"  Total: {total}" if total else ""
    _console.print(f"\n{heading}{duration_str}\n")
    _console.print(f"  Use case   : {use_case}")
    _console.print(f"  Namespace  : {namespace}\n")

    # --- Per-model outcome blocks ---
    # Source paths are omitted — they were already shown during execution via
    # the model_uri in the header_step label or are implicit from the config.
    _console.print("Models\n")
    for r in results:
        smoke_status = "Skipped (endpoint unreachable)" if r.validation_skipped else "Passed"
        _console.print(f"\u2714  {r.name}")
        _console.print(f"  Endpoint     : {r.endpoint}")
        _console.print(f"  Smoke test   : {smoke_status}")

        if not r.validation_skipped:
            if r.inference_input is not None:
                _console.print(
                    f"\n  Inference request\n"
                    + "\n".join(
                        f"    {line}"
                        for line in json.dumps(r.inference_input, indent=2).splitlines()
                    )
                )
            if r.inference_output is not None:
                _console.print(
                    f"\n  Inference response\n"
                    + "\n".join(
                        f"    {line}"
                        for line in json.dumps(r.inference_output, indent=2).splitlines()
                    )
                )

        _console.print("")

    # --- TrustyAI ---
    if trustyai_route:
        _console.print("TrustyAI\n")
        _console.print(f"  Endpoint    : {trustyai_route}\n")

    # --- Warnings: only when smoke test was skipped ---
    unvalidated = [r for r in results if r.validation_skipped]
    if unvalidated:
        _console.print("Warnings\n")
        for r in unvalidated:
            _console.print(f"\u26a0  {r.name}\n")
            if r.unreachable:
                _console.print(f"  Endpoint:\n    {r.unreachable.infer_url}\n")
                log.debug("Manual validation curl command: %s", r.unreachable.curl_cmd)
            _console.print(
                "  Inference could not be validated — endpoint not reachable\n"
                "  from this machine.\n\n"
                "  Verify the cluster route is accessible from your workstation.\n\n"
                "  If hostname resolution fails, check DNS or /etc/hosts.\n\n"
                f"  Then rerun:\n\n"
                f"    {verify_cmd}\n"
            )

    # --- Next steps ---
    _console.print("Next steps\n")

    # "Invoke the model" — one curl block per model, using the file-based command.
    # Falls back to the inline curl stored on EndpointUnreachable when the smoke
    # test was skipped (no on-disk request file was exercised in that case).
    invoke_lines: list[str] = []
    for r in results:
        if r.curl_cmd:
            invoke_lines.append(f"    # {r.name}")
            invoke_lines.append(f"    {r.curl_cmd.replace(chr(10), chr(10) + '    ')}\n")
        elif r.unreachable and r.unreachable.curl_cmd:
            invoke_lines.append(f"    # {r.name}")
            invoke_lines.append(f"    {r.unreachable.curl_cmd}\n")
    if invoke_lines:
        _console.print("  Invoke the model\n\n" + "\n".join(invoke_lines))

    if trustyai_route:
        # TrustyAI is active — show Observe → Metrics guidance with direct links.
        dashboard_url = _metrics_dashboard_url(trustyai_route)
        spd_url       = _metrics_url(trustyai_route, "trustyai_spd")
        identity_url  = _metrics_url(trustyai_route, "trustyai_identity") if show_identity else ""

        block = "  Check metrics in the OpenShift console\n\n"
        if dashboard_url:
            block += f"    {dashboard_url}\n\n"
        block += (
            "    Navigate to Observe \u2192 Metrics in the OpenShift console.\n"
            "    If you just deployed, refresh the page before the new metrics appear.\n"
            "    Set the time window to 5 minutes (top left)\n"
            "    and the refresh interval to 15 seconds (top right).\n"
            "    Enter one of the expressions below in the Expression field:\n\n"
            "      trustyai_spd       — statistical parity difference\n"
        )
        if show_identity:
            block += "      trustyai_identity  — identity metrics\n"
        if spd_url:
            block += f"\n    SPD metrics\n      {spd_url}\n"
        if identity_url:
            block += f"\n    Identity metrics\n      {identity_url}\n"
        _console.print(block)

    _console.print(f"  Clean up deployment\n\n    {cleanup_cmd}\n")


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root          = config["repo_root"]
    dep_cfg            = config.get("deployment", {})
    platform_namespace = config["platform"]["namespace"]
    namespace          = dep_cfg.get("namespace") or platform_namespace
    models             = dep_cfg.get("models", [])
    trustyai_name    = dep_cfg.get("trustyai_service_name",    "trustyai-service")
    trustyai_sa      = dep_cfg.get("trustyai_service_account", "trustyai-user")
    trustyai_timeout = config["timeouts"].get("trustyai_ready", 300)
    staging_timeout  = config["timeouts"].get("staging_ready", 120)

    log.info("Deploying Fraud Detection")

    with elapsed_timer() as timer:
        # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI).
        op_name       = config["operator"]["name"]
        op_ns         = config["operator"]["namespace"]
        dsc_name      = config["dsc"]["name"]
        dsci_name     = config["dsc"]["dsci_name"]
        components    = config.get("components") or []
        component_str = (
            ", ".join(_COMPONENT_DISPLAY[c] if c in _COMPONENT_DISPLAY else c.title()
                      for c in components)
            if components else "all"
        )

        with header_step("Checking RHOAI platform", outcome="Platform ready"):
            needs_recon = prepare.platform_needs_reconciliation(config)
            if needs_recon:
                prepare.prepare_platform(config)
                if not operators.is_installed(op_name, op_ns):
                    with step("Installing RHOAI operator") as s:
                        log.debug("Operator: %s in %s", op_name, op_ns)
                        operators.install(
                            op_name, op_ns,
                            config["operator"]["channel"],
                            repo_root,
                            config["timeouts"]["operator_ready"],
                            version=config["operator"].get("version", ""),
                            source=config["operator"].get("source", "redhat-operators"),
                            source_namespace=config["operator"].get("source_namespace", "openshift-marketplace"),
                        )
                else:
                    with step("Waiting for RHOAI operator") as s:
                        log.debug("Operator: %s in %s", op_name, op_ns)
                        operators.wait_until_ready(op_name, op_ns, config["timeouts"]["operator_ready"])
                with step("Ensuring DSCInitialization") as s:
                    log.debug("DSCI name: %s", dsci_name)
                    dsc.apply_dsci(manifests.get_dsci(repo_root))
                    dsc.wait_dsci_ready(dsci_name, config["timeouts"]["dsc_ready"])
                if components:
                    with step("Ensuring DataScienceCluster") as s:
                        log.debug("DSC name: %s  components: %s", dsc_name, components)
                        if not ocp_resources.exists("DataScienceCluster", dsc_name):
                            dsc.apply_dsc(manifests.get_dsc(repo_root))
                        dsc.set_component_states(dsc_name, {c: "Managed" for c in components})
                        dsc.wait_until_ready(dsc_name, config["timeouts"]["dsc_ready"])
                else:
                    with step("Ensuring DataScienceCluster") as s:
                        log.debug("DSC name: %s", dsc_name)
                        dsc.apply_dsc(manifests.get_dsc(repo_root))
                        dsc.wait_until_ready(dsc_name, config["timeouts"]["dsc_ready"])
                with sub_step(f"Components enabled: {component_str}"):
                    pass
            else:
                with sub_step(f"Operator ready"):
                    pass
                with sub_step(f"DSCInitialization ready"):
                    pass
                with sub_step(f"DataScienceCluster ready"):
                    pass
                with sub_step(f"Components enabled: {component_str}"):
                    pass

        # 4 — S3 credentials (applied once if any model uses an S3 URI).
        # Models using model_path/config_path derive a pvc:// URI at deploy time —
        # they do not need an S3 secret regardless of their eventual model_uri value.
        if any(
            not m.get("model_uri", "").startswith(_NON_S3_SCHEMES)
            and not m.get("model_path")
            for m in models
        ):
            with step("Applying S3 storage credentials"):
                storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

        # 5 — Deploy each model; collect results for the summary.
        n_models = len(models)
        results: list[ModelResult] = []
        for idx, model in enumerate(models, start=1):
            counter = f" ({idx}/{n_models})" if n_models > 1 else ""
            with header_step(
                f"Deploying '{model['name']}'{counter}",
                outcome=f"'{model['name']}' ready",
            ):
                results.append(
                    _deploy_model(
                        model, repo_root, platform_namespace, namespace,
                        config["timeouts"]["inference_ready"],
                        staging_timeout=staging_timeout,
                    )
                )

        # 6 — TrustyAI prerequisites + service (only when at least one model has
        #     bias_monitoring configured; skipped entirely otherwise).
        route = ""
        token = ""
        bias_models = [m for m in models if m.get("bias_monitoring")]

        if bias_models:
            with header_step("Preparing TrustyAI", outcome="TrustyAI ready"):
                with step("Configuring monitoring"):
                    trustyai.enable_user_workload_monitoring(
                        manifests.get_trustyai_monitoring_config(repo_root)
                    )
                with step("Configuring permissions"):
                    log.debug("TrustyAI service account: %s", trustyai_sa)
                    trustyai.apply_rbac(manifests.get_trustyai_rbac(repo_root), namespace, trustyai_sa)
                with step("Configuring logging"):
                    log.debug("Applying logger CA bundle and patching inferenceservice-config")
                    trustyai.apply_logger_ca_bundle(
                        manifests.get_trustyai_logger_ca_bundle(repo_root), namespace
                    )
                    trustyai.patch_inferenceservice_config(platform_namespace)
                with step("Ensuring TrustyAI service"):
                    trustyai.apply_trustyai_service(
                        manifests.get_trustyai_service(repo_root), namespace
                    )
                with step("Waiting for TrustyAI to become ready") as s:
                    trustyai.wait_until_ready(
                        trustyai_name, namespace, trustyai_timeout, on_tick=s.tick
                    )
                # Wait for ISVC pods to stabilise after the logger sidecar rollout.
                # patch_inferenceservice_config() causes KServe to recycle every predictor
                # pod to inject the updated logger configuration and payload-logger sidecar
                # (resulting in 3 containers per pod).  TrustyAI does not depend on this,
                # but send_observations() posts directly to the model endpoint, so the pods
                # must be fully Ready before bias monitoring begins.
                isvc_stabilize_timeout = config["timeouts"].get("isvc_stabilize", 300)
                with step("Waiting for model pods to stabilise") as s:
                    inference.wait_until_all_ready(namespace, isvc_stabilize_timeout, on_tick=s.tick)

            # 7 — Bias monitoring configuration (per model).
            route = trustyai.get_url(trustyai_name, namespace)
            token = trustyai.get_bearer_token(trustyai_sa, namespace)
            ingestion_timeout = config["timeouts"].get("ingestion_ready", 300)

            n_bias = len(bias_models)
            for idx, model in enumerate(bias_models, start=1):
                counter = f" ({idx}/{n_bias})" if n_bias > 1 else ""
                with header_step(
                    f"Configuring bias monitoring for '{model['name']}'{counter}",
                    outcome=f"'{model['name']}' monitoring configured",
                ):
                    _configure_bias_monitoring(
                        model, route, token, namespace, repo_root, ingestion_timeout,
                    )

    # Summary.
    has_identity = any(
        m.get("bias_monitoring", {}).get("identity_monitors")
        for m in models
    )
    print_summary(
        results,
        use_case=config.get("_use_case", "fraud-detection"),
        namespace=namespace,
        config_file=config.get("_config_file", ""),
        trustyai_route=route,
        total=timer.formatted,
        show_identity=has_identity,
    )
