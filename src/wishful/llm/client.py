from __future__ import annotations

import os
from typing import Sequence

import litellm

from wishful.config import settings
from wishful.llm.prompts import build_messages, strip_code_fences


class GenerationError(ImportError):
    """Raised when the LLM call fails or returns empty output."""


_FAKE_MODE = os.getenv("WISHFUL_FAKE_LLM", "0") == "1"


def _fake_response(functions: Sequence[str]) -> str:
    body = []
    for name in functions or ("generated_helper",):
        body.append(
            f"def {name}(*args, **kwargs):\n    \"\"\"Auto-generated placeholder. Replace with real logic.\"\"\"\n    return {{'args': args, 'kwargs': kwargs}}\n"
        )
    return "\n\n".join(body)


def generate_module_code(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
) -> str:
    """Call the LLM (or fake stub) to generate module source code."""

    if _FAKE_MODE:
        return _fake_response(functions)

    response = _call_llm(
        module, functions, context, type_schemas, function_output_types, mode
    )
    content = _extract_content(response)
    return strip_code_fences(content).strip()


def _call_llm(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
):
    messages = build_messages(
        module, functions, context, type_schemas, function_output_types, mode
    )
    try:
        return litellm.completion(
            model=settings.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    except Exception as exc:  # pragma: no cover - network path not executed in tests
        raise GenerationError(f"LLM call failed: {exc}") from exc


def _extract_content(response) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except Exception as exc:  # pragma: no cover
        raise GenerationError("Unexpected LLM response structure") from exc

    if not content or not content.strip():
        raise GenerationError("LLM returned empty content")
    return content
