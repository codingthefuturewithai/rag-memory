"""MCP knowledge graph tool integration tests.

Tests query_relationships and query_temporal tools.
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text

pytestmark = pytest.mark.anyio


class TestQueryRelationships:
    """Test query_relationships tool."""

    async def test_query_relationships_handles_gracefully(self, mcp_session):
        """Test that query_relationships returns gracefully even if graph unavailable."""
        session, transport = mcp_session

        # This should either return relationships or gracefully degrade if graph not available
        result = await session.call_tool("query_relationships", {
            "query": "How does the system work?"
        })

        # Should not error at MCP level (may return unavailable status)
        assert result is not None
        text = extract_text_content(result)
        assert text is not None  # Should have some response

    async def test_query_relationships_with_ingested_content(self, mcp_session, setup_test_collection):
        """Test querying relationships after ingesting content with entities."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content with entities
        await session.call_tool("ingest_text", {
            "content": "Python and Java are programming languages. Python is used for data science. Java is used for enterprise applications.",
            "collection_name": collection,
            "document_title": "Languages"
        })

        # Query relationships (may or may not find depending on graph availability)
        result = await session.call_tool("query_relationships", {
            "query": "What programming languages are mentioned?"
        })

        assert result is not None
        text = extract_text_content(result)
        data = json.loads(text) if text else {}

        # Should have status field
        assert "status" in data, "Should indicate graph status"

    async def test_query_relationships_with_collection_filter(self, mcp_session, setup_test_collection):
        """Test querying relationships with collection_name filter."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content with entities
        await session.call_tool("ingest_text", {
            "content": "Python and Java are programming languages used in software development.",
            "collection_name": collection,
            "document_title": "Languages"
        })

        # Query with collection filter (should only search this collection)
        result = await session.call_tool("query_relationships", {
            "query": "What programming languages are mentioned?",
            "collection_name": collection
        })

        assert result is not None
        text = extract_text_content(result)
        data = json.loads(text) if text else {}

        # Should have status field
        assert "status" in data, "Should indicate graph status"


class TestQueryTemporal:
    """Test query_temporal tool."""

    async def test_query_temporal_handles_gracefully(self, mcp_session):
        """Test that query_temporal returns gracefully even if graph unavailable."""
        session, transport = mcp_session

        # This should either return temporal data or gracefully degrade
        result = await session.call_tool("query_temporal", {
            "query": "How has the system evolved?"
        })

        # Should not error at MCP level
        assert result is not None
        text = extract_text_content(result)
        assert text is not None  # Should have some response

    async def test_query_temporal_with_ingested_content(self, mcp_session, setup_test_collection):
        """Test temporal queries after ingesting content."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": "The project started with basic features and evolved to support advanced capabilities.",
            "collection_name": collection,
            "document_title": "Evolution"
        })

        # Query temporal (may or may not work depending on graph)
        result = await session.call_tool("query_temporal", {
            "query": "How did the project evolve over time?"
        })

        assert result is not None
        text = extract_text_content(result)
        data = json.loads(text) if text else {}

        # Should have status field
        assert "status" in data, "Should indicate graph status"

    async def test_query_temporal_with_collection_filter(self, mcp_session, setup_test_collection):
        """Test temporal queries with collection_name filter."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": "The system was designed in Q1 2024 and implemented in Q2 2024.",
            "collection_name": collection,
            "document_title": "Timeline"
        })

        # Query with collection filter
        result = await session.call_tool("query_temporal", {
            "query": "When was the system designed and implemented?",
            "collection_name": collection
        })

        assert result is not None
        text = extract_text_content(result)
        data = json.loads(text) if text else {}

        # Should have status field
        assert "status" in data, "Should indicate graph status"

    async def test_query_temporal_with_custom_threshold(self, mcp_session, setup_test_collection):
        """Test temporal queries with custom similarity threshold parameter."""
        session, transport = mcp_session
        collection = setup_test_collection

        # Ingest content
        await session.call_tool("ingest_text", {
            "content": "Version 1.0 was released in January. Version 2.0 was released in March with new features.",
            "collection_name": collection,
            "document_title": "Releases"
        })

        # Query with high threshold (more restrictive, fewer results)
        result_high = await session.call_tool("query_temporal", {
            "query": "What versions were released?",
            "collection_name": collection,
            "threshold": 0.7  # High threshold
        })

        # Query with low threshold (less restrictive, more results)
        result_low = await session.call_tool("query_temporal", {
            "query": "What versions were released?",
            "collection_name": collection,
            "threshold": 0.1  # Low threshold
        })

        # Both queries should complete without error
        assert result_high is not None
        assert result_low is not None

        text_high = extract_text_content(result_high)
        text_low = extract_text_content(result_low)

        data_high = json.loads(text_high) if text_high else {}
        data_low = json.loads(text_low) if text_low else {}

        # Both should have status field
        assert "status" in data_high, "High threshold query should have status"
        assert "status" in data_low, "Low threshold query should have status"

        # If graph is available and results exist, low threshold should return >= high threshold
        if data_high.get("status") == "success" and "entities" in data_high and "entities" in data_low:
            high_count = len(data_high.get("entities", []))
            low_count = len(data_low.get("entities", []))
            assert low_count >= high_count, "Lower threshold should return same or more results"
