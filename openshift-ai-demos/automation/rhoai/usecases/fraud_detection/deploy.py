"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1-3. prepare.bootstrap_platform — validate cluster, operator, DSC/DSCI
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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rhoai.ocp import resources as ocp_resources
from rhoai.platform import inference, manifests, prepare, storage, trustyai, trustyai_client
from rhoai.platform.inference import EndpointUnreachable
from rhoai.usecases.fraud_detection import assets
from rhoai.utils import yaml_io
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import header_step, step, sub_step

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


@dataclass
class _ModelResult:
    """Outcome of a single model deployment."""
    name:               str
    model_uri:          str                        = ""
    endpoint:           str                        = ""
    validation_skipped: bool                       = False
    unreachable:        EndpointUnreachable | None = field(default=None, repr=False)


def _resolve_inference_request(model: dict[str, Any], repo_root: str) -> Path:
    """Return the absolute Path to this model's inference request file.

    The path is specified as ``inference_request`` in the model config entry,
    relative to ``repo_root``.  Raises ValueError when the field is absent or empty.
    """
    rel = model.get("inference_request", "")
    if not rel:
        raise ValueError(
            f"Model '{model.get('name', '?')}' has no inference_request configured. "
            "Set inference_request: <path relative to repo_root> in the model entry."
        )
    return Path(repo_root) / rel


