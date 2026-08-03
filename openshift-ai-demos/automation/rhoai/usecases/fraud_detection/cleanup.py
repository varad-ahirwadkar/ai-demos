"""Fraud Detection — cleanup.

Deletes use-case resources in reverse deploy order.
Platform resources (DSC, DSCI, operator) are managed by the CLI, not here.
Pass --delete-platform to 'rhoai usecase cleanup' to also remove them.

Each model has its own dedicated ServingRuntime (named via assets.serving_runtime_name).
Both the InferenceService and its ServingRuntime are deleted per model.
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
    models        = dep_cfg.get("models", [])
    trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")
    sa_name       = dep_cfg.get("trustyai_service_account", "trustyai-user")

    log.info("Cleaning up Fraud Detection in '%s'", namespace)

    # Reverse deploy order: TrustyAI first, then model serving.
    with step(f"Removing TrustyAI '{trustyai_name}'"):
        trustyai.delete_trustyai_service(trustyai_name, namespace)
        trustyai.delete_role_binding(f"{sa_name}-view", namespace)
        trustyai.delete_service_account(sa_name, namespace)

    for model in models:
        name         = model["name"]
        runtime_name = assets.serving_runtime_name(name)
        with step(f"Removing InferenceService '{name}'"):
            inference.delete_inference_service(name, namespace)
        with step(f"Removing ServingRuntime '{runtime_name}'"):
            inference.delete_serving_runtime(runtime_name, namespace)
