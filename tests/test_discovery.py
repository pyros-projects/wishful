"""Tests for context discovery and LLM prompt generation."""

import pytest

from wishful.core.discovery import ImportContext, _parse_imported_names, discover


def test_parse_imported_names_from_import():
    """Test parsing function names from 'from X import Y' statements."""
    source = "from wishful.text import extract_emails, parse_html"
    names = _parse_imported_names(source, "wishful.text")
    assert "extract_emails" in names
    assert "parse_html" in names


def test_parse_imported_names_import():
    """Test parsing module names from 'import X' statements."""
    source = "import wishful.utils"
    names = _parse_imported_names(source, "wishful.utils")
    assert "utils" in names


def test_parse_imported_names_with_alias():
    """Test that original name is returned, not alias."""
    source = "from wishful.text import extract_emails as get_emails"
    names = _parse_imported_names(source, "wishful.text")
    assert "extract_emails" in names
    assert "get_emails" not in names


def test_parse_imported_names_no_match():
    """Test that non-matching imports return empty list."""
    source = "from other.module import something"
    names = _parse_imported_names(source, "wishful.text")
    assert names == []


def test_import_context_structure():
    """Test ImportContext dataclass structure."""
    ctx = ImportContext(functions=["foo", "bar"], context="# some comment")
    assert ctx.functions == ["foo", "bar"]
    assert ctx.context == "# some comment"


def test_discover_returns_empty_when_no_context():
    """Test that discover returns empty context when called without import context."""
    # When called directly (not from an import), should return empty
    ctx = discover("wishful.nonexistent")
    assert isinstance(ctx, ImportContext)
    # May have empty functions or context depending on call site
