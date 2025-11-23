"""
06_omg_why.py - Because we can, and that's reason enough.

This file demonstrates the absolute chaos you can unleash when you
stop asking "should I?" and start asking "what if?"
"""

# ========================================
# Mathematical Nonsense
# ========================================

from wishful.omg import nth_digit_of_pi, prime_factors, fibonacci_mod_cheese

print("=== Mathematical Chaos ===")
print(f"100th digit of π: {nth_digit_of_pi(100)}")
print(f"Prime factors of 3734775621: {prime_factors(3734775621)}")
# desired: return nth fibonacci number modulo 7919 (the 1000th prime, aka "cheese prime")
print(f"Fibonacci(50) mod cheese: {fibonacci_mod_cheese(50)}")

# ========================================
# String Crimes
# ========================================

from wishful.cursed import reverse_words_keep_punctuation, zalgo_text, uwuify

print("\n=== String Crimes ===")
text = "Hello, world! How are you?"
print(f"Original: {text}")
print(f"Reversed words: {reverse_words_keep_punctuation(text)}")
# desired: add combining diacritical marks to make text look possessed
print(f"Zalgo'd: {zalgo_text('HELLO')}")
# desired: convert text to uwu speak (replace r/l with w, add uwu/owo, etc)
print(f"UwUified: {uwuify('This is a serious business application')}")

# ========================================
# Time Travel Crimes
# ========================================

from wishful.time import day_of_week_for_any_date, seconds_until_christmas, unix_time_to_readable

print("\n=== Temporal Shenanigans ===")
# desired: return day of week (Monday, Tuesday, etc) for any YYYY-MM-DD date
print(f"What day was 2000-01-01? {day_of_week_for_any_date('2000-01-01')}")
print(f"Seconds until Christmas: {seconds_until_christmas()}")
print(f"Unix epoch as human time: {unix_time_to_readable(0)}")

# ========================================
# List Manipulation Madness
# ========================================

from wishful.lists import flatten_nested, rotate_list, chunk_by_size

print("\n=== List Crimes ===")
nested = [1, [2, 3, [4, 5]], 6, [[7]]]
print(f"Nested: {nested}")
print(f"Flattened: {flatten_nested(nested)}")
print(f"Rotate [1,2,3,4,5] by 2: {rotate_list([1,2,3,4,5], 2)}")
print(f"Chunk [1..10] by 3: {chunk_by_size(list(range(1,11)), 3)}")

# ========================================
# Color Space Nonsense
# ========================================

from wishful.colors import hex_to_rgb, rgb_to_hsl, complementary_color

print("\n=== Color Chaos ===")
print(f"#FF5733 to RGB: {hex_to_rgb('#FF5733')}")
print(f"RGB(255,87,51) to HSL: {rgb_to_hsl(255, 87, 51)}")
# desired: return the complementary color (opposite on color wheel) as hex
print(f"Complement of #FF5733: {complementary_color('#FF5733')}")

# ========================================
# The Truly Unhinged
# ========================================

from wishful.why import generate_fake_ipsum, random_excuse, rock_paper_scissors_lizard_spock

print("\n=== Peak Absurdity ===")
# desired: generate Lorem Ipsum style text but with random tech buzzwords
print(f"Fake ipsum: {generate_fake_ipsum(words=15)}")
# desired: generate a random plausible-sounding excuse for being late
print(f"Excuse generator: {random_excuse()}")
# desired: play rock-paper-scissors-lizard-spock, return winner explanation
result = rock_paper_scissors_lizard_spock("rock", "spock")
print(f"Rock vs Spock: {result}")

print("\n✨ If you're not questioning your life choices, you're not dreaming big enough.")
