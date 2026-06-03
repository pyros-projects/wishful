"""wishful.evolve - AlphaEvolve-style evolutionary improvement."""

from wishful.evolve.evolver import evolve
from wishful.evolve.exceptions import EvolutionError
from wishful.evolve.history import EvolutionHistory, GenerationRecord, VariantRecord

__all__ = [
    "EvolutionError",
    "EvolutionHistory",
    "GenerationRecord",
    "VariantRecord",
    "evolve",
]
