"""MCP ingest_directory tool integration tests.

Tests that ingest_directory() correctly reads multiple files from a directory
and stores them in databases.

NOTE: ingest_directory has a security restriction - it can only read files from
configured mount directories. The test server is configured with 'test-data' as
the mount.

IMPORTANT: All paths must be relative to the mount (test-data/) or absolute paths
within the mounted directory. We use relative paths: 'test-data/subdir'
"""

import json
import pytest
from pathlib import Path
from .conftest import extract_text_content

pytestmark = pytest.mark.anyio


class TestIngestDirectory:
    """Test ingest_directory tool functionality via MCP."""

    async def test_ingest_directory_basic(self, mcp_session, setup_test_collection):
        """Test ingesting multiple files from a directory.

        Creates several test files in a directory and verifies they are all
        ingested into the collection.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Use relative path from mount: test-data/subdir
        relative_dir = "test-data/test_ingest_dir_basic"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        # Create multiple test files
        files_to_create = {
            "document1.txt": "This is the first test document about machine learning.",
            "document2.txt": "This is the second test document about neural networks.",
            "document3.md": "# Third Document\n\nThis markdown file discusses deep learning.",
        }

        created_files = []
        try:
            for filename, content in files_to_create.items():
                file_path = test_dir / filename
                file_path.write_text(content)
                created_files.append(file_path)

            # Ingest the directory using relative path
            result = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection_name,
                "file_extensions": [".txt", ".md"],
                "recursive": False,
                "include_document_ids": True
            })

            # Verify success
            assert not result.isError, f"ingest_directory failed: {result}"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify response structure
            assert response["files_found"] >= 3, "Should find at least 3 files"
            assert response["files_ingested"] >= 3, "Should ingest at least 3 files"
            assert response["files_failed"] == 0, "Should have no failed files"
            assert response["total_chunks"] >= 3, "Should create at least 3 chunks"
            assert response["collection_name"] == collection_name
            assert "document_ids" in response, "Should include document_ids when requested"
            assert isinstance(response["document_ids"], list)
            assert len(response["document_ids"]) >= 3, "Should have document IDs for all ingested files"

        finally:
            # Cleanup
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_file_extension_filtering(self, mcp_session, setup_test_collection):
        """Test that file extension filtering works correctly.

        Creates multiple files with different extensions and verifies only
        matching extensions are ingested.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        relative_dir = "test-data/test_ingest_dir_extensions"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create files with different extensions
            (test_dir / "readme.md").write_text("Markdown file")
            (test_dir / "notes.txt").write_text("Text file")
            (test_dir / "script.py").write_text("# Python file - should be skipped")
            (test_dir / "image.jpg").write_text("Image file - should be skipped")

            # Ingest only .md and .txt files using relative path
            result = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection_name,
                "file_extensions": [".md", ".txt"],
                "recursive": False
            })

            assert not result.isError, "ingest_directory should succeed"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Should find all 4 files but only ingest 2 (.md and .txt)
            assert response["files_found"] >= 2, "Should find at least the .md and .txt files"
            assert response["files_ingested"] == 2, "Should ingest exactly 2 files (.md and .txt)"
            assert response["files_failed"] == 0, "Should have no failed files"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_empty_directory(self, mcp_session, setup_test_collection):
        """Test ingest_directory on an empty directory.

        Verifies graceful handling when directory has no matching files.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        relative_dir = "test-data/test_ingest_dir_empty"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Ingest empty directory using relative path
            result = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection_name,
                "file_extensions": [".txt", ".md"],
                "recursive": False
            })

            assert not result.isError, "Should handle empty directory gracefully"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            assert response["files_found"] == 0, "Should find 0 files in empty directory"
            assert response["files_ingested"] == 0, "Should ingest 0 files"
            assert response["files_failed"] == 0, "Should have no failed files"
            assert response["total_chunks"] == 0, "Should create 0 chunks"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_invalid_collection(self, mcp_session):
        """Test ingest_directory fails with non-existent collection.

        Verifies proper error handling for missing collections.
        """
        session, transport = mcp_session

        relative_dir = "test-data/test_ingest_dir_invalid_collection"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            (test_dir / "test.txt").write_text("test content")

            result = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": "nonexistent_collection_xyz",
                "file_extensions": [".txt"],
                "recursive": False
            })

            # Should error
            assert result.isError, "Should fail with non-existent collection"

            error_text = extract_text_content(result)
            assert "does not exist" in error_text or "Collection" in error_text, \
                f"Error should mention missing collection: {error_text}"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_nonexistent_directory(self, mcp_session, setup_test_collection):
        """Test ingest_directory fails gracefully with non-existent directory.

        Verifies proper error handling for missing directories.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        # Use a relative path that doesn't exist
        result = await session.call_tool("ingest_directory", {
            "directory_path": "test-data/nonexistent_dir_12345",
            "collection_name": collection_name,
            "file_extensions": [".txt"],
            "recursive": False
        })

        # Should error
        assert result.isError, "Should fail with non-existent directory"

        error_text = extract_text_content(result)
        assert "not found" in error_text.lower() or "directory" in error_text.lower(), \
            f"Error should mention missing directory: {error_text}"

    async def test_ingest_directory_response_structure(self, mcp_session, setup_test_collection):
        """Test that ingest_directory returns properly structured response.

        Verifies all required fields in the response.
        """
        session, transport = mcp_session
        collection_name = setup_test_collection

        relative_dir = "test-data/test_ingest_dir_structure"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create a few test files
            (test_dir / "file1.txt").write_text("Content of file 1")
            (test_dir / "file2.md").write_text("# Content of file 2")

            result = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection_name,
                "file_extensions": [".txt", ".md"],
                "recursive": False,
                "include_document_ids": True
            })

            assert not result.isError, "Ingestion should succeed"

            response_text = extract_text_content(result)
            response = json.loads(response_text)

            # Verify required fields
            required_fields = ["files_found", "files_ingested", "files_failed", "total_chunks", "collection_name"]
            for field in required_fields:
                assert field in response, f"Response missing required field: {field}"

            # Verify field types
            assert isinstance(response["files_found"], int), "files_found should be integer"
            assert isinstance(response["files_ingested"], int), "files_ingested should be integer"
            assert isinstance(response["files_failed"], int), "files_failed should be integer"
            assert isinstance(response["total_chunks"], int), "total_chunks should be integer"
            assert isinstance(response["collection_name"], str), "collection_name should be string"

            # Verify consistency
            assert response["files_ingested"] + response["files_failed"] <= response["files_found"], \
                "Ingested + failed should not exceed found"
            assert response["total_chunks"] >= response["files_ingested"], \
                "Should have at least one chunk per file"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)
