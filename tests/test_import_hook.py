import importlib
import sys

from wishful import regenerate
from wishful.cache import manager
from wishful.core import loader


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

    # Ensure the original function still works without new generation
    from wishful.static.text import first as first_again
    assert first_again() == "first"
    assert call_count["n"] == 2
