from pathlib import Path

from loguru import logger as loguru_logger

import wishful
from wishful import logging as wl
from wishful.cache.manager import dynamic_snapshot_path
from wishful.logging import configure_logging


def _latest_log(cache_dir: Path) -> Path | None:
    log_dir = cache_dir / "_logs"
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("*.log"))
    return logs[-1] if logs else None


def test_logging_creates_file_and_records_generation(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        return "def foo():\n    return 'ok'\n"

    from wishful.core import loader

    monkeypatch.setattr(loader, "generate_module_code", gen)

    wishful.configure(debug=True, log_level="DEBUG")

    from wishful.static.logtest import foo

    assert foo() == "ok"
    log_path = _latest_log(wishful.settings.cache_dir)
    assert log_path and log_path.exists()
    log_text = log_path.read_text()
    assert "Generating wishful.static.logtest" in log_text
    assert call_count["n"] == 1


def test_logging_records_syntax_retry(monkeypatch):
    call_count = {"n": 0}

    def gen(module, functions, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "def broken(:\n    pass\n"
        return "def ping():\n    return 'pong'\n"

    from wishful.core import loader

    monkeypatch.setattr(loader, "generate_module_code", gen)

    wishful.configure(debug=True, log_level="DEBUG")

    import wishful.dynamic.logsyntax as mod

    assert mod.ping() == "pong"
    snap = dynamic_snapshot_path("wishful.dynamic.logsyntax")
    assert snap.exists()

    log_path = _latest_log(wishful.settings.cache_dir)
    assert log_path and log_path.exists()
    # With safety on (the shipped default), a malformed generation is caught at
    # validation time and the retry is logged here, before exec.
    assert (
        "wishful.dynamic.logsyntax has invalid syntax; regenerating once"
        in log_path.read_text()
    )


# --- U10: logging citizenship ------------------------------------------------


def test_configure_logging_preserves_host_sinks():
    """Importing/reconfiguring wishful must not delete a host app's loguru sink."""
    received = []
    host_id = loguru_logger.add(
        lambda m: received.append(m.record["message"]), level="DEBUG"
    )
    try:
        configure_logging(force=True)  # wishful reconfigures only its own sinks
        loguru_logger.info("host message after wishful reconfigure")
        assert any("host message" in r for r in received)
    finally:
        loguru_logger.remove(host_id)


def test_log_to_file_off_creates_no_files(tmp_path):
    fresh = tmp_path / "fresh_cache"
    wishful.configure(cache_dir=fresh, debug=False, log_to_file=False, log_level="WARNING")
    configure_logging(force=True)
    assert not (fresh / "_logs").exists()


def test_log_to_file_opt_in_creates_log(tmp_path):
    fresh = tmp_path / "optin_cache"
    wishful.configure(cache_dir=fresh, log_to_file=True, log_level="INFO")
    configure_logging(force=True)
    loguru_logger.info("hello file")
    log_dir = fresh / "_logs"
    assert log_dir.exists()
    assert list(log_dir.glob("*.log"))


def test_log_to_file_readonly_degrades_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(wl, "_file_log_warned", False)

    def boom(*args, **kwargs):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("pathlib.Path.mkdir", boom)
    wishful.configure(cache_dir=tmp_path / "ro_cache", log_to_file=True)
    # Must not raise even though the log directory cannot be created.
    configure_logging(force=True)
