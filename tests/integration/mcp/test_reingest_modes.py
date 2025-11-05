"""MCP reingest mode integration tests.

Tests comprehensive duplicate detection and reingest functionality across all 4 ingest tools:
- ingest_text
- ingest_file
- ingest_directory
- ingest_url

Each tool is tested for:
1. Duplicate detection (mode="ingest" errors on duplicate)
2. Reingest mode deletes old document completely
3. Graph cleanup verification
4. Other documents preserved during reingest

CRITICAL: These tests prevent regressions of the centralized deletion logic bug
where missing `await` keywords caused incomplete deletions and duplicate documents.
"""

import json
import pytest
from pathlib import Path
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


# ============================================================================
# Helper Functions
# ============================================================================


async def verify_document_exists(session, doc_id: int) -> bool:
    """Verify document exists by attempting to retrieve it.

    Returns:
        True if document exists, False otherwise
    """
    result = await session.call_tool("get_document_by_id", {
        "document_id": doc_id
    })
    return not result.isError


async def verify_document_deleted(session, doc_id: int) -> bool:
    """Verify document is completely deleted.

    Returns:
        True if document is deleted, False if still exists
    """
    result = await session.call_tool("get_document_by_id", {
        "document_id": doc_id
    })
    return result.isError


async def count_documents_in_collection(session, collection_name: str) -> int:
    """Count total documents in a collection.

    Returns:
        Number of documents in collection
    """
    result = await session.call_tool("list_documents", {
        "collection_name": collection_name
    })

    if result.isError:
        return 0

    data = extract_result_data(result) or {}
    documents = data.get("documents", [])
    return len(documents)


# ============================================================================
# Test Class: ingest_text Reingest Mode
# ============================================================================


