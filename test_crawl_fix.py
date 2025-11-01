"""
Test fix: Add stream=True to the config like the working rag-retriever implementation.
"""
import asyncio
import logging
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test crawl with stream=True in config."""
    logger.info("="*80)
    logger.info("Testing with stream=True (like working rag-retriever code)")
    logger.info("="*80)

    browser_config = BrowserConfig(headless=True, verbose=False)

    crawl_strategy = BFSDeepCrawlStrategy(max_depth=1, max_pages=5)

    # KEY DIFFERENCE: Add stream=True like the working implementation
    deep_crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside"],
        remove_overlay_elements=True,
        deep_crawl_strategy=crawl_strategy,
        stream=True  # THIS IS THE FIX
    )

    results = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        logger.info("Starting crawl with stream=True...")

        # With stream=True, we need to iterate async generator
        async for result in await crawler.arun('https://python.org/about', config=deep_crawler_config):
            if result.success:
                results.append(result)
                logger.info(f"✓ Crawled: {result.url}")
            else:
                logger.warning(f"✗ Failed: {result.url}")

    logger.info("="*80)
    logger.info(f"✅ COMPLETED: Crawled {len(results)} pages")
    logger.info("="*80)

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\n\nFINAL RESULT: {len(results)} pages crawled")
