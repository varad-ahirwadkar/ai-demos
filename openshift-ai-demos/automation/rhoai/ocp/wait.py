"""Polling helpers for Kubernetes resource state transitions.

All reads delegate to ocp.resources.
Dependency is one-way: wait.py → resources.py (never the reverse).
"""

import time
from collections.abc import Callable

from rhoai.ocp import resources
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

_DEFAULT_INTERVAL = 10  # seconds between polls


def wait_until_ready(
    kind: str,
    name: str,
    namespace: str | None = None,
    timeout: int = 300,
    interval: int = _DEFAULT_INTERVAL,
) -> None:
    """Block until ocp.resources.is_ready() returns True. Raises TimeoutError."""
    wait_until(
        lambda: resources.is_ready(kind, name, namespace),
        f"{kind}/{name} ready",
        timeout,
        interval,
    )


def wait_until_deleted(
    kind: str,
    name: str,
    namespace: str | None = None,
    timeout: int = 120,
    interval: int = 5,
) -> None:
    """Block until the resource no longer exists. Raises TimeoutError."""
    wait_until(
        lambda: not resources.exists(kind, name, namespace),
        f"{kind}/{name} deleted",
        timeout,
        interval,
    )


def wait_until(
    condition: Callable[[], bool],
    description: str,
    timeout: int = 300,
    interval: int = _DEFAULT_INTERVAL,
) -> None:
    """Block until condition() returns True or timeout is exceeded.

    Use when wait_until_ready / wait_until_deleted don't fit (e.g. custom CRD condition).
    Raises TimeoutError with description in the message.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            log.debug("Ready: %s", description)
            return
        log.debug("Waiting: %s", description)
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s waiting for: {description}")
