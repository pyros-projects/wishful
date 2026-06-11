import time

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


@pytest.mark.parametrize(
    "bad_name",
    [
        "wishful.static.../../etc/passwd",
        "wishful.static.a/b",
        "users/../../etc",
        "wishful.static..__init__",
        "wishful.static.\\windows",
    ],
)
def test_module_path_rejects_traversal(bad_name):
    with pytest.raises(ValueError):
        manager.module_path(bad_name)
    with pytest.raises(ValueError):
        manager.dynamic_snapshot_path(bad_name)


def test_delete_dynamic_does_not_touch_static(tmp_path):
    manager.write_cached("wishful.static.shared", "def s():\n    return 'static'\n")
    manager.write_dynamic_snapshot("wishful.dynamic.shared", "def d():\n    return 'dyn'\n")
    assert manager.module_path("wishful.static.shared").exists()

    manager.delete_cached("wishful.dynamic.shared")

    # static survives; only the dynamic snapshot is gone
    assert manager.read_cached("wishful.static.shared") == "def s():\n    return 'static'\n"
    assert not manager.dynamic_snapshot_path("wishful.dynamic.shared").exists()


class TestCacheHelpers:
    """The small manager helpers, pinned (#62)."""

    def test_has_cached_lifecycle(self):
        from wishful.cache import manager

        name = "wishful.static.helper_demo"
        assert manager.has_cached(name) is False
        manager.write_cached(name, "def f():\n    return 1\n")
        assert manager.has_cached(name) is True
        manager.delete_cached(name)
        assert manager.has_cached(name) is False

    def test_delete_cached_missing_is_noop(self):
        from wishful.cache import manager

        manager.delete_cached("wishful.static.never_existed")  # must not raise

    def test_snapshot_path_is_disjoint_from_static(self):
        from wishful.cache import manager

        static = manager.module_path("wishful.static.same_name")
        dynamic = manager.dynamic_snapshot_path("wishful.dynamic.same_name")
        assert static != dynamic
        assert "_dynamic" in str(dynamic)

    def test_inspect_cache_lists_written_modules(self):
        from wishful.cache import manager

        manager.write_cached("wishful.static.listme", "def f():\n    return 1\n")
        listed = [str(p) for p in manager.inspect_cache()]
        assert any("listme" in p for p in listed)


def _race_writer(cache_dir: str, marker: str, rounds: int) -> None:
    """Child-process body for the cross-process write race (module-level for spawn)."""
    import wishful

    wishful.configure(cache_dir=cache_dir)
    from wishful.cache import manager as child_manager

    payload = f"def f():\n    return {marker!r}\n" + ("# pad\n" * 2000)
    for _ in range(rounds):
        child_manager.write_cached("wishful.static.race_target", payload)


class TestCrossProcessAtomicity:
    """Two writer processes; readers never see a torn file (review testing gap)."""

    def test_concurrent_writers_never_tear(self, tmp_path):
        import multiprocessing

        import wishful
        from wishful.cache import manager

        cache_dir = str(tmp_path / ".wishful")
        wishful.configure(cache_dir=cache_dir)

        payloads = {
            m: f"def f():\n    return {m!r}\n" + ("# pad\n" * 2000) for m in ("a", "b")
        }

        ctx = multiprocessing.get_context("spawn")
        writers = [
            ctx.Process(target=_race_writer, args=(cache_dir, m, 40)) for m in ("a", "b")
        ]
        for w in writers:
            w.start()

        torn = []
        deadline = time.monotonic() + 60  # escape hatch: a hung child must not hang CI
        timed_out = False
        try:
            while any(w.is_alive() for w in writers):
                if time.monotonic() > deadline:
                    timed_out = True
                    break
                text = manager.read_cached("wishful.static.race_target")
                if text is not None and text not in payloads.values():
                    torn.append(text[:120])
        finally:
            for w in writers:
                w.join(timeout=30)
                if w.is_alive():
                    w.kill()

        assert not timed_out, "writer processes did not finish before the deadline"
        assert not torn, f"torn reads observed: {torn[:2]}"
        for w in writers:
            assert w.exitcode == 0
