"""Public evolution loop for improving Python functions."""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from typing import Any

from wishful.config import settings
from wishful.evolve.exceptions import EvolutionError
from wishful.evolve.history import EvolutionHistory, GenerationRecord
from wishful.evolve.mutation import get_function_source, mutate_with_llm
from wishful.safety.validator import validate_code


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
    verbose: bool = True,
) -> Callable[..., Any]:
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
        timeout_per_variant: Reserved for future timeout enforcement.
        verbose: Reserved for future progress output.

    Returns:
        The best passing function, annotated with ``__wishful_source__`` and
        ``__wishful_evolution__``.

    Raises:
        EvolutionError: If the original function and all variants fail the test.
    """
    _validate_evolve_args(generations, variants, history_limit, timeout_per_variant)

    function_name = fn.__name__
    current_source = _normalized_function_source(fn)
    original_passed, original_error = _passes_test(fn, test)
    original_fitness = _score_variant(fn, fitness) if original_passed else 0.0

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
            try:
                candidate_source = mutate_with_llm(
                    source=best_source,
                    mutation_prompt=mutation_prompt,
                    function_name=function_name,
                    history=mutation_history,
                )
            except Exception as exc:
                history.add_variant(
                    "",
                    failed=True,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                continue

            try:
                candidate = _compile_function(candidate_source, function_name)
                passed, error_message = _passes_test(candidate, test)
                if not passed:
                    history.add_variant(
                        candidate_source,
                        failed=True,
                        error_message=error_message,
                    )
                    continue

                candidate_fitness = _score_variant(candidate, fitness)
                history.add_variant(candidate_source, fitness=candidate_fitness)

                if best_fn is None or candidate_fitness > best_fitness:
                    best_fn = candidate
                    best_source = textwrap.dedent(candidate_source).strip()
                    best_fitness = candidate_fitness

            except Exception as exc:
                history.add_variant(
                    candidate_source,
                    failed=True,
                    error_message=f"{type(exc).__name__}: {exc}",
                )

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
    return best_fn


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
) -> tuple[bool, str | None]:
    if test is None:
        return True, None
    try:
        if test(fn):
            return True, None
        return False, "test returned False"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _score_variant(
    fn: Callable[..., Any],
    fitness: Callable[[Callable[..., Any]], float],
) -> float:
    return float(fitness(fn))


def _compile_function(source: str, function_name: str) -> Callable[..., Any]:
    normalized_source = textwrap.dedent(source).strip()
    validate_code(normalized_source, allow_unsafe=settings.allow_unsafe)
    namespace: dict[str, Any] = {}
    exec(compile(normalized_source, "<wishful.evolve>", "exec"), namespace)

    candidate = namespace.get(function_name)
    if not callable(candidate):
        raise EvolutionError(
            f"Generated source did not define callable {function_name!r}"
        )

    setattr(candidate, "__wishful_source__", normalized_source)
    return candidate


def _attach_evolution_metadata(
    fn: Callable[..., Any],
    source: str,
    history: EvolutionHistory,
) -> None:
    setattr(fn, "__wishful_source__", source)
    setattr(fn, "__wishful_evolution__", history.to_dict())
