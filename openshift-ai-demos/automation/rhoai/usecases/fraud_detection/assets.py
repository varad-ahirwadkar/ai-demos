"""Asset path resolution for the Fraud Detection use case.

The only file that knows where fraud-detection manifests live on disk.
Shared platform manifests are delegated to platform.manifests — only
fraud-detection-specific paths are resolved here.
"""

from pathlib import Path

from rhoai.platform import manifests


def serving_runtime_name(model_name: str) -> str:
    """Return the ServingRuntime resource name for a given model.

    Convention: ``triton-<model_name>``.  Each model deployment creates its
    own ServingRuntime so that Triton's ``--load-model`` flag is correct for
    that model and runtimes never overwrite each other.

    This value is passed as RUNTIME_NAME to the Triton Template and must match
    the ``spec.predictor.model.runtime`` field in the InferenceService manifest.
    """
    return f"triton-{model_name}"


def get_serving_runtime_template(repo_root: str | Path) -> Path:
    """Return the path to the Triton ServingRuntime OpenShift Template.

    The Template is processed via ``oc process`` before the ServingRuntime
    CR is created — see platform.inference.apply_serving_runtime_from_template().

    Returns:
        Path to model-serving/predictive-models/triton/triton-ppc64le-runtime-template.yaml
    """
    return manifests.get_triton_serving_runtime_template(repo_root)


def get_model_manifest(repo_root: str | Path) -> Path:
    """Return the path to the Fraud Detection InferenceService manifest.

    Returns:
        Path to model-serving/predictive-models/triton/fraud-detection.yaml
    """
    return (
        Path(repo_root)
        / "model-serving"
        / "predictive-models"
        / "triton"
        / "fraud-detection.yaml"
    )



def get_trustyai_service_manifest(repo_root: str | Path) -> Path:
    """Return the path to the TrustyAIService CR manifest.

    Returns:
        Path to trustyai/service/trustyai-service.yaml
    """
    return Path(repo_root) / "trustyai" / "service" / "trustyai-service.yaml"


