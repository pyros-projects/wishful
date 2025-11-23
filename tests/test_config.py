"""Tests for configuration and settings."""

import os
from pathlib import Path

import pytest

from wishful.config import Settings, configure, reset_defaults, settings


def test_default_settings():
    """Test default settings values."""
    s = Settings()
    assert s.cache_dir == Path(".wishful")
    assert s.review is False
    assert s.debug is False
    assert s.allow_unsafe is False
    assert s.spinner is True
    assert s.max_tokens == 800
    assert s.temperature == 0


def test_configure_model():
    """Test configuring the model."""
    # Save original and configure
    configure(model="gpt-4o-mini")
    assert settings.model == "gpt-4o-mini"
    # Note: reset_wishful fixture will restore settings after test


def test_configure_cache_dir():
    """Test configuring cache directory."""
    configure(cache_dir="/tmp/test")
    assert settings.cache_dir == Path("/tmp/test")
    # Note: reset_wishful fixture will restore settings after test


def test_configure_multiple_settings():
    """Test configuring multiple settings at once."""
    configure(
        spinner=True,
        review=True,
        temperature=0.7,
        max_tokens=1000,
    )
    assert settings.spinner is True
    assert settings.review is True
    assert settings.temperature == 0.7
    assert settings.max_tokens == 1000
    # Note: reset_wishful fixture will restore settings after test


def test_reset_defaults():
    """Test resetting to default values."""
    configure(spinner=True, review=True, temperature=0.9)
    reset_defaults()
    # Check reset to env defaults (WISHFUL_SPINNER default is "1")
    assert settings.spinner is True
    assert settings.review is False
    assert settings.temperature == 0


def test_settings_copy():
    """Test copying settings."""
    # Make a copy with current settings
    configure(spinner=True)
    original = settings.copy()
    # Change settings
    configure(spinner=False)
    copy = settings.copy()
    # Verify they're different
    assert copy.spinner is False
    assert original.spinner is True
    # Note: reset_wishful fixture will restore settings after test
