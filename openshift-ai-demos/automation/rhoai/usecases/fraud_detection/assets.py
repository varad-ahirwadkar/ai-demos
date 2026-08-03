"""Asset path resolution for the Fraud Detection use case.

The only file that knows where fraud-detection manifests live on disk.
Shared platform manifests are delegated to platform.manifests — only
fraud-detection-specific paths are resolved here.
"""

from pathlib import Path

from rhoai.platform import manifests


def get_model_manifest(repo_root: str | Path, model_name: str) -> Path:
    """Return the path to a generative model InferenceService manifest.

    Args:
        repo_root:  Root of the openshift-ai-demos repository.
        model_name: Manifest filename without extension,
                    e.g. "qwen2.5-1.5b-instruct".

    Returns:
        Path to model-serving/generative-models/vllm/<model_name>.yaml
    """
    return (
        Path(repo_root)
        / "model-serving"
        / "generative-models"
        / "vllm"
        / f"{model_name}.yaml"
    )


def get_serving_runtime_manifest(repo_root: str | Path) -> Path:
    """Return the path to the vLLM ServingRuntime manifest.

    Delegates to platform.manifests — the single source of truth for
    shared platform manifest paths.
    """
    return manifests.get_vllm_serving_runtime(repo_root)


def get_trustyai_guardrails_manifests(repo_root: str | Path) -> list[Path]:
    """Return manifest paths for TrustAI guardrails, in apply order.

    Args:
        repo_root: Root of the openshift-ai-demos repository.

    Returns:
        Ordered list of paths to the guardrails YAML files.
    """
    base = (
        Path(repo_root)
        / "trustyai"
        / "guardrails"
        / "fms-guardrails"
        / "lemonade-stand"
        / "guardrails"
    )
    return [
        base / "configmap_orchestrator.yaml",
        base / "configmap_vllm_gateway.yaml",
        base / "orchestrator_cr.yaml",
    ]


def get_prometheus_rules_manifest(repo_root: str | Path) -> Path:
    """Return the path to the Prometheus alerting rules manifest.

    Args:
        repo_root: Root of the openshift-ai-demos repository.

    Returns:
        Path to trustyai/monitoring/prometheus-rules.yaml
    """
    return Path(repo_root) / "trustyai" / "monitoring" / "prometheus-rules.yaml"
