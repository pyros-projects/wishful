from __future__ import annotations

import ast
import inspect
import linecache
from pathlib import Path
from textwrap import dedent
from typing import Iterable, List, Sequence

from wishful.config import configure, settings
from wishful.types import get_all_type_schemas, get_output_type_for_function


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


def _nested_request(tree: ast.AST, fullname: str) -> str | None:
    """Return the deeper module name when the call site imports below ``fullname``.

    ``import wishful.static.a.b`` (or ``from wishful.static.a.b import c``)
    while loading ``wishful.static.a`` is a nested wish — unsupported.
    """
    prefix = fullname + "."
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(prefix):
                    return alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(prefix):
                return node.module
    return None


def _is_plain_import(fullname: str, tree: ast.AST) -> bool:
    """Return True when the line is an ast.Import of the fullname (not ImportFrom)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _matches_import(alias.name, fullname):
                    return True
    return False


def _matches_import_from(module: str | None, fullname: str) -> bool:
    if not module:
        return False
    return module.startswith("wishful") and fullname.startswith(module)


def _matches_import(name: str, fullname: str) -> bool:
    return name.startswith("wishful") and fullname.startswith(name)


def discover(fullname: str, runtime_context: dict | None = None) -> ImportContext:
    """Attempt to recover requested symbol names and nearby comments.

    `runtime_context` is an optional dict (e.g., function name/args) that will
    be appended to the textual context sent to the LLM for dynamic calls.
    """

    first_frame: tuple[str, int] | None = None

    for filename, lineno in _iter_relevant_frames(fullname):
        if first_frame is None:
            first_frame = (filename, lineno)
        code_line = linecache.getline(filename, lineno).strip()
        if not code_line:
            continue

        tree = _safe_parse_line(code_line)
        if tree is not None:
            # Nested wishes have never worked (generated parents are not
            # packages); fail BEFORE the parent burns an LLM call, with an
            # error that names the problem instead of "X is not a package".
            nested = _nested_request(tree, fullname)
            if nested is not None:
                flat = nested.rsplit(".", 1)[-1]
                namespace = ".".join(fullname.split(".")[:2])
                raise ImportError(
                    f"nested wishful module {nested!r} is not supported: wish "
                    f"names are single-level. Flatten it, e.g. "
                    f"'{namespace}.{flat}'. No code was generated."
                )

        functions = _parse_imported_names(code_line, fullname)
        if not functions:
            continue

        if tree and _is_plain_import(fullname, tree):
            functions = []

        context = _build_context_snippets(filename, lineno, functions)

        if runtime_context:
            context = _append_runtime_context(context, runtime_context)

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

    # Fallback: even if we couldn't parse requested symbols (e.g., module-level
    # imports with later attribute access), still capture nearby context so the
    # LLM gets some hints.
    if first_frame is not None:
        filename, lineno = first_frame
        context = _build_context_snippets(filename, lineno, [])
    else:
        context = None

    if runtime_context:
        context = _append_runtime_context(context, runtime_context)

    type_schemas = get_all_type_schemas()
    return ImportContext(functions=[], context=context, type_schemas=type_schemas)


def _append_runtime_context(context: str | None, runtime_context: dict) -> str:
    def _safe(val):
        text = repr(val)
        return text[:500] + "…" if len(text) > 500 else text

    parts = ["Runtime call context:"]
    for key, val in runtime_context.items():
        parts.append(f"- {key}: {_safe(val)}")

    runtime_block = "\n".join(parts)
    if context:
        return f"{context}\n\n{runtime_block}"
    return runtime_block


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
    radius = settings.context_radius
    snippets = [_gather_context_lines(filename, lineno, radius=radius)]
    snippets += _gather_usage_context(filename, functions, radius=radius)
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
    """Update the context radius used for import discovery.

    Thin wrapper over ``configure(context_radius=...)`` — the radius lives in
    Settings so it is configure/reset/env aware like every other knob.
    """
    configure(context_radius=radius)
