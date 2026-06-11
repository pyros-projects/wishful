from __future__ import annotations

import re
from typing import List, Sequence

from wishful.config import settings

# A fenced block: an opening fence with an optional info string (``python``), a
# newline, then the body captured non-greedily up to the closing fence.
_FENCE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def build_messages(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
    mode: str | None = None,
) -> List[dict]:
    user_parts = [f"Module: {module}"]

    # Include type schemas if available
    if type_schemas:
        user_parts.append(
            "Type definitions to include in the module:\n"
            "(Copy these type definitions directly into the generated code. "
            "Do NOT import them from other modules.)\n"
        )
        for type_name, schema in type_schemas.items():
            user_parts.append(f"\n{schema}\n")

    # Include function signatures with output types
    if functions:
        if function_output_types:
            func_list = []
            for func in functions:
                if func in function_output_types:
                    output_type = function_output_types[func]
                    func_list.append(f"{func}(...) -> {output_type}")
                else:
                    func_list.append(func)
            user_parts.append(
                "Functions to implement:\n" + "\n".join(f"- {f}" for f in func_list)
            )
        else:
            user_parts.append(f"Functions to implement: {', '.join(functions)}")

    if context:
        user_parts.append("Context:\n" + context.strip())

    if mode == "dynamic":
        user_parts.append(
            "Dynamic mode guidance:\n"
            "- Treat the call-site context as one-off. Return a single, fully baked result.\n"
            "- Do NOT build strings with templates, f-strings, or .format; write the final prose directly.\n"
            "- Use contextual values (like settings, style, length hints) naturally in the narrative instead of inserting them verbatim at the start.\n"
            "- Keep the function signature, but it's fine if the body ignores parameters after using them as creative guidance."
        )

    user_prompt = "\n\n".join(user_parts)

    return [
        {"role": "system", "content": settings.system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def strip_code_fences(text: str) -> str:
    """Return the code inside Markdown fences, dropping the language info string.

    When the response contains one or more fenced blocks, only the fenced content
    is returned (blocks joined by a blank line); surrounding prose and the opening
    fence's language tag (e.g. ``python``) are stripped. Fence-free responses are
    returned unchanged. This is deliberate: a naive split left the ``python`` tag
    as the first source line, which parsed as a bare name and crashed at exec.
    """

    if "```" not in text:
        return text

    blocks = _FENCE_BLOCK.findall(text)
    if blocks:
        return "\n\n".join(block.rstrip("\n") for block in blocks).strip()

    # A stray opening fence with no matching close: drop the fence line (and its
    # language tag) plus any remaining backticks, keep whatever code is left.
    without_open = re.sub(r"```[^\n]*\n?", "", text, count=1)
    return without_open.replace("```", "").strip()
