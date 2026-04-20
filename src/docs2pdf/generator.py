import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from docs2pdf.database import Page

logger = logging.getLogger(__name__)

# Help WeasyPrint find libraries on macOS (Homebrew)
if sys.platform == "darwin":
    # Common Homebrew paths for Intel and Apple Silicon
    brew_paths = ["/opt/homebrew/lib", "/usr/local/lib"]
    existing_path = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    new_paths = [p for p in brew_paths if os.path.exists(p)]
    if new_paths:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(new_paths + ([existing_path] if existing_path else []))

try:
    from weasyprint import HTML
except (ImportError, OSError) as e:
    logger.error(f"WeasyPrint system libraries (Pango, Cairo) not found: {e}")
    logger.error("PDF generation will fail. Please install with: brew install weasyprint")
    HTML = MagicMock()  # type: ignore


class PDFGenerator:
    """
    Generates a single, beautiful PDF optimized for reMarkable Paper Pro.
    Handles breadcrumbs, internal link rewriting, and hierarchical merging.
    """

    def __init__(self, project_name: str, root_url: str = "", base_dir: Path | str | None = None):
        self.project_name = project_name
        self.root_url = root_url
        self.root_path = urlparse(root_url).path.rstrip("/")

        # Ensure base_dir is a Path
        if base_dir is None:
            self.project_dir = Path("projects") / project_name
        elif isinstance(base_dir, str):
            self.project_dir = Path(base_dir) / project_name
        else:
            self.project_dir = base_dir / project_name

        self.content_dir = self.project_dir / "content"
        self.url_to_id: dict[str, str] = {}

        # Setup Jinja2
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self._ensure_default_template()

    def _ensure_default_template(self):
        """Create the default PDF template with reMarkable Pro dimensions."""
        template_path = Path(__file__).parent / "templates" / "base.html"
        if not template_path.exists():
            template_path.write_text(
                """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: 1620px 2160px; /* reMarkable Paper Pro aspect ratio */
            margin: 60px;
        }
        body {
            font-family: serif;
            font-size: 18px;
            line-height: 1.5;
            color: #111;
        }
        .section {
            page-break-before: always;
        }
        .breadcrumbs {
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }
        .breadcrumbs a {
            color: #666;
            text-decoration: none;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
        }
        h1 { font-size: 32px; margin-top: 0; }
        h2 { font-size: 26px; }
        a { color: #004a99; }
    </style>
</head>
<body>
    {% for page in pages %}
    <div class="section" id="{{ page.anchor }}">
        <div class="breadcrumbs">
            {% for crumb in page.breadcrumbs %}
            <a href="#{{ crumb.anchor }}">{{ crumb.title }}</a>
            {% if not loop.last %} / {% endif %}
            {% endfor %}
        </div>
        <h1>{{ page.title }}</h1>
        <div class="content">
            {{ page.content | safe }}
        </div>
    </div>
    {% endfor %}
</body>
</html>
            """,
                encoding="utf-8",
            )

    def _slugify_url(self, url: str) -> str:
        """Create a unique anchor ID from a URL."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if path.startswith(self.root_path):
            path = path[len(self.root_path) :].lstrip("/")

        if not path:
            return "root"
        return path.replace("/", "_")

    def _rewrite_links(self, html_content: str, base_url: str) -> str:
        """Convert external documentation URLs to internal PDF anchors."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Ensure we keep the original heading levels
        # (Already handled by passing through HTML directly, but we ensure structure here)

        for a in soup.find_all("a", href=True):
            absolute_href = urljoin(base_url, a["href"])
            clean_href = absolute_href.split("#")[0].rstrip("/") + "/"
            if clean_href in self.url_to_id:
                # Point to the anchor of the page
                a["href"] = f"#{self.url_to_id[clean_href]}"
        return str(soup)

    def _get_breadcrumbs(self, page: Page, pages_by_id: dict[int, Page]) -> list[dict[str, str]]:
        """Generate a breadcrumb trail for a page."""
        crumbs = []
        current = page
        while current and current.parent_id:
            parent = pages_by_id.get(current.parent_id)
            if parent:
                crumbs.insert(0, {"title": parent.title, "anchor": self._slugify_url(parent.url)})
                current = parent
            else:
                break
        return crumbs

    def generate(self, selected_pages: list[Page], output_filename: str | None = None):
        """Merge selected pages and generate the final PDF."""
        if output_filename is None:
            # Use project name or fallback to documentation.pdf
            safe_name = self.project_dir.name.replace(" ", "_").lower()
            output_filename = f"{safe_name}.pdf"
        # Pre-calculate URL to Anchor mapping
        self.url_to_id = {p.url: self._slugify_url(p.url) for p in selected_pages}
        pages_by_id = {p.id: p for p in selected_pages if p.id is not None}

        render_data = []
        for page in selected_pages:
            # Read saved content from Phase 3
            filename = urlparse(page.url).path.strip("/").replace("/", "_") or "index"
            filepath = self.content_dir / f"{filename}.html"

            if not filepath.exists():
                logger.warning(f"Content file not found for {page.url}: {filepath}")
                continue

            raw_content = filepath.read_text(encoding="utf-8")

            rewritten_content = self._rewrite_links(raw_content, page.url)

            render_data.append(
                {
                    "title": page.title,
                    "anchor": self._slugify_url(page.url),
                    "breadcrumbs": self._get_breadcrumbs(page, pages_by_id),
                    "content": rewritten_content,
                }
            )

        # Render template
        template = self.env.get_template("base.html")
        full_html = template.render(pages=render_data)

        # Save HTML for debugging if needed
        # (self.project_dir / "debug.html").write_text(full_html, encoding="utf-8")

        # Generate PDF
        output_path = self.project_dir / output_filename
        base_url = Path.cwd().as_uri() + "/"
        HTML(string=full_html, base_url=base_url).write_pdf(output_path)
        return output_path
