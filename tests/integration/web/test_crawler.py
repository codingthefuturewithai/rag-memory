"""Integration tests for web crawler functionality."""

import pytest

from src.ingestion.web_crawler import crawl_single_page


@pytest.mark.asyncio
class TestWebCrawler:
    """Test web crawler functionality."""

    async def test_crawl_single_page_success(self):
        """Test successful single-page crawl."""
        result = await crawl_single_page("https://example.com", headless=True)

        assert result.success is True
        assert result.error is None
        assert result.url == "https://example.com"
        assert len(result.content) > 0
        # Check for actual body text, not title (which may be filtered by crawler)
        assert "domain" in result.content.lower() and "example" in result.content.lower()

        # Check metadata
        assert result.metadata["source"] == "https://example.com"
        assert result.metadata["content_type"] == "web_page"
        assert result.metadata["crawl_root_url"] == "https://example.com"
        assert result.metadata["crawl_depth"] == 0
        assert result.metadata["domain"] == "example.com"
        assert result.metadata["status_code"] == 200
        assert "crawl_timestamp" in result.metadata
        assert "crawl_session_id" in result.metadata
        assert result.metadata["crawler_version"] == "crawl4ai-0.7.4"

    async def test_crawl_invalid_url(self):
        """Test crawling an invalid URL."""
        result = await crawl_single_page("https://this-domain-definitely-does-not-exist-12345.com")

        assert result.success is False
        assert result.error is not None
        assert result.error.url == "https://this-domain-definitely-does-not-exist-12345.com"
        assert len(result.content) == 0

    async def test_crawl_with_custom_root_url(self):
        """Test crawling with custom root URL for crawl tracking."""
        from src.ingestion.web_crawler import WebCrawler

        crawler = WebCrawler(headless=True)
        result = await crawler.crawl_page(
            url="https://example.com",
            crawl_root_url="https://docs.example.com"
        )

        assert result.success is True
        assert result.metadata["source"] == "https://example.com"
        assert result.metadata["crawl_root_url"] == "https://docs.example.com"

    async def test_metadata_structure(self):
        """Test that metadata contains all required fields."""
        result = await crawl_single_page("https://example.com")

        required_fields = [
            "source",
            "content_type",
            "crawl_root_url",
            "crawl_timestamp",
            "crawl_session_id",
            "crawl_depth",
            "title",
            "domain",
            "status_code",
            "content_length",
            "crawler_version",
        ]

        for field in required_fields:
            assert field in result.metadata, f"Missing required field: {field}"

    async def test_crawl_result_to_dict(self):
        """Test CrawlResult serialization."""
        result = await crawl_single_page("https://example.com")

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert "url" in result_dict
        assert "content" in result_dict
        assert "metadata" in result_dict
        assert "success" in result_dict
        assert result_dict["success"] is True
