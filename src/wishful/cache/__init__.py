"""Cache utilities for wishful."""

from .manager import (
    clear_cache,
    delete_cached,
    ensure_cache_dir,
    has_cached,
    inspect_cache,
    module_path,
    read_cached,
    write_cached,
)

__all__ = [
    "read_cached",
    "write_cached",
    "clear_cache",
    "inspect_cache",
    "module_path",
    "ensure_cache_dir",
    "delete_cached",
    "has_cached",
]
