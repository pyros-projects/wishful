from pathlib import Path

import wishful
from wishful.cache.manager import dynamic_snapshot_path


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
    assert "SyntaxError while loading wishful.dynamic.logsyntax" in log_path.read_text()
