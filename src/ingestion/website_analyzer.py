"""
Website analysis utilities for discovering URL patterns.

This module provides raw data extraction for AI agents to make informed decisions
about website crawling. Discovers URLs from public sources with 50-second timeout
and graceful error handling.

NO heuristics or recommendations - just facts.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from crawl4ai import AsyncUrlSeeder, SeedingConfig
    ASYNCURLSEEDER_AVAILABLE = True
except ImportError:
    ASYNCURLSEEDER_AVAILABLE = False

logger = logging.getLogger(__name__)


class WebsiteAnalyzer:
    """
    Analyzes website structure by discovering URL patterns.

    Discovers URLs from public sources (sitemaps and search indexes).
    Includes 50-second timeout with graceful error handling.
    """

    ANALYSIS_TIMEOUT = 50  # seconds - hard timeout for complete analysis
    MAX_URLS = 150  # Maximum URLs to discover per site

    def __init__(self, base_url: str):
        """
        Initialize analyzer for a website.

        Args:
            base_url: The base URL of the website to analyze
                     (can be root domain or specific path)
        """
        self.base_url = base_url.rstrip('/')
        self.parsed_base = urlparse(self.base_url)
        self.domain = self.parsed_base.netloc
        if not self.domain:
            raise ValueError(f"Invalid URL: {base_url}")

    async def analyze_async(
        self,
        include_url_lists: bool = False,
        max_urls_per_pattern: int = 10
    ) -> Dict[str, Any]:
        """
        Perform complete website analysis with AsyncUrlSeeder.

        Uses 50-second timeout. Returns structured response in ALL scenarios:
        success, timeout, error, missing AsyncUrlSeeder, etc.

        Args:
            include_url_lists: If False (default), only returns pattern_stats summary.
                              If True, includes full URL lists per pattern.
            max_urls_per_pattern: Max URLs per pattern when include_url_lists=True

        Returns:
            Dictionary with analysis results. ALWAYS includes:
            - base_url: Input URL
            - analysis_method: "asyncurlseeder", "timeout", "error", "not_available"
            - total_urls: Number of URLs discovered (0 on error/timeout)
            - pattern_stats: Dictionary of URL patterns or empty dict
            - notes: Informative message about what happened

            May include (on success):
            - url_groups: Full URL lists if include_url_lists=True
            - domains: List of domains found
            - elapsed_seconds: Time taken for analysis
        """
        if not ASYNCURLSEEDER_AVAILABLE:
            return self._error_response(
                analysis_method="not_available",
                error="tool_unavailable",
                message=(
                    "Website analysis tool is not available. "
                    "This is typically a setup issue. Contact support for details."
                )
            )

        try:
            # Run analysis with 50-second hard timeout
            result = await asyncio.wait_for(
                self._perform_analysis(include_url_lists, max_urls_per_pattern),
                timeout=self.ANALYSIS_TIMEOUT
            )
            return result

        except asyncio.TimeoutError:
            # Timeout - 50+ seconds elapsed
            return self._error_response(
                analysis_method="timeout",
                error="timeout",
                message=(
                    f"Website analysis exceeded {self.ANALYSIS_TIMEOUT}-second timeout. "
                    "Site may be too large for automatic analysis. "
                    "Try analyzing a specific subsection (e.g., /docs, /api) "
                    "or use manual crawling with limited depth."
                )
            )

        except Exception as e:
            # Any other error during analysis
            error_type = type(e).__name__
            error_msg = str(e)
            logger.error(f"Website analysis error for {self.base_url}: {error_type}: {error_msg}")

            return self._error_response(
                analysis_method="error",
                error=error_type,
                message=(
                    f"Analysis failed ({error_type}): {error_msg}. "
                    "Unable to discover website structure. "
                    "Try using manual crawling with BFS strategy."
                )
            )

    async def _perform_analysis(
        self,
        include_url_lists: bool,
        max_urls_per_pattern: int
    ) -> Dict[str, Any]:
        """
        Perform the actual AsyncUrlSeeder analysis.

        Separated from analyze_async to isolate timeout handling.
        """
        start_time = time.time()

        # Use AsyncUrlSeeder with sitemap+cc source
        async with AsyncUrlSeeder() as seeder:
            config = SeedingConfig(
                source="sitemap+cc",              # Try sitemap, fall back to Common Crawl
                max_urls=self.MAX_URLS,           # Limit to 150 URLs
                live_check=False,                 # Speed over verification
                filter_nonsense_urls=True,        # Filter robots.txt, .css, etc
                verbose=False,                    # Reduce logging
            )

            # Fetch URLs from sitemap or Common Crawl
            urls = await seeder.urls(self.domain, config)

        elapsed = time.time() - start_time

        if not urls:
            # No URLs discovered
            return self._error_response(
                analysis_method="error",
                error="no_urls",
                message=(
                    f"No publicly discoverable URLs found for {self.domain}. "
                    "This may indicate: site behind authentication, "
                    "no sitemap and not indexed by public indexes, or "
                    "robots.txt blocking. "
                    "Try manual crawling if you have access."
                ),
                elapsed_seconds=round(elapsed, 2)
            )

        # Group and analyze discovered URLs
        url_dicts = urls
        url_strings = [u.get('url', '') if isinstance(u, dict) else u for u in url_dicts]
        url_strings = [u for u in url_strings if u]  # Filter empty

        if not url_strings:
            return self._error_response(
                analysis_method="error",
                error="no_valid_urls",
                message="URLs discovered but none were valid. This is an internal error.",
                elapsed_seconds=round(elapsed, 2)
            )

        # Group by pattern
        url_groups = self._group_urls_by_pattern(url_strings)
        pattern_stats = self._get_pattern_stats(url_groups)

        # Sort patterns by count
        sorted_patterns = sorted(
            pattern_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        # Extract domains
        domains = set()
        for url in url_strings:
            parsed = urlparse(url)
            if parsed.netloc:
                domains.add(parsed.netloc)

        # Build response
        result = {
            "base_url": self.base_url,
            "analysis_method": "success",
            "total_urls": len(url_strings),
            "url_patterns": len(url_groups),
            "elapsed_seconds": round(elapsed, 2),
            "pattern_stats": dict(sorted_patterns),
            "domains": sorted(list(domains)),
            "notes": self._build_success_notes(
                len(url_strings), len(url_groups), domains, elapsed
            ),
        }

        # Optionally include full URL lists
        if include_url_lists:
            limited_url_groups = {}
            for pattern, urls_list in url_groups.items():
                sorted_urls = sorted(urls_list, key=lambda u: len(urlparse(u).path))
                limited_url_groups[pattern] = sorted_urls[:max_urls_per_pattern]
            result["url_groups"] = limited_url_groups
            result["notes"] += f" Full URL lists included (max {max_urls_per_pattern} URLs per pattern)."

        return result

    def _group_urls_by_pattern(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        Group URLs by path patterns (e.g., /api/*, /docs/*).

        Simple path-based grouping: groups URLs sharing the same first path segment.

        Args:
            urls: List of URL strings

        Returns:
            Dictionary mapping pattern to list of URLs
            Example: {"/api": [url1, url2], "/docs": [url3, url4]}
        """
        groups: Dict[str, List[str]] = {}

        for url in urls:
            parsed = urlparse(url)
            path = parsed.path.rstrip('/')

            if not path or path == '/':
                pattern = "/"
            else:
                segments = path.split('/')
                pattern = f"/{segments[1]}" if len(segments) > 1 else "/"

            if pattern not in groups:
                groups[pattern] = []
            groups[pattern].append(url)

        return groups

    def _get_pattern_stats(self, url_groups: Dict[str, List[str]]) -> Dict[str, Dict]:
        """
        Calculate statistics for each URL pattern group.

        Args:
            url_groups: Dictionary from _group_urls_by_pattern()

        Returns:
            Statistics dict with count, avg_depth, example_urls for each pattern
        """
        stats = {}

        for pattern, urls in url_groups.items():
            # Calculate average path depth
            depths = []
            for url in urls:
                parsed = urlparse(url)
                path = parsed.path.rstrip('/')
                depth = len([s for s in path.split('/') if s])
                depths.append(depth)

            avg_depth = sum(depths) / len(depths) if depths else 0

            # Get up to 3 example URLs (shortest ones = typically most important)
            sorted_urls = sorted(urls, key=lambda u: len(urlparse(u).path))
            examples = sorted_urls[:3]

            stats[pattern] = {
                "count": len(urls),
                "avg_depth": round(avg_depth, 1),
                "example_urls": examples,
            }

        return stats

    def _error_response(
        self,
        analysis_method: str,
        error: str,
        message: str,
        elapsed_seconds: float = 0
    ) -> Dict[str, Any]:
        """
        Build structured error response.

        Ensures agent always gets valid response even on failure.

        Args:
            analysis_method: "timeout", "error", "not_available", etc
            error: Short error code
            message: Informative user-friendly message
            elapsed_seconds: How long analysis took before failure

        Returns:
            Valid response dict (same structure as success, but with error info)
        """
        return {
            "base_url": self.base_url,
            "analysis_method": analysis_method,
            "error": error,
            "total_urls": 0,
            "pattern_stats": {},
            "notes": message,
            "elapsed_seconds": round(elapsed_seconds, 2),
        }

    def _build_success_notes(
        self,
        total_urls: int,
        num_patterns: int,
        domains: set,
        elapsed: float
    ) -> str:
        """
        Build informative notes for successful analysis.

        Args:
            total_urls: Number of URLs discovered
            num_patterns: Number of patterns found
            domains: Set of domains in results
            elapsed: Seconds taken

        Returns:
            Informative notes string
        """
        notes_parts = [
            f"Discovered {total_urls} URLs in {elapsed:.2f}s.",
            f"URLs grouped into {num_patterns} patterns by first path segment.",
        ]

        if len(domains) > 1:
            domain_list = ', '.join(sorted(list(domains))[:3])
            if len(domains) > 3:
                domain_list += f" (+ {len(domains) - 3} more)"
            notes_parts.append(f"Domains: {domain_list}.")

        notes_parts.append(
            "Each pattern (e.g., /api, /docs) represents URLs sharing the same first path segment. "
            "Use pattern statistics to understand site structure."
        )

        return " ".join(notes_parts)


