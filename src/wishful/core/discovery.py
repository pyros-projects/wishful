from __future__ import annotations

import ast
import inspect
import linecache
from pathlib import Path
from textwrap import dedent
from typing import List, Optional, Sequence, Tuple


class ImportContext:
    def __init__(self, functions: Sequence[str], context: str | None):
        self.functions = list(functions)
        self.context = context

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ImportContext(functions={self.functions}, context={self.context!r})"


def _gather_context_lines(filename: str, lineno: int, radius: int = 2) -> str:
    lines = linecache.getlines(filename)
    if not lines:
        return ""
    start = max(lineno, 1) - 1
    end = min(lineno + radius, len(lines))
    snippet = lines[start:end]
    return "".join(snippet).strip()


def _parse_imported_names(source_line: str, fullname: str) -> List[str]:
    try:
        tree = ast.parse(dedent(source_line))
    except SyntaxError:
        return []

    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("wishful") and fullname.startswith(node.module):
                for alias in node.names:
                    # Use original name (not alias) because that's what the module must define.
                    names.append(alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("wishful") and fullname.startswith(alias.name):
                    # For `import wishful.foo as bar`, the target is bar (module).
                    target = alias.asname or alias.name.split(".")[-1]
                    names.append(target)
    return names


def discover(fullname: str) -> ImportContext:
    """Attempt to recover requested symbol names and nearby comments.

    This uses stack inspection heuristics. It is best-effort; absence of
    signals simply results in empty context.
    """

    frame = inspect.currentframe()
    # Skip the discover() frame itself.
    if frame:
        frame = frame.f_back

    while frame:
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno

        if filename.startswith("<"):
            frame = frame.f_back
            continue
        normalized = filename.replace("\\", "/")
        if "/src/wishful/" in normalized and "/tests/" not in normalized:
            frame = frame.f_back
            continue

        code_line = linecache.getline(filename, lineno).strip()
        if code_line:
            functions = _parse_imported_names(code_line, fullname)
            if functions:
                context = _gather_context_lines(filename, lineno + 1, radius=3)
                return ImportContext(functions=functions, context=context)

        frame = frame.f_back

    return ImportContext(functions=[], context=None)
