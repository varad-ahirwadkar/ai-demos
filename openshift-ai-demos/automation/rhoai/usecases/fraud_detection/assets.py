"""Fraud Detection use-case assets.

Two responsibilities:

    Path resolution  — the only file that knows where fraud-detection
                       manifests live on disk.  Shared platform manifests
                       are delegated to platform.manifests.

    Use-case types   — data types and config helpers shared by deploy.py
                       and verify.py so neither module depends on the other.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhoai.platform import manifests
from rhoai.platform.inference import EndpointUnreachable


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


# ---------------------------------------------------------------------------
# Use-case types
# ---------------------------------------------------------------------------

@dataclass
class ModelResult:
    """Outcome of a single model deploy or verify operation."""
    name:               str
    model_uri:          str                        = ""
    endpoint:           str                        = ""
    validation_skipped: bool                       = False
    unreachable:        EndpointUnreachable | None = field(default=None, repr=False)


def resolve_inference_request(model: dict[str, Any], repo_root: str) -> Path:
    """Return the absolute Path to this model's inference request file.

    The path is specified as ``inference_request`` in the model config entry,
    relative to ``repo_root``.  Raises ValueError when the field is absent or empty.
    """
    rel = model.get("inference_request", "")
    if not rel:
        raise ValueError(
            f"Model '{model.get('name', '?')}' has no inference_request configured. "
            "Set inference_request: <path relative to repo_root> in the model entry."
        )
    return Path(repo_root) / rel
