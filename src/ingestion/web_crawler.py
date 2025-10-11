"""Web crawler for documentation ingestion using Crawl4AI."""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

from src.ingestion.models import BatchCrawlResult, CrawlError, CrawlResult

logger = logging.getLogger(__name__)


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

        logger.info(
            f"WebCrawler initialized (headless={headless}, verbose={verbose})"
        )

    async def crawl_page(
        self, url: str, crawl_root_url: Optional[str] = None
    ) -> CrawlResult:
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

        crawl_timestamp = datetime.utcnow()
        crawl_session_id = str(uuid.uuid4())

        logger.info(f"Crawling page: {url}")

        try:
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


async def crawl_single_page(
    url: str, headless: bool = True, verbose: bool = False
) -> CrawlResult:
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
