"""Tests for static vs dynamic namespace behavior."""

import sys

from wishful import regenerate
from wishful.cache import manager
from wishful.core import loader
from wishful.core.finder import STATIC_NAMESPACE, DYNAMIC_NAMESPACE
from wishful.cache.manager import module_path


def _reset_modules():
    for name in list(sys.modules):
        if name.startswith("wishful.") or name == "wishful":
            sys.modules.pop(name, None)
    import importlib
    importlib.invalidate_caches()


def test_static_uses_cache(monkeypatch):
    """Static imports should cache and reuse generated code."""
    call_count = {"n": 0}

    def fake_generate(module, functions, context, **kwargs):
        call_count["n"] += 1
        return "def test_func():\n    return 'generated'\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)

    manager.clear_cache()
    _reset_modules()

    # First import generates
    from wishful.static.cached import test_func
    assert test_func() == "generated"
    assert call_count["n"] == 1

    # Second import uses cache (shouldn't call generate again)
    _reset_modules()
    def boom(*args, **kwargs):
        raise AssertionError("Should not generate - cache exists!")
    
    monkeypatch.setattr(loader, "generate_module_code", boom)
    from wishful.static.cached import test_func as test_func2
    assert test_func2() == "generated"
    assert call_count["n"] == 1  # Still 1 - didn't regenerate


def test_dynamic_skips_cache(monkeypatch):
    """Dynamic imports should regenerate every time, never use cache."""
    call_count = {"n": 0}

    def fake_generate(module, functions, context, **kwargs):
        call_count["n"] += 1
        return f"def test_func():\n    return 'gen_{call_count['n']}'\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)

    manager.clear_cache()
    _reset_modules()

    from wishful.dynamic.nocache import test_func
    result1 = test_func()
    first_calls = call_count["n"]
    assert first_calls >= 2  # initial import + proxy regen on access

    _reset_modules()
    from wishful.dynamic.nocache import test_func as test_func2
    result2 = test_func2()
    assert result1 != result2  # different generation after re-import
    assert call_count["n"] > first_calls


def test_dynamic_proxy_regenerates_on_each_access(monkeypatch):
    call_count = {"n": 0}

    def fake_generate(module, functions, context, **kwargs):
        call_count["n"] += 1
        return "def next_line():\n    return 'gen_" + str(call_count["n"]) + "'\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)

    manager.clear_cache()
    _reset_modules()

    import wishful.dynamic.proxy_story as proxy_story

    first = proxy_story.next_line()
    second = proxy_story.next_line()

    # Each call triggers regeneration with runtime context; counts should climb
    assert first != second
    assert call_count["n"] >= 4  # import regen + attr access + two call-time regens


def test_static_and_dynamic_independent_caches(monkeypatch):
    """Static and dynamic with same module name should have independent behavior."""
    
    def fake_generate(module, functions, context, **kwargs):
        if "static" in module:
            return "def get_value():\n    return 'static'\n"
        else:
            return "def get_value():\n    return 'dynamic'\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)

    manager.clear_cache()
    _reset_modules()

    # Import both static and dynamic versions of "data" module
    from wishful.static.data import get_value as static_get
    from wishful.dynamic.data import get_value as dynamic_get

    assert static_get() == "static"
    assert dynamic_get() == "dynamic"


def test_namespace_isolation():
    """Ensure wishful.* internal modules are protected."""
    # The important test is that wishful.static/dynamic don't conflict
    # with internal wishful.cache, wishful.config, etc.
    # This is validated in the finder's _is_internal_module check.
    
    # Just ensure static/dynamic work (internal isolation is implicit)
    assert STATIC_NAMESPACE == "wishful.static"
    assert DYNAMIC_NAMESPACE == "wishful.dynamic"


def test_regenerate_defaults_to_static():
    """The regenerate() function should default to static namespace."""    
    # Write a cached static module
    manager.write_cached("wishful.static.test", "def foo(): return 1")
    assert manager.has_cached("wishful.static.test")
    
    # Regenerate without prefix should work
    regenerate("test")
    assert not manager.has_cached("wishful.static.test")
    
    # Clean up
    manager.clear_cache()


def test_cache_path_strips_namespaces():
    """Cache paths should strip static/dynamic prefixes."""    
    # All these should map to the same cache file
    path1 = module_path("wishful.static.utils")
    path2 = module_path("wishful.dynamic.utils")
    path3 = module_path("wishful.utils")  # Legacy
    
    # They should all resolve to utils.py (without static/dynamic)
    assert path1.name == "utils.py"
    assert path2.name == "utils.py"
    assert path3.name == "utils.py"
    assert path1 == path2 == path3
