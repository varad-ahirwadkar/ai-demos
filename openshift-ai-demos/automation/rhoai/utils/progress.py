"""Reusable progress indicators for long-running CLI operations.

Two primitives:

step() — phase indicator
    Owns a spinner and elapsed time.  Use for any operation where the
    user should see activity while waiting.

    with step("Deploying model"):
        do_work()

    with step("Waiting for InferenceService") as s:
        wait_until_ready(..., on_tick=s.tick)

header_step() + sub_step() — phased verification
    header_step() prints the phase label immediately and owns elapsed time.
    sub_step() prints a single completed milestone line the instant its
    block exits — no spinner, no Live context, no buffering.

    with header_step("Checking RHOAI platform", outcome="Platform ready"):
        with sub_step("Operator ready"):
            check_operator()
        with sub_step("DSCI 'default-dsci' ready"):
            check_dsci()

on_tick protocol
----------------
Pass ``on_tick=spinner.tick`` to any long-running call that accepts it.
The callee calls ``on_tick(elapsed_seconds)`` so the spinner text shows
live elapsed time.
"""

import sys
import time
from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.status import Status

_console = Console(stderr=False, highlight=False)


class _Spinner:
    """Thin wrapper around a Rich Status so callers can push tick updates."""

    def __init__(self, status: Status, label: str) -> None:
        self._status = status
        self._label  = label

    def tick(self, elapsed: float) -> None:
        """Update the spinner text with current elapsed time."""
        self._status.update(f"{self._label}  ({int(elapsed)}s)...")


@contextmanager
def step(label: str) -> Generator[_Spinner, None, None]:
    """Context manager: spin while work runs, print outcome when done.

    Args:
        label: Human-readable description shown next to the spinner.

    Yields:
        _Spinner — call spinner.tick(elapsed_seconds) from within the block
                   to show live elapsed time in the spinner text.

    Example::

        with step("Waiting for InferenceService") as s:
            wait_until_ready(..., on_tick=s.tick)
    """
    start = time.monotonic()

    if not sys.stdout.isatty():
        # Non-TTY (CI, pipe): print static lines, no spinner codes.
        _console.print(f"{label}...")
        spinner = _Spinner(Status(""), label)
        try:
            yield spinner
            elapsed = int(time.monotonic() - start)
            _console.print(f"\u2714  {label}  ({elapsed}s)")
        except Exception:
            _console.print(f"\u2716  {label}  failed")
            raise
        return

    with _console.status(f"{label}...", spinner="dots") as rich_status:
        spinner = _Spinner(rich_status, label)
        try:
            yield spinner
        except Exception:
            elapsed = int(time.monotonic() - start)
            _console.print(f"\u2716  {label}  failed  ({elapsed}s)")
            raise

    elapsed = int(time.monotonic() - start)
    _console.print(f"\u2714  {label}  ({elapsed}s)")


@contextmanager
def header_step(label: str, outcome: str | None = None) -> Generator[None, None, None]:
    """Phase indicator that prints its label immediately and owns elapsed time.

    Prints ``<label>...`` before any work starts.  Sub-steps nested inside
    use sub_step(), which prints each milestone the instant it completes.
    No spinner or Live context is created here — output streams freely.

    Args:
        label:   Header text printed before work starts.
        outcome: Text for the final ✔ / ✖ line.  Defaults to *label*.

    Example::

        with header_step("Checking RHOAI platform", outcome="Platform ready"):
            with sub_step("Operator ready"):
                check_operator()
    """
    resolved = outcome if outcome is not None else label
    start    = time.monotonic()

    _console.print(f"\n{label}...\n")

    try:
        yield
    except Exception:
        elapsed = int(time.monotonic() - start)
        _console.print(f"\n\u2716  {resolved}  failed  ({elapsed}s)")
        raise

    elapsed = int(time.monotonic() - start)
    _console.print(f"\n\u2714  {resolved}  ({elapsed}s)")


@contextmanager
def sub_step(label: str) -> Generator[None, None, None]:
    """Milestone indicator for use inside a header_step() block.

    Prints "  ✔  <label>" the moment its block exits cleanly, or
    "  ✖  <label>  failed" on exception.  No spinner, no Live context —
    _console.print() outside any active Live flushes immediately.

    Args:
        label: Completion description, e.g. "Operator ready".

    Example::

        with header_step("Checking RHOAI platform", outcome="Platform ready"):
            with sub_step("Operator ready"):
                check_operator()
    """
    try:
        yield
        _console.print(f"  \u2714  {label}")
    except Exception:
        _console.print(f"  \u2716  {label}  failed")
        raise
