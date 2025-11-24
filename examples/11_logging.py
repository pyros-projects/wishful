"""Example: JSON and YAML parsing with wishful.

This demonstrates using wishful to generate utilities for working with
structured data formats like JSON and YAML.
"""


import wishful


# Set up logging/cache before importing generated modules
#wishful.clear_cache()
wishful.configure(debug=True)

# Desired: parse JSON with automatic type conversion and validation
from wishful.static.data import parse_json_safe, dict_to_yaml


json_str = '{"name": "Alice", "age": 30, "active": true}'
data = parse_json_safe(json_str)
print("Parsed JSON:", data)

# Convert to YAML format
yaml_output = dict_to_yaml(data)
print("\nAs YAML:")
print(yaml_output)
