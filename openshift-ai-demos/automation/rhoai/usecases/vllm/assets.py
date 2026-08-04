"""Asset path resolution for the vLLM generative use case.

The only file that knows where vLLM manifests live on disk.
Shared platform manifests are delegated to platform.manifests.
"""

from pathlib import Path

from rhoai.platform import manifests


def get_serving_runtime(repo_root: str | Path) -> Path:
    """Return the path to the shared vLLM CPU ServingRuntime manifest.

    Returns:
        Path to model-serving/shared/vllm-serving-runtime.yaml
    """
    return manifests.get_vllm_serving_runtime(repo_root)


def get_model_manifest(repo_root: str | Path, model: str) -> Path:
    """Return the path to the InferenceService manifest for *model*.

    Args:
        repo_root: Root of the openshift-ai-demos repository.
        model:     Filename stem (without .yaml), e.g. ``"qwen2.5-1.5b-instruct"``.
                   Available: qwen2.5-1.5b-instruct, phi-3-mini-4k-instruct,
                              qwen3-4b-instruct-2507

    Returns:
        Path to model-serving/generative-models/vllm/<model>.yaml
    """
    return manifests.get_vllm_model_manifest(repo_root, model)
