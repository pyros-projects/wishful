"""Selection strategies for explore()."""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from wishful.explore.exceptions import ExplorationError


def first_passing(
    variants: List[Tuple[Callable, str]],  # (fn, source_code)
    test: Optional[Callable[[Callable], bool]],
    benchmark: Optional[Callable[[Callable], float]],
) -> Tuple[Callable, int, Optional[float]]:
    """
    Return first variant that passes test.

    Returns: (function, variant_index, benchmark_score or None)
    """
    failures = []

    for i, (fn, source) in enumerate(variants):
        try:
            if test is None or test(fn):
                score = benchmark(fn) if benchmark else None
                return fn, i, score
            failures.append(f"Variant {i}: test returned False")
        except Exception as e:
            failures.append(f"Variant {i}: {type(e).__name__}: {e}")

    raise ExplorationError(
        f"No variant passed after {len(variants)} attempts",
        attempts=len(variants),
        failures=failures,
    )


def best_score(
    variants: List[Tuple[Callable, str]],
    test: Optional[Callable[[Callable], bool]],
    benchmark: Callable[[Callable], float],
) -> Tuple[Callable, int, float]:
    """
    Return variant with highest benchmark score (among those passing test).

    Returns: (function, variant_index, benchmark_score)
    """
    passing: List[Tuple[Callable, int, float]] = []
    failures = []

    for i, (fn, source) in enumerate(variants):
        try:
            if test is None or test(fn):
                score = benchmark(fn)
                passing.append((fn, i, score))
            else:
                failures.append(f"Variant {i}: test returned False")
        except Exception as e:
            failures.append(f"Variant {i}: {type(e).__name__}: {e}")

    if not passing:
        raise ExplorationError(
            f"No variant passed after {len(variants)} attempts",
            attempts=len(variants),
            failures=failures,
        )

    # Sort by score descending, return best
    passing.sort(key=lambda x: x[2], reverse=True)
    return passing[0]

