"""Example 15: The wishful CLI and runtime configuration.

Everything here is LLM-free, so it runs identically with or without an API key:

    uv run python examples/15_cli_and_config.py

Covers:
  - the `wishful` console script / `python -m wishful` (inspect, regen, clear)
  - `--json` for machine-readable output
  - `wishful.configure(...)` and `wishful.reset_defaults()`
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import wishful


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI as a subprocess, inheriting this example's cache dir."""
    env = dict(os.environ, WISHFUL_CACHE_DIR=str(wishful.settings.cache_dir))
    return subprocess.run(
        [sys.executable, "-m", "wishful", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def example_cli() -> None:
    heading("The CLI: inspect, regen, clear")

    # Plant a cache entry the CLI can see. The cache is plain Python files —
    # user-editable by design — so writing one directly is fair game.
    wishful.settings.cache_dir.mkdir(parents=True, exist_ok=True)
    (wishful.settings.cache_dir / "greetings.py").write_text(
        "def hello():\n    return 'hi'\n"
    )

    print("$ wishful --version")
    print(" ", run_cli("--version").stdout.strip())

    print("$ wishful inspect")
    print(run_cli("inspect").stdout.rstrip())

    # --json on every command, for scripts and agents:
    print("\n$ wishful inspect --json")
    payload = json.loads(run_cli("inspect", "--json").stdout)
    print(f"  cache_dir: {payload['cache_dir']}")
    print(f"  cached:    {len(payload['cached'])} module(s)")

    # regen drops the cached file so the NEXT import regenerates it.
    print("\n$ wishful regen greetings --json")
    print(" ", run_cli("regen", "greetings", "--json").stdout.strip())

    # Invalid names are rejected with exit code 1 (2 = usage error from argparse).
    bad = run_cli("regen", "../escape", "--json")
    print("\n$ wishful regen ../escape --json")
    print(f"  exit code {bad.returncode}: {bad.stdout.strip()}")

    print("\n$ wishful clear --json")
    print(" ", run_cli("clear", "--json").stdout.strip())


def example_configure() -> None:
    heading("configure() and reset_defaults()")

    print("Defaults:")
    print(f"  model       = {wishful.settings.model}")
    print(f"  temperature = {wishful.settings.temperature}")
    print(f"  max_tokens  = {wishful.settings.max_tokens}")

    # Tune generation without touching the environment. max_tokens defaults
    # high (16384) because reasoning models spend budget on hidden tokens.
    wishful.configure(
        model="openai/gpt-4.1",
        temperature=0.2,
        max_tokens=8192,
    )
    print("\nAfter configure(model='openai/gpt-4.1', temperature=0.2, max_tokens=8192):")
    print(f"  model       = {wishful.settings.model}")
    print(f"  temperature = {wishful.settings.temperature}")
    print(f"  max_tokens  = {wishful.settings.max_tokens}")

    # reset_defaults() re-reads the environment and restores every knob.
    wishful.reset_defaults()
    print("\nAfter reset_defaults():")
    print(f"  model       = {wishful.settings.model}")
    print(f"  temperature = {wishful.settings.temperature}")
    print(f"  max_tokens  = {wishful.settings.max_tokens}")


def main() -> None:
    example_cli()
    example_configure()


if __name__ == "__main__":
    main()
