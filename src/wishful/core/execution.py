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

from wishful.config import settings
from wishful.safety.validator import validate_code


def compile_and_exec(
    source: str,
    function_name: str,
    *,
    filename: str = "<wishful>",
    on_executed: Callable[[str, dict[str, Any]], None] | None = None,
) -> Callable[..., Any]:
    """Validate, compile, and execute ``source``; return the named callable.

    The one compile-and-exec path for the search loops (explorer, evolver) and
    the casefile hook point for spec 003: ``on_executed`` fires with
    ``(source, namespace)`` only after execution succeeds, so evidence capture
    can be deferred — it never runs inside an import lock and a failing
    callback cannot poison the compiled function.

    Raises ``ValueError`` when the executed source does not define
    ``function_name`` as a callable; ``SecurityError``/``SyntaxError``
    propagate from validation/compilation.
    """
    validate_code(source, allow_unsafe=settings.allow_unsafe)
    namespace: dict[str, Any] = {}
    exec(compile(source, filename, "exec"), namespace)
    candidate = namespace.get(function_name)
    if not callable(candidate):
        raise ValueError(f"source did not define callable {function_name!r}")
    if on_executed is not None:
        on_executed(source, namespace)
    return candidate


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
