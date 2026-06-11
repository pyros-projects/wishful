"""Exceptions for wishful.explore."""

from __future__ import annotations

from typing import List

from wishful.exceptions import WishfulError


class ExplorationError(WishfulError):
    """Raised when no variant passes the tests."""

    def __init__(self, message: str, attempts: int, failures: List[str]):
        super().__init__(message)
        self.attempts = attempts
        self.failures = failures

