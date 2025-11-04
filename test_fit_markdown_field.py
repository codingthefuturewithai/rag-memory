#!/usr/bin/env python3
"""
Check if fit_markdown field is actually populated.
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def test_markdown_fields():
    """Check which markdown fields are populated."""

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

    # Create crawler config
    crawler_config = CrawlerRunConfig(
        markdown_generator=markdown_generator,
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside", "form", "iframe", "script", "style", "noscript", "meta", "link"],
        remove_overlay_elements=True,
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

    # Crawl
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=url,
            config=crawler_config,
        )

        print(f"Crawl success: {result.success}")
        print(f"\nMarkdown result fields:")
        print(f"  - raw_markdown exists: {result.markdown.raw_markdown is not None}")
        print(f"  - raw_markdown size: {len(result.markdown.raw_markdown) if result.markdown.raw_markdown else 0}")
        print(f"  - markdown_with_citations exists: {result.markdown.markdown_with_citations is not None}")
        print(f"  - markdown_with_citations size: {len(result.markdown.markdown_with_citations) if result.markdown.markdown_with_citations else 0}")
        print(f"  - fit_markdown exists: {result.markdown.fit_markdown is not None}")
        print(f"  - fit_markdown size: {len(result.markdown.fit_markdown) if result.markdown.fit_markdown else 0}")
        print(f"  - fit_html exists: {result.markdown.fit_html is not None}")

        if result.markdown.fit_markdown:
            print(f"\n✓ fit_markdown IS populated")
            print(f"First 500 chars of fit_markdown:")
            print(result.markdown.fit_markdown[:500])
        else:
            print(f"\n✗ fit_markdown is NOT populated")
            print(f"Using fallback markdown_with_citations")
            print(f"First 500 chars:")
            print(result.markdown.markdown_with_citations[:500])


if __name__ == "__main__":
    asyncio.run(test_markdown_fields())
