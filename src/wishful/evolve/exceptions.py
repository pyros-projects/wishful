"""Exceptions for wishful.evolve."""

from typing import Callable, Optional


class EvolutionError(Exception):
    """Raised when evolution fails to produce valid results."""

    def __init__(
        self,
        message: str,
        best_variant: Optional[Callable] = None,
        best_fitness: Optional[float] = None,
        original_fitness: Optional[float] = None,
        generations_completed: int = 0,
        total_attempts: int = 0
    ):
        super().__init__(message)
        self.best_variant = best_variant
        self.best_fitness = best_fitness
        self.original_fitness = original_fitness
        self.generations_completed = generations_completed
        self.total_attempts = total_attempts
