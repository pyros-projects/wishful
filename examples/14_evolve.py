"""Example 14: Evolve a function with scored mutations.

Run with a real LLM:
    uv run python examples/14_evolve.py

Run offline with deterministic fake mutations:
    WISHFUL_FAKE_LLM=1 uv run python examples/14_evolve.py
"""

from __future__ import annotations

import importlib
import os

import wishful


def normalize_scores(values):
    """Baseline implementation: correct, but intentionally a little clunky."""
    numbers = [float(value) for value in values]
    if not numbers:
        return []
    minimum = min(numbers)
    maximum = max(numbers)
    if maximum == minimum:
        return [0.0 for _ in numbers]
    return [(number - minimum) / (maximum - minimum) for number in numbers]


normalize_scores.__wishful_source__ = """
def normalize_scores(values):
    numbers = [float(value) for value in values]
    if not numbers:
        return []
    minimum = min(numbers)
    maximum = max(numbers)
    if maximum == minimum:
        return [0.0 for _ in numbers]
    return [(number - minimum) / (maximum - minimum) for number in numbers]
""".strip()


def is_correct(fn) -> bool:
    """Correctness gate: outputs stay normalized and stable on edge cases."""
    cases = [
        ([10, 20, 30], [0.0, 0.5, 1.0]),
        (["2", "2", "2"], [0.0, 0.0, 0.0]),
        ([], []),
    ]
    return all(fn(values) == expected for values, expected in cases)


def source_quality(fn) -> float:
    """Toy fitness: reward correct, concise source for a quick demo."""
    if not is_correct(fn):
        return 0.0
    source = getattr(fn, "__wishful_source__", "")
    return 1_000.0 - len(source)


def install_fake_mutations_if_needed() -> None:
    """Make the example deterministic under WISHFUL_FAKE_LLM=1."""
    if os.getenv("WISHFUL_FAKE_LLM") != "1":
        return

    candidates = iter(
        [
            # Fails correctness because equal inputs divide by zero.
            """
def normalize_scores(values):
    values = [float(value) for value in values]
    minimum, maximum = min(values), max(values)
    return [(value - minimum) / (maximum - minimum) for value in values]
""".strip(),
            # Correct and shorter than the baseline.
            """
def normalize_scores(values):
    values = [float(value) for value in values]
    if not values:
        return []
    span = max(values) - min(values)
    return [0.0 if span == 0 else (value - min(values)) / span for value in values]
""".strip(),
        ]
    )

    evolver_module = importlib.import_module("wishful.evolve.evolver")
    evolver_module.mutate_with_llm = lambda **kwargs: next(candidates)


def main() -> None:
    install_fake_mutations_if_needed()

    evolved = wishful.evolve(
        normalize_scores,
        fitness=source_quality,
        test=is_correct,
        generations=1,
        variants=2,
        mutation_prompt="Keep the behavior identical but make the code concise.",
        verbose=False,
    )

    print("Original fitness:", source_quality(normalize_scores))
    print("Evolved fitness:", evolved.__wishful_evolution__["final_fitness"])
    print("Improvement:", evolved.__wishful_evolution__["improvement"])
    print("Result:", evolved([10, 20, 30]))
    print("\nWinning source:\n")
    print(evolved.__wishful_source__)


if __name__ == "__main__":
    main()
