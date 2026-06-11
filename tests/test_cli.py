"""Tests for the CLI interface.

Exit codes: 0 success, 1 runtime error, 2 usage error (argparse). main() returns
the int code; argparse raises SystemExit(2) for usage errors.
"""

import importlib.metadata
import json

import pytest

import wishful
from wishful import __main__ as cli
from wishful.cache import manager
from wishful.config import configure


def test_cli_no_args_prints_help_returns_zero(capsys):
    code = cli.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "usage: wishful" in out
    for cmd in ("inspect", "clear", "regen"):
        assert cmd in out


def test_cli_version():
    code = cli.main(["--version"])
    assert code == 0


def test_cli_version_matches_metadata(capsys):
    cli.main(["--version"])
    printed = capsys.readouterr().out.strip()
    assert printed == importlib.metadata.version("wishful")
    assert printed == wishful.__version__


def test_cli_inspect_empty(capsys):
    manager.clear_cache()
    assert cli.main(["inspect"]) == 0
    assert "No cached modules" in capsys.readouterr().out


def test_cli_inspect_json(capsys, tmp_path):
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.static.text", "# test")
    assert cli.main(["inspect", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "cached" in payload and "cache_dir" in payload
    assert any("text.py" in p for p in payload["cached"])
    manager.clear_cache()


def test_cli_clear_json(capsys, tmp_path):
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.static.text", "# test")
    assert cli.main(["clear", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["cleared"] is True
    assert not manager.inspect_cache()


def test_cli_regen_json(capsys, tmp_path):
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.static.text", "# test")
    assert cli.main(["regen", "wishful.static.text", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"module": "wishful.static.text", "regenerated": True}
    assert not manager.has_cached("wishful.static.text")


def test_cli_regen_rejects_traversal_module_name(capsys):
    code = cli.main(["regen", "../../etc/passwd", "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert "error" in payload


def test_cli_regen_module_name_validation():
    # Reserved wishful.* names must be fully-qualified static/dynamic.
    assert cli._valid_module("wishful.static.text") is True
    assert cli._valid_module("wishful.dynamic.story") is True
    assert cli._valid_module("users") is True  # bare -> static namespace
    assert cli._valid_module("wishful") is False
    assert cli._valid_module("wishful.text") is False  # framework package, not static/dynamic
    assert cli._valid_module("../etc/passwd") is False
    assert cli._valid_module("a/b") is False


def test_cli_regen_rejects_framework_package(capsys):
    code = cli.main(["regen", "wishful", "--json"])
    assert code == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_cli_regen_missing_module_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        cli.main(["regen"])
    assert exc.value.code == 2


def test_cli_unknown_command_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        cli.main(["bogus"])
    assert exc.value.code == 2
