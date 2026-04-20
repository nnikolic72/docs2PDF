import trafilatura
from trafilatura.settings import use_config

config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")
html = """<html>
<body>
<h1>Test Documentation</h1>
<p>This is a long paragraph about something important. It has enough words to be considered content by trafilatura. Here is a <a href="https://example.com/other-page">link to another page</a> that we should definitely keep.</p>
</body>
</html>"""

# Let's try passing config to extract
content = trafilatura.extract(html, include_links=True, include_formatting=True, config=config, output_format="xml")
print("XML with config:")
print(content)
