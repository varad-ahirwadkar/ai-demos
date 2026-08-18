"""KServe InferenceService and ServingRuntime capability."""

import json
import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
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


def apply_serving_runtime_from_template(
    template_path: Path,
    platform_namespace: str,
    deploy_namespace: str,
    model_name: str,
    runtime_name: str,
) -> None:
    """Instantiate an OpenShift Template and apply the resulting ServingRuntime.

    Mirrors the original manual flow:
        oc process -n <platform_namespace> <template-name> -p MODEL_NAME=<m> -p RUNTIME_NAME=<r> \
            | oc apply -n <deploy_namespace> -f -

    The Template is first uploaded to <platform_namespace> (redhat-ods-applications)
    where RHOAI catalogs serving-runtime templates, then processed server-side,
    and the resulting ServingRuntime is applied into <deploy_namespace>.

    Args:
        model_name:   Passed as MODEL_NAME — the model directory Triton loads
                      (must match the InferenceService name).
        runtime_name: Passed as RUNTIME_NAME — the metadata.name of the created
                      ServingRuntime. Must be unique per deployment so that multiple
                      models can coexist without overwriting each other's runtime.
    """
    log.info("Deploying Triton ServingRuntime '%s'", runtime_name)
    log.debug("Processing ServingRuntime template %s", template_path.name)
    resources.process_template(
        template_path, platform_namespace, deploy_namespace,
        {"MODEL_NAME": model_name, "RUNTIME_NAME": runtime_name},
    )


def wait_until_ready(
    name: str,
    namespace: str,
    timeout: int = 60,
    on_tick: Callable[[float], Any] | None = None,
) -> None:
    """Block until the InferenceService is Ready. Raises TimeoutError."""
    log.info("Waiting for InferenceService '%s'", name)
    log.debug("Timeout: %ss", timeout)
    wait.wait_until_ready("InferenceService", name, namespace, timeout=timeout, on_tick=on_tick)


def wait_until_all_ready(
    namespace: str,
    timeout: int = 300,
    on_tick: Callable[[float], Any] | None = None,
) -> None:
    """Block until every InferenceService in *namespace* is Ready.

    Used after ``patch_inferenceservice_config`` triggers a predictor pod
    rollout (KServe recycles pods to inject the updated logger configuration
    and the payload-logger sidecar).  The rolled-out pods end up with three
    containers; this function ensures they are all running and Ready before
    observations are sent.

    Args:
        namespace: Namespace to check.
        timeout:   Maximum seconds to wait before raising ``TimeoutError``.
        on_tick:   Optional progress callback invoked after each poll with
                   elapsed seconds as the sole argument.

    Raises:
        TimeoutError: If any InferenceService is not Ready within ``timeout``.
    """
    log.info("Waiting for all InferenceServices in '%s' to become Ready", namespace)
    log.debug("Timeout: %ss", timeout)

    def _all_ready() -> bool:
        isvcs = resources.list_resources("InferenceService", namespace)
        if not isvcs:
            return False
        return all(
            resources.is_ready("InferenceService", isvc["metadata"]["name"], namespace)
            for isvc in isvcs
        )

    wait.wait_until(
        _all_ready,
        description=f"all InferenceServices ready in '{namespace}'",
        timeout=timeout,
        on_tick=on_tick,
    )


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


