"""Tests for the EvolutionResult wrapper and evolve's compile/LLM-path contract.

Split out of test_evolve.py (which crossed 1000 lines): everything here
concerns the evolve() return wrapper and the shared execution seams rather
than the core evolution loop.
"""

from __future__ import annotations

import importlib

import pytest


class TestEvolutionResult:
    """The evolve() return wrapper (plan U4/R10)."""

    @staticmethod
    def _evolved(monkeypatch):
        from wishful.evolve import evolve

        def double(x):
            """Double a number."""
            return x

        double.__wishful_source__ = 'def double(x):\n    """Double a number."""\n    return x'

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module,
            "mutate_with_llm",
            lambda **kwargs: 'def double(x):\n    """Double a number."""\n    return x * 2',
        )
        return evolve(double, fitness=lambda fn: float(fn(10)), generations=1, variants=1)

    def test_result_is_callable_and_fn_matches(self, monkeypatch):
        result = self._evolved(monkeypatch)
        from wishful.evolve import EvolutionResult

        assert isinstance(result, EvolutionResult)
        assert result(10) == 20
        assert result.fn(10) == result(10)
        assert result.best_score == 20.0
        assert result.history.final_fitness == 20.0

    def test_inspect_signature_matches_winner(self, monkeypatch):
        import inspect

        result = self._evolved(monkeypatch)
        assert str(inspect.signature(result)) == "(x)"
        assert result.__name__ == "double"
        assert result.__doc__ == "Double a number."

    def test_metadata_proxies_to_winner(self, monkeypatch):
        result = self._evolved(monkeypatch)
        assert "x * 2" in result.__wishful_source__
        meta = result.__wishful_evolution__
        assert meta["schema_version"] == 1
        assert meta["final_fitness"] == 20.0

    def test_no_accept_method_ships(self, monkeypatch):
        # spec-003 Open Decision 1 is unresolved; a silent no-op accept() would
        # let callers form false beliefs. Pin its absence.
        result = self._evolved(monkeypatch)
        assert not hasattr(result, "accept")

    def test_chained_evolution(self, monkeypatch):
        """evolve(evolve(fn)) works: the wrapper feeds the winner's source on."""
        from wishful.evolve import evolve

        first = self._evolved(monkeypatch)

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        seen_sources = []

        def second_mutation(**kwargs):
            seen_sources.append(kwargs["source"])
            return "def double(x):\n    return x * 4"

        monkeypatch.setattr(evolver_module, "mutate_with_llm", second_mutation)

        second = evolve(first, fitness=lambda fn: float(fn(10)), generations=1, variants=1)
        assert second(10) == 40
        # The second run mutated the FIRST winner's source, not the original.
        assert any("x * 2" in s for s in seen_sources)


class TestSharedCompilePath:
    """explorer and evolver compile through core.execution.compile_and_exec (R9)."""

    def test_evolver_routes_through_shared_helper(self, monkeypatch):
        from wishful.core import execution
        from wishful.evolve import evolve

        calls = []
        real = execution.compile_and_exec

        def spy(source, function_name, **kwargs):
            calls.append(function_name)
            return real(source, function_name, **kwargs)

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(evolver_module, "compile_and_exec", spy)
        monkeypatch.setattr(
            evolver_module, "mutate_with_llm", lambda **kwargs: "def f(x):\n    return x + 1"
        )

        def f(x):
            return x

        f.__wishful_source__ = "def f(x):\n    return x"
        evolve(f, fitness=lambda fn: float(fn(1)), generations=1, variants=1)
        assert "f" in calls


class TestEvolveArgValidation:
    """evolve() rejects nonsensical arguments upfront (#62)."""

    @staticmethod
    def _fn():
        def f(x):
            return x

        f.__wishful_source__ = "def f(x):\n    return x"
        return f

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"generations": -1},
            {"variants": 0},
            {"history_limit": -1},
            {"timeout_per_variant": 0},
        ],
    )
    def test_invalid_args_raise(self, kwargs):
        from wishful.evolve import evolve

        with pytest.raises(ValueError):
            evolve(self._fn(), fitness=lambda fn: 1.0, **kwargs)


def test_mutation_uses_sync_llm_path(monkeypatch):
    """Pin review #48's decision: evolve mutates via the SYNC client call.

    evolve's bounding model is worker threads + per-variant timeout around a
    synchronous generate_module_code; the async path belongs to explore's owned
    loop. If this test fails because evolve went async, delete it and the
    decision comment in mutation.py together.
    """
    mutation_module = importlib.import_module("wishful.evolve.mutation")
    llm_module = importlib.import_module("wishful.llm.client")

    sync_calls = []

    def fake_sync(module, functions, context, **kwargs):
        sync_calls.append(module)
        return "def f(x):\n    return x + 1"

    async def bomb_async(*args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("evolve must not use the async LLM path")

    monkeypatch.setattr(mutation_module, "generate_module_code", fake_sync)
    monkeypatch.setattr(llm_module, "agenerate_module_code", bomb_async)

    from wishful.evolve import evolve

    def f(x):
        return x

    f.__wishful_source__ = "def f(x):\n    return x"
    result = evolve(f, fitness=lambda fn: float(fn(1)), generations=1, variants=1)
    assert result(1) == 2
    assert sync_calls == ["wishful.evolve._mutation"]


class TestEvolutionResultCopySemantics:
    """The __getattr__ proxy must not recurse during copy/deepcopy (review fix)."""

    @staticmethod
    def _result():
        from wishful.evolve.evolver import EvolutionResult
        from wishful.evolve.history import EvolutionHistory

        def winner(x):
            return x * 2

        history = EvolutionHistory(
            original_fitness=1.0, final_fitness=2.0, generations=1, total_variants_tried=1
        )
        return EvolutionResult(winner, history)

    def test_copy_and_deepcopy_do_not_recurse(self):
        import copy

        result = self._result()
        shallow = copy.copy(result)
        deep = copy.deepcopy(result)
        assert shallow(3) == 6
        assert deep(3) == 6
        assert deep.best_score == 2.0

    def test_getattr_on_uninitialized_instance_raises_attributeerror(self):
        from wishful.evolve.evolver import EvolutionResult

        bare = EvolutionResult.__new__(EvolutionResult)  # what unpickling probes
        with pytest.raises(AttributeError):
            bare.__setstate__  # must not recurse into __getattr__('fn') forever

    def test_top_level_reexport(self):
        import wishful

        assert wishful.EvolutionResult is importlib.import_module(
            "wishful.evolve.evolver"
        ).EvolutionResult
        assert "EvolutionResult" in wishful.__all__
