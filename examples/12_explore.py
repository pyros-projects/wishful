"""Example: Using wishful.explore to generate multiple variants.

This example demonstrates how to generate multiple implementations of a function
and select the best one through testing or benchmarking.

Run with: `uv run python examples/12_explore.py`
"""

import time

import wishful

wishful.clear_cache()


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def example_basic():
    """Basic: Get first working implementation with progress display."""
    heading("Example 1: Basic - First Passing Variant")

    # Generate 3 variants with beautiful progress display!
    parser = wishful.explore(
        "wishful.static.text.extract_emails",
        variants=3,
        test=lambda fn: fn("test@example.com hello") == ["test@example.com"],
    )

    print(f"\n✅ Found working parser!")
    result = parser("Contact: alice@example.com, bob@test.org")
    print(f"Result: {result}")
    print(f"Metadata: {parser.__wishful_metadata__}")


def example_benchmark():
    """Benchmark: Find the fastest implementation."""
    heading("Example 2: Benchmark - Find Fastest")

    def benchmark_sort(fn):
        """Returns operations per second (higher = better)."""
        data = list(range(100, 0, -1))  # Reverse sorted
        start = time.perf_counter()
        for _ in range(50):
            fn(data.copy())
        elapsed = time.perf_counter() - start
        return 50 / elapsed  # ops/sec

    # Generate 5 variants, benchmark each, return fastest
    fastest_sort = wishful.explore(
        "wishful.static.algorithms.sort_integers",
        variants=5,
        benchmark=benchmark_sort,
        optimize="fastest",
    )

    print(f"\n✅ Found fastest sort!")
    result = fastest_sort([3, 1, 4, 1, 5, 9, 2, 6])
    print(f"Result: {result}")
    score = fastest_sort.__wishful_metadata__.get("benchmark_score")
    if score:
        print(f"Benchmark score: {score:.1f} ops/sec")


def example_combined():
    """Combined: Test for correctness, then benchmark for speed."""
    heading("Example 3: Test + Benchmark Combined")

    def is_correct(fn):
        """Verify the function returns correct results."""
        cases = [
            ([3, 1, 2], [1, 2, 3]),
            ([], []),
            ([1], [1]),
            ([5, 4, 3, 2, 1], [1, 2, 3, 4, 5]),
        ]
        return all(fn(list(inp)) == exp for inp, exp in cases)

    def speed_score(fn):
        """Measure performance."""
        data = list(range(200, 0, -1))
        start = time.perf_counter()
        for _ in range(20):
            fn(data.copy())
        return 1.0 / (time.perf_counter() - start)

    best = wishful.explore(
        "wishful.static.algorithms.sort_list",
        variants=5,
        test=is_correct,
        benchmark=speed_score,
        optimize="fastest",
    )

    print(f"\n✅ Found correct AND fast implementation!")
    print(f"Test: {best([5, 2, 8, 1, 9])}")


def example_silent():
    """Silent mode: No progress display, just results."""
    heading("Example 4: Silent Mode (verbose=False)")

    print("Running exploration silently...")

    fn = wishful.explore(
        "wishful.static.math.fibonacci",
        variants=3,
        test=lambda fn: fn(10) == 55 and fn(0) == 0 and fn(1) == 1,
        verbose=False,  # No progress display
    )

    print(f"✅ Done! Result for fib(10): {fn(10)}")


def example_error_handling():
    """Demonstrate error handling when no variant passes."""
    heading("Example 5: Error Handling")

    try:
        # This will fail - no LLM can make 1 == 2
        wishful.explore(
            "wishful.static.impossible.magic",
            variants=3,
            test=lambda fn: fn() == "impossible_to_generate",
        )
    except wishful.ExplorationError as e:
        print(f"\n❌ Caught ExplorationError!")
        print(f"  Attempts: {e.attempts}")
        print(f"  Failures: {len(e.failures)}")
        for failure in e.failures[:2]:
            print(f"    - {failure[:60]}...")


def main():
    print("🔍 wishful.explore - Generate Multiple Variants\n")
    print("Generate multiple implementations and select the best through")
    print("testing, benchmarking, or both!\n")

    example_basic()
    example_benchmark()
    example_combined()
    example_silent()
    example_error_handling()

    # Show where CSV results are saved
    print("\n" + "=" * 60)
    print("📊 CSV results saved to: .wishful/_explore/")
    print("=" * 60)

    # List the saved files
    explore_dir = wishful.settings.cache_dir / "_explore"
    if explore_dir.exists():
        print("\nSaved exploration files:")
        for f in sorted(explore_dir.glob("*.csv")):
            print(f"  📄 {f.name}")

    print("\n" + "=" * 60)
    print("✨ Key Takeaways:")
    print("  • explore() generates multiple variants of a function")
    print("  • Use test= to filter by correctness")
    print("  • Use benchmark= to select by performance")
    print("  • The winning variant is cached to .wishful/")
    print("  • verbose=True shows beautiful progress (default)")
    print("  • save_results=True exports to CSV (default)")
    print("=" * 60)


if __name__ == "__main__":
    main()
