"""Fraud Detection — cleanup.

Deletes use-case resources in reverse deploy order.
Platform resources (DSC, DSCI, operator) are left intact by default
because they may be shared with other use cases.
"""

from typing import Any

from rhoai.platform import dsc, inference, trustyai
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def cleanup(config: dict[str, Any], delete_platform: bool = False) -> None:
    """Remove Fraud Detection resources from the cluster.

    Pass delete_platform=True to also remove DSC and DSCI.
    """
    namespace = config["cluster"]["namespace"]
    fd_cfg    = config.get("fraud_detection", {})
    isvc_name = fd_cfg.get("inference_service_name", "qwen")
    rt_name   = fd_cfg.get("serving_runtime_name", "vllm-cpu-runtime")

    log.info("=== Cleaning up Fraud Detection ===")

    # 1 — TrustAI guardrails (includes Prometheus rules and ConfigMaps)
    trustyai.delete_guardrails("guardrails-orchestrator", namespace)

    # 2 — model serving
    inference.delete_inference_service(isvc_name, namespace)
    inference.delete_serving_runtime(rt_name, namespace)

    # 3 — platform (only if explicitly requested)
    if delete_platform:
        log.warning("Deleting platform resources (DSC, DSCI)")
        dsc.delete_dsc(config["dsc"]["name"])
        dsc.delete_dsci(config["dsc"]["dsci_name"])

    log.info("=== Fraud Detection cleanup complete ===")
