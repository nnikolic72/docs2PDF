import httpx
import pytest

from docs2pdf.crawler import Crawler


def test_is_valid_url():
    """Test that the crawler correctly filters URLs based on domain and hierarchy."""
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project")

    # Same domain, deeper hierarchy
    assert crawler._is_valid_url("https://example.com/docs/intro") is True
    assert crawler._is_valid_url("https://example.com/docs/chapter1/page") is True

    # Equal hierarchy
    assert crawler._is_valid_url("https://example.com/docs/") is True

    # Same domain, higher hierarchy
    assert crawler._is_valid_url("https://example.com/") is False
    assert crawler._is_valid_url("https://example.com/other") is False

    # Different domain
    assert crawler._is_valid_url("https://google.com/docs/") is False

@pytest.mark.asyncio
async def test_discover_hierarchy(respx_mock):
    """Test building a hierarchical tree of discovered pages."""
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project")

    # Home page with two links
    home_html = """
    <html>
        <head><title>Home</title></head>
        <body>
            <a href="https://example.com/docs/get-started/">Get Started</a>
            <a href="https://example.com/docs/core-concepts/">Core Concepts</a>
        </body>
    </html>
    """
    # Sub page with more links
    get_started_html = """
    <html>
        <head><title>Get Started</title></head>
        <body>
            <a href="https://example.com/docs/get-started/install/">Installation</a>
        </body>
    </html>
    """

    respx_mock.get(root_url).mock(return_value=httpx.Response(200, content=home_html))
    respx_mock.get("https://example.com/docs/get-started/").mock(return_value=httpx.Response(200, content=get_started_html))
    respx_mock.get("https://example.com/docs/core-concepts/").mock(return_value=httpx.Response(200, content="<html><title>Core</title></html>"))
    respx_mock.get("https://example.com/docs/get-started/install/").mock(return_value=httpx.Response(200, content="<html><title>Install</title></html>"))

    # We want a shallow discovery that builds the tree
    pages = await crawler.discover_hierarchy(max_depth=2)

    urls = [p['url'] for p in pages]
    assert root_url in urls
    assert "https://example.com/docs/get-started/" in urls
    assert "https://example.com/docs/get-started/install/" in urls

    # Check parent-child relationship (mocking what we expect in the list of dicts or objects)
    get_started = next(p for p in pages if p['url'] == "https://example.com/docs/get-started/")
    install = next(p for p in pages if p['url'] == "https://example.com/docs/get-started/install/")
    assert install['parent_url'] == get_started['url']
