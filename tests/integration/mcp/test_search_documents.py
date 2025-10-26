"""MCP search_documents tool integration tests.

Tests that search_documents() actually finds ingested content via MCP protocol.
This is THE critical test - verifies core RAG functionality works end-to-end.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


class TestSearchDocuments:
    """Test search_documents tool functionality via MCP."""

    async def test_search_finds_ingested_content(self, mcp_session, setup_test_collection):
        """Test that search_documents actually finds ingested content.

        CRITICAL TEST: Verifies core RAG workflow:
        1. Ingest content via MCP
        2. Search for it via MCP
        3. Verify found with correct document ID
        """
        session, transport = mcp_session
        collection = setup_test_collection

        # Step 1: Ingest test content
        test_content = "Python is a high-level programming language with dynamic typing."
        ingest_result = await session.call_tool("ingest_text", {
            "content": test_content,
            "collection_name": collection,
            "document_title": "Python Basics",
            "metadata": json.dumps({"topic": "programming", "level": "beginner"})
        })

        # Verify ingestion succeeded
        assert not ingest_result.isError, f"Ingest failed: {ingest_result}"
        ingest_text = extract_text_content(ingest_result)
        ingest_data = json.loads(ingest_text)
        assert "source_document_id" in ingest_data, "Ingest should return document ID"
        doc_id = ingest_data["source_document_id"]

        # Step 2: Search for the content we just ingested
        search_result = await session.call_tool("search_documents", {
            "query": "Python programming language",
            "collection_name": collection,
            "limit": 10,
            "threshold": 0.5,
            "include_source": False,
            "include_metadata": False
        })

        # Step 3: Verify search actually found it
        assert not search_result.isError, f"Search failed: {search_result}"

        # Extract results using helper (handles structuredContent)
        results = extract_result_data(search_result) or []

        # THE CRITICAL ASSERTION: did we actually find the document?
        assert len(results) > 0, f"Search should return results for ingested content. Got: {results}"

        # Verify result structure and content
        first_result = results[0]
        assert "content" in first_result or "text" in first_result, "Result should have content"
        assert "source_document_id" in first_result, "Result should have source document ID"
        assert first_result["source_document_id"] == doc_id, "Result should match ingested document"

    async def test_search_respects_collection_scope(self, mcp_session, collection_mgr):
        """Test that search respects collection boundaries.

        Ingest into collection A, search collection B, verify not found.
        """
        session, transport = mcp_session

        # Create two separate collections
        collection_a = "test_search_a_" + session._mcp_test_id if hasattr(session, '_mcp_test_id') else "test_search_a"
        collection_b = "test_search_b_" + session._mcp_test_id if hasattr(session, '_mcp_test_id') else "test_search_b"

        await session.call_tool("create_collection", {
            "name": collection_a,
            "description": "Test collection A",
            "domain": "testing",
            "domain_scope": "Test collection A for search isolation testing"
        })
        await session.call_tool("create_collection", {
            "name": collection_b,
            "description": "Test collection B",
            "domain": "testing",
            "domain_scope": "Test collection B for search isolation testing"
        })

        # Ingest into collection A
        await session.call_tool("ingest_text", {
            "content": "Secret content in collection A",
            "collection_name": collection_a,
            "document_title": "Secret Doc"
        })

        # Search collection B (should not find it)
        search_result = await session.call_tool("search_documents", {
            "query": "Secret content",
            "collection_name": collection_b,
            "limit": 10,
            "threshold": 0.3
        })

        assert not search_result.isError, f"Search failed: {search_result}"
        results = extract_result_data(search_result) or []

        # Should not find content from collection A
        assert len(results) == 0, \
            "Should not find content from different collection"
        # Note: Collections persist in test database - this is acceptable for integration tests

    async def test_search_respects_threshold(self, mcp_session, setup_test_collection):
        """Test that search respects similarity threshold.

        Ingest content, search with low and high thresholds.
        """
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": "The quick brown fox jumps over the lazy dog",
            "collection_name": collection,
            "document_title": "Fox Story"
        })

        # Search with loose threshold (should find)
        search_loose = await session.call_tool("search_documents", {
            "query": "fast animal",
            "collection_name": collection,
            "threshold": 0.3,
            "limit": 5
        })

        assert not search_loose.isError
        loose_results = extract_result_data(search_loose) or []

        # Search with tight threshold (may not find if similarity is low)
        search_tight = await session.call_tool("search_documents", {
            "query": "fast animal",
            "collection_name": collection,
            "threshold": 0.95,
            "limit": 5
        })

        assert not search_tight.isError
        tight_results = extract_result_data(search_tight) or []

        # Loose should find at least as many as tight
        assert len(loose_results) >= len(tight_results), "Loose threshold should find at least as many results"

    async def test_search_includes_source_when_requested(self, mcp_session, setup_test_collection):
        """Test that search includes full source document when requested."""
        session, transport = mcp_session
        collection = setup_test_collection

        full_content = "This is a complete document about machine learning and AI concepts."

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": full_content,
            "collection_name": collection,
            "document_title": "ML Guide"
        })

        # Search WITHOUT source
        search_no_source = await session.call_tool("search_documents", {
            "query": "machine learning",
            "collection_name": collection,
            "include_source": False,
            "limit": 1
        })

        no_source_results = extract_result_data(search_no_source) or []

        # Search WITH source
        search_with_source = await session.call_tool("search_documents", {
            "query": "machine learning",
            "collection_name": collection,
            "include_source": True,
            "limit": 1
        })

        with_source_results = extract_result_data(search_with_source) or []

        # With source should include source_content field
        assert len(with_source_results) > 0, "Should find content"
        assert "source_content" in with_source_results[0], "Should include source_content when requested"

    async def test_search_empty_result_for_no_matches(self, mcp_session, setup_test_collection):
        """Test that search returns empty results when nothing matches."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest specific content
        await session.call_tool("ingest_text", {
            "content": "The sky is blue and beautiful",
            "collection_name": collection,
            "document_title": "Sky Description"
        })

        # Search for completely unrelated content
        search_result = await session.call_tool("search_documents", {
            "query": "cryptocurrency bitcoin blockchain ethereum",
            "collection_name": collection,
            "threshold": 0.9,
            "limit": 5
        })

        assert not search_result.isError
        results = json.loads(extract_text_content(search_result)) if extract_text_content(search_result) else []

        # Should return empty or very few results
        assert len(results) == 0 or all(r.get("similarity", 0) < 0.5 for r in results)
