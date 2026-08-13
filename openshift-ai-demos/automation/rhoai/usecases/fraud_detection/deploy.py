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
    6.   apply TrustyAI (phase 2)

model_uri behaviour (per model entry in deployment.models):
    pvc://, hf://, oci:// — set storageUri, remove storage block + S3 annotation,
                            skip S3 secret (model is self-contained)
    any other string      — treat as S3 path; update storage.path, apply S3 secret
"""

from pathlib import Path
from typing import Any

from rich.console import Console
from rhoai.ocp import resources as ocp_resources
from rhoai.platform import inference, manifests, prepare, storage
from rhoai.platform.inference import EndpointUnreachable
# from rhoai.platform import trustyai  # phase 2
from rhoai.usecases.fraud_detection import assets
from rhoai.utils import yaml_io
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import header_step, step, sub_step

log = get_logger(__name__)
_console = Console(stderr=False, highlight=False)


def _warn_unreachable(exc: EndpointUnreachable) -> None:
    """Print a concise, user-oriented message when an endpoint cannot be reached."""
    _console.print("\n\u26a0  Unable to reach the inference endpoint.\n")
    _console.print(f"  Endpoint:\n    {exc.infer_url}\n")
    _console.print(
        "  Possible causes:\n"
        "    \u2022 Endpoint is not reachable from this machine.\n"
        "    \u2022 Hostname cannot be resolved.\n"
        "    \u2022 Route is not accessible.\n"
    )
    _console.print(
        "  Please verify:\n"
        "    \u2022 The endpoint is reachable from your workstation.\n"
        "    \u2022 DNS resolution or /etc/hosts entries are correctly configured.\n"
    )
    _console.print(f"  Manual validation:\n    {exc.curl_cmd}\n")


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
) -> None:
    """Deploy a single model: ServingRuntime, InferenceService, smoke test."""
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

    with step("Validating model inference") as s:
        try:
            inference.verify_triton_inference(
                name, namespace, name, _resolve_inference_request(model, repo_root)
            )
        except EndpointUnreachable as exc:
            s.skip()
            _warn_unreachable(exc)


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root          = config["repo_root"]
    dep_cfg            = config.get("deployment", {})
    platform_namespace = config["platform"]["namespace"]
    namespace          = dep_cfg.get("namespace") or platform_namespace
    models             = dep_cfg.get("models", [])
    # phase 2: trustyai_name    = dep_cfg.get("trustyai_service_name", "trustyai-service")
    # phase 2: trustyai_timeout = config["timeouts"].get("trustyai_ready", 300)

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

    # 5 — Deploy each model.
    for model in models:
        with header_step(f"Deploying '{model['name']}'", outcome=f"'{model['name']}' ready"):
            _deploy_model(
                model, repo_root, platform_namespace, namespace,
                config["timeouts"]["inference_ready"],
            )

    # 6 — TrustyAI prerequisites + service (bias + data-drift monitoring)
    # with step("Deploying TrustyAI"):
    #     rbac_path = manifests.get_trustyai_rbac(repo_root)
    #     trustyai.enable_user_workload_monitoring(manifests.get_trustyai_monitoring_config(repo_root))
    #     trustyai.apply_rbac(rbac_path, namespace)
    #     trustyai.create_logger_ca_bundle(namespace)
    #     trustyai.patch_inferenceservice_config(platform_namespace)
    #     trustyai.apply_trustyai_service(
    #         assets.get_trustyai_service_manifest(repo_root), namespace
    #     )

    # with step("Waiting for TrustyAI to become ready") as s:
    #     trustyai.wait_until_ready(trustyai_name, namespace, trustyai_timeout, on_tick=s.tick)
