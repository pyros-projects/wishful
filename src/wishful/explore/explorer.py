"""Core explore() implementation with async LLM calls."""

from __future__ import annotations

import ast
import asyncio
import concurrent.futures
import os
import re
import sys
import threading
import time
import warnings
from functools import partial
from typing import Callable, List, Literal, Optional, Tuple, Union

from wishful.cache.manager import read_cached, write_cached
from wishful.config import settings
from wishful.core.execution import compile_and_exec, run_user_callable
from wishful.explore.exceptions import ExplorationError
from wishful.logging import logger
from wishful.explore.progress import (
    AsyncExploreLiveDisplay,
    ExploreProgress,
    save_exploration_results,
)
from wishful.explore.variant import VariantMetadata, wrap_with_metadata
from wishful.llm.client import agenerate_module_code
from wishful.types.registry import get_all_type_schemas, get_output_type_for_function
from wishful.safety.validator import SecurityError, validate_code

# Suppress litellm's fire-and-forget logging coroutines being abandoned at
# process exit. Scoped to litellm's Logging.* coroutines only — a user's own
# forgotten ``await`` still warns. (GC-time warnings can't be scoped by call
# site, so message-scoping is the tightest filter possible.)
warnings.filterwarnings(
    "ignore",
    message=r".*coroutine 'Logging\..*' was never awaited.*",
    category=RuntimeWarning,
)

# explore() runs its async pipeline on ONE persistent loop owned by wishful,
# living on a dedicated daemon thread. Verified 2026-06-11 against gpt-4.1 on
# litellm 1.88.1: per-call asyncio.run() still abandons litellm's
# Logging.async_success_handler coroutines (the loop dies before they run), so
# the plan's conservative owned-loop design applies — never the host's loop,
# never nest_asyncio.
_loop_lock = threading.Lock()
_owned_loop: Optional[asyncio.AbstractEventLoop] = None
_owned_thread: Optional[threading.Thread] = None
_owned_pid: Optional[int] = None


def _get_owned_loop() -> asyncio.AbstractEventLoop:
    """Start (or restart) and return wishful's background event loop.

    A loop is only reusable while its runner thread is alive in THIS process:
    a thread killed by an exception leaves ``is_closed() == False`` but never
    runs another callback, and a fork (Linux-default multiprocessing) clones
    the loop object without its thread — both used to hang future.result()
    forever. Detect either case and start a fresh loop+thread pair.
    """
    global _owned_loop, _owned_thread, _owned_pid
    with _loop_lock:
        if (
            _owned_loop is not None
            and not _owned_loop.is_closed()
            and _owned_thread is not None
            and _owned_thread.is_alive()
            and _owned_pid == os.getpid()
        ):
            return _owned_loop
        if _owned_loop is not None and not _owned_loop.is_closed() and _owned_pid == os.getpid():
            _owned_loop.close()  # dead thread; release the loop's resources
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_forever, name="wishful-explore-loop", daemon=True
        )
        thread.start()
        _owned_loop, _owned_thread, _owned_pid = loop, thread, os.getpid()
        return loop


def _run_async(coro):
    """Run an exploration coroutine on the owned loop and block for the result.

    Safe both from plain sync code and from inside a running event loop
    (Jupyter): the coroutine executes on wishful's background loop, so the
    host's loop is never re-entered or monkeypatched — the calling thread
    simply blocks until the exploration finishes, as a synchronous explore()
    has always done.

    The wait is a watchdog poll rather than a bare ``future.result()``: if the
    loop thread dies mid-run, the future would otherwise never resolve and the
    caller would hang forever.
    """
    future = asyncio.run_coroutine_threadsafe(coro, _get_owned_loop())
    try:
        while True:
            try:
                return future.result(timeout=1.0)
            except concurrent.futures.TimeoutError:
                if _owned_thread is not None and not _owned_thread.is_alive():
                    future.cancel()
                    raise RuntimeError(
                        "wishful's exploration event-loop thread died mid-run; "
                        "the next explore() call will start a fresh loop"
                    ) from None
    except KeyboardInterrupt:
        future.cancel()
        raise


