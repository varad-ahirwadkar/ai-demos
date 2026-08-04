"""Shared manifest path resolver for platform-level resources.

Maps logical names to file paths inside the openshift-ai-demos repo.
If the repo is reorganised, only this file needs to change.
Imports stdlib only.
"""

from pathlib import Path


def get_dsci(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "dsci.yaml"


def get_dsc(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "dsc.yaml"


def get_s3_secret(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "s3-secret.yaml"


def get_operator_group(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "operator-group.yaml"


def get_subscription(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "subscription.yaml"


def get_vllm_serving_runtime(repo_root: str | Path) -> Path:
    return Path(repo_root) / "model-serving" / "shared" / "vllm-serving-runtime.yaml"


def get_triton_serving_runtime_template(repo_root: str | Path) -> Path:
    return (
        Path(repo_root)
        / "model-serving"
        / "predictive-models"
        / "triton"
        / "triton-ppc64le-runtime-template.yaml"
    )


def get_vllm_model_manifest(repo_root: str | Path, model: str) -> Path:
    """Return the path to the vLLM InferenceService manifest for *model*.

    Args:
        repo_root: Root of the openshift-ai-demos repository.
        model:     Filename stem (without .yaml), e.g. ``"qwen2.5-1.5b-instruct"``.

    Returns:
        Path to model-serving/generative-models/vllm/<model>.yaml
    """
    return Path(repo_root) / "model-serving" / "generative-models" / "vllm" / f"{model}.yaml"
