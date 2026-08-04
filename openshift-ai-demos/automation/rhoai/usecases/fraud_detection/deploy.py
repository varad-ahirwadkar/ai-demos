"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1-3. deploy_platform — validate cluster, operator, DSC/DSCI
    4.   configure storage — S3 secret
    5.   deploy model      — Triton ServingRuntime (via Template) + InferenceService
    6.   apply TrustyAI    — monitoring config, patch inferenceservice-config,
                             deploy TrustyAIService (bias + drift monitoring)
"""

from typing import Any

from rhoai.platform import inference, manifests, prepare, storage, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root = config["repo_root"]
    namespace = config["cluster"]["namespace"]
    fd_cfg    = config.get("fraud_detection", {})

    log.info("=== Deploying Fraud Detection ===")

    # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI)
    prepare.deploy_platform(config)

    # 4 — S3 credentials
    storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

    # 5 — Triton ServingRuntime (from Template) + predictive model InferenceService
    inference.apply_serving_runtime_from_template(
        assets.get_serving_runtime_template(repo_root), namespace
    )
    inference.apply_inference_service(assets.get_model_manifest(repo_root), namespace)
    isvc_name = fd_cfg.get("inference_service_name", "fraud-detection")
    inference.wait_until_ready(isvc_name, namespace, config["timeouts"]["inference_ready"])

    # 6 — TrustyAI Service (bias + data-drift monitoring for the predictor above)
    trustyai_name    = fd_cfg.get("trustyai_service_name", "trustyai-service")
    trustyai_timeout = config["timeouts"].get("trustyai_ready", 300)
    trustyai.apply_monitoring_config(assets.get_trustyai_monitoring_manifest(repo_root))
    trustyai.patch_inferenceservice_config(namespace)
    trustyai.apply_trustyai_service(assets.get_trustyai_service_manifest(repo_root), namespace)
    trustyai.wait_until_ready(trustyai_name, namespace, trustyai_timeout)

    log.info("=== Fraud Detection deployment complete ===")
