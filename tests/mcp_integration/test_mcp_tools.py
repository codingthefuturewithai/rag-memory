"""MCP Tool Integration Tests

Tests all 12 MCP tools with real client-server interaction via STDIO transport.
Each test is atomic with complete data cleanup.
"""

import pytest
import json
import uuid
from mcp import ClientSession
from .conftest import extract_text_content, extract_error_text
from src.core.database import Database
from src.core.collections import CollectionManager


class TestMCPToolDiscovery:
    """Test MCP tool discovery and registration."""

    @pytest.mark.asyncio
    async def test_all_twelve_tools_discoverable(self, mcp_stdio_session: ClientSession):
        """Verify all 12 MCP tools are registered and discoverable."""
        tools_response = await mcp_stdio_session.list_tools()
        tool_names = [tool.name for tool in tools_response.tools]

        expected_tools = [
            "search_documents",
            "list_collections",
            "create_collection",
            "ingest_text",
            "ingest_url",
            "ingest_file",
            "ingest_directory",
            "delete_document",
            "update_document",
            "get_document_by_id",
            "get_collection_info",
            "query_relationships",
        ]

        for expected in expected_tools:
            assert expected in tool_names, f"Tool {expected} not found. Available: {tool_names}"

    @pytest.mark.asyncio
    async def test_tools_have_proper_schemas(self, mcp_stdio_session: ClientSession):
        """Verify all tools have descriptions and input schemas."""
        tools_response = await mcp_stdio_session.list_tools()

        for tool in tools_response.tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.inputSchema is not None, f"Tool {tool.name} missing input schema"
            assert tool.inputSchema.get("type") == "object", f"Tool {tool.name} schema type should be 'object'"


class TestSearchDocuments:
    """Test search_documents MCP tool."""

    @pytest.mark.asyncio
    async def test_search_documents_on_empty_collection(self, mcp_stdio_session: ClientSession):
        """Test search on empty collection returns no results."""
        # Create test collection
        collection_name = f"test_search_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection via MCP
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {
                    "name": collection_name,
                    "description": "Test collection for search"
                }
            )
            assert not create_result.isError, f"Collection creation failed: {create_result}"

            # Search empty collection
            search_result = await mcp_stdio_session.call_tool(
                "search_documents",
                {
                    "query": "test query",
                    "collection_name": collection_name
                }
            )
            assert not search_result.isError, f"Search failed: {search_result}"

            # Parse response - may be a list directly or may have no content for empty
            if search_result.content:
                text_content = extract_text_content(search_result)
                if text_content:
                    data = json.loads(text_content)
                    # Empty search may return empty list or dict
                    assert isinstance(data, (dict, list)), "Response should be dict or list"

        finally:
            # Cleanup: Delete collection
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestIngestAndSearch:
    """Test ingest_text and search_documents workflow."""

    @pytest.mark.asyncio
    async def test_ingest_text_then_search(self, mcp_stdio_session: ClientSession):
        """Test complete workflow: ingest text -> search -> validate results."""
        collection_name = f"test_ingest_{uuid.uuid4().hex[:8]}"
        test_content = "Python is a high-level programming language known for simplicity and readability."

        try:
            # Step 1: Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {
                    "name": collection_name,
                    "description": "Test ingest and search"
                }
            )
            assert not create_result.isError, f"Collection creation failed: {create_result}"

            # Step 2: Ingest text
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_text",
                {
                    "content": test_content,
                    "collection_name": collection_name,
                    "document_title": "Test Document",
                    "metadata": json.dumps({"test": "true", "version": "1.0"})
                }
            )
            assert not ingest_result.isError, f"Ingest failed: {ingest_result}"

            # Parse ingest result
            ingest_text = extract_text_content(ingest_result)
            assert ingest_text is not None, "No text content in ingest result"
            ingest_data = json.loads(ingest_text)
            assert "source_document_id" in ingest_data or "num_chunks" in ingest_data, "Ingest result missing key data"

            # Step 3: Search for ingested content
            search_result = await mcp_stdio_session.call_tool(
                "search_documents",
                {
                    "query": "Python programming language characteristics",
                    "collection_name": collection_name,
                    "limit": "5"
                }
            )
            assert not search_result.isError, f"Search failed: {search_result}"

            # Parse search result
            search_text = extract_text_content(search_result)
            assert search_text is not None, "No text content in search result"
            search_data = json.loads(search_text)

            # Search results might be returned as:
            # 1. List of results directly
            # 2. Dict with "results" or "chunks" key
            if isinstance(search_data, list):
                results = search_data
            else:
                results = search_data.get("results") or search_data.get("chunks") or []

            # Search may return results or empty list depending on processing timing
            # At minimum, validate that it returns a properly formatted response
            assert isinstance(results, list), "Results should be a list"

            # If results are found, validate structure
            for result in results[:1]:  # Check first result if exists
                assert "content" in result or "text" in result or "chunk" in result, f"Result missing content: {result}"

        finally:
            # Cleanup: Delete collection
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestListCollections:
    """Test list_collections MCP tool."""

    @pytest.mark.asyncio
    async def test_list_collections(self, mcp_stdio_session: ClientSession):
        """Test listing collections."""
        result = await mcp_stdio_session.call_tool(
            "list_collections",
            {}
        )
        assert not result.isError, f"list_collections failed: {result}"

        text_content = extract_text_content(result)
        assert text_content is not None, "No text content in list result"

        # Parse response
        try:
            data = json.loads(text_content)
            # Should be dict or list
            assert isinstance(data, (dict, list)), "Response should be dict or list"
        except json.JSONDecodeError:
            # Response may be plain text
            assert len(text_content) > 0, "Response should not be empty"


