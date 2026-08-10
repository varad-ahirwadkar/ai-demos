"""Generic Kubernetes/OpenShift resource operations.

The only module that talks to the Kubernetes API.
All platform modules call this — never the SDK directly.
"""

import subprocess
from pathlib import Path
from typing import Any

import urllib3
from kubernetes import config as k8s_config
from kubernetes import dynamic
from kubernetes.client import ApiClient
from kubernetes.dynamic.exceptions import NotFoundError

from rhoai.utils.logger import get_logger
from rhoai.utils.yaml_io import load

# OpenShift clusters commonly use self-signed certificates.
# Suppress the per-request noise; the kubeconfig verify_ssl setting controls
# whether verification actually happens.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = get_logger(__name__)

# API group/version hints for CRDs the dynamic client cannot discover by kind alone.
# Add an entry here when discovery fails in practice.
_API_HINTS: dict[str, str] = {
    # core v1 — pin these to avoid ambiguity with OpenShift CRDs of the same kind name
    "Node":                    "v1",
    "Namespace":               "v1",
    "Pod":                     "v1",
    "Secret":                  "v1",
    "ConfigMap":               "v1",
    "PersistentVolumeClaim":   "v1",
    "StorageClass":            "storage.k8s.io/v1",
    "PersistentVolume":        "v1",
    # OpenShift / OLM
    "ClusterVersion":          "config.openshift.io/v1",
    "Subscription":            "operators.coreos.com/v1alpha1",
    "OperatorGroup":           "operators.coreos.com/v1",
    "ClusterServiceVersion":   "operators.coreos.com/v1alpha1",
    "SelfSubjectAccessReview": "authorization.k8s.io/v1",
    "Template":                "template.openshift.io/v1",
    # RHOAI CRDs
    "DataScienceCluster":      "datasciencecluster.opendatahub.io/v2",
    "DSCInitialization":       "dscinitialization.opendatahub.io/v1",
    "InferenceService":        "serving.kserve.io/v1beta1",
    "ServingRuntime":          "serving.kserve.io/v1alpha1",
    "GuardrailsOrchestrator":  "trustyai.opendatahub.io/v1alpha1",
    "TrustyAIService":         "trustyai.opendatahub.io/v1alpha1",
}


_dynamic_client: dynamic.DynamicClient | None = None


def _client() -> dynamic.DynamicClient:
    """Return a process-scoped DynamicClient, creating it on first call."""
    global _dynamic_client
    if _dynamic_client is None:
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        _dynamic_client = dynamic.DynamicClient(ApiClient())
    return _dynamic_client


def _resource(client: dynamic.DynamicClient, kind: str, api_version: str | None = None) -> Any:
    if api_version:
        return client.resources.get(api_version=api_version, kind=kind)
    if kind in _API_HINTS:
        return client.resources.get(api_version=_API_HINTS[kind], kind=kind)
    return client.resources.get(kind=kind)


def process_template(path: Path, namespace: str) -> None:
    """Process an OpenShift Template and apply all rendered objects.

    Strips metadata.namespace from the Template before processing so that
    oc process accepts the target namespace regardless of what namespace is
    baked into the Template file itself.

    Equivalent to:
        oc process --namespace=<namespace> -f <stripped-template> | oc apply -n <namespace> -f -

    Idempotent. Raises RuntimeError if oc is not on PATH or any step fails.
    """
    import json
    import tempfile

    log.debug("Processing Template %s in '%s'", path.name, namespace)

    # Load the template and remove metadata.namespace so oc process does not
    # reject it when the baked-in namespace differs from the target namespace.
    template = load(path)
    template.get("metadata", {}).pop("namespace", None)
    template_json = json.dumps(template)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        tmp.write(template_json)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["oc", "process", f"--namespace={namespace}", "-f", tmp_path],
            capture_output=True,
            text=True,
        )
    finally:
        import os
        os.unlink(tmp_path)

    if result.returncode != 0:
        raise RuntimeError(
            f"oc process failed for {path.name}: {result.stderr.strip()}"
        )
    apply_result = subprocess.run(
        ["oc", "apply", "-n", namespace, "-f", "-"],
        input=result.stdout,
        capture_output=True,
        text=True,
    )
    if apply_result.returncode != 0:
        raise RuntimeError(
            f"oc apply failed after processing {path.name}: {apply_result.stderr.strip()}"
        )
    log.debug("Template %s applied successfully", path.name)


