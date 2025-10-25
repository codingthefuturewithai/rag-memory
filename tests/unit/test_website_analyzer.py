"""Unit tests for website_analyzer module."""

import pytest
from unittest.mock import MagicMock, patch, Mock
import xml.etree.ElementTree as ET
from datetime import datetime
from src.ingestion.website_analyzer import WebsiteAnalyzer, analyze_website


class TestWebsiteAnalyzer:
    """Tests for WebsiteAnalyzer class."""

    def test_init(self):
        """Test WebsiteAnalyzer initialization."""
        analyzer = WebsiteAnalyzer("https://example.com/", timeout=30)
        assert analyzer.base_url == "https://example.com"
        assert analyzer.timeout == 30

    @patch('requests.get')
    def test_fetch_sitemap_success(self, mock_get):
        """Test successful sitemap fetch."""
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>'''
        mock_get.return_value = mock_response

        urls, method = analyzer.fetch_sitemap()

        assert method == "sitemap"
        assert len(urls) == 2
        assert "https://example.com/page1" in urls

    @patch('requests.get')
    def test_fetch_sitemap_not_found(self, mock_get):
        """Test sitemap not found."""
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        urls, method = analyzer.fetch_sitemap()

        assert method == "not_found"
        assert urls is None

    @patch('requests.get')
    def test_fetch_sitemap_timeout(self, mock_get):
        """Test sitemap fetch timeout."""
        import requests
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_get.side_effect = requests.Timeout("Timeout")

        urls, method = analyzer.fetch_sitemap()

        assert method == "not_found"
        assert urls is None

    def test_parse_sitemap_xml_regular(self):
        """Test parsing regular sitemap XML using private method."""
        analyzer = WebsiteAnalyzer("https://example.com")

        xml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/page1</loc>
                <lastmod>2024-01-01</lastmod>
            </url>
            <url>
                <loc>https://example.com/page2</loc>
            </url>
        </urlset>'''

        # _parse_sitemap_xml is a private method that exists
        urls = analyzer._parse_sitemap_xml(xml_content)

        assert len(urls) == 2
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls

    @patch('requests.get')
    def test_parse_sitemap_xml_index(self, mock_get):
        """Test parsing sitemap index."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock the sub-sitemap fetch
        sub_sitemap = MagicMock()
        sub_sitemap.status_code = 200
        sub_sitemap.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
        </urlset>'''
        mock_get.return_value = sub_sitemap

        index_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
        </sitemapindex>'''

        urls = analyzer._parse_sitemap_xml(index_content)

        assert len(urls) == 1
        assert "https://example.com/page1" in urls

    def test_parse_sitemap_xml_invalid(self):
        """Test parsing invalid XML."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = analyzer._parse_sitemap_xml(b"not valid xml")
        assert urls == []

    def test_parse_sitemap_xml_empty(self):
        """Test parsing empty sitemap."""
        analyzer = WebsiteAnalyzer("https://example.com")

        xml_content = b'<?xml version="1.0" encoding="UTF-8"?><urlset></urlset>'
        urls = analyzer._parse_sitemap_xml(xml_content)
        assert urls == []

    def test_group_urls_by_pattern(self):
        """Test URL grouping by pattern using the actual public method."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/blog/post1",
            "https://example.com/blog/post2",
            "https://example.com/products/item1",
            "https://external.com/page"  # Different domain - will still be grouped
        ]

        # Use the actual public method: group_urls_by_pattern
        patterns = analyzer.group_urls_by_pattern(urls)

        # Patterns are "/blog" NOT "/blog/*"
        assert "/" in patterns
        assert "/about" in patterns  # Single segment paths get their own pattern
        assert "/blog" in patterns  # First segment only, no wildcard
        assert len(patterns["/blog"]) == 2
        assert "/products" in patterns

    def test_group_urls_by_pattern_max_limit(self):
        """Test URL grouping with many URLs."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = [f"https://example.com/blog/post{i}" for i in range(20)]
        patterns = analyzer.group_urls_by_pattern(urls)

        # Pattern is "/blog" not "/blog/*"
        assert "/blog" in patterns
        assert len(patterns["/blog"]) == 20  # group_urls_by_pattern doesn't limit

    def test_get_pattern_stats(self):
        """Test pattern statistics building using the actual public method."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Prepare input in the format group_urls_by_pattern would return
        url_groups = {
            "/": ["https://example.com/"],
            "/blog": [
                "https://example.com/blog/post1",
                "https://example.com/blog/post2"
            ],
            "/docs": [
                "https://example.com/docs/intro",
                "https://example.com/docs/api/v1",
                "https://example.com/docs/guides/advanced/setup"
            ]
        }

        # Use the actual public method: get_pattern_stats
        stats = analyzer.get_pattern_stats(url_groups)

        # Check homepage
        assert stats["/"]["count"] == 1
        assert stats["/"]["avg_depth"] == 0

        # Check blog
        assert stats["/blog"]["count"] == 2
        assert stats["/blog"]["avg_depth"] == 2

        # Check docs (varying depths: 2, 3, 4 -> avg 3)
        assert stats["/docs"]["count"] == 3
        assert stats["/docs"]["avg_depth"] == 3

        # Check example URLs are limited to 3
        assert len(stats["/blog"]["example_urls"]) <= 3

    @patch('requests.get')
    def test_analyze_with_sitemap(self, mock_get):
        """Test full analysis with sitemap."""
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/</loc></url>
            <url><loc>https://example.com/about</loc></url>
            <url><loc>https://example.com/blog/post1</loc></url>
            <url><loc>https://example.com/blog/post2</loc></url>
        </urlset>'''
        mock_get.return_value = mock_response

        result = analyzer.analyze(include_url_lists=False)

        assert result["base_url"] == "https://example.com"
        assert result["analysis_method"] == "sitemap"
        assert result["total_urls"] == 4
        assert "/" in result["pattern_stats"]
        assert "/about" in result["pattern_stats"]
        # Pattern is "/blog" NOT "/blog/*"
        assert "/blog" in result["pattern_stats"]
        assert "url_groups" not in result  # Not included when include_url_lists=False

    @patch('requests.get')
    def test_analyze_with_url_lists(self, mock_get):
        """Test analysis with URL lists included."""
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
        </urlset>'''
        mock_get.return_value = mock_response

        result = analyzer.analyze(include_url_lists=True)

        assert "url_groups" in result
        assert "/page1" in result["url_groups"]
        assert "/page2" in result["url_groups"]

    @patch('requests.get')
    def test_analyze_no_sitemap(self, mock_get):
        """Test analysis when no sitemap found."""
        analyzer = WebsiteAnalyzer("https://example.com")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = analyzer.analyze()

        assert result["base_url"] == "https://example.com"
        assert result["analysis_method"] == "not_found"
        assert result["total_urls"] == 0
        assert result["pattern_stats"] == {}
        assert "sitemap" in result["notes"].lower()


class TestAnalyzeWebsiteFunction:
    """Tests for the analyze_website convenience function."""

    @patch('requests.get')
    def test_analyze_website_function(self, mock_get):
        """Test the standalone analyze_website function."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
        </urlset>'''
        mock_get.return_value = mock_response

        result = analyze_website("https://example.com", timeout=15, include_url_lists=True)

        assert result["base_url"] == "https://example.com"
        assert result["total_urls"] == 1
        assert result["analysis_method"] == "sitemap"

    @patch('requests.get')
    def test_analyze_website_connection_error(self, mock_get):
        """Test analyze_website with connection error."""
        import requests
        mock_get.side_effect = requests.ConnectionError("Connection failed")

        result = analyze_website("https://example.com")

        assert result["analysis_method"] == "not_found"
        assert result["total_urls"] == 0

    @patch('requests.get')
    def test_analyze_website_max_urls(self, mock_get):
        """Test analyze_website respects max_urls_per_pattern."""
        # Create sitemap with many URLs
        urls = ''.join([f'<url><loc>https://example.com/blog/post{i}</loc></url>'
                       for i in range(20)])
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = f'''<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {urls}
        </urlset>'''.encode()
        mock_get.return_value = mock_response

        result = analyze_website("https://example.com", include_url_lists=True, max_urls_per_pattern=5)

        # Pattern is "/blog" NOT "/blog/*"
        assert result["pattern_stats"]["/blog"]["count"] == 20
        # URL groups should be limited
        assert len(result["url_groups"]["/blog"]) == 5


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('src.ingestion.website_analyzer.REQUESTS_AVAILABLE', False)
    def test_no_requests_library(self):
        """Test behavior when requests library not available."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls, method = analyzer.fetch_sitemap()
        assert method == "error: requests library not available"
        assert urls is None

    def test_url_patterns_with_different_structures(self):
        """Test URL pattern extraction with various URL structures."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Test that group_urls_by_pattern handles various cases
        urls = [
            "https://example.com/",  # Root
            "https://example.com/about",  # Single segment
            "https://example.com/blog/post1",  # Two segments
            "https://example.com/api/v1/users",  # Multiple segments
            "https://example.com:8080/page",  # With port
            "https://subdomain.example.com/page",  # Different subdomain
        ]

        patterns = analyzer.group_urls_by_pattern(urls)

        # Verify the grouping works as expected
        assert "/" in patterns
        assert "/about" in patterns
        assert "/blog" in patterns
        assert "/api" in patterns
        assert "/page" in patterns  # Port and subdomain URLs still get grouped

    def test_pattern_stats_with_empty_group(self):
        """Test get_pattern_stats handles empty URL lists."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Empty input
        stats = analyzer.get_pattern_stats({})
        assert stats == {}

        # Group with empty URL list
        stats = analyzer.get_pattern_stats({"/empty": []})
        assert stats["/empty"]["count"] == 0
        assert stats["/empty"]["avg_depth"] == 0