async def analyze_website_async(
    base_url: str,
    include_url_lists: bool = False,
    max_urls_per_pattern: int = 10
) -> Dict[str, Any]:
    """
    Async convenience function to analyze a website.

    Args:
        base_url: The base URL of the website to analyze
        include_url_lists: If True, includes full URL lists (limited per pattern)
        max_urls_per_pattern: Max URLs per pattern when include_url_lists=True

    Returns:
        Analysis results dictionary with guaranteed structure even on error.
        See WebsiteAnalyzer.analyze_async() for details.
    """
    try:
        analyzer = WebsiteAnalyzer(base_url)
        return await analyzer.analyze_async(include_url_lists, max_urls_per_pattern)
    except ValueError as e:
        # Invalid URL
        return {
            "base_url": base_url,
            "analysis_method": "error",
            "error": "invalid_url",
            "total_urls": 0,
            "pattern_stats": {},
            "notes": f"Invalid URL: {str(e)}",
            "elapsed_seconds": 0,
        }
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in analyze_website_async: {e}")
        return {
            "base_url": base_url,
            "analysis_method": "error",
            "error": "unexpected_error",
            "total_urls": 0,
            "pattern_stats": {},
            "notes": f"Unexpected error: {str(e)}",
            "elapsed_seconds": 0,
        }
