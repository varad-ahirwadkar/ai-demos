"""TrustyAI Service lifecycle — TrustyAIService CR and its prerequisites.

Manages:
  - OpenShift user-workload monitoring ConfigMaps (cluster-wide prerequisite)
  - The inferenceservice-config ConfigMap patch required in RawDeployment mode
    so TrustyAI can inject its sidecar without RHOAI reverting the change
  - The TrustyAIService CR itself

Does not own model serving — that lives in platform/inference.py.
"""

from pathlib import Path

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

_SERVICE_KIND = "TrustyAIService"
_ISVC_CONFIG_CM = "inferenceservice-config"


def apply_monitoring_config(manifest_path: Path) -> None:
    """Apply the cluster-monitoring and user-workload-monitoring ConfigMaps.

    These are cluster-scoped (namespace is baked into each document), so no
    namespace argument is needed.  Idempotent.
    """
    from rhoai.utils.yaml_io import load_all

    log.info("Applying monitoring config from %s", manifest_path.name)
    for doc in load_all(manifest_path):
        ns = doc.get("metadata", {}).get("namespace")
        resources.apply_dict(doc, ns)


def patch_inferenceservice_config(namespace: str) -> None:
    """Remove opendatahub.io/managed from inferenceservice-config.

    Required for any InferenceService using RawDeployment mode so that
    TrustyAI can inject its payload-logging sidecar without RHOAI reverting
    the ConfigMap change.  Idempotent — annotation is absent after the call
    whether or not it existed before.
    """
    log.info("Patching inferenceservice-config in '%s'", namespace)
    resources.patch(
        "ConfigMap",
        _ISVC_CONFIG_CM,
        {"metadata": {"annotations": {"opendatahub.io/managed": "false"}}},
        namespace=namespace,
    )


def apply_trustyai_service(manifest_path: Path, namespace: str) -> None:
    """Apply the TrustyAIService CR manifest.  Idempotent."""
    log.info("Applying TrustyAIService from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def wait_until_ready(name: str, namespace: str, timeout: int = 300) -> None:
    """Block until the TrustyAIService is Ready.  Raises TimeoutError."""
    log.info("Waiting for TrustyAIService '%s' (timeout: %ss)", name, timeout)
    wait.wait_until_ready(_SERVICE_KIND, name, namespace, timeout=timeout)


def verify(name: str, namespace: str) -> None:
    """Assert the TrustyAIService is Ready.  Raises RuntimeError if not."""
    log.info("Verifying TrustyAIService '%s' in '%s'", name, namespace)
    if not resources.is_ready(_SERVICE_KIND, name, namespace):
        raise RuntimeError(
            f"TrustyAIService '{name}' is not ready in '{namespace}'."
        )
    log.info("TrustyAIService '%s' is Ready", name)


def delete_trustyai_service(name: str, namespace: str) -> None:
    """Delete the TrustyAIService CR and wait for it to disappear."""
    log.info("Deleting TrustyAIService '%s'", name)
    resources.delete_manifest(_SERVICE_KIND, name, namespace)
    wait.wait_until_deleted(_SERVICE_KIND, name, namespace)