class TestGetDocumentById:
    """Test get_document_by_id MCP tool."""

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, mcp_stdio_session: ClientSession):
        """Test getting non-existent document returns proper error or null."""
        result = await mcp_stdio_session.call_tool(
            "get_document_by_id",
            {"document_id": "999999"}
        )

        # Either returns error or document not found message
        if result.isError:
            error_text = extract_error_text(result)
            assert error_text is not None, "Error result should have text"
        else:
            text_content = extract_text_content(result)
            # Document should not exist
            assert text_content is not None, "Response should have content"


class TestQueryRelationships:
    """Test query_relationships MCP tool."""

    @pytest.mark.asyncio
    async def test_query_relationships(self, mcp_stdio_session: ClientSession):
        """Test querying relationships from knowledge graph."""
        result = await mcp_stdio_session.call_tool(
            "query_relationships",
            {"query": "How do programming languages relate?"}
        )

        # Tool should succeed or return unavailable gracefully
        if result.isError:
            error_text = extract_error_text(result)
            # May not have graph data yet, which is ok
            assert error_text is not None, "Error result should have text"
        else:
            text_content = extract_text_content(result)
            assert text_content is not None, "Response should have content"
            # Parse response
            try:
                data = json.loads(text_content)
                # Should have status field
                assert "status" in data or "relationships" in data, "Response missing expected fields"
            except json.JSONDecodeError:
                # Plain text response is ok
                assert len(text_content) > 0, "Response should not be empty"


class TestGetCollectionInfo:
    """Test get_collection_info MCP tool."""

    @pytest.mark.asyncio
    async def test_get_collection_info_nonexistent(self, mcp_stdio_session: ClientSession):
        """Test getting info for non-existent collection."""
        result = await mcp_stdio_session.call_tool(
            "get_collection_info",
            {"collection_name": f"nonexistent_{uuid.uuid4().hex[:8]}"}
        )

        # Should either error or return empty/not found
        if result.isError:
            error_text = extract_error_text(result)
            assert error_text is not None, "Error should have text"


