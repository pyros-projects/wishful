"""Example 13: Advanced Explore - When LLMs Judge LLMs

This example demonstrates the truly wild possibilities when you combine
wishful.explore with wishful.dynamic:

1. LLM-as-Judge: Use a dynamic function to SCORE generated variants
2. Self-Improving Loops: The winner helps evaluate the next generation  
3. Multi-Criteria Selection: Combine automated tests with LLM judgment
4. Code Golf: Find the shortest implementation that still works

Run with: `uv run python examples/13_explore_advanced.py`

Warning: This example makes many LLM calls. Budget accordingly. 💸
"""

import time
import wishful

wishful.clear_cache()


def heading(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# =============================================================================
# Example 1: LLM-as-Judge - Let the LLM score code quality
# =============================================================================

def example_llm_as_judge():
    """Use wishful.dynamic to generate a scoring function that judges code."""
    heading("🧑‍⚖️ Example 1: LLM-as-Judge")
    
    print("The twist: We'll use wishful.dynamic to create a SCORING function")
    print("that evaluates code quality. LLMs judging LLMs. Very meta.\n")

    # First, let's create an LLM-powered code scorer
    # This function will be regenerated each time, seeing the actual code
    print("Step 1: Creating LLM-powered code quality scorer...")
    
    def llm_code_scorer(fn):
        """
        Score a function using LLM judgment.
        We pass the source code to a dynamic function that evaluates it.
        """
        source = getattr(fn, '__wishful_source__', None)
        if not source:
            return 50.0  # Neutral score
        
        # Use wishful.dynamic to judge the code!
        # The LLM sees the actual source and rates it
        import wishful.dynamic.code_review as reviewer
        
        # The reviewer function sees the source in its context
        # and returns a quality score from 0-100
        try:
            # desired: rate this code for readability, efficiency, and pythonic style
            # return a float score from 0 to 100
            score = reviewer.rate_code_quality(source)
            if isinstance(score, dict):
                return float(score.get('score', score.get('quality', 50)))
            return float(score) if score else 50.0
        except Exception as e:
            print(f"    LLM scorer error: {e}")
            return 50.0

    # Now explore with BOTH automated testing AND LLM judgment
    print("Step 2: Exploring with LLM scoring...\n")
    
    best = wishful.explore(
        "wishful.static.text.slugify",
        variants=4,
        test=lambda fn: (
            fn("Hello World") == "hello-world" and
            fn("  Multiple   Spaces  ") == "multiple-spaces" and
            fn("Special!@#Characters") in ["special-characters", "specialcharacters", "special---characters"]
        ),
        benchmark=llm_code_scorer,
        optimize="best_score",
    )
    
    print(f"\n✅ Best variant (LLM-approved!):")
    print(f"   Score: {best.__wishful_metadata__.get('benchmark_score', 'N/A')}")
    print(f"   Test: slugify('Hello World') = '{best('Hello World')}'")
    print(f"\n   Source preview:\n{best.__wishful_source__[:200]}...")


# =============================================================================
# Example 2: Code Golf - Find the shortest working implementation
# =============================================================================

def example_code_golf():
    """Find the most concise implementation that still works."""
    heading("⛳ Example 2: Code Golf")
    
    print("Goal: Find the SHORTEST implementation that passes all tests.")
    print("Because sometimes less is more.\n")

    def brevity_score(fn):
        """Score by inverse of code length. Shorter = higher score."""
        source = getattr(fn, '__wishful_source__', '')
        if not source:
            return 0.0
        # Count actual code characters (exclude excessive whitespace)
        lines = [line.strip() for line in source.split('\n') if line.strip()]
        code_length = sum(len(line) for line in lines)
        # Inverse score: shorter code = higher score
        # Typical functions are 50-300 chars, so 500 - length gives good range
        return max(0, 500 - code_length)

    winner = wishful.explore(
        "wishful.static.math.is_palindrome",
        variants=6,
        test=lambda fn: (
            fn(121) == True and
            fn(123) == False and
            fn(1) == True and
            fn(12321) == True and
            fn(-121) == False  # Negative numbers aren't palindromes
        ),
        benchmark=brevity_score,
        optimize="best_score",
    )
    
    source = winner.__wishful_source__
    print(f"\n✅ Most concise implementation:")
    print(f"   Length: {len(source)} characters")
    print(f"   Brevity score: {winner.__wishful_metadata__.get('benchmark_score', 'N/A')}")
    print(f"\n   Full source:\n{source}")


# =============================================================================
# Example 3: Self-Improving - Use the winner to help score the next round
# =============================================================================

def example_self_improving():
    """Run multiple rounds where each winner helps evaluate the next."""
    heading("🔄 Example 3: Self-Improving Loop")
    
    print("We'll run explore twice. The FIRST winner becomes part of")
    print("the benchmark for the SECOND round. Evolution in action.\n")

    # Round 1: Find a basic working implementation
    print("Round 1: Finding initial implementation...")
    
    round1_winner = wishful.explore(
        "wishful.static.algorithms.merge_sorted_lists",
        variants=3,
        test=lambda fn: (
            fn([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6] and
            fn([], [1, 2, 3]) == [1, 2, 3] and
            fn([1], []) == [1]
        ),
    )
    
    print(f"   Round 1 winner found!")
    
    # Round 2: Now benchmark AGAINST the round 1 winner
    print("\nRound 2: Finding faster implementation (benchmarked against Round 1)...")
    
    def relative_speed_score(fn):
        """Score based on speed relative to round 1 winner."""
        test_data = [
            (list(range(0, 1000, 2)), list(range(1, 1000, 2))),  # Large sorted lists
            (list(range(500)), list(range(500, 1000))),
        ]
        
        # Time the new function
        start = time.perf_counter()
        for a, b in test_data:
            for _ in range(10):
                fn(a.copy(), b.copy())
        new_time = time.perf_counter() - start
        
        # Time the round 1 winner
        start = time.perf_counter()
        for a, b in test_data:
            for _ in range(10):
                round1_winner(a.copy(), b.copy())
        baseline_time = time.perf_counter() - start
        
        # Score: how much faster than baseline (>1 = faster)
        return baseline_time / new_time if new_time > 0 else 1.0

    round2_winner = wishful.explore(
        "wishful.static.algorithms.merge_sorted_lists_v2",
        variants=4,
        test=lambda fn: (
            fn([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6] and
            fn([], [1, 2, 3]) == [1, 2, 3]
        ),
        benchmark=relative_speed_score,
        optimize="best_score",
    )
    
    speedup = round2_winner.__wishful_metadata__.get('benchmark_score', 1.0)
    print(f"\n✅ Self-improvement results:")
    print(f"   Speedup vs Round 1: {speedup:.2f}x")
    if speedup > 1:
        print("   🚀 Round 2 found a FASTER implementation!")
    else:
        print("   (Round 1 was already pretty optimal)")


# =============================================================================
# Example 4: Multi-Objective - Correctness + Performance + Style
# =============================================================================

def example_multi_objective():
    """Combine multiple scoring criteria into one mega-benchmark."""
    heading("🎯 Example 4: Multi-Objective Optimization")
    
    print("Scoring on THREE criteria:")
    print("  1. Speed (how fast)")
    print("  2. Brevity (how short)")
    print("  3. LLM quality score (how good)\n")

    def multi_objective_scorer(fn):
        """Combined score from multiple objectives."""
        scores = {}
        
        # 1. Speed score
        test_data = [i**2 for i in range(100)]
        start = time.perf_counter()
        for _ in range(100):
            fn(test_data.copy())
        speed = 100 / (time.perf_counter() - start + 0.001)
        scores['speed'] = min(speed, 10000)  # Cap at 10k
        
        # 2. Brevity score
        source = getattr(fn, '__wishful_source__', '')
        brevity = max(0, 500 - len(source)) if source else 0
        scores['brevity'] = brevity
        
        # 3. LLM quality (simplified - just check for docstring)
        has_docstring = '"""' in source or "'''" in source
        has_type_hints = '->' in source or ': ' in source
        quality = 0
        if has_docstring:
            quality += 50
        if has_type_hints:
            quality += 50
        scores['quality'] = quality
        
        # Weighted combination
        final = (
            scores['speed'] * 0.4 +
            scores['brevity'] * 0.3 +
            scores['quality'] * 0.3
        )
        
        print(f"    Variant scores: speed={scores['speed']:.0f}, "
              f"brevity={scores['brevity']}, quality={scores['quality']} → {final:.0f}")
        
        return final

    winner = wishful.explore(
        "wishful.static.algorithms.quicksort",
        variants=5,
        test=lambda fn: (
            fn([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9] and
            fn([]) == [] and
            fn([1]) == [1]
        ),
        benchmark=multi_objective_scorer,
        optimize="best_score",
    )
    
    print(f"\n✅ Multi-objective winner:")
    print(f"   Final score: {winner.__wishful_metadata__.get('benchmark_score', 'N/A'):.0f}")
    print(f"   Test: quicksort([3,1,4]) = {winner([3, 1, 4])}")


# =============================================================================
# Example 5: The Gauntlet - Real-world regex generator
# =============================================================================

def example_gauntlet():
    """Generate a regex pattern through exploration - a real challenge."""
    heading("🏋️ Example 5: The Gauntlet - Regex Generator")
    
    print("Challenge: Generate a function that validates email addresses.")
    print("This is notoriously hard to get right. Let's see how explore handles it.\n")

    # Comprehensive email test cases
    valid_emails = [
        "simple@example.com",
        "very.common@example.com",
        "user+tag@example.org",
        "user.name@example.co.uk",
        "test123@test-domain.com",
    ]
    
    invalid_emails = [
        "plainaddress",
        "@missinglocal.com",
        "missing@.com",
        "spaces in@email.com",
        "double..dots@email.com",
    ]

    def comprehensive_email_test(fn):
        """Test against known valid and invalid emails."""
        try:
            # All valid emails should return True
            for email in valid_emails:
                if not fn(email):
                    return False
            
            # All invalid emails should return False
            for email in invalid_emails:
                if fn(email):
                    return False
            
            return True
        except Exception:
            return False

    def robustness_score(fn):
        """Score based on handling edge cases."""
        edge_cases = [
            ("a@b.co", True),  # Minimal valid
            ("test@localhost", True),  # No TLD
            ("test@123.123.123.123", True),  # IP address
            (".start@email.com", False),  # Starts with dot
            ("end.@email.com", False),  # Ends with dot before @
            ("a" * 65 + "@toolong.com", False),  # Local part too long
        ]
        
        score = 0
        for email, expected in edge_cases:
            try:
                if fn(email) == expected:
                    score += 1
            except Exception:
                pass
        
        return score * 20  # Max 120

    winner = wishful.explore(
        "wishful.static.validation.is_valid_email",
        variants=5,
        test=comprehensive_email_test,
        benchmark=robustness_score,
        optimize="best_score",
        timeout_per_variant=45,  # Regex can be slow to generate
    )
    
    print(f"\n✅ Email validator found!")
    print(f"   Robustness score: {winner.__wishful_metadata__.get('benchmark_score', 0)}/120")
    print(f"\n   Testing:")
    for email in valid_emails[:3]:
        print(f"   '{email}' → {winner(email)}")
    for email in invalid_emails[:3]:
        print(f"   '{email}' → {winner(email)}")


# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("  🧪 ADVANCED EXPLORE: When LLMs Get Recursive")
    print("=" * 60)
    print("\nThis example pushes wishful.explore to its limits:")
    print("  • LLMs judging LLM-generated code")
    print("  • Self-improving loops")
    print("  • Multi-objective optimization")
    print("  • Real-world challenges")
    print("\n⚠️  Warning: Makes many LLM calls. Budget accordingly!")
    
    example_llm_as_judge()
    example_code_golf()
    example_self_improving()
    example_multi_objective()
    example_gauntlet()
    
    print("\n" + "=" * 60)
    print("  ✨ COMPLETE!")
    print("=" * 60)
    print("\nKey insights:")
    print("  • wishful.dynamic can BE the scoring function")
    print("  • Each winner can inform the next exploration")
    print("  • Multi-objective scoring combines speed, size, and quality")
    print("  • Real-world problems (like email regex) are tractable")
    print("\nThe recursive power of wishful is... wishful thinking made real. 🪄")
    print("=" * 60)


if __name__ == "__main__":
    main()

