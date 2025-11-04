#!/usr/bin/env python3
"""
Local test script to debug PruningContentFilter without rebuilding the container.
Tests the filter locally until we get clean content suitable for Graphiti.
"""

import asyncio
import sys
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def test_filter_configuration(
    url: str,
    threshold: float,
    threshold_type: str,
    min_word_threshold: int = None,
) -> dict:
    """
    Test a specific filter configuration and return results.

    Returns dict with:
    - raw_content_size: size of unfiltered markdown
    - filtered_content_size: size of filtered markdown
    - raw_content: first 2000 chars of raw markdown
    - filtered_content: first 2000 chars of filtered markdown
    - has_navigation: whether "Navigation" appears in filtered content
    - has_language_selector: whether language selector appears in filtered content
    - num_links: approximate number of links in filtered content
    """

    print(f"\n{'='*80}")
    print(f"Testing: threshold={threshold}, type={threshold_type}, min_words={min_word_threshold}")
    print(f"URL: {url}")
    print(f"{'='*80}")

    try:
        # Create filter with specified config
        content_filter = PruningContentFilter(
            threshold=threshold,
            threshold_type=threshold_type,
            min_word_threshold=min_word_threshold
        )

        # Wrap in markdown generator
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter
        )

        # Create crawler config
        crawler_config = CrawlerRunConfig(
            markdown_generator=markdown_generator,
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            excluded_tags=[
                "nav", "footer", "header", "aside",
                "form", "iframe", "script", "style",
                "noscript", "meta", "link"
            ],
            remove_overlay_elements=True,
        )

        # Browser config with single-process to avoid deadlocks
        browser_config = BrowserConfig(
            headless=True,
            extra_args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--single-process",
                "--no-zygote",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        # Crawl
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url=url,
                config=crawler_config,
            )

            if not result.success:
                print(f"❌ CRAWL FAILED: {result.error_message}")
                return None

            # Get both versions
            raw_md = result.markdown.raw_markdown or ""
            filtered_md = result.markdown.fit_markdown or ""

            # If fit_markdown is empty, the filter didn't work
            if not filtered_md:
                print(f"⚠️  fit_markdown is EMPTY - filter not applied!")
                filtered_md = result.markdown.markdown_with_citations or ""

            # Analysis
            has_nav = "Navigation" in filtered_md
            has_lang = "Greek" in filtered_md or "Spanish" in filtered_md or "語" in filtered_md
            num_links = filtered_md.count("[") // 2  # Approximate

            print(f"\n✓ Crawl successful")
            print(f"Raw markdown size: {len(raw_md)} chars")
            print(f"Filtered markdown size: {len(filtered_md)} chars")
            print(f"Reduction: {100 - (len(filtered_md) / len(raw_md) * 100):.1f}%")
            print(f"\nContent analysis:")
            print(f"  - Contains '### Navigation': {has_nav}")
            print(f"  - Contains language selectors: {has_lang}")
            print(f"  - Approximate link count: {num_links}")

            print(f"\n--- First 1500 chars of FILTERED content ---")
            print(filtered_md[:1500])
            print(f"\n--- Last 1500 chars of FILTERED content ---")
            print(filtered_md[-1500:])

            return {
                "threshold": threshold,
                "threshold_type": threshold_type,
                "min_word_threshold": min_word_threshold,
                "raw_size": len(raw_md),
                "filtered_size": len(filtered_md),
                "reduction_percent": 100 - (len(filtered_md) / len(raw_md) * 100),
                "has_navigation": has_nav,
                "has_language_selector": has_lang,
                "num_links": num_links,
                "filtered_content_sample": filtered_md[:2000],
            }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Test different filter configurations."""

    url = "https://docs.python.org/3.13/"

    # Test configurations to try
    # Start with different thresholds and modes
    configs_to_test = [
        # (threshold, threshold_type, min_word_threshold)
        (0.48, "dynamic", 5),      # Current (broken) config
        (0.40, "fixed", 5),        # Recommended config
        (0.35, "fixed", 5),        # More permissive
        (0.30, "fixed", 5),        # Very permissive
        (0.25, "fixed", 5),        # Extremely permissive
        (0.20, "fixed", 3),        # Very aggressive
    ]

    results = []

    for threshold, threshold_type, min_words in configs_to_test:
        result = await test_filter_configuration(
            url=url,
            threshold=threshold,
            threshold_type=threshold_type,
            min_word_threshold=min_words,
        )
        if result:
            results.append(result)

            # Check if content looks good (no Navigation headers, no language selectors)
            if not result["has_navigation"] and not result["has_language_selector"]:
                print(f"\n🎉 GOOD CONFIGURATION FOUND!")
                print(f"   threshold={threshold}, type={threshold_type}, min_words={min_words}")
                print(f"   Reduction: {result['reduction_percent']:.1f}%")
                break

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY OF TESTS")
    print(f"{'='*80}")
    for r in results:
        nav_status = "✓ NO NAV" if not r["has_navigation"] else "✗ HAS NAV"
        lang_status = "✓ NO LANG" if not r["has_language_selector"] else "✗ HAS LANG"
        print(
            f"threshold={r['threshold']:<5} type={r['threshold_type']:<7} "
            f"reduction={r['reduction_percent']:>5.1f}% {nav_status} {lang_status}"
        )


if __name__ == "__main__":
    asyncio.run(main())
