"""Tests for the CLI interface."""

import sys

import pytest

from wishful import __main__ as cli
from wishful.cache import manager
from wishful.config import configure


def test_cli_no_args(monkeypatch, capsys):
    """Test CLI with no arguments shows help."""
    monkeypatch.setattr(sys, "argv", ["wishful"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Usage:" in captured.out
    assert "inspect" in captured.out
    assert "clear" in captured.out
    assert "regen" in captured.out


def test_cli_inspect_empty(monkeypatch, capsys):
    """Test inspect command with no cached modules."""
    manager.clear_cache()
    monkeypatch.setattr(sys, "argv", ["wishful", "inspect"])
    cli.main()
    captured = capsys.readouterr()
    assert "No cached modules" in captured.out


def test_cli_inspect_with_cache(monkeypatch, capsys, tmp_path):
    """Test inspect command with cached modules."""
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.test", "# test")
    
    monkeypatch.setattr(sys, "argv", ["wishful", "inspect"])
    cli.main()
    captured = capsys.readouterr()
    assert "Cached modules" in captured.out
    assert "test.py" in captured.out
    
    manager.clear_cache()


def test_cli_clear(monkeypatch, capsys, tmp_path):
    """Test clear command."""
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.test", "# test")
    
    monkeypatch.setattr(sys, "argv", ["wishful", "clear"])
    cli.main()
    captured = capsys.readouterr()
    assert "Cleared all cached modules" in captured.out
    assert not manager.inspect_cache()


def test_cli_regen(monkeypatch, capsys, tmp_path):
    """Test regen command."""
    configure(cache_dir=tmp_path / ".wishful")
    manager.write_cached("wishful.test", "# test")
    
    monkeypatch.setattr(sys, "argv", ["wishful", "regen", "wishful.test"])
    cli.main()
    captured = capsys.readouterr()
    assert "Regenerated wishful.test" in captured.out
    assert not manager.has_cached("wishful.test")


def test_cli_regen_no_module(monkeypatch, capsys):
    """Test regen command without module name."""
    monkeypatch.setattr(sys, "argv", ["wishful", "regen"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "requires a module name" in captured.out


def test_cli_unknown_command(monkeypatch, capsys):
    """Test unknown command."""
    monkeypatch.setattr(sys, "argv", ["wishful", "unknown"])
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out
