"""Tests for wishful.evolve functionality."""

import importlib

import pytest

from wishful.evolve.exceptions import EvolutionError
from wishful.evolve.history import EvolutionHistory, GenerationRecord, VariantRecord


class TestEvolutionErrorUnit:
    """Unit tests for EvolutionError exception."""

    def test_evolution_error_message(self):
        """EvolutionError should store message."""
        err = EvolutionError("test error")
        assert str(err) == "test error"

    def test_evolution_error_attributes(self):
        """EvolutionError should store all attributes."""

        def dummy():
            pass

        err = EvolutionError(
            message="evolution failed",
            best_variant=dummy,
            best_fitness=42.5,
            original_fitness=10.0,
            generations_completed=5,
            total_attempts=25,
        )

        assert err.best_variant == dummy
        assert err.best_fitness == 42.5
        assert err.original_fitness == 10.0
        assert err.generations_completed == 5
        assert err.total_attempts == 25

    def test_evolution_error_defaults(self):
        """EvolutionError should have sensible defaults."""
        err = EvolutionError("test")
        assert err.best_variant is None
        assert err.best_fitness is None
        assert err.original_fitness is None
        assert err.generations_completed == 0
        assert err.total_attempts == 0


class TestVariantRecord:
    """Unit tests for VariantRecord dataclass."""

    def test_variant_record_creation(self):
        """VariantRecord should store variant data."""
        record = VariantRecord(
            source="def fn(): pass", fitness=42.0, failed=False, error_message=None
        )
        assert record.source == "def fn(): pass"
        assert record.fitness == 42.0
        assert record.failed is False
        assert record.error_message is None

    def test_variant_record_failed(self):
        """VariantRecord should handle failed variants."""
        record = VariantRecord(
            source="def fn(): syntax error",
            fitness=None,
            failed=True,
            error_message="SyntaxError",
        )
        assert record.failed is True
        assert record.error_message == "SyntaxError"


class TestGenerationRecord:
    """Unit tests for GenerationRecord dataclass."""

    def test_generation_record_creation(self):
        """GenerationRecord should store generation data."""
        record = GenerationRecord(
            generation=1,
            best_fitness=55.0,
            variants_tried=5,
            best_source="def fn(): return 1",
        )
        assert record.generation == 1
        assert record.best_fitness == 55.0
        assert record.variants_tried == 5
        assert record.best_source == "def fn(): return 1"


