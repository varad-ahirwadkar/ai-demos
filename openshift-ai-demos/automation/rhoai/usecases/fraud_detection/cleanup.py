"""Fraud Detection — cleanup.

Deletes use-case resources in reverse deploy order.
Platform resources (DSC, DSCI, operator) are managed by the CLI, not here.
Pass --delete-platform to 'rhoai usecase cleanup' to also remove them.
"""

from typing import Any

from rhoai.platform import inference, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def cleanup(config: dict[str, Any]) -> None:
    """Remove Fraud Detection use-case resources from the cluster."""
    namespace     = config["cluster"]["namespace"]
    fd_cfg        = config.get("fraud_detection", {})
    isvc_name     = fd_cfg.get("inference_service_name", "fraud-detection")
    trustyai_name = fd_cfg.get("trustyai_service_name", "trustyai-service")

    log.info("=== Cleaning up Fraud Detection ===")

    # Reverse deploy order: TrustyAI first, then model serving
    trustyai.delete_trustyai_service(trustyai_name, namespace)
    inference.delete_inference_service(isvc_name, namespace)
    # Runtime name comes from the assets constant — not user-facing config
    inference.delete_serving_runtime(assets.SERVING_RUNTIME_NAME, namespace)

    log.info("=== Fraud Detection cleanup complete ===")
