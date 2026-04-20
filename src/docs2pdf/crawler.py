import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class Crawler:
    """
    Asynchronous crawler for documentation websites.
    Respects hierarchy and domain boundaries.
    """

    def __init__(self, root_url: str, project_name: str, base_dir: Path = Path("projects")):
        self.root_url = root_url.rstrip("/") + "/"
        self.project_name = project_name
        self.project_dir = base_dir / project_name
        self.visited_urls: set[str] = set()
        self.root_domain = urlparse(root_url).netloc
        self.root_path = urlparse(self.root_url).path
        self._page_cache: dict[str, str] = {} # url -> html content

        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        (self.project_dir / "content").mkdir(exist_ok=True)
        (self.project_dir / "images").mkdir(exist_ok=True)

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is within the same domain and at the same or deeper hierarchy.
        """
        parsed = urlparse(url)

        # Check domain
        if parsed.netloc and parsed.netloc != self.root_domain:
            return False

        # Check hierarchy
        path = parsed.path if parsed.path else "/"
        return path.startswith(self.root_path)

    async def _fetch_page(self, url: str, client: httpx.AsyncClient | None = None) -> str | None:
        """Fetch page content with httpx, reusing client if provided and caching results."""
        if url in self._page_cache:
            return self._page_cache[url]

        if client is None:
            async with httpx.AsyncClient(follow_redirects=True) as local_client:
                return await self._fetch_page(url, client=local_client)

        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            html = response.text
            self._page_cache[url] = html
            return html
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _extract_title(self, html: str) -> str:
        """Extract page title using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()
        return "Untitled Page"

    async def _get_links_with_info(self, url: str, client: httpx.AsyncClient | None = None) -> list[dict[str, str]]:
        """Extract links from a page and resolve them."""
        html = await self._fetch_page(url, client=client)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        links = []

        for a in soup.find_all("a", href=True):
            absolute_url = urljoin(url, a["href"])
            clean_url = absolute_url.split("#")[0].rstrip("/") + "/"
            if self._is_valid_url(clean_url):
                links.append({
                    "url": clean_url,
                    "title": a.get_text().strip() or "No Title"
                })
        return links

    async def discover_hierarchy(self, max_depth: int = 5, client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
        """
        Build a hierarchical tree of discovered pages.
        Returns a flat list of dicts with parent_url references for easy tree building in TUI.
        """
        if client is None:
            async with httpx.AsyncClient(follow_redirects=True) as local_client:
                return await self.discover_hierarchy(max_depth=max_depth, client=local_client)

        discovered_pages: dict[str, dict[str, Any]] = {}
        queue: list[dict[str, Any]] = [{"url": self.root_url, "parent_url": None, "depth": 0}]

        while queue:
            current = queue.pop(0)
            url = current["url"]
            depth = current["depth"]

            if url in discovered_pages or depth > max_depth:
                continue

            html = await self._fetch_page(url, client=client)
            if not html:
                continue

            title = self._extract_title(html)
            discovered_pages[url] = {
                "url": url,
                "title": title,
                "parent_url": current["parent_url"],
            }

            # Find sub-links
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                absolute_url = urljoin(url, a["href"])
                clean_url = absolute_url.split("#")[0].rstrip("/") + "/"

                if self._is_valid_url(clean_url) and clean_url not in discovered_pages:
                    queue.append({
                        "url": clean_url,
                        "parent_url": url,
                        "depth": depth + 1
                    })

            await asyncio.sleep(0.05) # Be polite

        return list(discovered_pages.values())

    def _extract_content(self, html: str) -> str | None:
        """Extract clean content from HTML using trafilatura."""
        return trafilatura.extract(
            html,
            include_images=True,
            include_links=True,
            output_format="xml"
        )

    async def crawl_page(self, url: str, client: httpx.AsyncClient | None = None) -> None:
        """Download and save a single page's clean content."""
        if url in self.visited_urls:
            return

        filename = urlparse(url).path.strip("/").replace("/", "_") or "index"
        filepath = self.project_dir / "content" / f"{filename}.xml"
        
        if filepath.exists():
            self.visited_urls.add(url)
            return

        self.visited_urls.add(url)
        html = await self._fetch_page(url, client=client)
        if not html:
            return

        content = self._extract_content(html)
        if content:
            filepath.write_text(content, encoding="utf-8")

    async def run(self, selected_urls: set[str] | None = None, client: httpx.AsyncClient | None = None):
        """
        Main entry point for crawling.
        If selected_urls is provided, only crawl those.
        """
        if client is None:
            async with httpx.AsyncClient(follow_redirects=True) as local_client:
                await self.run(selected_urls=selected_urls, client=local_client)
                return

        if selected_urls:
            for url in selected_urls:
                await self.crawl_page(url, client=client)
        else:
            # Fallback to full recursive crawl
            queue = [self.root_url]
            while queue:
                current_url = queue.pop(0)
                if current_url in self.visited_urls:
                    continue
                await self.crawl_page(current_url, client=client)

                # Discovery for recursive mode
                html = await self._fetch_page(current_url, client=client)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        absolute_url = urljoin(current_url, a["href"])
                        clean_url = absolute_url.split("#")[0].rstrip("/") + "/"
                        if self._is_valid_url(clean_url) and clean_url not in self.visited_urls:
                            queue.append(clean_url)
                await asyncio.sleep(0.05)
