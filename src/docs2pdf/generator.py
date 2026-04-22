import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

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
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape(["html", "xml"])
        )
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
        @font-face {
            font-family: 'Bookerly';
            src: url('fonts/bookerly/Bookerly.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
        }
        @font-face {
            font-family: 'Bookerly';
            src: url('fonts/bookerly/Bookerly Bold.ttf') format('truetype');
            font-weight: bold;
            font-style: normal;
        }
        @font-face {
            font-family: 'Bookerly';
            src: url('fonts/bookerly/Bookerly Italic.ttf') format('truetype');
            font-weight: normal;
            font-style: italic;
        }
        @font-face {
            font-family: 'Bookerly';
            src: url('fonts/bookerly/Bookerly Bold Italic.ttf') format('truetype');
            font-weight: bold;
            font-style: italic;
        }
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('fonts/jetbrains-mono/JetbrainsMonoRegular-RpvmM.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
        }
        @font-face {
            font-family: 'JetBrains Mono';
            src: url('fonts/jetbrains-mono/JetbrainsMonoBold-51Xez.ttf') format('truetype');
            font-weight: bold;
            font-style: normal;
        }

        @page {
            size: 1620px 2160px; /* reMarkable Paper Pro aspect ratio */
            margin: 80px;
        }

        @page :first {
            margin: 0;
        }

        body {
            font-family: 'Bookerly', serif;
            font-size: 30px;
            line-height: 1.6;
            color: #111;
            margin: 0;
            padding: 0;
        }

        /* Cover Page */
        .cover-page {
            width: 1620px;
            height: 2160px;
            page-break-after: always;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            color: white;
            background-color: #333;
            {% if cover_image %}
            background-image: url('{{ cover_image }}');
            background-size: cover;
            background-position: center;
            {% endif %}
        }

        .cover-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.3);
            z-index: 1;
        }

        .cover-content {
            position: relative;
            z-index: 2;
            padding: 100px;
            background: rgba(0, 0, 0, 0.4);
            border-radius: 20px;
            backdrop-filter: blur(5px);
            max-width: 80%;
        }

        .cover-title {
            font-size: 100px;
            font-weight: bold;
            margin-bottom: 20px;
            line-height: 1.1;
        }

        .cover-subtitle {
            font-size: 50px;
            font-weight: normal;
            opacity: 0.9;
        }

        /* TOC */
        .toc-page {
            page-break-before: always;
            page-break-after: always;
        }

        .toc-title {
            font-size: 60px;
            margin-bottom: 60px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
        }

        .toc-list {
            list-style: none;
            padding: 0;
        }

        .toc-item {
            margin-bottom: 15px;
        }

        .toc-item a {
            text-decoration: none;
            color: #111;
            display: block;
        }

        .toc-item a::after {
            content: leader(dotted) " " target-counter(attr(href), page);
        }

        .toc-level-0 { font-weight: bold; font-size: 34px; margin-top: 30px; }
        .toc-level-1 { margin-left: 40px; font-size: 30px; }
        .toc-level-2 { margin-left: 80px; font-size: 28px; color: #444; }
        .toc-level-3 { margin-left: 120px; font-size: 26px; color: #666; }

        /* General Content */
        .section {
            page-break-before: always;
        }

        .breadcrumbs {
            font-size: 20px;
            color: #666;
            margin-bottom: 20px;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
        }

        .breadcrumbs a {
            color: #666;
            text-decoration: none;
        }

        h1 { font-size: 52px; margin-top: 0; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        h2 { font-size: 44px; margin-top: 50px; }
        h3 { font-size: 36px; margin-top: 40px; }

        pre {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            background-color: #f8f8f8;
            padding: 25px;
            border-radius: 12px;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 30px 0;
            border: 1px solid #eee;
        }

        code {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
            background-color: #f0f0f0;
            padding: 4px 8px;
            border-radius: 6px;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 40px auto;
            border-radius: 8px;
        }

        a { color: #004a99; text-decoration: none; }
        p { margin: 25px 0; }
        li { margin: 10px 0; }
    </style>
</head>
<body>
    <div class="cover-page">
        <div class="cover-overlay"></div>
        <div class="cover-content">
            <div class="cover-title">{{ project_name }}</div>
            <div class="cover-subtitle">Documentation</div>
        </div>
    </div>

    <div class="toc-page" id="toc">
        <div class="toc-title">Table of Contents</div>
        <ul class="toc-list">
            {% for page in pages %}
                <li class="toc-item toc-level-{{ page.level }}">
                    <a href="#{{ page.anchor }}" class="toc-link">{{ page.title }}</a>
                </li>
            {% endfor %}
        </ul>
    </div>

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
        (self.project_dir / "debug.html").write_text(full_html, encoding="utf-8")

        # Generate PDF
        output_path = self.project_dir / output_filename
        base_url = Path.cwd().as_uri() + "/"
        HTML(string=full_html, base_url=base_url).write_pdf(output_path)
        return output_path
