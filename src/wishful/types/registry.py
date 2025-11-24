"""Type registration system for wishful.

Allows users to register complex types (Pydantic models, dataclasses, TypedDict)
that the LLM can use when generating code.
"""

from __future__ import annotations

import inspect
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from typing import Any, Callable, TypeVar, get_type_hints

T = TypeVar("T")


class TypeRegistry:
    """Global registry for user-defined types."""

    def __init__(self):
        # Map: type_name -> serialized type definition
        self._types: dict[str, str] = {}
        # Map: function_name -> type_name (for output_for mapping)
        self._function_outputs: dict[str, str] = {}

    def register(
        self, type_class: type, *, output_for: str | list[str] | None = None
    ) -> None:
        """Register a type and optionally associate it with function(s)."""
        schema = self._serialize_type(type_class)
        self._types[type_class.__name__] = schema

        if output_for:
            functions = [output_for] if isinstance(output_for, str) else output_for
            for func_name in functions:
                self._function_outputs[func_name] = type_class.__name__

    def get_schema(self, type_name: str) -> str | None:
        """Get the serialized schema for a registered type."""
        return self._types.get(type_name)

    def get_all_schemas(self) -> dict[str, str]:
        """Get all registered type schemas."""
        return self._types.copy()

    def get_output_type(self, function_name: str) -> str | None:
        """Get the registered output type for a function."""
        return self._function_outputs.get(function_name)

    def clear(self) -> None:
        """Clear all registered types."""
        self._types.clear()
        self._function_outputs.clear()

    def _serialize_type(self, type_class: type) -> str:
        """Serialize a type to a string representation for the LLM."""
        # Check if it's a Pydantic model
        if self._is_pydantic_model(type_class):
            return self._serialize_pydantic(type_class)

        # Check if it's a dataclass
        if is_dataclass(type_class):
            return self._serialize_dataclass(type_class)

        # Check if it's a TypedDict
        if self._is_typed_dict(type_class):
            return self._serialize_typed_dict(type_class)

        # Fallback: get source code if available
        try:
            return inspect.getsource(type_class)
        except (OSError, TypeError):
            # Last resort: just return the class definition line
            return f"class {type_class.__name__}: ..."

    def _is_pydantic_model(self, type_class: type) -> bool:
        """Check if a class is a Pydantic BaseModel."""
        try:
            # Check if BaseModel is in the MRO or has model_fields
            return hasattr(type_class, "model_fields") or any(
                "BaseModel" in base.__name__ for base in type_class.__mro__
            )
        except (AttributeError, TypeError):
            return False

    def _serialize_pydantic(self, model_class: type) -> str:
        """Serialize a Pydantic model to source code."""
        lines = [f"class {model_class.__name__}(BaseModel):"]

        # Add docstring if present
        if model_class.__doc__:
            lines.append(f'    """{model_class.__doc__.strip()}"""')

        # Get model fields
        if hasattr(model_class, "model_fields"):
            # Pydantic v2
            for field_name, field_info in model_class.model_fields.items():
                annotation = self._format_annotation(field_info.annotation)

                # Handle default values
                if field_info.default is not None:
                    default_repr = repr(field_info.default)
                    lines.append(f"    {field_name}: {annotation} = {default_repr}")
                elif field_info.default_factory is not None:
                    lines.append(
                        f"    {field_name}: {annotation} = Field(default_factory=...)"
                    )
                else:
                    lines.append(f"    {field_name}: {annotation}")
        elif hasattr(model_class, "__fields__"):
            # Pydantic v1
            for field_name, field in model_class.__fields__.items():
                annotation = self._format_annotation(field.outer_type_)
                if field.default is not None:
                    default_repr = repr(field.default)
                    lines.append(f"    {field_name}: {annotation} = {default_repr}")
                else:
                    lines.append(f"    {field_name}: {annotation}")

        return "\n".join(lines)

    def _serialize_dataclass(self, dc_class: type) -> str:
        """Serialize a dataclass to source code."""
        lines = ["@dataclass", f"class {dc_class.__name__}:"]

        # Add docstring if present
        if dc_class.__doc__:
            lines.append(f'    """{dc_class.__doc__.strip()}"""')

        for field in dataclass_fields(dc_class):
            annotation = self._format_annotation(field.type)
            if field.default is not field.default_factory:  # type: ignore
                # Has a default value
                default_repr = repr(field.default)
                lines.append(f"    {field.name}: {annotation} = {default_repr}")
            elif field.default_factory is not field.default_factory:  # type: ignore
                lines.append(
                    f"    {field.name}: {annotation} = field(default_factory=...)"
                )
            else:
                lines.append(f"    {field.name}: {annotation}")

        return "\n".join(lines)

    def _is_typed_dict(self, type_class: type) -> bool:
        """Check if a class is a TypedDict."""
        try:
            return hasattr(type_class, "__annotations__") and hasattr(
                type_class, "__total__"
            )
        except AttributeError:
            return False

    def _serialize_typed_dict(self, td_class: type) -> str:
        """Serialize a TypedDict to source code."""
        lines = [f"class {td_class.__name__}(TypedDict):"]

        if td_class.__doc__:
            lines.append(f'    """{td_class.__doc__.strip()}"""')

        for field_name, field_type in get_type_hints(td_class).items():
            annotation = self._format_annotation(field_type)
            lines.append(f"    {field_name}: {annotation}")

        return "\n".join(lines)

    def _format_annotation(self, annotation: Any) -> str:
        """Format a type annotation as a string."""
        if hasattr(annotation, "__name__"):
            return annotation.__name__

        # Handle typing generics
        if hasattr(annotation, "__origin__"):
            origin = annotation.__origin__
            args = getattr(annotation, "__args__", ())

            if origin is list:
                return (
                    f"list[{self._format_annotation(args[0])}]" if args else "list"
                )
            elif origin is dict:
                key_type = self._format_annotation(args[0]) if args else "Any"
                val_type = self._format_annotation(args[1]) if len(args) > 1 else "Any"
                return f"dict[{key_type}, {val_type}]"
            elif origin is tuple:
                arg_strs = ", ".join(self._format_annotation(a) for a in args)
                return f"tuple[{arg_strs}]"
            # Handle Union/Optional
            elif hasattr(origin, "__name__") and origin.__name__ == "UnionType":
                arg_strs = " | ".join(self._format_annotation(a) for a in args)
                return arg_strs

        return str(annotation).replace("typing.", "")


