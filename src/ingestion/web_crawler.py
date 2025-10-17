"""Web crawler for documentation ingestion using Crawl4AI."""

import logging
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin

from crawl4ai import (
    AsyncWebCrawler,
    BFSDeepCrawlStrategy,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)

from src.ingestion.models import CrawlError, CrawlResult

logger = logging.getLogger(__name__)


@contextmanager
def suppress_crawl4ai_stdout():
    """
    Context manager to suppress Crawl4AI's stdout logging.

    Crawl4AI writes progress messages like [FETCH], [SCRAPE], [COMPLETE] directly
    to stdout, which interferes with MCP's JSON-RPC protocol over stdio transport.

    This redirects stdout to stderr temporarily during crawl operations.
    """
    original_stdout = sys.stdout
    try:
        # Redirect stdout to stderr (or to devnull if you want to suppress completely)
        sys.stdout = sys.stderr
        yield
    finally:
        # Restore original stdout
        sys.stdout = original_stdout


class WebCrawler:
    """Crawls web pages for documentation ingestion."""

    def __init__(self, headless: bool = True, verbose: bool = False):
        """
        Initialize web crawler.

        Args:
            headless: Run browser in headless mode (default: True)
            verbose: Enable verbose logging (default: False)
        """
        self.headless = headless
        self.verbose = verbose
        self.visited_urls: Set[str] = set()  # Track visited URLs to prevent duplicates

        # Browser configuration
        self.browser_config = BrowserConfig(
            headless=headless,
            verbose=verbose,
        )

        # Crawler run configuration (for single-page crawls)
        self.crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Always fetch fresh content
            word_count_threshold=10,  # Minimum words to consider valid content
            excluded_tags=["nav", "footer", "header", "aside"],  # Remove navigation
            remove_overlay_elements=True,  # Remove popups/modals
        )

        logger.info(f"WebCrawler initialized (headless={headless}, verbose={verbose})")

    async def crawl_page(self, url: str, crawl_root_url: Optional[str] = None) -> CrawlResult:
        """
        Crawl a single web page.

        Args:
            url: URL to crawl
            crawl_root_url: Root URL for the crawl session (defaults to url)

        Returns:
            CrawlResult with page content and metadata
        """
        if not crawl_root_url:
            crawl_root_url = url

        crawl_timestamp = datetime.now(timezone.utc)
        crawl_session_id = str(uuid.uuid4())

        logger.info(f"Crawling page: {url}")

        try:
            with suppress_crawl4ai_stdout():
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    result = await crawler.arun(
                        url=url,
                        config=self.crawler_config,
                    )

                    if not result.success:
                        error = CrawlError(
                            url=url,
                            error_type="crawl_failed",
                            error_message=result.error_message or "Unknown error",
                            timestamp=crawl_timestamp,
                            status_code=result.status_code,
                        )
                        logger.error(f"Failed to crawl {url}: {error.error_message}")
                        return CrawlResult(
                            url=url,
                            content="",
                            metadata={},
                            success=False,
                            error=error,
                        )

                    # Extract metadata
                    metadata = self._build_metadata(
                        url=url,
                        crawl_root_url=crawl_root_url,
                        crawl_timestamp=crawl_timestamp,
                        crawl_session_id=crawl_session_id,
                        crawl_depth=0,  # Single page = depth 0
                        result=result,
                    )

                    # Get clean markdown content
                    content = result.markdown.raw_markdown

                    logger.info(
                        f"Successfully crawled {url} ({len(content)} chars, "
                        f"status={result.status_code})"
                    )

                    return CrawlResult(
                        url=url,
                        content=content,
                        metadata=metadata,
                        success=True,
                        links_found=result.links.get("internal", []) if result.links else [],
                    )

        except Exception as e:
            error = CrawlError(
                url=url,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=crawl_timestamp,
            )
            logger.exception(f"Exception while crawling {url}")
            return CrawlResult(
                url=url,
                content="",
                metadata={},
                success=False,
                error=error,
            )

    def _build_metadata(
        self,
        url: str,
        crawl_root_url: str,
        crawl_timestamp: datetime,
        crawl_session_id: str,
        crawl_depth: int,
        result,
        parent_url: Optional[str] = None,
    ) -> Dict:
        """
        Build metadata dictionary for a crawled page.

        Args:
            url: Page URL
            crawl_root_url: Root URL of the crawl
            crawl_timestamp: Timestamp of the crawl
            crawl_session_id: Unique session ID
            crawl_depth: Depth level in the crawl tree
            result: Crawl4AI result object
            parent_url: Optional parent page URL

        Returns:
            Metadata dictionary
        """
        parsed = urlparse(url)

        metadata = {
            # PAGE IDENTITY
            "source": url,
            "content_type": "web_page",
            # CRAWL CONTEXT (for re-crawl management - CRITICAL)
            "crawl_root_url": crawl_root_url,
            "crawl_timestamp": crawl_timestamp.isoformat(),
            "crawl_session_id": crawl_session_id,
            "crawl_depth": crawl_depth,
            # PAGE METADATA
            "title": result.metadata.get("title", ""),
            "description": result.metadata.get("description", ""),
            "domain": parsed.netloc,
            # OPTIONAL BUT USEFUL
            "language": result.metadata.get("language", "en"),
            "status_code": result.status_code,
            "content_length": len(result.markdown.raw_markdown),
            "crawler_version": "crawl4ai-0.7.4",
        }

        if parent_url:
            metadata["parent_url"] = parent_url

        return metadata

    async def crawl_with_depth(
        self,
        url: str,
        max_depth: int = 1,
        crawl_root_url: Optional[str] = None,
    ) -> List[CrawlResult]:
        """
        Crawl a website following links up to max_depth.

        Uses BFSDeepCrawlStrategy for breadth-first traversal.

        Args:
            url: Starting URL
            max_depth: Maximum depth to crawl (0 = only starting page, 1 = starting + direct links, etc.)
            crawl_root_url: Root URL for the crawl session (defaults to url)

        Returns:
            List of CrawlResult objects, one per page crawled
        """
        if not crawl_root_url:
            crawl_root_url = url

        crawl_timestamp = datetime.now(timezone.utc)
        crawl_session_id = str(uuid.uuid4())

        logger.info(
            f"Starting deep crawl from {url} (max_depth={max_depth}, session={crawl_session_id})"
        )

        results: List[CrawlResult] = []
        self.visited_urls.clear()  # Reset visited tracking for this crawl session

        # Configure BFSDeepCrawlStrategy
        crawl_strategy = BFSDeepCrawlStrategy(max_depth=max_depth)

        # Multi-page crawler config
        deep_crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            excluded_tags=["nav", "footer", "header", "aside"],
            remove_overlay_elements=True,
            deep_crawl_strategy=crawl_strategy,
        )

        try:
            with suppress_crawl4ai_stdout():
                async with AsyncWebCrawler(config=self.browser_config) as crawler:
                    # Start crawling - returns list when deep_crawl_strategy is set
                    crawl_results = await crawler.arun(
                        url=url,
                        config=deep_crawler_config,
                    )

                    # Process each crawled page
                    for depth, crawl_result in enumerate(crawl_results):
                        page_url = crawl_result.url
                        self.visited_urls.add(page_url)

                        if crawl_result.success:
                            # Determine parent URL (first page has no parent)
                            parent_url = None
                            if depth > 0:
                                # Parent is the starting URL for depth 1, and could be any previously crawled page
                                # For simplicity, we'll use the starting URL as parent for all depth=1 pages
                                parent_url = url

                            metadata = self._build_metadata(
                                url=page_url,
                                crawl_root_url=crawl_root_url,
                                crawl_timestamp=crawl_timestamp,
                                crawl_session_id=crawl_session_id,
                                crawl_depth=depth,
                                result=crawl_result,
                                parent_url=parent_url,
                            )
                            results.append(
                                CrawlResult(
                                    url=page_url,
                                    content=crawl_result.markdown.raw_markdown,
                                    metadata=metadata,
                                    success=True,
                                    links_found=(
                                        crawl_result.links.get("internal", [])
                                        if crawl_result.links
                                        else []
                                    ),
                                )
                            )
                            logger.info(
                                f"Successfully crawled page {page_url} (depth={depth}, {len(crawl_result.markdown.raw_markdown)} chars)"
                            )
                        else:
                            error = CrawlError(
                                url=page_url,
                                error_type="crawl_failed",
                                error_message=crawl_result.error_message or "Unknown error",
                                timestamp=crawl_timestamp,
                                status_code=crawl_result.status_code,
                            )
                            results.append(
                                CrawlResult(
                                    url=page_url,
                                    content="",
                                    metadata={},
                                    success=False,
                                    error=error,
                                )
                            )
                            logger.warning(f"Failed to crawl {page_url}: {error.error_message}")

                    logger.info(
                        f"Deep crawl completed: {len(results)} pages crawled, "
                        f"{sum(1 for r in results if r.success)} successful"
                    )
                    return results

        except Exception as e:
            error = CrawlError(
                url=url,
                error_type=type(e).__name__,
                error_message=str(e),
                timestamp=crawl_timestamp,
            )
            logger.exception(f"Exception during deep crawl from {url}")
            # Return whatever we managed to crawl plus the error
            if not results:
                results.append(
                    CrawlResult(
                        url=url,
                        content="",
                        metadata={},
                        success=False,
                        error=error,
                    )
                )
            return results


async def crawl_single_page(url: str, headless: bool = True, verbose: bool = False) -> CrawlResult:
    """
    Convenience function to crawl a single page.

    Args:
        url: URL to crawl
        headless: Run browser in headless mode
        verbose: Enable verbose logging

    Returns:
        CrawlResult with page content and metadata
    """
    crawler = WebCrawler(headless=headless, verbose=verbose)
    return await crawler.crawl_page(url)
