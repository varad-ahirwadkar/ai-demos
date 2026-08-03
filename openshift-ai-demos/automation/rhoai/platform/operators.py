"""RHOAI operator lifecycle via OLM.

Manages Subscription, OperatorGroup, and CSV only.
Does not touch DSC, DSCI, or operand resources.
"""

from rhoai.ocp import resources, wait
from rhoai.platform import manifests
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def is_installed(name: str, namespace: str) -> bool:
    """Return True if the RHOAI operator CSV is in Succeeded phase."""
    return _csv_phase(resolve_csv_name(name, namespace), namespace) == "Succeeded"


def install(
    name: str,
    namespace: str,
    channel: str,
    repo_root: str,
    timeout: int,
) -> None:
    """Apply OperatorGroup + Subscription and wait for CSV to succeed."""
    log.info("Installing RHOAI operator (channel: %s)", channel)
    resources.apply_manifest(manifests.get_operator_group(repo_root), namespace)
    resources.apply_manifest(manifests.get_subscription(repo_root), namespace)
    wait_until_ready(name, namespace, timeout)


def upgrade(name: str, namespace: str, target_channel: str, timeout: int) -> None:
    """Switch OLM channel and wait for the new CSV to succeed."""
    log.info("Upgrading RHOAI operator to channel: %s", target_channel)
    resources.patch("Subscription", name, {"spec": {"channel": target_channel}}, namespace)
    wait_until_ready(name, namespace, timeout)


def wait_until_ready(name: str, namespace: str, timeout: int) -> None:
    """Block until the CSV for 'name' reaches Succeeded. Raises TimeoutError."""
    resolved = resolve_csv_name(name, namespace)
    log.info("Waiting for operator '%s' (timeout: %ss)", resolved, timeout)
    wait.wait_until(
        lambda: _csv_phase(resolved, namespace) == "Succeeded",
        f"CSV {resolved} Succeeded",
        timeout,
    )


def resolve_csv_name(package_name: str, namespace: str) -> str:
    """Return the versioned CSV name for a package, e.g. 'rhods-operator.3.5.0'.

    Looks up CSVs in the namespace and finds the one whose name starts with
    package_name. Falls back to package_name as-is if none is found, so that
    an already-versioned name passed directly still works.
    """
    csvs = resources.list_resources("ClusterServiceVersion", namespace)
    for csv in csvs:
        csv_name = csv.get("metadata", {}).get("name", "")
        if csv_name.startswith(package_name + ".") or csv_name == package_name:
            return csv_name
    return package_name


def verify(name: str, namespace: str) -> None:
    """Assert the operator CSV is Succeeded. Raises RuntimeError if not."""
    log.info("Verifying RHOAI operator")
    resolved = resolve_csv_name(name, namespace)
    phase = _csv_phase(resolved, namespace)
    if phase != "Succeeded":
        raise RuntimeError(
            f"Operator '{resolved}' is not ready (phase={phase!r}). "
            "Run 'rhoai platform deploy' to install it."
        )
    log.info("RHOAI operator is Succeeded")


def get_csv_info(name: str, namespace: str) -> dict[str, str]:
    """Return display info for the resolved CSV: name, version, phase."""
    resolved = resolve_csv_name(name, namespace)
    s = resources.status("ClusterServiceVersion", resolved, namespace)
    spec = resources.get("ClusterServiceVersion", resolved, namespace).get("spec", {})
    return {
        "name":    resolved,
        "version": spec.get("version", "unknown"),
        "phase":   s.get("phase", "Unknown"),
    }


def _csv_phase(name: str, namespace: str) -> str:
    return resources.status("ClusterServiceVersion", name, namespace).get("phase", "Unknown")
