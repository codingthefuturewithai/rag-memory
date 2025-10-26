"""Integration tests for the recrawl command."""

import pytest

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.document_store import get_document_store
from src.ingestion.web_crawler import WebCrawler
from src.retrieval.search import get_similarity_search


@pytest.mark.asyncio
class TestRecrawlCommand:
    """Test recrawl functionality with proper teardown."""

    @pytest.fixture
    def setup_components(self):
        """Setup database and components for testing with guaranteed teardown."""
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        # Create test collection
        collection_name = "test-recrawl"
        try:
            coll_mgr.create_collection(
                collection_name,
                "Test collection for recrawl",
                domain="testing",
                domain_scope="Test collection for web recrawling functionality",
                metadata_schema={"custom": {}, "system": []}
            )
        except ValueError:
            # Collection already exists - delete and recreate for clean state
            coll_mgr.delete_collection(collection_name)
            coll_mgr.create_collection(
                collection_name,
                "Test collection for recrawl",
                domain="testing",
                domain_scope="Test collection for web recrawling functionality",
                metadata_schema={"custom": {}, "system": []}
            )

        yield {
            "db": db,
            "embedder": embedder,
            "coll_mgr": coll_mgr,
            "doc_store": doc_store,
            "searcher": searcher,
            "collection_name": collection_name,
        }

        # Cleanup is handled by the global cleanup_after_each_test fixture in conftest.py
        # which clears ALL data from both PostgreSQL and Neo4j after every test

    async def test_recrawl_deletes_only_matching_crawl_root_url(self, setup_components):
        """Test that recrawl only deletes documents matching the specific crawl_root_url."""
        components = setup_components
        doc_store = components["doc_store"]
        db = components["db"]
        collection_name = components["collection_name"]

        # Step 1: Ingest two different crawl sessions into the same collection
        crawler = WebCrawler(headless=True)

        # Crawl example.com (this will be the one we recrawl)
        results_example = await crawler.crawl_with_depth("https://example.com", max_depth=0)
        assert results_example[0].success is True

        source_id_example, chunk_ids_example = doc_store.ingest_document(
            content=results_example[0].content,
            filename=results_example[0].metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=results_example[0].metadata,
            file_type="web_page",
        )

        # Crawl httpbin.org (different root URL, should NOT be affected by recrawl)
        results_httpbin = await crawler.crawl_with_depth("https://httpbin.org", max_depth=0)
        assert results_httpbin[0].success is True

        source_id_httpbin, chunk_ids_httpbin = doc_store.ingest_document(
            content=results_httpbin[0].content,
            filename=results_httpbin[0].metadata.get("title", "https://httpbin.org"),
            collection_name=collection_name,
            metadata=results_httpbin[0].metadata,
            file_type="web_page",
        )

        # Verify both documents exist
        result = doc_store.list_source_documents(collection_name)
        docs = result['documents']
        assert len(docs) == 2

        # Step 2: Simulate recrawl by deleting only documents matching https://example.com
        conn = db.connect()
        with conn.cursor() as cur:
            # Find documents with crawl_root_url = https://example.com
            cur.execute(
                """
                SELECT id, filename, metadata
                FROM source_documents
                WHERE metadata->>'crawl_root_url' = %s
                """,
                ("https://example.com",)
            )
            matching_docs = cur.fetchall()

            assert len(matching_docs) == 1
            assert matching_docs[0][0] == source_id_example

            # Delete the matching document and its chunks
            for doc_id, filename, metadata in matching_docs:
                cur.execute(
                    "DELETE FROM document_chunks WHERE source_document_id = %s",
                    (doc_id,)
                )
                cur.execute(
                    "DELETE FROM source_documents WHERE id = %s",
                    (doc_id,)
                )

        # Step 3: Verify only example.com was deleted, httpbin.org remains
        result = doc_store.list_source_documents(collection_name)
        docs_after = result['documents']
        assert len(docs_after) == 1
        assert docs_after[0]["id"] == source_id_httpbin

        # Verify httpbin.org chunks are intact
        httpbin_chunks = doc_store.get_document_chunks(source_id_httpbin)
        assert len(httpbin_chunks) == len(chunk_ids_httpbin)

    async def test_recrawl_handles_no_existing_documents(self, setup_components):
        """Test that recrawl works correctly when no existing documents match."""
        components = setup_components
        doc_store = components["doc_store"]
        db = components["db"]
        collection_name = components["collection_name"]

        # Try to find documents with a URL that doesn't exist
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, metadata
                FROM source_documents
                WHERE metadata->>'crawl_root_url' = %s
                """,
                ("https://nonexistent-url.com",)
            )
            existing_docs = cur.fetchall()

        # Should find no documents
        assert len(existing_docs) == 0

        # Proceed with crawl (would be done in recrawl command)
        crawler = WebCrawler(headless=True)
        results = await crawler.crawl_with_depth("https://example.com", max_depth=0)
        assert results[0].success is True

        source_id, chunk_ids = doc_store.ingest_document(
            content=results[0].content,
            filename=results[0].metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=results[0].metadata,
            file_type="web_page",
        )

        assert source_id > 0
        assert len(chunk_ids) > 0

    async def test_recrawl_replaces_old_content_with_new(self, setup_components):
        """Test that recrawl deletes old content and replaces with new crawl."""
        components = setup_components
        doc_store = components["doc_store"]
        db = components["db"]
        searcher = components["searcher"]
        collection_name = components["collection_name"]

        # Step 1: Initial crawl and ingest
        crawler = WebCrawler(headless=True)
        results_old = await crawler.crawl_with_depth("https://example.com", max_depth=0)
        assert results_old[0].success is True

        old_session_id = results_old[0].metadata["crawl_session_id"]

        source_id_old, chunk_ids_old = doc_store.ingest_document(
            content=results_old[0].content,
            filename=results_old[0].metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=results_old[0].metadata,
            file_type="web_page",
        )

        # Verify old content is searchable
        search_results_old = searcher.search_chunks(
            query="example domain",
            limit=5,
            collection_name=collection_name,
            metadata_filter={"crawl_session_id": old_session_id},
        )
        assert len(search_results_old) > 0

        # Step 2: Simulate recrawl - delete old documents
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM source_documents
                WHERE metadata->>'crawl_root_url' = %s
                """,
                ("https://example.com",)
            )
            old_doc_ids = [row[0] for row in cur.fetchall()]

            for doc_id in old_doc_ids:
                cur.execute("DELETE FROM document_chunks WHERE source_document_id = %s", (doc_id,))
                cur.execute("DELETE FROM source_documents WHERE id = %s", (doc_id,))

        # Verify old content is deleted
        result = doc_store.list_source_documents(collection_name)
        docs_after_delete = result['documents']
        assert len(docs_after_delete) == 0

        # Step 3: Re-crawl with new session
        results_new = await crawler.crawl_with_depth("https://example.com", max_depth=0)
        assert results_new[0].success is True

        new_session_id = results_new[0].metadata["crawl_session_id"]
        assert new_session_id != old_session_id  # Should be different session

        source_id_new, chunk_ids_new = doc_store.ingest_document(
            content=results_new[0].content,
            filename=results_new[0].metadata.get("title", "https://example.com"),
            collection_name=collection_name,
            metadata=results_new[0].metadata,
            file_type="web_page",
        )

        # Verify new content is searchable
        search_results_new = searcher.search_chunks(
            query="example domain",
            limit=5,
            collection_name=collection_name,
            metadata_filter={"crawl_session_id": new_session_id},
        )
        assert len(search_results_new) > 0

        # Verify old session is no longer searchable
        search_results_old_session = searcher.search_chunks(
            query="example domain",
            limit=5,
            collection_name=collection_name,
            metadata_filter={"crawl_session_id": old_session_id},
        )
        assert len(search_results_old_session) == 0

    async def test_recrawl_with_link_following(self, setup_components):
        """Test that recrawl works with multi-page crawls (link following)."""
        components = setup_components
        doc_store = components["doc_store"]
        db = components["db"]
        collection_name = components["collection_name"]

        # Step 1: Initial crawl with depth=1
        crawler = WebCrawler(headless=True)
        results_old = await crawler.crawl_with_depth("https://example.com", max_depth=1)
        old_page_count = len([r for r in results_old if r.success])

        # Ingest all pages
        old_source_ids = []
        for result in results_old:
            if result.success:
                source_id, chunk_ids = doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )
                old_source_ids.append(source_id)

        # Verify all pages are in the collection
        result = doc_store.list_source_documents(collection_name)
        docs_old = result['documents']
        assert len(docs_old) == old_page_count

        # Step 2: Simulate recrawl - delete all pages with matching crawl_root_url
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM source_documents
                WHERE metadata->>'crawl_root_url' = %s
                """,
                ("https://example.com",)
            )
            matching_doc_ids = [row[0] for row in cur.fetchall()]

            # Should match all old pages (all have same crawl_root_url)
            assert len(matching_doc_ids) == old_page_count

            # Delete them
            for doc_id in matching_doc_ids:
                cur.execute("DELETE FROM document_chunks WHERE source_document_id = %s", (doc_id,))
                cur.execute("DELETE FROM source_documents WHERE id = %s", (doc_id,))

        # Verify all pages are deleted
        result = doc_store.list_source_documents(collection_name)
        docs_after_delete = result['documents']
        assert len(docs_after_delete) == 0

        # Step 3: Re-crawl with new session
        results_new = await crawler.crawl_with_depth("https://example.com", max_depth=1)
        new_page_count = len([r for r in results_new if r.success])

        # Ingest all new pages
        new_source_ids = []
        for result in results_new:
            if result.success:
                source_id, chunk_ids = doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )
                new_source_ids.append(source_id)

        # Verify new pages are in the collection
        result = doc_store.list_source_documents(collection_name)
        docs_new = result['documents']
        assert len(docs_new) == new_page_count
        assert len(docs_new) >= 1  # At least the starting page

    async def test_recrawl_metadata_filter_query(self, setup_components):
        """Test that the metadata JSONB query correctly filters by crawl_root_url."""
        components = setup_components
        doc_store = components["doc_store"]
        db = components["db"]
        collection_name = components["collection_name"]

        # Ingest multiple pages with different crawl_root_urls
        crawler = WebCrawler(headless=True)

        urls = [
            "https://example.com",
            "https://httpbin.org",
            "https://www.iana.org",
        ]

        for url in urls:
            results = await crawler.crawl_with_depth(url, max_depth=0)
            if results[0].success:
                doc_store.ingest_document(
                    content=results[0].content,
                    filename=results[0].metadata.get("title", url),
                    collection_name=collection_name,
                    metadata=results[0].metadata,
                    file_type="web_page",
                )

        # Test metadata query for each URL
        conn = db.connect()
        for url in urls:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, metadata->>'crawl_root_url'
                    FROM source_documents
                    WHERE metadata->>'crawl_root_url' = %s
                    """,
                    (url,)
                )
                results = cur.fetchall()

                # Should find exactly one document for each URL
                assert len(results) == 1
                assert results[0][1] == url
