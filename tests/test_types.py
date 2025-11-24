"""Tests for the type registration system."""

from dataclasses import dataclass
from typing import TypedDict

import pytest

import wishful
from wishful.types import (
    TypeRegistry,
    clear_type_registry,
    get_all_type_schemas,
    get_output_type_for_function,
    get_type_schema,
    type as type_decorator,
)


# Test fixtures - various type definitions
class SimpleTypedDict(TypedDict):
    name: str
    age: int


@dataclass
class SimpleDataclass:
    """A simple dataclass for testing."""
    name: str
    email: str
    age: int = 0


# Mock Pydantic for testing (in case it's not installed)
class MockBaseModel:
    """Mock BaseModel for testing without requiring pydantic."""
    
    model_fields = {}
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Store annotations as model_fields
        annotations = getattr(cls, '__annotations__', {})
        cls.model_fields = {
            name: type(
                'MockFieldInfo',
                (),
                {
                    'annotation': ann,
                    'default': getattr(cls, name, None),
                    'default_factory': None
                }
            )()
            for name, ann in annotations.items()
        }


class UserProfile(MockBaseModel):
    """User profile model."""
    name: str
    email: str
    age: int


class Product(MockBaseModel):
    title: str
    price: float
    in_stock: bool


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the type registry before each test."""
    clear_type_registry()
    yield
    clear_type_registry()


class TestTypeRegistry:
    """Test the TypeRegistry class."""
    
    def test_registry_initialization(self):
        """Test that a new registry is empty."""
        registry = TypeRegistry()
        assert registry.get_all_schemas() == {}
        assert registry.get_output_type("any_function") is None
    
    def test_register_simple_class(self):
        """Test registering a simple class."""
        registry = TypeRegistry()
        
        class SimpleClass:
            pass
        
        registry.register(SimpleClass)
        assert "SimpleClass" in registry.get_all_schemas()
    
    def test_register_with_output_for_single(self):
        """Test registering a type with a single output_for function."""
        registry = TypeRegistry()
        registry.register(UserProfile, output_for="create_user")
        
        assert registry.get_output_type("create_user") == "UserProfile"
        assert registry.get_output_type("other_function") is None
    
    def test_register_with_output_for_multiple(self):
        """Test registering a type with multiple output_for functions."""
        registry = TypeRegistry()
        registry.register(UserProfile, output_for=["create_user", "update_user", "get_user"])
        
        assert registry.get_output_type("create_user") == "UserProfile"
        assert registry.get_output_type("update_user") == "UserProfile"
        assert registry.get_output_type("get_user") == "UserProfile"
        assert registry.get_output_type("delete_user") is None
    
    def test_serialize_mock_pydantic(self):
        """Test serialization of mock Pydantic models."""
        registry = TypeRegistry()
        registry.register(UserProfile)
        
        schema = registry.get_schema("UserProfile")
        assert schema is not None
        assert "class UserProfile" in schema
        assert "name: str" in schema
        assert "email: str" in schema
        assert "age: int" in schema
    
    def test_serialize_dataclass(self):
        """Test serialization of dataclasses."""
        registry = TypeRegistry()
        registry.register(SimpleDataclass)
        
        schema = registry.get_schema("SimpleDataclass")
        assert schema is not None
        assert "@dataclass" in schema
        assert "class SimpleDataclass:" in schema
        assert "name: str" in schema
        assert "email: str" in schema
        assert "age: int = 0" in schema
    
    def test_serialize_typed_dict(self):
        """Test serialization of TypedDict."""
        registry = TypeRegistry()
        registry.register(SimpleTypedDict)
        
        schema = registry.get_schema("SimpleTypedDict")
        assert schema is not None
        assert "class SimpleTypedDict" in schema
        assert "name: str" in schema
        assert "age: int" in schema
    
    def test_clear_registry(self):
        """Test clearing the registry."""
        registry = TypeRegistry()
        registry.register(UserProfile, output_for="create_user")
        
        assert len(registry.get_all_schemas()) > 0
        assert registry.get_output_type("create_user") is not None
        
        registry.clear()
        
        assert registry.get_all_schemas() == {}
        assert registry.get_output_type("create_user") is None


class TestTypeDecorator:
    """Test the @wishful.type decorator."""
    
    def test_decorator_without_args(self):
        """Test @wishful.type without arguments."""
        
        @type_decorator
        class TestModel(MockBaseModel):
            field: str
        
        # Type should be registered
        assert get_type_schema("TestModel") is not None
        assert "TestModel" in get_all_type_schemas()
    
    def test_decorator_with_output_for_single(self):
        """Test @wishful.type(output_for='function')."""
        
        @type_decorator(output_for="process_data")
        class DataModel(MockBaseModel):
            value: int
        
        assert get_type_schema("DataModel") is not None
        assert get_output_type_for_function("process_data") == "DataModel"
    
    def test_decorator_with_output_for_multiple(self):
        """Test @wishful.type(output_for=['func1', 'func2'])."""
        
        @type_decorator(output_for=["func1", "func2"])
        class MultiModel(MockBaseModel):
            data: str
        
        assert get_output_type_for_function("func1") == "MultiModel"
        assert get_output_type_for_function("func2") == "MultiModel"
    
    def test_decorator_preserves_class(self):
        """Test that the decorator returns the original class."""
        
        @type_decorator
        class OriginalClass(MockBaseModel):
            value: str
        
        # Should be able to instantiate and use the class normally
        assert OriginalClass.__name__ == "OriginalClass"
        assert hasattr(OriginalClass, 'model_fields')


class TestGlobalRegistryFunctions:
    """Test the global registry helper functions."""
    
    def test_get_type_schema(self):
        """Test getting a type schema."""
        
        @type_decorator
        class TestType(MockBaseModel):
            x: int
        
        schema = get_type_schema("TestType")
        assert schema is not None
        assert "TestType" in schema
    
    def test_get_type_schema_missing(self):
        """Test getting a non-existent type schema."""
        assert get_type_schema("NonExistent") is None
    
    def test_get_all_type_schemas(self):
        """Test getting all type schemas."""
        
        @type_decorator
        class Type1(MockBaseModel):
            a: str
        
        @type_decorator
        class Type2(MockBaseModel):
            b: int
        
        schemas = get_all_type_schemas()
        assert "Type1" in schemas
        assert "Type2" in schemas
        assert len(schemas) >= 2
    
    def test_get_output_type_for_function(self):
        """Test getting output type for a function."""
        
        @type_decorator(output_for="my_function")
        class OutputType(MockBaseModel):
            result: str
        
        assert get_output_type_for_function("my_function") == "OutputType"
        assert get_output_type_for_function("other_function") is None
    
    def test_clear_type_registry(self):
        """Test clearing the global registry."""
        
        @type_decorator
        class SomeType(MockBaseModel):
            field: str
        
        assert len(get_all_type_schemas()) > 0
        
        clear_type_registry()
        
        assert get_all_type_schemas() == {}


class TestComplexAnnotations:
    """Test handling of complex type annotations."""
    
    def test_list_annotation(self):
        """Test serialization with list annotations."""
        
        @dataclass
        class ListModel:
            items: list[str]
            numbers: list[int]
        
        registry = TypeRegistry()
        registry.register(ListModel)
        
        schema = registry.get_schema("ListModel")
        assert "list[str]" in schema or "list" in schema
    
    def test_dict_annotation(self):
        """Test serialization with dict annotations."""
        
        @dataclass
        class DictModel:
            mapping: dict[str, int]
        
        registry = TypeRegistry()
        registry.register(DictModel)
        
        schema = registry.get_schema("DictModel")
        assert "dict" in schema
    
    def test_optional_annotation(self):
        """Test serialization with Optional/Union annotations."""
        
        @dataclass
        class OptionalModel:
            name: str | None = None
        
        registry = TypeRegistry()
        registry.register(OptionalModel)
        
        schema = registry.get_schema("OptionalModel")
        assert schema is not None


class TestIntegrationWithWishful:
    """Test integration with the main wishful module."""
    
    def test_type_exported_from_wishful(self):
        """Test that 'type' is exported from wishful."""
        assert hasattr(wishful, 'type')
    
    def test_decorator_via_wishful(self):
        """Test using @wishful.type."""
        
        @wishful.type
        class WishfulModel(MockBaseModel):
            field: str
        
        # Should be registered
        assert get_type_schema("WishfulModel") is not None
    
    def test_decorator_with_args_via_wishful(self):
        """Test using @wishful.type(output_for=...)."""
        
        @wishful.type(output_for="generate_thing")
        class ThingModel(MockBaseModel):
            thing: str
        
        assert get_output_type_for_function("generate_thing") == "ThingModel"


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_register_same_type_twice(self):
        """Test registering the same type multiple times."""
        
        @type_decorator
        class DuplicateType(MockBaseModel):
            value: str
        
        # Register again with different output_for
        @type_decorator(output_for="func1")
        class DuplicateType(MockBaseModel):
            value: str
        
        # Should not raise, last registration wins
        assert get_output_type_for_function("func1") == "DuplicateType"
    
    def test_empty_class(self):
        """Test registering an empty class."""
        
        @type_decorator
        class EmptyClass:
            pass
        
        schema = get_type_schema("EmptyClass")
        assert schema is not None
    
    def test_class_with_docstring(self):
        """Test that docstrings are preserved in serialization."""
        
        @dataclass
        class DocumentedClass:
            """This class has documentation."""
            field: str
        
        registry = TypeRegistry()
        registry.register(DocumentedClass)
        
        schema = registry.get_schema("DocumentedClass")
        assert "This class has documentation" in schema


class TestSerializationEdgeCases:
    """Test edge cases in type serialization."""
    
    def test_pydantic_with_default_values(self):
        """Test Pydantic models with default values."""
        
        class ModelWithDefaults(MockBaseModel):
            name: str
            count: int
        
        # Add defaults to the mock
        ModelWithDefaults.model_fields['count'].default = 0
        
        registry = TypeRegistry()
        registry.register(ModelWithDefaults)
        schema = registry.get_schema("ModelWithDefaults")
        assert "count" in schema
    
    def test_format_annotation_with_union(self):
        """Test formatting Union type annotations."""
        from typing import Union
        
        registry = TypeRegistry()
        # Test the _format_annotation method directly
        result = registry._format_annotation(Union[str, int])
        # Should return a string representation
        assert isinstance(result, str)
        # Union formatting varies by Python version, just check it's not empty
        assert len(result) > 0
    
    def test_serialize_class_with_source_available(self):
        """Test serialization when source code is available."""
        
        # Define a simple class that inspect.getsource can read
        @type_decorator
        class SourceAvailableClass:
            """A class with accessible source."""
            x: int
            y: str
        
        schema = get_type_schema("SourceAvailableClass")
        assert schema is not None
        # Should contain the class name
        assert "SourceAvailableClass" in schema
    
    def test_typed_dict_without_docstring(self):
        """Test TypedDict serialization without docstring."""
        
        class SimpleDict(TypedDict):
            key: str
            value: int
        
        registry = TypeRegistry()
        registry.register(SimpleDict)
        schema = registry.get_schema("SimpleDict")
        assert "key: str" in schema
        assert "value: int" in schema
