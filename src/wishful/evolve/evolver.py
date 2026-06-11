"""Public evolution loop for improving Python functions."""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from functools import partial
from typing import Any

from wishful.config import settings
from wishful.core.execution import compile_and_exec, run_user_callable as _call_user
from wishful.evolve.exceptions import EvolutionError
from wishful.evolve.history import EvolutionHistory, GenerationRecord
from wishful.evolve.mutation import get_function_source, mutate_with_llm


class EvolutionResult:
    """Callable wrapper around an evolution winner.

    Behaves like the winning function — calling it delegates to ``fn``, and
    ``__name__``/``__wishful_source__``/``__wishful_evolution__`` and every
    other attribute proxy to the winner via ``__getattr__`` (proxy, not copy,
    so chained ``evolve(evolve(fn))`` reads the winner's current metadata).
    ``__wrapped__`` is set so ``inspect.signature(result)`` resolves to the
    winner's signature. The run's evidence rides along as ``history`` and
    ``best_score``.

    Deliberately ships **no** ``accept()`` method: spec-003 Open Decision 1
    (auto-cache vs require-accept) is unresolved, and a silent no-op would let
    callers form beliefs that later become behavior changes. Adding it later
    is non-breaking.
    """

    def __init__(self, fn: Callable[..., Any], history: EvolutionHistory):
        self.fn = fn
        self.history = history
        self.best_score = history.final_fitness
        self.__wrapped__ = fn

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # Fires only for names not on the instance/class — i.e. everything the
        # winner carries (__name__, __wishful_source__, __wishful_evolution__, …).
        # Fetch fn via __dict__: during copy/deepcopy/unpickle an empty instance
        # probes dunders before __init__ ran, and a plain self.fn would re-enter
        # __getattr__ infinitely.
        fn = self.__dict__.get("fn")
        if fn is None:
            raise AttributeError(name)
        return getattr(fn, name)

    @property  # the class docstring must not shadow the winner's
    def __doc__(self) -> str | None:  # type: ignore[override]
        return self.fn.__doc__

    def __repr__(self) -> str:
        name = getattr(self.fn, "__name__", "<fn>")
        return f"<EvolutionResult {name} best_score={self.best_score}>"


