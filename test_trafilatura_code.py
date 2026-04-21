import trafilatura
from bs4 import BeautifulSoup

html = """
<html>
<body>
<h1>My Super Content Page</h1>
<p>This is a paragraph with <code>inline code</code> inside it. We should see if it works.</p>
<p>Below is a multi-line code block:</p>
<pre><code>def hello():
    print("Hello, World!")
    return True</code></pre>
</body>
</html>
"""

content = trafilatura.extract(html, include_links=True, include_formatting=True, output_format="html")
print("Original Trafilatura Output:")
print(content)

soup = BeautifulSoup(content, "html.parser")

# Fix 1: pre inside p -> code
for p in soup.find_all("p"):
    for pre in p.find_all("pre"):
        pre.name = "code"

# Fix 2: pre inside pre -> pre > code
for pre in soup.find_all("pre"):
    if pre.find("pre"):
        inner_pre = pre.find("pre")
        inner_pre.name = "code"

print("\nProcessed Output:")
print(soup.prettify())
