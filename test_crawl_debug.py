"""
Debug test to see exactly where the crawl hangs in Docker.
"""
import asyncio
import logging
from src.ingestion.web_crawler import WebCrawler

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Test crawl with max_pages parameter and detailed logging."""
    logger.info("="*80)
    logger.info("STARTING CRAWL TEST with max_pages=5")
    logger.info("="*80)

    crawler = WebCrawler(headless=True, verbose=True)  # Enable verbose

    try:
        results = await crawler.crawl_with_depth(
            url='https://python.org/about',
            max_depth=1,
            max_pages=5  # Smaller number for faster testing
        )

        logger.info("="*80)
        logger.info(f"✅ COMPLETED: Crawled {len(results)} pages")
        logger.info("="*80)

        for i, result in enumerate(results):
            logger.info(f"{i+1}. {result.url} (success={result.success})")

        return results

    except Exception as e:
        logger.error(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    logger.info("Starting asyncio.run...")
    results = asyncio.run(main())
    print(f"\n\nFINAL RESULT: {len(results)} pages crawled")
