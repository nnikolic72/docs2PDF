from pathlib import Path

from docs2pdf.generator import PDFGenerator


def reproduce():
    # Setup dummy project
    project_name = "repro_formatting"
    project_dir = Path("projects") / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    gen = PDFGenerator(project_name)

    # Create a dummy HTML content
    html_content = """
    <h1>Code Formatting Test</h1>
    <p>This is a paragraph with <code>inline code</code> inside it.</p>
    <p>Below is a multi-line code block:</p>
    <pre><code>def hello():
    print("Hello, World!")
    return True</code></pre>
    <p>Another paragraph after the block.</p>
    """

    # For the generator to work, it needs render_data which is a list of dicts
    render_data = [{"title": "Reproduction", "content": html_content, "breadcrumbs": ["Home", "Test"]}]

    # We can't easily call gen.generate() because it expects files on disk
    # and has a lot of side effects. Let's just render the template.
    template = gen.env.get_template("base.html")
    full_html = template.render(pages=render_data)

    output_path = project_dir / "repro.html"
    output_path.write_text(full_html, encoding="utf-8")
    print(f"Generated {output_path}")

    # Also try to generate PDF if weasyprint is available
    try:
        from weasyprint import HTML

        pdf_path = project_dir / "repro.pdf"
        HTML(string=full_html, base_url=str(Path.cwd())).write_pdf(pdf_path)
        print(f"Generated {pdf_path}")
    except ImportError:
        print("WeasyPrint not found, skipping PDF generation")
    except Exception as e:
        print(f"Error generating PDF: {e}")


if __name__ == "__main__":
    reproduce()
