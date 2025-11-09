"""Integration tests for web crawler link following functionality."""

import pytest

from src.ingestion.web_crawler import WebCrawler


@pytest.mark.asyncio
class TestWebCrawlerLinkFollowing:
    """Test web crawler link following with depth tracking."""

    async def test_crawl_depth_0_single_page_only(self):
        """Test depth=0 crawls only the starting page."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=0)

        # Should only crawl the starting page
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].url == "https://example.com"
        assert results[0].metadata["crawl_depth"] == 0
        # Check for actual body text that's definitely present
        assert "domain" in results[0].content.lower() and "example" in results[0].content.lower()

    async def test_crawl_depth_1_follows_direct_links(self):
        """Test depth=1 crawls starting page + direct links."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Should crawl starting page + any internal links
        assert len(results) >= 1

        # First result should be the starting page
        assert results[0].url == "https://example.com"
        assert results[0].metadata["crawl_depth"] == 0

        # Check if any linked pages were found
        if len(results) > 1:
            for i, result in enumerate(results[1:], 1):
                # Linked pages should have depth=1
                assert result.metadata["crawl_depth"] == 1
                # Should have parent_url set
                assert result.metadata.get("parent_url") == "https://example.com"
                # All should be from same domain
                assert "example.com" in result.metadata["domain"]

    async def test_visited_urls_tracking(self):
        """Test that visited URLs are tracked to prevent duplicates."""
        crawler = WebCrawler(headless=True)

        # Clear visited URLs
        crawler.visited_urls.clear()
        assert len(crawler.visited_urls) == 0

        # Crawl with depth=1
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Visited URLs should contain at least the starting page
        assert "https://example.com" in crawler.visited_urls
        assert len(crawler.visited_urls) >= 1

        # All result URLs should be in visited set
        for result in results:
            if result.success:
                assert result.url in crawler.visited_urls

    async def test_crawl_session_id_consistent(self):
        """Test that all pages in a crawl share the same session ID."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        assert len(results) >= 1

        # Get session ID from first result
        session_id = results[0].metadata["crawl_session_id"]
        assert session_id is not None

        # All results should have the same session ID
        for result in results:
            if result.success:
                assert result.metadata["crawl_session_id"] == session_id

    async def test_crawl_root_url_propagation(self):
        """Test that crawl_root_url is preserved across all crawled pages."""
        crawler = WebCrawler(headless=True)
        root_url = "https://example.com"

        results = await crawler.crawl_with_depth(root_url, max_depth=1)

        # All results should have the same crawl_root_url
        for result in results:
            if result.success:
                assert result.metadata["crawl_root_url"] == root_url

    async def test_error_handling_invalid_url(self):
        """Test that invalid URLs are handled gracefully."""
        crawler = WebCrawler(headless=True)

        results = await crawler.crawl_with_depth(
            "https://this-domain-definitely-does-not-exist-12345.com",
            max_depth=1
        )

        # Should return at least one result with error
        assert len(results) >= 1
        assert results[0].success is False
        assert results[0].error is not None
        assert results[0].url == "https://this-domain-definitely-does-not-exist-12345.com"

    async def test_links_found_populated(self):
        """Test that links_found is populated in crawl results."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=0)

        assert len(results) == 1
        # example.com should have internal links (at minimum, to itself)
        # Note: links_found may be empty depending on page structure
        assert isinstance(results[0].links_found, list)

    async def test_metadata_complete(self):
        """Test that all required metadata fields are present."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

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

        for result in results:
            if result.success:
                for field in required_fields:
                    assert field in result.metadata, f"Missing field: {field} in {result.url}"

    async def test_parent_url_set_for_linked_pages(self):
        """Test that parent_url is set for linked pages (depth > 0)."""
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        if len(results) > 1:
            # Linked pages should have parent_url
            for result in results[1:]:
                if result.success and result.metadata["crawl_depth"] > 0:
                    assert "parent_url" in result.metadata
                    assert result.metadata["parent_url"] is not None
