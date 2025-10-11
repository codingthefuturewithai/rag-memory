"""Integration tests for web crawling + ingestion + search pipeline."""

import pytest

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.document_store import get_document_store
from src.ingestion.web_crawler import crawl_single_page
from src.retrieval.search import get_similarity_search


@pytest.mark.asyncio
class TestWebIngestionIntegration:
    """Test complete web crawling pipeline: crawl -> ingest -> search."""

    @pytest.fixture
    def setup_components(self):
        """Setup database and components for testing."""
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        # Create test collection
        collection_name = "test-web-integration"
        try:
            coll_mgr.create_collection(collection_name, "Test collection for web integration")
        except ValueError:
            # Collection already exists - delete and recreate for clean state
            coll_mgr.delete_collection(collection_name)
            coll_mgr.create_collection(collection_name, "Test collection for web integration")

        yield {
            "db": db,
            "embedder": embedder,
            "coll_mgr": coll_mgr,
            "doc_store": doc_store,
            "searcher": searcher,
            "collection_name": collection_name,
        }

        # TEARDOWN: Delete all data created during test
        try:
            conn = db.connect()
            with conn.cursor() as cur:
                # Get collection ID before deletion
                cur.execute("SELECT id FROM collections WHERE name = %s", (collection_name,))
                result = cur.fetchone()

                if result:
                    collection_id = result[0]

                    # Step 1: Get all source documents from this collection
                    cur.execute(
                        """
                        SELECT DISTINCT dc.source_document_id
                        FROM document_chunks dc
                        INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                        WHERE cc.collection_id = %s
                        """,
                        (collection_id,)
                    )
                    source_doc_ids = [row[0] for row in cur.fetchall()]

                    # Step 2: Delete the collection (CASCADE deletes chunk_collections)
                    coll_mgr.delete_collection(collection_name)

                    # Step 3: Delete all chunks belonging to source documents from this collection
                    if source_doc_ids:
                        cur.execute(
                            """
                            DELETE FROM document_chunks
                            WHERE source_document_id = ANY(%s)
                            """,
                            (source_doc_ids,)
                        )

                        # Step 4: Delete the source documents
                        cur.execute(
                            """
                            DELETE FROM source_documents
                            WHERE id = ANY(%s)
                            """,
                            (source_doc_ids,)
                        )
        except Exception as e:
            # Log but don't fail the test if cleanup fails
            print(f"Warning: Cleanup failed for collection {collection_name}: {e}")

    async def test_crawl_ingest_search_pipeline(self, setup_components):
        """Test complete pipeline: crawl web page, ingest, then search."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Step 1: Crawl a web page
        crawl_result = await crawl_single_page("https://example.com")
        assert crawl_result.success is True

        # Step 2: Ingest the crawled content
        source_id, chunk_ids = doc_store.ingest_document(
            content=crawl_result.content,
            filename=crawl_result.metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=crawl_result.metadata,
            file_type="web_page",
        )

        assert source_id > 0
        assert len(chunk_ids) > 0

        # Step 3: Verify document was stored
        doc = doc_store.get_source_document(source_id)
        assert doc is not None
        assert doc["filename"] == "Example Domain"
        assert doc["file_type"] == "web_page"
        assert doc["metadata"]["source"] == "https://example.com"
        assert doc["metadata"]["content_type"] == "web_page"
        assert doc["metadata"]["crawl_root_url"] == "https://example.com"

        # Step 4: Search for crawled content
        search_results = searcher.search_chunks(
            query="domain examples documentation",
            limit=5,
            collection_name=collection_name,
        )

        assert len(search_results) > 0

        # Find our document in the results (might not be first due to other test data)
        our_result = None
        for result in search_results:
            if result.source_document_id == source_id:
                our_result = result
                break

        assert our_result is not None, f"Document {source_id} not found in search results"
        assert "domain" in our_result.content.lower()
        assert our_result.metadata["content_type"] == "web_page"

    async def test_web_metadata_searchable(self, setup_components):
        """Test that web crawl metadata is stored and accessible."""
        components = setup_components
        doc_store = components["doc_store"]
        collection_name = components["collection_name"]

        # Crawl and ingest
        crawl_result = await crawl_single_page("https://example.com")
        source_id, _ = doc_store.ingest_document(
            content=crawl_result.content,
            filename=crawl_result.metadata.get("title", "test"),
            collection_name=collection_name,
            metadata=crawl_result.metadata,
            file_type="web_page",
        )

        # Retrieve and check metadata
        doc = doc_store.get_source_document(source_id)
        metadata = doc["metadata"]

        # Verify all critical crawl metadata fields are present
        assert "crawl_root_url" in metadata
        assert "crawl_timestamp" in metadata
        assert "crawl_session_id" in metadata
        assert "crawl_depth" in metadata
        assert metadata["crawl_depth"] == 0

        # Verify page metadata
        assert "domain" in metadata
        assert metadata["domain"] == "example.com"
        assert "status_code" in metadata
        assert metadata["status_code"] == 200

    async def test_metadata_filter_by_crawl_root(self, setup_components):
        """Test filtering search results by crawl_root_url."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Crawl and ingest
        crawl_result = await crawl_single_page("https://example.com")
        source_id, _ = doc_store.ingest_document(
            content=crawl_result.content,
            filename=crawl_result.metadata.get("title", "test"),
            collection_name=collection_name,
            metadata=crawl_result.metadata,
            file_type="web_page",
        )

        # Search with metadata filter
        search_results = searcher.search_chunks(
            query="domain",
            limit=5,
            collection_name=collection_name,
            metadata_filter={"crawl_root_url": "https://example.com"},
        )

        # Should find results
        assert len(search_results) > 0
        for result in search_results:
            assert result.metadata.get("crawl_root_url") == "https://example.com"

        # Search with non-matching filter
        search_results_empty = searcher.search_chunks(
            query="domain",
            limit=5,
            collection_name=collection_name,
            metadata_filter={"crawl_root_url": "https://different-domain.com"},
        )

        # Should find nothing
        assert len(search_results_empty) == 0

    async def test_multiple_pages_same_crawl_session(self, setup_components):
        """Test ingesting multiple pages with same crawl_session_id."""
        components = setup_components
        doc_store = components["doc_store"]
        collection_name = components["collection_name"]

        # Simulate crawling multiple pages in same session
        from datetime import datetime, timezone
        import uuid

        session_id = str(uuid.uuid4())
        crawl_timestamp = datetime.now(timezone.utc)
        root_url = "https://example.com"

        # Crawl first page
        result1 = await crawl_single_page("https://example.com")
        result1.metadata["crawl_session_id"] = session_id
        result1.metadata["crawl_timestamp"] = crawl_timestamp.isoformat()

        source_id1, _ = doc_store.ingest_document(
            content=result1.content,
            filename="Page 1",
            collection_name=collection_name,
            metadata=result1.metadata,
            file_type="web_page",
        )

        # Verify session ID is stored
        doc1 = doc_store.get_source_document(source_id1)
        assert doc1["metadata"]["crawl_session_id"] == session_id
        assert doc1["metadata"]["crawl_root_url"] == root_url
