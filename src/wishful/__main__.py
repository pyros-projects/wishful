"""Command-line interface for wishful.

Exit codes: 0 success, 1 runtime error, 2 usage error (argparse).
Every command supports ``--json`` for machine-readable output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Sequence

import wishful

# A regen target is either a fully-qualified wishful.static/dynamic name or a
# bare dotted name (which regenerate() maps into the static namespace). The
# allowlist rejects path separators, '..', and absolute paths so a crafted name
# can never be mapped to an arbitrary file.
_FULL_RE = re.compile(r"^wishful\.(static|dynamic)(\.[A-Za-z_][A-Za-z0-9_]*)+$")
_BARE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _valid_module(name: str) -> bool:
    # A wishful.* name must be a fully-qualified static/dynamic module; a bare
    # name (mapped into the static namespace by regenerate) must not itself start
    # with the reserved 'wishful' prefix, so `wishful regen wishful` is rejected.
    if name.startswith("wishful"):
        return bool(_FULL_RE.match(name))
    return bool(_BARE_RE.match(name))


def _emit_error(msg: str, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"error": msg}))
    else:
        print(f"Error: {msg}", file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wishful", description="Just-in-time Python module generation"
    )
    parser.add_argument(
        "--version", action="store_true", help="print the wishful version and exit"
    )
    sub = parser.add_subparsers(dest="command")

    p_inspect = sub.add_parser("inspect", help="show cached modules")
    p_inspect.add_argument("--json", action="store_true", help="machine-readable JSON")

    p_clear = sub.add_parser("clear", help="clear all cached modules")
    p_clear.add_argument("--json", action="store_true", help="machine-readable JSON")

    p_regen = sub.add_parser("regen", help="regenerate a module on next import")
    p_regen.add_argument("module", help="module name, e.g. wishful.static.text")
    p_regen.add_argument("--json", action="store_true", help="machine-readable JSON")
    return parser


def _cmd_inspect(as_json: bool) -> int:
    cached = wishful.inspect_cache()
    if as_json:
        print(json.dumps({"cache_dir": str(wishful.settings.cache_dir), "cached": cached}))
    elif not cached:
        print("No cached modules found in", wishful.settings.cache_dir)
    else:
        print(f"Cached modules in {wishful.settings.cache_dir}:")
        for path in cached:
            print(f"  {path}")
    return 0


def _cmd_clear(as_json: bool) -> int:
    wishful.clear_cache()
    if as_json:
        print(json.dumps({"cleared": True, "cache_dir": str(wishful.settings.cache_dir)}))
    else:
        print(f"Cleared all cached modules from {wishful.settings.cache_dir}")
    return 0


def _cmd_regen(module: str, as_json: bool) -> int:
    if not _valid_module(module):
        _emit_error(f"invalid module name: {module!r}", as_json)
        return 1
    wishful.regenerate(module)
    if as_json:
        print(json.dumps({"module": module, "regenerated": True}))
    else:
        print(f"Regenerated {module} (will be re-created on next import)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)  # argparse exits 2 on usage errors

    if args.version:
        print(wishful.__version__)
        return 0
    if args.command is None:
        parser.print_help()
        return 0

    as_json = getattr(args, "json", False)
    if args.command == "inspect":
        return _cmd_inspect(as_json)
    if args.command == "clear":
        return _cmd_clear(as_json)
    if args.command == "regen":
        return _cmd_regen(args.module, as_json)
    return 2  # pragma: no cover - argparse rejects unknown commands first


if __name__ == "__main__":
    sys.exit(main())
