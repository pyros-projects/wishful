"""Tests for context discovery and LLM prompt generation."""

from dataclasses import dataclass

from wishful.core.discovery import ImportContext, _parse_imported_names, discover
from wishful.core import discovery
from wishful.types import type as type_decorator, clear_type_registry


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


def test_set_context_radius_updates(monkeypatch):
    """Ensure the exported setter updates discovery radius."""
    discovery.set_context_radius(7)
    assert discovery._context_radius == 7


def test_gather_usage_context_includes_calls(tmp_path):
    """Call sites should add surrounding lines to context."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from wishful.text import foo\n"
        "# note: foo returns value\n"
        "foo(1)\n"
        "# trailing comment\n"
    )

    snippets = discovery._gather_usage_context(str(sample), ["foo"], radius=1)
    assert snippets, "expected at least one usage snippet"
    # radius=1 should include the line before and after the call
    assert any("# note" in s and "# trailing" in s for s in snippets)


def test_discover_includes_type_schemas_when_registered(monkeypatch):
    """Test that discover includes type schemas from registry."""
    clear_type_registry()
    
    # Register a type
    @type_decorator
    @dataclass
    class TestType:
        """Test type for discovery."""
        name: str
        value: int
    
    # Mock the frame iteration to simulate an import
    def mock_iter_frames(fullname):
        # Return a fake frame that looks like an import
        import tempfile
        import os
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        try:
            temp.write("from wishful.static.test import my_function\n")
            temp.flush()
            temp.close()
            yield (temp.name, 1)
        finally:
            os.unlink(temp.name)
    
    monkeypatch.setattr(discovery, "_iter_relevant_frames", mock_iter_frames)
    
    ctx = discover("wishful.static.test")
    
    # Should have the registered type schema
    assert "TestType" in ctx.type_schemas
    assert "Test type for discovery" in ctx.type_schemas["TestType"]
    assert "name: str" in ctx.type_schemas["TestType"]
    
    clear_type_registry()


def test_discover_includes_function_output_types(monkeypatch):
    """Test that discover maps functions to their output types."""
    clear_type_registry()
    
    # Register a type with output_for
    @type_decorator(output_for="my_function")
    @dataclass
    class OutputType:
        """Output type."""
        result: str
    
    # Mock the frame iteration
    def mock_iter_frames(fullname):
        import tempfile
        import os
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        try:
            temp.write("from wishful.static.test import my_function\n")
            temp.flush()
            temp.close()
            yield (temp.name, 1)
        finally:
            os.unlink(temp.name)
    
    monkeypatch.setattr(discovery, "_iter_relevant_frames", mock_iter_frames)
    
    ctx = discover("wishful.static.test")
    
    # Should map the function to its output type
    assert "my_function" in ctx.function_output_types
    assert ctx.function_output_types["my_function"] == "OutputType"
    
    clear_type_registry()


def test_discover_handles_multiple_functions_with_types(monkeypatch):
    """Test that discover correctly maps multiple functions to types."""
    clear_type_registry()
    
    # Register types with different output_for settings
    @type_decorator(output_for=["func1", "func2"])
    @dataclass
    class SharedType:
        """Shared type."""
        data: str
    
    @type_decorator(output_for="func3")
    @dataclass
    class SpecificType:
        """Specific type."""
        value: int
    
    # Mock importing multiple functions
    def mock_iter_frames(fullname):
        import tempfile
        import os
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        try:
            temp.write("from wishful.static.test import func1, func2, func3\n")
            temp.flush()
            temp.close()
            yield (temp.name, 1)
        finally:
            os.unlink(temp.name)
    
    monkeypatch.setattr(discovery, "_iter_relevant_frames", mock_iter_frames)
    
    ctx = discover("wishful.static.test")
    
    # Should have both types
    assert "SharedType" in ctx.type_schemas
    assert "SpecificType" in ctx.type_schemas
    
    # Should map functions correctly
    assert ctx.function_output_types.get("func1") == "SharedType"
    assert ctx.function_output_types.get("func2") == "SharedType"
    assert ctx.function_output_types.get("func3") == "SpecificType"
    
    clear_type_registry()


def test_discover_works_without_registered_types(monkeypatch):
    """Test that discover still works when no types are registered."""
    clear_type_registry()
    
    # Mock the frame iteration
    def mock_iter_frames(fullname):
        import tempfile
        import os
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        try:
            temp.write("from wishful.static.test import some_function\n")
            temp.flush()
            temp.close()
            yield (temp.name, 1)
        finally:
            os.unlink(temp.name)
    
    monkeypatch.setattr(discovery, "_iter_relevant_frames", mock_iter_frames)
    
    ctx = discover("wishful.static.test")
    
    # Should still work, just with empty type info
    assert ctx.type_schemas == {}
    assert ctx.function_output_types == {}
    assert ctx.functions == ["some_function"]

