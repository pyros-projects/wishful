import sys
import pytest

from wishful import clear_cache
from wishful.config import configure, reset_defaults
from wishful.types.registry import clear_type_registry


@pytest.fixture(autouse=True)
def reset_wishful(tmp_path):
    # Isolate cache per test and kill spinner/interactive prompts. Safety is ON
    # by default — the suite must exercise the same validator path that ships.
    configure(
        cache_dir=tmp_path / ".wishful",
        spinner=False,
        review=False,
        debug=True,
        allow_unsafe=False,
    )
    clear_cache()
    # Registered types are global state; a leaked registration must not bleed
    # schemas into another test's prompts.
    clear_type_registry()
    yield
    clear_cache()
    clear_type_registry()
    reset_defaults()
    for name in list(sys.modules):
        if name.startswith("wishful.static") or name.startswith("wishful.dynamic"):
            sys.modules.pop(name, None)
    #sys.modules.pop("wishful", None)


@pytest.fixture
def unsafe_settings():
    """Opt-in fixture for the rare test that must run with safety disabled."""
    configure(allow_unsafe=True)
    yield
    configure(allow_unsafe=False)
