#!/usr/bin/env python3
"""
Test if PruningContentFilter works with BFSDeepCrawlStrategy
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode, BFSDeepCrawlStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def test_deep_crawl_with_filter():
    """Test deep crawl WITH filter in config."""

    url = "https://docs.python.org/3.13/"

    # Create filter
    content_filter = PruningContentFilter(
        threshold=0.48,
        threshold_type="dynamic",
        min_word_threshold=5
    )

    # Wrap in markdown generator
    markdown_generator = DefaultMarkdownGenerator(
        content_filter=content_filter
    )

    # Create crawl strategy
    crawl_strategy = BFSDeepCrawlStrategy(max_depth=1, max_pages=3)

    # Create crawler config WITH markdown_generator
    crawler_config = CrawlerRunConfig(
        markdown_generator=markdown_generator,  # Include filter!
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside", "form", "iframe", "script", "style", "noscript", "meta", "link"],
        remove_overlay_elements=True,
        deep_crawl_strategy=crawl_strategy,
        session_id="test_session_with_filter",
        stream=True,
    )

    # Browser config
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

    print("TEST 1: Deep crawl WITH markdown_generator filter")
    print("=" * 80)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        crawl_results = await crawler.arun(
            url=url,
            config=crawler_config,
        )

        page_count = 0
        async for result in crawl_results:
            page_count += 1
            if result.success:
                # Check which fields are populated
                has_raw = result.markdown.raw_markdown is not None
                has_fit = result.markdown.fit_markdown is not None
                raw_size = len(result.markdown.raw_markdown) if has_raw else 0
                fit_size = len(result.markdown.fit_markdown) if has_fit else 0

                print(f"\nPage {page_count}: {result.url}")
                print(f"  raw_markdown: {raw_size} chars")
                print(f"  fit_markdown: {fit_size} chars")
                print(f"  Has Navigation: {'### Navigation' in (result.markdown.fit_markdown or result.markdown.raw_markdown)}")

                if page_count == 1:
                    first_content = result.markdown.fit_markdown or result.markdown.raw_markdown
                    print(f"  First 300 chars: {first_content[:300]}")

    print("\n" + "=" * 80)
    print("TEST 2: Deep crawl WITHOUT markdown_generator filter")
    print("=" * 80)

    # Create crawler config WITHOUT markdown_generator (current broken approach)
    crawler_config_no_filter = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside"],
        remove_overlay_elements=True,
        deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1, max_pages=3),
        session_id="test_session_no_filter",
        stream=True,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        crawl_results = await crawler.arun(
            url=url,
            config=crawler_config_no_filter,
        )

        page_count = 0
        async for result in crawl_results:
            page_count += 1
            if result.success:
                # Check which fields are populated
                has_raw = result.markdown.raw_markdown is not None
                has_fit = result.markdown.fit_markdown is not None
                raw_size = len(result.markdown.raw_markdown) if has_raw else 0
                fit_size = len(result.markdown.fit_markdown) if has_fit else 0

                print(f"\nPage {page_count}: {result.url}")
                print(f"  raw_markdown: {raw_size} chars")
                print(f"  fit_markdown: {fit_size} chars (populated: {has_fit})")
                print(f"  Has Navigation: {'### Navigation' in result.markdown.raw_markdown}")

                if page_count == 1:
                    print(f"  First 300 chars: {result.markdown.raw_markdown[:300]}")


if __name__ == "__main__":
    asyncio.run(test_deep_crawl_with_filter())
