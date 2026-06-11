from __future__ import annotations

import asyncio
import os
from typing import Sequence

import litellm

from wishful.config import settings
from wishful.exceptions import WishfulError
from wishful.llm.prompts import build_messages, strip_code_fences
from wishful.logging import logger


class GenerationError(WishfulError, ImportError):
    """Raised when the LLM call fails or returns empty output."""


_EMPTY_CONTENT_MSG = "LLM returned empty content"


def _is_fake_mode() -> bool:
    """Read the fake-LLM flag per call so tests can toggle it without reimport."""
    return os.getenv("WISHFUL_FAKE_LLM", "0") == "1"


def _empty_content_error() -> GenerationError:
    """Build the diagnostic raised after an empty-content response survives retry."""
    return GenerationError(
        f"{settings.model} returned empty content after 2 attempts. "
        f"If this is a reasoning model, raise max_tokens (currently {settings.max_tokens}) "
        f"or set WISHFUL_TEMPERATURE — reasoning models can spend the whole budget "
        f"on hidden tokens and return nothing."
    )


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
    """Call the LLM (or fake stub) to generate module source code (sync version)."""

    if _is_fake_mode():
        return _fake_response(functions)

    for _ in range(2):  # initial attempt + one retry on empty content
        response = _call_llm(
            module, functions, context, type_schemas, function_output_types, mode
        )
        try:
            content = _extract_content(response)
        except GenerationError as exc:
            if str(exc) == _EMPTY_CONTENT_MSG:
                continue
            raise
        code = strip_code_fences(content).strip()
        if code:
            return code
    raise _empty_content_error()


async def agenerate_module_code(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
) -> str:
    """Call the LLM (or fake stub) to generate module source code (async version).
    
    This is the preferred method for explore() and other features that need
    concurrent operations or responsive UI updates.
    """

    if _is_fake_mode():
        # Small delay to simulate async behavior in fake mode
        await asyncio.sleep(0.01)
        return _fake_response(functions)

    for _ in range(2):  # initial attempt + one retry on empty content
        response = await _acall_llm(
            module, functions, context, type_schemas, function_output_types, mode
        )
        try:
            content = _extract_content(response)
        except GenerationError as exc:
            if str(exc) == _EMPTY_CONTENT_MSG:
                continue
            raise
        code = strip_code_fences(content).strip()
        if code:
            return code
    raise _empty_content_error()


def _call_llm(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
):
    """Synchronous LLM call."""
    messages = build_messages(
        module, functions, context, type_schemas, function_output_types, mode
    )
    _log_llm_call(module, mode, functions, context, type_schemas, function_output_types, messages)
    
    try:
        return litellm.completion(
            model=settings.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.request_timeout,
        )
    except Exception as exc:  # pragma: no cover - network path not executed in tests
        raise GenerationError(f"LLM call failed: {exc}") from exc


async def _acall_llm(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
):
    """Asynchronous LLM call using litellm.acompletion()."""
    messages = build_messages(
        module, functions, context, type_schemas, function_output_types, mode
    )
    _log_llm_call(module, mode, functions, context, type_schemas, function_output_types, messages)
    
    try:
        return await litellm.acompletion(
            model=settings.model,
            messages=messages,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.request_timeout,
        )
    except Exception as exc:  # pragma: no cover - network path not executed in tests
        raise GenerationError(f"LLM call failed: {exc}") from exc


def _log_llm_call(
    module: str,
    mode: str | None,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None,
    function_output_types: dict[str, str] | None,
    messages: list,
) -> None:
    """Log LLM call details."""
    # The context preview and prompt bodies can contain the caller's source and
    # secrets, so they are redacted unless log_prompts is explicitly enabled.
    context_len = len(context) if context else 0
    preview = (
        (context[:500] + "…" if context and len(context) > 500 else (context or ""))
        if settings.log_prompts
        else f"<redacted {context_len} chars; set WISHFUL_LOG_PROMPTS=1 to log>"
    )
    logger.debug(
        "LLM call module={} mode={} model={} temp={} max_tokens={} functions={} context_len={} type_schemas={} output_types={} preview={}",
        module,
        mode,
        settings.model,
        settings.temperature,
        settings.max_tokens,
        list(functions),
        context_len,
        list((type_schemas or {}).keys()),
        list((function_output_types or {}).keys()),
        preview,
    )

    if settings.log_prompts:
        prompt_text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        if len(prompt_text) > 4000:
            prompt_text = prompt_text[:4000] + "…"
        logger.debug("LLM prompt for {}:\n{}", module, prompt_text)


def _extract_content(response) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise GenerationError("Unexpected LLM response structure") from exc

    if not content or not content.strip():
        raise GenerationError(_EMPTY_CONTENT_MSG)
    return content
