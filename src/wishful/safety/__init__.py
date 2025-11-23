"""Safety checks for generated code."""

from .validator import validate_code, SecurityError

__all__ = ["validate_code", "SecurityError"]