def _merge_into_module(existing, function_name: str, winner_source: str) -> str:
    """Merge a winning variant into an existing cached module.

    Replaces only the explored function and preserves any other symbols already
    cached in the module — exploring one function must not wipe its siblings. If
    there is no existing module (or it cannot be parsed), the winner is used as-is.
    """
    if not existing or not existing.strip():
        return winner_source
    try:
        tree = ast.parse(existing)
    except SyntaxError:
        return winner_source
    kept = [
        node
        for node in tree.body
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == function_name
        )
    ]
    if len(kept) == len(tree.body):
        prefix = existing.rstrip()  # function wasn't here before; keep verbatim
    else:
        tree.body = kept
        prefix = ast.unparse(tree).rstrip()
    if not prefix.strip():
        return winner_source
    # The winner is appended after the kept siblings, so any top-level name it
    # shares with a sibling silently rebinds that sibling (later definition wins at
    # exec). We can't safely rename without risking the winner, but a silent wipe
    # violates the "exploring one function must not wipe its siblings" contract —
    # surface it loudly so the caller knows the cache no longer holds the original.
    collisions = (
        _top_level_names(prefix) & _top_level_names(winner_source)
    ) - {function_name}
    if collisions:
        logger.warning(
            "explore(): the winner for {} redefines existing sibling symbol(s) {}; "
            "its definitions shadow the cached ones in the merged module.",
            function_name,
            ", ".join(sorted(collisions)),
        )
    merged = _hoist_future_imports(prefix + "\n\n\n" + winner_source.lstrip())
    # ast.parse (used by the validator) does not enforce __future__ placement, but
    # compile() does — verify the merged file actually compiles, else fall back to
    # the winner alone so a broken cache is never written.
    try:
        compile(merged, "<wishful-merge>", "exec")
    except SyntaxError:
        return winner_source
    return merged