class TestEvolutionHistory:
    """Unit tests for EvolutionHistory - the core tracking class."""

    def test_history_creation(self):
        """EvolutionHistory should initialize correctly."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=50.0,
            generations=5,
            total_variants_tried=25,
        )
        assert history.original_fitness == 10.0
        assert history.final_fitness == 50.0
        assert history.generations == 5
        assert history.total_variants_tried == 25
        assert history.history == []
        assert history.all_variants == []

    def test_improvement_calculation(self):
        """improvement property should calculate percentage correctly."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=15.0,
            generations=1,
            total_variants_tried=1,
        )
        assert history.improvement == "+50.0%"

    def test_improvement_negative(self):
        """improvement should handle negative changes."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=5.0,
            generations=1,
            total_variants_tried=1,
        )
        assert history.improvement == "-50.0%"

    def test_improvement_zero_original(self):
        """improvement should handle zero original fitness."""
        history = EvolutionHistory(
            original_fitness=0.0,
            final_fitness=10.0,
            generations=1,
            total_variants_tried=1,
        )
        assert history.improvement == "N/A"

    def test_add_variant(self):
        """add_variant should append to all_variants."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        history.add_variant("def fn(): return 1", fitness=20.0)
        history.add_variant("def fn(): return 2", fitness=30.0)

        assert len(history.all_variants) == 2
        assert history.all_variants[0].fitness == 20.0
        assert history.all_variants[1].fitness == 30.0

    def test_add_variant_failed(self):
        """add_variant should handle failed variants."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        history.add_variant(
            "def fn(): syntax error", failed=True, error_message="SyntaxError"
        )

        assert history.all_variants[0].failed is True
        assert history.all_variants[0].error_message == "SyntaxError"

    def test_get_context_for_llm_sorted(self):
        """get_context_for_llm should return variants sorted by fitness (best first)."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        history.add_variant("def fn(): return 1", fitness=10.0)
        history.add_variant("def fn(): return 2", fitness=50.0)  # Best
        history.add_variant("def fn(): return 3", fitness=30.0)

        context = history.get_context_for_llm()

        assert len(context) == 3
        assert context[0]["fitness"] == 50.0  # Best first
        assert context[1]["fitness"] == 30.0
        assert context[2]["fitness"] == 10.0

    def test_get_context_for_llm_limit(self):
        """get_context_for_llm should respect limit parameter."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        for i in range(10):
            history.add_variant(f"def fn(): return {i}", fitness=float(i))

        context = history.get_context_for_llm(limit=3)

        assert len(context) == 3
        # Should be top 3 by fitness: 9, 8, 7
        assert context[0]["fitness"] == 9.0
        assert context[1]["fitness"] == 8.0
        assert context[2]["fitness"] == 7.0

    def test_get_context_for_llm_includes_failed(self):
        """get_context_for_llm should include failed variants (they help LLM learn)."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        history.add_variant("def fn(): return 1", fitness=50.0)
        history.add_variant(
            "def fn(): syntax", failed=True, error_message="SyntaxError"
        )

        context = history.get_context_for_llm()

        assert len(context) == 2
        failed_entry = next(c for c in context if c["failed"])
        assert failed_entry["error"] == "SyntaxError"

    def test_get_context_for_llm_handles_none_fitness(self):
        """get_context_for_llm should handle None fitness (treat as worst)."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0,
        )

        history.add_variant("def fn(): fail", fitness=None, failed=True)
        history.add_variant("def fn(): return 1", fitness=10.0)

        context = history.get_context_for_llm()

        # None fitness should be sorted last
        assert context[0]["fitness"] == 10.0
        assert context[1]["fitness"] is None

    def test_to_dict(self):
        """to_dict should produce correct dictionary structure."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=50.0,
            generations=2,
            total_variants_tried=10,
        )
        history.history.append(
            GenerationRecord(generation=1, best_fitness=30.0, variants_tried=5)
        )
        history.history.append(
            GenerationRecord(generation=2, best_fitness=50.0, variants_tried=5)
        )

        d = history.to_dict()

        assert d["original_fitness"] == 10.0
        assert d["final_fitness"] == 50.0
        assert d["improvement"] == "+400.0%"
        assert d["generations"] == 2
        assert d["total_variants_tried"] == 10
        assert len(d["history"]) == 2
        assert d["history"][0]["generation"] == 1
        assert d["history"][0]["best_fitness"] == 30.0


# =============================================================================
# Phase 2: Mutation Module Tests
# =============================================================================


