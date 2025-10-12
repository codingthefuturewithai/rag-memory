"""
Website analysis utilities for sitemap parsing and URL pattern detection.

This module provides raw data extraction for AI agents to make informed decisions
about website crawling. NO heuristics or recommendations - just facts.
"""

import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class WebsiteAnalyzer:
    """Analyzes website structure by extracting and grouping URLs."""

    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize analyzer for a website.

        Args:
            base_url: The base URL of the website to analyze
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.parsed_base = urlparse(self.base_url)

    def fetch_sitemap(self) -> Tuple[Optional[List[str]], str]:
        """
        Attempt to fetch and parse sitemap.xml from common locations.

        Returns:
            Tuple of (list of URLs or None, method used for analysis)
            method is one of: "sitemap", "not_found", "error"
        """
        if not REQUESTS_AVAILABLE:
            return None, "error: requests library not available"

        # Try common sitemap locations
        sitemap_urls = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
            f"{self.base_url}/sitemap1.xml",
        ]

        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=self.timeout)
                if response.status_code == 200:
                    urls = self._parse_sitemap_xml(response.content)
                    if urls:
                        return urls, "sitemap"
            except Exception:
                continue

        return None, "not_found"

    def _parse_sitemap_xml(self, xml_content: bytes) -> List[str]:
        """
        Parse sitemap XML and extract all URLs.

        Handles both regular sitemaps and sitemap indexes (recursively).

        Args:
            xml_content: Raw XML content from sitemap

        Returns:
            List of URLs found in sitemap
        """
        urls = []

        try:
            root = ET.fromstring(xml_content)

            # Handle namespace (most sitemaps use http://www.sitemaps.org/schemas/sitemap/0.9)
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Check if this is a sitemap index (contains <sitemap> tags)
            sitemaps = root.findall('.//ns:sitemap/ns:loc', namespace)
            if sitemaps:
                # This is a sitemap index - fetch each referenced sitemap
                for sitemap_elem in sitemaps:
                    sitemap_url = sitemap_elem.text
                    if sitemap_url:
                        try:
                            response = requests.get(sitemap_url, timeout=self.timeout)
                            if response.status_code == 200:
                                urls.extend(self._parse_sitemap_xml(response.content))
                        except Exception:
                            continue

            # Extract URLs from <url><loc> tags
            url_elements = root.findall('.//ns:url/ns:loc', namespace)
            for url_elem in url_elements:
                url = url_elem.text
                if url:
                    urls.append(url)

            # Fallback: try without namespace (some sitemaps don't use it)
            if not urls:
                for loc in root.findall('.//loc'):
                    url = loc.text
                    if url:
                        urls.append(url)

        except ET.ParseError:
            pass

        return urls

    def group_urls_by_pattern(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        Group URLs by path patterns (e.g., /api/*, /docs/*).

        Simple path-based grouping with NO HEURISTICS. Just groups URLs
        that share the same first path segment.

        Args:
            urls: List of URLs to group

        Returns:
            Dictionary mapping pattern to list of URLs
            Example: {
                "/api": ["https://example.com/api/v1", "https://example.com/api/v2"],
                "/docs": ["https://example.com/docs/intro", "https://example.com/docs/guide"],
                "/": ["https://example.com/", "https://example.com/about"]
            }
        """
        groups: Dict[str, List[str]] = {}

        for url in urls:
            parsed = urlparse(url)

            # Only group URLs from the same domain
            if parsed.netloc != self.parsed_base.netloc:
                continue

            # Extract first path segment
            path = parsed.path.rstrip('/')
            if not path or path == '/':
                pattern = "/"
            else:
                # Get first segment: /docs/intro -> /docs
                segments = path.split('/')
                pattern = f"/{segments[1]}" if len(segments) > 1 else "/"

            if pattern not in groups:
                groups[pattern] = []
            groups[pattern].append(url)

        return groups

    def get_pattern_stats(self, url_groups: Dict[str, List[str]]) -> Dict[str, Dict]:
        """
        Calculate statistics for each URL pattern group.

        Args:
            url_groups: Dictionary from group_urls_by_pattern()

        Returns:
            Dictionary with stats for each pattern:
            {
                "/api": {
                    "count": 45,
                    "avg_depth": 2.3,
                    "example_urls": ["url1", "url2", "url3"]
                }
            }
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

            # Get up to 3 example URLs (shortest ones)
            sorted_urls = sorted(urls, key=lambda u: len(urlparse(u).path))
            examples = sorted_urls[:3]

            stats[pattern] = {
                "count": len(urls),
                "avg_depth": round(avg_depth, 1),
                "example_urls": examples,
            }

        return stats

    def analyze(self, include_url_lists: bool = False, max_urls_per_pattern: int = 10) -> Dict:
        """
        Perform complete website analysis.

        Returns raw data about website structure for AI agent to process.
        NO recommendations or heuristics - just facts.

        Args:
            include_url_lists: If False (default), only returns pattern_stats summary.
                              If True, includes full URL lists (may be large for sites with 1000s of URLs).
            max_urls_per_pattern: Maximum URLs to return per pattern when include_url_lists=True (default: 10)

        Returns:
            Dictionary with analysis results:
            {
                "base_url": str,
                "analysis_method": str,  # "sitemap" or "not_found"
                "total_urls": int,
                "pattern_stats": {  # Always included (lightweight summary)
                    "/pattern": {"count": int, "avg_depth": float, "example_urls": []}
                },
                "url_groups": {  # Only if include_url_lists=True (full URLs)
                    "/pattern": ["url1", "url2", ...]  # Limited to max_urls_per_pattern
                },
                "notes": str  # Important context about data quality
            }
        """
        # Try to fetch sitemap
        urls, method = self.fetch_sitemap()

        if not urls:
            return {
                "base_url": self.base_url,
                "analysis_method": method,
                "total_urls": 0,
                "pattern_stats": {},
                "notes": (
                    "No sitemap found at common locations (/sitemap.xml, /sitemap_index.xml). "
                    "Cannot analyze website structure. Consider manually specifying starting URLs."
                ),
            }

        # Group URLs by pattern
        url_groups = self.group_urls_by_pattern(urls)

        # Calculate stats
        pattern_stats = self.get_pattern_stats(url_groups)

        # Sort patterns by count (most URLs first)
        sorted_patterns = sorted(
            pattern_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )

        result = {
            "base_url": self.base_url,
            "analysis_method": method,
            "total_urls": len(urls),
            "pattern_stats": dict(sorted_patterns),
            "notes": (
                f"Sitemap found with {len(urls)} URLs grouped into {len(url_groups)} patterns. "
                "Each pattern represents URLs sharing the same first path segment (e.g., /api/*, /docs/*). "
                "Use pattern_stats to understand site structure. Set include_url_lists=True to get full URL lists."
            ),
        }

        # Optionally include full URL lists (limited per pattern to avoid overwhelming response)
        if include_url_lists:
            limited_url_groups = {}
            for pattern, urls_list in url_groups.items():
                # Limit URLs per pattern, prioritize shortest URLs (often index pages)
                sorted_urls = sorted(urls_list, key=lambda u: len(urlparse(u).path))
                limited_url_groups[pattern] = sorted_urls[:max_urls_per_pattern]
            result["url_groups"] = limited_url_groups
            result["notes"] += f" Full URL lists included (max {max_urls_per_pattern} URLs per pattern)."

        return result


def analyze_website(
    base_url: str,
    timeout: int = 10,
    include_url_lists: bool = False,
    max_urls_per_pattern: int = 10
) -> Dict:
    """
    Convenience function to analyze a website.

    Args:
        base_url: The base URL of the website to analyze
        timeout: Request timeout in seconds
        include_url_lists: If True, includes full URL lists (limited per pattern)
        max_urls_per_pattern: Max URLs per pattern when include_url_lists=True

    Returns:
        Analysis results dictionary (see WebsiteAnalyzer.analyze())
    """
    analyzer = WebsiteAnalyzer(base_url, timeout)
    return analyzer.analyze(include_url_lists, max_urls_per_pattern)
