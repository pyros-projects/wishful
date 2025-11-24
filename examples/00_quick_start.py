"""Executable examples for wishful.

Run with: `python examples.py`
Each example shows a small end-to-end flow. Requires API env vars set
per README (or WISHFUL_FAKE_LLM=1 for offline stub generation).
"""

import os
from pathlib import Path

import wishful


def heading(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def example_extract_emails():
    heading("Example: extract emails from text")
    text = "Contact us: team@example.com or sales@demo.dev"
    from wishful.static.text import extract_emails

    print(extract_emails(text))


def example_date_normalizer():
    heading("Example: normalize dates")
    from wishful.static.dates import to_yyyy_mm_dd

    print(to_yyyy_mm_dd("31.12.2025"))
    print(to_yyyy_mm_dd("12/25/2025"))


def example_nginx_logs():
    heading("Example: nginx log parser with inline context")
    # desired: parse standard nginx combined logs into list of dicts
    from wishful.static.logs import parse_nginx_logs

    sample = '127.0.0.1 - - [10/Oct/2025:13:55:36 +0000] "GET /index.html HTTP/1.1" 200 2326 "-" "curl/7.81.0"'
    records = parse_nginx_logs(sample)
    print(records)

def example_read_README():
    heading("Example: read README and count headers")
    # desired: loads text and counts headers
    from wishful.static.text import count_headers

    
    records = count_headers(path="README.md")
    print(records)

def example_primes():
    heading("Example: functions inside functions - sum of primes")
    from wishful.static.numbers import primes_from_to, sum_list

    
    sum = sum_list(list=primes_from_to(1, 100))
    print(sum)


def example_story():
    heading("Example: story generation with setting")
    from wishful.static.story import cosmic_horror_intro

    
    intro = cosmic_horror_intro(setting="a deserted amusement park", word_count_at_least=100)
    print(intro)


def example_cache_ops(tmp_dir: Path):
    heading("Example: cache inspection and regeneration")
    wishful.configure(cache_dir=tmp_dir)
    from wishful.static.utils import hello_world

    print("hello_world():", hello_world())
    print("cached files:", wishful.inspect_cache())
    wishful.regenerate("wishful.static.utils")
    print("after regenerate:", wishful.inspect_cache())


def main():
    # Make output deterministic in CI if desired
    if os.getenv("WISHFUL_FAKE_LLM") == "1":
        print("Using fake LLM stub responses (WISHFUL_FAKE_LLM=1)")

    example_extract_emails()
    example_date_normalizer()
    example_nginx_logs()
    example_read_README()
    example_primes()
    example_story()
    example_cache_ops(Path("/tmp/.wishful_examples"))


if __name__ == "__main__":
    main()
