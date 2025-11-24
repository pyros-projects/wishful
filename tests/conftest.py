import sys
import pytest

from wishful import clear_cache
from wishful.config import configure, reset_defaults


@pytest.fixture(autouse=True)
def reset_wishful(tmp_path):
    # Isolate cache per test and kill spinner/interactive prompts.
    configure(
        cache_dir=tmp_path / ".wishful",
        spinner=False,
        review=False,
        debug=True,
        allow_unsafe=True,
    )
    clear_cache()
    yield
    clear_cache()
    reset_defaults()
    for name in list(sys.modules):
        if name.startswith("wishful.static") or name.startswith("wishful.dynamic"):
            sys.modules.pop(name, None)
    #sys.modules.pop("wishful", None)
