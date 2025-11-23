from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from a local .env if present so users don't need to
# export them manually when running examples.
load_dotenv()


_DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", os.getenv("WISHFUL_MODEL", "azure/gpt-4.1"))


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
) -> None:
    """Update global settings in-place.

    All parameters are optional; only provided values overwrite current
    settings. Accepts both strings and :class:`pathlib.Path` for `cache_dir`.
    """

    if model is not None:
        settings.model = model
    if cache_dir is not None:
        settings.cache_dir = Path(cache_dir)
    if review is not None:
        settings.review = review
    if debug is not None:
        settings.debug = debug
    if allow_unsafe is not None:
        settings.allow_unsafe = allow_unsafe
    if spinner is not None:
        settings.spinner = spinner
    if temperature is not None:
        settings.temperature = temperature
    if max_tokens is not None:
        settings.max_tokens = max_tokens


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
