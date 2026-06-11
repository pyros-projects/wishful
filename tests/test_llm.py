"""Tests for LLM client and prompt generation."""

import asyncio

import pytest

from wishful.llm import client as llm_client
from wishful.llm.client import (
    _EMPTY_CONTENT_MSG,
    GenerationError,
    _extract_content,
    _fake_response,
    _is_fake_mode,
    agenerate_module_code,
    generate_module_code,
)
from wishful.llm.prompts import build_messages, strip_code_fences
from wishful.config import configure, reset_defaults


def _resp(content):
    return {"choices": [{"message": {"content": content}}]}


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


def test_build_messages_custom_system_prompt():
    """System prompt should come from settings/configure."""
    custom = "Custom system prompt for tests."
    configure(system_prompt=custom)
    messages = build_messages("wishful.data", ["parse_json"], None)
    assert messages[0]["content"] == custom
    reset_defaults()


def test_build_messages_with_type_schemas():
    """Test building messages with type schemas."""
    type_schemas = {
        "UserProfile": "class UserProfile(BaseModel):\n    name: str\n    email: str"
    }
    messages = build_messages("wishful.users", ["create_user"], None, type_schemas=type_schemas)
    assert "UserProfile" in messages[1]["content"]
    assert "BaseModel" in messages[1]["content"]
    assert "Type definitions to include" in messages[1]["content"]
    assert "Do NOT import them" in messages[1]["content"]


def test_build_messages_with_function_output_types():
    """Test building messages with function output types."""
    function_output_types = {"create_user": "UserProfile"}
    messages = build_messages("wishful.users", ["create_user"], None, function_output_types=function_output_types)
    assert "create_user(...) -> UserProfile" in messages[1]["content"]


def test_build_messages_with_both_types_and_outputs():
    """Test building messages with both type schemas and output types."""
    type_schemas = {
        "UserProfile": "class UserProfile(BaseModel):\n    name: str"
    }
    function_output_types = {"create_user": "UserProfile"}
    messages = build_messages(
        "wishful.users", 
        ["create_user"], 
        None, 
        type_schemas=type_schemas,
        function_output_types=function_output_types
    )
    assert "UserProfile" in messages[1]["content"]
    assert "create_user(...) -> UserProfile" in messages[1]["content"]


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


# --- U3: fence stripping ----------------------------------------------------


def test_strip_fences_drops_python_language_tag():
    """The standard ```python response must not leave 'python' as a source line."""
    result = strip_code_fences("```python\ndef f():\n    return 1\n```")
    assert result == "def f():\n    return 1"
    assert not result.startswith("python")
    # And it must actually compile (the original bug exec'd 'python\n...').
    compile(result, "<test>", "exec")


def test_strip_fences_bare_fence():
    result = strip_code_fences("```\ndef f():\n    return 1\n```")
    assert result == "def f():\n    return 1"


def test_strip_fences_prose_before_and_after():
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nHope this helps!"
    result = strip_code_fences(text)
    assert result == "def f():\n    return 1"
    assert "Hope this helps" not in result
    assert "Here you go" not in result


def test_strip_fences_multiple_blocks_joined():
    text = "```python\nimport re\n```\nand\n```python\ndef f():\n    return 1\n```"
    result = strip_code_fences(text)
    assert result == "import re\n\ndef f():\n    return 1"
    compile(result, "<test>", "exec")


def test_strip_fences_empty_block_returns_empty():
    assert strip_code_fences("```python\n```") == ""


def test_strip_fences_windows_line_endings():
    result = strip_code_fences("```python\r\ndef f():\r\n    return 1\r\n```")
    assert "python" not in result
    assert "def f():" in result


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


# --- U2: client resilience ---------------------------------------------------


def test_fake_mode_reads_env_per_call(monkeypatch):
    """_is_fake_mode reads the env each call so tests can toggle without reimport."""
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "1")
    assert _is_fake_mode() is True
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "0")
    assert _is_fake_mode() is False


def test_extract_content_normal():
    assert _extract_content(_resp("def f(): pass")) == "def f(): pass"


def test_extract_content_empty_raises_canonical_message():
    with pytest.raises(GenerationError) as exc:
        _extract_content(_resp(""))
    assert str(exc.value) == _EMPTY_CONTENT_MSG


def test_extract_content_malformed_response_raises():
    with pytest.raises(GenerationError, match="Unexpected LLM response structure"):
        _extract_content({"nonsense": True})


def test_request_timeout_passed_to_litellm(monkeypatch):
    """Both the timeout kwarg and the configured value reach litellm.completion."""
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "0")
    configure(request_timeout=42.0)
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _resp("def f(): pass")

    monkeypatch.setattr(llm_client.litellm, "completion", fake_completion)
    code = generate_module_code("wishful.static.x", ["f"], None)
    assert code == "def f(): pass"
    assert captured["timeout"] == 42.0
    reset_defaults()


def test_empty_content_retries_once_then_raises_diagnostic(monkeypatch):
    """Two empty responses -> exactly 2 calls -> GenerationError naming the model."""
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "0")
    configure(model="openai/gpt-5.5")
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        return _resp("")

    monkeypatch.setattr(llm_client.litellm, "completion", fake_completion)
    with pytest.raises(GenerationError) as exc:
        generate_module_code("wishful.static.x", ["f"], None)
    assert calls["n"] == 2
    assert "openai/gpt-5.5" in str(exc.value)
    reset_defaults()


def test_empty_then_content_succeeds_on_retry(monkeypatch):
    """First empty, second valid -> success with exactly 2 calls."""
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "0")
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        return _resp("" if calls["n"] == 1 else "def f(): pass")

    monkeypatch.setattr(llm_client.litellm, "completion", fake_completion)
    code = generate_module_code("wishful.static.x", ["f"], None)
    assert code == "def f(): pass"
    assert calls["n"] == 2


def test_async_empty_content_retries_once_then_raises(monkeypatch):
    """Async path mirrors sync: retry-once on empty, then diagnostic error."""
    monkeypatch.setenv("WISHFUL_FAKE_LLM", "0")
    calls = {"n": 0}

    async def fake_acompletion(**kwargs):
        calls["n"] += 1
        return _resp("")

    monkeypatch.setattr(llm_client.litellm, "acompletion", fake_acompletion)
    with pytest.raises(GenerationError):
        asyncio.run(agenerate_module_code("wishful.static.x", ["f"], None))
    assert calls["n"] == 2
