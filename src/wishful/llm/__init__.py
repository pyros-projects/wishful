"""LLM integration layer."""

from .client import generate_module_code, GenerationError

__all__ = ["generate_module_code", "GenerationError"]
