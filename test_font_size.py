import logging
from pathlib import Path

from docs2pdf.database import Page
from docs2pdf.generator import PDFGenerator

logging.basicConfig(level=logging.DEBUG)


def test_font():
    # Setup paths
    project_name = "FontTest"
    project_dir = Path("projects") / project_name
    content_dir = project_dir / "content"
    content_dir.mkdir(parents=True, exist_ok=True)

    # Create a dummy content file
    html_content = """
    <h1>Test Title</h1>
    <p>This is a paragraph with Bookerly font at 23px.</p>
    <pre><code>This is code with JetBrains Mono at 19px.</code></pre>
    """
    (content_dir / "index.html").write_text(html_content, encoding="utf-8")

    # Create a dummy Page object
    page = Page(id=1, project_id=1, url="https://example.com/", title="Test Page")

    # Initialize generator
    generator = PDFGenerator(project_name, root_url="https://example.com/")

    # Generate PDF
    output_path = generator.generate([page], "test_font.pdf")
    print(f"Generated PDF at: {output_path}")


if __name__ == "__main__":
    test_font()