# Global registry instance
_registry = TypeRegistry()


def type(
    cls: type[T] | None = None, *, output_for: str | list[str] | None = None
) -> type[T] | Callable[[type[T]], type[T]]:
    """Decorator to register a type with wishful.

    Usage:
        @wishful.type
        class UserProfile(BaseModel):
            name: str
            email: str

        # Or with output type specification
        @wishful.type(output_for='create_user')
        class UserProfile(BaseModel):
            name: str
            email: str

        # Multiple functions
        @wishful.type(output_for=['create_user', 'update_user'])
        class UserProfile(BaseModel):
            name: str
            email: str
    """

    def decorator(type_class: type[T]) -> type[T]:
        _registry.register(type_class, output_for=output_for)
        return type_class

    # Handle both @wishful.type and @wishful.type(...) syntax
    if cls is None:
        # Called with arguments: @wishful.type(output_for='...')
        return decorator
    else:
        # Called without arguments: @wishful.type
        return decorator(cls)


def get_type_schema(type_name: str) -> str | None:
    """Get the schema for a registered type."""
    return _registry.get_schema(type_name)


def get_all_type_schemas() -> dict[str, str]:
    """Get all registered type schemas."""
    return _registry.get_all_schemas()


def get_output_type_for_function(function_name: str) -> str | None:
    """Get the output type registered for a function."""
    return _registry.get_output_type(function_name)


def clear_type_registry() -> None:
    """Clear all registered types (useful for testing)."""
    _registry.clear()
