"""Platform preparation — cluster validation, namespace setup, and bootstrap."""

from typing import Any

from rhoai.ocp import resources
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def prepare_platform(config: dict[str, Any]) -> None:
    """Validate login, storage, and namespace — in that order."""
    log.info("Starting platform preparation")
    validate_login()
    validate_storage(config.get("storage", {}).get("class_name", ""))
    validate_namespace(config["cluster"]["namespace"])
    log.info("Platform preparation complete")


def deploy_platform(config: dict[str, Any]) -> None:
    """Validate prerequisites, install the RHOAI operator, and configure DSC/DSCI.

    Consolidates the bootstrap sequence shared by the platform CLI command and
    every use-case deploy function:
        1. prepare_platform  — login, storage, namespace
        2. operator          — install or wait for the existing CSV
        3. DSC/DSCI          — apply manifests only when not already Ready,
                               then wait for Ready

    Callers that need to run further steps (e.g. storage secrets, model serving)
    simply continue after this function returns.
    """
    from rhoai.platform import dsc, manifests, operators

    repo_root  = config["repo_root"]
    op_name    = config["operator"]["name"]
    op_ns      = config["operator"]["namespace"]
    op_timeout = config["timeouts"]["operator_ready"]
    dsc_name   = config["dsc"]["name"]
    dsci_name  = config["dsc"]["dsci_name"]
    dsc_timeout = config["timeouts"]["dsc_ready"]

    prepare_platform(config)

    if not operators.is_installed(op_name, op_ns):
        operators.install(op_name, op_ns, config["operator"]["channel"], repo_root, op_timeout)
    else:
        operators.wait_until_ready(op_name, op_ns, op_timeout)

    # Always apply DSCI: idempotent, only initialisation settings.
    dsc.apply_dsci(manifests.get_dsci(repo_root))

    # Always apply DSC: ensures any newly-enabled components in the manifest
    # are reconciled even when the cluster already has a DSC.
    dsc.apply_dsc(manifests.get_dsc(repo_root))

    dsc.wait_until_ready(dsc_name, dsc_timeout)


