"""
POC: Test Crawl4AI's link extraction capability for sites without sitemaps.

This script explores whether Crawl4AI can provide better website analysis
than sitemap parsing alone, especially for sites like Reddit that don't
provide sitemaps.

Parameterized to test different websites and link extraction strategies.
"""

import asyncio
import json
import sys
import logging
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Try to import crawl4ai
try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("Crawl4AI not available. Install with: uv add crawl4ai")


class WebLinkExtractor:
    """Extract and analyze links from a website using Crawl4AI."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Initialize link extractor.

        Args:
            base_url: Starting URL to crawl
            timeout: Timeout per page in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.parsed_base = urlparse(self.base_url)
        self.base_domain = self.parsed_base.netloc

    async def extract_links_from_page(
        self,
        url: str,
        crawler: AsyncWebCrawler,
        max_links: int = 100
    ) -> List[str]:
        """
        Extract all internal links from a single page using Crawl4AI.

        Args:
            url: URL to crawl
            crawler: AsyncWebCrawler instance
            max_links: Maximum links to extract (for performance)

        Returns:
            List of absolute URLs found on the page
        """
        try:
            logger.info(f"  Crawling: {url}")
            config = CrawlerRunConfig(
                word_count_threshold=10,
                remove_overlay_elements=True,
                page_timeout=self.timeout * 1000,  # Convert to milliseconds
                exclude_external_links=True,
            )

            result = await crawler.arun(url, config)

            if not result.success:
                logger.warning(f"    Failed to crawl: {result.error_message}")
                return []

            # Update base domain if we were redirected
            # This handles cases like golang.org -> go.dev
            actual_url = result.url if hasattr(result, 'url') else url
            if actual_url != url:
                self.base_domain = urlparse(actual_url).netloc
                logger.info(f"    (Redirected from {urlparse(url).netloc} to {self.base_domain})")

            # Extract links from result.links (Crawl4AI provides structured link data)
            links = []
            if hasattr(result, 'links') and result.links:
                # result.links is a dict with 'internal' and 'external' keys
                internal_links = result.links.get("internal", [])

                for link_item in internal_links[:max_links]:
                    # Link items are dicts with 'href' key
                    if isinstance(link_item, dict):
                        link = link_item.get("href", "")
                    elif isinstance(link_item, str):
                        link = link_item
                    else:
                        link = str(link_item)

                    if link and link not in links:  # Avoid duplicates
                        # Convert to absolute URL
                        absolute_url = urljoin(url, link)
                        if self._is_internal_link(absolute_url):
                            links.append(absolute_url)

            logger.info(f"    Found {len(links)} internal links")
            return links

        except Exception as e:
            logger.error(f"    Error crawling {url}: {e}")
            return []

    def _is_internal_link(self, url: str) -> bool:
        """
        Check if URL is internal to the base domain.

        Handles redirects and domain variations:
        - example.com and www.example.com are both internal
        - example.com and api.example.com are both internal
        - But example.com and othersite.com are not
        """
        parsed = urlparse(url)
        url_domain = parsed.netloc

        # Exact match
        if url_domain == self.base_domain:
            return True

        # Handle www prefix variations
        base_without_www = self.base_domain.lstrip('www.')
        url_without_www = url_domain.lstrip('www.')

        if url_without_www == base_without_www:
            return True

        # Handle subdomains of same parent
        # e.g., api.example.com and docs.example.com share example.com
        if '.' in base_without_www and '.' in url_without_www:
            base_parts = base_without_www.split('.')
            url_parts = url_without_www.split('.')
            # Check if they share the same root domain
            if base_parts[-2:] == url_parts[-2:]:
                return True

        return False

    def group_links_by_pattern(self, links: List[str]) -> Dict[str, List[str]]:
        """Group discovered links by path pattern."""
        groups: Dict[str, List[str]] = defaultdict(list)

        for url in links:
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')
            if not path or path == '/':
                pattern = "/"
            else:
                segments = path.split('/')
                pattern = f"/{segments[1]}" if len(segments) > 1 else "/"

            groups[pattern].append(url)

        return dict(groups)

    def get_pattern_stats(self, url_groups: Dict[str, List[str]]) -> Dict[str, Dict]:
        """Calculate statistics for each URL pattern group."""
        stats = {}

        for pattern, urls in url_groups.items():
            # Calculate average path depth
            depths = []
            for url in urls:
                parsed = urlparse(url)
                path = parsed.path.rstrip('/')
                depth = len([s for s in path.split('/') if s])
                depths.append(depth)

            avg_depth = sum(depths) / len(depths) if depths else 0

            # Get up to 3 example URLs (shortest ones)
            sorted_urls = sorted(urls, key=lambda u: len(urlparse(u).path))
            examples = sorted_urls[:3]

            stats[pattern] = {
                "count": len(urls),
                "avg_depth": round(avg_depth, 1),
                "example_urls": examples,
            }

        return stats

    async def analyze(self, max_pages: int = 5, max_links_per_page: int = 50) -> Dict:
        """
        Analyze website by crawling pages and extracting links.

        Args:
            max_pages: Maximum pages to crawl for link discovery
            max_links_per_page: Maximum links to extract per page

        Returns:
            Analysis results with discovered link patterns
        """
        if not CRAWL4AI_AVAILABLE:
            return {
                "base_url": self.base_url,
                "analysis_method": "error",
                "error": "Crawl4AI not available",
                "total_urls": 0,
                "pattern_stats": {},
                "notes": "Install Crawl4AI to use link extraction: uv add crawl4ai"
            }

        logger.info(f"Starting link extraction analysis for {self.base_url}")
        logger.info(f"Will crawl up to {max_pages} pages to discover links\n")

        all_links: Set[str] = set()
        crawled_urls: List[str] = [self.base_url]
        queue: List[str] = [self.base_url]

        async with AsyncWebCrawler(verbose=False) as crawler:
            # BFS link discovery (limited by max_pages)
            while queue and len(crawled_urls) < max_pages:
                url = queue.pop(0)

                # Extract links from this page
                links = await self.extract_links_from_page(
                    url, crawler, max_links=max_links_per_page
                )

                for link in links:
                    if link not in crawled_urls and link not in queue:
                        all_links.add(link)
                        queue.append(link)

                # Limit queue size to avoid explosion
                if len(queue) > max_pages * 2:
                    queue = queue[:max_pages * 2]

                crawled_urls.append(url)

        logger.info(f"\n✓ Analysis complete")
        logger.info(f"  Pages crawled: {len(crawled_urls)}")
        logger.info(f"  Unique links discovered: {len(all_links)}\n")

        # Group and analyze discovered links
        url_groups = self.group_links_by_pattern(all_links)
        pattern_stats = self.get_pattern_stats(url_groups)

        # Sort by count
        sorted_patterns = sorted(
            pattern_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        return {
            "base_url": self.base_url,
            "analysis_method": "crawl4ai_link_extraction",
            "pages_crawled": len(crawled_urls),
            "total_urls_discovered": len(all_links),
            "pattern_stats": dict(sorted_patterns),
            "crawled_pages": crawled_urls,
            "notes": (
                f"Discovered {len(all_links)} unique links by crawling {len(crawled_urls)} pages. "
                f"Links grouped into {len(url_groups)} patterns. "
                f"This approach works well for sites without sitemaps."
            )
        }


async def main():
    """Run POC on parameterized website."""
    # Parse command line arguments
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        # Default to Reddit (a site without sitemap that's worth analyzing)
        url = "https://reddit.com"

    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    max_links = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    logger.info("=" * 80)
    logger.info("POC: Crawl4AI Link Extraction for Website Analysis")
    logger.info("=" * 80)
    logger.info(f"\nTest Parameters:")
    logger.info(f"  URL: {url}")
    logger.info(f"  Max pages to crawl: {max_pages}")
    logger.info(f"  Max links per page: {max_links}\n")

    # Run analysis
    extractor = WebLinkExtractor(url)
    result = await extractor.analyze(max_pages=max_pages, max_links_per_page=max_links)

    # Print results
    logger.info("=" * 80)
    logger.info("ANALYSIS RESULTS")
    logger.info("=" * 80)
    logger.info(json.dumps(result, indent=2))

    return result


if __name__ == "__main__":
    asyncio.run(main())
