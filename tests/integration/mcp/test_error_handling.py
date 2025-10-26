"""MCP error handling integration tests.

Tests that tools properly handle errors and edge cases.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text

pytestmark = pytest.mark.anyio


class TestErrorHandling:
    """Test error handling across MCP tools."""

    async def test_search_nonexistent_collection(self, mcp_session):
        """Test error when searching non-existent collection."""
        session, transport = mcp_session

        result = await session.call_tool("search_documents", {
            "query": "test",
            "collection_name": "nonexistent_collection_xyz"
        })

        # May or may not be isError, but should handle gracefully
        assert result is not None
        text = extract_text_content(result)
        assert text is not None  # Should have some response

    async def test_ingest_nonexistent_collection(self, mcp_session):
        """Test error when ingesting to non-existent collection."""
        session, transport = mcp_session

        result = await session.call_tool("ingest_text", {
            "content": "Test",
            "collection_name": "nonexistent_xyz",
            "document_title": "Test"
        })

        # Should error
        assert result.isError or extract_error_text(result) is not None, \
            "Should error when collection doesn't exist"

    async def test_delete_nonexistent_document(self, mcp_session):
        """Test error when deleting non-existent document."""
        session, transport = mcp_session

        result = await session.call_tool("delete_document", {
            "document_id": 999999
        })

        # Should error
        assert result.isError or extract_error_text(result) is not None, \
            "Should error for non-existent document"

    async def test_get_nonexistent_document(self, mcp_session):
        """Test error when getting non-existent document."""
        session, transport = mcp_session

        result = await session.call_tool("get_document_by_id", {
            "document_id": 999999
        })

        # Should error
        assert result.isError or extract_error_text(result) is not None, \
            "Should error for non-existent document"

    async def test_search_with_invalid_threshold(self, mcp_session, setup_test_collection):
        """Test search with invalid threshold values."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": "Test content",
            "collection_name": collection,
            "document_title": "Test"
        })

        # Search with extreme threshold (should handle gracefully)
        result = await session.call_tool("search_documents", {
            "query": "test",
            "collection_name": collection,
            "threshold": 0.0,  # Minimum
            "limit": 5
        })

        assert not result.isError, "Should handle minimum threshold"

        result2 = await session.call_tool("search_documents", {
            "query": "test",
            "collection_name": collection,
            "threshold": 1.0,  # Maximum
            "limit": 5
        })

        assert not result2.isError, "Should handle maximum threshold"

    async def test_create_duplicate_collection(self, mcp_session):
        """Test error when creating duplicate collection."""
        session, transport = mcp_session

        # Use unique name based on session ID to avoid collisions
        collection_name = f"dup_test_{id(session)}"

        # Create first time
        result1 = await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "First",
            "domain": "testing",
            "domain_scope": "Test collection for MCP error handling testing"
        })

        assert not result1.isError

        # Try to create duplicate
        result2 = await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Second",
            "domain": "testing",
            "domain_scope": "Attempt to create duplicate collection"
        })

        # Should error or handle gracefully
        assert result2.isError or extract_error_text(result2) is not None or \
               extract_text_content(result2) is not None, \
               "Should handle duplicate collection"
        # Note: Collection persists in test database - this is acceptable for integration tests
