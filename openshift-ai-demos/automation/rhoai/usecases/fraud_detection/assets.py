"""Asset path resolution for the Fraud Detection use case.

The only file that knows where fraud-detection manifests live on disk.
Shared platform manifests are delegated to platform.manifests — only
fraud-detection-specific paths are resolved here.

Internal constants (not user-facing config):
    SERVING_RUNTIME_NAME  — the ServingRuntime resource name created by the Triton Template.
                            Used by cleanup to delete it; never exposed in defaults.yaml.
"""

from pathlib import Path

from rhoai.platform import manifests

# The ServingRuntime name produced by the Triton OpenShift Template.
# Matches metadata.name inside triton-ppc64le-runtime-template.yaml.
# Cleanup reads this constant directly — users never need to configure it.
SERVING_RUNTIME_NAME = "triton-ppc64le-runtime"


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


def get_sample_inference_request() -> Path:
    """Return the path to the KServe v2 sample inference payload.

    The file lives alongside this package, so no repo_root is needed.
    Used by verify_triton_inference() as the smoke-test request body.

    Returns:
        Path to usecases/fraud_detection/data/sample-fraud.json
    """
    return Path(__file__).parent / "data" / "sample-fraud.json"