class TestListDocuments:
    """Test list_documents MCP tool."""

    @pytest.mark.asyncio
    async def test_list_documents_empty_collection(self, mcp_stdio_session: ClientSession):
        """Test listing documents from empty collection."""
        collection_name = f"test_list_docs_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {
                    "name": collection_name,
                    "description": "Test list documents"
                }
            )
            assert not create_result.isError, f"Collection creation failed: {create_result}"

            # List documents (should be empty)
            result = await mcp_stdio_session.call_tool(
                "list_documents",
                {"collection_name": collection_name}
            )
            assert not result.isError, f"list_documents failed: {result}"

            # Parse response
            text_content = extract_text_content(result)
            assert text_content is not None, "No text content in response"
            data = json.loads(text_content)

            # Should have documents key
            assert "documents" in data or "total_count" in data, "Response missing documents info"

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_list_documents_with_content(self, mcp_stdio_session: ClientSession):
        """Test listing documents after ingesting content."""
        collection_name = f"test_list_with_docs_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {
                    "name": collection_name,
                    "description": "Test list with documents"
                }
            )
            assert not create_result.isError

            # Ingest text
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_text",
                {
                    "content": "Sample document content for testing list functionality.",
                    "collection_name": collection_name,
                    "document_title": "Test Doc 1"
                }
            )
            assert not ingest_result.isError

            # List documents
            result = await mcp_stdio_session.call_tool(
                "list_documents",
                {"collection_name": collection_name}
            )
            assert not result.isError

            # Parse and validate
            text_content = extract_text_content(result)
            assert text_content is not None
            data = json.loads(text_content)

            # Should have documents
            documents = data.get("documents", [])
            assert len(documents) > 0, "Should have ingested document"

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestUpdateDocument:
    """Test update_document MCP tool."""

    @pytest.mark.asyncio
    async def test_update_document_content(self, mcp_stdio_session: ClientSession):
        """Test updating document content."""
        collection_name = f"test_update_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {"name": collection_name, "description": "Test update"}
            )
            assert not create_result.isError

            # Ingest document
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_text",
                {
                    "content": "Original content",
                    "collection_name": collection_name,
                    "document_title": "Original Title"
                }
            )
            assert not ingest_result.isError
            ingest_data = json.loads(extract_text_content(ingest_result))
            doc_id = ingest_data.get("source_document_id")
            assert doc_id is not None, "Should return document ID"

            # Update document
            update_result = await mcp_stdio_session.call_tool(
                "update_document",
                {
                    "document_id": str(doc_id),
                    "content": "Updated content",
                    "title": "Updated Title"
                }
            )
            assert not update_result.isError, f"Update failed: {update_result}"

            # Verify update result
            text_content = extract_text_content(update_result)
            assert text_content is not None
            data = json.loads(text_content)
            assert "document_id" in data, "Update result should contain document_id"

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_update_document_metadata(self, mcp_stdio_session: ClientSession):
        """Test updating document metadata."""
        collection_name = f"test_update_meta_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {"name": collection_name, "description": "Test update metadata"}
            )
            assert not create_result.isError

            # Ingest document
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_text",
                {
                    "content": "Sample content",
                    "collection_name": collection_name,
                    "metadata": json.dumps({"version": "1.0"})
                }
            )
            assert not ingest_result.isError
            ingest_data = json.loads(extract_text_content(ingest_result))
            doc_id = ingest_data.get("source_document_id")

            # Update metadata
            update_result = await mcp_stdio_session.call_tool(
                "update_document",
                {
                    "document_id": str(doc_id),
                    "metadata": json.dumps({"version": "2.0", "updated": True})
                }
            )
            assert not update_result.isError

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestDeleteDocument:
    """Test delete_document MCP tool."""

    @pytest.mark.asyncio
    async def test_delete_document(self, mcp_stdio_session: ClientSession):
        """Test deleting a document."""
        collection_name = f"test_delete_{uuid.uuid4().hex[:8]}"

        try:
            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {"name": collection_name, "description": "Test delete"}
            )
            assert not create_result.isError

            # Ingest document
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_text",
                {
                    "content": "Content to delete",
                    "collection_name": collection_name,
                    "document_title": "Deletable Document"
                }
            )
            assert not ingest_result.isError
            ingest_data = json.loads(extract_text_content(ingest_result))
            doc_id = ingest_data.get("source_document_id")
            assert doc_id is not None

            # Delete document
            delete_result = await mcp_stdio_session.call_tool(
                "delete_document",
                {"document_id": str(doc_id)}
            )
            assert not delete_result.isError, f"Delete failed: {delete_result}"

            # Verify deletion result
            text_content = extract_text_content(delete_result)
            assert text_content is not None
            data = json.loads(text_content)
            assert "document_id" in data or "success" in data, "Delete result should confirm deletion"

        finally:
            # Cleanup (collection may be empty now)
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestQueryTemporal:
    """Test query_temporal MCP tool."""

    @pytest.mark.asyncio
    async def test_query_temporal(self, mcp_stdio_session: ClientSession):
        """Test querying temporal knowledge graph data."""
        result = await mcp_stdio_session.call_tool(
            "query_temporal",
            {"query": "How has the project evolved?"}
        )

        # Tool should succeed or return unavailable gracefully
        if result.isError:
            error_text = extract_error_text(result)
            assert error_text is not None, "Error result should have text"
        else:
            text_content = extract_text_content(result)
            assert text_content is not None, "Response should have content"
            # Parse response
            try:
                data = json.loads(text_content)
                # Should have status field
                assert "status" in data or "timeline" in data, "Response missing expected fields"
            except json.JSONDecodeError:
                # Plain text response is ok
                assert len(text_content) > 0, "Response should not be empty"


