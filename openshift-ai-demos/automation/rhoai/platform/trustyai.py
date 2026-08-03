"""TrustyAI platform capabilities.

Organised into four sections:

    Prerequisites  — cluster and namespace setup before the TrustyAIService is deployed.
    Lifecycle      — TrustyAIService CR deploy, wait, verify, delete.
    Discovery      — resolve the TrustyAI route URL and obtain a bearer token.
    Cleanup        — delete prerequisite resources in reverse order.

Does not own model serving — that lives in platform/inference.py.
Does not contain REST API calls — those live in platform/trustyai_client.py.
"""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger
from rhoai.utils.yaml_io import load_all

log = get_logger(__name__)

_SERVICE_KIND    = "TrustyAIService"
_ISVC_CONFIG_CM  = "inferenceservice-config"
_LOGGER_CA_CM    = "kserve-logger-ca-bundle"


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

def enable_user_workload_monitoring(manifest_path: Path) -> None:
    """Enable OpenShift User Workload Monitoring.

    Applies two cluster-scoped ConfigMaps from *manifest_path*:
      - cluster-monitoring-config        (openshift-monitoring)
      - user-workload-monitoring-config  (openshift-user-workload-monitoring)

    Idempotent. Must be run once per cluster before deploying TrustyAI.

    Args:
        manifest_path: Path to trustyai/service/monitoring-config.yaml.
    """
    log.info("Enabling OpenShift User Workload Monitoring")
    log.debug("Manifest: %s", manifest_path.name)
    for doc in load_all(manifest_path):
        ns = doc["metadata"]["namespace"]
        resources.apply_dict(doc, ns)
    log.info("User Workload Monitoring enabled")


def apply_rbac(manifest_path: Path, namespace: str) -> None:
    """Apply the TrustyAI RBAC manifest (ServiceAccount + RoleBinding). Idempotent.

    Accepts a multi-document YAML file and applies each document individually.
    """
    log.info("Applying TrustyAI RBAC resources")
    log.debug("Manifest: %s", manifest_path.name)
    for doc in load_all(manifest_path):
        resources.apply_dict(doc, namespace)


def create_logger_ca_bundle(namespace: str) -> None:
    """Create the kserve-logger-ca-bundle ConfigMap.

    The annotation service.beta.openshift.io/inject-cabundle instructs
    the OpenShift service CA operator to populate the ConfigMap with the
    cluster CA bundle automatically after creation.

    Required before TrustyAI's payload logger can trust cluster-internal
    TLS endpoints.  Idempotent.
    """
    log.info("Creating kserve-logger-ca-bundle ConfigMap in '%s'", namespace)
    resources.apply_dict({
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": _LOGGER_CA_CM,
            "namespace": namespace,
            "annotations": {"service.beta.openshift.io/inject-cabundle": "true"},
        },
        "data": {},
    }, namespace)


def patch_inferenceservice_config(namespace: str) -> None:
    """Remove opendatahub.io/managed from inferenceservice-config.

    Required for InferenceServices using RawDeployment mode so that
    TrustyAI can inject its payload-logging sidecar without RHOAI
    reverting the ConfigMap change.  Idempotent.
    """
    log.info("Patching inferenceservice-config in '%s'", namespace)
    resources.patch(
        "ConfigMap",
        _ISVC_CONFIG_CM,
        {"metadata": {"annotations": {"opendatahub.io/managed": "false"}}},
        namespace=namespace,
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def apply_trustyai_service(manifest_path: Path, namespace: str) -> None:
    """Apply the TrustyAIService CR manifest. Idempotent."""
    log.info("Deploying TrustyAIService")
    log.debug("Manifest: %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def wait_until_ready(
    name: str,
    namespace: str,
    timeout: int = 300,
    on_tick: Callable[[float], Any] | None = None,
) -> None:
    """Block until the TrustyAIService reaches Ready. Raises TimeoutError."""
    log.info("Waiting for TrustyAIService '%s'", name)
    log.debug("Timeout: %ss", timeout)
    wait.wait_until_ready(_SERVICE_KIND, name, namespace, timeout=timeout, on_tick=on_tick)


def verify(name: str, namespace: str) -> None:
    """Assert the TrustyAIService is Ready. Raises RuntimeError if not."""
    log.info("Verifying TrustyAIService '%s'", name)
    if not resources.is_ready(_SERVICE_KIND, name, namespace):
        raise RuntimeError(
            f"TrustyAIService '{name}' is not ready in '{namespace}'."
        )
    log.info("TrustyAIService '%s' is Ready", name)


def delete_trustyai_service(name: str, namespace: str) -> None:
    """Delete the TrustyAIService CR and wait for removal."""
    log.info("Deleting TrustyAIService '%s'", name)
    resources.delete_manifest(_SERVICE_KIND, name, namespace)
    wait.wait_until_deleted(_SERVICE_KIND, name, namespace)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def get_url(name: str, namespace: str) -> str:
    """Return the public URL for the TrustyAI service.

    Looks up status.url on the TrustyAIService first, then falls back to
    the OpenShift Route created by the opendatahub.io/enable-route annotation.

    Raises:
        RuntimeError: If no URL can be resolved — call wait_until_ready() first.
    """
    url = resources.status(_SERVICE_KIND, name, namespace).get("url")
    if url:
        return url
    if resources.exists("Route", name, namespace):
        route = resources.get("Route", name, namespace)
        host  = route.get("spec", {}).get("host", "")
        if host:
            scheme = "https" if route.get("spec", {}).get("tls") else "http"
            return f"{scheme}://{host}"
    raise RuntimeError(
        f"TrustyAIService '{name}' has no URL — call wait_until_ready() first."
    )


def get_bearer_token(service_account: str, namespace: str) -> str:
    """Create and return a short-lived bearer token for the given ServiceAccount.

    Uses `oc create token` via the TokenRequest API.  The token is valid for
    the cluster default duration (typically 1 hour) and is not cached —
    call this function once per session and pass the result to trustyai_client.

    Args:
        service_account: Name of the ServiceAccount (e.g. "trustyai-user").
        namespace:        Namespace where the ServiceAccount lives.

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: If the TokenRequest fails.
    """
    log.info("Obtaining bearer token for ServiceAccount '%s'", service_account)
    result = subprocess.run(
        [
            "oc", "create", "token", service_account,
            "-n", namespace,
            "--output", "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create token for ServiceAccount '{service_account}': "
            f"{result.stderr.strip()}"
        )
    try:
        return json.loads(result.stdout)["status"]["token"]
    except (json.JSONDecodeError, KeyError):
        # Older oc versions return the token as plain text
        token = result.stdout.strip()
        if not token:
            raise RuntimeError(
                f"Empty token returned for ServiceAccount '{service_account}'."
            ) from None
        return token


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def delete_service_account(name: str, namespace: str) -> None:
    """Delete the TrustyAI ServiceAccount."""
    log.info("Deleting ServiceAccount '%s'", name)
    resources.delete_manifest("ServiceAccount", name, namespace)


def delete_role_binding(name: str, namespace: str) -> None:
    """Delete the TrustyAI RoleBinding."""
    log.info("Deleting RoleBinding '%s'", name)
    resources.delete_manifest("RoleBinding", name, namespace)
