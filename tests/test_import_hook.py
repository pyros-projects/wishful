import importlib
import sys
import types

import pytest

from wishful import regenerate
from wishful.cache import manager
from wishful.cache.manager import dynamic_snapshot_path
from wishful.config import configure
from wishful.core import loader
from wishful.llm.client import GenerationError
from wishful.safety.validator import SecurityError


def _reset_modules():
    for name in list(sys.modules):
        if name.startswith("wishful.") or name == "wishful":
            sys.modules.pop(name, None)
    importlib.invalidate_caches()


def test_generates_and_caches_on_first_import(monkeypatch):
    call_count = {"n": 0}

    def fake_generate(module, functions, context, **kwargs):
        call_count["n"] += 1
        assert module == "wishful.static.utils"
        # ensure discovery passes function names through
        assert "meaning_of_life" in functions
        return "def meaning_of_life():\n    return 42\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)

    manager.clear_cache()
    _reset_modules()

    from wishful.static.utils import meaning_of_life

    assert meaning_of_life() == 42
    assert call_count["n"] == 1
    assert manager.has_cached("wishful.static.utils")


def test_reimport_uses_cache(monkeypatch):
    # First import to populate cache
    def first_generate(module, functions, context, **kwargs):
        return "def meaning_of_life():\n    return 84\n"

    monkeypatch.setattr(loader, "generate_module_code", first_generate)
    manager.clear_cache()
    _reset_modules()
    from wishful.static.utils import meaning_of_life
    assert meaning_of_life() == 84

    # Second import should not invoke generator even if patched to blow up
    def boom(*args, **kwargs):
        raise AssertionError("generator should not run for cached module")

    monkeypatch.setattr(loader, "generate_module_code", boom)
    _reset_modules()
    meaning_again = importlib.import_module("wishful.static.utils").meaning_of_life
    assert meaning_again() == 84


def test_regenerate_forces_new_generation(monkeypatch):
    # Seed cache with one value
    def gen_one(module, functions, context, **kwargs):
        return "def answer():\n    return 1\n"

    monkeypatch.setattr(loader, "generate_module_code", gen_one)
    manager.clear_cache()
    _reset_modules()
    from wishful.static.values import answer
    assert answer() == 1

    # Change generator and regenerate
    def gen_two(module, functions, context, **kwargs):
        return "def answer():\n    return 2\n"

    monkeypatch.setattr(loader, "generate_module_code", gen_two)
    regenerate("wishful.static.values")
    _reset_modules()
    from wishful.static.values import answer as answer_two
    assert answer_two() == 2


def test_missing_symbol_in_cache_triggers_regeneration(monkeypatch):
    """If cached module lacks requested name, loader regenerates once."""

    manager.write_cached("wishful.static.broken", "def other():\n    return 'nope'\n")

    def gen_fixed(module, functions, context, **kwargs):
        assert "expect_me" in functions
        return "def expect_me():\n    return 'fixed'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen_fixed)

    _reset_modules()
    from wishful.static.broken import expect_me

    assert expect_me() == "fixed"


