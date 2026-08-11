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
from rhoai.platform import inference, manifests, prepare, storage, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils import yaml_io
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

_NON_S3_SCHEMES = ("pvc://", "hf://", "oci://")


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root          = config["repo_root"]
    dep_cfg            = config.get("deployment", {})
    platform_namespace = config["platform"]["namespace"]
    namespace          = dep_cfg.get("namespace") or platform_namespace
    model_uri          = dep_cfg.get("model_uri", "")

    log.info("Deploying Fraud Detection")

    # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI)
    prepare.bootstrap_platform(config)

    # 4 — S3 credentials (skipped when the model URI is self-contained)
    if not model_uri or not model_uri.startswith(_NON_S3_SCHEMES):
        storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

    # 5 — Triton ServingRuntime (from Template) + predictive model InferenceService
    isvc_name = dep_cfg.get("inference_service_name", "fraud-detection")
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

    log.info("Deploying InferenceService '%s'", isvc_name)
    ocp_resources.apply_dict(model_dict, namespace)

    inference.wait_until_ready(isvc_name, namespace, config["timeouts"]["inference_ready"])

    # 5b — smoke test: confirm the model is reachable and serving requests
    inference.verify_triton_inference(
        isvc_name, namespace, isvc_name, assets.get_sample_inference_request()
    )

    # 6 — TrustyAI prerequisites + service (bias + data-drift monitoring)
    trustyai_name    = dep_cfg.get("trustyai_service_name", "trustyai-service")
    trustyai_timeout = config["timeouts"].get("trustyai_ready", 300)
    rbac_path        = manifests.get_trustyai_rbac(repo_root)
    trustyai.enable_user_workload_monitoring(manifests.get_trustyai_monitoring_config(repo_root))
    trustyai.apply_rbac(rbac_path, namespace)
    trustyai.create_logger_ca_bundle(namespace)
    trustyai.patch_inferenceservice_config(namespace)
    trustyai.apply_trustyai_service(
        assets.get_trustyai_service_manifest(repo_root), namespace
    )
    trustyai.wait_until_ready(trustyai_name, namespace, trustyai_timeout)
