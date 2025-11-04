#!/usr/bin/env python3
"""
Test PruningContentFilter on multiple websites to verify it works broadly.
"""

import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode, BFSDeepCrawlStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


async def test_site(site_name: str, url: str, with_filter: bool = True) -> dict:
    """Test a single site with or without filter."""

    filter_status = "WITH filter" if with_filter else "WITHOUT filter"
    print(f"\n{site_name} - {filter_status}")
    print("=" * 80)

    try:
        # Create filter if needed
        if with_filter:
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

        # Create crawl strategy
        crawl_strategy = BFSDeepCrawlStrategy(max_depth=1, max_pages=2)

        # Create crawler config
        crawler_config = CrawlerRunConfig(
            markdown_generator=markdown_generator if with_filter else None,
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            excluded_tags=["nav", "footer", "header", "aside"],
            remove_overlay_elements=True,
            deep_crawl_strategy=crawl_strategy,
            session_id=f"test_{site_name.replace(' ', '_')}",
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

        results = {
            "site": site_name,
            "url": url,
            "with_filter": with_filter,
            "pages": []
        }

        async with AsyncWebCrawler(config=browser_config) as crawler:
            crawl_results = await crawler.arun(
                url=url,
                config=crawler_config,
            )

            page_count = 0
            async for result in crawl_results:
                if result.success:
                    page_count += 1

                    raw_md = result.markdown.raw_markdown or ""
                    fit_md = result.markdown.fit_markdown or ""

                    # Determine which content was actually used
                    if with_filter and fit_md:
                        actual_content = fit_md
                        content_type = "filtered"
                    else:
                        actual_content = raw_md
                        content_type = "raw"

                    # Analysis
                    has_nav = "nav" in actual_content.lower() or "navigation" in actual_content.lower()
                    has_footer = "footer" in actual_content.lower()
                    has_header = "header" in actual_content.lower()

                    page_result = {
                        "url": result.url,
                        "raw_size": len(raw_md),
                        "fit_size": len(fit_md),
                        "actual_size": len(actual_content),
                        "content_type": content_type,
                        "reduction_percent": round(100 - (len(fit_md) / len(raw_md) * 100), 1) if raw_md else 0,
                        "has_nav_text": has_nav,
                        "has_footer_text": has_footer,
                        "has_header_text": has_header,
                        "first_100_chars": actual_content[:100].replace('\n', ' ')[:100]
                    }

                    results["pages"].append(page_result)

                    print(f"\nPage {page_count}: {result.url}")
                    print(f"  Raw markdown: {page_result['raw_size']} chars")
                    print(f"  Filtered markdown: {page_result['fit_size']} chars")
                    print(f"  Using: {page_result['content_type'].upper()} ({page_result['actual_size']} chars)")
                    if page_result['reduction_percent'] > 0:
                        print(f"  Reduction: {page_result['reduction_percent']}%")
                    print(f"  Quality issues in content:")
                    print(f"    - Has nav/navigation text: {page_result['has_nav_text']}")
                    print(f"    - Has footer text: {page_result['has_footer_text']}")
                    print(f"    - Has header text: {page_result['has_header_text']}")
                    print(f"  First 100 chars: '{page_result['first_100_chars']}...'")

        return results

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Test multiple sites."""

    sites = [
        ("Django Docs", "https://docs.djangoproject.com/en/5.1/"),
        ("Node.js Docs", "https://nodejs.org/docs/latest/api/"),
        ("PostgreSQL Docs", "https://www.postgresql.org/docs/current/"),
    ]

    all_results = []

    for site_name, url in sites:
        print(f"\n\n{'#'*80}")
        print(f"# {site_name}")
        print(f"{'#'*80}")

        # Test WITHOUT filter first
        result_no_filter = await test_site(site_name, url, with_filter=False)
        if result_no_filter:
            all_results.append(result_no_filter)

        # Small delay to avoid overwhelming the servers
        await asyncio.sleep(2)

        # Test WITH filter
        result_with_filter = await test_site(site_name, url, with_filter=True)
        if result_with_filter:
            all_results.append(result_with_filter)

        # Delay between sites
        await asyncio.sleep(2)

    # Summary comparison
    print(f"\n\n{'='*80}")
    print("SUMMARY: Filter effectiveness across sites")
    print(f"{'='*80}")

    for site_name, _ in sites:
        without = next((r for r in all_results if r["site"] == site_name and not r["with_filter"]), None)
        with_f = next((r for r in all_results if r["site"] == site_name and r["with_filter"]), None)

        print(f"\n{site_name}:")
        if without and with_f:
            print(f"  WITHOUT filter: {without['pages'][0]['actual_size']} chars, Has nav: {without['pages'][0]['has_nav_text']}, Has footer: {without['pages'][0]['has_footer_text']}")
            print(f"  WITH filter:    {with_f['pages'][0]['actual_size']} chars, Has nav: {with_f['pages'][0]['has_nav_text']}, Has footer: {with_f['pages'][0]['has_footer_text']}")

            size_diff = without['pages'][0]['actual_size'] - with_f['pages'][0]['actual_size']
            percent_reduction = round(100 * size_diff / without['pages'][0]['actual_size'], 1)

            nav_improvement = without['pages'][0]['has_nav_text'] and not with_f['pages'][0]['has_nav_text']
            footer_improvement = without['pages'][0]['has_footer_text'] and not with_f['pages'][0]['has_footer_text']

            print(f"  Size reduction: {percent_reduction}% ({size_diff} chars)")
            if nav_improvement:
                print(f"  ✓ Navigation noise REMOVED")
            if footer_improvement:
                print(f"  ✓ Footer noise REMOVED")


if __name__ == "__main__":
    asyncio.run(main())