class TestBuildEvolutionContext:
    """Tests for _build_evolution_context() - the AlphaEvolve context builder."""

    def test_context_includes_current_source(self):
        """Context should include the current best implementation."""
        from wishful.evolve.mutation import _build_evolution_context

        context = _build_evolution_context(
            source="def fn(x):\n    return x * 2",
            mutation_prompt="",
            function_name="fn",
            history=[],
        )

        assert "def fn(x):" in context
        assert "return x * 2" in context
        assert "CURRENT BEST IMPLEMENTATION" in context

    def test_context_includes_mutation_prompt(self):
        """Context should include user guidance when provided."""
        from wishful.evolve.mutation import _build_evolution_context

        context = _build_evolution_context(
            source="def fn(x): return x",
            mutation_prompt="make it faster using numpy",
            function_name="fn",
            history=[],
        )

        assert "make it faster using numpy" in context
        assert "USER GUIDANCE" in context

    def test_context_excludes_prompt_when_empty(self):
        """Context should not have USER GUIDANCE section when prompt is empty."""
        from wishful.evolve.mutation import _build_evolution_context

        context = _build_evolution_context(
            source="def fn(x): return x",
            mutation_prompt="",
            function_name="fn",
            history=[],
        )

        assert "USER GUIDANCE" not in context

    def test_context_includes_history(self):
        """Context should include evolution history when provided."""
        from wishful.evolve.mutation import _build_evolution_context

        history = [
            {
                "source": "def fn(x): return x + 1",
                "fitness": 50.0,
                "failed": False,
                "error": None,
            },
            {
                "source": "def fn(x): return x * 2",
                "fitness": 30.0,
                "failed": False,
                "error": None,
            },
        ]

        context = _build_evolution_context(
            source="def fn(x): return x + 1",
            mutation_prompt="",
            function_name="fn",
            history=history,
        )

        assert "EVOLUTION HISTORY" in context
        assert "sorted by fitness" in context.lower()
        assert "Fitness = 50.00" in context
        assert "Fitness = 30.00" in context

    def test_context_includes_failed_variants(self):
        """Context should include failed variants with error info."""
        from wishful.evolve.mutation import _build_evolution_context

        history = [
            {
                "source": "def fn(x): return x",
                "fitness": 50.0,
                "failed": False,
                "error": None,
            },
            {
                "source": "def fn(x): syntax error",
                "fitness": None,
                "failed": True,
                "error": "SyntaxError",
            },
        ]

        context = _build_evolution_context(
            source="def fn(x): return x",
            mutation_prompt="",
            function_name="fn",
            history=history,
        )

        assert "FAILED" in context
        assert "SyntaxError" in context

    def test_context_has_task_instructions(self):
        """Context should include clear instructions for the LLM."""
        from wishful.evolve.mutation import _build_evolution_context

        context = _build_evolution_context(
            source="def fn(x): return x",
            mutation_prompt="",
            function_name="fn",
            history=[],
        )

        assert "YOUR TASK" in context
        assert "IMPROVED" in context or "improved" in context

    def test_context_empty_history(self):
        """Context should work with empty history."""
        from wishful.evolve.mutation import _build_evolution_context

        context = _build_evolution_context(
            source="def fn(x): return x",
            mutation_prompt="",
            function_name="fn",
            history=[],
        )

        # Should not include history section when empty
        assert "EVOLUTION HISTORY" not in context


class TestTruncateSource:
    """Tests for _truncate_source() utility."""

    def test_short_source_unchanged(self):
        """Short source code should be returned unchanged."""
        from wishful.evolve.mutation import _truncate_source

        source = "def fn():\n    return 1"
        result = _truncate_source(source, max_lines=10)

        assert result == source

    def test_long_source_truncated(self):
        """Long source code should be truncated with indicator."""
        from wishful.evolve.mutation import _truncate_source

        lines = [f"    line{i}" for i in range(20)]
        source = "def fn():\n" + "\n".join(lines)

        result = _truncate_source(source, max_lines=5)

        # Should have max_lines lines
        result_lines = result.strip().split("\n")
        assert len(result_lines) == 6  # 5 lines + truncation indicator

        # Should have truncation indicator
        assert "more lines" in result

    def test_truncate_exact_limit(self):
        """Source at exactly max_lines should not be truncated."""
        from wishful.evolve.mutation import _truncate_source

        lines = ["def fn():"] + [f"    line{i}" for i in range(9)]
        source = "\n".join(lines)

        result = _truncate_source(source, max_lines=10)

        assert result == source
        assert "more lines" not in result


class TestGetFunctionSource:
    """Tests for get_function_source() utility."""

    def test_get_source_from_wishful_attribute(self):
        """Should extract source from __wishful_source__ attribute."""
        from wishful.evolve.mutation import get_function_source

        def dummy():
            pass

        dummy.__wishful_source__ = "def dummy():\n    return 42"

        result = get_function_source(dummy)

        assert result == "def dummy():\n    return 42"

    def test_get_source_from_inspect(self):
        """Should fall back to inspect.getsource() for regular functions."""
        from wishful.evolve.mutation import get_function_source

        def regular_function():
            return 123

        result = get_function_source(regular_function)

        assert "def regular_function" in result
        assert "return 123" in result

    def test_get_source_raises_for_unavailable(self):
        """Should raise ValueError when source is unavailable."""
        from wishful.evolve.mutation import get_function_source

        # Built-in function has no source
        with pytest.raises(ValueError, match="source"):
            get_function_source(len)


