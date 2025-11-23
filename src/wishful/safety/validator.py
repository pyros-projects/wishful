from __future__ import annotations

import ast
from typing import Iterable, Set


class SecurityError(ImportError):
    """Raised when generated code violates safety policy."""


_FORBIDDEN_IMPORTS = {"os", "subprocess", "sys"}
_FORBIDDEN_CALLS = {"eval", "exec"}
_FORBIDDEN_FUNCTIONS = {"open"}


def _collect_names(node: ast.AST) -> Set[str]:
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
    return names


def validate_code(source: str, *, allow_unsafe: bool = False) -> None:
    """Perform light-weight static checks on generated code.

    The goal is to block obviously dangerous constructs without being overly
    restrictive. Users can opt-out by setting `allow_unsafe=True`.
    """

    if allow_unsafe:
        return

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # surface errors early
        raise ImportError(f"Generated code has syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _FORBIDDEN_IMPORTS:
                    raise SecurityError(f"Forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
                raise SecurityError(f"Forbidden import: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in _FORBIDDEN_CALLS:
                    raise SecurityError(f"Forbidden call: {func_name}()")
                if func_name == "open":
                    # Evaluate mode argument safety (write modes contain 'w', 'a', '+').
                    if node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                            mode_arg = None
                            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                                mode_arg = node.args[1].value
                            elif node.keywords:
                                for kw in node.keywords:
                                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                                        mode_arg = kw.value.value
                            if mode_arg and any(ch in str(mode_arg) for ch in "wa+"):
                                raise SecurityError("open() in write/append mode is blocked")
            if isinstance(node.func, ast.Attribute):
                # Block os.system / subprocess.call etc even if imported under alias.
                attr_chain = []
                current = node.func
                while isinstance(current, ast.Attribute):
                    attr_chain.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    attr_chain.append(current.id)
                    dotted = ".".join(reversed(attr_chain))
                    if dotted.startswith("os.") or dotted.startswith("subprocess."):
                        raise SecurityError(f"Forbidden call: {dotted}()")

    # Additional rule: do not allow top-level exec/eval in any alias
    names = _collect_names(tree)
    if names & _FORBIDDEN_CALLS:
        raise SecurityError(f"Forbidden builtins present: {', '.join(names & _FORBIDDEN_CALLS)}")