class TestIngestTextReingestMode:
    """Test ingest_text duplicate detection and reingest mode."""

    async def test_ingest_text_duplicate_detection_mode_ingest(self, mcp_session, setup_test_collection):
        """Test that ingest_text with mode='ingest' errors on duplicate title.

        Verifies:
        - First ingest succeeds
        - Second ingest with same title and mode='ingest' errors
        - Error message suggests using mode='reingest'
        """
        session, transport = mcp_session
        collection = setup_test_collection

        content = "This is test content for duplicate detection"
        title = "Duplicate Test Doc"

        # First ingest should succeed
        result1 = await session.call_tool("ingest_text", {
            "content": content,
            "collection_name": collection,
            "document_title": title,
            "mode": "ingest"
        })

        assert not result1.isError, f"First ingest should succeed: {result1}"

        # Second ingest with same title should error
        result2 = await session.call_tool("ingest_text", {
            "content": "Different content but same title",
            "collection_name": collection,
            "document_title": title,
            "mode": "ingest"
        })

        assert result2.isError, "Second ingest with duplicate title should error"

        error_text = extract_text_content(result2)
        assert error_text is not None, "Error should have text content"
        assert "already exists" in error_text.lower() or "duplicate" in error_text.lower(), \
            f"Error should mention duplicate: {error_text}"
        assert "reingest" in error_text.lower(), \
            f"Error should suggest using mode='reingest': {error_text}"

    async def test_ingest_text_reingest_mode_deletes_old_document(self, mcp_session, setup_test_collection):
        """Test that ingest_text with mode='reingest' completely deletes old document.

        Verifies:
        - First ingest creates document with doc_id_1
        - Reingest creates new document with doc_id_2
        - Old document (doc_id_1) is completely deleted
        - New document (doc_id_2) exists with new content
        - Only ONE document exists in collection (not both)
        """
        session, transport = mcp_session
        collection = setup_test_collection

        title = "Reingest Test Doc"

        # First ingest
        result1 = await session.call_tool("ingest_text", {
            "content": "Original content version 1",
            "collection_name": collection,
            "document_title": title,
            "mode": "ingest"
        })

        assert not result1.isError, f"First ingest failed: {result1}"

        data1 = json.loads(extract_text_content(result1))
        doc_id_1 = data1["source_document_id"]
        chunks_1 = data1["num_chunks"]

        # Verify first document exists
        assert await verify_document_exists(session, doc_id_1), \
            f"Document {doc_id_1} should exist after first ingest"

        # Reingest with mode='reingest'
        result2 = await session.call_tool("ingest_text", {
            "content": "Updated content version 2 with more text to ensure different chunks",
            "collection_name": collection,
            "document_title": title,
            "mode": "reingest"
        })

        assert not result2.isError, f"Reingest should succeed: {result2}"

        data2 = json.loads(extract_text_content(result2))
        doc_id_2 = data2["source_document_id"]
        chunks_2 = data2["num_chunks"]

        # Verify old document is DELETED
        assert await verify_document_deleted(session, doc_id_1), \
            f"Old document {doc_id_1} should be DELETED after reingest"

        # Verify new document EXISTS
        assert await verify_document_exists(session, doc_id_2), \
            f"New document {doc_id_2} should exist after reingest"

        # Verify document IDs are different
        assert doc_id_1 != doc_id_2, "Reingest should create a new document ID"

        # Verify only ONE document in collection (not both)
        doc_count = await count_documents_in_collection(session, collection)
        assert doc_count == 1, \
            f"Collection should have exactly 1 document after reingest, found {doc_count}"

    async def test_ingest_text_reingest_preserves_other_documents(self, mcp_session, setup_test_collection):
        """Test that reingest only affects the target document, not others.

        Verifies:
        - Ingest document A
        - Ingest document B
        - Reingest document A
        - Document B is completely untouched
        - Both documents exist in collection
        """
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest document A
        result_a1 = await session.call_tool("ingest_text", {
            "content": "Document A original content",
            "collection_name": collection,
            "document_title": "Document A",
            "mode": "ingest"
        })

        assert not result_a1.isError
        data_a1 = json.loads(extract_text_content(result_a1))
        doc_id_a1 = data_a1["source_document_id"]

        # Ingest document B
        result_b = await session.call_tool("ingest_text", {
            "content": "Document B content",
            "collection_name": collection,
            "document_title": "Document B",
            "mode": "ingest"
        })

        assert not result_b.isError
        data_b = json.loads(extract_text_content(result_b))
        doc_id_b = data_b["source_document_id"]

        # Verify both exist
        assert await verify_document_exists(session, doc_id_a1)
        assert await verify_document_exists(session, doc_id_b)

        # Reingest document A
        result_a2 = await session.call_tool("ingest_text", {
            "content": "Document A updated content",
            "collection_name": collection,
            "document_title": "Document A",
            "mode": "reingest"
        })

        assert not result_a2.isError
        data_a2 = json.loads(extract_text_content(result_a2))
        doc_id_a2 = data_a2["source_document_id"]

        # Verify document B is UNTOUCHED
        assert await verify_document_exists(session, doc_id_b), \
            f"Document B ({doc_id_b}) should still exist after reingest of Document A"

        # Verify old document A is deleted, new A exists
        assert await verify_document_deleted(session, doc_id_a1), \
            f"Old Document A ({doc_id_a1}) should be deleted"
        assert await verify_document_exists(session, doc_id_a2), \
            f"New Document A ({doc_id_a2}) should exist"

        # Verify collection has exactly 2 documents
        doc_count = await count_documents_in_collection(session, collection)
        assert doc_count == 2, \
            f"Collection should have 2 documents (A and B), found {doc_count}"

    async def test_ingest_text_reingest_searchable_content_updated(self, mcp_session, setup_test_collection):
        """Test that reingest updates searchable content correctly.

        Verifies:
        - Original content is searchable
        - After reingest, new content is searchable
        - Old content is no longer found in search results
        """
        session, transport = mcp_session
        collection = setup_test_collection

        title = "Search Test Doc"

        # Ingest with unique keyword "zebras"
        result1 = await session.call_tool("ingest_text", {
            "content": "This document is about zebras in the wild",
            "collection_name": collection,
            "document_title": title,
            "mode": "ingest"
        })

        assert not result1.isError
        data1 = json.loads(extract_text_content(result1))
        doc_id_1 = data1["source_document_id"]

        # Search for "zebras" should find document
        search1 = await session.call_tool("search_documents", {
            "query": "zebras in the wild",
            "collection_name": collection
        })

        results1 = extract_result_data(search1) or []
        assert len(results1) > 0, "Should find document with 'zebras' keyword"
        assert any(r.get("source_document_id") == doc_id_1 for r in results1), \
            "Search results should include original document"

        # Reingest with different keyword "elephants"
        result2 = await session.call_tool("ingest_text", {
            "content": "This document is now about elephants in the jungle",
            "collection_name": collection,
            "document_title": title,
            "mode": "reingest"
        })

        assert not result2.isError
        data2 = json.loads(extract_text_content(result2))
        doc_id_2 = data2["source_document_id"]

        # Search for "elephants" should find new document
        search2 = await session.call_tool("search_documents", {
            "query": "elephants in the jungle",
            "collection_name": collection
        })

        results2 = extract_result_data(search2) or []
        assert len(results2) > 0, "Should find document with 'elephants' keyword"
        assert any(r.get("source_document_id") == doc_id_2 for r in results2), \
            "Search results should include new document"

        # Search for "zebras" should NOT find old document
        search3 = await session.call_tool("search_documents", {
            "query": "zebras in the wild",
            "collection_name": collection,
            "threshold": 0.3
        })

        results3 = extract_result_data(search3) or []
        # Should not find old document (it's deleted)
        assert not any(r.get("source_document_id") == doc_id_1 for r in results3), \
            "Old document should not appear in search results"


