"""MCP analyze_website tool integration tests.

Tests that analyze_website() correctly parses websites and extracts URL patterns.
"""

import json
import pytest
from .conftest import extract_text_content, extract_result_data

pytestmark = pytest.mark.anyio


class TestAnalyzeWebsite:
    """Test analyze_website tool functionality via MCP."""

    async def test_analyze_website_with_valid_url(self, mcp_session):
        """Test analyze_website with a real website that has sitemap.

        Verifies that:
        1. Tool returns without error
        2. Response contains all required fields
        3. Base URL is echoed correctly
        """
        session, transport = mcp_session

        # Analyze a real website known to have sitemap
        result = await session.call_tool("analyze_website", {
            "base_url": "https://codingthefuture.ai",
            "timeout": 15,
            "include_url_lists": False,
            "max_urls_per_pattern": 10
        })

        # Verify no error
        assert not result.isError, f"analyze_website failed: {result}"

        # Extract response data
        response_text = extract_text_content(result)
        assert response_text is not None, "Response should have text content"

        response = json.loads(response_text)

        # Verify core response structure (always present)
        assert isinstance(response, dict), "Response should be a dict"
        assert "base_url" in response, "Response should echo base_url"
        assert response["base_url"] == "https://codingthefuture.ai", "Should match input URL"
        assert "analysis_method" in response, "Should include analysis_method"
        assert response["analysis_method"] in ("sitemap", "not_found", "error"), \
            "analysis_method should be sitemap/not_found/error"
        assert "total_urls" in response, "Should include total_urls count"
        assert "pattern_stats" in response, "Should include pattern_stats"
        assert "notes" in response, "Should include notes explaining data"
        assert isinstance(response["total_urls"], int), "total_urls should be integer"
        assert response["total_urls"] >= 0, "total_urls should be non-negative"

    async def test_analyze_website_response_structure(self, mcp_session):
        """Test that analyze_website returns properly structured response.

        Verifies all required fields and their types.
        """
        session, transport = mcp_session

        result = await session.call_tool("analyze_website", {
            "base_url": "https://codingthefuture.ai",
            "timeout": 15,
            "include_url_lists": False,
            "max_urls_per_pattern": 5
        })

        assert not result.isError, f"Tool failed: {result}"

        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # Verify all required fields exist
        required_fields = ["base_url", "analysis_method", "total_urls", "pattern_stats", "notes"]
        for field in required_fields:
            assert field in response, f"Response missing required field: {field}"

        # Verify field types
        assert isinstance(response["base_url"], str), "base_url should be string"
        assert isinstance(response["analysis_method"], str), "analysis_method should be string"
        assert isinstance(response["total_urls"], int), "total_urls should be integer"
        assert isinstance(response["pattern_stats"], dict), "pattern_stats should be dict"
        assert isinstance(response["notes"], str), "notes should be string"

        # Verify pattern_stats structure when non-empty
        for pattern, stats in response["pattern_stats"].items():
            assert isinstance(stats, dict), f"Pattern {pattern} stats should be dict"
            assert "count" in stats, f"Pattern {pattern} should have count"
            assert "avg_depth" in stats, f"Pattern {pattern} should have avg_depth"
            assert "example_urls" in stats, f"Pattern {pattern} should have example_urls"

    async def test_analyze_website_with_include_url_lists(self, mcp_session):
        """Test analyze_website with include_url_lists enabled.

        Verifies that when include_url_lists=True and sitemap found, url_groups field is included.
        When no sitemap is found, url_groups is NOT included (only present when sitemap succeeds).
        """
        session, transport = mcp_session

        result = await session.call_tool("analyze_website", {
            "base_url": "https://codingthefuture.ai",
            "timeout": 15,
            "include_url_lists": True,
            "max_urls_per_pattern": 5
        })

        assert not result.isError
        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # If sitemap was found, url_groups field should be present
        if response["analysis_method"] == "sitemap" and response["total_urls"] > 0:
            assert "url_groups" in response, \
                "url_groups field should be present when sitemap found and include_url_lists=True"

            # url_groups should be dict mapping patterns to URL lists
            assert isinstance(response["url_groups"], dict), \
                "url_groups should be dict"
            for pattern, urls in response["url_groups"].items():
                assert isinstance(urls, list), \
                    f"url_groups[{pattern}] should be list of URLs"
                assert len(urls) > 0, f"url_groups[{pattern}] should have at least one URL"
        else:
            # If sitemap was not found, url_groups won't be present
            # This is correct behavior - we only include url_groups when we have data
            assert response["total_urls"] == 0 or response["analysis_method"] != "sitemap"

    async def test_analyze_website_without_url_lists(self, mcp_session):
        """Test analyze_website with include_url_lists disabled.

        Verifies that url_groups is NOT included when include_url_lists=False.
        """
        session, transport = mcp_session

        result = await session.call_tool("analyze_website", {
            "base_url": "https://codingthefuture.ai",
            "timeout": 15,
            "include_url_lists": False,
            "max_urls_per_pattern": 5
        })

        assert not result.isError
        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # pattern_stats should always be present (lightweight summary)
        assert "pattern_stats" in response, "pattern_stats should always be present"
        assert isinstance(response["pattern_stats"], dict), "pattern_stats should be dict"

        # But url_groups should NOT be included when include_url_lists=False
        assert "url_groups" not in response, \
            "url_groups should not be present when include_url_lists=False"

    async def test_analyze_website_no_sitemap_handling(self, mcp_session):
        """Test analyze_website handles websites without sitemap gracefully.

        Tests behavior when sitemap cannot be found (like invalid domains).
        """
        session, transport = mcp_session

        result = await session.call_tool("analyze_website", {
            "base_url": "https://invalid-site-that-does-not-exist-12345.com",
            "timeout": 5,
            "include_url_lists": False,
            "max_urls_per_pattern": 5
        })

        assert not result.isError, "Should return error response gracefully"
        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # Should still have base structure even on failure
        assert response["base_url"] == "https://invalid-site-that-does-not-exist-12345.com"
        assert response["analysis_method"] in ("not_found", "error")
        assert response["total_urls"] == 0, "Should have 0 URLs when sitemap not found"
        assert isinstance(response["notes"], str), "Should provide explanation in notes"
        # Notes should explain why no data was found
        assert "sitemap" in response["notes"].lower(), \
            "Notes should mention sitemap when it's not found"
