import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock weasyprint before importing PDFGenerator if it fails
try:
    pass
except OSError:
    sys.modules["weasyprint"] = MagicMock()

from docs2pdf.database import Page
from docs2pdf.generator import PDFGenerator


@pytest.fixture
def generator(tmp_path: Path):
    return PDFGenerator(project_name="test_project", base_dir=tmp_path)


def test_slugify_url():
    """Test generating a unique anchor ID from a URL."""
    generator = PDFGenerator("test", root_url="https://example.com/docs/", base_dir=Path("."))
    url = "https://example.com/docs/get-started/install/"
    slug = generator._slugify_url(url)
    assert slug == "get-started_install"

    # Root URL
    assert generator._slugify_url("https://example.com/docs/") == "root"


def test_rewrite_links():
    """Test rewriting HTML links to internal PDF anchors."""
    gen = PDFGenerator("test", root_url="https://example.com/docs/", base_dir=Path("."))
    # Define a map of URLs to their internal IDs
    gen.url_to_id = {
        "https://example.com/docs/": "root",
        "https://example.com/docs/get-started/": "get-started",
    }

    html = '<a href="https://example.com/docs/get-started/">Link</a> and <a href="https://google.com">External</a>'
    rewritten = gen._rewrite_links(html, "https://example.com/docs/")

    assert '<a href="#get-started">Link</a>' in rewritten
    assert '<a href="https://google.com">External</a>' in rewritten


def test_get_breadcrumbs():
    """Test generating a breadcrumb list for a page."""
    gen = PDFGenerator("test", root_url="url/", base_dir=Path("."))

    # Mock some page objects
    p1 = Page(id=1, project_id=1, url="url/", title="Home", parent_id=None)
    p2 = Page(id=2, project_id=1, url="url/a/", title="Level A", parent_id=1)
    p3 = Page(id=3, project_id=1, url="url/a/b/", title="Level B", parent_id=2)

    pages_by_id = {1: p1, 2: p2, 3: p3}

    crumbs = gen._get_breadcrumbs(p3, pages_by_id)

    assert len(crumbs) == 2  # Home and Level A
    assert crumbs[0]["title"] == "Home"
    assert crumbs[1]["title"] == "Level A"
    assert crumbs[0]["anchor"] == gen._slugify_url("url/")
