"""TrustAI guardrails lifecycle — GuardrailsOrchestrator and supporting ConfigMaps.

Manages the FMS guardrails stack deployed alongside inference models.
Does not own model serving — that lives in platform/inference.py.
"""

from pathlib import Path

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

# Resource names created by the guardrails manifests.
_ORCHESTRATOR_NAME = "guardrails-orchestrator"
_ORCHESTRATOR_KIND = "GuardrailsOrchestrator"
_ORCHESTRATOR_CM   = "fms-orchestr8-config-nlp"
_GATEWAY_CM        = "fms-orchestr8-config-gateway"


def apply_guardrails(manifest_paths: list[Path], namespace: str) -> None:
    """Apply all guardrails manifests in order. Idempotent."""
    for path in manifest_paths:
        log.info("Applying TrustAI manifest: %s", path.name)
        resources.apply_manifest(path, namespace)


def apply_prometheus_rules(manifest_path: Path, namespace: str) -> None:
    """Apply a PrometheusRule manifest. Idempotent."""
    log.info("Applying PrometheusRule from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def wait_until_ready(namespace: str, timeout: int = 300) -> None:
    """Block until the GuardrailsOrchestrator is Ready. Raises TimeoutError."""
    log.info("Waiting for GuardrailsOrchestrator (timeout: %ss)", timeout)
    wait.wait_until_ready(_ORCHESTRATOR_KIND, _ORCHESTRATOR_NAME, namespace, timeout=timeout)


def verify(namespace: str) -> None:
    """Assert the GuardrailsOrchestrator is Ready. Raises RuntimeError if not."""
    log.info("Verifying GuardrailsOrchestrator in '%s'", namespace)
    if not resources.is_ready(_ORCHESTRATOR_KIND, _ORCHESTRATOR_NAME, namespace):
        raise RuntimeError(
            f"GuardrailsOrchestrator '{_ORCHESTRATOR_NAME}' is not ready in '{namespace}'."
        )
    log.info("GuardrailsOrchestrator is Ready")


def delete_guardrails(name: str, namespace: str) -> None:
    """Delete the GuardrailsOrchestrator and its ConfigMaps."""
    log.info("Deleting GuardrailsOrchestrator '%s'", name)
    resources.delete_manifest(_ORCHESTRATOR_KIND, name, namespace)
    resources.delete_manifest("ConfigMap", _ORCHESTRATOR_CM, namespace)
    resources.delete_manifest("ConfigMap", _GATEWAY_CM, namespace)
