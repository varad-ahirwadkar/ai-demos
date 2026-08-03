"""Storage configuration — S3 credentials, Secrets, and PVCs."""

import base64
from pathlib import Path
from typing import Any

from rhoai.ocp import resources, wait
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def apply_s3_secret(manifest_path: Path, namespace: str) -> None:
    """Apply the S3 credentials Secret manifest. Idempotent."""
    log.info("Applying S3 credentials from %s", manifest_path.name)
    resources.apply_manifest(manifest_path, namespace)


def create_secret(
    name: str, namespace: str, data: dict[str, str], secret_type: str = "Opaque"
) -> None:
    """Create or update a Secret. Values are plain strings; base64 is applied here."""
    log.info("Creating Secret '%s' in '%s'", name, namespace)
    resources.apply_dict({
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace},
        "type": secret_type,
        "data": {k: base64.b64encode(v.encode()).decode() for k, v in data.items()},
    }, namespace)


def create_pvc(
    name: str,
    namespace: str,
    size: str,
    storage_class: str = "",
    access_mode: str = "ReadWriteOnce",
) -> None:
    """Create a PVC. Idempotent. Raises RuntimeError if storage_class does not exist."""
    if resources.exists("PersistentVolumeClaim", name, namespace):
        log.info("PVC '%s' already exists — skipping", name)
        return
    if storage_class and not resources.exists("StorageClass", storage_class):
        raise RuntimeError(f"StorageClass '{storage_class}' not found.")
    log.info("Creating PVC '%s' (%s, %s)", name, size, storage_class or "default class")
    spec: dict[str, Any] = {
        "accessModes": [access_mode],
        "resources": {"requests": {"storage": size}},
    }
    if storage_class:
        spec["storageClassName"] = storage_class
    resources.apply_dict({
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": name, "namespace": namespace},
        "spec": spec,
    }, namespace)


def verify(s3_secret_name: str, namespace: str) -> None:
    """Assert the S3 credentials Secret exists. Raises RuntimeError if absent."""
    log.info("Verifying storage Secret '%s'", s3_secret_name)
    if not resources.exists("Secret", s3_secret_name, namespace):
        raise RuntimeError(
            f"S3 credentials Secret '{s3_secret_name}' not found in namespace '{namespace}'. "
            "Run 'rhoai platform deploy' to configure storage."
        )
    log.info("Storage Secret '%s' confirmed", s3_secret_name)


def delete_pvc(name: str, namespace: str) -> None:
    """Delete a PVC and wait for removal."""
    log.info("Deleting PVC '%s'", name)
    resources.delete_manifest("PersistentVolumeClaim", name, namespace)
    wait.wait_until_deleted("PersistentVolumeClaim", name, namespace)
