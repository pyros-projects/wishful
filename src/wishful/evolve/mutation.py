"""LLM-based code mutation with history context for AlphaEvolve-style evolution.

This module contains the core AlphaEvolve-inspired component: mutation functions
that receive and use evolutionary history to make informed code improvements.
"""

from typing import Callable, List, Optional
import inspect

from wishful.llm.client import generate_module_code


def mutate_with_llm(
    source: str,
    mutation_prompt: str,
    function_name: str,
    history: List[dict]
) -> str:
    """
    Ask the LLM to create a mutation informed by evolutionary history.

    This is the key AlphaEvolve insight: the LLM doesn't just see the current
    code—it sees what approaches worked and what didn't, enabling it to make
    increasingly informed mutations.

    Args:
        source: The current best source code
        mutation_prompt: User hint about how to mutate
        function_name: Name of the function being evolved
        history: List of previous attempts with scores:
            [{"source": "...", "fitness": 51.0, "failed": False, "error": None}, ...]

    Returns:
        New source code with mutation applied
    """
    context = _build_evolution_context(source, mutation_prompt, function_name, history)

    # Use existing LLM infrastructure
    return generate_module_code(
        module="wishful.evolve._mutation",
        functions=[function_name],
        context=context
    )


def _build_evolution_context(
    source: str,
    mutation_prompt: str,
    function_name: str,
    history: List[dict]
) -> str:
    """
    Build rich context string for LLM mutation.

    The context includes:
    1. The current best implementation
    2. User guidance (mutation_prompt)
    3. Full history of attempts sorted by fitness

    This is THE KEY to AlphaEvolve: giving the LLM enough context to make
    informed mutations rather than random changes.
    """
    parts = [
        "=" * 60,
        "EVOLUTION TASK: Improve this Python function",
        "=" * 60,
        "",
        "CURRENT BEST IMPLEMENTATION:",
        "```python",
        source,
        "```",
        "",
    ]

    # Add history context (the AlphaEvolve secret sauce)
    if history:
        parts.extend([
            "-" * 60,
            "EVOLUTION HISTORY (sorted by fitness, best first):",
            "-" * 60,
            "",
            "Learn from these previous attempts. Higher fitness = better.",
            ""
        ])

        for i, entry in enumerate(history):
            fitness = entry.get("fitness")
            failed = entry.get("failed", False)
            error = entry.get("error")
            variant_source = entry.get("source", "")

            if failed:
                status = f"FAILED: {error}" if error else "FAILED"
                parts.append(f"Attempt {i + 1}: {status}")
            else:
                parts.append(f"Attempt {i + 1}: Fitness = {fitness:.2f}")

            # Include truncated source for context
            source_preview = _truncate_source(variant_source, max_lines=10)
            parts.extend([
                "```python",
                source_preview,
                "```",
                ""
            ])

    # Add user guidance (only if provided)
    if mutation_prompt:
        parts.extend([
            "-" * 60,
            f"USER GUIDANCE: {mutation_prompt}",
            "-" * 60,
            ""
        ])

    # Instructions for the LLM
    parts.extend([
        "YOUR TASK:",
        "1. Analyze what made high-scoring attempts successful",
        "2. Understand why low-scoring attempts performed poorly",
        "3. Create an IMPROVED version that should score higher",
        "4. Keep the same function name and signature",
        "5. Return ONLY the Python code, no explanations",
        "",
    ])

    return "\n".join(parts)


def _truncate_source(source: str, max_lines: int = 10) -> str:
    """
    Truncate source code to max_lines for context.

    Long source code can overflow context windows. This helper ensures
    we include enough to understand the approach without overwhelming
    the LLM's context.
    """
    lines = source.strip().split("\n")
    if len(lines) <= max_lines:
        return source
    return "\n".join(lines[:max_lines]) + f"\n    # ... ({len(lines) - max_lines} more lines)"


def get_function_source(fn: Callable) -> str:
    """
    Get source code of a function.

    Tries multiple strategies:
    1. Check for __wishful_source__ attribute (wishful-generated functions)
    2. Use inspect.getsource() for regular functions

    Args:
        fn: The function to get source code from

    Returns:
        The source code as a string

    Raises:
        ValueError: If source code cannot be obtained
    """
    # First try wishful's attached source
    if hasattr(fn, "__wishful_source__"):
        return fn.__wishful_source__

    # Try inspect
    try:
        return inspect.getsource(fn)
    except (OSError, TypeError):
        pass

    raise ValueError(
        f"Cannot get source code for {fn}. "
        "Function must have __wishful_source__ attribute or be inspectable."
    )