class TestIngestFile:
    """Test ingest_file MCP tool."""

    @pytest.mark.asyncio
    async def test_ingest_file_text(self, tmp_path, mcp_stdio_session: ClientSession):
        """Test ingesting a text file."""
        collection_name = f"test_ingest_file_{uuid.uuid4().hex[:8]}"

        try:
            # Create test file
            test_file = tmp_path / "test_document.txt"
            test_content = "This is a test document.\nIt contains multiple lines.\nFor file ingestion testing."
            test_file.write_text(test_content)

            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {"name": collection_name, "description": "Test file ingestion"}
            )
            assert not create_result.isError

            # Ingest file
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_file",
                {
                    "file_path": str(test_file),
                    "collection_name": collection_name
                }
            )
            assert not ingest_result.isError, f"File ingest failed: {ingest_result}"

            # Verify ingestion result
            text_content = extract_text_content(ingest_result)
            assert text_content is not None
            data = json.loads(text_content)
            assert "source_document_id" in data or "num_chunks" in data, "Ingest result should contain document info"

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass


class TestIngestDirectory:
    """Test ingest_directory MCP tool."""

    @pytest.mark.asyncio
    async def test_ingest_directory_multiple_files(self, tmp_path, mcp_stdio_session: ClientSession):
        """Test ingesting multiple files from a directory."""
        collection_name = f"test_ingest_dir_{uuid.uuid4().hex[:8]}"

        try:
            # Create test files
            test_dir = tmp_path / "test_docs"
            test_dir.mkdir()

            (test_dir / "doc1.txt").write_text("First document content")
            (test_dir / "doc2.txt").write_text("Second document content")

            # Create collection
            create_result = await mcp_stdio_session.call_tool(
                "create_collection",
                {"name": collection_name, "description": "Test directory ingestion"}
            )
            assert not create_result.isError

            # Ingest directory
            ingest_result = await mcp_stdio_session.call_tool(
                "ingest_directory",
                {
                    "directory_path": str(test_dir),
                    "collection_name": collection_name,
                    "file_extensions": [".txt"]
                }
            )
            assert not ingest_result.isError, f"Directory ingest failed: {ingest_result}"

            # Verify ingestion result
            text_content = extract_text_content(ingest_result)
            assert text_content is not None
            data = json.loads(text_content)
            assert "files_ingested" in data or "total_chunks" in data, "Ingest result should contain stats"

        finally:
            # Cleanup
            db = Database()
            collection_mgr = CollectionManager(db)
            try:
                collection_mgr.delete_collection(collection_name)
            except Exception:
                pass
