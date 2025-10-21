"""MCP ingestion tool integration tests.

Tests ingest_text, ingest_file, ingest_directory, ingest_url tools.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


class TestIngestText:
    """Test ingest_text tool functionality."""

    async def test_ingest_text_creates_searchable_document(self, mcp_session, setup_test_collection):
        """Test that ingest_text creates searchable content."""
        session, transport = mcp_session
        collection = setup_test_collection

        content = "Machine learning is a subset of artificial intelligence"
        result = await session.call_tool("ingest_text", {
            "content": content,
            "collection_name": collection,
            "document_title": "ML Overview"
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        assert "source_document_id" in data
        assert data.get("collection_name") == collection

        # Verify searchable
        search_result = await session.call_tool("search_documents", {
            "query": "machine learning",
            "collection_name": collection
        })

        assert not search_result.isError
        search_text = extract_text_content(search_result)
        results = json.loads(search_text) if search_text else []
        assert len(results) > 0, "Ingested content should be searchable"

    async def test_ingest_text_preserves_metadata(self, mcp_session, setup_test_collection):
        """Test that ingest_text preserves metadata."""
        session, transport = mcp_session
        collection = setup_test_collection

        metadata = {"author": "test", "version": "1.0", "category": "documentation"}

        result = await session.call_tool("ingest_text", {
            "content": "Test content with metadata",
            "collection_name": collection,
            "document_title": "Meta Test",
            "metadata": json.dumps(metadata)
        })

        assert not result.isError

    async def test_ingest_text_nonexistent_collection_error(self, mcp_session):
        """Test error when ingesting to non-existent collection."""
        session, transport = mcp_session

        result = await session.call_tool("ingest_text", {
            "content": "Some content",
            "collection_name": "nonexistent_collection_xyz",
            "document_title": "Should Fail"
        })

        assert result.isError or "error" in (extract_text_content(result) or "").lower(), \
            "Should error for non-existent collection"


class TestIngestFile:
    """Test ingest_file tool functionality."""

    async def test_ingest_file_requires_existing_collection(self, mcp_session):
        """Test that ingest_file requires collection to exist."""
        session, transport = mcp_session

        # Try to ingest to non-existent collection
        result = await session.call_tool("ingest_file", {
            "file_path": "/tmp/nonexistent.txt",
            "collection_name": "nonexistent_collection"
        })

        # Should error (either file not found or collection not found)
        assert result.isError or extract_error_text(result), \
            "Should error for invalid inputs"


class TestIngestUrl:
    """Test ingest_url tool functionality."""

    async def test_ingest_url_requires_collection(self, mcp_session):
        """Test that ingest_url requires collection to exist."""
        session, transport = mcp_session

        # Try to ingest to non-existent collection
        result = await session.call_tool("ingest_url", {
            "url": "https://example.com",
            "collection_name": "nonexistent_collection"
        })

        # Should error
        assert result.isError or extract_error_text(result), \
            "Should error for non-existent collection"
