"""Command-line interface for wishful."""

import sys
from pathlib import Path

import wishful


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("wishful - Just-in-time Python module generation")
        print("\nUsage:")
        print("  python -m wishful inspect         Show cached modules")
        print("  python -m wishful clear           Clear all cache")
        print("  python -m wishful regen <module>  Regenerate a module")
        print("\nExamples:")
        print("  python -m wishful inspect")
        print("  python -m wishful regen wishful.text")
        print("  python -m wishful clear")
        sys.exit(0)

    command = sys.argv[1]

    if command == "inspect":
        cached = wishful.inspect_cache()
        if not cached:
            print("No cached modules found in", wishful.settings.cache_dir)
        else:
            print(f"Cached modules in {wishful.settings.cache_dir}:")
            for path in cached:
                print(f"  {path}")
        
    elif command == "clear":
        wishful.clear_cache()
        print(f"Cleared all cached modules from {wishful.settings.cache_dir}")
        
    elif command == "regen":
        if len(sys.argv) < 3:
            print("Error: 'regen' requires a module name")
            print("Usage: python -m wishful regen <module>")
            sys.exit(1)
        module_name = sys.argv[2]
        wishful.regenerate(module_name)
        print(f"Regenerated {module_name} (will be re-created on next import)")
        
    else:
        print(f"Unknown command: {command}")
        print("Use 'python -m wishful' for help")
        sys.exit(1)


if __name__ == "__main__":
    main()
