"""DataScienceCluster (DSC) and DSCInitialization (DSCI) lifecycle."""

from pathlib import Path

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def apply_dsci(manifest_path: Path) -> None:
    """Apply the DSCInitialization manifest. Idempotent."""
    log.info("Applying DSCInitialization from %s", manifest_path.name)
    resources.apply_manifest(manifest_path)


def apply_dsc(manifest_path: Path) -> None:
    """Apply the DataScienceCluster manifest. Idempotent."""
    log.info("Applying DataScienceCluster from %s", manifest_path.name)
    resources.apply_manifest(manifest_path)


def wait_until_ready(name: str, timeout: int) -> None:
    """Block until the DataScienceCluster reaches Ready phase. Raises TimeoutError."""
    log.info("Waiting for DSC '%s' (timeout: %ss)", name, timeout)
    wait.wait_until(lambda: _is_ready(name), f"DataScienceCluster/{name} Ready", timeout)


def verify_dsci(name: str) -> None:
    """Assert the DSCInitialization is in Ready phase. Raises RuntimeError if not."""
    log.info("Verifying DSCInitialization '%s'", name)
    phase = resources.status("DSCInitialization", name).get("phase", "Unknown")
    if phase != "Ready":
        raise RuntimeError(
            f"DSCInitialization '{name}' is not ready (phase={phase!r}). "
            "Run 'rhoai platform deploy' to configure it."
        )
    log.info("DSCInitialization '%s' is Ready", name)


def verify(name: str) -> None:
    """Assert the DSC is in Ready phase. Raises RuntimeError if not."""
    log.info("Verifying DataScienceCluster '%s'", name)
    if not _is_ready(name):
        phase = resources.status("DataScienceCluster", name).get("phase", "Unknown")
        raise RuntimeError(
            f"DataScienceCluster '{name}' is not ready (phase={phase!r}). "
            "Run 'rhoai platform deploy' to configure it."
        )
    log.info("DataScienceCluster '%s' is Ready", name)


def delete_dsc(name: str) -> None:
    """Delete the DataScienceCluster and wait for removal."""
    log.info("Deleting DataScienceCluster '%s'", name)
    resources.delete_manifest("DataScienceCluster", name)
    wait.wait_until_deleted("DataScienceCluster", name)


def delete_dsci(name: str) -> None:
    """Delete the DSCInitialization and wait for removal."""
    log.info("Deleting DSCInitialization '%s'", name)
    resources.delete_manifest("DSCInitialization", name)
    wait.wait_until_deleted("DSCInitialization", name)


def get_component_states(name: str) -> dict[str, str]:
    """Return a dict of component -> managementState from the DSC spec.

    Example: {"kserve": "Managed", "dashboard": "Managed", "trustyai": "Managed", ...}
    """
    obj = resources.get("DataScienceCluster", name)
    components = obj.get("spec", {}).get("components", {})
    return {
        comp: cfg.get("managementState", "Unknown")
        for comp, cfg in components.items()
        if isinstance(cfg, dict)
    }


def _is_ready(name: str) -> bool:
    return resources.status("DataScienceCluster", name).get("phase") == "Ready"
