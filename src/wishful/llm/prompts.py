from __future__ import annotations

from textwrap import dedent
from typing import Iterable, List, Sequence


def build_messages(module: str, functions: Sequence[str], context: str | None) -> List[dict]:
    func_list = ", ".join(functions) if functions else "" "module-level helpers" ""
    user_parts = [f"Module: {module}"]
    if functions:
        user_parts.append(f"Functions to implement: {', '.join(functions)}")
    if context:
        user_parts.append("Context:\n" + context.strip())

    user_prompt = "\n\n".join(user_parts)

    system = dedent(
        """
        You are a Python code generator. Output ONLY executable Python code.
        - Do not wrap code in markdown fences.
        - Only use the Python standard library.
        - Prefer simple, readable implementations.
        - Avoid network, filesystem writes, subprocess, or shell execution.
        - Include docstrings and type hints where helpful.
        """
    ).strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def strip_code_fences(text: str) -> str:
    """Remove Markdown code fences if present."""

    if "```" not in text:
        return text

    parts = text.split("```")
    if len(parts) >= 3:
        # content between first and second fence
        return parts[1].strip('\n') if parts[0].strip() == "" else parts[1]+parts[2]
    return text
