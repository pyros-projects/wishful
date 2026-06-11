from __future__ import annotations

import ast
from typing import Iterable


class SecurityError(ImportError):
    """Raised when generated code violates safety policy."""


# Module imports that are never allowed in generated code. importlib/builtins/
# ctypes are included because they are the obvious escape hatches around the
# os/subprocess/sys block.
_FORBIDDEN_IMPORTS = {"os", "subprocess", "sys", "importlib", "builtins", "ctypes"}

# Bare-name calls that are never allowed (direct or via the __import__ gadget).
_FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}

# Bare-name *references* (load context) that signal a gadget chain even when not
# called directly, e.g. ``f = __import__`` or ``b = __builtins__``.
_FORBIDDEN_NAMES = {"eval", "exec", "compile", "__import__", "__builtins__"}

# Attribute-call bases that, when *unbound* (not a local variable), can only
# resolve through injected globals — block those.
_UNBOUND_ATTR_BASES = {"os", "subprocess", "sys", "importlib", "ctypes", "builtins"}

# String literals that must not be fed to getattr() as an attribute name.
_FORBIDDEN_ATTR_STRINGS = {"eval", "exec", "compile", "__import__", "__builtins__", "system", "popen"}

_WRITE_MODES = {"w", "a", "+", "x"}


def _parse_source(source: str) -> ast.AST:
    # Let SyntaxError propagate as SyntaxError so callers can distinguish a
    # malformed generation (retryable) from a policy violation (SecurityError).
    # The previous ImportError wrapper made the loader's regenerate-once retry
    # unreachable whenever safety was on.
    return ast.parse(source)


def _collect_bound_names(tree: ast.AST) -> set[str]:
    """Names bound somewhere in the module (assignments, params, loops, etc.).

    A base like ``os`` that is locally bound (``os = platform.system()``) is a
    user variable, not the os module, so attribute calls on it are not flagged.
    """
    bound: set[str] = set()

    def _add_target(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            bound.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                _add_target(elt)
        elif isinstance(target, ast.Starred):
            _add_target(target.value)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign,)):
            for target in node.targets:
                _add_target(target)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            _add_target(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            _add_target(node.target)
        elif isinstance(node, ast.comprehension):
            _add_target(node.target)
        elif isinstance(node, ast.withitem):
            if node.optional_vars is not None:
                _add_target(node.optional_vars)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            args = getattr(node, "args", None)
            if args is not None:
                for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                    bound.add(arg.arg)
                if args.vararg:
                    bound.add(args.vararg.arg)
                if args.kwarg:
                    bound.add(args.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                bound.add(arg.arg)
            if args.vararg:
                bound.add(args.vararg.arg)
            if args.kwarg:
                bound.add(args.kwarg.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


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


def _check_calls(tree: ast.AST, bound_names: set[str]) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            _check_named_call(node.func.id, node)
        elif isinstance(node.func, ast.Attribute):
            _check_attribute_call(node.func, bound_names)


def _check_named_call(func_name: str, call: ast.Call) -> None:
    if func_name in _FORBIDDEN_CALLS:
        raise SecurityError(f"Forbidden call: {func_name}()")
    if func_name == "open":
        _validate_open_call(call)
    if func_name == "getattr":
        _check_getattr_call(call)


def _check_getattr_call(call: ast.Call) -> None:
    if call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == "__builtins__":
        raise SecurityError("getattr() on __builtins__ is blocked")
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        if str(call.args[1].value) in _FORBIDDEN_ATTR_STRINGS:
            raise SecurityError(f"getattr() for forbidden attribute '{call.args[1].value}'")


def _check_attribute_call(attr: ast.Attribute, bound_names: set[str]) -> None:
    base = _attribute_base(attr)
    if base is not None and base in _UNBOUND_ATTR_BASES and base not in bound_names:
        raise SecurityError(f"Forbidden call on unbound '{base}'")


def _attribute_base(attr: ast.Attribute) -> str | None:
    current: ast.AST | None = attr
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _check_subscripts(tree: ast.AST) -> None:
    """Block __builtins__[...] and globals()/vars()[...] gadget access."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id == "__builtins__":
            raise SecurityError("Subscripting __builtins__ is blocked")
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id in {"globals", "vars"}:
                raise SecurityError(f"Subscripting {value.func.id}() is blocked")


def _validate_open_call(call: ast.Call) -> None:
    mode_node = _open_mode_node(call)
    if mode_node is None:
        return  # defaults to read mode
    if not isinstance(mode_node, ast.Constant):
        raise SecurityError("open() with a non-literal mode is blocked")
    mode = str(mode_node.value)
    if any(ch in mode for ch in _WRITE_MODES):
        raise SecurityError("open() in write/append mode is blocked")


def _open_mode_node(call: ast.Call) -> ast.AST | None:
    if len(call.args) > 1:
        return call.args[1]
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value
    return None


def _check_forbidden_names(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in _FORBIDDEN_NAMES:
                raise SecurityError(f"Forbidden builtin reference: {node.id}")


def validate_code(source: str, *, allow_unsafe: bool = False) -> None:
    """Perform light-weight static checks on generated code.

    This is defense-in-depth, NOT a sandbox. It blocks the obvious dangerous
    constructs (forbidden imports/builtins, exec gadgets, write-mode file I/O) so
    a careless generation is caught, but AST scanning cannot stop a determined
    attacker — aliased or computed access slips through. Generated code still
    executes in-process; only an out-of-process sandbox makes that truly safe.
    Users can opt out entirely with ``allow_unsafe=True``.
    """

    if allow_unsafe:
        return

    tree = _parse_source(source)
    bound_names = _collect_bound_names(tree)
    _check_imports(tree)
    _check_calls(tree, bound_names)
    _check_subscripts(tree)
    _check_forbidden_names(tree)
