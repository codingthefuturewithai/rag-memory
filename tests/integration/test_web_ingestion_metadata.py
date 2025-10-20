"""
Phase 2: Verify Web Ingestion Metadata

Tests that web page crawling adds and maintains crawl metadata,
verifying that crawl_root_url, crawl_session_id, and crawl_depth are
properly set during web page ingestion.
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
async def web_metadata_env():
    """Setup web ingestion test environment."""
    db = Database()
    embedder = EmbeddingGenerator()
    collection_mgr = CollectionManager(db)

    test_collection = f"web_metadata_{uuid.uuid4().hex[:8]}"

    try:
        collection_mgr.delete_collection(test_collection)
    except Exception:
        pass

    collection_mgr.create_collection(
        name=test_collection,
        description="Web ingestion metadata test"
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


class TestWebIngestionMetadata:
    """Test web ingestion metadata."""

    @pytest.mark.asyncio
    async def test_crawl_metadata_set_on_ingestion(self, web_metadata_env):
        """Verify crawl metadata is set during web page ingestion."""
        env = web_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Crawl metadata set on ingestion")
        print("="*70)

        # Simulate web ingestion with crawl metadata
        # (In real scenario, this would come from web crawler)
        crawl_root_url = "https://example.com/docs"
        crawl_session_id = str(uuid.uuid4())
        crawl_depth = 0

        metadata = {
            "crawl_root_url": crawl_root_url,
            "crawl_session_id": crawl_session_id,
            "crawl_depth": crawl_depth
        }

        # Ingest as if from web crawler
        doc_store.ingest_document(
            content="This is a web page about API documentation",
            filename="API Documentation",
            collection_name=collection,
            metadata=metadata,
            file_type="text"
        )

        print(f"\n✅ Ingested web page with crawl metadata")
        print(f"   crawl_root_url: {crawl_root_url}")
        print(f"   crawl_session_id: {crawl_session_id}")
        print(f"   crawl_depth: {crawl_depth}")

        # Search and verify metadata
        results = searcher.search_chunks(
            query="API documentation",
            collection_name=collection,
            threshold=0.0,
            limit=5
        )

        print(f"\n✅ Searched - found {len(results)} results")
        assert len(results) > 0, "Should find web page content"

        result = results[0]
        print(f"   Result metadata: {result.metadata}")
        assert result.metadata.get("crawl_root_url") == crawl_root_url, \
            "crawl_root_url should persist"
        assert result.metadata.get("crawl_session_id") == crawl_session_id, \
            "crawl_session_id should persist"
        assert result.metadata.get("crawl_depth") == crawl_depth, \
            "crawl_depth should persist"

        print("✅ TEST PASSED: Crawl metadata persists")

    @pytest.mark.asyncio
    async def test_crawl_root_url_filtering(self, web_metadata_env):
        """Verify filtering by crawl_root_url works correctly."""
        env = web_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Crawl root URL filtering")
        print("="*70)

        # Ingest pages from two different root URLs
        session_1 = str(uuid.uuid4())
        session_2 = str(uuid.uuid4())

        doc_store.ingest_document(
            content="Documentation from site A",
            filename="Site A Page",
            collection_name=collection,
            metadata={
                "crawl_root_url": "https://site-a.com/docs",
                "crawl_session_id": session_1,
                "crawl_depth": 0
            },
            file_type="text"
        )

        doc_store.ingest_document(
            content="Documentation from site B",
            filename="Site B Page",
            collection_name=collection,
            metadata={
                "crawl_root_url": "https://site-b.com/docs",
                "crawl_session_id": session_2,
                "crawl_depth": 0
            },
            file_type="text"
        )

        print(f"\n✅ Ingested pages from two different root URLs")

        # Filter by site A root URL
        results = searcher.search_chunks(
            query="documentation",
            collection_name=collection,
            metadata_filter={"crawl_root_url": "https://site-a.com/docs"},
            threshold=0.0,
            limit=10
        )

        print(f"   Filtered to site-a.com: found {len(results)} results")
        assert len(results) > 0, "Should find site A pages"
        assert all(
            r.metadata.get("crawl_root_url") == "https://site-a.com/docs"
            for r in results
        ), "All results should be from site A"

        # Filter by site B root URL
        results = searcher.search_chunks(
            query="documentation",
            collection_name=collection,
            metadata_filter={"crawl_root_url": "https://site-b.com/docs"},
            threshold=0.0,
            limit=10
        )

        print(f"   Filtered to site-b.com: found {len(results)} results")
        assert len(results) > 0, "Should find site B pages"
        assert all(
            r.metadata.get("crawl_root_url") == "https://site-b.com/docs"
            for r in results
        ), "All results should be from site B"

        print("✅ TEST PASSED: Crawl root URL filtering works")

    @pytest.mark.asyncio
    async def test_crawl_depth_hierarchy(self, web_metadata_env):
        """Verify crawl depth correctly represents page hierarchy."""
        env = web_metadata_env
        doc_store = env["doc_store"]
        searcher = env["searcher"]
        collection = env["collection"]

        print("\n" + "="*70)
        print("TEST: Crawl depth hierarchy")
        print("="*70)

        # Simulate crawl with different depths
        session_id = str(uuid.uuid4())
        root_url = "https://docs.example.com"

        # Root page (depth 0)
        doc_store.ingest_document(
            content="Root documentation page overview",
            filename="Root",
            collection_name=collection,
            metadata={
                "crawl_root_url": root_url,
                "crawl_session_id": session_id,
                "crawl_depth": 0
            },
            file_type="text"
        )

        # First level pages (depth 1)
        doc_store.ingest_document(
            content="API reference guide for endpoints",
            filename="API Guide",
            collection_name=collection,
            metadata={
                "crawl_root_url": root_url,
                "crawl_session_id": session_id,
                "crawl_depth": 1
            },
            file_type="text"
        )

        # Second level pages (depth 2)
        doc_store.ingest_document(
            content="Authentication details and examples",
            filename="Auth Details",
            collection_name=collection,
            metadata={
                "crawl_root_url": root_url,
                "crawl_session_id": session_id,
                "crawl_depth": 2
            },
            file_type="text"
        )

        print(f"\n✅ Ingested pages at depths 0, 1, and 2")

        # Filter by depth 0 (only root pages)
        results = searcher.search_chunks(
            query="documentation",
            collection_name=collection,
            metadata_filter={"crawl_depth": 0},
            threshold=0.0,
            limit=10
        )

        print(f"   Depth 0: found {len(results)} results")
        assert len(results) > 0, "Should find depth 0 pages"
        assert all(r.metadata.get("crawl_depth") == 0 for r in results), \
            "All results should be at depth 0"

        # Filter by depth 1
        results = searcher.search_chunks(
            query="documentation",
            collection_name=collection,
            metadata_filter={"crawl_depth": 1},
            threshold=0.0,
            limit=10
        )

        print(f"   Depth 1: found {len(results)} results")
        assert len(results) > 0, "Should find depth 1 pages"
        assert all(r.metadata.get("crawl_depth") == 1 for r in results), \
            "All results should be at depth 1"

        # Filter by depth 2
        results = searcher.search_chunks(
            query="documentation",
            collection_name=collection,
            metadata_filter={"crawl_depth": 2},
            threshold=0.0,
            limit=10
        )

        print(f"   Depth 2: found {len(results)} results")
        assert len(results) > 0, "Should find depth 2 pages"
        assert all(r.metadata.get("crawl_depth") == 2 for r in results), \
            "All results should be at depth 2"

        print("✅ TEST PASSED: Crawl depth hierarchy works")
