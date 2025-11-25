"""Tests for wishful.evolve functionality."""

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
            total_attempts=25
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
            source="def fn(): pass",
            fitness=42.0,
            failed=False,
            error_message=None
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
            error_message="SyntaxError"
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
            best_source="def fn(): return 1"
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
            total_variants_tried=25
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
            total_variants_tried=1
        )
        assert history.improvement == "+50.0%"

    def test_improvement_negative(self):
        """improvement should handle negative changes."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=5.0,
            generations=1,
            total_variants_tried=1
        )
        assert history.improvement == "-50.0%"

    def test_improvement_zero_original(self):
        """improvement should handle zero original fitness."""
        history = EvolutionHistory(
            original_fitness=0.0,
            final_fitness=10.0,
            generations=1,
            total_variants_tried=1
        )
        assert history.improvement == "N/A"

    def test_add_variant(self):
        """add_variant should append to all_variants."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0
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
            total_variants_tried=0
        )

        history.add_variant(
            "def fn(): syntax error",
            failed=True,
            error_message="SyntaxError"
        )

        assert history.all_variants[0].failed is True
        assert history.all_variants[0].error_message == "SyntaxError"

    def test_get_context_for_llm_sorted(self):
        """get_context_for_llm should return variants sorted by fitness (best first)."""
        history = EvolutionHistory(
            original_fitness=10.0,
            final_fitness=10.0,
            generations=0,
            total_variants_tried=0
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
            total_variants_tried=0
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
            total_variants_tried=0
        )

        history.add_variant("def fn(): return 1", fitness=50.0)
        history.add_variant("def fn(): syntax", failed=True, error_message="SyntaxError")

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
            total_variants_tried=0
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
            total_variants_tried=10
        )
        history.history.append(GenerationRecord(
            generation=1,
            best_fitness=30.0,
            variants_tried=5
        ))
        history.history.append(GenerationRecord(
            generation=2,
            best_fitness=50.0,
            variants_tried=5
        ))

        d = history.to_dict()

        assert d["original_fitness"] == 10.0
        assert d["final_fitness"] == 50.0
        assert d["improvement"] == "+400.0%"
        assert d["generations"] == 2
        assert d["total_variants_tried"] == 10
        assert len(d["history"]) == 2
        assert d["history"][0]["generation"] == 1
        assert d["history"][0]["best_fitness"] == 30.0
