"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1. prepare_platform  — validate cluster, ensure namespace
    2. install operator  — RHOAI operator via OLM
    3. apply DSC/DSCI    — enable RHOAI components
    4. configure storage — S3 secret
    5. deploy model      — Triton ServingRuntime (via Template) + InferenceService
    6. apply TrustyAI    — monitoring config, patch inferenceservice-config,
                           deploy TrustyAIService (bias + drift monitoring)
"""

from typing import Any

from rhoai.platform import dsc, inference, manifests, operators, prepare, storage, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root = config["repo_root"]
    namespace = config["cluster"]["namespace"]
    fd_cfg    = config.get("fraud_detection", {})

    log.info("=== Deploying Fraud Detection ===")

    # 1 — cluster validation and namespace
    prepare.prepare_platform(config)

    # 2 — RHOAI operator
    op_name    = config["operator"]["name"]
    op_ns      = config["operator"]["namespace"]
    op_timeout = config["timeouts"]["operator_ready"]
    if not operators.is_installed(op_name, op_ns):
        operators.install(op_name, op_ns, config["operator"]["channel"], repo_root, op_timeout)
    else:
        operators.wait_until_ready(op_name, op_ns, op_timeout)

    # 3 — DataScienceCluster
    dsc.apply_dsci(manifests.get_dsci(repo_root))
    dsc.apply_dsc(manifests.get_dsc(repo_root))
    dsc.wait_until_ready(config["dsc"]["name"], config["timeouts"]["dsc_ready"])

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
