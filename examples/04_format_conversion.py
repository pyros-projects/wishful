"""Example: File format conversions with wishful.

This demonstrates generating utilities for converting between different file formats.
"""

# Desired: convert CSV to JSON, JSON to XML, dict to query string
from wishful.static.convert import csv_to_json, dict_to_query_string

csv_data = """name,age,city
Alice,30,NYC
Bob,25,LA
Charlie,35,Chicago"""

# Convert CSV to JSON
json_result = csv_to_json(csv_data)
print("CSV to JSON:")
print(json_result)

# Create URL query string from dict
params = {"search": "python tutorial", "page": 2, "filter": "recent"}
query = dict_to_query_string(params)
print(f"\nQuery string: {query}")
