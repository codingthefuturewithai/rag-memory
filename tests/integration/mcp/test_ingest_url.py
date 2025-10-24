"""MCP ingest_url tool integration tests.

Tests that ingest_url() correctly crawls web pages and stores them in databases.
"""

import json
import pytest
from .conftest import extract_text_content, extract_result_data

pytestmark = pytest.mark.anyio


class TestIngestUrl:
    """Test ingest_url tool functionality via MCP."""

    async def test_ingest_url_single_page(self, mcp_session, setup_test_collection):
        """Test ingesting a single web page without following links.

        Verifies that:
        1. Single page can be crawled
        2. Data is stored in source_documents and document_chunks
        3. Response includes document metadata
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Ingest a single page
        result = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl",
            "include_document_ids": True
        })

        # Verify no error
        assert not result.isError, f"ingest_url failed: {result}"

        response_text = extract_text_content(result)
        assert response_text is not None, "Response should have text content"

        response = json.loads(response_text)

        # Verify response structure
        assert isinstance(response, dict), "Response should be a dict"
        assert "mode" in response, "Response should include mode"
        assert response["mode"] in ("crawl", "recrawl"), "Mode should be crawl or recrawl"
        assert "pages_crawled" in response, "Should report pages_crawled"
        assert response["pages_crawled"] >= 1, "Should crawl at least one page"
        assert "pages_ingested" in response, "Should report pages_ingested"
        assert response["pages_ingested"] >= 1, "Should ingest at least one page"
        assert "total_chunks" in response, "Should report total_chunks"
        assert response["total_chunks"] >= 1, "Should create at least one chunk"
        assert "collection_name" in response, "Should echo collection_name"
        assert response["collection_name"] == collection_name
        assert "crawl_metadata" in response, "Should include crawl_metadata"
        assert "crawl_root_url" in response["crawl_metadata"], "Metadata should have crawl_root_url"

    async def test_ingest_url_has_document_ids(self, mcp_session, setup_test_collection):
        """Test that ingest_url returns document IDs when requested.

        This verifies that the tool returns the created document IDs in the response.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Ingest a page with include_document_ids=True
        result = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl",
            "include_document_ids": True
        })

        assert not result.isError, "ingest_url should succeed"

        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # Verify document_ids field exists and has data
        assert "document_ids" in response, "Response should include document_ids when requested"
        assert isinstance(response["document_ids"], list), "document_ids should be a list"
        assert len(response["document_ids"]) >= 1, "Should have at least 1 document_id"

        # Verify all IDs are integers
        for doc_id in response["document_ids"]:
            assert isinstance(doc_id, int), f"Document ID should be integer, got {type(doc_id)}"
            assert doc_id > 0, f"Document ID should be positive, got {doc_id}"

    async def test_ingest_url_invalid_collection(self, mcp_session):
        """Test ingest_url fails gracefully with non-existent collection.

        Verifies proper error handling.
        """
        session, transport = mcp_session

        result = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": "nonexistent-collection-xyz",
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl"
        })

        # Should have error
        assert result.isError, "Should fail with non-existent collection"

        # Extract error message
        error_text = extract_text_content(result)
        assert error_text is not None
        assert "does not exist" in error_text or "Collection" in error_text, \
            f"Error should mention missing collection: {error_text}"

    async def test_ingest_url_duplicate_crawl_error(self, mcp_session, setup_test_collection):
        """Test ingest_url prevents duplicate crawls of same URL in same collection.

        Verifies that crawling the same URL twice with mode='crawl' fails on second attempt.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # First crawl should succeed
        result1 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl"
        })

        assert not result1.isError, "First crawl should succeed"

        # Second crawl with mode='crawl' should fail
        result2 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl"
        })

        assert result2.isError, "Second crawl with mode='crawl' should fail (already exists)"

        error_text = extract_text_content(result2)
        assert "already been crawled" in error_text or "already exists" in error_text.lower(), \
            f"Error should mention duplicate crawl: {error_text}"

    async def test_ingest_url_recrawl_mode(self, mcp_session, setup_test_collection):
        """Test ingest_url with mode='recrawl' updates existing crawl.

        Verifies that recrawl mode succeeds and returns updated data.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # First crawl
        result1 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl"
        })

        assert not result1.isError, "First crawl should succeed"

        response1 = json.loads(extract_text_content(result1))
        first_chunk_count = response1.get("total_chunks", 0)
        assert first_chunk_count >= 1, "First crawl should create chunks"

        # Recrawl with mode='recrawl' should succeed
        result2 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "recrawl"
        })

        assert not result2.isError, "Recrawl with mode='recrawl' should succeed"

        response2 = json.loads(extract_text_content(result2))

        # Verify recrawl response structure
        assert response2["mode"] == "recrawl", "Response mode should be 'recrawl'"
        assert response2.get("total_chunks", 0) >= 1, "Recrawl should create chunks"
        assert response2["collection_name"] == collection_name, "Should maintain collection name"

        # Recrawl should indicate pages were handled
        assert "pages_crawled" in response2, "Recrawl response should include pages_crawled"
        assert response2["pages_crawled"] >= 1, "Recrawl should indicate pages were processed"

    async def test_ingest_url_response_structure(self, mcp_session, setup_test_collection):
        """Test that ingest_url returns properly structured response.

        Verifies all required fields in the response.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        result = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "crawl"
        })

        assert not result.isError, "ingest_url should succeed"

        response_text = extract_text_content(result)
        response = json.loads(response_text)

        # Verify required fields
        required_fields = ["mode", "pages_crawled", "pages_ingested", "total_chunks", "collection_name", "crawl_metadata"]
        for field in required_fields:
            assert field in response, f"Response missing required field: {field}"

        # Verify field types
        assert isinstance(response["mode"], str), "mode should be string"
        assert isinstance(response["collection_name"], str), "collection_name should be string"
        assert isinstance(response["pages_crawled"], int), "pages_crawled should be integer"
        assert isinstance(response["pages_ingested"], int), "pages_ingested should be integer"
        assert isinstance(response["total_chunks"], int), "total_chunks should be integer"
        assert isinstance(response["crawl_metadata"], dict), "crawl_metadata should be dict"

        # Verify values are reasonable
        assert response["pages_crawled"] >= 1, "Should crawl at least 1 page"
        assert response["pages_ingested"] >= 1, "Should ingest at least 1 page"
        assert response["total_chunks"] >= 1, "Should create at least 1 chunk"

        # Verify crawl_metadata has required fields
        assert "crawl_root_url" in response["crawl_metadata"]
        assert "crawl_session_id" in response["crawl_metadata"]
        assert "crawl_timestamp" in response["crawl_metadata"]
