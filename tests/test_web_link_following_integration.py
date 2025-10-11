"""Integration tests for web crawler link following + ingestion + search."""

import pytest

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.document_store import get_document_store
from src.ingestion.web_crawler import WebCrawler
from src.retrieval.search import get_similarity_search


@pytest.mark.asyncio
class TestWebLinkFollowingIntegration:
    """Test complete link following pipeline: crawl (multi-page) -> ingest -> search."""

    @pytest.fixture
    def setup_components(self):
        """Setup database and components for testing with guaranteed teardown."""
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        # Create test collection
        collection_name = "test-link-following"
        try:
            coll_mgr.create_collection(collection_name, "Test collection for link following")
        except ValueError:
            # Collection already exists - delete and recreate for clean state
            coll_mgr.delete_collection(collection_name)
            coll_mgr.create_collection(collection_name, "Test collection for link following")

        yield {
            "db": db,
            "embedder": embedder,
            "coll_mgr": coll_mgr,
            "doc_store": doc_store,
            "searcher": searcher,
            "collection_name": collection_name,
        }

        # TEARDOWN: Delete all data created during test
        # This MUST run even if test fails to prevent database pollution
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

    async def test_crawl_depth_0_ingest_search(self, setup_components):
        """Test crawling single page (depth=0), ingesting, and searching."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Crawl with depth=0 (single page)
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=0)

        assert len(results) == 1
        assert results[0].success is True

        # Ingest the page
        source_id, chunk_ids = doc_store.ingest_document(
            content=results[0].content,
            filename=results[0].metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=results[0].metadata,
            file_type="web_page",
        )

        assert source_id > 0
        assert len(chunk_ids) > 0

        # Search for content
        search_results = searcher.search_chunks(
            query="domain examples",
            limit=5,
            collection_name=collection_name,
        )

        assert len(search_results) > 0
        # Find our document
        found = any(r.source_document_id == source_id for r in search_results)
        assert found, f"Document {source_id} not found in search results"

    async def test_crawl_depth_1_ingest_all_pages(self, setup_components):
        """Test crawling with depth=1, ingesting all pages, and searching."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Crawl with depth=1 (follow direct links)
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Should crawl at least the starting page
        assert len(results) >= 1
        successful_results = [r for r in results if r.success]
        assert len(successful_results) >= 1

        # Ingest all successfully crawled pages
        source_ids = []
        total_chunks = 0
        for result in successful_results:
            source_id, chunk_ids = doc_store.ingest_document(
                content=result.content,
                filename=result.metadata.get("title", result.url),
                collection_name=collection_name,
                metadata=result.metadata,
                file_type="web_page",
            )
            source_ids.append(source_id)
            total_chunks += len(chunk_ids)

        assert len(source_ids) == len(successful_results)
        assert total_chunks > 0

        # Verify all documents are in the collection
        docs = doc_store.list_source_documents(collection_name)
        doc_ids = [d["id"] for d in docs]
        for source_id in source_ids:
            assert source_id in doc_ids

        # Search and verify we can find content from any page
        search_results = searcher.search_chunks(
            query="example domain",
            limit=10,
            collection_name=collection_name,
        )

        assert len(search_results) > 0

    async def test_crawl_session_metadata_searchable(self, setup_components):
        """Test that crawl session metadata is searchable."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Crawl with depth=1
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Get session ID from first result
        assert len(results) >= 1
        session_id = results[0].metadata["crawl_session_id"]

        # Ingest all pages
        for result in results:
            if result.success:
                doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )

        # Search with metadata filter for this crawl session
        search_results = searcher.search_chunks(
            query="domain",
            limit=10,
            collection_name=collection_name,
            metadata_filter={"crawl_session_id": session_id},
        )

        # Should find results from this session
        assert len(search_results) > 0
        for result in search_results:
            assert result.metadata.get("crawl_session_id") == session_id

    async def test_filter_by_crawl_depth(self, setup_components):
        """Test filtering search results by crawl_depth."""
        components = setup_components
        doc_store = components["doc_store"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Crawl with depth=1
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Ingest all pages
        depth_0_ids = []
        depth_1_ids = []
        for result in results:
            if result.success:
                source_id, _ = doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )
                if result.metadata["crawl_depth"] == 0:
                    depth_0_ids.append(source_id)
                elif result.metadata["crawl_depth"] == 1:
                    depth_1_ids.append(source_id)

        # Search for depth=0 pages only (starting page)
        search_depth_0 = searcher.search_chunks(
            query="domain",
            limit=10,
            collection_name=collection_name,
            metadata_filter={"crawl_depth": 0},
        )

        assert len(search_depth_0) > 0
        for result in search_depth_0:
            assert result.metadata.get("crawl_depth") == 0

        # If we have depth=1 pages, test filtering for them
        if depth_1_ids:
            search_depth_1 = searcher.search_chunks(
                query="domain",
                limit=10,
                collection_name=collection_name,
                metadata_filter={"crawl_depth": 1},
            )

            assert len(search_depth_1) > 0
            for result in search_depth_1:
                assert result.metadata.get("crawl_depth") == 1

    async def test_parent_url_metadata(self, setup_components):
        """Test that parent_url metadata is preserved for linked pages."""
        components = setup_components
        doc_store = components["doc_store"]
        collection_name = components["collection_name"]

        # Crawl with depth=1
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=1)

        # Ingest and check parent_url for depth > 0 pages
        for result in results:
            if result.success and result.metadata["crawl_depth"] > 0:
                source_id, _ = doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )

                # Retrieve and check metadata
                doc = doc_store.get_source_document(source_id)
                assert "parent_url" in doc["metadata"]
                assert doc["metadata"]["parent_url"] == "https://example.com"
