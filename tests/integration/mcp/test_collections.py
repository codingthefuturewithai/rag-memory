"""MCP collection management tool integration tests.

Tests create_collection, list_collections, update_collection_description, get_collection_info.
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

    async def test_update_collection_description(self, mcp_session):
        """Test updating collection description."""
        session, transport = mcp_session

        collection_name = f"test_update_desc_{id(session)}"
        original_desc = "Original description"
        updated_desc = "Updated description"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": original_desc
        })

        # Update description
        result = await session.call_tool("update_collection_description", {
            "name": collection_name,
            "description": updated_desc
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)
        assert data.get("description") == updated_desc

        # Verify change persisted
        info_result = await session.call_tool("get_collection_info", {
            "collection_name": collection_name
        })

        assert not info_result.isError
        info_text = extract_text_content(info_result)
        info_data = json.loads(info_text)
        assert info_data.get("description") == updated_desc
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
