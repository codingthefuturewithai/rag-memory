"""MCP document CRUD tool integration tests.

Tests list_documents, get_document_by_id, update_document, delete_document.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


class TestListDocuments:
    """Test list_documents tool."""

    async def test_list_documents_shows_ingested(self, mcp_session, setup_test_collection):
        """Test that list_documents shows ingested documents."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest multiple documents
        for i in range(3):
            await session.call_tool("ingest_text", {
                "content": f"Document {i} content",
                "collection_name": collection,
                "document_title": f"Doc {i}"
            })

        # List documents
        result = await session.call_tool("list_documents", {
            "collection_name": collection
        })

        assert not result.isError
        data = extract_result_data(result) or {}
        documents = data.get("documents", [])
        assert len(documents) >= 3, "Should list all ingested documents"

    async def test_list_documents_pagination(self, mcp_session, setup_test_collection):
        """Test that list_documents supports pagination."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest multiple documents
        for i in range(5):
            await session.call_tool("ingest_text", {
                "content": f"Content {i}",
                "collection_name": collection,
                "document_title": f"Doc {i}"
            })

        # List with limit
        result = await session.call_tool("list_documents", {
            "collection_name": collection,
            "limit": 2
        })

        assert not result.isError
        data = extract_result_data(result) or {}
        documents = data.get("documents", [])
        returned_count = data.get("returned_count", len(documents))
        assert returned_count <= 2, "Should respect limit"


class TestGetDocument:
    """Test get_document_by_id tool."""

    async def test_get_document_by_id_returns_content(self, mcp_session, setup_test_collection):
        """Test that get_document_by_id returns full document content."""
        session, transport = mcp_session
        collection = setup_test_collection

        content = "Complete document content for testing"

        # Ingest
        ingest_result = await session.call_tool("ingest_text", {
            "content": content,
            "collection_name": collection,
            "document_title": "Full Doc"
        })

        ingest_data = extract_result_data(ingest_result)
        doc_id = ingest_data["source_document_id"]

        # Get document
        result = await session.call_tool("get_document_by_id", {
            "document_id": doc_id
        })

        assert not result.isError
        data = extract_result_data(result) or {}

        assert "content" in data or "source_content" in data, "Should return document content"
        assert data.get("filename") == "Full Doc" or data.get("id") == doc_id

    async def test_get_document_nonexistent_error(self, mcp_session):
        """Test error when getting non-existent document."""
        session, transport = mcp_session

        result = await session.call_tool("get_document_by_id", {
            "document_id": 99999
        })

        assert result.isError or "error" in (extract_text_content(result) or "").lower(), \
            "Should error for non-existent document"


class TestUpdateDocument:
    """Test update_document tool."""

    async def test_update_document_content_affects_search(self, mcp_session, setup_test_collection):
        """Test that updating document content affects search results."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest
        ingest_result = await session.call_tool("ingest_text", {
            "content": "Original content about dogs",
            "collection_name": collection,
            "document_title": "Pet Doc"
        })

        ingest_data = extract_result_data(ingest_result)
        doc_id = ingest_data["source_document_id"]

        # Search for original (should find)
        search1 = await session.call_tool("search_documents", {
            "query": "dogs",
            "collection_name": collection
        })

        results1 = extract_result_data(search1) or []
        assert len(results1) > 0, "Should find original content"

        # Update content
        await session.call_tool("update_document", {
            "document_id": doc_id,
            "content": "New content about cats"
        })

        # Search for new content (should find)
        search2 = await session.call_tool("search_documents", {
            "query": "cats",
            "collection_name": collection
        })

        results2 = extract_result_data(search2) or []
        assert len(results2) > 0, "Should find updated content"

    async def test_update_document_metadata(self, mcp_session, setup_test_collection):
        """Test updating document metadata."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest with initial metadata
        ingest_result = await session.call_tool("ingest_text", {
            "content": "Test content",
            "collection_name": collection,
            "document_title": "Metadata Doc",
            "metadata": json.dumps({"version": "1.0"})
        })

        ingest_data = extract_result_data(ingest_result)
        doc_id = ingest_data["source_document_id"]

        # Update metadata
        result = await session.call_tool("update_document", {
            "document_id": doc_id,
            "metadata": json.dumps({"version": "2.0", "updated": True})
        })

        assert not result.isError


class TestDeleteDocument:
    """Test delete_document tool."""

    async def test_delete_document_removes_from_search(self, mcp_session, setup_test_collection):
        """Test that deleting a document removes it from search."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest
        ingest_result = await session.call_tool("ingest_text", {
            "content": "Content to be deleted",
            "collection_name": collection,
            "document_title": "Delete Me"
        })

        ingest_data = extract_result_data(ingest_result)
        doc_id = ingest_data["source_document_id"]

        # Verify searchable
        search1 = await session.call_tool("search_documents", {
            "query": "deleted",
            "collection_name": collection
        })

        results1 = extract_result_data(search1) or []
        assert len(results1) > 0, "Should find content before deletion"

        # Delete
        delete_result = await session.call_tool("delete_document", {
            "document_id": doc_id
        })

        assert not delete_result.isError

        # Verify no longer searchable
        search2 = await session.call_tool("search_documents", {
            "query": "deleted",
            "collection_name": collection
        })

        results2 = extract_result_data(search2) or []
        # Should not find deleted document
        for r in results2:
            assert r.get("source_document_id") != doc_id, "Deleted document should not appear in results"

    async def test_delete_nonexistent_error(self, mcp_session):
        """Test error when deleting non-existent document."""
        session, transport = mcp_session

        result = await session.call_tool("delete_document", {
            "document_id": 99999
        })

        assert result.isError or "error" in (extract_text_content(result) or "").lower(), \
            "Should error for non-existent document"
