"""vLLM generative — cleanup.

Deletes use-case resources in reverse deploy order.
Platform resources (DSC, DSCI, operator) are managed by the CLI, not here.
Pass --delete-platform to 'rhoai usecase cleanup' to also remove them.
"""

from typing import Any

from rhoai.platform import inference
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def cleanup(config: dict[str, Any]) -> None:
    """Remove vLLM use-case resources from the cluster."""
    namespace = config["cluster"]["namespace"]
    vllm_cfg  = config.get("vllm", {})
    isvc_name = vllm_cfg.get("inference_service_name", "qwen")
    rt_name   = vllm_cfg.get("serving_runtime_name", "vllm-cpu-runtime")

    log.info("=== Cleaning up vLLM ===")

    # Reverse deploy order: InferenceService first, then ServingRuntime
    inference.delete_inference_service(isvc_name, namespace)
    inference.delete_serving_runtime(rt_name, namespace)

    log.info("=== vLLM cleanup complete ===")
