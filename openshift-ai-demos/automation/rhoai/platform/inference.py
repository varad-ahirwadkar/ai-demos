"""KServe InferenceService and ServingRuntime capability."""

from pathlib import Path

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def apply_serving_runtime(manifest_path: Path, namespace: str) -> None:
    """Apply a ServingRuntime manifest. Idempotent."""
    log.info("Applying ServingRuntime from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def apply_serving_runtime_from_template(template_path: Path, namespace: str) -> None:
    """Instantiate an OpenShift Template and apply the resulting ServingRuntime.

    Equivalent to:
        oc process -n <namespace> -f <template_path> | oc apply -f -

    Use this when the ServingRuntime is defined inside a Template object
    (e.g. triton-ppc64le-runtime-template.yaml).
    """
    log.info("Processing ServingRuntime template %s", template_path.name)
    resources.process_template(template_path, namespace)


def apply_inference_service(manifest_path: Path, namespace: str) -> None:
    """Apply an InferenceService manifest. Does not block — call wait_until_ready() after."""
    log.info("Applying InferenceService from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def wait_until_ready(name: str, namespace: str, timeout: int = 600) -> None:
    """Block until the InferenceService is Ready. Raises TimeoutError."""
    log.info("Waiting for InferenceService '%s' (timeout: %ss)", name, timeout)
    wait.wait_until_ready("InferenceService", name, namespace, timeout=timeout)


def get_inference_url(name: str, namespace: str) -> str:
    """Return the public inference URL from status.url or the OpenShift Route.

    Raises RuntimeError if the service has no URL yet.
    """
    url = resources.status("InferenceService", name, namespace).get("url")
    if url:
        return url
    if resources.exists("Route", name, namespace):
        route = resources.get("Route", name, namespace)
        host = route.get("spec", {}).get("host", "")
        if host:
            scheme = "https" if route.get("spec", {}).get("tls") else "http"
            return f"{scheme}://{host}"
    raise RuntimeError(f"InferenceService '{name}' has no URL — call wait_until_ready() first.")


def verify(namespace: str, name: str | None = None) -> None:
    """Assert InferenceService(s) are Ready. Raises RuntimeError if any are not.

    Args:
        namespace: Namespace to check.
        name:      If given, check only that specific InferenceService.
                   If None, check every InferenceService in the namespace.
    """
    if name is not None:
        log.info("Verifying InferenceService '%s' in '%s'", name, namespace)
        if not resources.is_ready("InferenceService", name, namespace):
            raise RuntimeError(
                f"InferenceService '{name}' is not ready in '{namespace}'."
            )
        log.info("InferenceService '%s' is Ready", name)
        return

    log.info("Verifying all InferenceServices in '%s'", namespace)
    services = resources.list_resources("InferenceService", namespace)
    not_ready = [
        svc.get("metadata", {}).get("name", "?")
        for svc in services
        if not resources.is_ready(
            "InferenceService", svc.get("metadata", {}).get("name", ""), namespace
        )
    ]
    if not_ready:
        raise RuntimeError(f"InferenceServices not ready in '{namespace}': {', '.join(not_ready)}")
    log.info("All InferenceServices in '%s' are Ready", namespace)


def delete_inference_service(name: str, namespace: str) -> None:
    """Delete an InferenceService and wait for removal."""
    log.info("Deleting InferenceService '%s'", name)
    resources.delete_manifest("InferenceService", name, namespace)
    wait.wait_until_deleted("InferenceService", name, namespace)


def delete_serving_runtime(name: str, namespace: str) -> None:
    """Delete a ServingRuntime and wait for removal."""
    log.info("Deleting ServingRuntime '%s'", name)
    resources.delete_manifest("ServingRuntime", name, namespace)
    wait.wait_until_deleted("ServingRuntime", name, namespace)
