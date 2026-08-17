"""TrustyAI REST API client.

Stateless functions that call the TrustyAI service HTTP endpoints.
Every public function takes explicit ``route`` and ``token`` parameters —
no session objects, no module-level state.

Endpoint reference (validated against ta-svc-bias branch):
    GET  /info                               → all models dict
    POST /info/names                         → apply field name mapping
    POST /metrics/group/fairness/spd         → one-shot SPD computation
    POST /metrics/group/fairness/spd/request → scheduled SPD monitoring
    POST /metrics/identity/request           → scheduled identity metric

Data ingestion is handled by platform/inference.send_observations(), which
posts KServe v2 requests directly to the model endpoint.  The KServe
payload-logger sidecar forwards inputs + outputs to TrustyAI automatically.
"""

from typing import Any

import requests

from rhoai.utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = 30  # seconds


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _raise_with_body(response: "requests.Response") -> None:
    """Raise RuntimeError with the HTTP status and TrustyAI response body included.

    Called whenever TrustyAI returns a non-2xx response.  Including the body
    means validation errors (e.g. unknown protected attribute) are readable
    without requiring the user to reproduce the request manually.
    """
    body = response.text.strip() or "<empty body>"
    raise RuntimeError(
        f"TrustyAI request failed: HTTP {response.status_code} — {body}"
    )


def _post(route: str, token: str, path: str, body: dict[str, Any]) -> Any:
    url = f"{route.rstrip('/')}{path}"
    log.debug("POST %s", url)
    response = requests.post(url, json=body, headers=_headers(token), timeout=_TIMEOUT)
    if not response.ok:
        _raise_with_body(response)
    return response.json()


def _get(route: str, token: str, path: str) -> Any:
    url = f"{route.rstrip('/')}{path}"
    log.debug("GET %s", url)
    response = requests.get(url, headers=_headers(token), timeout=_TIMEOUT)
    if not response.ok:
        _raise_with_body(response)
    return response.json()


# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------

def get_model_info(route: str, token: str, model_id: str) -> dict[str, Any]:
    """Return the TrustyAI info entry for a single model.

    Calls GET /info (returns all models) and filters client-side.

    Args:
        route:    TrustyAI service base URL (e.g. ``https://trustyai-service.apps…``).
        token:    Bearer token for authentication.
        model_id: The model identifier to look up.

    Returns:
        The info dict for ``model_id``.

    Raises:
        KeyError: If ``model_id`` is not found in the response.
        requests.HTTPError: On a non-2xx response.
    """
    log.info("Fetching TrustyAI info for model '%s'", model_id)
    all_info: dict[str, Any] = _get(route, token, "/info")
    if model_id not in all_info:
        raise KeyError(
            f"Model '{model_id}' not found in TrustyAI info response. "
            f"Available: {list(all_info.keys())}"
        )
    return all_info[model_id]


def get_observation_count(route: str, token: str, model_id: str) -> int:
    """Return the number of observations TrustyAI has ingested for a model.

    Calls GET /info and reads ``info[model_id]["data"]["observations"]``.
    Returns 0 if the model is not yet known to TrustyAI — does not raise
    KeyError, so callers can poll safely before any data has arrived.

    Args:
        route:    TrustyAI service base URL.
        token:    Bearer token for authentication.
        model_id: The model identifier to look up.

    Returns:
        Number of observations ingested, or 0 if the model is not yet registered.

    Raises:
        requests.HTTPError: On a non-2xx response from /info.
    """
    log.debug("Fetching observation count for model '%s'", model_id)
    all_info: dict[str, Any] = _get(route, token, "/info")
    entry = all_info.get(model_id, {})
    return entry.get("data", {}).get("observations", 0)


def apply_name_mapping(
    route: str,
    token: str,
    model_id: str,
    input_mapping: dict[str, str],
    output_mapping: dict[str, str],
) -> None:
    """Apply a human-readable field name mapping to a model's data.

    Args:
        route:          TrustyAI service base URL.
        token:          Bearer token for authentication.
        model_id:       The model identifier.
        input_mapping:  ``{internal_name: display_name}`` for input features.
        output_mapping: ``{internal_name: display_name}`` for output features.

    Raises:
        requests.HTTPError: On a non-2xx response.
    """
    log.info("Applying name mapping for model '%s'", model_id)
    _post(route, token, "/info/names", {
        "modelId": model_id,
        "inputMapping": input_mapping,
        "outputMapping": output_mapping,
    })


# ---------------------------------------------------------------------------
# Metrics — SPD (Statistical Parity Difference)
# ---------------------------------------------------------------------------

def compute_spd(
    route: str,
    token: str,
    model_id: str,
    protected_attribute: str,
    privileged_value: float,
    unprivileged_value: float,
    outcome_name: str,
    favorable_outcome: float,
    batch_size: int = 5000,
) -> dict[str, Any]:
    """Compute a one-shot SPD fairness metric.

    Returns:
        Dict with keys ``value``, ``id``, ``thresholds``, ``specificDefinition``.

    Raises:
        requests.HTTPError: On a non-2xx response.
    """
    log.info("Computing SPD for model '%s' (attribute='%s')", model_id, protected_attribute)
    return _post(route, token, "/metrics/group/fairness/spd", {
        "modelId": model_id,
        "protectedAttribute": protected_attribute,
        "privilegedAttribute": {"type": "DOUBLE", "value": privileged_value},
        "unprivilegedAttribute": {"type": "DOUBLE", "value": unprivileged_value},
        "outcomeName": outcome_name,
        "favorableOutcome": {"type": "DOUBLE", "value": favorable_outcome},
        "batchSize": batch_size,
    })


def schedule_spd(
    route: str,
    token: str,
    model_id: str,
    protected_attribute: str,
    privileged_value: float,
    unprivileged_value: float,
    outcome_name: str,
    favorable_outcome: float,
    batch_size: int = 5000,
) -> str:
    """Schedule recurring SPD monitoring for a model.

    Returns:
        The request ID assigned by TrustyAI (use to cancel or inspect later).

    Raises:
        requests.HTTPError: On a non-2xx response.
    """
    log.info("Scheduling SPD for model '%s' (attribute='%s')", model_id, protected_attribute)
    response = _post(route, token, "/metrics/group/fairness/spd/request", {
        "modelId": model_id,
        "protectedAttribute": protected_attribute,
        "privilegedAttribute": {"type": "DOUBLE", "value": privileged_value},
        "unprivilegedAttribute": {"type": "DOUBLE", "value": unprivileged_value},
        "outcomeName": outcome_name,
        "favorableOutcome": {"type": "DOUBLE", "value": favorable_outcome},
        "batchSize": batch_size,
    })
    return response["id"]


# ---------------------------------------------------------------------------
# Metrics — Identity
# ---------------------------------------------------------------------------

def schedule_identity(
    route: str,
    token: str,
    model_id: str,
    column_name: str,
    batch_size: int = 5000,
) -> str:
    """Schedule recurring identity metric tracking for a model column.

    Args:
        route:       TrustyAI service base URL.
        token:       Bearer token for authentication.
        model_id:    The model identifier.
        column_name: The feature/output column to track.
        batch_size:  Number of recent observations to include per computation.

    Returns:
        The request ID assigned by TrustyAI.

    Raises:
        requests.HTTPError: On a non-2xx response.
    """
    log.info("Scheduling identity metric for model '%s' (column='%s')", model_id, column_name)
    response = _post(route, token, "/metrics/identity/request", {
        "modelId": model_id,
        "columnName": column_name,
        "batchSize": batch_size,
    })
    return response["id"]