# ============================================================================
# Test Class: ingest_file Reingest Mode
# ============================================================================


class TestIngestFileReingestMode:
    """Test ingest_file duplicate detection and reingest mode."""

    async def test_ingest_file_duplicate_detection_mode_ingest(self, mcp_session, setup_test_collection):
        """Test that ingest_file with mode='ingest' errors on duplicate file_path.

        Verifies:
        - First ingest succeeds
        - Second ingest with same file_path and mode='ingest' errors
        - Error message suggests using mode='reingest'
        """
        session, transport = mcp_session
        collection = setup_test_collection

        # Create test file
        relative_path = "test-data/test_file_duplicate.txt"
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Original file content for duplicate test")

        try:
            # First ingest should succeed
            result1 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "mode": "ingest"
            })

            assert not result1.isError, f"First ingest should succeed: {result1}"

            # Modify file content but same path
            test_file.write_text("Modified file content but same path")

            # Second ingest with same file_path should error
            result2 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "mode": "ingest"
            })

            assert result2.isError, "Second ingest with duplicate file_path should error"

            error_text = extract_text_content(result2)
            assert error_text is not None, "Error should have text content"
            assert "already exists" in error_text.lower() or "duplicate" in error_text.lower(), \
                f"Error should mention duplicate: {error_text}"
            assert "reingest" in error_text.lower(), \
                f"Error should suggest using mode='reingest': {error_text}"

        finally:
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_reingest_mode_deletes_old_document(self, mcp_session, setup_test_collection):
        """Test that ingest_file with mode='reingest' completely deletes old document.

        Verifies:
        - First ingest creates document with doc_id_1
        - Reingest creates new document with doc_id_2
        - Old document (doc_id_1) is completely deleted
        - New document (doc_id_2) exists with new content
        - Only ONE document exists in collection
        """
        session, transport = mcp_session
        collection = setup_test_collection

        relative_path = "test-data/test_file_reingest.txt"
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # First ingest
            test_file.write_text("Original file content version 1")

            result1 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "mode": "ingest"
            })

            assert not result1.isError, f"First ingest failed: {result1}"

            data1 = json.loads(extract_text_content(result1))
            doc_id_1 = data1["source_document_id"]

            # Verify first document exists
            assert await verify_document_exists(session, doc_id_1), \
                f"Document {doc_id_1} should exist after first ingest"

            # Modify file and reingest
            test_file.write_text("Updated file content version 2 with more text to ensure different chunks")

            result2 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "mode": "reingest"
            })

            assert not result2.isError, f"Reingest should succeed: {result2}"

            data2 = json.loads(extract_text_content(result2))
            doc_id_2 = data2["source_document_id"]

            # Verify old document is DELETED
            assert await verify_document_deleted(session, doc_id_1), \
                f"Old document {doc_id_1} should be DELETED after reingest"

            # Verify new document EXISTS
            assert await verify_document_exists(session, doc_id_2), \
                f"New document {doc_id_2} should exist after reingest"

            # Verify document IDs are different
            assert doc_id_1 != doc_id_2, "Reingest should create a new document ID"

            # Verify only ONE document in collection
            doc_count = await count_documents_in_collection(session, collection)
            assert doc_count == 1, \
                f"Collection should have exactly 1 document after reingest, found {doc_count}"

        finally:
            if test_file.exists():
                test_file.unlink()

    async def test_ingest_file_reingest_preserves_other_files(self, mcp_session, setup_test_collection):
        """Test that reingest only affects the target file, not others.

        Verifies:
        - Ingest file A
        - Ingest file B
        - Reingest file A
        - File B is completely untouched
        - Both files exist in collection
        """
        session, transport = mcp_session
        collection = setup_test_collection

        file_a_path = "test-data/test_file_a.txt"
        file_b_path = "test-data/test_file_b.txt"

        file_a = Path(file_a_path)
        file_b = Path(file_b_path)

        file_a.parent.mkdir(parents=True, exist_ok=True)
        file_b.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Ingest file A
            file_a.write_text("File A original content")
            result_a1 = await session.call_tool("ingest_file", {
                "file_path": file_a_path,
                "collection_name": collection,
                "mode": "ingest"
            })

            assert not result_a1.isError
            data_a1 = json.loads(extract_text_content(result_a1))
            doc_id_a1 = data_a1["source_document_id"]

            # Ingest file B
            file_b.write_text("File B content")
            result_b = await session.call_tool("ingest_file", {
                "file_path": file_b_path,
                "collection_name": collection,
                "mode": "ingest"
            })

            assert not result_b.isError
            data_b = json.loads(extract_text_content(result_b))
            doc_id_b = data_b["source_document_id"]

            # Verify both exist
            assert await verify_document_exists(session, doc_id_a1)
            assert await verify_document_exists(session, doc_id_b)

            # Reingest file A
            file_a.write_text("File A updated content")
            result_a2 = await session.call_tool("ingest_file", {
                "file_path": file_a_path,
                "collection_name": collection,
                "mode": "reingest"
            })

            assert not result_a2.isError
            data_a2 = json.loads(extract_text_content(result_a2))
            doc_id_a2 = data_a2["source_document_id"]

            # Verify file B is UNTOUCHED
            assert await verify_document_exists(session, doc_id_b), \
                f"File B document ({doc_id_b}) should still exist after reingest of File A"

            # Verify old file A is deleted, new A exists
            assert await verify_document_deleted(session, doc_id_a1), \
                f"Old File A document ({doc_id_a1}) should be deleted"
            assert await verify_document_exists(session, doc_id_a2), \
                f"New File A document ({doc_id_a2}) should exist"

            # Verify collection has exactly 2 documents
            doc_count = await count_documents_in_collection(session, collection)
            assert doc_count == 2, \
                f"Collection should have 2 documents (A and B), found {doc_count}"

        finally:
            if file_a.exists():
                file_a.unlink()
            if file_b.exists():
                file_b.unlink()

    async def test_ingest_file_reingest_with_metadata_update(self, mcp_session, setup_test_collection):
        """Test that reingest updates file with new metadata.

        Verifies:
        - First ingest with metadata v1
        - Reingest with metadata v2
        - Old document is deleted
        - New document has updated metadata
        """
        session, transport = mcp_session
        collection = setup_test_collection

        relative_path = "test-data/test_file_metadata.txt"
        test_file = Path(relative_path)
        test_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # First ingest with metadata
            test_file.write_text("File content with metadata")

            result1 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "metadata": {"version": "1.0", "status": "draft"},
                "mode": "ingest"
            })

            assert not result1.isError
            data1 = json.loads(extract_text_content(result1))
            doc_id_1 = data1["source_document_id"]

            # Reingest with updated metadata
            test_file.write_text("Updated file content")

            result2 = await session.call_tool("ingest_file", {
                "file_path": relative_path,
                "collection_name": collection,
                "metadata": {"version": "2.0", "status": "published"},
                "mode": "reingest"
            })

            assert not result2.isError
            data2 = json.loads(extract_text_content(result2))
            doc_id_2 = data2["source_document_id"]

            # Verify old document deleted, new exists
            assert await verify_document_deleted(session, doc_id_1)
            assert await verify_document_exists(session, doc_id_2)

        finally:
            if test_file.exists():
                test_file.unlink()


