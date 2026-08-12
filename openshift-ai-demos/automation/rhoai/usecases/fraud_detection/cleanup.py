"""Fraud Detection — cleanup.

Deletes use-case resources in reverse deploy order.
Platform resources (DSC, DSCI, operator) are managed by the CLI, not here.
Pass --delete-platform to 'rhoai usecase cleanup' to also remove them.
"""

from typing import Any

from rhoai.platform import inference, trustyai
from rhoai.usecases.fraud_detection import assets
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import step

log = get_logger(__name__)


def cleanup(config: dict[str, Any]) -> None:
    """Remove Fraud Detection use-case resources from the cluster."""
    dep_cfg       = config.get("deployment", {})
    namespace     = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name     = dep_cfg.get("inference_service_name", "fraud-detection")
    trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")
    sa_name       = dep_cfg.get("trustyai_service_account", "trustyai-user")

    log.info("Cleaning up Fraud Detection in '%s'", namespace)

    # Reverse deploy order: TrustyAI first, then model serving
    with step(f"Removing TrustyAI '{trustyai_name}'"):
        trustyai.delete_trustyai_service(trustyai_name, namespace)
        trustyai.delete_role_binding(f"{sa_name}-view", namespace)
        trustyai.delete_service_account(sa_name, namespace)

    with step(f"Removing InferenceService '{isvc_name}'"):
        inference.delete_inference_service(isvc_name, namespace)

    with step(f"Removing ServingRuntime '{assets.SERVING_RUNTIME_NAME}'"):
        inference.delete_serving_runtime(assets.SERVING_RUNTIME_NAME, namespace)
