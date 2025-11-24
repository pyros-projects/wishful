from __future__ import annotations

import importlib.abc
import importlib.util
from pathlib import Path

from wishful.core.loader import MagicLoader, MagicPackageLoader


MAGIC_NAMESPACE = "wishful"


class MagicFinder(importlib.abc.MetaPathFinder):
    """Intercept imports for the `wishful.*` namespace."""

    def find_spec(self, fullname: str, path, target=None):  # type: ignore[override]
        if not fullname.startswith(MAGIC_NAMESPACE):
            return None

        if _is_internal_module(fullname):
            return None

        if fullname == MAGIC_NAMESPACE:
            return importlib.util.spec_from_loader(fullname, MagicPackageLoader(), is_package=True)

        return importlib.util.spec_from_loader(fullname, MagicLoader(fullname), is_package=False)


def _is_internal_module(fullname: str) -> bool:
    parts = fullname.split('.')
    if len(parts) < 2:
        return False
    module_file = Path(__file__).parent.parent / parts[1]
    return module_file.exists() or module_file.with_suffix('.py').exists()


def install() -> None:
    """Register the finder if it is not already present."""

    for finder in list(__import__("sys").meta_path):  # type: ignore
        if isinstance(finder, MagicFinder):
            return
    __import__("sys").meta_path.insert(0, MagicFinder())
