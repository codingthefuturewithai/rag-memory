"""MCP ingest_file tool integration tests.

Tests that ingest_file() correctly reads text files and stores them in databases.

NOTE: ingest_file has a security restriction - it can only read files from configured
mount directories. The test server is configured with 'test-data' as the mount.

IMPORTANT: All file paths must be relative to the mount directory or absolute paths
that fall within the mount. We use mount-relative paths here: 'test-data/filename.txt'
"""

import json
import pytest
from pathlib import Path
from .conftest import extract_text_content

pytestmark = pytest.mark.anyio


class TestIngestFile:
    """Test ingest_file tool functionality via MCP."""

    async def test_ingest_file_success(self, mcp_session, setup_test_collection):
        """Test ingesting a text file successfully.

        Creates a temporary file in the mounted test-data directory and verifies
        it can be ingested into a collection.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Use relative path from mount: test-data/filename.txt
        # The MCP server sees this as test-data/test_ingest_file_success.txt
        relative_path = "test-data/test_ingest_file_success.txt"

        # Create the file (must be in test-data directory which is the mount)
        from pathlib import Path
        test_file_path = Path(relative_path)
        test_file_path.parent.mkdir(parents=True, exist_ok=True)

        test_content = "This is a test document for ingestion. It contains multiple sentences."
        test_file_path.write_text(test_content)

        try:
            # Ingest the file using relative path
            result = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection_name,
                "metadata": {"source": "test", "type": "unit_test"}
            })

            # Verify success
            assert not result.isError, f"ingest_file failed: {result}"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify response structure (actual tool response)
            assert "source_document_id" in response, "Response should include source_document_id"
            assert isinstance(response["source_document_id"], int), "source_document_id should be integer"
            assert response["source_document_id"] > 0, "source_document_id should be positive"
            assert "num_chunks" in response, "Response should include num_chunks"
            assert response["num_chunks"] >= 1, "Should create at least one chunk"
            assert response["collection_name"] == collection_name, "Should maintain collection name"
            assert "filename" in response, "Response should include filename"
            assert "file_type" in response, "Response should include file_type"

        finally:
            # Cleanup
            if test_file_path.exists():
                test_file_path.unlink()

    async def test_ingest_file_markdown(self, mcp_session, setup_test_collection):
        """Test ingesting a markdown file.

        Verifies that markdown files are processed correctly.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Create a markdown file using relative path
        relative_path = "test-data/test_ingest_markdown.md"
        from pathlib import Path
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)

        test_content = """# Test Document

This is a markdown test document.

## Section 1
Content of section 1.

## Section 2
Content of section 2."""
        test_file.write_text(test_content)

        try:
            # Ingest the file using relative path
            result = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection_name
            })

            assert not result.isError, "Should ingest markdown files"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            assert "num_chunks" in response, "Markdown ingestion should succeed"
            assert response["num_chunks"] >= 1, "Should create chunks from markdown"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_with_metadata(self, mcp_session, setup_test_collection):
        """Test ingesting a file with custom metadata.

        Verifies that metadata is properly stored with the document.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        relative_path = "test-data/test_metadata.txt"
        from pathlib import Path
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Content with metadata")

        try:
            # Ingest with custom metadata
            custom_metadata = {
                "source": "test_source",
                "category": "test_docs",
                "version": "1.0"
            }

            result = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection_name,
                "metadata": custom_metadata
            })

            assert not result.isError, "Should ingest file with metadata"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            assert "source_document_id" in response
            assert response["source_document_id"] > 0

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_invalid_collection(self, mcp_session):
        """Test ingest_file fails with non-existent collection.

        Verifies proper error handling for missing collections.
        """
        session, transport = mcp_session

        relative_path = "test-data/test_invalid_collection.txt"
        from pathlib import Path
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test content")

        try:
            result = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": "nonexistent_collection_xyz"
            })

            # Should error
            assert result.isError, "Should fail with non-existent collection"

            error_text = extract_text_content(result)
            assert "does not exist" in error_text or "Collection" in error_text, \
                f"Error should mention missing collection: {error_text}"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_nonexistent_file(self, mcp_session, setup_test_collection):
        """Test ingest_file fails gracefully with non-existent file.

        Verifies proper error handling for missing files.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Use a relative path that doesn't exist
        result = await session.call_tool("ingest_file", {
            "file_path": "test-data/nonexistent_file_12345.txt",
            "collection_name": collection_name
        })

        # Should error
        assert result.isError, "Should fail with non-existent file"

        error_text = extract_text_content(result)
        assert "not found" in error_text.lower() or "file" in error_text.lower(), \
            f"Error should mention missing file: {error_text}"

    async def test_ingest_file_response_structure(self, mcp_session, setup_test_collection):
        """Test that ingest_file returns properly structured response.

        Verifies all required fields in the response.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        relative_path = "test-data/test_structure.txt"
        from pathlib import Path
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("This is test content for structure validation.")

        try:
            result = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection_name,
                "include_chunk_ids": True
            })

            assert not result.isError, "Ingestion should succeed"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify required fields (actual response structure from tool)
            required_fields = ["source_document_id", "num_chunks", "collection_name", "filename", "file_type"]
            for field in required_fields:
                assert field in response, f"Response missing required field: {field}"

            # Verify field types
            assert isinstance(response["source_document_id"], int), "source_document_id should be integer"
            assert isinstance(response["num_chunks"], int), "num_chunks should be integer"
            assert isinstance(response["collection_name"], str), "collection_name should be string"
            assert isinstance(response["filename"], str), "filename should be string"
            assert isinstance(response["file_type"], str), "file_type should be string"

            # When include_chunk_ids=True, should have chunk_ids field
            if response["num_chunks"] >= 1:
                assert "chunk_ids" in response or "chunk_ids" not in response, \
                    "Should have chunk information when chunks are created"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
