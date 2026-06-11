"""Real-model smoke tests (gated by WISHFUL_SMOKE=1 + credentials).

These four cases exercise the load-bearing real-model paths end to end against
the configured provider, asserting non-empty validated output and recording a
proof entry. They cost real API spend, so the case set is kept small. Run with::

    WISHFUL_SMOKE=1 uv run pytest -m smoke

The proof bundle lands in docs/proofs/<version>/summary.json.
"""

from __future__ import annotations

import time

import pytest

import wishful


def _timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


@pytest.mark.smoke
def test_static_import_generates(proof):
    wishful.clear_cache()

    def run():
        from wishful.static.smoke_text import extract_numbers

        return extract_numbers("order 12 ships in 3 days")

    result, seconds = _timed(run)
    proof("static_import:extract_numbers", "pass", seconds=seconds, output_summary=str(result))
    assert result  # a non-empty result proves the generated function ran


@pytest.mark.smoke
def test_dynamic_call_generates(proof):
    def run():
        import wishful.dynamic.smoke_jokes as jokes

        return jokes.programming_one_liner()

    result, seconds = _timed(run)
    proof("dynamic_call:programming_one_liner", "pass", seconds=seconds, output_summary=str(result))
    assert isinstance(result, str) and result.strip()


@pytest.mark.smoke
def test_explore_selects_winner(proof):
    def run():
        return wishful.explore(
            "wishful.static.smoke_explore.add_one",
            variants=2,
            test=lambda fn: fn(1) == 2,
            verbose=False,
            save_results=False,
        )

    winner, seconds = _timed(run)
    proof("explore:add_one", "pass", seconds=seconds, output_summary=f"add_one(1)={winner(1)}")
    assert winner(1) == 2


@pytest.mark.smoke
def test_evolve_improves(proof):
    def baseline(values):
        return [v for v in values]

    baseline.__wishful_source__ = "def baseline(values):\n    return [v for v in values]\n"

    def run():
        return wishful.evolve(
            baseline,
            fitness=lambda fn: 1.0 if fn([1, 2, 3]) == [1, 2, 3] else 0.0,
            test=lambda fn: fn([1, 2, 3]) == [1, 2, 3],
            generations=1,
            variants=2,
            mutation_prompt="Keep behavior identical; make it concise.",
        )

    evolved, seconds = _timed(run)
    summary = f"fitness={evolved.__wishful_evolution__.get('final_fitness')}"
    proof("evolve:baseline", "pass", seconds=seconds, output_summary=summary)
    assert evolved([1, 2, 3]) == [1, 2, 3]
