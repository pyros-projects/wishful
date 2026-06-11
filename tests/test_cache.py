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
