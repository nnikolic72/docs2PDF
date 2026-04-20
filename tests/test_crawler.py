import httpx
import pytest

from docs2pdf.crawler import Crawler


@pytest.mark.asyncio
async def test_crawler_uses_provided_session(tmp_path):
    """Test that the crawler reuses a provided httpx.AsyncClient."""
    import httpx
    from unittest.mock import AsyncMock, MagicMock
    
    root_url = "https://example.com/docs/"
    # We use base_dir instead of project_dir as that is what Crawler expects
    crawler = Crawler(root_url, "test_project", base_dir=tmp_path)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><h1>Test</h1><p>Content</p></body></html>"
    
    # Mock the client
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    
    # Run crawl with the mock client
    import trafilatura
    from unittest.mock import patch
    with patch("trafilatura.extract", return_value="<content>Test</content>"):
        await crawler.crawl_page(root_url, client=mock_client)
    
    # Check if file was created
    filename = "docs.xml" # /docs/ becomes docs.xml
    content_file = tmp_path / "test_project" / "content" / filename
    assert content_file.exists()

@pytest.mark.asyncio
async def test_crawler_caches_pages(tmp_path):
    """Test that the crawler caches fetched pages."""
    import httpx
    from unittest.mock import AsyncMock, MagicMock
    
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project", base_dir=tmp_path)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><h1>Test</h1></body></html>"
    
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response
    
    # First fetch
    await crawler._fetch_page(root_url, client=mock_client)
    assert mock_client.get.call_count == 1
    
    # Second fetch should use cache
    await crawler._fetch_page(root_url, client=mock_client)
    assert mock_client.get.call_count == 1
    assert crawler._page_cache[root_url] == mock_response.text

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

    # Fragment/Query handling (should be normalized or ignored for crawling logic)
    assert crawler._is_valid_url("https://example.com/docs/intro#section") is True

@pytest.mark.asyncio
async def test_crawl_extracts_links(respx_mock):
    """Test that the crawler correctly extracts links from a page."""
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project")
    
    html = f"""
    <html>
        <body>
            <a href="{root_url}subpage">Sublink</a>
            <a href="/docs/relative">Relative</a>
        </body>
    </html>
    """

    # Mock the root page response
    respx_mock.get(root_url).mock(return_value=httpx.Response(200, content=html))

    links = await crawler._get_links_with_info(root_url)
    discovered_urls = [l["url"] for l in links]
    assert f"{root_url}subpage/" in discovered_urls
    assert f"{root_url}relative/" in discovered_urls

@pytest.mark.asyncio
async def test_crawl_respects_hierarchy(respx_mock):
    """Test that the crawler only queues valid links."""
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project")

    html = """
    <a href="https://example.com/docs/page1">Valid</a>
    <a href="https://example.com/other">Invalid</a>
    <a href="/docs/page2">Valid Relative</a>
    """
    respx_mock.get(root_url).mock(return_value=httpx.Response(200, content=html))

    # We'll need to mock the sub-pages too if we run a full crawl,
    # but for now let's just test the discovery phase.
    discovered = await crawler._get_links_with_info(root_url)
    discovered_urls = [d["url"] for d in discovered]
    assert "https://example.com/docs/page1/" in discovered_urls
    assert "https://example.com/docs/page2/" in discovered_urls
    assert "https://example.com/other/" not in discovered_urls
