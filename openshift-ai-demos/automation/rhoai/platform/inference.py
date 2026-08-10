"""KServe InferenceService and ServingRuntime capability."""

import json
import time
from pathlib import Path
from typing import Any

import urllib3

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

# Triton HTTP REST API paths (KServe v2 inference protocol).
_TRITON_INFER_PATH = "/v2/models/{model_name}/infer"

# Smoke-test defaults — not user-facing config.
_INFER_TIMEOUT   = 30    # seconds for the inference HTTP call
_RETRY_DELAY     = 3     # seconds to wait before one connection-error retry
_POOL_CONNECTIONS = 1


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
    log.info("Deploying Triton ServingRuntime")
    log.debug("Processing ServingRuntime template %s", template_path.name)
    resources.process_template(template_path, namespace)


def apply_inference_service(manifest_path: Path, namespace: str) -> None:
    """Apply an InferenceService manifest. Does not block — call wait_until_ready() after."""
    log.info("Applying InferenceService from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def wait_until_ready(name: str, namespace: str, timeout: int = 60) -> None:
    """Block until the InferenceService is Ready. Raises TimeoutError."""
    log.info("Waiting for InferenceService '%s'", name)
    log.debug("Timeout: %ss", timeout)
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


def verify_triton_inference(
    isvc_name: str,
    namespace: str,
    model_name: str,
    sample_request: Path,
) -> None:
    """Smoke-test a Triton InferenceService by submitting a sample request.

    Steps:
        1. Resolve the InferenceService URL.
        2. POST the sample payload to /v2/models/<model_name>/infer.
        3. Assert HTTP 200, model_name present, and outputs present in response.

    One retry after a short delay is attempted on connection errors to absorb
    the brief propagation gap between IS Ready and the Route becoming reachable.

    Args:
        isvc_name:      Kubernetes name of the InferenceService.
        namespace:      Namespace where the InferenceService lives.
        model_name:     Model name as registered in Triton (used in URL and response check).
        sample_request: Path to a JSON file containing the KServe v2 inference payload.

    Raises:
        RuntimeError: If the inference request fails or the response is not valid.
    """
    base_url  = get_inference_url(isvc_name, namespace)
    infer_url = base_url + _TRITON_INFER_PATH.format(model_name=model_name)
    payload   = json.loads(sample_request.read_text())

    log.info("Running model smoke test")
    log.debug("POST %s", infer_url)

    try:
        response = _http_post(infer_url, payload)
    except _ConnectionError:
        log.warning("Connection error — retrying in %ss", _RETRY_DELAY)
        time.sleep(_RETRY_DELAY)
        response = _http_post(infer_url, payload)

    _assert_triton_response(response, model_name)
    log.info("Model is serving inference requests")


# ---------------------------------------------------------------------------
# Private HTTP helpers
# ---------------------------------------------------------------------------

class _ConnectionError(RuntimeError):
    """Raised when the HTTP call cannot reach the server (not an HTTP error)."""


def _http_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST a JSON body to *url* and return the decoded JSON response.

    Raises:
        _ConnectionError: On connection/timeout failure.
        RuntimeError:     On a non-200 HTTP response.
    """
    http = urllib3.PoolManager(num_pools=_POOL_CONNECTIONS, cert_reqs="CERT_NONE")
    encoded = json.dumps(body).encode()
    try:
        resp = http.request(
            "POST",
            url,
            body=encoded,
            headers={"Content-Type": "application/json"},
            timeout=_INFER_TIMEOUT,
        )
    except urllib3.exceptions.HTTPError as exc:
        raise _ConnectionError(f"Cannot reach {url}: {exc}") from exc

    if resp.status != 200:
        preview = resp.data[:200].decode(errors="replace")
        raise RuntimeError(
            f"Triton inference request failed: HTTP {resp.status} — {preview}"
        )
    try:
        return json.loads(resp.data)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Triton response is not valid JSON: {exc}") from exc


def _assert_triton_response(response: dict[str, Any], model_name: str) -> None:
    """Assert the minimal KServe v2 response structure is present.

    Raises:
        RuntimeError: If model_name or outputs are missing from the response.
    """
    if response.get("model_name") != model_name:
        raise RuntimeError(
            f"Unexpected model_name in Triton response: "
            f"expected '{model_name}', got '{response.get('model_name')}'"
        )
    if not response.get("outputs"):
        raise RuntimeError(
            f"Triton response for '{model_name}' contains no outputs."
        )