def _top_level_names(source: str) -> set[str]:
    """Top-level def/class/assignment names bound by ``source`` (best-effort)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


_FUTURE_RE = re.compile(r"^[ \t]*from[ \t]+__future__[ \t]+import[ \t]+.*$", re.MULTILINE)


def _hoist_future_imports(source: str) -> str:
    """Move every ``from __future__ import ...`` to the top (deduped).

    A merged module can end up with a __future__ import after the first sibling
    symbol, which compiles to a SyntaxError. Collect them and emit a single
    leading block.
    """
    futures = _FUTURE_RE.findall(source)
    if not futures:
        return source
    features: list[str] = []
    for line in futures:
        for name in line.split("import", 1)[1].split(","):
            name = name.strip()
            if name and name not in features:
                features.append(name)
    body = _FUTURE_RE.sub("", source).lstrip("\n")
    return f"from __future__ import {', '.join(features)}\n\n" + body


def explore(
    module_path: str,
    *,
    variants: int = 5,
    test: Optional[Callable[[Callable], bool]] = None,
    benchmark: Optional[Callable[[Callable], float]] = None,
    optimize: Literal["first_passing", "fastest", "best_score"] = "first_passing",
    timeout_per_variant: float = 30.0,
    return_all: bool = False,
    verbose: Optional[bool] = None,
    save_results: Optional[bool] = None,
) -> Union[Callable, List[Callable]]:
    """
    Generate multiple variants of a function and select the best one.

    Args:
        module_path: Full path like "wishful.static.text.extract_emails"
        variants: Number of variants to generate (default: 5)
        test: Function that takes the generated fn and returns True if it passes
        benchmark: Function that takes the generated fn and returns a score (higher = better)
        optimize: Selection strategy
            - "first_passing": Return first variant that passes test (fastest)
            - "fastest": Run all, return the one with best benchmark score
            - "best_score": Alias for "fastest"
        timeout_per_variant: Max seconds to spend generating each variant
        return_all: If True, return list of all valid variants instead of just best
        verbose: Show live progress display. Defaults to whether stdout is a TTY,
            so headless/CI runs stay quiet unless explicitly set.
        save_results: Save results to CSV in cache_dir/_explore/. Defaults to the
            WISHFUL_EXPLORE_SAVE_RESULTS env var (on unless set to "0").

    Returns:
        The best function, or list of functions if return_all=True

    Raises:
        wishful.ExplorationError: If no variant passes the test
        ValueError: If module_path is invalid
    """
    if verbose is None:
        verbose = sys.stdout.isatty()
    if save_results is None:
        save_results = os.getenv("WISHFUL_EXPLORE_SAVE_RESULTS", "1") != "0"
    # Run the async implementation with reusable event loop
    return _run_async(
        _explore_async(
            module_path=module_path,
            variants=variants,
            test=test,
            benchmark=benchmark,
            optimize=optimize,
            timeout_per_variant=timeout_per_variant,
            return_all=return_all,
            verbose=verbose,
            save_results=save_results,
        )
    )


async def _explore_async(
    module_path: str,
    *,
    variants: int,
    test: Optional[Callable[[Callable], bool]],
    benchmark: Optional[Callable[[Callable], float]],
    optimize: Literal["first_passing", "fastest", "best_score"],
    timeout_per_variant: float,
    return_all: bool,
    verbose: bool,
    save_results: bool,
) -> Union[Callable, List[Callable]]:
    """Async implementation of explore with live progress updates."""

    # Validate module path
    if not module_path.startswith("wishful."):
        raise ValueError(
            f"Invalid module path: {module_path}. "
            "Must start with 'wishful.static.' or 'wishful.dynamic.'"
        )

    parts = module_path.split(".")
    if len(parts) < 3:
        raise ValueError(f"Invalid module path: {module_path}")

    module_name = ".".join(parts[:-1])
    function_name = parts[-1]

    # Create progress tracker
    progress = ExploreProgress(
        module_path=module_path,
        function_name=function_name,
        total_variants=variants,
        optimize_strategy=optimize,
        has_benchmark=benchmark is not None,
    )

    # Generate and evaluate variants with live display
    if verbose:
        with AsyncExploreLiveDisplay(progress) as display:
            generated = await _generate_and_evaluate_async(
                module_name=module_name,
                function_name=function_name,
                count=variants,
                timeout=timeout_per_variant,
                test=test,
                benchmark=benchmark,
                progress=progress,
                display=display,
            )
    else:
        generated = await _generate_and_evaluate_async(
            module_name=module_name,
            function_name=function_name,
            count=variants,
            timeout=timeout_per_variant,
            test=test,
            benchmark=benchmark,
            progress=progress,
            display=None,
        )

    # Save results
    if save_results:
        save_exploration_results(progress)

    if not generated:
        raise ExplorationError(
            "Failed to generate any valid variants",
            attempts=variants,
            failures=[r.error_message or "Unknown error" for r in progress.results],
        )

    # Apply selection strategy
    if optimize == "first_passing":
        if return_all:
            return _collect_all_passing(generated, module_name, function_name)
        winner = _select_first_passing(generated, module_name, function_name, progress)
    else:
        if benchmark is None:
            raise ValueError(
                "benchmark is required when optimize='fastest' or 'best_score'"
            )
        if return_all:
            return _collect_all_passing(generated, module_name, function_name)
        winner = _select_best_score(generated, module_name, function_name, progress)

    # Cache the winning variant as a regular wishful module so subsequent
    # `from wishful.static.X import Y` uses the proven winner. Re-validate under
    # current settings right before writing — the variant was validated when it
    # was generated, but safety could have been toggled since.
    if hasattr(winner, "__wishful_source__"):
        validate_code(winner.__wishful_source__, allow_unsafe=settings.allow_unsafe)
        merged = _merge_into_module(
            read_cached(module_name), function_name, winner.__wishful_source__
        )
        # The merge may fold in a pre-existing dangerous sibling the caller never
        # touched. That must not sink the valid winner we promised to return —
        # fall back to caching the winner alone if the merged module won't validate.
        try:
            validate_code(merged, allow_unsafe=settings.allow_unsafe)
            write_cached(module_name, merged)
        except SecurityError:
            validate_code(winner.__wishful_source__, allow_unsafe=settings.allow_unsafe)
            write_cached(module_name, winner.__wishful_source__)

    return winner


async def _generate_and_evaluate_async(
    module_name: str,
    function_name: str,
    count: int,
    timeout: float,
    test: Optional[Callable],
    benchmark: Optional[Callable],
    progress: ExploreProgress,
    display: Optional[AsyncExploreLiveDisplay],
) -> List[Tuple[Callable, str, bool, Optional[float]]]:
    """Generate and evaluate variants asynchronously with live updates."""
    results: List[Tuple[Callable, str, bool, Optional[float]]] = []

    for i in range(count):
        progress.record_generation_start(i)
        if display:
            display.update()

        try:
            start_time = time.perf_counter()

            # Async generation with timeout. explore has no import site to
            # discover context from, but registered @wishful.type schemas and
            # output bindings still apply (plan R12).
            type_schemas = get_all_type_schemas() or None
            output_type = get_output_type_for_function(function_name)
            try:
                source = await asyncio.wait_for(
                    agenerate_module_code(
                        module_name,
                        [function_name],
                        None,
                        type_schemas=type_schemas,
                        function_output_types=(
                            {function_name: output_type} if output_type else None
                        ),
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                progress.record_timeout(i)
                if display:
                    display.update()
                continue

            generation_time = time.perf_counter() - start_time
            progress.record_generation_complete(i, generation_time, source)
            if display:
                display.update()

            # Compile
            fn = _compile_source(source, function_name)
            if fn is None:
                progress.record_compile_error(i, "Failed to compile or extract function")
                if display:
                    display.update()
                continue

            # Attach source to function so benchmark can access it
            fn.__wishful_source__ = source  # type: ignore[attr-defined]  # dynamic marker

            # Test/benchmark — user callables run on a bounded worker thread
            # (run_user_callable) so a hanging candidate can't stall explore and
            # a SystemExit inside one can't kill the host. Timeouts and raised
            # BaseExceptions are recorded as variant failures; the loop continues.
            # awaited via to_thread: run_user_callable blocks in worker.join, and
            # this coroutine runs ON the owned loop — joining inline would stall
            # the loop (starving concurrent explores and litellm logging) and
            # deadlock any user test that itself calls explore().
            if test is None:
                passed, error = True, None
            else:
                ok, value, error = await asyncio.to_thread(
                    run_user_callable, partial(test, fn), timeout
                )
                passed = bool(ok and value)
                if ok and not value:
                    error = "test returned False"

            score = None
            if passed and benchmark:
                ok, score, bench_error = await asyncio.to_thread(
                    run_user_callable, partial(benchmark, fn), timeout
                )
                if not ok:
                    passed, score, error = False, None, bench_error

            progress.record_test_result(i, passed, score, error=error)
            if display:
                display.update()

            if passed:
                results.append((fn, source, passed, score))

        except Exception as e:
            progress.record_compile_error(i, str(e))
            if display:
                display.update()

    return results


def _compile_source(source: str, function_name: str) -> Optional[Callable]:
    """Compile source and extract function via the shared execution path."""
    try:
        return compile_and_exec(source, function_name, filename="<explore>")
    except Exception:
        return None


def _select_first_passing(
    generated: List[Tuple[Callable, str, bool, Optional[float]]],
    module_name: str,
    function_name: str,
    progress: ExploreProgress,
) -> Callable:
    """Select the first passing variant."""
    if not generated:
        raise ExplorationError(
            "No variant passed",
            attempts=progress.total_variants,
            failures=[
                r.error_message or "test returned False" for r in progress.results
            ],
        )

    fn, source, _, score = generated[0]
    idx = progress.first_passing_index or 0

    metadata = VariantMetadata(
        module=module_name,
        function=function_name,
        variant_index=idx,
        generation_time=progress.results[idx].generation_time
        if idx < len(progress.results)
        else 0.0,
        benchmark_score=score,
        source_code=source,
    )
    return wrap_with_metadata(fn, metadata)


def _select_best_score(
    generated: List[Tuple[Callable, str, bool, Optional[float]]],
    module_name: str,
    function_name: str,
    progress: ExploreProgress,
) -> Callable:
    """Select the variant with the best benchmark score."""
    if not generated:
        raise ExplorationError(
            "No variant passed",
            attempts=progress.total_variants,
            failures=[
                r.error_message or "test returned False" for r in progress.results
            ],
        )

    best_fn, best_source, _, best_score = max(
        generated, key=lambda x: x[3] if x[3] is not None else float("-inf")
    )
    idx = progress.best_variant_index or 0

    metadata = VariantMetadata(
        module=module_name,
        function=function_name,
        variant_index=idx,
        generation_time=progress.results[idx].generation_time
        if idx < len(progress.results)
        else 0.0,
        benchmark_score=best_score,
        source_code=best_source,
    )
    return wrap_with_metadata(best_fn, metadata)


def _collect_all_passing(
    generated: List[Tuple[Callable, str, bool, Optional[float]]],
    module_name: str,
    function_name: str,
) -> List[Callable]:
    """Return all passing variants wrapped with metadata."""
    if not generated:
        raise ExplorationError(
            "No variant passed",
            attempts=len(generated),
            failures=["All variants failed"],
        )

    result = []
    for i, (fn, source, _, score) in enumerate(generated):
        metadata = VariantMetadata(
            module=module_name,
            function=function_name,
            variant_index=i,
            generation_time=0.0,
            benchmark_score=score,
            source_code=source,
        )
        result.append(wrap_with_metadata(fn, metadata))

    return result