def send_observations(
    model_name: str,
    namespace: str,
    observation_files: list[Path],
) -> int:
    """Send historical observation batches to a deployed model for TrustyAI ingestion.

    Each file in observation_files must be a local JSON file containing one
    complete KServe v2 inference request.  Expected structure::

        {
          "inputs": [{
            "name":     "<tensor-name>",
            "shape":    [N, F],   # N rows, F features
            "datatype": "FP64",
            "data":     [[...], ...]
          }]
        }

    Files are validated locally before any network call is made.  Validation
    checks that each file is valid JSON, contains a non-empty ``inputs`` list,
    and that the first tensor has both ``shape`` and ``data`` fields with
    ``shape[0] == len(data)``.

    Each file is posted as a single HTTP call to the model's KServe v2
    inference endpoint (``/v2/models/<model_name>/infer``).  The KServe
    payload-logger sidecar intercepts each call and forwards inputs + outputs
    to TrustyAI automatically — no direct TrustyAI API call is needed here.

    Args:
        model_name:         InferenceService name (also the Triton model name).
        namespace:          Namespace where the model is deployed.
        observation_files:  Ordered list of validated local KServe v2 JSON files.

    Returns:
        Total number of observation rows sent across all files.

    Raises:
        FileNotFoundError: If any path does not exist.
        ValueError:        If any file fails structural validation.
        RuntimeError:      If any HTTP POST fails (non-200 response).
    """
    if not observation_files:
        raise ValueError("observation_files must not be empty")

    # --- local validation pass (before touching the cluster) ---
    total_rows = 0
    for path in observation_files:
        total_rows += _validate_observation_file(path)

    # --- send each batch ---
    base_url  = get_inference_url(model_name, namespace)
    infer_url = base_url + _TRITON_INFER_PATH.format(model_name=model_name)

    log.info(
        "Sending %d observation rows across %d file(s) to '%s'",
        total_rows, len(observation_files), model_name,
    )
    for path in observation_files:
        payload = json.loads(path.read_text())
        log.debug("POST %s  (%s)", infer_url, path.name)
        with _quiet_urllib3():
            _http_post(infer_url, payload)

    log.info("Observations sent: %d rows", total_rows)
    return total_rows


def _validate_observation_file(path: Path) -> int:
    """Validate a single KServe v2 observation file and return its row count.

    Only the first tensor (``inputs[0]``) is inspected.  The row count comes
    from ``inputs[0].shape[0]``, which is the batch dimension for a standard
    single-input model.  Files with multiple tensors are posted in full; the
    additional tensors are not validated here because TrustyAI's ingestion
    threshold is computed against the row count of the first tensor only.

    Args:
        path: Local path to the JSON file.

    Returns:
        Number of rows (``inputs[0].shape[0]``).

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError:        On any structural problem, with a descriptive message.
    """
    if not path.exists():
        raise FileNotFoundError(f"Observation file not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Observation file is not valid JSON: {path}") from exc

    inputs = payload.get("inputs")
    if not inputs or not isinstance(inputs, list):
        raise ValueError(
            f"Observation file '{path.name}' has no 'inputs' list. "
            "This framework expects KServe v2 inference request payloads "
            "({'inputs': [{'name': ..., 'shape': [N, ...], 'datatype': ..., 'data': [...]}]})."
        )
    first = inputs[0]
    shape = first.get("shape")
    data  = first.get("data")
    if not shape or not isinstance(shape, list) or len(shape) < 1:
        raise ValueError(
            f"Observation file '{path.name}': inputs[0] missing valid 'shape'."
        )
    if data is None or not isinstance(data, list):
        raise ValueError(
            f"Observation file '{path.name}': inputs[0] missing 'data'."
        )
    declared_rows = shape[0]
    actual_rows   = len(data)
    if declared_rows != actual_rows:
        raise ValueError(
            f"Observation file '{path.name}': shape[0]={declared_rows} "
            f"does not match len(data)={actual_rows}."
        )
    return declared_rows


def delete_inference_service(name: str, namespace: str) -> None:
    """Send the delete request for an InferenceService. Does not wait."""
    log.info("Deleting InferenceService '%s'", name)
    resources.delete_manifest("InferenceService", name, namespace)


def delete_serving_runtime(name: str, namespace: str) -> None:
    """Send the delete request for a ServingRuntime. Does not wait."""
    log.info("Deleting ServingRuntime '%s'", name)
    resources.delete_manifest("ServingRuntime", name, namespace)


def wait_until_inference_services_gone(names: list[str], namespace: str, timeout: int = 120) -> None:
    """Block until every named InferenceService no longer exists.

    All deletes should be issued before calling this so the removals run
    concurrently and the wait covers all of them in a single poll loop.

    Raises:
        TimeoutError: If any InferenceService is still present after timeout.
    """
    log.info("Waiting for InferenceService(s) to be removed: %s", names)
    wait.wait_until(
        lambda: all(not resources.exists("InferenceService", n, namespace) for n in names),
        f"InferenceServices gone in '{namespace}'",
        timeout=timeout,
    )


def wait_until_serving_runtimes_gone(names: list[str], namespace: str, timeout: int = 120) -> None:
    """Block until every named ServingRuntime no longer exists.

    All deletes should be issued before calling this so the removals run
    concurrently and the wait covers all of them in a single poll loop.

    Raises:
        TimeoutError: If any ServingRuntime is still present after timeout.
    """
    log.info("Waiting for ServingRuntime(s) to be removed: %s", names)
    wait.wait_until(
        lambda: all(not resources.exists("ServingRuntime", n, namespace) for n in names),
        f"ServingRuntimes gone in '{namespace}'",
        timeout=timeout,
    )


