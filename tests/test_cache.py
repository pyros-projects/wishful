import pytest

from wishful.cache import manager


def test_cache_roundtrip(tmp_path):
    source = "def alpha():\n    return 1\n"
    path = manager.write_cached("wishful.utils", source)

    assert path.exists()
    assert path.parent == tmp_path / ".wishful"
    assert manager.read_cached("wishful.utils") == source

    all_cached = manager.inspect_cache()
    assert path in all_cached


def test_clear_cache(tmp_path):
    manager.write_cached("wishful.utils", "# stub")
    manager.write_cached("wishful.other", "# stub")
    assert manager.inspect_cache()
    manager.clear_cache()
    assert manager.inspect_cache() == []
    assert not (tmp_path / ".wishful").exists()


# --- U4: cache integrity ----------------------------------------------------


def test_empty_cache_file_is_a_miss(tmp_path):
    """A torn/empty cache file reads as a miss, not a valid empty module."""
    path = manager.module_path("wishful.static.empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("   \n")
    assert manager.read_cached("wishful.static.empty") is None


def test_atomic_write_failure_leaves_original_intact(monkeypatch, tmp_path):
    """A failed os.replace must leave the previous cache file untouched and
    leave no stray temp file behind."""
    manager.write_cached("wishful.static.keep", "def foo():\n    return 1\n")
    original = manager.read_cached("wishful.static.keep")

    def boom(*args, **kwargs):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(manager.os, "replace", boom)
    with pytest.raises(OSError):
        manager.write_cached("wishful.static.keep", "def foo():\n    return 2\n")

    assert manager.read_cached("wishful.static.keep") == original
    leftovers = list(manager.settings.cache_dir.glob("**/*.tmp"))
    assert leftovers == []


# --- U5: cache namespacing ---------------------------------------------------


def test_static_and_dynamic_never_share_a_path():
    static = manager.module_path("wishful.static.foo")
    dynamic = manager.module_path("wishful.dynamic.foo")
    assert static != dynamic
    assert "_dynamic" in dynamic.parts
    assert "_dynamic" not in static.parts


def test_static_module_path_unchanged():
    """Static layout stays at <cache>/<name>.py (documented, user-editable)."""
    p = manager.module_path("wishful.static.text")
    assert p == manager.settings.cache_dir / "text.py"


def test_delete_dynamic_does_not_touch_static(tmp_path):
    manager.write_cached("wishful.static.shared", "def s():\n    return 'static'\n")
    manager.write_dynamic_snapshot("wishful.dynamic.shared", "def d():\n    return 'dyn'\n")
    assert manager.module_path("wishful.static.shared").exists()

    manager.delete_cached("wishful.dynamic.shared")

    # static survives; only the dynamic snapshot is gone
    assert manager.read_cached("wishful.static.shared") == "def s():\n    return 'static'\n"
    assert not manager.dynamic_snapshot_path("wishful.dynamic.shared").exists()