def evolve(
    fn: Callable[..., Any],
    *,
    fitness: Callable[[Callable[..., Any]], float],
    generations: int = 5,
    variants: int = 3,
    test: Callable[[Callable[..., Any]], bool] | None = None,
    mutation_prompt: str = "",
    keep_history: bool = True,
    history_limit: int = 10,
    timeout_per_variant: float = 30.0,
) -> EvolutionResult:
    """Improve a function by mutating it and selecting higher-fitness variants.

    Args:
        fn: Function to evolve.
        fitness: Scoring function. Higher scores are better.
        generations: Number of mutation rounds to run.
        variants: Number of candidate variants to try per generation.
        test: Optional correctness filter. Variants that return false are rejected.
        mutation_prompt: Human guidance included in the mutation prompt.
        keep_history: Whether prior attempts should be passed to the LLM.
        history_limit: Maximum number of prior attempts to include in mutation context.
        timeout_per_variant: Per-variant wall-clock bound for the mutation call and
            the user-supplied test/fitness callables. A variant that exceeds it is
            recorded as failed and the loop continues.

    Returns:
        An :class:`EvolutionResult` — callable like the winner itself, with
        ``__wishful_source__``/``__wishful_evolution__`` proxied from it and
        the run's ``history`` and ``best_score`` attached.

    Raises:
        EvolutionError: If the original function and all variants fail the test.
    """
    _validate_evolve_args(generations, variants, history_limit, timeout_per_variant)

    function_name = fn.__name__
    current_source = _normalized_function_source(fn)
    original_passed, original_error = _passes_test(fn, test, timeout_per_variant)
    original_fitness = 0.0
    if original_passed:
        original_fitness, original_score_error = _score_variant(
            fn, fitness, timeout_per_variant
        )
        if original_score_error is not None:
            # Scoring the original must not crash the run before any mutation.
            original_passed = False
            original_error = original_score_error
            original_fitness = 0.0

    history = EvolutionHistory(
        original_fitness=original_fitness,
        final_fitness=original_fitness,
        generations=0,
        total_variants_tried=0,
    )
    history.add_variant(
        current_source,
        fitness=original_fitness if original_passed else None,
        failed=not original_passed,
        error_message=original_error,
    )

    best_fn = fn if original_passed else None
    best_source = current_source
    best_fitness = original_fitness if original_passed else float("-inf")
    total_attempts = 0

    for generation in range(1, generations + 1):
        variants_tried = 0

        for _ in range(variants):
            variants_tried += 1
            total_attempts += 1

            mutation_history = (
                history.get_context_for_llm(limit=history_limit) if keep_history else []
            )
            # Cap the LLM call itself at the per-variant budget. _call_user runs it
            # on a daemon thread it cannot cancel, so without this bound a "timed
            # out" mutation keeps its HTTP request alive up to settings.request_timeout
            # (300s) long after the loop moved on. partial() freezes the per-iteration
            # values now, so an abandoned thread can't read state a later iteration
            # mutated.
            mutate_timeout = min(timeout_per_variant, settings.request_timeout)
            ok, candidate_source, mutate_error = _call_user(
                partial(
                    mutate_with_llm,
                    source=best_source,
                    mutation_prompt=mutation_prompt,
                    function_name=function_name,
                    history=mutation_history,
                    timeout=mutate_timeout,
                ),
                timeout_per_variant,
            )
            if not ok:
                history.add_variant("", failed=True, error_message=mutate_error)
                continue

            try:
                candidate = _compile_function(candidate_source, function_name)
            except Exception as exc:
                history.add_variant(
                    candidate_source,
                    failed=True,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                continue

            passed, error_message = _passes_test(candidate, test, timeout_per_variant)
            if not passed:
                history.add_variant(
                    candidate_source, failed=True, error_message=error_message
                )
                continue

            candidate_fitness, score_error = _score_variant(
                candidate, fitness, timeout_per_variant
            )
            if score_error is not None:
                history.add_variant(
                    candidate_source, failed=True, error_message=score_error
                )
                continue

            history.add_variant(candidate_source, fitness=candidate_fitness)
            if best_fn is None or candidate_fitness > best_fitness:
                best_fn = candidate
                best_source = textwrap.dedent(candidate_source).strip()
                best_fitness = candidate_fitness

        recorded_fitness = best_fitness if best_fn is not None else original_fitness
        history.history.append(
            GenerationRecord(
                generation=generation,
                best_fitness=recorded_fitness,
                variants_tried=variants_tried,
                best_source=best_source if best_fn is not None else None,
            )
        )
        history.generations = generation
        history.total_variants_tried = total_attempts

    if best_fn is None:
        raise EvolutionError(
            "No variant satisfied the evolution test",
            best_variant=None,
            best_fitness=None,
            original_fitness=original_fitness,
            generations_completed=generations,
            total_attempts=total_attempts,
        )

    history.final_fitness = best_fitness
    history.generations = generations
    history.total_variants_tried = total_attempts
    _attach_evolution_metadata(best_fn, best_source, history)
    return EvolutionResult(best_fn, history)


def _validate_evolve_args(
    generations: int,
    variants: int,
    history_limit: int,
    timeout_per_variant: float,
) -> None:
    if generations < 0:
        raise ValueError("generations must be >= 0")
    if variants < 1:
        raise ValueError("variants must be >= 1")
    if history_limit < 0:
        raise ValueError("history_limit must be >= 0")
    if timeout_per_variant <= 0:
        raise ValueError("timeout_per_variant must be > 0")


def _normalized_function_source(fn: Callable[..., Any]) -> str:
    return textwrap.dedent(get_function_source(fn)).strip()


def _passes_test(
    fn: Callable[..., Any],
    test: Callable[[Callable[..., Any]], bool] | None,
    timeout: float,
) -> tuple[bool, str | None]:
    if test is None:
        return True, None
    ok, value, error = _call_user(lambda: test(fn), timeout)
    if not ok:
        return False, error
    if value:
        return True, None
    return False, "test returned False"


def _score_variant(
    fn: Callable[..., Any],
    fitness: Callable[[Callable[..., Any]], float],
    timeout: float,
) -> tuple[float, str | None]:
    """Return ``(fitness, None)`` or ``(0.0, error)`` — never raises through."""
    ok, value, error = _call_user(lambda: fitness(fn), timeout)
    if not ok:
        return 0.0, error
    try:
        return float(value), None
    except (TypeError, ValueError) as exc:
        return 0.0, f"fitness returned non-numeric value: {exc}"


def _compile_function(source: str, function_name: str) -> Callable[..., Any]:
    normalized_source = textwrap.dedent(source).strip()
    try:
        candidate = compile_and_exec(
            normalized_source, function_name, filename="<wishful.evolve>"
        )
    except ValueError as exc:
        raise EvolutionError(
            f"Generated source did not define callable {function_name!r}"
        ) from exc

    setattr(candidate, "__wishful_source__", normalized_source)
    return candidate


def _attach_evolution_metadata(
    fn: Callable[..., Any],
    source: str,
    history: EvolutionHistory,
) -> None:
    setattr(fn, "__wishful_source__", source)
    setattr(fn, "__wishful_evolution__", history.to_dict())
