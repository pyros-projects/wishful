"""Core import machinery for wishful."""

from .finder import MagicFinder, install
from .loader import MagicLoader

__all__ = ["MagicFinder", "MagicLoader", "install"]
