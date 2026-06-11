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

    after_import = call_count["n"]
    first = proxy_story.next_line()
    second = proxy_story.next_line()

    # Each *call* regenerates exactly once with runtime context — accessing the
    # attribute no longer double-generates. (Was 2 generations per call.)
    assert first != second
    assert call_count["n"] == after_import + 2

    # Probing an attribute (hasattr/dir) must not cost a generation.
    before_probe = call_count["n"]
    hasattr(proxy_story, "never_generated_name")
    assert call_count["n"] == before_probe


def test_dynamic_module_identity_survives_regeneration(monkeypatch):
    """A dynamic module keeps its name/spec/loader across call-time re-exec."""
    def fake_generate(module, functions, context, **kwargs):
        return "def line():\n    return 'x'\n"

    monkeypatch.setattr(loader, "generate_module_code", fake_generate)
    manager.clear_cache()
    _reset_modules()

    import wishful.dynamic.identity_demo as demo

    assert demo.__name__ == "wishful.dynamic.identity_demo"
    spec_before = demo.__spec__
    demo.line()  # forces a clear_first re-exec
    assert demo.__name__ == "wishful.dynamic.identity_demo"
    assert demo.__spec__ is spec_before
    assert demo.__loader__ is not None


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


def test_cache_path_keeps_namespaces_disjoint():
    """Static and dynamic caches must never address the same file.

    Static (and the legacy unqualified form) live at <cache>/utils.py; dynamic
    lives under <cache>/_dynamic/utils.py so the two namespaces cannot collide.
    """
    static = module_path("wishful.static.utils")
    dynamic = module_path("wishful.dynamic.utils")
    legacy = module_path("wishful.utils")  # unqualified -> static base

    assert static.name == "utils.py"
    assert dynamic.name == "utils.py"
    assert legacy.name == "utils.py"

    assert static == legacy
    assert dynamic != static
    assert "_dynamic" in dynamic.parts
    assert "_dynamic" not in static.parts


# --- U15: API surface -------------------------------------------------------


def test_exception_hierarchy_under_wishful_error():
    from wishful import (
        EvolutionError,
        ExplorationError,
        GenerationError,
        SecurityError,
        WishfulError,
    )

    for exc in (SecurityError, GenerationError, ExplorationError, EvolutionError):
        assert issubclass(exc, WishfulError)
    # The generation/safety errors still surface as ImportError.
    assert issubclass(SecurityError, ImportError)
    assert issubclass(GenerationError, ImportError)


def test_subpackage_all_names_are_reachable():
    # The wishful.explore / wishful.evolve *attributes* are the top-level
    # explore()/evolve() functions (the documented API), so sub-items are reached
    # via the actual module; every __all__ name must resolve there.
    import importlib

    ex = importlib.import_module("wishful.explore")
    ev = importlib.import_module("wishful.evolve")
    for name in ex.__all__:
        assert hasattr(ex, name), f"wishful.explore.{name} missing"
    for name in ev.__all__:
        assert hasattr(ev, name), f"wishful.evolve.{name} missing"
    # And the direct from-import path works for a representative internal symbol.
    from wishful.explore import ExploreProgress  # noqa: F401
    from wishful.evolve import EvolutionHistory  # noqa: F401


def test_star_import_does_not_shadow_builtin_type():
    import subprocess

    code = (
        "from wishful import *\n"
        "assert type(5) is int\n"
        "import wishful\n"
        "assert wishful.type is not None\n"
        "assert 'type' not in getattr(__import__('wishful'), '__all__')\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_cache_subpackage_not_shadowed_by_alias():
    import subprocess

    code = (
        "import wishful\n"
        "import wishful.cache.manager\n"
        "assert hasattr(wishful.cache, 'read_cached'), 'wishful.cache is not the subpackage'\n"
        "assert wishful.cache.manager.module_path('wishful.static.x').name == 'x.py'\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
