"""Tests for configuration and settings."""

from pathlib import Path

from wishful.config import Settings, configure, reset_defaults, settings


def test_default_settings():
    """Test default settings values."""
    s = Settings()
    assert s.cache_dir == Path(".wishful")
    assert s.review is False
    assert s.debug is False
    assert s.allow_unsafe is False
    assert s.spinner is True
    assert s.max_tokens == 16384
    assert s.temperature == 1
    assert "Python code generator" in s.system_prompt


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
        system_prompt="be concise",
    )
    assert settings.spinner is True
    assert settings.review is True
    assert settings.temperature == 0.7
    assert settings.max_tokens == 1000
    assert settings.system_prompt == "be concise"
    # Note: reset_wishful fixture will restore settings after test


def test_reset_defaults():
    """Test resetting to default values."""
    configure(spinner=True, review=True, temperature=0.9)
    reset_defaults()
    # Check reset to env defaults (WISHFUL_SPINNER default is "1")
    assert settings.spinner is True
    assert settings.review is False
    assert settings.temperature == 1.0


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


# --- U13: config contract ---------------------------------------------------


def test_model_precedence_wishful_wins(monkeypatch):
    from wishful.config import _resolve_model

    monkeypatch.setenv("WISHFUL_MODEL", "openai/specific")
    monkeypatch.setenv("DEFAULT_MODEL", "openai/generic")
    assert _resolve_model() == "openai/specific"


def test_model_precedence_default_is_fallback(monkeypatch):
    from wishful.config import _resolve_model

    monkeypatch.delenv("WISHFUL_MODEL", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "openai/generic")
    assert _resolve_model() == "openai/generic"


def test_model_builtin_default(monkeypatch):
    from wishful.config import _resolve_model

    monkeypatch.delenv("WISHFUL_MODEL", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    assert _resolve_model() == "azure/gpt-4.1"


def test_model_disagreement_warns(monkeypatch):
    import pytest

    from wishful.config import _resolve_model

    monkeypatch.setenv("WISHFUL_MODEL", "openai/a")
    monkeypatch.setenv("DEFAULT_MODEL", "openai/b")
    with pytest.warns(UserWarning, match="WISHFUL_MODEL"):
        assert _resolve_model() == "openai/a"


def test_reset_defaults_rereads_env_uniformly(monkeypatch):
    monkeypatch.setenv("WISHFUL_MODEL", "openai/fromenv")
    monkeypatch.setenv("WISHFUL_MAX_TOKENS", "1234")
    monkeypatch.setenv("WISHFUL_CACHE_DIR", "/tmp/wishful_env_cache")
    monkeypatch.setenv("WISHFUL_REVIEW", "1")
    reset_defaults()
    assert settings.model == "openai/fromenv"
    assert settings.max_tokens == 1234
    assert str(settings.cache_dir) == "/tmp/wishful_env_cache"
    assert settings.review is True
