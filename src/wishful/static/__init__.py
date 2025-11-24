"""Wishful static namespace - cached code generation.

Modules imported from wishful.static.* are generated once, cached to disk,
and reused on subsequent imports for optimal performance.

Example:
    from wishful.static.text import extract_emails
"""
