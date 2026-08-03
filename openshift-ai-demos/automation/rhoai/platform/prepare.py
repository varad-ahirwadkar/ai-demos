"""Platform preparation — cluster validation and namespace setup."""

from typing import Any

from rhoai.ocp import resources
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def prepare_platform(config: dict[str, Any]) -> None:
    """Validate login, permissions, storage, and namespace — in that order."""
    log.info("Starting platform preparation")
    validate_login()
    validate_permissions(config["operator"]["namespace"])
    validate_storage(config.get("storage", {}).get("class_name", ""))
    validate_namespace(config["cluster"]["namespace"])
    log.info("Platform preparation complete")


def validate_login() -> None:
    """Confirm the CLI is authenticated. Raises RuntimeError if unreachable."""
    log.info("Validating cluster login")
    try:
        resources.get("ClusterVersion", "version")
    except Exception as exc:
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
    except Exception as exc:
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

    is_sno = len(nodes) == 1

    # On SNO the single node carries both master and worker labels — treat it as worker.
    worker_nodes = [n for n in nodes if _has_role(n, "worker")] or nodes

    # Per-node breakdown for workers
    worker_details = []
    for n in worker_nodes:
        name = n.get("metadata", {}).get("name", "?")
        cap  = n.get("status", {}).get("capacity", {})
        cpu_cores = _parse_cpu(cap.get("cpu", "0")) // 1000
        mem_gib   = _parse_memory_ki(cap.get("memory", "0Ki")) // (1024 * 1024)
        gpu       = int(cap.get("nvidia.com/gpu", 0))
        worker_details.append({
            "name":   name,
            "cpu":    f"{cpu_cores} cores",
            "memory": f"{mem_gib} GiB",
            "gpu":    gpu,
        })

    # Aggregate PV capacity per StorageClass split by phase
    # Phase "Bound"     = in use by a PVC
    # Phase "Available" = pre-provisioned, not yet claimed
    # Phase "Released"  = was bound, PVC deleted, not yet recycled
    pv_bound_ki:     dict[str, int] = {}
    pv_available_ki: dict[str, int] = {}

    for pv in pvs:
        sc_name  = pv.get("spec", {}).get("storageClassName", "unknown")
        capacity = pv.get("spec", {}).get("capacity", {}).get("storage", "0")
        phase    = pv.get("status", {}).get("phase", "Unknown")
        ki       = _parse_memory_ki(capacity)
        if phase == "Bound":
            pv_bound_ki[sc_name]     = pv_bound_ki.get(sc_name, 0) + ki
        elif phase in ("Available", "Released"):
            pv_available_ki[sc_name] = pv_available_ki.get(sc_name, 0) + ki

    sc_names = [sc.get("metadata", {}).get("name", "?") for sc in classes]
    storage_summary: dict[str, dict[str, str]] = {}
    for sc in sc_names:
        bound_gib = pv_bound_ki.get(sc, 0) // (1024 * 1024)
        avail_gib = pv_available_ki.get(sc, 0) // (1024 * 1024)
        storage_summary[sc] = {
            "used":      f"{bound_gib} GiB",
            "available": f"{avail_gib} GiB",
        }

    return {
        "openshift_version": cv.get("status", {}).get("desired", {}).get("version", "unknown"),
        "topology":          "SNO" if is_sno else "Multi-node",
        "node_count":        len(nodes),
        "worker_count":      len(worker_nodes),
        "worker_nodes":      worker_details,
        "storage_summary":   storage_summary,
    }


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
