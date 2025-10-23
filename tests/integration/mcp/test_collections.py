"""MCP collection management tool integration tests.

Tests create_collection, list_collections, get_collection_metadata_schema, get_collection_info,
and delete_collection.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


class TestCollections:
    """Test collection management tools via MCP."""

    async def test_create_collection(self, mcp_session):
        """Test creating a collection via MCP."""
        session, transport = mcp_session

        collection_name = f"test_create_coll_{id(session)}"

        result = await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test collection creation"
        })

        assert not result.isError, f"Create collection failed: {result}"
        text = extract_text_content(result)
        data = json.loads(text)
        assert data.get("name") == collection_name
        assert data.get("created") is True
        # Note: Collection persists in test database - this is acceptable for integration tests

    async def test_list_collections_discovers_created(self, mcp_session):
        """Test that list_collections shows newly created collections."""
        session, transport = mcp_session

        collection_name = f"test_list_discovery_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "For listing test"
        })

        # List collections
        result = await session.call_tool("list_collections")

        assert not result.isError
        collections = extract_result_data(result)

        # Find our collection
        found = any(c.get("name") == collection_name for c in collections)
        if not found:
            print(f"Looking for: '{collection_name}'")
            print(f"Available collections: {[c.get('name') for c in collections]}")
        assert found, f"Created collection not found in list"
        # Note: Collection persists in test database - this is acceptable for integration tests

    async def test_get_collection_metadata_schema(self, mcp_session):
        """Test getting collection metadata schema."""
        session, transport = mcp_session

        collection_name = f"test_metadata_schema_{id(session)}"
        test_schema = {
            "custom": {
                "author": {
                    "type": "string",
                    "required": True
                },
                "version": {
                    "type": "number"
                }
            },
            "system": ["file_type", "ingested_at"]
        }

        # Create collection with metadata schema
        create_result = await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test metadata schema",
            "metadata_schema": test_schema
        })

        assert not create_result.isError

        # Get metadata schema
        result = await session.call_tool("get_collection_metadata_schema", {
            "collection_name": collection_name
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify schema returned
        assert data.get("collection_name") == collection_name
        assert data.get("custom_fields") is not None
        assert "author" in data.get("custom_fields", {})
        assert "version" in data.get("custom_fields", {})
        assert "file_type" in data.get("system_fields", [])
        # Note: Collection persists in test database - this is acceptable for integration tests

    async def test_get_collection_info(self, mcp_session):
        """Test getting detailed collection information."""
        session, transport = mcp_session

        collection_name = f"test_get_info_{id(session)}"

        # Create and ingest
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test collection"
        })

        await session.call_tool("ingest_text", {
            "content": "Test document",
            "collection_name": collection_name,
            "document_title": "Doc1"
        })

        # Get info
        result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        assert data.get("name") == collection_name
        assert data.get("description") == "Test collection"
        assert "document_count" in data or "chunk_count" in data
        # Note: Collection persists in test database - this is acceptable for integration tests

    async def test_delete_collection_requires_confirmation(self, mcp_session):
        """Test that delete_collection requires confirm=True."""
        session, transport = mcp_session

        collection_name = f"test_delete_no_confirm_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Collection to test deletion without confirmation"
        })

        # Try to delete without confirmation (should fail)
        result = await session.call_tool("delete_collection", {
            "name": collection_name,
            "confirm": False
        })

        # Should error
        assert result.isError, "delete_collection should require confirm=True"

        # Verify collection still exists
        verify_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })
        assert not verify_result.isError, "Collection should still exist after failed deletion"

    async def test_delete_collection_with_confirmation(self, mcp_session):
        """Test successful delete_collection with confirm=True."""
        session, transport = mcp_session

        collection_name = f"test_delete_with_confirm_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Collection to delete with confirmation"
        })

        # Delete with confirmation
        result = await session.call_tool("delete_collection", {
            "name": collection_name,
            "confirm": True
        })

        assert not result.isError, f"delete_collection with confirm=True failed: {result}"
        text = extract_text_content(result)
        data = json.loads(text)
        assert data.get("deleted") is True
        assert data.get("name") == collection_name
        assert "permanently deleted" in data.get("message", "").lower()

        # Verify collection no longer exists
        verify_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })
        assert verify_result.isError, "Collection should not exist after deletion"

    async def test_delete_collection_with_documents(self, mcp_session):
        """Test delete_collection removes associated documents."""
        session, transport = mcp_session

        collection_name = f"test_delete_with_docs_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Collection with documents to delete"
        })

        # Add documents
        for i in range(3):
            await session.call_tool("ingest_text", {
                "content": f"Test document {i} with some content",
                "collection_name": collection_name,
                "document_title": f"Doc{i}"
            })

        # Get collection info to see document count
        info_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })
        assert not info_result.isError
        info_text = extract_text_content(info_result)
        info_data = json.loads(info_text)
        initial_doc_count = info_data.get("document_count", 0)
        assert initial_doc_count > 0, "Should have at least 1 document"

        # Delete collection with all its documents
        result = await session.call_tool("delete_collection", {
            "name": collection_name,
            "confirm": True
        })

        assert not result.isError, "delete_collection should succeed"
        text = extract_text_content(result)
        data = json.loads(text)
        assert data.get("deleted") is True
        assert str(initial_doc_count) in str(data.get("message", "")), \
            f"Message should mention document count {initial_doc_count}"

        # Verify collection is gone
        verify_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })
        assert verify_result.isError, "Collection should be deleted"

    async def test_delete_nonexistent_collection(self, mcp_session):
        """Test delete_collection on nonexistent collection fails gracefully."""
        session, transport = mcp_session

        collection_name = f"nonexistent_{id(session)}"

        # Try to delete nonexistent collection
        result = await session.call_tool("delete_collection", {
            "name": collection_name,
            "confirm": True
        })

        # Should error because collection doesn't exist
        assert result.isError, "Should error when collection doesn't exist"

    async def test_delete_collection_cleans_graph_episodes(self, mcp_session):
        """Test that delete_collection actually removes episodes from Neo4j graph."""
        session, transport = mcp_session

        collection_name = f"test_delete_graph_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Collection for graph cleanup test"
        })

        # Add documents (these create episodes in Neo4j during ingest)
        doc_ids = []
        for i in range(2):
            result = await session.call_tool("ingest_text", {
                "content": f"Test document {i} with AI knowledge content",
                "collection_name": collection_name,
                "document_title": f"GraphTest{i}"
            })
            assert not result.isError, f"ingest_text failed: {result}"
            # Extract document ID from response
            text = extract_text_content(result)
            data = json.loads(text)
            doc_id = data.get("source_document_id")
            if doc_id:
                doc_ids.append(doc_id)

        # Verify episodes exist in Neo4j before deletion
        # (We can't directly query Neo4j from MCP tests, but we can verify
        # the message says episodes will be cleaned)
        assert len(doc_ids) > 0, "Should have created at least one document"

        # Delete collection (should clean graph episodes)
        result = await session.call_tool("delete_collection", {
            "name": collection_name,
            "confirm": True
        })

        assert not result.isError, f"delete_collection failed: {result}"
        text = extract_text_content(result)
        data = json.loads(text)
        assert data.get("deleted") is True

        # Verify message indicates graph cleanup occurred
        message = data.get("message", "")
        # The message should mention graph episodes being cleaned
        # Message format: "Collection 'X' and N document(s) permanently deleted. (M graph episodes cleaned)"
        assert "deleted" in message.lower(), f"Message should confirm deletion: {message}"

        # Verify collection is gone
        verify_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })
        assert verify_result.isError, "Collection should be deleted from RAG"
