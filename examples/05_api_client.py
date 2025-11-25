"""Example: Simple API client generation with wishful.

This demonstrates using context hints to generate a basic HTTP client.

Run with: `uv run python examples/05_api_client.py`
"""

# Desired: make a GET request with headers, parse JSON response, handle errors gracefully
from wishful.static.http import fetch_json, post_json

try:
    # Fetch JSON from a URL
    data = fetch_json("https://api.github.com/users/octocat")
    print("Fetched user data:", data)
except Exception as e:
    print(f"Error: {e}")

# POST JSON data
payload = {"title": "Test", "body": "Hello world"}
try:
    response = post_json("https://httpbin.org/post", payload)
    print("\nPOST response:", response)
except Exception as e:
    print(f"Error: {e}")
