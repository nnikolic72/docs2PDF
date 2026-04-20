import trafilatura

html = """<html>
<body>
<h1>Test Documentation</h1>
<p>This is a long paragraph about something important. It has enough words to be considered content by trafilatura. Here is a <a href="https://example.com/other-page">link to another page</a> that we should definitely keep.</p>
</body>
</html>"""

content = trafilatura.extract(html, include_links=True, include_formatting=True, output_format="xml")
print("XML:")
print(content)

content_html = trafilatura.extract(html, include_links=True, include_formatting=True, output_format="html")
print("HTML:")
print(content_html)
