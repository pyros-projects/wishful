import importlib
import sys

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

    # First access triggers regeneration via proxy
    fn = ctxdemo.make_line
    assert call_count["n"] >= 1

    # Call should trigger regeneration with runtime context
    result = fn("hello", mood="grim")
    assert result == "make_line"

    # Latest generation should include runtime call info and dynamic mode
    assert any(context and "Runtime call context" in context for context in contexts)
    assert modes and modes[-1] == "dynamic"

    # Call count should reflect import + attr + call-time generations
    assert call_count["n"] >= 3


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


def test_cache_hit_revalidates_poisoned_source(monkeypatch):
    """A poisoned cache file (dangerous code) is rejected at load time."""
    configure(allow_unsafe=False)
    manager.write_cached(
        "wishful.static.poisoned",
        "import os\nos.system('rm -rf /')\ndef foo():\n    return 1\n",
    )
    _reset_modules()

    with pytest.raises(SecurityError):
        importlib.import_module("wishful.static.poisoned")


def test_regenerate_dynamic_preserves_static_namesake():
    """regenerate('wishful.dynamic.x') must not delete the static x cache."""
    manager.write_cached("wishful.static.report", "def s():\n    return 'static'\n")
    manager.write_dynamic_snapshot("wishful.dynamic.report", "def d():\n    return 'dyn'\n")

    regenerate("wishful.dynamic.report")

    assert manager.has_cached("wishful.static.report")
    assert not manager.dynamic_snapshot_path("wishful.dynamic.report").exists()


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
