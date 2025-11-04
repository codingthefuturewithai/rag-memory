#!/usr/bin/env python3
"""
Test analyze_website functionality against popular websites.
Uses the same logic as analyze_website but runs locally to avoid MCP server blocking.
"""

import asyncio
import time
from crawl4ai import AsyncWebCrawler, CacheMode
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

async def get_sitemap(base_url: str, timeout: int = 10) -> tuple[list[str], str]:
    """
    Attempt to fetch and parse sitemap from a website.
    Returns: (urls_found, sitemap_location)
    """
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    # Try provided URL first
    sitemap_urls = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
    ]

    # Try root domain
    sitemap_urls.extend([
        f"{domain}/sitemap.xml",
        f"{domain}/sitemap_index.xml",
    ])

    async with AsyncWebCrawler() as crawler:
        for sitemap_url in sitemap_urls:
            try:
                print(f"  Trying: {sitemap_url}")
                result = await asyncio.wait_for(
                    crawler.arun(
                        url=sitemap_url,
                        cache_mode=CacheMode.BYPASS,
                        bypass_cache_for_all=True,
                    ),
                    timeout=timeout
                )

                if result.status_code == 200:
                    # Try to parse as XML
                    try:
                        root = ET.fromstring(result.html)

                        # Extract URLs from sitemap
                        urls = []
                        # Handle sitemap_index
                        for elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                            urls.append(elem.text)

                        if urls:
                            sitemap_location = "provided URL" if "/sitemap" in sitemap_url else "root domain"
                            return urls, sitemap_location
                    except ET.ParseError:
                        continue
            except asyncio.TimeoutError:
                print(f"    → Timeout")
                continue
            except Exception as e:
                print(f"    → Error: {type(e).__name__}")
                continue

    return [], ""

async def analyze_website(base_url: str, timeout: int = 10):
    """
    Analyze a website to understand its structure.
    """
    print(f"\nAnalyzing: {base_url}")
    start_time = time.time()

    try:
        urls, sitemap_location = await asyncio.wait_for(
            get_sitemap(base_url, timeout),
            timeout=timeout + 2
        )
        elapsed = time.time() - start_time

        if urls:
            print(f"  ✓ Found sitemap ({sitemap_location}): {len(urls)} URLs")
            return {
                "base_url": base_url,
                "status": "success",
                "sitemap_found": True,
                "total_urls": len(urls),
                "sitemap_location": sitemap_location,
                "time_seconds": elapsed
            }
        else:
            print(f"  ✗ No sitemap found")
            return {
                "base_url": base_url,
                "status": "success",
                "sitemap_found": False,
                "total_urls": 0,
                "sitemap_location": "",
                "time_seconds": elapsed
            }
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        print(f"  ✗ TIMEOUT after {elapsed:.1f}s")
        return {
            "base_url": base_url,
            "status": "timeout",
            "sitemap_found": False,
            "total_urls": 0,
            "time_seconds": elapsed
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ✗ ERROR: {type(e).__name__}: {str(e)}")
        return {
            "base_url": base_url,
            "status": "error",
            "error": str(e),
            "time_seconds": elapsed
        }

async def main():
    """Test analyze_website on popular sites."""
    websites = [
        # Documentation
        "https://docs.python.org",
        "https://docs.djangoproject.com",
        "https://www.ruby-lang.org",
        "https://golang.org",
        "https://docs.microsoft.com",
        "https://docs.swift.org",
        "https://dart.dev",
        "https://kotlinlang.org",
        "https://www.scala-lang.org",
        "https://elixir-lang.org",
        # News/Content
        "https://www.bbc.com",
        "https://techcrunch.com",
        "https://medium.com",
        "https://dev.to",
        "https://hashnode.com",
        # Reference/Community
        "https://en.wikipedia.org",
        "https://github.com",
        "https://stackoverflow.com",
        "https://reddit.com",
        # Commerce/Services
        "https://www.amazon.com",
        "https://stripe.com",
        "https://twilio.com",
        "https://cloudflare.com",
        "https://blog.google",
        "https://aws.amazon.com",
        # Educational
        "https://www.coursera.org",
        "https://www.edx.org",
        "https://www.khanacademy.org",
        "https://www.w3schools.com",
        "https://developer.mozilla.org",
    ]

    results = []

    print("=" * 70)
    print("Testing analyze_website on popular sites")
    print("=" * 70)

    for url in websites:
        result = await analyze_website(url, timeout=10)
        results.append(result)
        await asyncio.sleep(0.5)  # Small delay between requests

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    sitemap_found = sum(1 for r in results if r.get("sitemap_found"))
    no_sitemap = sum(1 for r in results if not r.get("sitemap_found") and r.get("status") == "success")
    timeouts = sum(1 for r in results if r.get("status") == "timeout")
    errors = sum(1 for r in results if r.get("status") == "error")

    print(f"Total sites tested: {len(results)}")
    print(f"Sitemap found: {sitemap_found}")
    print(f"No sitemap (but accessible): {no_sitemap}")
    print(f"Timeouts: {timeouts}")
    print(f"Errors: {errors}")

    print("\nDetailed Results:")
    print("-" * 70)

    for result in results:
        url = result["base_url"]
        if result["status"] == "success":
            if result.get("sitemap_found"):
                print(f"✓ {url}: {result['total_urls']} URLs ({result['time_seconds']:.1f}s)")
            else:
                print(f"○ {url}: No sitemap ({result['time_seconds']:.1f}s)")
        elif result["status"] == "timeout":
            print(f"⏱ {url}: TIMEOUT ({result['time_seconds']:.1f}s)")
        else:
            print(f"✗ {url}: ERROR - {result.get('error', 'Unknown')}")

if __name__ == "__main__":
    asyncio.run(main())
