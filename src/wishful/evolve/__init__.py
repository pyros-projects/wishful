"""wishful.evolve - AlphaEvolve-style evolutionary improvement."""

from wishful.evolve.evolver import EvolutionResult, evolve
from wishful.evolve.exceptions import EvolutionError
from wishful.evolve.history import (
    EvolutionHistory,
    EvolutionMetadata,
    GenerationRecord,
    VariantRecord,
)

__all__ = [
    "EvolutionError",
    "EvolutionHistory",
    "EvolutionMetadata",
    "EvolutionResult",
    "GenerationRecord",
    "VariantRecord",
    "evolve",
]
