"""Fraud Detection use-case assets.

Three responsibilities:

    Path resolution  — the only file that knows where fraud-detection
                       manifests live on disk.  Shared platform manifests
                       are delegated to platform.manifests.

    Triton layout    — builds the file map that storage.copy_files_to_pvc
                       needs to construct the Triton repository structure on a PVC.
                       The ``<model>/1/<file>`` convention lives here, not in
                       platform/storage.py (which is format-agnostic).

    Use-case types   — data types and config helpers shared by deploy.py
                       and verify.py so neither module depends on the other.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rhoai.platform import manifests
from rhoai.platform.inference import EndpointUnreachable

# Triton requires model files under a versioned sub-directory.
# Version "1" is the conventional first version used throughout this framework.
_TRITON_MODEL_VERSION = "1"


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


def triton_file_map(
    model_name: str,
    model_file: Path,
    config_file: Path,
) -> dict[str, Path]:
    """Return the file map for a Triton model repository on a PVC.

    Encodes the Triton directory layout convention so that no other module
    needs to know about it.  Pass the returned dict directly to
    ``storage.copy_files_to_pvc()``.

    The resulting structure on the PVC will be:

        <model_name>/
          config.pbtxt          ← config_file
          1/
            <model_file.name>   ← model_file  (filename preserved)

    Args:
        model_name:  Top-level directory name on the PVC (matches the ISVC name).
        model_file:  Local path to the model file (e.g. model.onnx).
        config_file: Local path to the Triton config file (config.pbtxt).

    Returns:
        Dict mapping absolute PVC destination paths to local source Paths,
        ready to pass to ``storage.copy_files_to_pvc(files=...)``.
    """
    base = f"/mnt/pvc/{model_name}"
    return {
        f"{base}/{_TRITON_MODEL_VERSION}/{model_file.name}": model_file,
        f"{base}/{config_file.name}": config_file,
    }


def triton_pvc_uri(pvc_name: str, model_name: str) -> str:  # noqa: ARG001
    """Return the KServe ``pvc://`` URI for a staged Triton model.

    KServe resolves ``pvc://<name>`` by mounting the PVC root as
    ``/mnt/models``.  Triton is started with
    ``--model-repository=/mnt/models``, so it expects to find the model
    directory (e.g. ``<model_name>/``) *directly inside* that mount point.

    The staging layout on the PVC is therefore::

        <model_name>/
          config.pbtxt
          1/
            model.onnx

    which Triton sees as ``/mnt/models/<model_name>/`` — exactly what
    ``--load-model=<model_name>`` needs.

    A sub-path in the URI (``pvc://<name>/<model_name>``) would cause KServe
    to descend into the model directory before mounting, presenting its
    *contents* as ``/mnt/models``.  Triton would then look for a sub-directory
    named ``<model_name>`` inside the model directory itself and fail with
    "model not found in any model repository".

    Args:
        pvc_name:   Name of the PVC the model was staged onto.
        model_name: Unused — kept for a consistent call-site signature so
                    callers do not need to special-case this function.

    Returns:
        ``pvc://<pvc_name>``  (no sub-path)
    """
    return f"pvc://{pvc_name}"


# ---------------------------------------------------------------------------
# Use-case types
# ---------------------------------------------------------------------------

@dataclass
class ModelResult:
    """Outcome of a single model deploy or verify operation."""
    name:               str
    model_uri:          str                        = ""
    endpoint:           str                        = ""
    inference_input:    dict[str, Any] | None      = field(default=None, repr=False)
    inference_output:   dict[str, Any] | None      = field(default=None, repr=False)
    curl_cmd:           str                        = ""
    request_path:       Path | None                = field(default=None, repr=False)
    validation_skipped: bool                       = False
    unreachable:        EndpointUnreachable | None = field(default=None, repr=False)


def resolve_inference_request(model: dict[str, Any], repo_root: str) -> Path | None:
    """Return the absolute Path to this model's inference request file, if set."""
    rel = model.get("inference_request", "")
    if not rel:
        return None
    return Path(repo_root) / rel



def resolve_inference_dataset(model: dict[str, Any], repo_root: str) -> Path:
    """Return the absolute Path to the dataset used to auto-generate a request."""
    rel = model.get("inference_dataset", "")
    if not rel:
        raise ValueError(
            f"Model '{model.get('name', '?')}' has no inference_request or inference_dataset configured. "
            "Set inference_request: <json/csv path> or inference_dataset: <csv path relative to repo_root>."
        )
    return Path(repo_root) / rel


def render_curl_command(infer_url: str, payload: dict[str, Any]) -> str:
    """Return a copy-pasteable curl command with the request payload inline."""
    body = json.dumps(payload, separators=(",", ":"))
    return (
        f"curl -sk -X POST {infer_url}"
        f" -H 'Content-Type: application/json'"
        f" -d '{body}'"
    )


def render_curl_command_file(infer_url: str, request_path: Path) -> str:
    """Return a copy-pasteable curl command that reads the payload from a file.

    Uses ``-d @<path>`` instead of embedding the JSON inline, producing a
    command that is readable and directly runnable at a terminal.
    """
    return (
        f"curl -sk -X POST \\\n"
        f"  {infer_url} \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d @{request_path}"
    )
