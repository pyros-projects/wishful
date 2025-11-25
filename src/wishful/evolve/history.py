"""Evolution history tracking for AlphaEvolve-style context passing."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VariantRecord:
    """Record of a single variant attempt."""
    source: str
    fitness: Optional[float] = None
    failed: bool = False
    error_message: Optional[str] = None


@dataclass
class GenerationRecord:
    """Record of a single generation."""
    generation: int
    best_fitness: float
    variants_tried: int
    best_source: Optional[str] = None


@dataclass
class EvolutionHistory:
    """Complete evolution history with context for LLM."""
    original_fitness: float
    final_fitness: float
    generations: int
    total_variants_tried: int
    history: List[GenerationRecord] = field(default_factory=list)

    # All variant attempts (for context passing)
    all_variants: List[VariantRecord] = field(default_factory=list)

    @property
    def improvement(self) -> str:
        """Return improvement as percentage string."""
        if self.original_fitness == 0:
            return "N/A"
        pct = (self.final_fitness - self.original_fitness) / abs(self.original_fitness) * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    def get_context_for_llm(self, limit: int = 10) -> List[dict]:
        """
        Get history formatted for LLM context.

        Returns top `limit` variants sorted by fitness (best first).
        Failed variants are included to help LLM learn what doesn't work.

        This is THE KEY AlphaEvolve mechanism - passing history to LLM.
        """
        # Sort by fitness (handle None as worst)
        sorted_variants = sorted(
            self.all_variants,
            key=lambda v: v.fitness if v.fitness is not None else float('-inf'),
            reverse=True
        )

        # Take top N
        top_variants = sorted_variants[:limit]

        # Format for LLM
        return [
            {
                "source": v.source,
                "fitness": v.fitness,
                "failed": v.failed,
                "error": v.error_message
            }
            for v in top_variants
        ]

    def add_variant(
        self,
        source: str,
        fitness: Optional[float] = None,
        failed: bool = False,
        error_message: Optional[str] = None
    ):
        """Add a variant attempt to history."""
        self.all_variants.append(VariantRecord(
            source=source,
            fitness=fitness,
            failed=failed,
            error_message=error_message
        ))

    def to_dict(self) -> dict:
        """Convert to dictionary for __wishful_evolution__."""
        return {
            "original_fitness": self.original_fitness,
            "final_fitness": self.final_fitness,
            "improvement": self.improvement,
            "generations": self.generations,
            "total_variants_tried": self.total_variants_tried,
            "history": [
                {
                    "generation": r.generation,
                    "best_fitness": r.best_fitness,
                    "variants_tried": r.variants_tried,
                }
                for r in self.history
            ]
        }
