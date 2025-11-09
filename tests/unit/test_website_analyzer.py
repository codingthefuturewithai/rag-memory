"""Unit tests for website_analyzer module."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
from src.ingestion.website_analyzer import WebsiteAnalyzer, analyze_website_async


class TestWebsiteAnalyzer:
    """Tests for WebsiteAnalyzer class."""

    def test_init(self):
        """Test WebsiteAnalyzer initialization."""
        analyzer = WebsiteAnalyzer("https://example.com/")
        assert analyzer.base_url == "https://example.com"
        assert analyzer.domain == "example.com"

    def test_init_invalid_url(self):
        """Test initialization with invalid URL."""
        with pytest.raises(ValueError, match="Invalid URL"):
            WebsiteAnalyzer("not-a-url")

    def test_group_urls_by_pattern(self):
        """Test URL grouping by pattern using private method."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/blog/post1",
            "https://example.com/blog/post2",
            "https://example.com/products/item1",
            "https://external.com/page"
        ]

        # Test private method directly
        patterns = analyzer._group_urls_by_pattern(urls)

        # Patterns are first path segment: "/", "/about", "/blog", "/products", "/page"
        assert "/" in patterns
        assert "/about" in patterns
        assert "/blog" in patterns
        assert len(patterns["/blog"]) == 2
        assert "/products" in patterns
        assert "/page" in patterns  # External domain still grouped by path

    def test_group_urls_by_pattern_many_urls(self):
        """Test URL grouping with many URLs in same pattern."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = [f"https://example.com/blog/post{i}" for i in range(20)]
        patterns = analyzer._group_urls_by_pattern(urls)

        # All should be grouped under "/blog"
        assert "/blog" in patterns
        assert len(patterns["/blog"]) == 20

    def test_get_pattern_stats(self):
        """Test pattern statistics calculation using private method."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Prepare input in the format _group_urls_by_pattern would return
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

        # Test private method directly
        stats = analyzer._get_pattern_stats(url_groups)

        # Check homepage
        assert stats["/"]["count"] == 1
        assert stats["/"]["avg_depth"] == 0

        # Check blog
        assert stats["/blog"]["count"] == 2
        assert stats["/blog"]["avg_depth"] == 2.0

        # Check docs (depths: 2, 3, 4 -> avg 3)
        assert stats["/docs"]["count"] == 3
        assert stats["/docs"]["avg_depth"] == 3.0

        # Check example URLs are limited to 3
        assert len(stats["/blog"]["example_urls"]) <= 3
        assert len(stats["/docs"]["example_urls"]) <= 3

    def test_get_pattern_stats_empty(self):
        """Test pattern stats with empty input."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Empty input
        stats = analyzer._get_pattern_stats({})
        assert stats == {}

        # Group with empty URL list
        stats = analyzer._get_pattern_stats({"/empty": []})
        assert stats["/empty"]["count"] == 0
        assert stats["/empty"]["avg_depth"] == 0

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', False)
    async def test_analyze_async_tool_not_available(self):
        """Test analyze_async when AsyncUrlSeeder not available."""
        analyzer = WebsiteAnalyzer("https://example.com")

        result = await analyzer.analyze_async()

        assert result["status"] == "not_available"
        assert result["error"] == "tool_unavailable"
        assert result["total_urls"] == 0
        assert result["pattern_stats"] == {}
        assert "not available" in result["notes"]

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_success(self):
        """Test successful website analysis."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)

        # Mock URLs returned by seeder
        mock_urls = [
            {"url": "https://example.com/"},
            {"url": "https://example.com/about"},
            {"url": "https://example.com/blog/post1"},
            {"url": "https://example.com/blog/post2"},
        ]
        mock_seeder.urls = AsyncMock(return_value=mock_urls)

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async(include_url_lists=False)

        assert result["status"] == "success"
        assert result["base_url"] == "https://example.com"
        assert result["total_urls"] == 4
        assert "/" in result["pattern_stats"]
        assert "/about" in result["pattern_stats"]
        assert "/blog" in result["pattern_stats"]
        assert result["pattern_stats"]["/blog"]["count"] == 2
        assert "url_groups" not in result  # Not included when include_url_lists=False
        assert "domains" in result
        assert "elapsed_seconds" in result

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_with_url_lists(self):
        """Test analysis with URL lists included."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)

        mock_urls = [
            {"url": "https://example.com/page1"},
            {"url": "https://example.com/page2"},
        ]
        mock_seeder.urls = AsyncMock(return_value=mock_urls)

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async(include_url_lists=True, max_urls_per_pattern=10)

        assert result["status"] == "success"
        assert "url_groups" in result
        assert "/page1" in result["url_groups"]
        assert "/page2" in result["url_groups"]

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_no_urls_found(self):
        """Test analysis when no URLs discovered."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder returning empty list
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(return_value=[])

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async()

        assert result["status"] == "error"
        assert result["error"] == "no_urls"
        assert result["total_urls"] == 0
        assert result["pattern_stats"] == {}
        assert "No publicly discoverable URLs" in result["notes"]

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_timeout(self):
        """Test analysis timeout handling."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder that takes too long
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)

        # Simulate timeout by raising asyncio.TimeoutError in urls()
        async def slow_urls(*args, **kwargs):
            import asyncio
            await asyncio.sleep(60)  # Longer than ANALYSIS_TIMEOUT

        mock_seeder.urls = slow_urls

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async()

        assert result["status"] == "timeout"
        assert result["error"] == "timeout"
        assert result["total_urls"] == 0
        assert "exceeded" in result["notes"].lower()

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_network_error(self):
        """Test analysis with network error."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder raising connection error
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(side_effect=ConnectionError("Network error"))

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async()

        assert result["status"] == "error"
        assert result["error"] == "network_error"
        assert result["total_urls"] == 0
        assert "Network error" in result["notes"]

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_url_error(self):
        """Test analysis with URL-related error."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder raising URL error
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(side_effect=ValueError("Invalid URL format"))

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async()

        assert result["status"] == "error"
        assert result["error"] == "invalid_url"
        assert result["total_urls"] == 0

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_async_generic_error(self):
        """Test analysis with generic error."""
        analyzer = WebsiteAnalyzer("https://example.com")

        # Mock AsyncUrlSeeder raising generic error
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(side_effect=RuntimeError("Something went wrong"))

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyzer.analyze_async()

        assert result["status"] == "error"
        assert result["error"] == "analysis_failed"
        assert result["total_urls"] == 0


class TestAnalyzeWebsiteFunction:
    """Tests for the analyze_website_async convenience function."""

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_website_function_success(self):
        """Test the standalone analyze_website_async function."""
        # Mock AsyncUrlSeeder
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(return_value=[{"url": "https://example.com/page1"}])

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyze_website_async(
                base_url="https://example.com",
                include_url_lists=True
            )

        assert result["base_url"] == "https://example.com"
        assert result["total_urls"] == 1
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_analyze_website_invalid_url(self):
        """Test analyze_website_async with invalid URL."""
        result = await analyze_website_async(base_url="not-a-url")

        assert result["status"] == "error"
        assert result["error"] == "invalid_url"
        assert result["total_urls"] == 0

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_website_connection_error(self):
        """Test analyze_website_async with connection error."""
        # Mock AsyncUrlSeeder raising connection error
        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(side_effect=ConnectionError("Connection failed"))

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyze_website_async(base_url="https://example.com")

        assert result["status"] == "error"
        assert result["total_urls"] == 0

    @pytest.mark.asyncio
    @patch('src.ingestion.website_analyzer.ASYNCURLSEEDER_AVAILABLE', True)
    async def test_analyze_website_max_urls_per_pattern(self):
        """Test analyze_website_async respects max_urls_per_pattern."""
        # Mock AsyncUrlSeeder with many URLs in same pattern
        mock_urls = [{"url": f"https://example.com/blog/post{i}"} for i in range(20)]

        mock_seeder = AsyncMock()
        mock_seeder.__aenter__ = AsyncMock(return_value=mock_seeder)
        mock_seeder.__aexit__ = AsyncMock(return_value=None)
        mock_seeder.urls = AsyncMock(return_value=mock_urls)

        with patch('src.ingestion.website_analyzer.AsyncUrlSeeder', return_value=mock_seeder):
            result = await analyze_website_async(
                base_url="https://example.com",
                include_url_lists=True,
                max_urls_per_pattern=5
            )

        # Pattern stats should show all 20 URLs
        assert result["pattern_stats"]["/blog"]["count"] == 20
        # But url_groups should be limited to 5
        assert len(result["url_groups"]["/blog"]) == 5


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_url_patterns_with_different_structures(self):
        """Test URL pattern extraction with various URL structures."""
        analyzer = WebsiteAnalyzer("https://example.com")

        urls = [
            "https://example.com/",  # Root
            "https://example.com/about",  # Single segment
            "https://example.com/blog/post1",  # Two segments
            "https://example.com/api/v1/users",  # Multiple segments
            "https://example.com:8080/page",  # With port
            "https://subdomain.example.com/page",  # Different subdomain
        ]

        patterns = analyzer._group_urls_by_pattern(urls)

        # Verify the grouping works as expected
        assert "/" in patterns
        assert "/about" in patterns
        assert "/blog" in patterns
        assert "/api" in patterns
        assert "/page" in patterns

    def test_error_response_structure(self):
        """Test that error responses have consistent structure."""
        analyzer = WebsiteAnalyzer("https://example.com")

        result = analyzer._error_response(
            status="error",
            error="test_error",
            message="Test error message",
            elapsed_seconds=1.5
        )

        # Check required fields
        assert result["base_url"] == "https://example.com"
        assert result["status"] == "error"
        assert result["error"] == "test_error"
        assert result["total_urls"] == 0
        assert result["pattern_stats"] == {}
        assert result["notes"] == "Test error message"
        assert result["elapsed_seconds"] == 1.5

    def test_build_success_notes(self):
        """Test success notes generation."""
        analyzer = WebsiteAnalyzer("https://example.com")

        notes = analyzer._build_success_notes(
            total_urls=50,
            num_patterns=5,
            domains={"example.com", "sub.example.com"},
            elapsed=2.5
        )

        assert "50 URLs" in notes
        assert "2.50s" in notes
        assert "5 patterns" in notes
        assert "example.com" in notes