def validate_login() -> None:
    """Confirm the CLI is authenticated. Raises RuntimeError if unreachable."""
    log.info("Validating cluster login")
    try:
        resources.get("ClusterVersion", "version")
    except (ConnectionError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Cannot reach cluster — run 'oc login' first. Detail: {exc}") from exc
    log.info("Cluster login confirmed")


def validate_permissions(operator_namespace: str) -> None:
    """Confirm create access on Subscriptions in the operator namespace.

    Uses SelfSubjectAccessReview — does not require cluster-admin explicitly,
    but RHOAI installation in practice does.
    """
    log.info("Validating RBAC permissions")
    review = {
        "apiVersion": "authorization.k8s.io/v1",
        "kind": "SelfSubjectAccessReview",
        "spec": {
            "resourceAttributes": {
                "namespace": operator_namespace,
                "verb": "create",
                "group": "operators.coreos.com",
                "resource": "subscriptions",
            }
        },
    }
    try:
        result = resources.apply_dict(review)
        allowed = result.get("status", {}).get("allowed", False)
    except RuntimeError as exc:
        raise RuntimeError(f"Permission check failed: {exc}") from exc

    if not allowed:
        raise RuntimeError(
            f"Insufficient permissions: cannot create Subscriptions in '{operator_namespace}'. "
            "Cluster-admin role is required."
        )
    log.info("RBAC permissions confirmed")


def validate_storage(class_name: str) -> None:
    """Confirm a suitable StorageClass exists.

    If class_name is set, verifies that exact class. Otherwise, verifies
    at least one StorageClass is present on the cluster.
    """
    log.info("Validating storage classes")
    if class_name:
        if not resources.exists("StorageClass", class_name):
            raise RuntimeError(
                f"StorageClass '{class_name}' not found. "
                "Update storage.class_name in your config or leave it empty "
                "to use the cluster default."
            )
        log.info("StorageClass '%s' confirmed", class_name)
    else:
        classes = resources.list_resources("StorageClass")
        if not classes:
            raise RuntimeError(
                "No StorageClasses found. Create one before deploying RHOAI workloads."
            )
        names = [sc.get("metadata", {}).get("name", "?") for sc in classes]
        log.info("StorageClasses available: %s", ", ".join(names))


def validate_namespace(namespace: str) -> None:
    """Ensure the namespace exists, creating it if absent."""
    if not resources.exists("Namespace", namespace):
        log.info("Namespace '%s' not found — creating", namespace)
        resources.apply_dict({
            "apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace},
        })
    else:
        log.info("Namespace '%s' exists", namespace)


def get_cluster_info() -> dict[str, Any]:
    """Return cluster metadata: version, topology, per-role CPU/memory/GPU, storage summary."""
    log.info("Collecting cluster info")
    cv      = resources.get("ClusterVersion", "version")
    nodes   = resources.list_resources("Node")
    classes = resources.list_resources("StorageClass")
    pvs     = resources.list_resources("PersistentVolume")

    worker_nodes = [n for n in nodes if _has_role(n, "worker")] or nodes

    return {
        "openshift_version": _openshift_version(cv),
        "topology":          "SNO" if len(nodes) == 1 else "Multi-node",
        "node_count":        len(nodes),
        "worker_count":      len(worker_nodes),
        "worker_nodes":      _worker_details(worker_nodes),
        "storage_summary":   _storage_summary(classes, pvs),
    }


def _openshift_version(cluster_version: dict[str, Any]) -> str:
    return cluster_version.get("status", {}).get("desired", {}).get("version", "unknown")


def _worker_details(worker_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return per-node CPU/memory/GPU breakdown for each worker node."""
    result = []
    for n in worker_nodes:
        name = n.get("metadata", {}).get("name", "?")
        cap  = n.get("status", {}).get("capacity", {})
        result.append({
            "name":   name,
            "cpu":    f"{_parse_cpu(cap.get('cpu', '0')) // 1000} cores",
            "memory": f"{_parse_memory_ki(cap.get('memory', '0Ki')) // (1024 * 1024)} GiB",
            "gpu":    int(cap.get("nvidia.com/gpu", 0)),
        })
    return result


def _storage_summary(
    classes: list[dict[str, Any]],
    pvs: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Return per-StorageClass used/available GiB aggregated from PV phases."""
    # Phase "Bound"               = in use by a PVC
    # Phase "Available"/"Released"= pre-provisioned or pending recycle
    pv_bound_ki:     dict[str, int] = {}
    pv_available_ki: dict[str, int] = {}

    for pv in pvs:
        sc    = pv.get("spec", {}).get("storageClassName", "unknown")
        ki    = _parse_memory_ki(pv.get("spec", {}).get("capacity", {}).get("storage", "0"))
        phase = pv.get("status", {}).get("phase", "Unknown")
        if phase == "Bound":
            pv_bound_ki[sc]     = pv_bound_ki.get(sc, 0) + ki
        elif phase in ("Available", "Released"):
            pv_available_ki[sc] = pv_available_ki.get(sc, 0) + ki

    summary: dict[str, dict[str, str]] = {}
    for sc_obj in classes:
        sc = sc_obj.get("metadata", {}).get("name", "?")
        summary[sc] = {
            "used":      f"{pv_bound_ki.get(sc, 0) // (1024 * 1024)} GiB",
            "available": f"{pv_available_ki.get(sc, 0) // (1024 * 1024)} GiB",
        }
    return summary


def _has_role(node: dict[str, Any], role: str) -> bool:
    labels = node.get("metadata", {}).get("labels", {})
    return f"node-role.kubernetes.io/{role}" in labels


def _parse_cpu(value: str) -> int:
    """Return CPU as millicores. Handles '4' (cores) and '4000m' (millicores)."""
    value = value.strip()
    if value.endswith("m"):
        return int(value[:-1])
    return int(value) * 1000


def _parse_memory_ki(value: str) -> int:
    """Return memory in kibibytes. Handles Ki, Mi, Gi, and plain bytes."""
    value = value.strip()
    if value.endswith("Ki"):
        return int(value[:-2])
    if value.endswith("Mi"):
        return int(value[:-2]) * 1024
    if value.endswith("Gi"):
        return int(value[:-2]) * 1024 * 1024
    if value.endswith("Ti"):
        return int(value[:-2]) * 1024 * 1024 * 1024
    # plain bytes
    return int(value) // 1024
