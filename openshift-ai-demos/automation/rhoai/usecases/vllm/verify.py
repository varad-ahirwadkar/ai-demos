"""vLLM generative — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then use-case-specific checks.
"""

from typing import Any

from rhoai.platform import inference
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def verify(config: dict[str, Any]) -> None:
    """Verify the vLLM deployment is healthy."""
    log.info("=== Verifying vLLM ===")

    platform_verify.verify_platform(config)

    namespace = config["cluster"]["namespace"]
    vllm_cfg  = config.get("vllm", {})
    isvc_name = vllm_cfg.get("inference_service_name", "qwen")

    log.info("Checking InferenceService '%s'", isvc_name)
    inference.verify(namespace, name=isvc_name)

    log.info("=== vLLM verification passed ===")
