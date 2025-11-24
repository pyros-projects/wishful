from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from wishful.config import settings


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
        return path.read_text()
    return None


def write_cached(fullname: str, source: str) -> Path:
    path = module_path(fullname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


def write_dynamic_snapshot(fullname: str, source: str) -> Path:
    path = dynamic_snapshot_path(fullname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
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
