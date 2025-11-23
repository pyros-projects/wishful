"""Example: Web scraping helpers with wishful.

This demonstrates generating utilities for common web scraping tasks.
"""

# Desired: extract all links from HTML, clean URLs
from wishful.web import extract_links, clean_url

html = """
<html>
    <body>
        <a href="/about">About</a>
        <a href="https://example.com/blog?utm_source=test">Blog</a>
        <a href="mailto:test@example.com">Email</a>
    </body>
</html>
"""

links = extract_links(html)
print("Extracted links:", links)

# Clean a URL by removing query parameters
dirty_url = "https://example.com/page?utm_source=twitter&ref=abc123"
clean = clean_url(dirty_url)
print(f"\nCleaned URL: {clean}")
