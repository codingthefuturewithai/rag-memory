"""Test delete_collection graph cleanup integration.

This test verifies that when delete_collection is called, episodes are
actually removed from Neo4j, not just from the RAG store.
"""

import os
import pytest
import asyncio
from src.core.database import Database
from src.core.collections import CollectionManager
from src.core.embeddings import EmbeddingGenerator
from src.ingestion.document_store import DocumentStore
from src.unified import GraphStore, UnifiedIngestionMediator
from src.mcp.tools import delete_collection_impl

pytestmark = [pytest.mark.anyio]


class TestDeleteCollectionGraphCleanup:
    """Test graph episode cleanup during collection deletion."""

    @pytest.fixture
    async def setup(self):
        """Set up database, collections, and graph store."""
        db = Database()
        coll_mgr = CollectionManager(db)
        embedder = EmbeddingGenerator()
        doc_store = DocumentStore(db, embedder, coll_mgr)

        # Try to initialize graph store
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "test-password")

        graph_store = None
        graph_available = False

        try:
            from graphiti_core import Graphiti

            graphiti = Graphiti(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
            )
            graph_store = GraphStore(graphiti)
            graph_available = True
        except Exception as e:
            print(f"⚠️  Graph store not available: {e}")

        # Create unified mediator
        mediator = None
        if graph_available:
            mediator = UnifiedIngestionMediator(db, embedder, coll_mgr, graph_store)

        yield {
            "db": db,
            "coll_mgr": coll_mgr,
            "embedder": embedder,
            "doc_store": doc_store,
            "graph_store": graph_store,
            "mediator": mediator,
            "graph_available": graph_available,
        }

        # Cleanup
        try:
            if graph_store:
                await graph_store.close()
            db.close()
        except Exception:
            pass

    async def test_graph_episodes_deleted_with_collection(self, setup):
        """Test that graph episodes are actually deleted when collection is deleted."""
        if not setup["graph_available"]:
            pytest.skip("Graph store not available")

        db = setup["db"]
        coll_mgr = setup["coll_mgr"]
        graph_store = setup["graph_store"]
        mediator = setup["mediator"]

        collection_name = f"graph_cleanup_test_{id(self)}"

        # Create collection
        coll_mgr.create_collection(collection_name, "Test for graph cleanup")

        # Ingest documents (creates episodes in graph)
        doc_ids = []
        for i in range(2):
            result = await mediator.ingest_text(
                content=f"Test document {i} with important AI content",
                collection_name=collection_name,
                document_title=f"Test_{i}",
                metadata={"test": True},
            )
            source_doc_id = result.get("source_document_id")
            if source_doc_id:
                doc_ids.append(source_doc_id)

        print(f"✅ Created {len(doc_ids)} documents: {doc_ids}")

        # Verify episodes exist in Neo4j
        episodes_before = []
        for doc_id in doc_ids:
            episode_name = f"doc_{doc_id}"
            episode_uuid = await graph_store.get_episode_uuid_by_name(episode_name)
            if episode_uuid:
                episodes_before.append(episode_name)
                print(f"✅ Found episode: {episode_name} (UUID: {episode_uuid})")

        assert (
            len(episodes_before) > 0
        ), f"Should have created episodes in graph, but found 0"

        # Delete collection with graph cleanup
        result = await delete_collection_impl(
            coll_mgr=coll_mgr,
            name=collection_name,
            confirm=True,
            graph_store=graph_store,
            db=db,
        )

        assert result["deleted"] is True
        print(f"✅ Collection deleted: {result['message']}")

        # Verify episodes are gone from Neo4j
        episodes_after = []
        for doc_id in doc_ids:
            episode_name = f"doc_{doc_id}"
            episode_uuid = await graph_store.get_episode_uuid_by_name(episode_name)
            if episode_uuid:
                episodes_after.append(episode_name)
                print(f"❌ FOUND ORPHANED EPISODE: {episode_name} (should be deleted!)")

        assert (
            len(episodes_after) == 0
        ), f"Episodes should be deleted from graph, but found: {episodes_after}"

        print(f"✅ Graph cleanup verified - all {len(episodes_before)} episodes deleted")
