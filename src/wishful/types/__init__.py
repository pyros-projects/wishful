"""Type registry for complex type hints in wishful."""

from wishful.types.registry import (
    TypeRegistry,
    clear_type_registry,
    get_all_type_schemas,
    get_output_type_for_function,
    get_type_schema,
    type,
)

__all__ = [
    "type",
    "TypeRegistry",
    "get_type_schema",
    "get_all_type_schemas",
    "get_output_type_for_function",
    "clear_type_registry",
]