class TestMutateWithLLM:
    """Tests for mutate_with_llm() - the core LLM mutation function."""

    def test_mutate_calls_llm(self, monkeypatch):
        """mutate_with_llm should call generate_module_code."""
        called_with = {"context": None, "functions": None}

        def fake_generate(module, functions, context, **kwargs):
            called_with["context"] = context
            called_with["functions"] = functions
            return "def fn(x):\n    return x + 1"

        mutation_module = importlib.import_module("wishful.evolve.mutation")
        monkeypatch.setattr(mutation_module, "generate_module_code", fake_generate)

        from wishful.evolve.mutation import mutate_with_llm

        result = mutate_with_llm(
            source="def fn(x):\n    return x",
            mutation_prompt="improve it",
            function_name="fn",
            history=[],
        )

        assert called_with["functions"] == ["fn"]
        assert "def fn(x)" in called_with["context"]
        assert "improve it" in called_with["context"]
        assert "def fn(x):" in result

    def test_mutate_passes_history_to_context(self, monkeypatch):
        """mutate_with_llm should include history in LLM context."""
        called_with = {"context": None}

        def fake_generate(module, functions, context, **kwargs):
            called_with["context"] = context
            return "def fn(x):\n    return x + 1"

        mutation_module = importlib.import_module("wishful.evolve.mutation")
        monkeypatch.setattr(mutation_module, "generate_module_code", fake_generate)

        from wishful.evolve.mutation import mutate_with_llm

        history = [
            {
                "source": "def fn(x): return x * 2",
                "fitness": 50.0,
                "failed": False,
                "error": None,
            },
        ]

        mutate_with_llm(
            source="def fn(x):\n    return x",
            mutation_prompt="",
            function_name="fn",
            history=history,
        )

        assert "Fitness = 50.00" in called_with["context"]
        assert "def fn(x): return x * 2" in called_with["context"]

    def test_mutate_returns_generated_code(self, monkeypatch):
        """mutate_with_llm should return the LLM-generated code."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn(x):\n    return x * 100"

        mutation_module = importlib.import_module("wishful.evolve.mutation")
        monkeypatch.setattr(mutation_module, "generate_module_code", fake_generate)

        from wishful.evolve.mutation import mutate_with_llm

        result = mutate_with_llm(
            source="def fn(x):\n    return x",
            mutation_prompt="",
            function_name="fn",
            history=[],
        )

        assert result == "def fn(x):\n    return x * 100"


# =============================================================================
# Phase 3: Public evolve() Loop Tests
# =============================================================================


class TestEvolveBasic:
    """Tests for the public evolve() loop."""

    def test_evolve_returns_better_variant(self, monkeypatch):
        """evolve should return the highest-fitness generated variant."""
        from wishful.evolve import evolve

        def score(fn):
            return float(fn(10))

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        variants = iter(
            [
                "def transform(x):\n    return x + 5",
                "def transform(x):\n    return x + 20",
            ]
        )

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module, "mutate_with_llm", lambda **kwargs: next(variants)
        )

        evolved = evolve(
            transform,
            fitness=score,
            generations=1,
            variants=2,
        )

        assert evolved(10) == 30
        assert evolved.__wishful_source__ == "def transform(x):\n    return x + 20"
        assert evolved.__wishful_evolution__["original_fitness"] == 10.0
        assert evolved.__wishful_evolution__["final_fitness"] == 30.0
        assert evolved.__wishful_evolution__["improvement"] == "+200.0%"

    def test_evolve_uses_history_for_later_mutations(self, monkeypatch):
        """evolve should pass scored variant history into subsequent mutations."""
        from wishful.evolve import evolve

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        seen_history = []
        variants = iter(
            [
                "def transform(x):\n    return x + 1",
                "def transform(x):\n    return x + 2",
            ]
        )

        def fake_mutate(**kwargs):
            seen_history.append(kwargs["history"])
            return next(variants)

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(evolver_module, "mutate_with_llm", fake_mutate)

        evolve(
            transform,
            fitness=lambda fn: float(fn(10)),
            generations=1,
            variants=2,
            history_limit=5,
        )

        assert seen_history[0][0]["fitness"] == 10.0
        assert any(entry["fitness"] == 11.0 for entry in seen_history[1])

    def test_evolve_can_disable_history_context(self, monkeypatch):
        """keep_history=False should call mutations with an empty history."""
        from wishful.evolve import evolve

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        seen_history = []

        def fake_mutate(**kwargs):
            seen_history.append(kwargs["history"])
            return "def transform(x):\n    return x + 1"

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(evolver_module, "mutate_with_llm", fake_mutate)

        evolve(
            transform,
            fitness=lambda fn: float(fn(10)),
            generations=1,
            variants=1,
            keep_history=False,
        )

        assert seen_history == [[]]


class TestEvolveWithTest:
    """Tests for correctness filters during evolution."""

    def test_evolve_skips_variants_that_fail_test(self, monkeypatch):
        """A high-scoring variant must not win if the test rejects it."""
        from wishful.evolve import evolve

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        variants = iter(
            [
                "def transform(x):\n    return 999",
                "def transform(x):\n    return x + 5",
            ]
        )

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module, "mutate_with_llm", lambda **kwargs: next(variants)
        )

        evolved = evolve(
            transform,
            fitness=lambda fn: float(fn(10)),
            test=lambda fn: fn(10) < 100,
            generations=1,
            variants=2,
        )

        assert evolved(10) == 15
        failures = [
            entry
            for entry in evolved.__wishful_evolution__["variants"]
            if entry["failed"]
        ]
        assert failures
        assert "test returned False" in failures[0]["error"]

    def test_evolve_does_not_score_original_that_fails_test(self, monkeypatch):
        """A rejected baseline should not crash fitness before mutations run."""
        from wishful.evolve import evolve

        def transform(x):
            return 999

        transform.__wishful_source__ = "def transform(x):\n    return 999"

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module,
            "mutate_with_llm",
            lambda **kwargs: "def transform(x):\n    return x + 3",
        )

        def score(fn):
            value = fn(10)
            if value >= 100:
                raise AssertionError("fitness should only score passing functions")
            return float(value)

        evolved = evolve(
            transform,
            fitness=score,
            test=lambda fn: fn(10) < 100,
            generations=1,
            variants=1,
        )

        assert evolved(10) == 13
        evolution = evolved.__wishful_evolution__
        assert evolution["original_fitness"] == 0.0
        assert evolution["variants"][0]["failed"] is True
        assert "test returned False" in evolution["variants"][0]["error"]

    def test_evolve_raises_when_original_and_all_variants_fail(self, monkeypatch):
        """evolve should raise with best-known context when nothing satisfies test."""
        from wishful.evolve import evolve

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module,
            "mutate_with_llm",
            lambda **kwargs: "def transform(x):\n    return x + 1",
        )

        with pytest.raises(EvolutionError) as exc:
            evolve(
                transform,
                fitness=lambda fn: float(fn(10)),
                test=lambda fn: False,
                generations=1,
                variants=1,
            )

        assert exc.value.generations_completed == 1
        assert exc.value.total_attempts == 1

    def test_evolve_records_mutation_errors_and_keeps_trying(self, monkeypatch):
        """A failed mutation call should not abort the whole evolution run."""
        from wishful.evolve import evolve

        def transform(x):
            return x

        transform.__wishful_source__ = "def transform(x):\n    return x"

        calls = 0

        def fake_mutate(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("provider hiccup")
            return "def transform(x):\n    return x + 3"

        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(evolver_module, "mutate_with_llm", fake_mutate)

        evolved = evolve(
            transform,
            fitness=lambda fn: float(fn(10)),
            generations=1,
            variants=2,
        )

        assert evolved(10) == 13
        failures = [
            entry
            for entry in evolved.__wishful_evolution__["variants"]
            if entry["failed"]
        ]
        assert "provider hiccup" in failures[0]["error"]


class TestEvolveIntegration:
    """Tests for evolve package exports."""

    def test_evolve_importable_from_package(self):
        """evolve and EvolutionError should be importable from wishful.evolve."""
        from wishful.evolve import EvolutionError as PackageEvolutionError
        from wishful.evolve import evolve

        assert callable(evolve)
        assert PackageEvolutionError is EvolutionError

    def test_evolve_importable_from_wishful(self):
        """evolve and EvolutionError should be importable from root package."""
        from wishful import EvolutionError as RootEvolutionError
        from wishful import evolve

        assert callable(evolve)
        assert RootEvolutionError is EvolutionError


# --- U14: evolve() contract -------------------------------------------------


class TestEvolveContract:
    """Timeout enforcement, failure containment, and removed verbose param."""

    def _identity_source(self):
        # A trivially-evolvable function the fake LLM can mutate.
        def score(n):
            return n

        score.__wishful_source__ = "def score(n):\n    return n\n"
        return score

    def test_verbose_param_removed(self):
        fn = self._identity_source()
        with pytest.raises(TypeError):
            from wishful import evolve

            evolve(fn, fitness=lambda f: 1.0, generations=1, variants=1, verbose=False)

    @staticmethod
    def _stub_mutation(monkeypatch, source="def score(n):\n    return n + 1\n"):
        """Replace the LLM mutation with a deterministic stub.

        Without this these tests call the real provider (conftest never forces
        WISHFUL_FAKE_LLM), so a populated .env makes them spend money and flake.
        """
        evolver_module = importlib.import_module("wishful.evolve.evolver")
        monkeypatch.setattr(
            evolver_module, "mutate_with_llm", lambda **kwargs: source
        )

    def test_original_fitness_exception_does_not_crash(self, monkeypatch):
        """A fitness() that raises on the original is recorded, not propagated."""
        from wishful import evolve

        self._stub_mutation(monkeypatch)
        fn = self._identity_source()
        calls = {"n": 0}

        def flaky_fitness(f):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom on original")
            return 1.0

        # Should not raise RuntimeError; the original is marked failed and the
        # run proceeds with mutated variants.
        result = evolve(
            fn, fitness=flaky_fitness, test=lambda f: True, generations=1, variants=1
        )
        assert callable(result)

    def test_slow_fitness_is_bounded_and_loop_continues(self, monkeypatch):
        """A fitness() that exceeds the per-variant timeout fails that variant
        without hanging the run."""
        import time

        from wishful import evolve

        self._stub_mutation(monkeypatch)
        fn = self._identity_source()

        def slow_fitness(f):
            time.sleep(5)
            return 1.0

        with pytest.raises(EvolutionError):
            evolve(
                fn,
                fitness=slow_fitness,
                test=lambda f: True,
                generations=1,
                variants=1,
                timeout_per_variant=0.2,
            )

    def test_systemexit_in_test_is_contained(self, monkeypatch):
        """A candidate test() that calls sys.exit must not kill the host."""
        from wishful import evolve

        self._stub_mutation(monkeypatch)
        fn = self._identity_source()

        def exiting_test(f):
            raise SystemExit(1)

        with pytest.raises(EvolutionError):
            evolve(
                fn,
                fitness=lambda f: 1.0,
                test=exiting_test,
                generations=1,
                variants=1,
            )

    def test_mutation_call_is_bounded_by_per_variant_timeout(self, monkeypatch):
        """The LLM mutation call must inherit the per-variant budget, not the
        global 300s request timeout — otherwise a 'timed-out' variant's daemon
        thread keeps the HTTP call alive far past timeout_per_variant."""
        from wishful import evolve

        mutation_module = importlib.import_module("wishful.evolve.mutation")
        captured = {}

        def fake_generate(module, functions, context, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return "def score(n):\n    return n + 1\n"

        monkeypatch.setattr(mutation_module, "generate_module_code", fake_generate)
        fn = self._identity_source()

        evolve(
            fn,
            fitness=lambda f: 1.0,
            test=lambda f: True,
            generations=1,
            variants=1,
            timeout_per_variant=7.0,
        )

        assert captured["timeout"] is not None
        assert captured["timeout"] <= 7.0