def apply_manifest(path: Path, namespace: str | None = None) -> dict[str, Any]:
    """Load a YAML file and apply it via server-side apply. Idempotent."""
    return apply_dict(load(path), namespace)


def apply_dict(manifest: dict[str, Any], namespace: str | None = None) -> dict[str, Any]:
    """Apply a manifest dict via server-side apply. Idempotent."""
    client = _client()
    kind = manifest["kind"]
    res = _resource(client, kind, manifest.get("apiVersion"))
    effective_ns = namespace or manifest.get("metadata", {}).get("namespace")
    name = manifest.get("metadata", {}).get("name", "?")
    log.debug("Applying %s/%s (ns=%s)", kind, name, effective_ns)
    return res.server_side_apply(
        body=manifest,
        namespace=effective_ns,
        field_manager="rhoai-automation",
        force_conflicts=True,
    ).to_dict()


def delete_manifest(kind: str, name: str, namespace: str | None = None) -> None:
    """Delete a resource by kind and name. Idempotent — silent if already absent."""
    client = _client()
    res = _resource(client, kind)
    log.debug("Deleting %s/%s (ns=%s)", kind, name, namespace)
    try:
        res.delete(name=name, namespace=namespace)
    except NotFoundError:
        pass


def exists(kind: str, name: str, namespace: str | None = None) -> bool:
    """Return True if the named resource exists on the cluster."""
    try:
        get(kind, name, namespace)
        return True
    except NotFoundError:
        return False


def get(kind: str, name: str, namespace: str | None = None) -> dict[str, Any]:
    """Return the full resource object. Raises NotFoundError if absent."""
    client = _client()
    return _resource(client, kind).get(name=name, namespace=namespace).to_dict()


def patch(
    kind: str,
    name: str,
    patch_body: dict[str, Any],
    namespace: str | None = None,
    strategy: str = "merge",
) -> dict[str, Any]:
    """Patch a resource. strategy: 'merge' (default), 'json', or 'strategic'."""
    client = _client()
    res = _resource(client, kind)
    content_type = {
        "merge":    "application/merge-patch+json",
        "json":     "application/json-patch+json",
        "strategic": "application/strategic-merge-patch+json",
    }.get(strategy, "application/merge-patch+json")
    log.debug("Patching %s/%s (ns=%s)", kind, name, namespace)
    return res.patch(
        name=name, namespace=namespace, body=patch_body, content_type=content_type
    ).to_dict()


def status(kind: str, name: str, namespace: str | None = None) -> dict[str, Any]:
    """Return the .status sub-object of a resource, or {} if absent."""
    return get(kind, name, namespace).get("status") or {}


def is_ready(kind: str, name: str, namespace: str | None = None) -> bool:
    """Return True if the resource satisfies its readiness condition.

    Dispatch by kind:
        Deployment            — availableReplicas >= replicas
        Pod                   — phase Running and all containers ready
        Job                   — succeeded >= 1
        DataScienceCluster    — .status.phase == "Ready"
        ClusterServiceVersion — .status.phase == "Succeeded"
        others                — conditions[type=Ready, status=True]
    """
    try:
        s = status(kind, name, namespace)
    except NotFoundError:
        return False

    if kind == "Deployment":
        return s.get("availableReplicas", 0) >= s.get("replicas", 1)

    if kind == "Pod":
        return s.get("phase") == "Running" and all(
            cs.get("ready", False) for cs in s.get("containerStatuses") or []
        )

    if kind == "Job":
        return s.get("succeeded", 0) >= 1

    if kind in ("DataScienceCluster", "DSCInitialization"):
        return s.get("phase") == "Ready"

    if kind == "ClusterServiceVersion":
        return s.get("phase") == "Succeeded"

    return any(
        c.get("type") == "Ready" and c.get("status") == "True"
        for c in s.get("conditions") or []
    )


def list_resources(
    kind: str,
    namespace: str | None = None,
    label_selector: str = "",
) -> list[dict[str, Any]]:
    """Return all resources of the given kind, optionally filtered by namespace and label."""
    client = _client()
    res = _resource(client, kind)
    kwargs: dict[str, Any] = {}
    if namespace:
        kwargs["namespace"] = namespace
    if label_selector:
        kwargs["label_selector"] = label_selector
    return res.get(**kwargs).to_dict().get("items", [])
