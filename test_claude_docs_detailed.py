#!/usr/bin/env python3
"""
Detailed analysis of Claude Docs crawl with BEFORE/AFTER content inspection.

This script will:
1. Crawl https://docs.claude.com/en/docs/mcp
2. Show the ACTUAL HTML/content that should be filtered (navigation, sidebars)
3. Show raw markdown output WITH navigation
4. Show filtered markdown output WITHOUT navigation
5. Verify valuable content is still present in both

We inspect ACTUAL CONTENT, not just file sizes.
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def crawl_with_config(url: str, use_filter: bool) -> dict:
    """Crawl a URL and return detailed content analysis."""

    filter_status = "WITH filter" if use_filter else "WITHOUT filter"

    # Create filter if needed
    if use_filter:
        content_filter = PruningContentFilter(
            threshold=0.48,
            threshold_type="dynamic",
            min_word_threshold=5
        )
        markdown_generator = DefaultMarkdownGenerator(
            content_filter=content_filter
        )
    else:
        markdown_generator = None

    # Create crawler config
    crawler_config = CrawlerRunConfig(
        markdown_generator=markdown_generator if use_filter else None,
        cache_mode=CacheMode.BYPASS,
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "header", "aside"],
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

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=url,
            config=crawler_config,
        )

        if not result.success:
            return {"success": False, "error": result.error_message}

        raw_md = result.markdown.raw_markdown or ""
        fit_md = result.markdown.fit_markdown or ""

        # Determine which version was actually used
        if use_filter and fit_md:
            actual_content = fit_md
            content_source = "fit_markdown (FILTERED)"
        else:
            actual_content = raw_md
            content_source = "raw_markdown (UNFILTERED)"

        # Analyze content for specific markers
        analysis = {
            "url": url,
            "filter_status": filter_status,
            "success": True,
            "raw_size": len(raw_md),
            "fit_size": len(fit_md),
            "actual_content_source": content_source,
            "actual_content_size": len(actual_content),
            "size_reduction_percent": round(100 - (len(fit_md) / len(raw_md) * 100), 1) if raw_md else 0,
            "markers_found": {
                "raw": {
                    "has_nav_sidebar": "sidebar" in raw_md.lower() or "navigation" in raw_md.lower(),
                    "has_skip_links": "[skip" in raw_md.lower(),
                    "has_breadcrumb": "breadcrumb" in raw_md.lower() or " > " in raw_md,
                    "has_search": "search" in raw_md.lower() and "search box" in raw_md.lower(),
                    "has_table_of_contents": "table of contents" in raw_md.lower() or "# table" in raw_md.lower(),
                },
                "actual": {
                    "has_nav_sidebar": "sidebar" in actual_content.lower() or ("navigation" in actual_content.lower() and "docs" in actual_content.lower()),
                    "has_skip_links": "[skip" in actual_content.lower(),
                    "has_breadcrumb": "breadcrumb" in actual_content.lower() or " > " in actual_content,
                    "has_search": "search" in actual_content.lower() and "search box" in actual_content.lower(),
                    "has_table_of_contents": "table of contents" in actual_content.lower() or "# table" in actual_content.lower(),
                }
            },
            "content_quality": {
                "has_main_heading": "#" in actual_content and len(actual_content) > 100,
                "has_paragraphs": actual_content.count("\n\n") > 2,
                "has_code_blocks": "```" in actual_content,
                "has_links_to_docs": "[" in actual_content and "](" in actual_content,
            },
            "sample_raw": raw_md[:2000] if raw_md else "NO RAW MARKDOWN",
            "sample_actual": actual_content[:2000] if actual_content else "NO CONTENT",
            "raw_full": raw_md,  # Keep full content for detailed inspection
            "actual_full": actual_content,
        }

        return analysis


async def main():
    """Analyze Claude Docs with and without filter."""

    url = "https://docs.claude.com/en/docs/mcp"

    print("=" * 100)
    print("CLAUDE DOCS MCP DETAILED ANALYSIS")
    print("=" * 100)
    print(f"\nURL: {url}\n")

    # Crawl WITHOUT filter
    print("\n" + "=" * 100)
    print("STEP 1: CRAWL WITHOUT FILTER")
    print("=" * 100)
    result_no_filter = await crawl_with_config(url, use_filter=False)

    if not result_no_filter["success"]:
        print(f"ERROR: {result_no_filter['error']}")
        return

    print(f"\nContent source: {result_no_filter['actual_content_source']}")
    print(f"Total size: {result_no_filter['actual_content_size']} chars")
    print(f"\nNavigation/Structure elements FOUND in RAW content:")
    for marker, found in result_no_filter['markers_found']['raw'].items():
        status = "✓ FOUND" if found else "✗ NOT FOUND"
        print(f"  {marker}: {status}")

    print(f"\n--- First 2000 chars of RAW MARKDOWN (WITHOUT FILTER) ---")
    print(result_no_filter['sample_raw'])
    print("\n...")

    # Crawl WITH filter
    print("\n\n" + "=" * 100)
    print("STEP 2: CRAWL WITH FILTER")
    print("=" * 100)
    result_with_filter = await crawl_with_config(url, use_filter=True)

    if not result_with_filter["success"]:
        print(f"ERROR: {result_with_filter['error']}")
        return

    print(f"\nRaw markdown size: {result_with_filter['raw_size']} chars")
    print(f"Filtered markdown size: {result_with_filter['fit_size']} chars")
    print(f"Size reduction: {result_with_filter['size_reduction_percent']}%")
    print(f"\nContent source: {result_with_filter['actual_content_source']}")
    print(f"Actual content used: {result_with_filter['actual_content_size']} chars")

    print(f"\nNavigation/Structure elements found in ACTUAL content:")
    for marker, found in result_with_filter['markers_found']['actual'].items():
        status = "✓ FOUND" if found else "✗ REMOVED"
        print(f"  {marker}: {status}")

    print(f"\nContent Quality Metrics (does actual content have real doc content?):")
    for metric, has_it in result_with_filter['content_quality'].items():
        status = "✓ YES" if has_it else "✗ NO"
        print(f"  {metric}: {status}")

    print(f"\n--- First 2000 chars of FILTERED CONTENT (WITH FILTER) ---")
    print(result_with_filter['sample_actual'])
    print("\n...")

    # DETAILED COMPARISON
    print("\n\n" + "=" * 100)
    print("STEP 3: DETAILED COMPARISON")
    print("=" * 100)

    print(f"\nNAVIGATION REMOVAL ANALYSIS:")
    print(f"{'Marker':<30} {'WITHOUT Filter':<20} {'WITH Filter':<20} {'Removed?':<15}")
    print("-" * 85)

    for marker in result_no_filter['markers_found']['raw'].keys():
        without = result_no_filter['markers_found']['raw'][marker]
        with_f = result_with_filter['markers_found']['actual'][marker]
        removed = "✓ YES" if without and not with_f else ("✗ NO" if without and with_f else "N/A")

        without_str = "PRESENT" if without else "absent"
        with_f_str = "PRESENT" if with_f else "absent"

        print(f"{marker:<30} {without_str:<20} {with_f_str:<20} {removed:<15}")

    print(f"\nCONTENT QUALITY:")
    print(f"{'Metric':<35} {'Present?':<15}")
    print("-" * 50)
    for metric, has_it in result_with_filter['content_quality'].items():
        status = "✓ YES" if has_it else "✗ NO"
        print(f"{metric:<35} {status:<15}")

    # Save full content for manual inspection
    print("\n\n" + "=" * 100)
    print("STEP 4: SAVING FULL CONTENT FOR MANUAL INSPECTION")
    print("=" * 100)

    with open("claude_docs_without_filter.txt", "w") as f:
        f.write("FULL RAW MARKDOWN (WITHOUT FILTER)\n")
        f.write("=" * 100 + "\n\n")
        f.write(result_no_filter['raw_full'])

    with open("claude_docs_with_filter.txt", "w") as f:
        f.write("FULL FILTERED MARKDOWN (WITH FILTER)\n")
        f.write("=" * 100 + "\n\n")
        f.write(result_with_filter['actual_full'])

    print(f"\n✓ Saved raw content to: claude_docs_without_filter.txt ({result_no_filter['actual_content_size']} chars)")
    print(f"✓ Saved filtered content to: claude_docs_with_filter.txt ({result_with_filter['actual_content_size']} chars)")
    print(f"\nYou can now manually inspect both files to verify:")
    print(f"  1. What navigation/sidebars were in the raw version")
    print(f"  2. Whether they're actually removed in the filtered version")
    print(f"  3. Whether valuable documentation content is preserved")

    # Final verdict
    print("\n\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    nav_removed = all(
        result_no_filter['markers_found']['raw'][key] and not result_with_filter['markers_found']['actual'][key]
        for key in result_no_filter['markers_found']['raw'].keys()
        if result_no_filter['markers_found']['raw'][key]
    )

    content_quality_ok = all(result_with_filter['content_quality'].values())

    print(f"\nNavigation/sidebars removed: {'✓ YES' if nav_removed else '✗ PARTIAL/NO'}")
    print(f"Content quality preserved: {'✓ YES' if content_quality_ok else '✗ SOME ISSUES'}")
    print(f"\nSize reduction: {result_with_filter['size_reduction_percent']}%")
    print(f"Verdict: {'✓ FILTER WORKING' if nav_removed and content_quality_ok else '✗ FILTER HAS ISSUES'}")


if __name__ == "__main__":
    asyncio.run(main())
