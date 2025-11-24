"""Example demonstrating wishful.static.* vs wishful.dynamic.* namespaces.

This example shows the difference between:
- wishful.static.* : Cached generation (generated once, reused)
- wishful.dynamic.* : Runtime generation (regenerated every time with context)

Run with: `uv run python examples/08_dynamic_vs_static.py`
"""

import os
import wishful


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def example_static_cached():
    heading("Example 1: Static (Cached) Behavior")
    
    print("First import - generates code:")
    from wishful.static.greetings import say_hello
    result1 = say_hello("Alice")
    print(f"  Result: {result1}")
    
    print("\nSecond import - uses cache, same result:")
    # Use wishful.reimport() to re-import the module
    greetings = wishful.reimport('wishful.static.greetings')
    result2 = greetings.say_hello("Bob")
    print(f"  Result: {result2}")
    print("  (Same function definition, just different input)")


def example_dynamic_runtime():
    heading("Example 2: Dynamic (Runtime Context) Behavior")
    
    print("Dynamic generation sees runtime arguments:")
    print("\nCalling with topic='space':")
    from wishful.dynamic.ideas import generate_project_idea
    idea1 = generate_project_idea(topic="space")
    print(f"  Result: {idea1}")
    
    print("\nCalling with topic='cooking' (regenerates with new context):")
    # Use wishful.reimport() for fresh generation with new context
    ideas = wishful.reimport('wishful.dynamic.ideas')
    idea2 = ideas.generate_project_idea(topic="cooking")
    print(f"  Result: {idea2}")
    print("  (LLM sees the actual argument values during generation!)")

    print("\nCalling with topic='python ai library':")
    # Each reimport regenerates with fresh context
    ideas = wishful.reimport('wishful.dynamic.ideas')
    idea3 = ideas.generate_project_idea(topic="python ai library")
    print(f"  Result: {idea3}")


def example_why_static():
    heading("Example 3: When to Use Static")
    
    print("Use wishful.static.* for:")
    print("  ✓ Utilities that don't depend on runtime values")
    print("  ✓ Parsers, validators, formatters")
    print("  ✓ Performance (generated once, cached forever)")
    print()
    
    from wishful.static.text import extract_emails
    text = "Contact: alice@example.com or bob@test.org"
    emails = extract_emails(text)
    print(f"Extract emails: {emails}")
    print("(This function definition won't change, so cache it!)")


def example_why_dynamic():
    heading("Example 4: When to Use Dynamic")
    
    print("Use wishful.dynamic.* for:")
    print("  ✓ Functions that should 'hardcode' runtime values")
    print("  ✓ Generating creative content based on specific inputs")
    print("  ✓ Context-aware behavior")
    print()
    
    print("Generating a story opening with specific setting:")
    from wishful.dynamic.stories import create_opening
    opening = create_opening(
        genre="sci-fi",
        setting="abandoned space station",
        protagonist="a lone engineer"
    )
    print(f"Result: {opening}")
    print("\n(The LLM saw those exact values and generated accordingly!)")


def example_namespace_isolation():
    heading("Example 5: Namespace Isolation")
    
    print("Internal wishful.* modules (core, cache, etc.) are protected:")
    print("  wishful.cache      ✓ Internal module")
    print("  wishful.config     ✓ Internal module")
    print("  wishful.types      ✓ Internal module")
    print()
    print("Your generated code lives in namespaces:")
    print("  wishful.static.*   ✓ Your cached functions")
    print("  wishful.dynamic.*  ✓ Your runtime-aware functions")
    print()
    print("This prevents naming conflicts!")


def main():
    if os.getenv("WISHFUL_FAKE_LLM") == "1":
        print("Using fake LLM stub responses (WISHFUL_FAKE_LLM=1)")
        print("Note: Fake mode doesn't show the full power of dynamic generation\n")
    
    print("\n🪄 Static vs Dynamic Namespaces in Wishful\n")
    
    example_static_cached()
    example_dynamic_runtime()
    example_why_static()
    example_why_dynamic()
    example_namespace_isolation()
    
    print("\n" + "=" * 60)
    print("✨ Key Takeaway:")
    print("  • wishful.static.*  → Generate once, cache, reuse")
    print("  • wishful.dynamic.* → See runtime context, regenerate")
    print("=" * 60)


if __name__ == "__main__":
    main()
