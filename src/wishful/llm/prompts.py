from __future__ import annotations

from typing import List, Sequence

from wishful.config import settings


def build_messages(
    module: str,
    functions: Sequence[str],
    context: str | None,
    type_schemas: dict[str, str] | None = None,
    function_output_types: dict[str, str] | None = None,
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

    user_prompt = "\n\n".join(user_parts)

    return [
        {"role": "system", "content": settings.system_prompt},
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
