"""
Phase 1: Verify RAG Metadata Filtering

Tests that the RAG store's metadata_filter parameter works correctly,
verifying that metadata persists through ingestion and is queryable.
"""

import pytest
import pytest_asyncio
import uuid
from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.ingestion.document_store import get_document_store
from src.search import get_similarity_search


@pytest_asyncio.fixture
async def rag_metadata_env():
    """Setup RAG test environment."""
    db = Database()
    embedder = EmbeddingGenerator()
    collection_mgr = CollectionManager(db)

    test_collection = f"rag_metadata_{uuid.uuid4().hex[:8]}"

    try:
        collection_mgr.delete_collection(test_collection)
    except Exception:
        pass

    collection_mgr.create_collection(
        name=test_collection,
        description="RAG metadata test"
    )

    doc_store = get_document_store(db, embedder, collection_mgr)
    searcher = get_similarity_search(db, embedder, collection_mgr)

    yield {
        "doc_store": doc_store,
        "searcher": searcher,
        "collection": test_collection,
        "collection_mgr": collection_mgr
    }

    try:
        collection_mgr.delete_collection(test_collection)
    except Exception:
        pass


class TestRagMetadataFiltering:
    """Test RAG metadata filtering."""

    @pytest.mark.asyncio
    async def test_metadata_persists_in_search_results(self, rag_metadata_env):
        """Verify metadata persists through ingestion and appears in search results."""
        env = rag_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Metadata persists in search results")
        print("="*70)

        # Ingest with metadata
        doc_store.ingest_document(
            content="PostgreSQL is a powerful relational database",
            filename="PostgreSQL Guide",
            collection_name=collection,
            metadata={"domain": "backend", "content_type": "documentation", "version": "15"},
            file_type="text"
        )

        # Search
        results = searcher.search_chunks(
            query="PostgreSQL database",
            collection_name=collection,
            threshold=0.0,
            limit=5
        )

        print(f"\n✅ Ingested and searched")
        assert len(results) > 0, "Should find PostgreSQL content"

        # Check metadata
        result = results[0]
        print(f"   Result metadata: {result.metadata}")
        assert result.metadata.get("domain") == "backend", "Domain should persist"
        assert result.metadata.get("content_type") == "documentation", "Content type should persist"
        assert result.metadata.get("version") == "15", "Version should persist"

        print("✅ TEST PASSED")

    @pytest.mark.asyncio
    async def test_single_metadata_filter(self, rag_metadata_env):
        """Verify single-field metadata filtering."""
        env = rag_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Single metadata field filtering")
        print("="*70)

        # Ingest with different domains
        doc_store.ingest_document(
            content="Docker containerization system",
            filename="Docker",
            collection_name=collection,
            metadata={"domain": "devops"},
            file_type="text"
        )

        doc_store.ingest_document(
            content="React JavaScript library",
            filename="React",
            collection_name=collection,
            metadata={"domain": "frontend"},
            file_type="text"
        )

        # Search with filter
        results = searcher.search_chunks(
            query="technology",
            collection_name=collection,
            metadata_filter={"domain": "devops"},
            threshold=0.0,
            limit=10
        )

        print(f"\n✅ Searched with metadata_filter={{'domain': 'devops'}}")
        print(f"   Found {len(results)} results")
        assert len(results) > 0, "Should find devops documents"
        assert all(r.metadata.get("domain") == "devops" for r in results), "All should be devops"

        print("✅ TEST PASSED")

    @pytest.mark.asyncio
    async def test_multiple_metadata_filters(self, rag_metadata_env):
        """Verify multi-field metadata filtering (AND logic)."""
        env = rag_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Multiple metadata field filtering (AND logic)")
        print("="*70)

        # Ingest with combinations
        doc_store.ingest_document(
            content="Backend REST API design patterns",
            filename="REST Guide",
            collection_name=collection,
            metadata={"domain": "backend", "content_type": "guide"},
            file_type="text"
        )

        doc_store.ingest_document(
            content="Backend microservices architecture",
            filename="Microservices",
            collection_name=collection,
            metadata={"domain": "backend", "content_type": "architecture"},
            file_type="text"
        )

        doc_store.ingest_document(
            content="Frontend React guide",
            filename="React Guide",
            collection_name=collection,
            metadata={"domain": "frontend", "content_type": "guide"},
            file_type="text"
        )

        # Search with multiple filters (AND logic)
        results = searcher.search_chunks(
            query="guide tutorial",
            collection_name=collection,
            metadata_filter={"domain": "backend", "content_type": "guide"},
            threshold=0.0,
            limit=10
        )

        print(f"\n✅ Searched with metadata_filter={{'domain': 'backend', 'content_type': 'guide'}}")
        print(f"   Found {len(results)} results")
        assert len(results) > 0, "Should find backend guides"
        for r in results:
            assert r.metadata.get("domain") == "backend"
            assert r.metadata.get("content_type") == "guide"

        print("✅ TEST PASSED")
