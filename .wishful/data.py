import json
from typing import Any, Dict, Optional

def parse_json_safe(json_str: str) -> Optional[Any]:
    """
    Safely parse a JSON string. Returns the parsed object,
    or None if parsing fails.
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None

def dict_to_yaml(data: Dict[str, Any]) -> str:
    """
    Convert a dictionary to a simple YAML string.
    Only supports flat dictionaries with basic types.
    """
    lines = []
    for key, value in data.items():
        if isinstance(value, bool):
            val_str = 'true' if value else 'false'
        elif value is None:
            val_str = 'null'
        else:
            val_str = str(value)
        lines.append(f"{key}: {val_str}")
    return '\n'.join(lines)