# ============================================================================
# Test Class: ingest_directory Reingest Mode
# ============================================================================


class TestIngestDirectoryReingestMode:
    """Test ingest_directory duplicate detection and reingest mode."""

    async def test_ingest_directory_duplicate_detection_mode_ingest(self, mcp_session, setup_test_collection):
        """Test that ingest_directory with mode='ingest' errors on duplicate file_paths.

        Verifies:
        - First directory ingest succeeds
        - Second ingest with same files and mode='ingest' errors
        - Error message lists duplicate files
        - Error message suggests using mode='reingest'
        """
        session, transport = mcp_session
        collection = setup_test_collection

        # Create test directory with files
        relative_dir = "test-data/test_dir_duplicate"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create test files
            (test_dir / "file1.txt").write_text("File 1 content")
            (test_dir / "file2.txt").write_text("File 2 content")

            # First ingest should succeed
            result1 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest"
            })

            assert not result1.isError, f"First directory ingest should succeed: {result1}"

            # Modify files but same paths
            (test_dir / "file1.txt").write_text("Modified file 1 content")
            (test_dir / "file2.txt").write_text("Modified file 2 content")

            # Second ingest with same directory should error
            result2 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest"
            })

            assert result2.isError, "Second ingest with duplicate files should error"

            error_text = extract_text_content(result2)
            assert error_text is not None, "Error should have text content"
            assert "already been ingested" in error_text.lower() or "duplicate" in error_text.lower(), \
                f"Error should mention duplicates: {error_text}"
            assert "reingest" in error_text.lower(), \
                f"Error should suggest using mode='reingest': {error_text}"
            # Should list the duplicate files
            assert "file1.txt" in error_text or "file2.txt" in error_text, \
                f"Error should list duplicate files: {error_text}"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_reingest_mode_deletes_old_documents(self, mcp_session, setup_test_collection):
        """Test that ingest_directory with mode='reingest' deletes all old documents.

        Verifies:
        - First ingest creates multiple documents
        - Reingest creates new documents for all files
        - ALL old documents are completely deleted
        - ALL new documents exist
        - Document count matches number of files
        """
        session, transport = mcp_session
        collection = setup_test_collection

        relative_dir = "test-data/test_dir_reingest"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # First ingest
            (test_dir / "doc1.txt").write_text("Document 1 original")
            (test_dir / "doc2.txt").write_text("Document 2 original")
            (test_dir / "doc3.txt").write_text("Document 3 original")

            result1 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest",
                "include_document_ids": True
            })

            assert not result1.isError, f"First ingest failed: {result1}"

            data1 = json.loads(extract_text_content(result1))
            old_doc_ids = data1.get("document_ids", [])
            assert len(old_doc_ids) == 3, "Should have 3 document IDs from first ingest"

            # Verify all old documents exist
            for doc_id in old_doc_ids:
                assert await verify_document_exists(session, doc_id), \
                    f"Document {doc_id} should exist after first ingest"

            # Modify files and reingest
            (test_dir / "doc1.txt").write_text("Document 1 updated with more content")
            (test_dir / "doc2.txt").write_text("Document 2 updated with more content")
            (test_dir / "doc3.txt").write_text("Document 3 updated with more content")

            result2 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "reingest",
                "include_document_ids": True
            })

            assert not result2.isError, f"Reingest should succeed: {result2}"

            data2 = json.loads(extract_text_content(result2))
            new_doc_ids = data2.get("document_ids", [])
            assert len(new_doc_ids) == 3, "Should have 3 new document IDs from reingest"

            # Verify ALL old documents are DELETED
            for old_doc_id in old_doc_ids:
                assert await verify_document_deleted(session, old_doc_id), \
                    f"Old document {old_doc_id} should be DELETED after reingest"

            # Verify ALL new documents EXIST
            for new_doc_id in new_doc_ids:
                assert await verify_document_exists(session, new_doc_id), \
                    f"New document {new_doc_id} should exist after reingest"

            # Verify no overlap between old and new IDs
            assert not any(doc_id in new_doc_ids for doc_id in old_doc_ids), \
                "Old and new document IDs should not overlap"

            # Verify collection has exactly 3 documents (not 6)
            doc_count = await count_documents_in_collection(session, collection)
            assert doc_count == 3, \
                f"Collection should have exactly 3 documents after reingest, found {doc_count}"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)

    async def test_ingest_directory_reingest_preserves_other_directories(self, mcp_session, setup_test_collection):
        """Test that reingest only affects files in target directory, not others.

        Verifies:
        - Ingest directory A with files
        - Ingest directory B with files
        - Reingest directory A
        - Directory B files are completely untouched
        - All documents from both directories exist
        """
        session, transport = mcp_session
        collection = setup_test_collection

        dir_a_path = "test-data/test_dir_a"
        dir_b_path = "test-data/test_dir_b"

        dir_a = Path(dir_a_path)
        dir_b = Path(dir_b_path)

        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        try:
            # Ingest directory A
            (dir_a / "file_a1.txt").write_text("Dir A File 1")
            (dir_a / "file_a2.txt").write_text("Dir A File 2")

            result_a1 = await session.call_tool("ingest_directory", {
                "directory_path": dir_a_path,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest",
                "include_document_ids": True
            })

            assert not result_a1.isError
            data_a1 = json.loads(extract_text_content(result_a1))
            old_dir_a_ids = data_a1.get("document_ids", [])
            assert len(old_dir_a_ids) == 2

            # Ingest directory B
            (dir_b / "file_b1.txt").write_text("Dir B File 1")
            (dir_b / "file_b2.txt").write_text("Dir B File 2")

            result_b = await session.call_tool("ingest_directory", {
                "directory_path": dir_b_path,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest",
                "include_document_ids": True
            })

            assert not result_b.isError
            data_b = json.loads(extract_text_content(result_b))
            dir_b_ids = data_b.get("document_ids", [])
            assert len(dir_b_ids) == 2

            # Verify all 4 documents exist
            for doc_id in old_dir_a_ids + dir_b_ids:
                assert await verify_document_exists(session, doc_id)

            # Reingest directory A
            (dir_a / "file_a1.txt").write_text("Dir A File 1 Updated")
            (dir_a / "file_a2.txt").write_text("Dir A File 2 Updated")

            result_a2 = await session.call_tool("ingest_directory", {
                "directory_path": dir_a_path,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "reingest",
                "include_document_ids": True
            })

            assert not result_a2.isError
            data_a2 = json.loads(extract_text_content(result_a2))
            new_dir_a_ids = data_a2.get("document_ids", [])
            assert len(new_dir_a_ids) == 2

            # Verify directory B files are UNTOUCHED
            for doc_id in dir_b_ids:
                assert await verify_document_exists(session, doc_id), \
                    f"Directory B document {doc_id} should still exist after reingest of Directory A"

            # Verify old directory A files are deleted
            for doc_id in old_dir_a_ids:
                assert await verify_document_deleted(session, doc_id), \
                    f"Old Directory A document {doc_id} should be deleted"

            # Verify new directory A files exist
            for doc_id in new_dir_a_ids:
                assert await verify_document_exists(session, doc_id), \
                    f"New Directory A document {doc_id} should exist"

            # Verify collection has exactly 4 documents (2 from A, 2 from B)
            doc_count = await count_documents_in_collection(session, collection)
            assert doc_count == 4, \
                f"Collection should have 4 documents (2 from each directory), found {doc_count}"

        finally:
            import shutil
            if dir_a.exists():
                shutil.rmtree(dir_a)
            if dir_b.exists():
                shutil.rmtree(dir_b)

    async def test_ingest_directory_reingest_partial_files(self, mcp_session, setup_test_collection):
        """Test reingest with subset of files (some exist, some are new).

        Verifies:
        - Ingest directory with 3 files
        - Remove 1 file, add 1 new file (3 total but different)
        - Reingest should only affect the 2 files that existed before
        - New file should be ingested as new document
        - Removed file's document should remain (not affected by reingest)
        """
        session, transport = mcp_session
        collection = setup_test_collection

        relative_dir = "test-data/test_dir_partial"
        test_dir = Path(relative_dir)
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            # First ingest with 3 files
            (test_dir / "keep1.txt").write_text("Keep file 1")
            (test_dir / "keep2.txt").write_text("Keep file 2")
            (test_dir / "remove.txt").write_text("File to remove")

            result1 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "ingest",
                "include_document_ids": True
            })

            assert not result1.isError
            data1 = json.loads(extract_text_content(result1))
            old_doc_ids = data1.get("document_ids", [])
            assert len(old_doc_ids) == 3

            # Get document for removed file (to verify it's not touched)
            list_result = await session.call_tool("list_documents", {
                "collection_name": collection,
                "include_details": True
            })
            list_data = extract_result_data(list_result) or {}
            docs = list_data.get("documents", [])
            removed_file_doc = next((d for d in docs if "remove.txt" in d.get("filename", "")), None)
            assert removed_file_doc is not None
            removed_doc_id = removed_file_doc["id"]

            # Modify files: remove one, add one
            (test_dir / "remove.txt").unlink()  # Remove file
            (test_dir / "keep1.txt").write_text("Keep file 1 updated")
            (test_dir / "keep2.txt").write_text("Keep file 2 updated")
            (test_dir / "new.txt").write_text("New file added")  # Add new file

            # Reingest - should affect keep1, keep2 (reingest) and new (fresh ingest)
            # The removed.txt document should remain untouched since file doesn't exist
            result2 = await session.call_tool("ingest_directory", {
                "directory_path": relative_dir,
                "collection_name": collection,
                "file_extensions": [".txt"],
                "recursive": False,
                "mode": "reingest",
                "include_document_ids": True
            })

            assert not result2.isError
            data2 = json.loads(extract_text_content(result2))

            # Should ingest 3 files: keep1 (reingest), keep2 (reingest), new (new)
            assert data2["files_ingested"] == 3

            # The removed file's document should still exist (reingest only affects files in directory)
            assert await verify_document_exists(session, removed_doc_id), \
                "Document for removed file should still exist (reingest only affects current directory files)"

        finally:
            import shutil
            if test_dir.exists():
                shutil.rmtree(test_dir)