def _deploy_model(
    model: dict[str, Any],
    repo_root: str,
    platform_namespace: str,
    namespace: str,
    inference_timeout: int,
) -> _ModelResult:
    """Deploy a single model: ServingRuntime, InferenceService, smoke test.

    Returns a _ModelResult that records whether validation was skipped.
    The caller is responsible for surfacing any warnings in the summary.
    """
    name         = model["name"]
    model_uri    = model.get("model_uri", "")
    runtime_name = assets.serving_runtime_name(name)

    with step("Configuring Triton ServingRuntime"):
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

    with step(f"Deploying service '{name}'") as s:
        ocp_resources.apply_dict(model_dict, namespace)
        inference.wait_until_ready(
            name, namespace, inference_timeout,
            on_tick=s.tick,
        )

    endpoint = inference.get_inference_url(name, namespace)
    result = _ModelResult(name=name, model_uri=model_uri, endpoint=endpoint)
    with step("Validating model inference") as s:
        try:
            inference.verify_triton_inference(
                name, namespace, name, _resolve_inference_request(model, repo_root)
            )
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
    files are returned in lexical filename order.  An empty directory raises
    ``ValueError``.

    ``files`` — an explicit ordered list of file paths (relative to repo_root).

    ``path`` and ``files`` must not both be set.

    Args:
        obs_cfg:   The ``bias_monitoring.observations`` sub-dict from the model config.
        repo_root: Absolute path to the repo root (used to resolve relative paths).

    Returns:
        Non-empty ordered list of absolute Path objects.

    Raises:
        ValueError: If the config is invalid (both keys set, neither key set,
                    directory is empty).
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
        paths = sorted(resolved.glob("*.json"), key=lambda p: p.name)
        if not paths:
            raise ValueError(
                f"Observation directory contains no *.json files: {resolved}"
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
        5. For each SPD monitor: validate via compute_spd, then schedule.
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
    obs_files = _resolve_observation_files(cfg["observations"], repo_root)
    total_sent = inference.send_observations(model_id, namespace, obs_files)

    # 3 — wait for TrustyAI to ingest the observations.
    trustyai.wait_for_ingestion(route, token, model_id, expected=total_sent,
                                timeout=ingestion_timeout)

    # 4 — optional name mapping.
    if nm := cfg.get("name_mapping"):
        trustyai_client.apply_name_mapping(
            route, token, model_id,
            nm.get("inputs", {}),
            nm.get("outputs", {}),
        )

    # 5 — SPD monitors: validate first, then schedule.
    for monitor in cfg.get("spd_monitors", []):
        kwargs = dict(monitor)
        trustyai_client.compute_spd(route, token, model_id, **kwargs)
        trustyai_client.schedule_spd(route, token, model_id, **kwargs)

    # 6 — identity monitors.
    for monitor in cfg.get("identity_monitors", []):
        trustyai_client.schedule_identity(
            route, token, model_id,
            column_name=monitor["column_name"],
            batch_size=monitor.get("batch_size", 5000),
        )


def _verify_cmd(use_case: str, config_file: str) -> str:
    """Return the copy-pasteable verify command, including -c if a config was used."""
    if config_file:
        return f"rhoai usecase verify {use_case} \\\n      -c {config_file}"
    return f"rhoai usecase verify {use_case}"


def _print_summary(
    results: list[_ModelResult],
    use_case: str,
    namespace: str,
    config_file: str = "",
    trustyai_route: str = "",
    mode: str = "deploy",
) -> None:
    """Print the end-of-command summary.

    Args:
        results:        Per-model outcomes collected during the run.
        use_case:       Use case name (e.g. "fraud-detection").
        namespace:      Workload namespace.
        config_file:    Path to the --config file used, for the verify command hint.
        trustyai_route: TrustyAI service URL; omitted from output when empty.
        mode:           "deploy" — prints "Deployment complete." and a "Next / verify" hint.
                        "verify" — prints "Verification complete." and no "Next" hint.
    """
    verify_cmd = _verify_cmd(use_case, config_file)

    heading = "Deployment complete." if mode == "deploy" else "Verification complete."
    _console.print(f"\n{heading}\n")
    _console.print(f"  Use case  : {use_case}")
    _console.print(f"  Namespace : {namespace}\n")

    # --- Per-model detail blocks ---
    _console.print("Models\n")
    for r in results:
        validation = "Unavailable" if r.validation_skipped else "Passed"
        source     = r.model_uri or "(from manifest)"
        _console.print(f"\u2714  {r.name}\n")
        _console.print(f"  Source      : {source}")
        _console.print(f"  Endpoint    : {r.endpoint}")
        _console.print(f"  Status      : Ready")
        _console.print(f"  Validation  : {validation}\n")

    # --- TrustyAI ---
    if trustyai_route:
        _console.print("TrustyAI\n")
        _console.print(f"  Endpoint    : {trustyai_route}\n")

    # --- Follow-up actions (shown in both modes when validation was skipped) ---
    unvalidated = [r for r in results if r.validation_skipped]
    if unvalidated:
        _console.print("Follow-up actions\n")
        for r in unvalidated:
            _console.print(f"\u26a0  {r.name}\n")
            if r.unreachable:
                _console.print(f"  Endpoint:\n    {r.unreachable.infer_url}\n")
                log.debug("Manual validation: %s", r.unreachable.curl_cmd)
            _console.print(
                "  Model inference could not be validated because the endpoint\n"
                "  was not reachable from this machine.\n\n"
                "  Verify the cluster route is reachable from your workstation.\n\n"
                "  If hostname resolution fails, check your DNS or /etc/hosts configuration.\n\n"
                f"  Then rerun:\n\n"
                f"    {verify_cmd}\n"
            )

    # --- Next steps: deploy only ---
    if mode == "deploy":
        _console.print(f"Next\n\n  {verify_cmd}\n")


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

    log.info("Deploying Fraud Detection")

    # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI).
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
            prepare.bootstrap_platform(config, _needs_reconciliation=True)
        with sub_step("Operator ready"):
            pass
        with sub_step(f"DSCI '{dsci_name}' ready"):
            pass
        with sub_step(f"DSC '{dsc_name}' ready"):
            pass
        with sub_step(f"Components enabled: {component_str}"):
            pass

    # 4 — S3 credentials (applied once if any model uses an S3 URI).
    if any(
        not m.get("model_uri", "").startswith(_NON_S3_SCHEMES)
        for m in models
    ):
        with step("Configuring model storage credentials"):
            storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

    # 5 — Deploy each model; collect results for the summary.
    results: list[_ModelResult] = []
    for model in models:
        with header_step(f"Deploying '{model['name']}'", outcome=f"'{model['name']}' ready"):
            results.append(
                _deploy_model(
                    model, repo_root, platform_namespace, namespace,
                    config["timeouts"]["inference_ready"],
                )
            )

    # 6 — TrustyAI prerequisites + service (only when at least one model has
    #     bias_monitoring configured; skipped entirely otherwise).
    route = ""
    token = ""
    bias_models = [m for m in models if m.get("bias_monitoring")]

    if bias_models:
        with step("Deploying TrustyAI"):
            trustyai.enable_user_workload_monitoring(manifests.get_trustyai_monitoring_config(repo_root))
            trustyai.apply_rbac(manifests.get_trustyai_rbac(repo_root), namespace, trustyai_sa)
            trustyai.create_logger_ca_bundle(namespace)
            trustyai.patch_inferenceservice_config(platform_namespace)
            trustyai.apply_trustyai_service(
                assets.get_trustyai_service_manifest(repo_root), namespace
            )

        with step("Waiting for TrustyAI to become ready") as s:
            trustyai.wait_until_ready(trustyai_name, namespace, trustyai_timeout, on_tick=s.tick)

        # 7 — Bias monitoring configuration (per model).
        route = trustyai.get_url(trustyai_name, namespace)
        token = trustyai.get_bearer_token(trustyai_sa, namespace)
        ingestion_timeout = config["timeouts"].get("ingestion_ready", 300)

        for model in bias_models:
            with step(f"Configuring TrustyAI for '{model['name']}'") as s:
                _configure_bias_monitoring(
                    model, route, token, namespace, repo_root, ingestion_timeout,
                )

    # 8 — Deployment summary.
    _print_summary(
        results,
        use_case=config.get("_use_case", "fraud-detection"),
        namespace=namespace,
        config_file=config.get("_config_file", ""),
        trustyai_route=route,
    )
