"""Example 16: The safety gate — SecurityError, allow_unsafe, and review=True.

Runs LLM-free (the demos plant cache files directly), so it works with or
without an API key:

    uv run python examples/16_safety_and_review.py

What you'll see:
  - generated/cached code is validated before it executes; dangerous imports
    raise wishful.SecurityError and the offending cache file is discarded
  - allow_unsafe=True turns the validator off (know what you're doing)
  - review=True shows you every generation and asks before running it
    (interactive terminals only — headless runs fail closed)

Honest framing: the validator is a best-effort AST blocklist, not a sandbox.
It stops accidental footguns, not a determined adversary. Treat generated
code like any other untrusted code review surface.
"""

from __future__ import annotations

import sys

import wishful

POISONED = '''\
import subprocess


def run_anything(cmd):
    """Looks helpful; wants shell access."""
    return subprocess.run(cmd, shell=True, capture_output=True)
'''


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def plant_poisoned_module() -> None:
    """Write a dangerous module straight into the cache, as an attacker (or a
    careless model) might. The cache is plain .py files on disk."""
    wishful.settings.cache_dir.mkdir(parents=True, exist_ok=True)
    (wishful.settings.cache_dir / "dangerzone.py").write_text(POISONED)


def example_security_error() -> None:
    heading("SecurityError: the validator refuses dangerous cached code")

    plant_poisoned_module()
    try:
        from wishful.static.dangerzone import run_anything  # noqa: F401

        print("!! should not get here")
    except wishful.SecurityError as exc:
        print(f"Blocked at load time: {exc}")

    # A rejected static cache file is deleted so it can't permanently poison
    # the import — the next import regenerates from scratch.
    gone = not (wishful.settings.cache_dir / "dangerzone.py").exists()
    print(f"Poisoned cache file removed: {gone}")


def example_allow_unsafe() -> None:
    heading("allow_unsafe=True: you take the wheel")

    print("allow_unsafe disables validation entirely. Use it when your wishes")
    print("legitimately need subprocess/filesystem access AND you review the")
    print("cache files yourself. Demo (import only, nothing executed):")

    plant_poisoned_module()
    wishful.configure(allow_unsafe=True)
    try:
        from wishful.static.dangerzone import run_anything

        print(f"Imported under allow_unsafe: {run_anything.__name__}()")
        print("(not calling it, obviously)")
    finally:
        wishful.configure(allow_unsafe=False)
        wishful.clear_cache()


def example_review() -> None:
    heading("review=True: approve every generation before it runs")

    if not sys.stdin.isatty():
        print("Not an interactive terminal — skipping the live walkthrough.")
        print("With review=True, every generation is printed and wishful asks")
        print("  'Run this code? [y/N]'")
        print("before executing it. Rejecting a fresh generation discards it;")
        print("rejecting a previously cached file keeps the file but does not")
        print("run it. Headless runs fail closed with an ImportError telling")
        print("you to set review=False or WISHFUL_REVIEW=0.")
        return

    print("Importing with review=True — you'll be asked to approve the code.")
    wishful.configure(review=True)
    try:
        from wishful.static.reviewed import add_numbers

        print(f"You approved it: add_numbers(2, 3) = {add_numbers(2, 3)}")
    except ImportError as exc:
        print(f"You rejected it (or generation failed): {exc}")
    finally:
        wishful.configure(review=False)


def main() -> None:
    example_security_error()
    example_allow_unsafe()
    example_review()


if __name__ == "__main__":
    main()
