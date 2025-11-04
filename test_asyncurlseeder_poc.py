#!/usr/bin/env python3
"""
POC: Test AsyncUrlSeeder for website analysis (user's proposed solution).

This script validates the AsyncUrlSeeder approach with source="sitemap+cc"
on problematic sites that timeout with traditional sitemap parsing.

Uses the ACTUAL Crawl4AI AsyncUrlSeeder implementation (not custom code).
Tests both successful sites and sites that previously failed/timed out.
"""

import asyncio
import json
import sys
import logging
from typing import Dict, List
from urllib.parse import urlparse
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(message)s'
)
logger = logging.getLogger(__name__)

# Import AsyncUrlSeeder from Crawl4AI
try:
    from crawl4ai import AsyncUrlSeeder, SeedingConfig
    ASYNCURLSEEDER_AVAILABLE = True
except ImportError:
    ASYNCURLSEEDER_AVAILABLE = False
    logger.error("AsyncUrlSeeder not available. Install: uv add crawl4ai")


class AsyncUrlSeederAnalyzer:
    """Analyze websites using AsyncUrlSeeder (sitemap+cc source)."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.parsed_base = urlparse(self.base_url)
        self.domain = self.parsed_base.netloc

    def group_urls_by_pattern(self, urls: List[Dict]) -> Dict[str, List[Dict]]:
        """Group discovered URLs by path pattern."""
        groups: Dict[str, List[Dict]] = defaultdict(list)

        for url_data in urls:
            url = url_data.get('url', '')
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')

            if not path or path == '/':
                pattern = "/"
            else:
                segments = path.split('/')
                pattern = f"/{segments[1]}" if len(segments) > 1 else "/"

            groups[pattern].append(url_data)

        return dict(groups)

    def get_pattern_stats(self, url_groups: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """Calculate statistics for each URL pattern group."""
        stats = {}

        for pattern, urls in url_groups.items():
            # Calculate average path depth
            depths = []
            for url_data in urls:
                url = url_data.get('url', '')
                parsed = urlparse(url)
                path = parsed.path.rstrip('/')
                depth = len([s for s in path.split('/') if s])
                depths.append(depth)

            avg_depth = sum(depths) / len(depths) if depths else 0

            # Get up to 3 example URLs
            sorted_urls = sorted(
                [u.get('url', '') for u in urls],
                key=lambda u: len(urlparse(u).path)
            )
            examples = sorted_urls[:3]

            # Count URLs by source
            sources = defaultdict(int)
            for url_data in urls:
                source = url_data.get('source', 'unknown')
                sources[source] += 1

            stats[pattern] = {
                "count": len(urls),
                "avg_depth": round(avg_depth, 1),
                "example_urls": examples,
                "sources": dict(sources),
            }

        return stats

    async def analyze(self, max_urls: int = 150, extract_head: bool = False) -> Dict:
        """
        Analyze website using AsyncUrlSeeder with sitemap+cc source.

        Args:
            max_urls: Maximum URLs to discover (default 150)
            extract_head: Whether to extract <head> metadata (default False)

        Returns:
            Analysis results with URL patterns and statistics
        """
        if not ASYNCURLSEEDER_AVAILABLE:
            return {
                "base_url": self.base_url,
                "analysis_method": "error",
                "error": "AsyncUrlSeeder not available",
                "total_urls": 0,
                "pattern_stats": {},
            }

        logger.info(f"Analyzing: {self.base_url}")
        logger.info(f"  Domain: {self.domain}")
        logger.info(f"  Max URLs: {max_urls}")
        logger.info(f"  Extract head: {extract_head}")

        try:
            async with AsyncUrlSeeder() as seeder:
                config = SeedingConfig(
                    source="sitemap+cc",              # Try sitemap first, fall back to Common Crawl
                    max_urls=max_urls,                # Limit results
                    live_check=False,                 # Speed over verification
                    filter_nonsense_urls=True,        # Clean results
                    extract_head=extract_head,        # Don't need metadata for analysis
                    verbose=False,
                )

                logger.info("  Fetching URLs with source='sitemap+cc'...")
                import time
                start_time = time.time()

                urls = await seeder.urls(self.domain, config)

                elapsed = time.time() - start_time
                logger.info(f"  ✓ Completed in {elapsed:.2f}s")

                if not urls:
                    logger.warning(f"  No URLs discovered from {self.domain}")
                    return {
                        "base_url": self.base_url,
                        "analysis_method": "asyncurlseeder",
                        "source": "sitemap+cc",
                        "total_urls": 0,
                        "elapsed_seconds": round(elapsed, 2),
                        "pattern_stats": {},
                        "notes": "No URLs discovered from either sitemap or Common Crawl",
                    }

                logger.info(f"  Found {len(urls)} unique URLs")

                # Group and analyze
                url_groups = self.group_urls_by_pattern(urls)
                pattern_stats = self.get_pattern_stats(url_groups)

                # Sort by count
                sorted_patterns = sorted(
                    pattern_stats.items(),
                    key=lambda x: x[1]["count"],
                    reverse=True
                )

                # Count sources
                source_counts = defaultdict(int)
                for url_data in urls:
                    source = url_data.get('source', 'unknown')
                    source_counts[source] += 1

                return {
                    "base_url": self.base_url,
                    "analysis_method": "asyncurlseeder",
                    "source": "sitemap+cc",
                    "total_urls": len(urls),
                    "elapsed_seconds": round(elapsed, 2),
                    "url_patterns": len(url_groups),
                    "pattern_stats": dict(sorted_patterns),
                    "source_distribution": dict(source_counts),
                    "notes": (
                        f"Discovered {len(urls)} URLs using AsyncUrlSeeder with sitemap+cc source. "
                        f"URLs grouped into {len(url_groups)} patterns. "
                        f"Source: {', '.join(f'{k}={v}' for k, v in sorted(source_counts.items()))}"
                    ),
                }

        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                "base_url": self.base_url,
                "analysis_method": "asyncurlseeder",
                "error": str(e),
                "total_urls": 0,
                "pattern_stats": {},
            }


async def test_site(url: str, max_urls: int = 150) -> Dict:
    """Test a single site with AsyncUrlSeeder."""
    analyzer = AsyncUrlSeederAnalyzer(url)
    return await analyzer.analyze(max_urls=max_urls)


async def main():
    """Run tests on problematic sites."""

    # Test sites from previous validation work
    # These are sites that timed out with sitemap parsing
    problem_sites = [
        ("https://www.edx.org", "Sitemap timeout case (15.4s)"),
        ("https://www.amazon.com", "Large sitemap case (12.1s)"),
        ("https://www.khanacademy.org", "Indefinite timeout case"),
    ]

    # Additional sites to test
    # These had issues in previous POC attempts
    failure_sites = [
        ("https://reddit.com", "JavaScript-heavy site (0 links in POC)"),
        ("https://golang.org", "Redirect site (0 links in POC)"),
    ]

    # Success sites from previous validation
    success_sites = [
        ("https://docs.python.org", "Sitemap success case (42 links)"),
        ("https://docs.djangoproject.com", "Sitemap success case (211 links)"),
    ]

    logger.info("=" * 80)
    logger.info("AsyncUrlSeeder POC - Website Analysis")
    logger.info("=" * 80)
    logger.info("")

    all_results = []

    # Test problem sites (previously timed out)
    logger.info("PROBLEM SITES (Previously timed out with sitemap):")
    logger.info("-" * 80)
    for url, description in problem_sites:
        logger.info(f"\n{description}")
        result = await test_site(url)
        all_results.append(result)
        if result.get('total_urls', 0) > 0:
            logger.info(f"  Result: ✓ {result['total_urls']} URLs in {result['elapsed_seconds']}s")
            logger.info(f"  Patterns: {result.get('url_patterns', 0)}")
            logger.info(f"  Source: {result.get('source_distribution', {})}")
        else:
            logger.warning(f"  Result: ✗ No URLs found")

    # Test failure sites (previously returned 0 links)
    logger.info("\n" + "=" * 80)
    logger.info("FAILURE SITES (Previously returned 0 links in POC):")
    logger.info("-" * 80)
    for url, description in failure_sites:
        logger.info(f"\n{description}")
        result = await test_site(url)
        all_results.append(result)
        if result.get('total_urls', 0) > 0:
            logger.info(f"  Result: ✓ {result['total_urls']} URLs in {result['elapsed_seconds']}s")
            logger.info(f"  Patterns: {result.get('url_patterns', 0)}")
            logger.info(f"  Source: {result.get('source_distribution', {})}")
        else:
            logger.warning(f"  Result: ✗ No URLs found")

    # Test success sites (should still work)
    logger.info("\n" + "=" * 80)
    logger.info("CONTROL SITES (Previously successful):")
    logger.info("-" * 80)
    for url, description in success_sites:
        logger.info(f"\n{description}")
        result = await test_site(url)
        all_results.append(result)
        if result.get('total_urls', 0) > 0:
            logger.info(f"  Result: ✓ {result['total_urls']} URLs in {result['elapsed_seconds']}s")
            logger.info(f"  Patterns: {result.get('url_patterns', 0)}")
            logger.info(f"  Source: {result.get('source_distribution', {})}")
        else:
            logger.warning(f"  Result: ✗ No URLs found")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    successful = [r for r in all_results if r.get('total_urls', 0) > 0]
    failed = [r for r in all_results if r.get('total_urls', 0) == 0]

    logger.info(f"Total sites tested: {len(all_results)}")
    logger.info(f"Successful (found URLs): {len(successful)}/{len(all_results)}")
    logger.info(f"Failed (no URLs): {len(failed)}/{len(all_results)}")

    if successful:
        avg_time = sum(r.get('elapsed_seconds', 0) for r in successful) / len(successful)
        logger.info(f"Average time per successful site: {avg_time:.2f}s")

    # Detailed results
    logger.info("\n" + "=" * 80)
    logger.info("DETAILED RESULTS")
    logger.info("=" * 80)
    logger.info(json.dumps(all_results, indent=2))

    return all_results


if __name__ == "__main__":
    results = asyncio.run(main())
