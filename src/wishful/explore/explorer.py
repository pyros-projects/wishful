"""Core explore() implementation with async LLM calls."""

from __future__ import annotations

import asyncio
import atexit
import time
import warnings
from typing import Callable, List, Literal, Optional, Tuple, Union

from wishful.cache.manager import write_cached
from wishful.config import settings
from wishful.explore.exceptions import ExplorationError
from wishful.explore.progress import (
    AsyncExploreLiveDisplay,
    ExploreProgress,
    save_exploration_results,
)
from wishful.explore.variant import VariantMetadata, wrap_with_metadata
from wishful.llm.client import agenerate_module_code
from wishful.safety.validator import validate_code

# Suppress litellm's async cleanup warnings at module level (they're harmless)
warnings.filterwarnings(
    "ignore",
    message=".*coroutine.*was never awaited.*",
    category=RuntimeWarning,
)

# Cache event loop to avoid litellm's LoggingWorker issues with multiple asyncio.run() calls
_cached_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Get existing event loop or create a new one (reusable across calls)."""
    global _cached_loop
    
    # Try to get existing loop
    try:
        loop = asyncio.get_running_loop()
        return loop
    except RuntimeError:
        pass
    
    # Reuse cached loop if it's still valid
    if _cached_loop is not None and not _cached_loop.is_closed():
        return _cached_loop
    
    # Create new loop and cache it
    _cached_loop = asyncio.new_event_loop()
    return _cached_loop


def _cleanup_loop():
    """Clean up the cached event loop on exit."""
    global _cached_loop
    if _cached_loop is not None and not _cached_loop.is_closed():
        try:
            # Cancel pending tasks
            pending = asyncio.all_tasks(_cached_loop)
            for task in pending:
                task.cancel()
            # Don't close - let Python handle it to avoid warnings
        except Exception:
            pass


atexit.register(_cleanup_loop)


def _run_async(coro):
    """Run async coroutine, reusing event loop to avoid litellm issues."""
    loop = _get_or_create_event_loop()
    
    # If we're already in an event loop, we can't use run_until_complete
    try:
        asyncio.get_running_loop()
        # Already in async context - shouldn't happen in normal usage
        # but handle gracefully
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # Not in async context - normal case
        return loop.run_until_complete(coro)


def explore(
    module_path: str,
    *,
    variants: int = 5,
    test: Optional[Callable[[Callable], bool]] = None,
    benchmark: Optional[Callable[[Callable], float]] = None,
    optimize: Literal["first_passing", "fastest", "best_score"] = "first_passing",
    timeout_per_variant: float = 30.0,
    return_all: bool = False,
    verbose: bool = True,
    save_results: bool = True,
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
        verbose: If True, show live progress display (default: True)
        save_results: If True, save results to CSV in cache_dir/_explore/ (default: True)

    Returns:
        The best function, or list of functions if return_all=True

    Raises:
        wishful.ExplorationError: If no variant passes the test
        ValueError: If module_path is invalid
    """
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

    # Cache the winning variant as a regular wishful module
    # So subsequent `from wishful.static.X import Y` uses the proven winner
    if hasattr(winner, "__wishful_source__"):
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

            # Async generation with timeout
            try:
                source = await asyncio.wait_for(
                    agenerate_module_code(module_name, [function_name], None),
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

            # Test/benchmark
            try:
                passed = test is None or test(fn)
                score = benchmark(fn) if benchmark and passed else None
                progress.record_test_result(i, passed, score)
                if display:
                    display.update()

                if passed:
                    results.append((fn, source, passed, score))

            except Exception as e:
                progress.record_test_result(i, False, error=str(e))
                if display:
                    display.update()

        except Exception as e:
            progress.record_compile_error(i, str(e))
            if display:
                display.update()

    return results


def _compile_source(source: str, function_name: str) -> Optional[Callable]:
    """Compile source and extract function. Returns None on failure."""
    try:
        validate_code(source, allow_unsafe=settings.allow_unsafe)
        namespace: dict = {}
        exec(compile(source, "<explore>", "exec"), namespace)
        return namespace.get(function_name)
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
