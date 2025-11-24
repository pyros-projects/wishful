from __future__ import annotations

import ast
import inspect
import linecache
import os
from pathlib import Path
from textwrap import dedent
from typing import Iterable, List, Sequence

from wishful.types import get_all_type_schemas, get_output_type_for_function

# Default radius for surrounding-context capture; configurable via env + setter.
_context_radius = int(os.getenv("WISHFUL_CONTEXT_RADIUS", "3"))


class ImportContext:
    def __init__(
        self,
        functions: Sequence[str],
        context: str | None,
        type_schemas: dict[str, str] | None = None,
        function_output_types: dict[str, str] | None = None,
    ):
        self.functions = list(functions)
        self.context = context
        self.type_schemas = type_schemas or {}
        self.function_output_types = function_output_types or {}

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"ImportContext(functions={self.functions}, "
            f"context={self.context!r}, "
            f"type_schemas={list(self.type_schemas.keys())}, "
            f"function_output_types={self.function_output_types})"
        )


def _gather_context_lines(filename: str, lineno: int, radius: int = 2) -> str:
    lines = linecache.getlines(filename)
    if not lines:
        return ""
    start = max(lineno - radius, 1) - 1
    end = min(lineno + radius, len(lines))
    snippet = lines[start:end]
    return "".join(snippet).strip()


def _parse_imported_names(source_line: str, fullname: str) -> List[str]:
    tree = _safe_parse_line(source_line)
    if tree is None:
        return []

    names: list[str] = []
    names.extend(_names_from_import_from(tree, fullname))
    names.extend(_names_from_import(tree, fullname))
    return names


def _safe_parse_line(source_line: str) -> ast.AST | None:
    try:
        return ast.parse(dedent(source_line))
    except SyntaxError:
        return None


def _names_from_import_from(tree: ast.AST, fullname: str) -> list[str]:
    return [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if _matches_import_from(node.module, fullname)
    ]


def _names_from_import(tree: ast.AST, fullname: str) -> list[str]:
    matches: list[str] = []
    for node in (n for n in ast.walk(tree) if isinstance(n, ast.Import)):
        matches.extend(_alias_targets(node.names, fullname))
    return matches


def _alias_targets(aliases: Sequence[ast.alias], fullname: str) -> list[str]:
    return [
        alias.asname or alias.name.split(".")[-1]
        for alias in aliases
        if _matches_import(alias.name, fullname)
    ]


def _matches_import_from(module: str | None, fullname: str) -> bool:
    return bool(module) and module.startswith("wishful") and fullname.startswith(module)


def _matches_import(name: str, fullname: str) -> bool:
    return name.startswith("wishful") and fullname.startswith(name)


def discover(fullname: str, runtime_context: dict | None = None) -> ImportContext:
    """Attempt to recover requested symbol names and nearby comments."""

    for filename, lineno in _iter_relevant_frames(fullname):
        code_line = linecache.getline(filename, lineno).strip()
        if not code_line:
            continue

        functions = _parse_imported_names(code_line, fullname)
        if not functions:
            continue

        context = _build_context_snippets(filename, lineno, functions)
        
        # Fetch type information from registry
        type_schemas = get_all_type_schemas()
        function_output_types = {}
        for func in functions:
            output_type = get_output_type_for_function(func)
            if output_type:
                function_output_types[func] = output_type
        
        return ImportContext(
            functions=functions,
            context=context,
            type_schemas=type_schemas,
            function_output_types=function_output_types,
        )

    return ImportContext(functions=[], context=None)


def _iter_relevant_frames(fullname: str) -> Iterable[tuple[str, int]]:
    frame = inspect.currentframe()
    if frame:
        frame = frame.f_back

    while frame:
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        if _is_user_frame(filename):
            yield filename, lineno

        frame = frame.f_back


def _is_user_frame(filename: str) -> bool:
    if filename.startswith("<"):
        return False
    normalized = filename.replace("\\", "/")
    return not ("/src/wishful/" in normalized and "/tests/" not in normalized)


def _gather_usage_context(filename: str, functions: Sequence[str], radius: int) -> list[str]:
    """Collect context snippets around call sites of the requested functions."""
    if not functions:
        return []

    tree = _parse_file_safe(filename)
    if tree is None:
        return []

    linenos = _call_site_lines(tree, set(functions))
    return _snippets_from_lines(filename, linenos, radius)


def _call_site_lines(tree: ast.AST, targets: set[str]) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        if isinstance(node.func, ast.Name)
        if node.func.id in targets
    ]


def _snippets_from_lines(filename: str, linenos: Sequence[int], radius: int) -> list[str]:
    snippets = [_gather_context_lines(filename, lineno, radius=radius) for lineno in linenos]
    return _dedupe([s for s in snippets if s])


def _parse_file_safe(filename: str) -> ast.AST | None:
    try:
        return ast.parse(Path(filename).read_text())
    except (OSError, SyntaxError):
        return None


def _build_context_snippets(filename: str, lineno: int, functions: Sequence[str]) -> str | None:
    snippets = [_gather_context_lines(filename, lineno, radius=_context_radius)]
    snippets += _gather_usage_context(filename, functions, radius=_context_radius)
    combined = "\n\n".join(part for part in snippets if part)
    return combined or None


def _dedupe(items: Sequence[str]) -> list[str]:
    seen = set()
    unique: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def set_context_radius(radius: int) -> None:
    """Update the global context radius used for import discovery."""
    global _context_radius
    if radius < 0:
        raise ValueError("context radius must be non-negative")
    _context_radius = radius
