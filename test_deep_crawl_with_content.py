#!/usr/bin/env python3
"""
Test PruningContentFilter with deep crawl (follow_links=True, max_depth=1)
to ensure we're testing on pages with ACTUAL CONTENT, not just boxes and links.

This will crawl https://docs.claude.com/en/docs/mcp and follow internal links
to get at least 3-4 pages with real documentation content.
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode, BFSDeepCrawlStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def crawl_with_filter(url: str, use_filter: bool) -> dict:
    """Crawl with follow_links=True, depth=1 with or without filter."""

    filter_status = "WITH filter" if use_filter else "WITHOUT filter"
    print(f"\n{'='*100}")
    print(f"CRAWLING: {filter_status}")
    print(f"{'='*100}")

    # Create filter if needed
    if use_filter:
        content_filter = PruningContentFilter(
            threshold=0.40,
            threshold_type="fixed",
            min_word_threshold=5
        )
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter
        )
    else:
        markdown_generator = None

    # Create crawl strategy: follow links, max depth 1, max 5 pages
    crawl_strategy = BFSDeepCrawlStrategy(max_depth=1, max_pages=5)

    # Create crawler config
    crawler_config = CrawlerRunConfig(
        markdown_generator=markdown_generator if use_filter else None,
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside", "form", "iframe", "script", "style"],
        remove_overlay_elements=True,
        deep_crawl_strategy=crawl_strategy,
        session_id=f"test_deep_{'with_filter' if use_filter else 'no_filter'}",
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

    pages = []

    async with AsyncWebCrawler(config=browser_config) as crawler:
        crawl_results = await crawler.arun(
            url=url,
            config=crawler_config,
        )

        page_num = 0
        async for result in crawl_results:
            if result.success:
                page_num += 1

                raw_md = result.markdown.raw_markdown or ""
                fit_md = result.markdown.fit_markdown or ""

                # Determine which content was actually used
                if use_filter and fit_md:
                    actual_content = fit_md
                    content_type = "fit_markdown (FILTERED)"
                else:
                    actual_content = raw_md
                    content_type = "raw_markdown (UNFILTERED)"

                # Analyze content
                has_nav = "nav" in actual_content.lower() or "navigation" in actual_content.lower()
                has_logo = "logo" in actual_content.lower()
                has_search_box = "search" in actual_content.lower()
                has_breadcrumb = " > " in actual_content or "breadcrumb" in actual_content.lower()

                # Content quality checks
                has_headings = actual_content.count("##") > 0
                has_paragraphs = actual_content.count("\n\n") > 2
                has_code = "```" in actual_content
                has_links = "[" in actual_content and "](" in actual_content

                page_info = {
                    "url": result.url,
                    "page_num": page_num,
                    "raw_size": len(raw_md),
                    "fit_size": len(fit_md),
                    "actual_size": len(actual_content),
                    "content_type": content_type,
                    "reduction_percent": round(100 - (len(fit_md) / len(raw_md) * 100), 1) if raw_md else 0,
                    "has_nav": has_nav,
                    "has_logo": has_logo,
                    "has_search_box": has_search_box,
                    "has_breadcrumb": has_breadcrumb,
                    "has_headings": has_headings,
                    "has_paragraphs": has_paragraphs,
                    "has_code": has_code,
                    "has_links": has_links,
                    "first_500_chars": actual_content[:500],
                    "full_content": actual_content,
                }
                pages.append(page_info)

                print(f"\nPage {page_num}: {result.url}")
                print(f"  Raw size: {page_info['raw_size']} chars")
                print(f"  Fit size: {page_info['fit_size']} chars")
                print(f"  Using: {content_type} ({page_info['actual_size']} chars)")
                if page_info['reduction_percent'] > 0:
                    print(f"  Size reduction: {page_info['reduction_percent']}%")
                print(f"\n  Navigation elements:")
                print(f"    - Has nav/navigation text: {page_info['has_nav']}")
                print(f"    - Has logo: {page_info['has_logo']}")
                print(f"    - Has search box: {page_info['has_search_box']}")
                print(f"    - Has breadcrumb: {page_info['has_breadcrumb']}")
                print(f"\n  Content quality:")
                print(f"    - Has headings: {page_info['has_headings']}")
                print(f"    - Has paragraphs: {page_info['has_paragraphs']}")
                print(f"    - Has code blocks: {page_info['has_code']}")
                print(f"    - Has links: {page_info['has_links']}")
                print(f"\n  First 500 chars:")
                print(f"    {page_info['first_500_chars'][:500]}")

    return {
        "filter_status": filter_status,
        "use_filter": use_filter,
        "pages": pages,
        "total_pages": page_num,
    }


async def main():
    """Run deep crawl test with and without filter."""

    base_url = "https://docs.claude.com/en/docs/mcp"

    print("="*100)
    print("DEEP CRAWL TEST: Claude Docs MCP (follow_links=True, depth=1, max_pages=5)")
    print("="*100)
    print(f"\nBase URL: {base_url}")
    print("This will crawl the MCP page and follow internal links to get multiple pages with real content")

    # Test WITHOUT filter
    result_no_filter = await crawl_with_filter(base_url, use_filter=False)

    # Small delay
    await asyncio.sleep(2)

    # Test WITH filter
    result_with_filter = await crawl_with_filter(base_url, use_filter=True)

    # DETAILED COMPARISON
    print(f"\n\n{'='*100}")
    print("DETAILED COMPARISON: WITHOUT FILTER vs WITH FILTER")
    print(f"{'='*100}")

    if result_no_filter["total_pages"] != result_with_filter["total_pages"]:
        print(f"\nWARNING: Different number of pages crawled!")
        print(f"  Without filter: {result_no_filter['total_pages']} pages")
        print(f"  With filter: {result_with_filter['total_pages']} pages")

    # Compare page by page
    max_pages = max(result_no_filter["total_pages"], result_with_filter["total_pages"])
    for i in range(max_pages):
        page_no_filter = result_no_filter["pages"][i] if i < len(result_no_filter["pages"]) else None
        page_with_filter = result_with_filter["pages"][i] if i < len(result_with_filter["pages"]) else None

        if page_no_filter:
            print(f"\n\n{'#'*100}")
            print(f"# PAGE {i+1}: {page_no_filter['url']}")
            print(f"{'#'*100}")

            print(f"\nSize Comparison:")
            print(f"  WITHOUT filter: {page_no_filter['raw_size']} chars (raw)")
            if page_with_filter:
                print(f"  WITH filter:    {page_with_filter['actual_size']} chars ({page_with_filter['content_type']})")
                size_diff = page_no_filter['raw_size'] - page_with_filter['actual_size']
                percent_reduction = round(100 * size_diff / page_no_filter['raw_size'], 1) if page_no_filter['raw_size'] > 0 else 0
                print(f"  Reduction: {percent_reduction}% ({size_diff} chars)")

            print(f"\nNavigation Elements:")
            print(f"  {'Element':<25} {'WITHOUT Filter':<20} {'WITH Filter':<20}")
            print(f"  {'-'*65}")

            nav_elements = ["has_nav", "has_logo", "has_search_box", "has_breadcrumb"]
            for elem in nav_elements:
                without = "PRESENT" if page_no_filter.get(elem) else "absent"
                with_f = "PRESENT" if (page_with_filter and page_with_filter.get(elem)) else "absent"
                print(f"  {elem:<25} {without:<20} {with_f:<20}")

            print(f"\nContent Quality (does valuable content remain?):")
            print(f"  {'Metric':<25} {'WITHOUT Filter':<20} {'WITH Filter':<20}")
            print(f"  {'-'*65}")

            quality_metrics = ["has_headings", "has_paragraphs", "has_code", "has_links"]
            for metric in quality_metrics:
                without = "YES" if page_no_filter.get(metric) else "NO"
                with_f = "YES" if (page_with_filter and page_with_filter.get(metric)) else "NO"
                print(f"  {metric:<25} {without:<20} {with_f:<20}")

            if page_with_filter:
                print(f"\nFirst 300 chars of FILTERED content:")
                print(f"  {page_with_filter['first_500_chars'][:300]}")

    # Save full content for inspection
    print(f"\n\n{'='*100}")
    print("SAVING FULL PAGE CONTENT FOR MANUAL INSPECTION")
    print(f"{'='*100}")

    for i, page in enumerate(result_no_filter["pages"]):
        filename = f"page_{i+1}_without_filter.txt"
        with open(filename, "w") as f:
            f.write(f"PAGE {i+1}: {page['url']}\n")
            f.write(f"{'='*100}\n\n")
            f.write(f"RAW MARKDOWN (WITHOUT FILTER) - {page['raw_size']} chars\n\n")
            f.write(page['full_content'])
        print(f"✓ Saved: {filename}")

    for i, page in enumerate(result_with_filter["pages"]):
        filename = f"page_{i+1}_with_filter.txt"
        with open(filename, "w") as f:
            f.write(f"PAGE {i+1}: {page['url']}\n")
            f.write(f"{'='*100}\n\n")
            f.write(f"FILTERED MARKDOWN (WITH FILTER) - {page['actual_size']} chars\n\n")
            f.write(page['full_content'])
        print(f"✓ Saved: {filename}")

    print(f"\nYou can now manually inspect these files to verify navigation removal and content preservation.")


if __name__ == "__main__":
    asyncio.run(main())
