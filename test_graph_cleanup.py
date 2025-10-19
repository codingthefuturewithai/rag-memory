"""
Test script to verify Graph episode cleanup works correctly.

Tests three use cases:
1. delete_document() - should delete both RAG document and Graph episode
2. update_document() - should delete old Graph episode when content changes
3. recrawl - should delete old Graph episodes before re-ingesting

Run this script with Neo4j running to verify Graph cleanup.
"""

import asyncio
import logging
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.ingestion.document_store import get_document_store
from src.unified.graph_store import GraphStore
from graphiti_core import Graphiti

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def verify_episode_exists(graph_store: GraphStore, episode_name: str) -> bool:
    """Check if an episode exists in the Graph."""
    uuid = await graph_store.get_episode_uuid_by_name(episode_name)
    return uuid is not None


async def test_delete_document_cleanup():
    """Test 1: delete_document() should clean up Graph episode."""
    logger.info("\n" + "="*80)
    logger.info("TEST 1: delete_document() Graph cleanup")
    logger.info("="*80)

    # Initialize components
    db = get_database()
    embedder = get_embedding_generator()
    coll_mgr = get_collection_manager(db)
    doc_store = get_document_store(db, embedder, coll_mgr)

    graphiti = Graphiti(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="graphiti-password"
    )
    await graphiti.build_indices_and_constraints()
    graph_store = GraphStore(graphiti)

    # Create test collection
    try:
        coll_mgr.create_collection("test-graph-cleanup", "Test Graph cleanup functionality")
    except ValueError:
        pass  # Collection already exists

    # Ingest a test document (this will create doc_X and episode doc_X)
    source_id, chunk_ids = doc_store.ingest_document(
        content="Test document for Graph cleanup. This is a test.",
        filename="test-cleanup.txt",
        collection_name="test-graph-cleanup",
        metadata={"test": "delete_cleanup"},
        file_type="text"
    )
    logger.info(f"✅ Created test document: doc_{source_id}")

    # Manually add to Graph (simulate unified ingestion)
    await graph_store.add_knowledge(
        content="Test document for Graph cleanup. This is a test.",
        source_document_id=source_id,
        metadata={"test": "delete_cleanup"}
    )
    episode_name = f"doc_{source_id}"
    logger.info(f"✅ Created Graph episode: {episode_name}")

    # Verify episode exists
    exists_before = await verify_episode_exists(graph_store, episode_name)
    logger.info(f"Episode exists before deletion: {exists_before}")
    assert exists_before, "Episode should exist before deletion"

    # Delete document (should delete both RAG and Graph)
    result = await doc_store.delete_document(source_id, graph_store=graph_store)
    logger.info(f"✅ Deleted document {source_id}")
    logger.info(f"   Graph episode deleted: {result['graph_episode_deleted']}")

    # Verify episode was deleted
    exists_after = await verify_episode_exists(graph_store, episode_name)
    logger.info(f"Episode exists after deletion: {exists_after}")

    await graph_store.close()

    if not exists_after and result['graph_episode_deleted']:
        logger.info("✅ TEST 1 PASSED: delete_document() successfully cleaned up Graph episode")
        return True
    else:
        logger.error("❌ TEST 1 FAILED: Graph episode still exists after deletion")
        return False


async def test_update_document_cleanup():
    """Test 2: update_document() should delete old Graph episode when content changes."""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: update_document() Graph cleanup")
    logger.info("="*80)

    # Initialize components
    db = get_database()
    embedder = get_embedding_generator()
    coll_mgr = get_collection_manager(db)
    doc_store = get_document_store(db, embedder, coll_mgr)

    graphiti = Graphiti(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="graphiti-password"
    )
    await graphiti.build_indices_and_constraints()
    graph_store = GraphStore(graphiti)

    # Create test collection
    try:
        coll_mgr.create_collection("test-graph-cleanup", "Test Graph cleanup functionality")
    except ValueError:
        pass  # Collection already exists

    # Ingest a test document
    source_id, chunk_ids = doc_store.ingest_document(
        content="Original content for update test.",
        filename="test-update.txt",
        collection_name="test-graph-cleanup",
        metadata={"test": "update_cleanup"},
        file_type="text"
    )
    logger.info(f"✅ Created test document: doc_{source_id}")

    # Manually add to Graph
    await graph_store.add_knowledge(
        content="Original content for update test.",
        source_document_id=source_id,
        metadata={"test": "update_cleanup"}
    )
    episode_name = f"doc_{source_id}"
    logger.info(f"✅ Created Graph episode: {episode_name}")

    # Verify episode exists
    exists_before = await verify_episode_exists(graph_store, episode_name)
    logger.info(f"Episode exists before update: {exists_before}")
    assert exists_before, "Episode should exist before update"

    # Update document content (should delete old episode)
    result = await doc_store.update_document(
        document_id=source_id,
        content="Updated content. This is completely different.",
        graph_store=graph_store
    )
    logger.info(f"✅ Updated document {source_id}")
    logger.info(f"   Graph episode deleted: {result['graph_episode_deleted']}")
    logger.info(f"   Old chunks: {result['old_chunk_count']}, New chunks: {result['new_chunk_count']}")

    # Verify old episode was deleted
    exists_after = await verify_episode_exists(graph_store, episode_name)
    logger.info(f"Episode exists after update: {exists_after}")

    # Clean up: delete the test document
    await doc_store.delete_document(source_id, graph_store=graph_store)

    await graph_store.close()

    if not exists_after and result['graph_episode_deleted']:
        logger.info("✅ TEST 2 PASSED: update_document() successfully cleaned up old Graph episode")
        return True
    else:
        logger.error("❌ TEST 2 FAILED: Old Graph episode still exists after update")
        return False


async def run_all_tests():
    """Run all Graph cleanup tests."""
    logger.info("\n" + "="*80)
    logger.info("GRAPH CLEANUP TEST SUITE")
    logger.info("="*80)
    logger.info("Testing Graph episode cleanup for delete and update operations")
    logger.info("="*80 + "\n")

    test_results = []

    # Test 1: delete_document cleanup
    try:
        result1 = await test_delete_document_cleanup()
        test_results.append(("delete_document", result1))
    except Exception as e:
        logger.error(f"❌ TEST 1 ERROR: {e}", exc_info=True)
        test_results.append(("delete_document", False))

    # Test 2: update_document cleanup
    try:
        result2 = await test_update_document_cleanup()
        test_results.append(("update_document", result2))
    except Exception as e:
        logger.error(f"❌ TEST 2 ERROR: {e}", exc_info=True)
        test_results.append(("update_document", False))

    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    all_passed = all(result for _, result in test_results)
    logger.info("="*80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("="*80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
