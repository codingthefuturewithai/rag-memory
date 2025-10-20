"""
Phase 5: Cross-Store Metadata Consistency

Tests that metadata flows through and is accessible from both RAG and Graph stores,
ensuring they remain in sync and provide consistent views of ingested content.
"""

import pytest
import pytest_asyncio
import os
import uuid
from datetime import datetime, timezone
from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.unified.mediator import UnifiedIngestionMediator
from src.unified.graph_store import GraphStore
from src.search import get_similarity_search
from graphiti_core import Graphiti


@pytest_asyncio.fixture
async def cross_store_env():
    """Setup environment with both RAG and Graph stores."""
    # Initialize RAG layer
    db = Database()
    embedder = EmbeddingGenerator()
    collection_mgr = CollectionManager(db)

    # Initialize Graph layer
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "test-password")

    graphiti = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    graph_store = GraphStore(graphiti=graphiti)

    # Create unified mediator
    mediator = UnifiedIngestionMediator(db, embedder, collection_mgr, graph_store)

    # Create test collection
    test_collection = f"cross_store_{uuid.uuid4().hex[:8]}"

    try:
        collection_mgr.delete_collection(test_collection)
    except Exception:
        pass

    collection_mgr.create_collection(
        name=test_collection,
        description="Cross-store consistency test"
    )

    searcher = get_similarity_search(db, embedder, collection_mgr)

    yield {
        "mediator": mediator,
        "searcher": searcher,
        "collection_mgr": collection_mgr,
        "graphiti": graphiti,
        "collection": test_collection
    }

    # Cleanup
    try:
        collection_mgr.delete_collection(test_collection)
        await graphiti.driver.execute_query("MATCH (e:Episodic) DETACH DELETE e")
        await graph_store.close()
    except Exception:
        pass


class TestMetadataConsistency:
    """Test metadata consistency across RAG and Graph stores."""

    @pytest.mark.asyncio
    async def test_rag_metadata_persists(self, cross_store_env):
        """
        TEST: Metadata persists in RAG store through ingestion.

        Scenario:
        1. Ingest via mediator with custom metadata
        2. Verify metadata appears in RAG search results
        """
        env = cross_store_env
        mediator = env["mediator"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: RAG metadata persists through ingestion")
        print("="*70)

        # Ingest with rich metadata
        metadata = {
            "domain": "backend",
            "content_type": "api-docs",
            "version": "2.0"
        }

        result = await mediator.ingest_text(
            content="REST API endpoints documentation",
            collection_name=collection,
            document_title="API Reference",
            metadata=metadata
        )

        source_id = result["source_document_id"]
        print(f"\n✅ Ingested with metadata via mediator")
        print(f"   Source ID: {source_id}")

        # Verify in RAG store
        rag_results = searcher.search_chunks(
            query="API endpoints",
            collection_name=collection,
            threshold=0.0,
            limit=5
        )

        print(f"\n✅ RAG store search found {len(rag_results)} results")
        assert len(rag_results) > 0, "Should find content in RAG"

        rag_result = rag_results[0]
        print(f"   Metadata keys: {list(rag_result.metadata.keys())}")
        print(f"   Domain: {rag_result.metadata.get('domain')}")
        print(f"   Content type: {rag_result.metadata.get('content_type')}")
        print(f"   Version: {rag_result.metadata.get('version')}")

        assert rag_result.metadata.get("domain") == "backend", "Domain should persist"
        assert rag_result.metadata.get("content_type") == "api-docs", "Content type should persist"
        assert rag_result.metadata.get("version") == "2.0", "Version should persist"

        print("\n✅ TEST PASSED: RAG metadata persists")

    @pytest.mark.asyncio
    async def test_multiple_ingestions_maintain_isolation(self, cross_store_env):
        """
        TEST: Multiple documents maintain isolation in metadata.

        Scenario:
        1. Ingest 3 different documents
        2. Verify each has correct metadata
        3. Verify no cross-contamination
        """
        env = cross_store_env
        mediator = env["mediator"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Multiple documents maintain metadata isolation")
        print("="*70)

        # Ingest 3 documents with different metadata
        docs = [
            {
                "title": "Python Guide",
                "content": "Python is a programming language",
                "metadata": {"language": "python", "level": "beginner"}
            },
            {
                "title": "JavaScript Guide",
                "content": "JavaScript runs in browsers",
                "metadata": {"language": "javascript", "level": "intermediate"}
            },
            {
                "title": "Rust Guide",
                "content": "Rust provides memory safety",
                "metadata": {"language": "rust", "level": "advanced"}
            }
        ]

        for doc in docs:
            await mediator.ingest_text(
                content=doc["content"],
                collection_name=collection,
                document_title=doc["title"],
                metadata=doc["metadata"]
            )

        print(f"\n✅ Ingested {len(docs)} documents")

        # Search for each and verify metadata
        for doc in docs:
            results = searcher.search_chunks(
                query=doc["metadata"]["language"],
                collection_name=collection,
                metadata_filter={"language": doc["metadata"]["language"]},
                threshold=0.0,
                limit=5
            )

            print(f"\n   Searching for {doc['metadata']['language']}...")
            assert len(results) > 0, f"Should find {doc['metadata']['language']} content"

            # Verify no cross-contamination
            for result in results:
                assert result.metadata.get("language") == doc["metadata"]["language"], \
                    f"Should only find {doc['metadata']['language']}"
                assert result.metadata.get("level") == doc["metadata"]["level"], \
                    f"Level should be {doc['metadata']['level']}"
                print(f"   ✓ Found correct: {result.metadata.get('language')} - {result.metadata.get('level')}")

        print("\n✅ TEST PASSED: Metadata isolation maintained")
