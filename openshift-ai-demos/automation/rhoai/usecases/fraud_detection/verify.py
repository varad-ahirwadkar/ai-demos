"""Fraud Detection — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then use-case-specific checks.
"""

from typing import Any

from rhoai.platform import inference
# from rhoai.platform import trustyai  # phase 2
from rhoai.platform import verify as platform_verify
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import step

log = get_logger(__name__)


def verify(config: dict[str, Any]) -> None:
    """Verify the Fraud Detection deployment is healthy."""
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name = dep_cfg.get("inference_service_name", "fraud-detection")
    # phase 2: trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")

    log.info("Verifying Fraud Detection in '%s'", namespace)

    with step("Checking platform"):
        platform_verify.verify_platform(config)

    with step(f"Checking InferenceService '{isvc_name}'"):
        inference.verify(namespace, name=isvc_name)

    with step("Validating model inference"):
        inference.verify_triton_inference(
            isvc_name, namespace, isvc_name, assets.get_sample_inference_request()
        )

    # phase 2:
    # with step(f"Checking TrustyAI '{trustyai_name}'"):
    #     trustyai.verify(trustyai_name, namespace)
