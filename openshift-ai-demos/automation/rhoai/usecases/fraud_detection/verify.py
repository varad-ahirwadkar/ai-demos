"""Fraud Detection — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then use-case-specific checks.
"""

from typing import Any

from rhoai.platform import inference, trustyai
from rhoai.platform import verify as platform_verify
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def verify(config: dict[str, Any]) -> None:
    """Verify the Fraud Detection deployment is healthy."""
    log.info("=== Verifying Fraud Detection ===")

    platform_verify.verify_platform(config)

    dep_cfg       = config.get("deployment", {})
    namespace     = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name     = dep_cfg.get("inference_service_name", "fraud-detection")
    trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")

    log.info("Checking InferenceService '%s'", isvc_name)
    inference.verify(namespace, name=isvc_name)

    log.info("Smoke-testing Triton inference for '%s'", isvc_name)
    inference.verify_triton_inference(
        isvc_name, namespace, "fraud-detection", assets.get_sample_inference_request()
    )

    log.info("Checking TrustyAIService '%s'", trustyai_name)
    trustyai.verify(trustyai_name, namespace)

    log.info("=== Fraud Detection verification passed ===")
