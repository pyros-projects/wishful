from __future__ import annotations

import ast
from typing import Iterable


class SecurityError(ImportError):
    """Raised when generated code violates safety policy."""


_FORBIDDEN_IMPORTS = {"os", "subprocess", "sys"}
_FORBIDDEN_CALLS = {"eval", "exec"}
_WRITE_MODES = {"w", "a", "+"}


def _parse_source(source: str) -> ast.AST:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise ImportError(f"Generated code has syntax error: {exc}") from exc


def _check_imports(tree: ast.AST) -> None:
    _validate_import_names(list(_iter_import_names(tree)))


def _iter_import_names(tree: ast.AST):
    yield from _import_names(tree)
    yield from _importfrom_names(tree)


def _import_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name


def _importfrom_names(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def _validate_import_names(names: Iterable[str]) -> None:
    for name in names:
        if name.split(".")[0] in _FORBIDDEN_IMPORTS:
            raise SecurityError(f"Forbidden import: {name}")


def _check_calls(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            _check_named_call(node.func.id, node)
        elif isinstance(node.func, ast.Attribute):
            _check_attribute_call(node.func)


def _check_named_call(func_name: str, call: ast.Call) -> None:
    if func_name in _FORBIDDEN_CALLS:
        raise SecurityError(f"Forbidden call: {func_name}()")
    if func_name == "open":
        _validate_open_call(call)


def _check_attribute_call(attr: ast.Attribute) -> None:
    dotted = _resolve_attribute_name(attr)
    if dotted.startswith("os.") or dotted.startswith("subprocess."):
        raise SecurityError(f"Forbidden call: {dotted}()")


def _resolve_attribute_name(attr: ast.Attribute) -> str:
    parts = []
    current: ast.AST | None = attr
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _validate_open_call(call: ast.Call) -> None:
    mode_arg = _extract_open_mode(call)
    if mode_arg and any(ch in mode_arg for ch in _WRITE_MODES):
        raise SecurityError("open() in write/append mode is blocked")


def _extract_open_mode(call: ast.Call) -> str | None:
    positional = _extract_positional_mode(call)
    if positional is not None:
        return positional
    return _extract_keyword_mode(call)


def _extract_positional_mode(call: ast.Call) -> str | None:
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        return str(call.args[1].value)
    return None


def _extract_keyword_mode(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def _check_forbidden_builtins(tree: ast.AST) -> None:
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    forbidden = names & _FORBIDDEN_CALLS
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise SecurityError(f"Forbidden builtins present: {joined}")


def validate_code(source: str, *, allow_unsafe: bool = False) -> None:
    """Perform light-weight static checks on generated code.

    The goal is to block obviously dangerous constructs without being overly
    restrictive. Users can opt-out by setting `allow_unsafe=True`.
    """

    if allow_unsafe:
        return

    tree = _parse_source(source)
    _check_imports(tree)
    _check_calls(tree)
    _check_forbidden_builtins(tree)
