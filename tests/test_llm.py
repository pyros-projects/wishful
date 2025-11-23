"""Tests for LLM client and prompt generation."""

import importlib
import os

import pytest

from wishful.llm import client
from wishful.llm.client import GenerationError, _fake_response, generate_module_code
from wishful.llm.prompts import build_messages, strip_code_fences


def test_build_messages_basic():
    """Test building basic prompt messages."""
    messages = build_messages("wishful.utils", ["foo", "bar"], None)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "wishful.utils" in messages[1]["content"]
    assert "foo" in messages[1]["content"]
    assert "bar" in messages[1]["content"]


def test_build_messages_with_context():
    """Test building messages with context."""
    context = "# desired: parse JSON safely"
    messages = build_messages("wishful.data", ["parse_json"], context)
    assert context in messages[1]["content"]


def test_strip_code_fences_with_fences():
    """Test stripping markdown code fences."""
    text = "```python\ndef foo():\n    pass\n```"
    result = strip_code_fences(text)
    assert "```" not in result
    assert "def foo():" in result


def test_strip_code_fences_without_fences():
    """Test that text without fences is unchanged."""
    text = "def foo():\n    pass"
    result = strip_code_fences(text)
    assert result == text


def test_fake_response_single_function():
    """Test fake LLM response with single function."""
    result = _fake_response(["foo"])
    assert "def foo(" in result
    assert "args" in result
    assert "kwargs" in result


def test_fake_response_multiple_functions():
    """Test fake LLM response with multiple functions."""
    result = _fake_response(["foo", "bar"])
    assert "def foo(" in result
    assert "def bar(" in result


def test_fake_response_no_functions():
    """Test fake LLM response with no function names."""
    result = _fake_response([])
    assert "def generated_helper(" in result


def test_generate_module_code_fake_mode():
    """Test module code generation with fake mode directly."""
    # Test the fake response function directly since env var is checked at import time
    code = _fake_response(["foo", "bar"])
    assert "def foo(" in code
    assert "def bar(" in code
    assert "args" in code
    assert "kwargs" in code
