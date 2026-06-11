import pytest

from wishful.safety.validator import SecurityError, validate_code


def test_blocks_os_system():
    source = "import os\nos.system('ls')\n"
    with pytest.raises(SecurityError):
        validate_code(source, allow_unsafe=False)


def test_allows_safe_code():
    source = "def ok(x):\n    return x * 2\n"
    # Should not raise
    validate_code(source, allow_unsafe=False)


def test_validate_raises_syntaxerror_not_importerror():
    """Malformed source must raise SyntaxError so the loader can retry it.

    The old behaviour wrapped syntax errors as ImportError, which made the
    loader's regenerate-once path unreachable whenever safety was on.
    """
    with pytest.raises(SyntaxError):
        validate_code("def broken(:\n    pass\n", allow_unsafe=False)
    # SyntaxError is not an ImportError subclass, so callers can distinguish it.
    assert not issubclass(SyntaxError, ImportError)
