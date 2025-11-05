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
            "mode": "ingest",
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
        assert response["mode"] in ("ingest", "reingest"), "Mode should be ingest or reingest"
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
            "mode": "ingest",
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
            "mode": "ingest"
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
            "mode": "ingest"
        })

        assert not result1.isError, "First crawl should succeed"

        # Second crawl with mode='ingest' should fail
        result2 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "ingest"
        })

        assert result2.isError, "Second crawl with mode='ingest' should fail (already exists)"

        error_text = extract_text_content(result2)
        assert "already been ingested" in error_text.lower() or "already exists" in error_text.lower(), \
            f"Error should mention duplicate crawl: {error_text}"

    async def test_ingest_url_recrawl_mode(self, mcp_session, setup_test_collection):
        """Test ingest_url with mode='reingest' updates existing crawl.

        Verifies that reingest mode succeeds and returns updated data.
        Also verifies that old documents are completely deleted and new documents exist.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # First crawl
        result1 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "ingest",
            "include_document_ids": True  # NEW: Request document IDs
        })

        assert not result1.isError, "First crawl should succeed"

        response1 = json.loads(extract_text_content(result1))
        first_chunk_count = response1.get("total_chunks", 0)
        first_doc_ids = response1.get("document_ids", [])  # NEW: Capture old doc IDs
        assert first_chunk_count >= 1, "First crawl should create chunks"
        assert len(first_doc_ids) >= 1, "First crawl should return document IDs"

        # Reingest with mode='reingest' should succeed
        result2 = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": collection_name,
            "follow_links": False,
            "max_depth": 1,
            "mode": "reingest",
            "include_document_ids": True  # NEW: Request document IDs
        })

        assert not result2.isError, "Reingest with mode='reingest' should succeed"

        response2 = json.loads(extract_text_content(result2))
        second_doc_ids = response2.get("document_ids", [])  # NEW: Capture new doc IDs

        # Verify reingest response structure
        assert response2["mode"] == "reingest", "Response mode should be 'reingest'"
        assert response2.get("total_chunks", 0) >= 1, "Reingest should create chunks"
        assert response2["collection_name"] == collection_name, "Should maintain collection name"

        # Reingest should indicate pages were handled
        assert "pages_crawled" in response2, "Reingest response should include pages_crawled"
        assert response2["pages_crawled"] >= 1, "Reingest should indicate pages were processed"

        # NEW: Verify old documents are completely deleted
        for old_doc_id in first_doc_ids:
            verify_result = await session.call_tool("get_document_by_id", {
                "document_id": old_doc_id
            })
            assert verify_result.isError, \
                f"Old document {old_doc_id} should be deleted after reingest"

        # NEW: Verify new documents exist
        assert len(second_doc_ids) >= 1, "Reingest should return new document IDs"
        for new_doc_id in second_doc_ids:
            verify_result = await session.call_tool("get_document_by_id", {
                "document_id": new_doc_id
            })
            assert not verify_result.isError, \
                f"New document {new_doc_id} should exist after reingest"

        # NEW: Verify no overlap between old and new document IDs
        assert not any(doc_id in second_doc_ids for doc_id in first_doc_ids), \
            "Old and new document IDs should not overlap (reingest should create new documents)"

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
            "mode": "ingest"
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

    async def test_ingest_url_with_follow_links(self, mcp_session, setup_test_collection):
        """Test ingest_url with follow_links=True to crawl multiple pages.

        This is the critical test that verifies the max_pages parameter fix works.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Ingest with follow_links=True and max_pages=5
        # analyze_website is optional for decision-making, not required
        result = await session.call_tool("ingest_url", {
            "url": "https://python.org/about",
            "collection_name": collection_name,
            "follow_links": True,
            "max_pages": 5,
            "mode": "ingest",
            "include_document_ids": True
        })

        # Verify no error
        assert not result.isError, f"ingest_url with follow_links failed: {result}"

        response_text = extract_text_content(result)
        assert response_text is not None, "Response should have text content"

        response = json.loads(response_text)

        # Verify we crawled multiple pages
        assert response["pages_crawled"] >= 2, f"Should crawl at least 2 pages with follow_links, got {response['pages_crawled']}"
        assert response["pages_crawled"] <= 5, f"Should not exceed max_pages=5, got {response['pages_crawled']}"

        # Verify we ingested successfully
        assert response["pages_ingested"] >= 2, f"Should ingest at least 2 pages, got {response['pages_ingested']}"
        assert response["total_chunks"] >= 2, f"Should create at least 2 chunks, got {response['total_chunks']}"

        # Verify document_ids are returned
        assert "document_ids" in response, "Should include document_ids"
        assert len(response["document_ids"]) >= 2, f"Should have at least 2 document IDs, got {len(response['document_ids'])}"

        print(f"\n✅ SUCCESS: Crawled {response['pages_crawled']} pages with follow_links=True")
