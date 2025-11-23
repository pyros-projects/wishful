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
