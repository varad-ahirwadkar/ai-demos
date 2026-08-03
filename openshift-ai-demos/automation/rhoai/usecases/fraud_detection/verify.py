"""Fraud Detection — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then use-case-specific checks.
"""

from typing import Any

from rhoai.platform import inference, trustyai
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def verify(config: dict[str, Any]) -> None:
    """Verify the Fraud Detection deployment is healthy."""
    log.info("=== Verifying Fraud Detection ===")

    platform_verify.verify_platform(config)

    namespace = config["cluster"]["namespace"]
    fd_cfg    = config.get("fraud_detection", {})
    isvc_name = fd_cfg.get("inference_service_name", "qwen")

    log.info("Checking InferenceService '%s'", isvc_name)
    inference.verify(namespace, name=isvc_name)

    log.info("Checking GuardrailsOrchestrator")
    trustyai.verify(namespace)

    log.info("=== Fraud Detection verification passed ===")
