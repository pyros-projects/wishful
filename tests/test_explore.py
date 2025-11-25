"""Tests for wishful.explore functionality."""

from __future__ import annotations

import asyncio
import time

import pytest

from wishful.explore import ExplorationError, explore
from wishful.explore import explorer as explorer_module


def make_async_fake(sync_fn):
    """Convert a sync function to an async mock that calls it."""
    async def async_wrapper(*args, **kwargs):
        return sync_fn(*args, **kwargs)
    return async_wrapper


class TestExploreBasic:
    """Basic explore functionality."""

    def test_explore_returns_callable(self, monkeypatch):
        """explore() should return a callable function."""

        def fake_generate(module, functions, context, **kwargs):
            return "def greet(name):\n    return f'Hello, {name}!'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore("wishful.static.greet.greet", variants=1, verbose=False)

        assert callable(fn)
        assert fn("World") == "Hello, World!"

    def test_explore_generates_multiple_variants(self, monkeypatch):
        """explore() should call generator multiple times for variants > 1."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            return f"def fn():\n    return {call_count['n']}"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore("wishful.static.test.fn", variants=5, verbose=False)

        assert call_count["n"] == 5

    def test_explore_default_variants_is_5(self, monkeypatch):
        """Default should generate 5 variants."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            return "def fn():\n    return 42"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        explore("wishful.static.test.fn", verbose=False)

        assert call_count["n"] == 5


class TestExploreWithTest:
    """Test-based selection."""

    def test_first_passing_returns_first_that_passes(self, monkeypatch):
        """With optimize='first_passing', return first variant that passes test."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            # Variants 1, 2 return wrong value; variant 3 returns correct
            if call_count["n"] < 3:
                return "def fn():\n    return 'wrong'"
            return "def fn():\n    return 'correct'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore(
            "wishful.static.test.fn",
            variants=5,
            test=lambda f: f() == "correct",
            optimize="first_passing",
            verbose=False,
        )

        assert fn() == "correct"
        assert call_count["n"] == 5  # All generated, but first_passing selects #3

    def test_first_passing_tries_all_if_none_pass(self, monkeypatch):
        """If no variant passes, try all before raising."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            return "def fn():\n    return 'wrong'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ExplorationError) as exc_info:
            explore(
                "wishful.static.test.fn",
                variants=5,
                test=lambda f: f() == "correct",
                verbose=False,
            )

        assert call_count["n"] == 5
        assert exc_info.value.attempts == 5

    def test_test_receives_callable(self, monkeypatch):
        """Test function should receive the generated function."""
        received_fn = {"fn": None}

        def fake_generate(module, functions, context, **kwargs):
            return "def fn(x):\n    return x * 2"

        def test_fn(fn):
            received_fn["fn"] = fn
            return fn(5) == 10

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        explore("wishful.static.test.fn", variants=1, test=test_fn, verbose=False)

        assert callable(received_fn["fn"])
        assert received_fn["fn"](3) == 6


class TestExploreWithBenchmark:
    """Benchmark-based selection."""

    def test_fastest_returns_highest_benchmark_score(self, monkeypatch):
        """With optimize='fastest', return variant with highest benchmark score."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            # Each variant returns its index as "speed"
            return f"def fn():\n    return {call_count['n']}"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore(
            "wishful.static.test.fn",
            variants=5,
            benchmark=lambda f: f(),  # Score = return value
            optimize="fastest",
            verbose=False,
        )

        assert fn() == 5  # Variant 5 had highest score

    def test_benchmark_with_test_filters_first(self, monkeypatch):
        """When both test and benchmark provided, test filters, benchmark selects."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            # Odd variants return "valid", even return "invalid"
            if call_count["n"] % 2 == 1:
                return f"def fn():\n    return ('valid', {call_count['n']})"
            return f"def fn():\n    return ('invalid', {call_count['n']})"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore(
            "wishful.static.test.fn",
            variants=5,
            test=lambda f: f()[0] == "valid",
            benchmark=lambda f: f()[1],  # Score = second element
            optimize="fastest",
            verbose=False,
        )

        # Valid variants: 1, 3, 5. Highest score is 5.
        assert fn() == ("valid", 5)


class TestExploreReturnAll:
    """Return all variants mode."""

    def test_return_all_gives_list(self, monkeypatch):
        """With return_all=True, return list of all passing variants."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            return f"def fn():\n    return {call_count['n']}"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        variants = explore(
            "wishful.static.test.fn",
            variants=5,
            test=lambda f: f() % 2 == 1,  # Only odd
            return_all=True,
            verbose=False,
        )

        assert isinstance(variants, list)
        assert len(variants) == 3  # 1, 3, 5
        assert [v() for v in variants] == [1, 3, 5]

    def test_return_all_empty_raises(self, monkeypatch):
        """With return_all=True, still raise if none pass."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn():\n    return 'nope'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ExplorationError):
            explore(
                "wishful.static.test.fn",
                variants=5,
                test=lambda f: False,
                return_all=True,
                verbose=False,
            )


