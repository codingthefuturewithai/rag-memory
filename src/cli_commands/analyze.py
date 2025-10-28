"""Analysis commands."""

import sys
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.table import Table

from src.ingestion.website_analyzer import analyze_website

console = Console()


@click.group()
def analyze():
    """Analyze various resources."""
    pass


@analyze.command("website")
@click.argument("url")
@click.option("--include-urls", is_flag=True, help="Include full URL lists per pattern")
@click.option("--max-urls", type=int, default=10, help="Max URLs per pattern when --include-urls (default: 10)")
@click.option("--timeout", type=int, default=10, help="Request timeout in seconds (default: 10)")
def analyze_website_cmd(url, include_urls, max_urls, timeout):
    """Analyze a website's structure by parsing its sitemap.

    This command fetches and parses the sitemap.xml from a website, then groups
    URLs by pattern (e.g., /api/*, /docs/*, /blog/*) to help you understand
    the site structure and plan comprehensive crawls.

    Examples:
        # Quick analysis (pattern statistics only)
        rag analyze website https://docs.python.org

        # Include sample URLs for each pattern
        rag analyze website https://docs.python.org --include-urls

        # Show more URLs per pattern
        rag analyze website https://docs.python.org --include-urls --max-urls 20
    """
    try:
        console.print(f"[bold blue]Analyzing website: {url}[/bold blue]\n")

        # Perform analysis
        result = analyze_website(url, timeout, include_urls, max_urls)

        # Show results
        if result["total_urls"] == 0:
            console.print(f"[yellow]⚠ {result['notes']}[/yellow]")
            return

        console.print(f"[green]✓ Found sitemap with {result['total_urls']:,} URLs[/green]")
        console.print(f"[dim]Method: {result['analysis_method']}[/dim]")

        # Show domains if multiple
        if "domains" in result and len(result["domains"]) > 1:
            console.print(f"[yellow]⚠ Sitemap contains URLs from {len(result['domains'])} domains:[/yellow]")
            for domain in result["domains"]:
                console.print(f"  • {domain}")
        elif "domains" in result and len(result["domains"]) == 1:
            console.print(f"[dim]Domain: {result['domains'][0]}[/dim]")

        console.print()

        # Display pattern statistics table
        if result["pattern_stats"]:
            table = Table(title="URL Pattern Statistics")
            table.add_column("Pattern", style="cyan", no_wrap=True)
            table.add_column("Count", style="green", justify="right")
            table.add_column("Avg Depth", style="blue", justify="right")
            table.add_column("Example URLs", style="white")

            for pattern, stats in result["pattern_stats"].items():
                # Format example URLs (show just paths, truncate if needed)
                examples = stats["example_urls"][:3]
                example_text = "\n".join([
                    urlparse(url).path[:50] + ("..." if len(urlparse(url).path) > 50 else "")
                    for url in examples
                ])

                table.add_row(
                    pattern,
                    str(stats["count"]),
                    str(stats["avg_depth"]),
                    example_text
                )

            console.print(table)

        # Show full URL lists if requested
        if include_urls and "url_groups" in result:
            console.print(f"\n[bold cyan]URL Lists (max {max_urls} per pattern):[/bold cyan]\n")
            for pattern, urls in result["url_groups"].items():
                console.print(f"[bold]{pattern}[/bold] ({len(urls)} URLs):")
                for url in urls:
                    console.print(f"  • {url}")
                console.print()

        console.print(f"\n[dim]{result['notes']}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