# ============================================================================
# Test Class: ingest_url Reingest Mode
# ============================================================================


class TestIngestUrlReingestMode:
    """Test ingest_url duplicate detection and reingest mode."""

    async def test_ingest_url_duplicate_detection_mode_ingest(self, mcp_session, setup_test_collection):
        """Test that ingest_url with mode='ingest' errors on duplicate crawl_root_url.

        Verifies:
        - First crawl succeeds
        - Second crawl with same URL and mode='ingest' errors
        - Error message suggests using mode='reingest'
        """
        session, transport = mcp_session
        collection = setup_test_collection

        url = "https://example.com"

        # First crawl should succeed
        result1 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": False,
            "mode": "ingest"
        })

        assert not result1.isError, f"First crawl should succeed: {result1}"

        # Second crawl with same URL should error
        result2 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": False,
            "mode": "ingest"
        })

        assert result2.isError, "Second crawl with duplicate URL should error"

        error_text = extract_text_content(result2)
        assert error_text is not None, "Error should have text content"
        assert "already been ingested" in error_text.lower() or "already exists" in error_text.lower(), \
            f"Error should mention duplicate crawl: {error_text}"
        assert "reingest" in error_text.lower(), \
            f"Error should suggest using mode='reingest': {error_text}"

    async def test_ingest_url_reingest_mode_deletes_old_pages(self, mcp_session, setup_test_collection):
        """Test that ingest_url with mode='reingest' deletes all old pages completely.

        Verifies:
        - First crawl creates page document(s)
        - Reingest creates new page document(s)
        - ALL old page documents are completely deleted
        - ALL new page documents exist
        - Only new pages remain in collection
        """
        session, transport = mcp_session
        collection = setup_test_collection

        url = "https://example.com"

        # First crawl
        result1 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": False,
            "mode": "ingest",
            "include_document_ids": True
        })

        assert not result1.isError, f"First crawl failed: {result1}"

        data1 = json.loads(extract_text_content(result1))
        old_doc_ids = data1.get("document_ids", [])
        assert len(old_doc_ids) >= 1, "Should have at least 1 document from first crawl"

        # Verify all old documents exist
        for doc_id in old_doc_ids:
            assert await verify_document_exists(session, doc_id), \
                f"Document {doc_id} should exist after first crawl"

        # Reingest with mode='reingest'
        result2 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": False,
            "mode": "reingest",
            "include_document_ids": True
        })

        assert not result2.isError, f"Reingest should succeed: {result2}"

        data2 = json.loads(extract_text_content(result2))
        new_doc_ids = data2.get("document_ids", [])
        assert len(new_doc_ids) >= 1, "Should have at least 1 new document from reingest"

        # Verify ALL old documents are DELETED
        for old_doc_id in old_doc_ids:
            assert await verify_document_deleted(session, old_doc_id), \
                f"Old document {old_doc_id} should be DELETED after reingest"

        # Verify ALL new documents EXIST
        for new_doc_id in new_doc_ids:
            assert await verify_document_exists(session, new_doc_id), \
                f"New document {new_doc_id} should exist after reingest"

        # Verify no overlap between old and new IDs
        assert not any(doc_id in new_doc_ids for doc_id in old_doc_ids), \
            "Old and new document IDs should not overlap"

    async def test_ingest_url_reingest_preserves_other_urls(self, mcp_session, setup_test_collection):
        """Test that reingest only affects pages from target URL, not others.

        Verifies:
        - Crawl URL A
        - Crawl URL B
        - Reingest URL A
        - URL B pages are completely untouched
        - Pages from both URLs exist in collection
        """
        session, transport = mcp_session
        collection = setup_test_collection

        url_a = "https://example.com"
        url_b = "https://httpbin.org"

        # Crawl URL A
        result_a1 = await session.call_tool("ingest_url", {
            "url": url_a,
            "collection_name": collection,
            "follow_links": False,
            "mode": "ingest",
            "include_document_ids": True
        })

        assert not result_a1.isError
        data_a1 = json.loads(extract_text_content(result_a1))
        old_url_a_ids = data_a1.get("document_ids", [])
        assert len(old_url_a_ids) >= 1

        # Crawl URL B
        result_b = await session.call_tool("ingest_url", {
            "url": url_b,
            "collection_name": collection,
            "follow_links": False,
            "mode": "ingest",
            "include_document_ids": True
        })

        assert not result_b.isError
        data_b = json.loads(extract_text_content(result_b))
        url_b_ids = data_b.get("document_ids", [])
        assert len(url_b_ids) >= 1

        # Verify all documents exist
        for doc_id in old_url_a_ids + url_b_ids:
            assert await verify_document_exists(session, doc_id)

        # Reingest URL A
        result_a2 = await session.call_tool("ingest_url", {
            "url": url_a,
            "collection_name": collection,
            "follow_links": False,
            "mode": "reingest",
            "include_document_ids": True
        })

        assert not result_a2.isError
        data_a2 = json.loads(extract_text_content(result_a2))
        new_url_a_ids = data_a2.get("document_ids", [])
        assert len(new_url_a_ids) >= 1

        # Verify URL B pages are UNTOUCHED
        for doc_id in url_b_ids:
            assert await verify_document_exists(session, doc_id), \
                f"URL B document {doc_id} should still exist after reingest of URL A"

        # Verify old URL A pages are deleted
        for doc_id in old_url_a_ids:
            assert await verify_document_deleted(session, doc_id), \
                f"Old URL A document {doc_id} should be deleted"

        # Verify new URL A pages exist
        for doc_id in new_url_a_ids:
            assert await verify_document_exists(session, doc_id), \
                f"New URL A document {doc_id} should exist"

    async def test_ingest_url_reingest_with_link_following(self, mcp_session, setup_test_collection):
        """Test reingest with multi-page crawls (follow_links=True).

        Verifies:
        - First crawl with follow_links creates multiple pages
        - Reingest with follow_links deletes ALL old pages
        - Reingest creates new pages for all crawled URLs
        - Page count is reasonable (not excessive)
        """
        session, transport = mcp_session
        collection = setup_test_collection

        url = "https://example.com"

        # First crawl with follow_links (limit to 3 pages to keep test fast)
        result1 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": True,
            "max_pages": 3,
            "mode": "ingest",
            "include_document_ids": True
        })

        assert not result1.isError
        data1 = json.loads(extract_text_content(result1))
        old_doc_ids = data1.get("document_ids", [])
        old_page_count = len(old_doc_ids)
        assert old_page_count >= 1, "Should have at least 1 page from first crawl"

        # Verify all old pages exist
        for doc_id in old_doc_ids:
            assert await verify_document_exists(session, doc_id)

        # Reingest with follow_links
        result2 = await session.call_tool("ingest_url", {
            "url": url,
            "collection_name": collection,
            "follow_links": True,
            "max_pages": 3,
            "mode": "reingest",
            "include_document_ids": True
        })

        assert not result2.isError
        data2 = json.loads(extract_text_content(result2))
        new_doc_ids = data2.get("document_ids", [])
        new_page_count = len(new_doc_ids)
        assert new_page_count >= 1, "Should have at least 1 new page from reingest"

        # Verify ALL old pages are DELETED
        for old_doc_id in old_doc_ids:
            assert await verify_document_deleted(session, old_doc_id), \
                f"Old page {old_doc_id} should be DELETED after reingest"

        # Verify ALL new pages EXIST
        for new_doc_id in new_doc_ids:
            assert await verify_document_exists(session, new_doc_id), \
                f"New page {new_doc_id} should exist after reingest"

        # Verify collection has only new pages (not both old and new)
        doc_count = await count_documents_in_collection(session, collection)
        assert doc_count == new_page_count, \
            f"Collection should have {new_page_count} documents (new pages only), found {doc_count}"
