from pathlib import Path

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
