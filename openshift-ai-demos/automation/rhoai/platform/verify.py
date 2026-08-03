"""Platform health verification.

Checks only the core platform components: operator CSV, DSCI, and DSC.
InferenceServices and storage are use-case concerns — each use case's
verify() is responsible for those.
"""

from dataclasses import dataclass
from typing import Any

from rhoai.platform import dsc, operators
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""


def verify_platform(config: dict[str, Any]) -> list[CheckResult]:
    """Run core platform health checks: operator, DSCI, and DSC."""
    op_name   = config["operator"]["name"]
    op_ns     = config["operator"]["namespace"]
    results = [
        _run("RHOAI Operator",        lambda: operators.verify(op_name, op_ns)),
        _run("DSCInitialization",     lambda: dsc.verify_dsci(config["dsc"]["dsci_name"])),
        _run("DataScienceCluster",    lambda: dsc.verify(config["dsc"]["name"])),
    ]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        line = f"  [{status}] {r.name}"
        if r.message:
            line += f" — {r.message}"
        log.info(line)

    failed = [r for r in results if not r.passed]
    if failed:
        raise RuntimeError("Platform verification failed: " + ", ".join(r.name for r in failed))
    return results


def _run(name: str, check_fn) -> CheckResult:
    try:
        check_fn()
        return CheckResult(name=name, passed=True)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name=name, passed=False, message=str(exc))
