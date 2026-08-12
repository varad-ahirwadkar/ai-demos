"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1-3. prepare.bootstrap_platform — validate cluster, operator, DSC/DSCI
    4.   configure storage — S3 secret (skipped when model_uri is a non-S3 URI)
    5.   deploy model      — Triton ServingRuntime (via Template) + InferenceService
    6.   apply TrustyAI    — monitoring config, patch inferenceservice-config,
                             deploy TrustyAIService (bias + drift monitoring)

model_uri behaviour (deployment.model_uri in config):
    unset / empty       — use the manifest file unchanged; apply S3 secret
    pvc://, hf://, oci:// — set storageUri, remove storage block + S3 annotation,
                            skip S3 secret (model is self-contained)
    any other string    — treat as S3 path; update storage.path, apply S3 secret
"""

from typing import Any

from rhoai.ocp import resources as ocp_resources
from rhoai.platform import inference, manifests, prepare, storage
# from rhoai.platform import trustyai  # phase 2
from rhoai.usecases.fraud_detection import assets
from rhoai.utils import yaml_io
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import header_step, step, sub_step

log = get_logger(__name__)

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


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root          = config["repo_root"]
    dep_cfg            = config.get("deployment", {})
    platform_namespace = config["platform"]["namespace"]
    namespace          = dep_cfg.get("namespace") or platform_namespace
    model_uri          = dep_cfg.get("model_uri", "")
    isvc_name          = dep_cfg.get("inference_service_name", "fraud-detection")
    # phase 2: trustyai_name    = dep_cfg.get("trustyai_service_name", "trustyai-service")
    # phase 2: trustyai_timeout = config["timeouts"].get("trustyai_ready", 300)

    log.info("Deploying Fraud Detection")

    # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI).
    #
    # platform_needs_reconciliation() is called inside header_step so its
    # work (several read-only API calls) is included in the elapsed time.
    #
    # Path 1 (fast-path): platform already matches desired state.
    #   Sub-steps display the result of each check already performed above.
    #
    # Path 2 (reconciliation): bootstrap_platform() writes + waits.
    #   Sub-steps display a config-derived summary — no re-verification.
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

    # 4 — S3 credentials (skipped when the model URI is self-contained)
    if not model_uri or not model_uri.startswith(_NON_S3_SCHEMES):
        with step("Configuring model storage credentials"):
            storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

    # 5 — Triton ServingRuntime (from Template) + predictive model InferenceService
    with step("Configuring Triton ServingRuntime"):
        inference.apply_serving_runtime_from_template(
            assets.get_serving_runtime_template(repo_root), platform_namespace, namespace,
            model_name=isvc_name,
        )

    model_dict = yaml_io.load(assets.get_model_manifest(repo_root))
    # Always stamp the configured name onto the manifest so the ISVC is created
    # with the right name regardless of what is hardcoded in the file.
    model_dict["metadata"]["name"] = isvc_name
    if model_uri:
        model_spec = model_dict["spec"]["predictor"]["model"]
        if model_uri.startswith(_NON_S3_SCHEMES):
            # Replace S3 storage block with a self-contained storageUri
            model_spec.pop("storage", None)
            model_spec["storageUri"] = model_uri
            model_dict["metadata"]["annotations"].pop(
                "opendatahub.io/connection-type-ref", None
            )
        else:
            # Plain S3 path — update path only, keep existing key
            model_spec.setdefault("storage", {})["path"] = model_uri

    with step(f"Deploying model '{isvc_name}'") as s:
        ocp_resources.apply_dict(model_dict, namespace)
        inference.wait_until_ready(
            isvc_name, namespace, config["timeouts"]["inference_ready"],
            on_tick=s.tick,
        )

    # 5b — smoke test: confirm the model is reachable and serving requests
    with step("Validating model inference"):
        inference.verify_triton_inference(
            isvc_name, namespace, isvc_name, assets.get_sample_inference_request()
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