class EndpointUnreachable(RuntimeError):
    """Raised when the inference endpoint cannot be reached after retries.

    Carries the endpoint URL and the curl reproduction command so the caller
    can present a structured, user-oriented message without knowing internals.
    """

    def __init__(self, infer_url: str, curl_cmd: str) -> None:
        super().__init__(f"Inference endpoint unreachable: {infer_url}")
        self.infer_url = infer_url
        self.curl_cmd  = curl_cmd


@contextmanager
def _quiet_urllib3():
    """Temporarily raise the urllib3 log level to ERROR.

    urllib3 emits WARNING-level records for connection retries and name
    resolution failures.  These are implementation noise when we already
    handle the failure ourselves — suppress them for the duration of the
    with-block and restore the original level afterwards.
    """
    logger = logging.getLogger("urllib3")
    original = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(original)


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
    urllib3 connection-level warnings are suppressed during both attempts so that
    internal retry noise does not appear in user-facing output.

    Args:
        isvc_name:      Kubernetes name of the InferenceService.
        namespace:      Namespace where the InferenceService lives.
        model_name:     Model name as registered in Triton (used in URL and response check).
        sample_request: Path to a JSON file containing the KServe v2 inference payload.

    Raises:
        EndpointUnreachable: When the endpoint cannot be reached after one retry.
        RuntimeError:        If the inference request fails or the response is not valid.
    """
    base_url  = get_inference_url(isvc_name, namespace)
    infer_url = base_url + _TRITON_INFER_PATH.format(model_name=model_name)
    payload   = json.loads(sample_request.read_text())
    curl_cmd  = (
        f"curl -sk -X POST {infer_url}"
        f" -H 'Content-Type: application/json'"
        f" -d @{sample_request}"
    )

    log.info("Running model smoke test")
    log.debug("Model:    %s", model_name)
    log.debug("Endpoint: %s", infer_url)
    log.debug("Request payload:\n%s", json.dumps(payload, indent=2))
    log.debug("Reproduce manually:\n  %s", curl_cmd)

    with _quiet_urllib3():
        try:
            response, elapsed, status = _http_post(infer_url, payload)
        except _ConnectionError as exc:
            log.debug("Connection attempt 1 failed: %s", exc)
            time.sleep(_RETRY_DELAY)
            try:
                response, elapsed, status = _http_post(infer_url, payload)
            except _ConnectionError as exc2:
                log.debug("Connection attempt 2 failed: %s", exc2)
                raise EndpointUnreachable(infer_url, curl_cmd) from exc2

    log.debug("Response status: %s  elapsed: %.2fs", status, elapsed)
    log.debug("Response body:\n%s", json.dumps(response, indent=2))

    _assert_triton_response(response, model_name)
    log.info("Model is serving inference requests")


# ---------------------------------------------------------------------------
# Private HTTP helpers
# ---------------------------------------------------------------------------

class _ConnectionError(RuntimeError):
    """Raised when the HTTP call cannot reach the server (not an HTTP error)."""


def _http_post(url: str, body: dict[str, Any]) -> tuple[dict[str, Any], float, int]:
    """POST a JSON body to *url* and return (decoded response, elapsed seconds, status code).

    Raises:
        _ConnectionError: On connection/timeout failure.
        RuntimeError:     On a non-200 HTTP response.
    """
    http     = urllib3.PoolManager(num_pools=_POOL_CONNECTIONS, cert_reqs="CERT_NONE")
    encoded  = json.dumps(body).encode()
    t_start  = time.monotonic()
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
    elapsed = time.monotonic() - t_start

    if resp.status != 200:
        raw     = resp.data.decode(errors="replace")
        preview = raw[:200]
        log.debug("Error response body:\n%s", raw)
        raise RuntimeError(
            f"Triton inference request failed: HTTP {resp.status} — {preview}"
        )
    try:
        return json.loads(resp.data), elapsed, resp.status
    except json.JSONDecodeError as exc:
        log.debug("Raw response (non-JSON): %s", resp.data[:500].decode(errors="replace"))
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
