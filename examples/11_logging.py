"""Example 11: Logging knobs — debug, log_level, log_to_file, log_prompts.

Run with a real LLM, or offline:

    WISHFUL_FAKE_LLM=1 uv run python examples/11_logging.py

wishful is quiet by default: WARNING-level console output, no log files.
Every knob below is also an env var (WISHFUL_DEBUG, WISHFUL_LOG_LEVEL,
WISHFUL_LOG_TO_FILE, WISHFUL_LOG_PROMPTS).
"""

from __future__ import annotations

import wishful

wishful.clear_cache()

# --- 1) debug=True: the firehose -------------------------------------------
# Sets log_level=DEBUG and turns on file logging (under <cache_dir>/logs/),
# so a misbehaving generation can be diagnosed after the fact.
wishful.configure(debug=True)
print(f"debug on -> level={wishful.settings.log_level}, "
      f"file logging={wishful.settings.log_to_file}")

from wishful.static.greet import make_greeting

print("import under debug:", make_greeting("Ada"))

# --- 2) log_level: pick your own volume -------------------------------------
# INFO shows one line per generation; DEBUG adds cache decisions and timings.
wishful.configure(debug=False, log_level="INFO", log_to_file=False)
print(f"\nnow level={wishful.settings.log_level}, "
      f"file logging={wishful.settings.log_to_file}")

# --- 3) log_to_file: opt-in, never on import --------------------------------
# A library must not write files just because you imported it. File logs are
# opt-in (or ride along with debug=True). Today's file, when enabled:
log_dir = wishful.settings.cache_dir / "logs"
print(f"file logs (when enabled) land in: {log_dir}")

# --- 4) log_prompts: redacted by default ------------------------------------
# Prompt/context bodies can contain YOUR source code and secrets, so they are
# redacted from logs even at DEBUG. Set log_prompts=True (or
# WISHFUL_LOG_PROMPTS=1) to log them while debugging prompt quality.
print(f"prompt bodies logged: {wishful.settings.log_prompts} (default: False)")

wishful.reset_defaults()
