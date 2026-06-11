"""Common exception base for wishful.

Every error wishful raises derives from :class:`WishfulError`, so callers can
catch the whole family with one ``except``. The generation/safety errors also
derive from ``ImportError`` because they surface through the import machinery;
existing ``except ImportError`` handlers keep working.
"""

from __future__ import annotations


class WishfulError(Exception):
    """Base class for all errors raised by wishful."""
