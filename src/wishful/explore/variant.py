"""Variant wrapper for generated functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class VariantMetadata:
    """Metadata about a generated variant."""

    module: str
    function: str
    variant_index: int
    generation_time: float
    benchmark_score: Optional[float] = None
    source_code: Optional[str] = None


def wrap_with_metadata(fn: Callable, metadata: VariantMetadata) -> Callable:
    """Attach metadata to a function without changing its behavior."""
    fn.__wishful_metadata__ = {  # type: ignore[attr-defined]
        "module": metadata.module,
        "function": metadata.function,
        "variant_index": metadata.variant_index,
        "generation_time": metadata.generation_time,
        "benchmark_score": metadata.benchmark_score,
    }
    if metadata.source_code:
        fn.__wishful_source__ = metadata.source_code  # type: ignore[attr-defined]
    return fn

