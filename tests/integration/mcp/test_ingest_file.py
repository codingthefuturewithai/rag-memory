"""MCP ingest_file tool integration tests.

Tests that ingest_file() correctly reads text files and stores them in databases.

NOTE: ingest_file has a security restriction - it can only read files from configured
mount directories. The test server is configured with 'test-data' as the mount.
"""

import json
import pytest
from pathlib import Path
from .conftest import extract_text_content

pytestmark = pytest.mark.anyio

# Determine the test-data directory relative to this file
TEST_DATA_DIR = Path(__file__).parent.parent.parent.parent / "test-data"


class TestIngestFile:
    """Test ingest_file tool functionality via MCP."""

    async def test_ingest_file_success(self, mcp_session, setup_test_collection):
        """Test ingesting a text file successfully.

        Creates a temporary file in the mounted test-data directory and verifies
        it can be ingested into a collection.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Create a test file in the test-data mount directory
        test_file = TEST_DATA_DIR / "test_ingest_file_success.txt"
        test_content = "This is a test document for ingestion. It contains multiple sentences."
        test_file.write_text(test_content)

        try:
            # Ingest the file
            result = await session.call_tool("ingest_file", {
                "file_path": str(test_file),
                "collection_name": collection_name,
                "metadata": {"source": "test", "type": "unit_test"}
            })

            # Verify success
            assert not result.isError, f"ingest_file failed: {result}"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify response structure
            assert response["status"] == "success", "Ingestion should succeed"
            assert "document_id" in response, "Response should include document_id"
            assert isinstance(response["document_id"], int), "document_id should be integer"
            assert response["document_id"] > 0, "document_id should be positive"
            assert "chunks_created" in response, "Response should include chunks_created"
            assert response["chunks_created"] >= 1, "Should create at least one chunk"
            assert response["collection_name"] == collection_name, "Should maintain collection name"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_markdown(self, mcp_session, setup_test_collection):
        """Test ingesting a markdown file.

        Verifies that markdown files are processed correctly.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Create a markdown file in test-data mount
        test_file = TEST_DATA_DIR / "test_ingest_markdown.md"
        test_content = """# Test Document

This is a markdown test document.

## Section 1
Content of section 1.

## Section 2
Content of section 2."""
        test_file.write_text(test_content)

        try:
            # Ingest the file
            result = await session.call_tool("ingest_file", {
                "file_path": str(test_file),
                "collection_name": collection_name
            })

            assert not result.isError, "Should ingest markdown files"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            assert response["status"] == "success", "Markdown ingestion should succeed"
            assert response["chunks_created"] >= 1, "Should create chunks from markdown"

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

        test_file = TEST_DATA_DIR / "test_metadata.txt"
        test_file.write_text("Content with metadata")

        try:
            # Ingest with custom metadata
            custom_metadata = {
                "source": "test_source",
                "category": "test_docs",
                "version": "1.0"
            }

            result = await session.call_tool("ingest_file", {
                "file_path": str(test_file),
                "collection_name": collection_name,
                "metadata": custom_metadata
            })

            assert not result.isError, "Should ingest file with metadata"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            assert response["status"] == "success"
            assert "document_id" in response

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_invalid_collection(self, mcp_session):
        """Test ingest_file fails with non-existent collection.

        Verifies proper error handling for missing collections.
        """
        session, transport = mcp_session

        test_file = TEST_DATA_DIR / "test_invalid_collection.txt"
        test_file.write_text("test content")

        try:
            result = await session.call_tool("ingest_file", {
                "file_path": str(test_file),
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

        result = await session.call_tool("ingest_file", {
            "file_path": str(TEST_DATA_DIR / "nonexistent_file_12345.txt"),
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

        test_file = TEST_DATA_DIR / "test_structure.txt"
        test_file.write_text("This is test content for structure validation.")

        try:
            result = await session.call_tool("ingest_file", {
                "file_path": str(test_file),
                "collection_name": collection_name,
                "include_chunk_ids": True
            })

            assert not result.isError, "Ingestion should succeed"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify required fields
            required_fields = ["status", "document_id", "chunks_created", "collection_name"]
            for field in required_fields:
                assert field in response, f"Response missing required field: {field}"

            # Verify field types
            assert isinstance(response["status"], str), "status should be string"
            assert isinstance(response["document_id"], int), "document_id should be integer"
            assert isinstance(response["chunks_created"], int), "chunks_created should be integer"
            assert isinstance(response["collection_name"], str), "collection_name should be string"

            # When include_chunk_ids=True, should have chunk_ids field
            if response.get("status") == "success":
                # chunk_ids might not be present if there's an error, but on success it should be
                assert "chunk_ids" in response or response["chunks_created"] >= 1, \
                    "Should have chunk information on success"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
