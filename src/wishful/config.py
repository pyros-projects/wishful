from __future__ import annotations

import os
import builtins
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from a local .env if present so users don't need to
# export them manually when running examples.
load_dotenv()


def _resolve_model() -> str:
    """Resolve the model id with WISHFUL_MODEL taking precedence over DEFAULT_MODEL.

    The wishful-specific variable wins over the generic one; a stale DEFAULT_MODEL
    from other tooling must not silently override an explicit WISHFUL_MODEL.
    """
    specific = os.getenv("WISHFUL_MODEL")
    generic = os.getenv("DEFAULT_MODEL")
    if specific and generic and specific != generic:
        warnings.warn(
            f"Both WISHFUL_MODEL ({specific!r}) and DEFAULT_MODEL ({generic!r}) are set; "
            f"using WISHFUL_MODEL. DEFAULT_MODEL is only the fallback.",
            stacklevel=2,
        )
    return specific or generic or "azure/gpt-4.1"


def _resolve_system_prompt() -> str:
    return os.getenv(
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


@dataclass
class Settings:
    """Runtime configuration for wishful.

    Values are mutable at runtime via :func:`configure`. Every env-derived field
    uses a default_factory so that constructing a fresh ``Settings()`` (as
    :func:`reset_defaults` does) re-reads the current environment uniformly.
    """

    model: str = field(default_factory=_resolve_model)
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("WISHFUL_CACHE_DIR", ".wishful")))
    review: bool = field(default_factory=lambda: os.getenv("WISHFUL_REVIEW", "0") == "1")
    debug: bool = field(default_factory=lambda: os.getenv("WISHFUL_DEBUG", "0") == "1")
    allow_unsafe: bool = field(default_factory=lambda: os.getenv("WISHFUL_UNSAFE", "0") == "1")
    spinner: bool = field(default_factory=lambda: os.getenv("WISHFUL_SPINNER", "1") != "0")
    max_tokens: int = field(default_factory=lambda: int(os.getenv("WISHFUL_MAX_TOKENS", "4096")))
    temperature: float = field(default_factory=lambda: float(os.getenv("WISHFUL_TEMPERATURE", "1")))
    system_prompt: str = field(default_factory=_resolve_system_prompt)
    log_level: str = field(default_factory=lambda: os.getenv("WISHFUL_LOG_LEVEL", "WARNING").upper())
    # Opt-in: a library must not create files in the user's CWD just on import.
    log_to_file: bool = field(default_factory=lambda: os.getenv("WISHFUL_LOG_TO_FILE", "0") == "1")
    request_timeout: float = field(default_factory=lambda: float(os.getenv("WISHFUL_REQUEST_TIMEOUT", "300")))

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
            request_timeout=self.request_timeout,
        )


# Persist the settings object across module reloads (tests deliberately purge
# wishful.* modules). Stash it on `builtins` so all imports share the same
# instance even after sys.modules churn.
if getattr(builtins, "_wishful_settings", None) is None:
    builtins._wishful_settings = Settings()
settings = builtins._wishful_settings  # type: ignore[attr-defined]


# Internal helper to load logging module robustly (handles altered sys.modules)
def _load_logging_module():
    try:
        from wishful import logging as logging_mod  # type: ignore
        return logging_mod
    except Exception:
        pass
    try:
        import importlib.util
        import sys
        path = Path(__file__).parent / "logging.py"
        spec = importlib.util.spec_from_file_location("wishful.logging", path)
        if spec and spec.loader:
            logging_mod = importlib.util.module_from_spec(spec)
            sys.modules["wishful.logging"] = logging_mod
            spec.loader.exec_module(logging_mod)  # type: ignore[arg-type]
            return logging_mod
    except Exception:
        return None
    return None


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
    request_timeout: Optional[float] = None,
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
        "request_timeout": request_timeout,
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
    logging_mod = _load_logging_module()
    if logging_mod:
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
    settings.request_timeout = defaults.request_timeout

    logging_mod = _load_logging_module()
    if logging_mod:
        logging_mod.configure_logging(force=True)
