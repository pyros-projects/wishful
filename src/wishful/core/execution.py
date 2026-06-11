"""Shared execution helpers for generated code and user callables.

Everything wishful runs on behalf of the user — candidate tests, benchmarks,
fitness functions — funnels through here, so the bounding/containment policy
lives in one place. This module is also the planned casefile hook point
(spec 003): execution-evidence capture attaches here without touching the
explore/evolve loops.
"""

from __future__ import annotations

import threading
from typing import Any, Callable


def run_user_callable(
    func: Callable[[], Any], timeout: float
) -> tuple[bool, Any, str | None]:
    """Run an untrusted user callable under a wall-clock timeout.

    Returns ``(ok, value, error)``. A timeout or any BaseException (including
    SystemExit) is reported as a failure rather than propagating — search loops
    must survive a runaway or exiting candidate. CPython cannot cancel a
    running thread, so a timed-out callable keeps running, but the worker is a
    **daemon** thread: it is abandoned without leaking into interpreter
    shutdown or accumulating non-daemon threads across many timeouts.
    """
    outcome: dict[str, Any] = {}

    def _runner() -> None:
        try:
            outcome["value"] = func()
        except BaseException as exc:  # noqa: BLE001 - SystemExit/etc. must be contained
            outcome["error"] = exc

    worker = threading.Thread(target=_runner, name="wishful-user-call", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        return False, None, f"exceeded {timeout}s timeout"
    if "error" in outcome:
        exc = outcome["error"]
        return False, None, f"{type(exc).__name__}: {exc}"
    return True, outcome.get("value"), None
