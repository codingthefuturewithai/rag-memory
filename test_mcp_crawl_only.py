"""
Test ONLY the crawling part from ingest_url_impl - no database, no ingestion.
This isolates whether the issue is in the crawler or in the MCP/database layers.
"""
import asyncio
import logging
from src.ingestion.web_crawler import WebCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Simulate the EXACT crawling code from ingest_url_impl (lines 1125-1127)."""
    logger.info("="*80)
    logger.info("Testing WebCrawler.crawl_with_depth (MCP code path simulation)")
    logger.info("="*80)
    
    # This is the EXACT code from ingest_url_impl lines 1125-1127
    crawler = WebCrawler(headless=True, verbose=False)
    results = await crawler.crawl_with_depth(url='https://python.org/about', max_depth=1, max_pages=5)
    
    # Check if we hit limit (line 1130)
    if len(results) == 5:
        logger.info(
            f"Crawl reached max_pages limit (5). "
            f"Consider multiple targeted crawls for complete coverage."
        )
    
    logger.info("="*80)
    logger.info(f"✅ COMPLETED: Crawled {len(results)} pages")
    logger.info("="*80)
    
    for i, result in enumerate(results):
        logger.info(f"{i+1}. {result.url} (success={result.success})")
    
    return results


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\n\nFINAL RESULT: {len(results)} pages crawled")
