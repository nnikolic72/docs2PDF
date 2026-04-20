import httpx
from bs4 import BeautifulSoup

from docs2pdf.crawler import Crawler


async def test_link_discovery(url):
    print(f"Testing discovery for: {url}")
    crawler = Crawler(url, "test_discovery")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        html = await crawler._fetch_page(url, client=client)
        if not html:
            print("Failed to fetch page")
            return

        soup = BeautifulSoup(html, "html.parser")
        all_links = soup.find_all("a", href=True)
        print(f"Total <a> tags found: {len(all_links)}")

        valid_links = []
        for a in all_links:
            from urllib.parse import urljoin

            abs_url = urljoin(url, a["href"])
            clean_url = abs_url.split("#")[0].rstrip("/")
            # Add trailing slash for comparison if it's a directory-like URL
            if not clean_url.split("/")[-1].count("."):
                clean_url += "/"

            if crawler._is_valid_url(clean_url):
                valid_links.append(clean_url)

        print(f"Valid links according to _is_valid_url: {len(set(valid_links))}")
        for link in sorted(set(valid_links))[:10]:
            print(f"  - {link}")


if __name__ == "__main__":
    # Test with a known documentation site if possible, or a local mock
    # Since I can't guarantee external access, I'll just check the logic with a mock
    pass
