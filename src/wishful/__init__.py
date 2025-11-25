"""wishful - Just-in-Time code generation via import hooks."""

from __future__ import annotations

import importlib
import sys
from typing import List

from wishful.cache import manager as cache
from wishful.config import configure, reset_defaults, settings
from wishful.core.discovery import set_context_radius as _set_context_radius
from wishful.core.finder import install as install_finder
from wishful.explore import ExplorationError, explore
from wishful.llm.client import GenerationError
from wishful.safety.validator import SecurityError
from wishful.types import type as type_decorator

# Install on import so `import magic.xyz` is intercepted immediately.
install_finder()

__all__ = [
    "configure",
    "clear_cache",
    "inspect_cache",
    "regenerate",
    "reimport",
    "set_context_radius",
    "settings",
    "reset_defaults",
    "SecurityError",
    "GenerationError",
    "ExplorationError",
    "explore",
    "type",
]

# Alias for cleaner API
type = type_decorator


def clear_cache() -> None:
    """Delete all generated files from the cache directory."""

    cache.clear_cache()
    # Remove generated namespaces so they regenerate on next import.
    for name in list(sys.modules):
        if name.startswith("wishful.static") or name.startswith("wishful.dynamic"):
            sys.modules.pop(name, None)
    # Keep root wishful module to retain settings/logging; re-importer can handle children.


def inspect_cache() -> List[str]:
    """Return a list of cached module file paths as strings."""

    return [str(p) for p in cache.inspect_cache()]


def regenerate(module_name: str) -> None:
    """Force regeneration of a module on next import.
    
    Accepts module names with or without the wishful.static prefix.
    Example: regenerate('users') or regenerate('wishful.static.users')
    """
    # Ensure it has the wishful prefix
    if not module_name.startswith("wishful"):
        # Default to static namespace for backward compatibility
        module_name = f"wishful.static.{module_name}"
    
    cache.delete_cached(module_name)
    sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def set_context_radius(radius: int) -> None:
    """Adjust how many surrounding lines are sent as context to the LLM."""
    _set_context_radius(radius)


def reimport(module_path: str):
    """Force a fresh import by clearing the module from cache.
    
    This is especially useful for wishful.dynamic.* imports in loops,
    where you want the LLM to regenerate with fresh context on each iteration.
    
    Args:
        module_path: The full module path (e.g., 'wishful.dynamic.story')
    
    Returns:
        The freshly imported module
    
    Example:
        >>> story = wishful.reimport('wishful.dynamic.story')
        >>> next_line = story.cosmic_horror_next_sentence(current_text)
    """
    # Clear from Python's module cache
    sys.modules.pop(module_path, None)
    
    # Import fresh (this triggers wishful's import hook if it's a wishful.* module)
    return importlib.import_module(module_path)


__version__ = "0.1.0"
