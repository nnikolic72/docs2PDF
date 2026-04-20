import httpx
import pytest

from docs2pdf.crawler import Crawler


@pytest.mark.asyncio
async def test_discover_hierarchy_depth_6(respx_mock):
    """Test that discover_hierarchy can go up to 6 levels."""
    root_url = "https://example.com/docs/"
    crawler = Crawler(root_url, "test_project_depth")

    # Mock 7 levels of depth (0 to 6)
    for i in range(7):
        current_url = f"{root_url}level{i}/" if i > 0 else root_url
        next_url = f"{root_url}level{i + 1}/"
        html = f'<html><title>Level {i}</title><body><a href="{next_url}">Next</a></body></html>'
        respx_mock.get(current_url).mock(return_value=httpx.Response(200, content=html))

    # Level 7 should not be reached if max_depth is 6
    respx_mock.get(f"{root_url}level7/").mock(
        return_value=httpx.Response(200, content="<html><title>Level 7</title></html>")
    )

    pages = await crawler.discover_hierarchy(max_depth=6)

    urls = [p["url"] for p in pages]
    assert f"{root_url}" in urls
    assert f"{root_url}level6/" in urls
    assert f"{root_url}level7/" not in urls
    assert len(pages) == 7


@pytest.mark.asyncio
async def test_run_recursive_depth(respx_mock, tmp_path):
    """Test that Crawler.run respects max_depth when doing recursive crawl."""
    root_url = "https://example.com/docs/"
    # Use tmp_path for project_dir to avoid polluting projects/
    crawler = Crawler(root_url, "test_project_run", base_dir=tmp_path)

    # Mock 3 levels of depth
    for i in range(3):
        current_url = f"{root_url}level{i}/" if i > 0 else root_url
        next_url = f"{root_url}level{i + 1}/"
        html = f'<html><title>Level {i}</title><body><a href="{next_url}">Next</a></body></html>'
        respx_mock.get(current_url).mock(return_value=httpx.Response(200, content=html))

    # Level 3 should not be reached if max_depth is 2
    respx_mock.get(f"{root_url}level3/").mock(
        return_value=httpx.Response(200, content="<html><title>Level 3</title></html>")
    )

    await crawler.run(selected_urls=None, max_depth=2)

    assert root_url in crawler.visited_urls
    assert f"{root_url}level1/" in crawler.visited_urls
    assert f"{root_url}level2/" in crawler.visited_urls
    assert f"{root_url}level3/" not in crawler.visited_urls