def test_dynamic_getattr_generates_additional_functions(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            assert functions == ["foo"]
            return "def foo():\n    return 'foo'\n"
        assert "bar" in functions
        # return both functions to ensure prior ones stay available
        return "def foo():\n    return 'foo'\n\ndef bar():\n    return 'bar'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.text import foo
    assert foo() == "foo"
    assert call_count["n"] == 1

    from wishful.static.text import bar
    assert bar() == "bar"
    assert call_count["n"] == 2

    # Ensure original function still present after regeneration
    from wishful.static.text import foo as foo_again
    assert foo_again() == "foo"


def test_multiple_imports_preserve_existing(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        body = []
        for name in sorted(set(functions)):
            body.append(f"def {name}():\n    return '{name}'\n")
        return "\n".join(body)

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.text import first
    assert first() == "first"
    assert call_count["n"] == 1

    from wishful.static.text import second
    assert second() == "second"
    assert call_count["n"] == 2


def test_dynamic_call_includes_runtime_context(monkeypatch):
    call_count = {"n": 0}
    contexts: list[str | None] = []
    modes: list[str | None] = []

    def gen(module, functions, context, type_schemas=None, function_output_types=None, mode=None):
        call_count["n"] += 1
        contexts.append(context)
        modes.append(mode)
        body = []
        for name in sorted(set(functions)):
            body.append(f"def {name}(*args, **kwargs):\n    return '{name}'\n")
        return "\n".join(body)

    monkeypatch.setattr(loader, "generate_module_code", gen)

    manager.clear_cache()
    _reset_modules()

    import wishful.dynamic.ctxdemo as ctxdemo

    # Importing the module generated it once; merely *accessing* an attribute
    # does not generate again (the call does).
    after_import = call_count["n"]
    fn = ctxdemo.make_line
    assert call_count["n"] == after_import

    # Call should trigger regeneration with runtime context
    result = fn("hello", mood="grim")
    assert result == "make_line"

    # Latest generation should include runtime call info and dynamic mode
    assert any(context and "Runtime call context" in context for context in contexts)
    assert modes and modes[-1] == "dynamic"

    # One generation at import + one at call time — no wasteful attr-access gen.
    assert call_count["n"] == after_import + 1


def test_static_syntax_error_retries_once(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "def broken(:\n    pass\n"
        return "def foo():\n    return 'ok'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)

    manager.clear_cache()
    _reset_modules()

    from wishful.static.syntax_retry import foo

    assert foo() == "ok"
    assert call_count["n"] == 2

    cached = manager.read_cached("wishful.static.syntax_retry")
    assert "def foo" in cached
    assert "broken" not in cached


def test_dynamic_syntax_error_retries_once(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "def broken(:\n    pass\n"
        return "def ping():\n    return 'pong'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)

    manager.clear_cache()
    _reset_modules()

    import wishful.dynamic.syntax_retry_dyn as mod

    assert mod.ping() == "pong"
    assert call_count["n"] >= 2

    snap = dynamic_snapshot_path("wishful.dynamic.syntax_retry_dyn")
    assert snap.exists()
    text = snap.read_text()
    assert "def ping" in text


# --- U4: cache integrity with safety ON -------------------------------------


def test_syntax_retry_works_with_safety_on(monkeypatch):
    """The regenerate-once retry must fire with the validator enabled (the
    composition bug: validator used to swallow SyntaxError as ImportError)."""
    configure(allow_unsafe=False)
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "def broken(:\n    pass\n"
        return "def foo():\n    return 'ok'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.safe_retry import foo

    assert foo() == "ok"
    assert call_count["n"] == 2
    cached = manager.read_cached("wishful.static.safe_retry")
    assert "def foo" in cached
    assert "broken" not in cached


def test_persistent_syntax_error_leaves_no_cache(monkeypatch):
    """Two malformed generations -> GenerationError, and nothing is cached."""
    configure(allow_unsafe=False)

    def gen(module, functions, context, **kwargs):
        return "def broken(:\n    pass\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    with pytest.raises(GenerationError):
        importlib.import_module("wishful.static.always_broken")
    assert not manager.has_cached("wishful.static.always_broken")


def test_security_violation_not_cached_then_recovers(monkeypatch):
    """A dangerous generation is never written; a later clean generation works."""
    configure(allow_unsafe=False)
    calls = {"n": 0}

    def gen(module, functions, context, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "import os\nos.system('echo hi')\ndef foo():\n    return 1\n"
        return "def foo():\n    return 1\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    with pytest.raises(SecurityError):
        importlib.import_module("wishful.static.danger")
    assert not manager.has_cached("wishful.static.danger")

    _reset_modules()
    from wishful.static.danger import foo

    assert foo() == 1
    assert calls["n"] == 2


def test_cache_hit_revalidates_poisoned_source_and_cleans_up(monkeypatch):
    """A poisoned cache file is rejected at load AND deleted so it can't
    permanently break the import."""
    configure(allow_unsafe=False)
    manager.write_cached(
        "wishful.static.poisoned",
        "import os\nos.system('rm -rf /')\ndef foo():\n    return 1\n",
    )
    _reset_modules()

    with pytest.raises(SecurityError):
        importlib.import_module("wishful.static.poisoned")
    # The rejected cache entry is removed, not left to fail forever.
    assert not manager.has_cached("wishful.static.poisoned")


def test_attribute_defined_via_unpacking_is_accepted(monkeypatch):
    """A regeneration that binds the requested symbol via tuple unpacking must
    be committed, not rejected (the _source_defines AST check must see it)."""
    calls = {"n": 0}

    def gen(module, functions, context, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "def foo():\n    return 'foo'\n"
        return (
            "def foo():\n    return 'foo'\n"
            "def _pair():\n    return ('a', 'b')\n"
            "bar, baz = _pair()\n"
        )

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.unpk import foo

    assert foo() == "foo"
    mod = sys.modules["wishful.static.unpk"]
    assert mod.bar == "a"  # bound via unpacking; must be accepted


def test_regenerate_dynamic_preserves_static_namesake():
    """regenerate('wishful.dynamic.x') must not delete the static x cache."""
    manager.write_cached("wishful.static.report", "def s():\n    return 'static'\n")
    manager.write_dynamic_snapshot("wishful.dynamic.report", "def d():\n    return 'dyn'\n")

    regenerate("wishful.dynamic.report")

    assert manager.has_cached("wishful.static.report")
    assert not manager.dynamic_snapshot_path("wishful.dynamic.report").exists()


# --- U6: probe-safe attribute handling --------------------------------------


def _counting_generator(call_count):
    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        body = [f"def {n}():\n    return '{n}'\n" for n in sorted(set(functions))]
        return "\n".join(body)

    return gen


def test_underscore_probes_do_not_generate(monkeypatch):
    call_count = {"n": 0}
    monkeypatch.setattr(loader, "generate_module_code", _counting_generator(call_count))
    manager.clear_cache()
    _reset_modules()

    from wishful.static.probe import foo

    assert foo() == "foo"
    assert call_count["n"] == 1

    mod = sys.modules["wishful.static.probe"]
    # Underscore-prefixed probes (IPython repr, private) raise AttributeError
    # without a single generation.
    assert not hasattr(mod, "_repr_html_")
    assert getattr(mod, "_private", None) is None
    assert getattr(mod, "__wrapped__", None) is None
    assert call_count["n"] == 1


def test_public_attribute_miss_still_generates(monkeypatch):
    call_count = {"n": 0}
    monkeypatch.setattr(loader, "generate_module_code", _counting_generator(call_count))
    manager.clear_cache()
    _reset_modules()

    from wishful.static.probe2 import foo

    assert foo() == "foo"
    assert call_count["n"] == 1

    mod = sys.modules["wishful.static.probe2"]
    assert mod.bar() == "bar"  # a real wish for a new public symbol
    assert call_count["n"] == 2


def test_generation_lacking_symbol_does_not_clobber_cache(monkeypatch):
    call_count = {"n": 0}

    def stubborn(module, functions, context, **kwargs):
        call_count["n"] += 1
        return "def foo():\n    return 'foo'\n"  # never defines the new name

    monkeypatch.setattr(loader, "generate_module_code", stubborn)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.stubborn import foo

    assert foo() == "foo"
    cached_before = manager.read_cached("wishful.static.stubborn")

    mod = sys.modules["wishful.static.stubborn"]
    with pytest.raises(AttributeError):
        _ = mod.nonexistent

    # The discarded regeneration must not have overwritten the cache or module.
    assert manager.read_cached("wishful.static.stubborn") == cached_before
    assert mod.foo() == "foo"


# --- U8: review gate ordering + TTY guard -----------------------------------


def test_review_rejection_blocks_execution_before_it_runs(monkeypatch):
    """Rejection must raise before the module body executes (the bug: review
    ran AFTER exec, so the code had already run)."""
    configure(review=True)
    monkeypatch.setattr(loader, "_is_promptable", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    def gen(module, functions, context, **kwargs):
        # If this body ever executes, it raises RuntimeError, not ImportError.
        return "raise RuntimeError('top-level executed')\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    with pytest.raises(ImportError):  # rejection, NOT RuntimeError
        importlib.import_module("wishful.static.reviewed_reject")
    assert not manager.has_cached("wishful.static.reviewed_reject")


def test_review_approval_executes(monkeypatch):
    configure(review=True)
    monkeypatch.setattr(loader, "_is_promptable", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    def gen(module, functions, context, **kwargs):
        return "def foo():\n    return 'ok'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.reviewed_ok import foo

    assert foo() == "ok"


def test_review_non_interactive_raises_before_generation(monkeypatch):
    """Headless + review=True must raise an actionable ImportError and never
    pay for an LLM call."""
    configure(review=True)
    monkeypatch.setattr(loader, "_is_promptable", lambda: False)
    calls = {"n": 0}

    def gen(module, functions, context, **kwargs):
        calls["n"] += 1
        return "def foo():\n    return 1\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    with pytest.raises(ImportError, match="interactive"):
        importlib.import_module("wishful.static.headless_review")
    assert calls["n"] == 0


def test_review_eof_is_treated_as_rejection(monkeypatch):
    configure(review=True)
    monkeypatch.setattr(loader, "_is_promptable", lambda: True)

    def raise_eof(prompt=""):
        raise EOFError()

    monkeypatch.setattr("builtins.input", raise_eof)

    def gen(module, functions, context, **kwargs):
        return "def foo():\n    return 1\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    with pytest.raises(ImportError):
        importlib.import_module("wishful.static.eof_review")


def test_review_gates_regeneration_path(monkeypatch):
    """A new-attribute regeneration also goes through the review prompt."""
    configure(review=True)
    monkeypatch.setattr(loader, "_is_promptable", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    def gen(module, functions, context, **kwargs):
        body = [f"def {n}():\n    return '{n}'\n" for n in sorted(set(functions))]
        return "\n".join(body)

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.regrev import foo

    assert foo() == "foo"
    mod = sys.modules["wishful.static.regrev"]
    assert mod.bar() == "bar"  # regen path prompted (approved) then executed


def test_ipykernel_counts_as_promptable(monkeypatch):
    """Notebooks route input() to the frontend even though stdin isn't a TTY."""
    monkeypatch.setitem(sys.modules, "ipykernel", types.ModuleType("ipykernel"))
    assert loader._is_promptable() is True


# --- U9: safety-ON test posture ---------------------------------------------


def test_suite_default_is_safety_on():
    """Guard against a regression back to the global allow_unsafe=True default."""
    from wishful.config import settings

    assert settings.allow_unsafe is False


def test_unsafe_settings_fixture_enables_bypass(unsafe_settings):
    from wishful.config import settings
    from wishful.safety.validator import validate_code

    assert settings.allow_unsafe is True
    # With the bypass on, even dangerous code passes validation.
    validate_code("import os\nos.system('x')\n", allow_unsafe=settings.allow_unsafe)


def test_clean_generation_imports_end_to_end_with_validation(monkeypatch):
    """A clean generation runs through the full pipeline with safety ON."""

    def gen(module, functions, context, **kwargs):
        return "import json\n\ndef dump(obj):\n    return json.dumps(obj)\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)
    manager.clear_cache()
    _reset_modules()

    from wishful.static.jsonhelp import dump

    assert dump({"a": 1}) == '{"a": 1}'


def test_dynamic_writes_snapshot(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        return "def ping():\n    return 'pong'\n"

    monkeypatch.setattr(loader, "generate_module_code", gen)

    manager.clear_cache()
    _reset_modules()

    from wishful.dynamic.snapdemo import ping

    assert ping() == "pong"

    path = dynamic_snapshot_path("wishful.dynamic.snapdemo")
    assert path.exists()
    assert "ping" in path.read_text()
    assert call_count["n"] >= 2
