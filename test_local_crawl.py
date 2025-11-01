"""
Test the crawl_with_depth fix locally to prove it works.
"""
import asyncio
import logging
from src.ingestion.web_crawler import WebCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test crawl with max_pages parameter."""
    logger.info("="*80)
    logger.info("Testing crawl_with_depth with max_pages=10")
    logger.info("="*80)

    crawler = WebCrawler(headless=True, verbose=False)

    # This is the EXACT call that ingest_url_impl makes
    results = await crawler.crawl_with_depth(
        url='https://python.org/about',
        max_depth=1,
        max_pages=10
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
