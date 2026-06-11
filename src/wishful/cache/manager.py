from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

from wishful.config import settings


def _atomic_write(path: Path, source: str) -> None:
    """Write ``source`` to ``path`` atomically (temp file + os.replace).

    A crash or concurrent writer can never leave a torn .py file behind: readers
    see either the old contents or the complete new ones, never a partial write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(source)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def module_path(fullname: str) -> Path:
    # Strip leading namespace "wishful" (and static/dynamic) and map dots to directories.
    parts = fullname.split(".")
    if parts[0] == "wishful":
        parts = parts[1:]
    # Also strip 'static' or 'dynamic' if present
    if parts and parts[0] in ("static", "dynamic"):
        parts = parts[1:]
    relative = Path(*parts) if parts else Path("__init__")
    return settings.cache_dir / relative.with_suffix(".py")


def dynamic_snapshot_path(fullname: str) -> Path:
    """Path for storing dynamic-generation snapshots without affecting cache."""
    parts = fullname.split(".")
    if parts[0] == "wishful":
        parts = parts[1:]
    if parts and parts[0] in ("static", "dynamic"):
        parts = parts[1:]
    relative = Path(*parts) if parts else Path("__init__")
    return settings.cache_dir / "_dynamic" / relative.with_suffix(".py")


def ensure_cache_dir() -> Path:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return settings.cache_dir


def read_cached(fullname: str) -> Optional[str]:
    path = module_path(fullname)
    if path.exists():
        text = path.read_text()
        # An empty (e.g. torn) cache file is a miss, not a valid empty module.
        if not text.strip():
            return None
        return text
    return None


def write_cached(fullname: str, source: str) -> Path:
    path = module_path(fullname)
    _atomic_write(path, source)
    return path


def write_dynamic_snapshot(fullname: str, source: str) -> Path:
    path = dynamic_snapshot_path(fullname)
    _atomic_write(path, source)
    return path


def delete_cached(fullname: str) -> None:
    path = module_path(fullname)
    if path.exists():
        path.unlink()


def clear_cache() -> None:
    if settings.cache_dir.exists():
        shutil.rmtree(settings.cache_dir)


def inspect_cache() -> List[Path]:
    if not settings.cache_dir.exists():
        return []
    return sorted(settings.cache_dir.rglob("*.py"))


def has_cached(fullname: str) -> bool:
    return module_path(fullname).exists()
