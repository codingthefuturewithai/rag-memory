#!/usr/bin/env python
"""
Test script for new MCP features:
- Website analysis
- Duplicate crawl detection
- Collection info with crawl history
"""

import asyncio
from src.mcp.tools import analyze_website_impl, check_existing_crawl
from src.core.database import get_database
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def test_website_analysis():
    """Test website analysis with sitemap parsing."""
    console.print("\n[bold]Test 1: Website Analysis[/bold]")

    # Test with Claude docs (has sitemap)
    result = analyze_website_impl("https://docs.claude.com", timeout=10)

    console.print(f"  Base URL: {result['base_url']}")
    console.print(f"  Analysis Method: {result['analysis_method']}")
    console.print(f"  Total URLs: {result['total_urls']}")
    console.print(f"  URL Groups: {len(result['url_groups'])}")

    # Show top 3 patterns
    table = Table(title="Top URL Patterns")
    table.add_column("Pattern", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Avg Depth", justify="right", style="yellow")
    table.add_column("Example URL", style="dim")

    for pattern, stats in list(result['pattern_stats'].items())[:5]:
        table.add_row(
            pattern,
            str(stats['count']),
            str(stats['avg_depth']),
            stats['example_urls'][0] if stats['example_urls'] else "N/A"
        )

    console.print(table)
    console.print(f"  Notes: {result['notes'][:100]}...")

    return result['total_urls'] > 0


def test_duplicate_detection():
    """Test duplicate crawl detection."""
    console.print("\n[bold]Test 2: Duplicate Crawl Detection[/bold]")

    db = get_database()

    # Check for existing crawl (should return None for non-existent)
    result = check_existing_crawl(
        db,
        "https://example.com/nonexistent",
        "test-collection"
    )

    if result is None:
        console.print("  ✓ No existing crawl found (expected)")
        return True
    else:
        console.print(f"  ✗ Unexpected result: {result}")
        return False


def test_collection_info_enhancement():
    """Test that get_collection_info includes crawled_urls."""
    console.print("\n[bold]Test 3: Collection Info with Crawl History[/bold]")

    from src.core.collections import get_collection_manager
    from src.mcp.tools import get_collection_info_impl

    db = get_database()
    coll_mgr = get_collection_manager(db)

    # Get existing collection (claude-agent-sdk from earlier tests)
    try:
        result = get_collection_info_impl(db, coll_mgr, "claude-agent-sdk")

        console.print(f"  Collection: {result['name']}")
        console.print(f"  Documents: {result['document_count']}")
        console.print(f"  Chunks: {result['chunk_count']}")
        console.print(f"  Crawled URLs: {len(result['crawled_urls'])}")

        if result['crawled_urls']:
            for crawl in result['crawled_urls'][:3]:
                console.print(f"    - {crawl['url']}")
                console.print(f"      Pages: {crawl['page_count']}, Chunks: {crawl['chunk_count']}")
                console.print(f"      Timestamp: {crawl['timestamp']}")

        return 'crawled_urls' in result
    except ValueError as e:
        console.print(f"  ℹ️  Collection not found (OK for fresh setup): {e}")
        return True


def main():
    console.print(Panel.fit(
        "[bold cyan]Testing New MCP Features[/bold cyan]",
        border_style="blue"
    ))

    results = {
        "Website Analysis": test_website_analysis(),
        "Duplicate Detection": test_duplicate_detection(),
        "Collection Info Enhancement": test_collection_info_enhancement(),
    }

    console.print("\n[bold]Test Results:[/bold]")
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        color = "green" if passed else "red"
        console.print(f"  [{color}]{status}[/{color}] {test_name}")

    all_passed = all(results.values())
    if all_passed:
        console.print("\n[bold green]All tests passed! ✓[/bold green]")
    else:
        console.print("\n[bold red]Some tests failed ✗[/bold red]")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
