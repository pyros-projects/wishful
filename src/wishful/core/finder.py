from __future__ import annotations

import importlib.abc
import importlib.util
from pathlib import Path

from wishful.core.loader import MagicLoader, MagicPackageLoader


MAGIC_NAMESPACE = "wishful"
STATIC_NAMESPACE = "wishful.static"
DYNAMIC_NAMESPACE = "wishful.dynamic"


class MagicFinder(importlib.abc.MetaPathFinder):
    """Intercept imports for the `wishful.static.*` and `wishful.dynamic.*` namespaces."""

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if not fullname.startswith(MAGIC_NAMESPACE):
            return None

        # Allow internal wishful modules (core, cache, llm, etc.)
        if _is_internal_module(fullname):
            return None

        # Handle root namespace packages
        if fullname == MAGIC_NAMESPACE:
            return importlib.util.spec_from_loader(fullname, MagicPackageLoader(), is_package=True)
        if fullname == STATIC_NAMESPACE:
            return importlib.util.spec_from_loader(fullname, MagicPackageLoader(), is_package=True)
        if fullname == DYNAMIC_NAMESPACE:
            return importlib.util.spec_from_loader(fullname, MagicPackageLoader(), is_package=True)

        # Determine if this is a static or dynamic import
        is_static = fullname.startswith(STATIC_NAMESPACE + ".")
        is_dynamic = fullname.startswith(DYNAMIC_NAMESPACE + ".")

        if is_static:
            return importlib.util.spec_from_loader(
                fullname, MagicLoader(fullname, mode="static"), is_package=False
            )
        elif is_dynamic:
            return importlib.util.spec_from_loader(
                fullname, MagicLoader(fullname, mode="dynamic"), is_package=False
            )

        # Reject direct wishful.* imports that aren't static/dynamic
        return None


def _is_internal_module(fullname: str) -> bool:
    """Check if a module is part of the internal wishful package."""
    parts = fullname.split('.')
    if len(parts) < 2:
        return False
    
    # Skip static/dynamic namespace checks - they're never internal
    if parts[1] in ('static', 'dynamic'):
        return False
    
    # Check if it's a real internal module
    module_file = Path(__file__).parent.parent / parts[1]
    return module_file.exists() or module_file.with_suffix('.py').exists()


def install() -> None:
    """Register the finder if it is not already present."""

    for finder in list(__import__("sys").meta_path):  # type: ignore
        if isinstance(finder, MagicFinder):
            return
    __import__("sys").meta_path.insert(0, MagicFinder())
