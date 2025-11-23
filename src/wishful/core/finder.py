from __future__ import annotations

import importlib.abc
import importlib.util
import sys
from pathlib import Path
from typing import Optional

from wishful.core.loader import MagicLoader, MagicPackageLoader


MAGIC_NAMESPACE = "wishful"


class MagicFinder(importlib.abc.MetaPathFinder):
    """Intercept imports for the `wishful.*` namespace."""

    def find_spec(self, fullname: str, path, target=None):
        if not fullname.startswith(MAGIC_NAMESPACE):
            return None
        
        # Check if this module actually exists on disk as part of our package
        # If it does, let the default import mechanism handle it
        parts = fullname.split('.')
        if len(parts) >= 2:
            # Check for our internal package modules
            module_file = Path(__file__).parent.parent / parts[1]
            if module_file.exists() or (module_file.with_suffix('.py')).exists():
                return None

        if fullname == MAGIC_NAMESPACE:
            return importlib.util.spec_from_loader(fullname, MagicPackageLoader(), is_package=True)

        loader = MagicLoader(fullname)
        return importlib.util.spec_from_loader(fullname, loader, is_package=False)


def install() -> None:
    """Register the finder if it is not already present."""

    for finder in list(__import__("sys").meta_path):  # type: ignore
        if isinstance(finder, MagicFinder):
            return
    __import__("sys").meta_path.insert(0, MagicFinder())
