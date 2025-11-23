"""wishful - Just-in-Time code generation via import hooks."""

from __future__ import annotations

import importlib
import sys
from typing import List

from wishful.cache import manager as cache
from wishful.config import configure, reset_defaults, settings
from wishful.core.discovery import set_context_radius as _set_context_radius
from wishful.core.finder import install as install_finder
from wishful.llm.client import GenerationError
from wishful.safety.validator import SecurityError

# Install on import so `import magic.xyz` is intercepted immediately.
install_finder()

__all__ = [
    "configure",
    "clear_cache",
    "inspect_cache",
    "regenerate",
    "set_context_radius",
    "SecurityError",
    "GenerationError",
]


def clear_cache() -> None:
    """Delete all generated files from the cache directory."""

    cache.clear_cache()
    # Remove any loaded wishful modules so they regenerate on next import.
    for name in list(sys.modules):
        if name.startswith("wishful."):
            sys.modules.pop(name, None)


def inspect_cache() -> List[str]:
    """Return a list of cached module file paths as strings."""

    return [str(p) for p in cache.inspect_cache()]


def regenerate(module_name: str) -> None:
    """Force regeneration of a module on next import."""

    if not module_name.startswith("wishful"):
        module_name = f"wishful.{module_name}"
    cache.delete_cached(module_name)
    sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def set_context_radius(radius: int) -> None:
    """Adjust how many surrounding lines are sent as context to the LLM."""
    _set_context_radius(radius)


__version__ = "0.1.0"
