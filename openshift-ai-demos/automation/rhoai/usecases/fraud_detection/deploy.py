"""Fraud Detection — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1. prepare_platform  — validate cluster, ensure namespace
    2. install operator  — RHOAI operator via OLM
    3. apply DSC/DSCI    — enable RHOAI components
    4. configure storage — S3 secret
    5. deploy model      — ServingRuntime + InferenceService
    6. apply TrustAI     — guardrails manifests
    7. apply alerts      — Prometheus rules
"""

from typing import Any

from rhoai.platform import dsc, inference, manifests, operators, prepare, storage, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def deploy(config: dict[str, Any]) -> None:
    """Deploy the complete Fraud Detection solution."""
    repo_root  = config["repo_root"]
    namespace  = config["cluster"]["namespace"]
    fd_cfg     = config.get("fraud_detection", {})
    model_name = fd_cfg.get("model_name", "qwen2.5-1.5b-instruct")

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

    # 5 — model serving
    inference.apply_serving_runtime(assets.get_serving_runtime_manifest(repo_root), namespace)
    inference.apply_inference_service(assets.get_model_manifest(repo_root, model_name), namespace)
    isvc_name = fd_cfg.get("inference_service_name", "qwen")
    inference.wait_until_ready(isvc_name, namespace, config["timeouts"]["inference_ready"])

    # 6 — TrustAI guardrails
    trustyai.apply_guardrails(assets.get_trustyai_guardrails_manifests(repo_root), namespace)

    # 7 — Prometheus alerts
    trustyai.apply_prometheus_rules(assets.get_prometheus_rules_manifest(repo_root), namespace)

    log.info("=== Fraud Detection deployment complete ===")
