import asyncio
import logging
from collections.abc import Callable
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

    def __init__(
        self,
        root_url: str,
        project_name: str,
        base_dir: Path = Path("projects"),
        exclude_patterns: list[str] | None = None,
    ):
        # Parse multiple URLs
        raw_urls = root_url.split(" ")
        self.root_urls = []
        for u in raw_urls:
            clean_u = u.split("#")[0].rstrip("/")
            if not clean_u.split("/")[-1].count("."):
                clean_u += "/"
            self.root_urls.append(clean_u)

        self.root_url = self.root_urls[0]  # Use first URL for domain logic
        self.project_name = project_name
        self.project_dir = base_dir / project_name
        self.visited_urls: set[str] = set()
        self.exclude_patterns = exclude_patterns or []
        parsed_root = urlparse(self.root_url)
        self.root_domain = parsed_root.netloc

        # Base path for hierarchy: the directory containing the root URL
        path = parsed_root.path if parsed_root.path else "/"
        if "/" in path:
            self.base_path = path.rsplit("/", 1)[0] + "/"
        else:
            self.base_path = "/"

        self._page_cache: dict[str, str] = {}  # url -> html content
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }

        # Ensure project directory exists
        self.project_dir.mkdir(parents=True, exist_ok=True)
        (self.project_dir / "content").mkdir(exist_ok=True)
        (self.project_dir / "images").mkdir(exist_ok=True)

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if the URL is within the same domain, at the same or deeper hierarchy,
        and does not match any exclude patterns.
        """
        # Explicitly pasted URLs are always valid
        if url in self.root_urls:
            return True

        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if pattern and pattern in url:
                return False

        parsed = urlparse(url)

        # Check domain
        if parsed.netloc and parsed.netloc != self.root_domain:
            return False

        # Check hierarchy: must be at or below base_path
        path = parsed.path if parsed.path else "/"
        return path.startswith(self.base_path)

    async def _fetch_page(self, url: str, client: httpx.AsyncClient | None = None) -> str | None:
        """Fetch page content with httpx, reusing client if provided and caching results."""
        if url in self._page_cache:
            return self._page_cache[url]

        if client is None:
            async with httpx.AsyncClient(follow_redirects=True, headers=self.headers) as local_client:
                return await self._fetch_page(url, client=local_client)

        try:
            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            html = response.text
            self._page_cache[url] = html
            return html
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _clean_url(self, url: str) -> str:
        """Normalize URL by removing fragments and ensuring consistent trailing slashes for directories."""
        url = url.split("#")[0].rstrip("/")
        if not url.split("/")[-1].count("."):
            url += "/"
        return url

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
            clean_url = self._clean_url(absolute_url)
            if self._is_valid_url(clean_url):
                links.append({"url": clean_url, "title": a.get_text().strip() or "No Title"})
        return links

    async def discover_hierarchy(
        self,
        max_depth: int = 6,
        client: httpx.AsyncClient | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build a hierarchical tree of discovered pages.
        Returns a flat list of dicts with parent_url references for easy tree building in TUI.
        """
        if client is None:
            async with httpx.AsyncClient(follow_redirects=True, headers=self.headers) as local_client:
                return await self.discover_hierarchy(max_depth=max_depth, client=local_client, on_progress=on_progress)

        discovered_pages: dict[str, dict[str, Any]] = {}
        queue: list[dict[str, Any]] = [
            {"url": self._clean_url(u), "parent_url": None, "depth": 0} for u in self.root_urls
        ]

        while queue:
            current = queue.pop(0)
            url = current["url"]
            depth = current["depth"]

            if url in discovered_pages or depth > max_depth:
                continue

            if on_progress:
                on_progress(url, "downloading")

            html = await self._fetch_page(url, client=client)
            if not html:
                if on_progress:
                    on_progress(url, "error")
                continue

            if on_progress:
                on_progress(url, "done")

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
                clean_url = self._clean_url(absolute_url)

                if self._is_valid_url(clean_url) and clean_url not in discovered_pages:
                    queue.append({"url": clean_url, "parent_url": url, "depth": depth + 1})

            await asyncio.sleep(0.05)  # Be polite

        return list(discovered_pages.values())

    def _extract_content(self, html: str) -> str | None:
        """Extract clean content from HTML using trafilatura."""
        content = trafilatura.extract(
            html, include_images=True, include_links=True, include_formatting=True, output_format="html"
        )
        if not content:
            return None

        # Post-process to fix trafilatura converting all code to <pre>
        soup = BeautifulSoup(content, "html.parser")

        # 1. pre inside p should be code (inline)
        for p in soup.find_all("p"):
            for pre in p.find_all("pre"):
                pre.name = "code"

        # 2. pre inside pre should be pre > code (block)
        for pre in soup.find_all("pre"):
            inner_pre = pre.find("pre")
            if inner_pre:
                inner_pre.name = "code"

        return str(soup)

    async def crawl_page(
        self, url: str, client: httpx.AsyncClient | None = None, on_progress: Callable[[str, str], None] | None = None
    ) -> None:
        """Download and save a single page's clean content."""
        if url in self.visited_urls:
            return

        filename = urlparse(url).path.strip("/").replace("/", "_") or "index"
        filepath = self.project_dir / "content" / f"{filename}.html"

        if filepath.exists():
            self.visited_urls.add(url)
            if on_progress:
                on_progress(url, "done")
            return

        if on_progress:
            on_progress(url, "downloading")

        self.visited_urls.add(url)
        html = await self._fetch_page(url, client=client)
        if not html:
            if on_progress:
                on_progress(url, "error")
            return

        try:
            content = self._extract_content(html)
            if content:
                filepath.write_text(content, encoding="utf-8")
                if on_progress:
                    on_progress(url, "done")
            else:
                if on_progress:
                    on_progress(url, "error")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            if on_progress:
                on_progress(url, "error")

    async def run(
        self,
        selected_urls: set[str] | None = None,
        max_depth: int = 6,
        client: httpx.AsyncClient | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ):
        """
        Main entry point for crawling.
        If selected_urls is provided, only crawl those.
        """
        if client is None:
            async with httpx.AsyncClient(follow_redirects=True, headers=self.headers) as local_client:
                await self.run(
                    selected_urls=selected_urls, max_depth=max_depth, client=local_client, on_progress=on_progress
                )
                return

        if selected_urls:
            for url in selected_urls:
                await self.crawl_page(url, client=client, on_progress=on_progress)
                await asyncio.sleep(0.05)  # Be polite
        else:
            # Fallback to full recursive crawl
            queue: list[dict[str, Any]] = [{"url": self._clean_url(u), "depth": 0} for u in self.root_urls]
            while queue:
                current = queue.pop(0)
                current_url = current["url"]
                depth = current["depth"]

                if current_url in self.visited_urls or depth > max_depth:
                    continue

                await self.crawl_page(current_url, client=client, on_progress=on_progress)

                # Discovery for recursive mode
                html = await self._fetch_page(current_url, client=client)
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        absolute_url = urljoin(current_url, a["href"])
                        clean_url = self._clean_url(absolute_url)
                        if self._is_valid_url(clean_url) and clean_url not in self.visited_urls:
                            queue.append({"url": clean_url, "depth": depth + 1})
                await asyncio.sleep(0.05)
