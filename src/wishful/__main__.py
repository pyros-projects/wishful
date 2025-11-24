"""Command-line interface for wishful."""

import sys

import wishful


def _print_usage() -> None:
    print("wishful - Just-in-time Python module generation")
    print("\nUsage:")
    print("  python -m wishful inspect         Show cached modules")
    print("  python -m wishful clear           Clear all cache")
    print("  python -m wishful regen <module>  Regenerate a module")
    print("\nExamples:")
    print("  python -m wishful inspect")
    print("  python -m wishful regen wishful.text")
    print("  python -m wishful clear")


def _cmd_inspect() -> None:
    cached = wishful.inspect_cache()
    if not cached:
        print("No cached modules found in", wishful.settings.cache_dir)
        return
    print(f"Cached modules in {wishful.settings.cache_dir}:")
    for path in cached:
        print(f"  {path}")


def _cmd_clear() -> None:
    wishful.clear_cache()
    print(f"Cleared all cached modules from {wishful.settings.cache_dir}")


def _cmd_regen(args: list[str]) -> None:
    if not args:
        raise ValueError("'regen' requires a module name")
    module_name = args[0]
    wishful.regenerate(module_name)
    print(f"Regenerated {module_name} (will be re-created on next import)")


def main() -> None:
    """Main CLI entry point."""
    args = sys.argv[1:]
    if not args:
        _print_usage()
        sys.exit(0)

    command, *rest = args
    handlers = {
        "inspect": _cmd_inspect,
        "clear": _cmd_clear,
        "regen": lambda: _cmd_regen(rest),
    }

    handler = handlers.get(command)
    if handler is None:
        print(f"Unknown command: {command}")
        print("Use 'python -m wishful' for help")
        sys.exit(1)

    try:
        handler()
    except ValueError as exc:
        print(f"Error: {exc}")
        print("Usage: python -m wishful regen <module>")
        sys.exit(1)


if __name__ == "__main__":
    main()
