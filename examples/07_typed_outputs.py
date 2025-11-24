"""Example demonstrating type registration for complex return types.

This example shows how to use @wishful.type to register Pydantic models,
dataclasses, and TypedDict types so the LLM can generate functions that
return properly structured data.

Run with: `uv run python examples/07_typed_outputs.py`
"""

import os
from dataclasses import dataclass
from typing import TypedDict

import wishful


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


# Example 1: Simple type registration
@wishful.type
@dataclass
class Book:
    """A book with title, author, and year."""
    title: str
    author: str
    year: int
    isbn: str | None = None


def example_simple_type_registration():
    heading("Example 1: Simple Type Registration")
    
    # The LLM knows about the Book type and can use it
    from wishful.static.library import create_sample_book
    
    book = create_sample_book()
    print(f"Generated book: {book}")
    print(f"Type: {type(book)}")


# Example 2: Specify output type for a function
@wishful.type(output_for="parse_user_data")
@dataclass
class UserProfile:
    """User profile with name, email, and age."""
    name: str
    email: str
    age: int
    is_active: bool = True


def example_typed_output():
    heading("Example 2: Typed Function Output")
    
    # The LLM will generate parse_user_data to return a UserProfile
    from wishful.static.users import parse_user_data
    
    raw_data = "John Doe, john@example.com, 30"
    profile = parse_user_data(raw_data)
    
    print(f"Parsed profile: {profile}")
    
    # In fake mode, this returns a dict; with a real LLM, it returns UserProfile
    if hasattr(profile, 'name'):
        print(f"Name: {profile.name}")
        print(f"Email: {profile.email}")
        print(f"Age: {profile.age}")
    else:
        print("(Fake mode returns dict; real LLM would return UserProfile instance)")


# Example 3: Multiple functions sharing the same output type
class ProductInfo(TypedDict):
    """Product information."""
    name: str
    price: float
    in_stock: bool
    category: str


wishful.type(ProductInfo, output_for=["parse_product", "create_product"])


def example_shared_type():
    heading("Example 3: Multiple Functions with Shared Type")
    
    from wishful.static.products import parse_product, create_product
    
    # Both functions return ProductInfo
    product1 = parse_product("Laptop,$999.99,true,Electronics")
    print(f"Parsed product: {product1}")
    
    product2 = create_product(
        name="Mouse",
        price=29.99,
        in_stock=True,
        category="Accessories"
    )
    print(f"Created product: {product2}")


# Example 4: Nested types for complex data structures
@wishful.type
@dataclass
class Address:
    """Mailing address."""
    street: str
    city: str
    state: str
    zip_code: str


@wishful.type(output_for="extract_contact_info")
@dataclass
class ContactInfo:
    """Contact information with address."""
    name: str
    phone: str
    email: str
    address: Address | None = None


def example_nested_types():
    heading("Example 4: Nested Complex Types")
    
    # The LLM knows about both Address and ContactInfo
    from wishful.static.contacts import extract_contact_info
    
    text = """
    Name: Alice Smith
    Phone: 555-1234
    Email: alice@example.com
    Address: 123 Main St, Springfield, IL, 62701
    """
    
    contact = extract_contact_info(text)
    print(f"Extracted contact: {contact}")
    
    # Handle both real and fake mode
    if hasattr(contact, 'address') and contact.address:
        print(f"Lives in: {contact.address.city}, {contact.address.state}")
    else:
        print("(Fake mode returns dict; real LLM would return ContactInfo instance)")


# Example 5: Using types with validation logic
@wishful.type(output_for=["validate_age", "calculate_birth_year"])
@dataclass
class Person:
    """Person with validated age."""
    name: str
    age: int
    
    def __post_init__(self):
        if self.age < 0 or self.age > 150:
            raise ValueError(f"Invalid age: {self.age}")


def example_validated_types():
    heading("Example 5: Types with Validation")
    
    from wishful.static.people import validate_age, calculate_birth_year
    
    # validate_age checks if age is in valid range
    result = validate_age("25")
    print(f"Age validation result: {result}")
    
    # calculate_birth_year computes birth year from age
    person = calculate_birth_year(age=30, current_year=2025)
    print(f"Birth year calculation: {person}")
    print("(With real LLM, these would return Person instances with validation)")


def main():
    # Make output deterministic in CI if desired
    if os.getenv("WISHFUL_FAKE_LLM") == "1":
        print("Using fake LLM stub responses (WISHFUL_FAKE_LLM=1)")
    
    print("\n🪄 Type Registry Examples for Wishful\n")
    print("These examples show how to register complex types so the LLM")
    print("can generate functions that return properly structured data.\n")
    
    example_simple_type_registration()
    example_typed_output()
    example_shared_type()
    example_nested_types()
    example_validated_types()
    
    print("\n" + "=" * 60)
    print("✨ All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