class TestExploreTimeout:
    """Timeout handling."""

    def test_timeout_skips_slow_generation(self, monkeypatch):
        """Variants that exceed timeout should be skipped."""
        call_count = {"n": 0}

        async def fake_generate_async(module, functions, context, **kwargs):
            nonlocal call_count
            call_count["n"] += 1
            if call_count["n"] == 2:
                await asyncio.sleep(2)  # Slow generation
            return f"def fn():\n    return {call_count['n']}"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", fake_generate_async)

        variants = explore(
            "wishful.static.test.fn",
            variants=3,
            timeout_per_variant=0.5,
            return_all=True,
            verbose=False,
        )

        # Variant 2 should have been skipped due to timeout
        assert len(variants) == 2
        assert [v() for v in variants] == [1, 3]


class TestExploreMetadata:
    """Metadata attachment."""

    def test_function_has_wishful_metadata(self, monkeypatch):
        """Returned function should have __wishful_metadata__ attribute."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn():\n    return 42"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore("wishful.static.test.fn", variants=1, verbose=False)

        assert hasattr(fn, "__wishful_metadata__")
        assert "module" in fn.__wishful_metadata__
        assert "variant_index" in fn.__wishful_metadata__

    def test_function_has_wishful_source(self, monkeypatch):
        """Returned function should have __wishful_source__ attribute."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn():\n    return 42"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore("wishful.static.test.fn", variants=1, verbose=False)

        assert hasattr(fn, "__wishful_source__")
        assert "def fn():" in fn.__wishful_source__


class TestExploreErrorHandling:
    """Error cases."""

    def test_invalid_module_path_raises(self):
        """Invalid module path should raise ValueError."""
        with pytest.raises(ValueError, match="module path"):
            explore("invalid_path", variants=1, verbose=False)

    def test_short_module_path_raises(self):
        """Too short module path should raise ValueError."""
        with pytest.raises(ValueError, match="module path"):
            explore("wishful.static", variants=1, verbose=False)

    def test_syntax_error_in_variant_skips_it(self, monkeypatch):
        """If LLM generates invalid Python, skip that variant."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "def fn(\n    syntax error"  # Invalid
            return "def fn():\n    return 'valid'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore("wishful.static.test.fn", variants=2, verbose=False)

        assert fn() == "valid"

    def test_runtime_error_in_test_skips_variant(self, monkeypatch):
        """If test raises exception, skip that variant."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "def fn():\n    raise ValueError('boom')"
            return "def fn():\n    return 'ok'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        fn = explore(
            "wishful.static.test.fn",
            variants=2,
            test=lambda f: f() == "ok",  # First will raise
            verbose=False,
        )

        assert fn() == "ok"

    def test_no_valid_variants_raises(self, monkeypatch):
        """If all variants fail to compile, raise ExplorationError."""

        def fake_generate(module, functions, context, **kwargs):
            return "this is not valid python at all!!!"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ExplorationError) as exc_info:
            explore("wishful.static.test.fn", variants=3, verbose=False)

        assert "Failed to generate any valid variants" in str(exc_info.value)


class TestExplorationError:
    """ExplorationError details."""

    def test_error_includes_attempt_count(self, monkeypatch):
        """ExplorationError should include number of attempts."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn():\n    return 'nope'"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ExplorationError) as exc_info:
            explore("wishful.static.test.fn", variants=7, test=lambda f: False, verbose=False)

        assert exc_info.value.attempts == 7

    def test_error_includes_failure_reasons(self, monkeypatch):
        """ExplorationError should include why each variant failed."""
        call_count = {"n": 0}

        def fake_generate(module, functions, context, **kwargs):
            call_count["n"] += 1
            return f"def fn():\n    return {call_count['n']}"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ExplorationError) as exc_info:
            explore(
                "wishful.static.test.fn",
                variants=3,
                test=lambda f: f() > 100,  # None will pass
                verbose=False,
            )

        assert len(exc_info.value.failures) == 3


class TestExploreIntegration:
    """Integration with wishful module."""

    def test_explore_importable_from_wishful(self):
        """explore should be importable from main wishful module."""
        import wishful

        assert hasattr(wishful, "explore")
        assert hasattr(wishful, "ExplorationError")

    def test_explore_with_benchmark_requires_benchmark_for_fastest(self, monkeypatch):
        """optimize='fastest' without benchmark should raise ValueError."""

        def fake_generate(module, functions, context, **kwargs):
            return "def fn():\n    return 42"

        monkeypatch.setattr(explorer_module, "agenerate_module_code", make_async_fake(fake_generate))

        with pytest.raises(ValueError, match="benchmark is required"):
            explore(
                "wishful.static.test.fn",
                variants=3,
                optimize="fastest",
                verbose=False,
                # No benchmark provided!
            )
