"""Example: Data validation and cleaning with wishful.

This demonstrates generating utilities for validating and cleaning messy data.
"""

# Desired: validate email format, sanitize user input, normalize whitespace
from wishful.static.validation import is_valid_email, sanitize_html, normalize_whitespace

# Email validation
emails = ["valid@example.com", "invalid@", "also@valid.co.uk", "nope"]
for email in emails:
    valid = is_valid_email(email)
    print(f"{email:25} -> {'✓ valid' if valid else '✗ invalid'}")

# Sanitize HTML input
dirty = "<script>alert('xss')</script><p>Hello <b>world</b>!</p>"
clean = sanitize_html(dirty)
print(f"\nSanitized HTML: {clean}")

# Normalize whitespace
messy = "  hello    world  \n\n  foo   bar  "
normal = normalize_whitespace(messy)
print(f"\nNormalized: '{normal}'")
