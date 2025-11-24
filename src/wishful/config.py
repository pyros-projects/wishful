from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from a local .env if present so users don't need to
# export them manually when running examples.
load_dotenv()


_DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", os.getenv("WISHFUL_MODEL", "azure/gpt-4.1"))
_DEFAULT_SYSTEM_PROMPT = os.getenv(
    "WISHFUL_SYSTEM_PROMPT",
    dedent(
        """
        You are a Python code generator. Output ONLY executable Python code.
        - Do not wrap code in markdown fences.
        - You may use any Python libraries available in the environment.
        - Prefer simple, readable implementations.
        - Avoid network calls, filesystem writes, subprocess, or shell execution.
        - Include docstrings and type hints where helpful.
        """
    ).strip(),
)
_DEFAULT_LOG_LEVEL = os.getenv("WISHFUL_LOG_LEVEL", "WARNING").upper()
_DEFAULT_LOG_TO_FILE = os.getenv("WISHFUL_LOG_TO_FILE", "1") != "0"


@dataclass
class Settings:
    """Runtime configuration for wishful.

    Values are mutable at runtime via :func:`configure` to make tests and user
    code ergonomics-friendly. Defaults are sourced from environment variables.
    """

    model: str = _DEFAULT_MODEL
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("WISHFUL_CACHE_DIR", ".wishful")))
    review: bool = os.getenv("WISHFUL_REVIEW", "0") == "1"
    debug: bool = os.getenv("WISHFUL_DEBUG", "0") == "1"
    allow_unsafe: bool = os.getenv("WISHFUL_UNSAFE", "0") == "1"
    spinner: bool = os.getenv("WISHFUL_SPINNER", "1") != "0"
    max_tokens: int = int(os.getenv("WISHFUL_MAX_TOKENS", "4096"))
    temperature: float = float(os.getenv("WISHFUL_TEMPERATURE", "1"))
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT
    log_level: str = _DEFAULT_LOG_LEVEL
    log_to_file: bool = _DEFAULT_LOG_TO_FILE

    def copy(self) -> "Settings":
        return Settings(
            model=self.model,
            cache_dir=self.cache_dir,
            review=self.review,
            debug=self.debug,
            allow_unsafe=self.allow_unsafe,
            spinner=self.spinner,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system_prompt=self.system_prompt,
            log_level=self.log_level,
            log_to_file=self.log_to_file,
        )


settings = Settings()


def configure(
    *,
    model: Optional[str] = None,
    cache_dir: Optional[str | Path] = None,
    review: Optional[bool] = None,
    debug: Optional[bool] = None,
    allow_unsafe: Optional[bool] = None,
    spinner: Optional[bool] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
    log_level: Optional[str] = None,
    log_to_file: Optional[bool] = None,
) -> None:
    """Update global settings in-place.

    All parameters are optional; only provided values overwrite current
    settings. Accepts both strings and :class:`pathlib.Path` for `cache_dir`.
    """

    updates = {
        "model": model,
        "cache_dir": Path(cache_dir) if cache_dir is not None else None,
        "review": review,
        "debug": debug,
        "allow_unsafe": allow_unsafe,
        "spinner": spinner,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "log_level": log_level.upper() if isinstance(log_level, str) else log_level,
        "log_to_file": log_to_file,
    }

    # If debug explicitly enabled, default to DEBUG level and file logging unless
    # caller provided overrides.
    if debug is True:
        if updates["log_level"] is None:
            updates["log_level"] = "DEBUG"
        if updates["log_to_file"] is None:
            updates["log_to_file"] = True
        # Spinners and heavy debug output don't mix nicely
        if updates["spinner"] is None:
            updates["spinner"] = False

    for attr, value in updates.items():
        if value is not None:
            setattr(settings, attr, value)

    # Reconfigure logging after updates (lazy import to avoid cycles during init)
    import importlib

    logging_mod = importlib.import_module("wishful.logging")
    # Ensure sinks are rebuilt with current settings
    logging_mod.configure_logging(force=True)


def reset_defaults() -> None:
    """Reset settings to environment-driven defaults (useful for tests)."""
    # Create new defaults and copy to existing settings object
    # This ensures all existing references to settings get updated
    defaults = Settings()
    settings.model = defaults.model
    settings.cache_dir = defaults.cache_dir
    settings.review = defaults.review
    settings.debug = defaults.debug
    settings.allow_unsafe = defaults.allow_unsafe
    settings.spinner = defaults.spinner
    settings.max_tokens = defaults.max_tokens
    settings.temperature = defaults.temperature
    settings.system_prompt = defaults.system_prompt
    settings.log_level = defaults.log_level
    settings.log_to_file = defaults.log_to_file

    import importlib

    logging_mod = importlib.import_module("wishful.logging")
    logging_mod.configure_logging(force=True)
