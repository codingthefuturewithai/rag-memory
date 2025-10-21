"""Tests for document chunking functionality."""

import tempfile
from pathlib import Path

import pytest

from src.chunking import ChunkingConfig, DocumentChunker, get_document_chunker
from src.collections import get_collection_manager
from src.database import get_database
from src.document_store import get_document_store
from src.embeddings import get_embedding_generator
from src.search import get_similarity_search


@pytest.fixture
def db():
    """Get database instance."""
    return get_database()


@pytest.fixture
def embedder():
    """Get embedding generator."""
    return get_embedding_generator()


@pytest.fixture
def coll_mgr(db):
    """Get collection manager."""
    return get_collection_manager(db)


@pytest.fixture
def doc_store(db, embedder, coll_mgr):
    """Get document store."""
    return get_document_store(db, embedder, coll_mgr)


@pytest.fixture
def searcher(db, embedder, coll_mgr):
    """Get similarity searcher."""
    return get_similarity_search(db, embedder, coll_mgr)


@pytest.fixture
def test_collection(coll_mgr, db):
    """Create a test collection and ensure cleanup after test."""
    collection_name = "test_chunking"

    # Create collection
    try:
        coll_mgr.create_collection(collection_name, "Test collection for chunking")
    except ValueError:
        # Collection already exists - delete and recreate for clean state
        coll_mgr.delete_collection(collection_name)
        coll_mgr.create_collection(collection_name, "Test collection for chunking")

    yield collection_name

    # TEARDOWN: Delete all data created during test
    # The CASCADE relationships will handle cleanup in this order:
    # 1. Delete collection -> CASCADE deletes chunk_collections
    # 2. Delete orphaned chunks -> CASCADE from source_documents handles this
    # 3. Delete orphaned source documents
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            # Get collection ID before deletion
            cur.execute("SELECT id FROM collections WHERE name = %s", (collection_name,))
            result = cur.fetchone()

            if result:
                collection_id = result[0]

                # Step 1: Get all chunks in this collection before we delete anything
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
                # This may delete chunks used by other collections, but that's OK for isolated tests
                if source_doc_ids:
                    cur.execute(
                        """
                        DELETE FROM document_chunks
                        WHERE source_document_id = ANY(%s)
                        """,
                        (source_doc_ids,)
                    )

                    # Step 4: Delete the source documents (now that their chunks are gone)
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


class TestDocumentChunker:
    """Tests for DocumentChunker class."""

    def test_default_config(self):
        """Test default chunking configuration."""
        chunker = DocumentChunker()
        assert chunker.config.chunk_size == 1000
        assert chunker.config.chunk_overlap == 200
        assert chunker.config.separators is not None

    def test_custom_config(self):
        """Test custom chunking configuration."""
        config = ChunkingConfig(chunk_size=500, chunk_overlap=50)
        chunker = DocumentChunker(config)
        assert chunker.config.chunk_size == 500
        assert chunker.config.chunk_overlap == 50

    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        chunker = DocumentChunker()
        chunks = chunker.chunk_text("")
        assert chunks == []

    def test_chunk_text_small(self):
        """Test chunking small text (should produce 1 chunk)."""
        chunker = DocumentChunker()
        text = "This is a small document."
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].page_content == text
        assert chunks[0].metadata["chunk_index"] == 0
        assert chunks[0].metadata["total_chunks"] == 1

    def test_chunk_text_large(self):
        """Test chunking large text (should produce multiple chunks)."""
        chunker = DocumentChunker(ChunkingConfig(chunk_size=100, chunk_overlap=20))
        text = " ".join([f"Sentence {i}." for i in range(100)])
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["chunk_index"] == i
            assert chunk.metadata["total_chunks"] == len(chunks)

    def test_chunk_metadata(self):
        """Test that custom metadata is preserved."""
        chunker = DocumentChunker()
        text = "Test document"
        metadata = {"author": "Test Author", "category": "test"}
        chunks = chunker.chunk_text(text, metadata)
        assert chunks[0].metadata["author"] == "Test Author"
        assert chunks[0].metadata["category"] == "test"

    def test_get_stats(self):
        """Test chunk statistics calculation."""
        chunker = DocumentChunker(ChunkingConfig(chunk_size=100, chunk_overlap=20))
        text = " ".join([f"Sentence {i}." for i in range(50)])
        chunks = chunker.chunk_text(text)
        stats = chunker.get_stats(chunks)

        assert stats["num_chunks"] == len(chunks)
        assert stats["total_chars"] > 0
        assert stats["avg_chunk_size"] > 0
        assert stats["min_chunk_size"] > 0
        assert stats["max_chunk_size"] > 0

    def test_get_stats_empty(self):
        """Test statistics for empty chunks."""
        chunker = DocumentChunker()
        stats = chunker.get_stats([])
        assert stats["num_chunks"] == 0
        assert stats["total_chars"] == 0


class TestDocumentStore:
    """Tests for DocumentStore class."""

    def test_ingest_document(self, doc_store, test_collection):
        """Test ingesting a document with chunking."""
        content = "This is a test document. " * 100  # Create larger text
        filename = "test.txt"

        source_id, chunk_ids = doc_store.ingest_document(
            content=content,
            filename=filename,
            collection_name=test_collection,
            metadata={"test": True},
        )

        assert source_id is not None
        assert len(chunk_ids) > 0

    def test_ingest_file(self, doc_store, test_collection):
        """Test ingesting a file with chunking."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is test content. " * 100)
            temp_path = f.name

        try:
            source_id, chunk_ids = doc_store.ingest_file(
                temp_path, test_collection, metadata={"source": "test"}
            )

            assert source_id is not None
            assert len(chunk_ids) > 0

            # Verify document was stored
            doc = doc_store.get_source_document(source_id)
            assert doc is not None
            assert doc["filename"] == Path(temp_path).name
            assert doc["metadata"]["source"] == "test"
        finally:
            Path(temp_path).unlink()

    def test_get_source_document(self, doc_store, test_collection):
        """Test retrieving source document."""
        content = "Test document content"
        source_id, _ = doc_store.ingest_document(
            content=content,
            filename="test.txt",
            collection_name=test_collection,
        )

        doc = doc_store.get_source_document(source_id)
        assert doc is not None
        assert doc["id"] == source_id
        assert doc["content"] == content
        assert doc["filename"] == "test.txt"

    def test_get_document_chunks(self, doc_store, test_collection):
        """Test retrieving document chunks."""
        content = "Test content. " * 200  # Force multiple chunks
        source_id, chunk_ids = doc_store.ingest_document(
            content=content,
            filename="test.txt",
            collection_name=test_collection,
        )

        chunks = doc_store.get_document_chunks(source_id)
        assert len(chunks) == len(chunk_ids)
        assert all(c["id"] in chunk_ids for c in chunks)

        # Verify chunks are ordered by index
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i

    def test_list_source_documents(self, doc_store, test_collection):
        """Test listing source documents."""
        # Get initial count
        result = doc_store.list_source_documents(test_collection)
        initial_docs = result['documents']
        initial_count = len(initial_docs)

        # Ingest some documents
        source_ids = []
        for i in range(3):
            source_id, _ = doc_store.ingest_document(
                content=f"Document {i} content",
                filename=f"doc{i}.txt",
                collection_name=test_collection,
            )
            source_ids.append(source_id)

        # List documents in specific collection - should be initial + 3
        result = doc_store.list_source_documents(test_collection)
        coll_docs = result['documents']
        assert len(coll_docs) == initial_count + 3

        # Verify our documents are in the list
        coll_doc_ids = [d["id"] for d in coll_docs]
        for source_id in source_ids:
            assert source_id in coll_doc_ids


class TestChunkSearch:
    """Tests for chunk-based similarity search."""

    def test_search_chunks_basic(self, doc_store, searcher, test_collection):
        """Test basic chunk search."""
        # Ingest a document with known content
        content = (
            "PostgreSQL is a powerful database. "
            "Python is a great programming language. "
            "Machine learning is transforming AI. "
        ) * 50  # Make it large enough to chunk

        doc_store.ingest_document(
            content=content,
            filename="test_search.txt",
            collection_name=test_collection,
        )

        # Search for database-related content
        results = searcher.search_chunks(
            "What database systems are powerful?",
            limit=5,
            collection_name=test_collection,
        )

        assert len(results) > 0
        assert results[0].similarity > 0.5  # Should have decent similarity
        assert "PostgreSQL" in results[0].content or "database" in results[0].content

    def test_search_chunks_with_source(self, doc_store, searcher, test_collection):
        """Test chunk search with source document included."""
        content = "Test document for source retrieval. " * 100
        filename = "source_test.txt"

        doc_store.ingest_document(
            content=content,
            filename=filename,
            collection_name=test_collection,
        )

        results = searcher.search_chunks(
            "document retrieval",
            limit=3,
            collection_name=test_collection,
            include_source=True,
        )

        assert len(results) > 0
        assert results[0].source_content is not None
        assert results[0].source_filename == filename

    def test_search_chunks_threshold(self, doc_store, searcher, test_collection):
        """Test chunk search with similarity threshold."""
        content = "Specific technical content about databases. " * 50

        doc_store.ingest_document(
            content=content,
            filename="threshold_test.txt",
            collection_name=test_collection,
        )

        # Search with high threshold
        results_high = searcher.search_chunks(
            "technical databases",
            limit=10,
            threshold=0.7,
            collection_name=test_collection,
        )

        # Search with low threshold
        results_low = searcher.search_chunks(
            "technical databases",
            limit=10,
            threshold=0.3,
            collection_name=test_collection,
        )

        # Low threshold should return more or equal results
        assert len(results_low) >= len(results_high)

        # All results should meet threshold
        for result in results_high:
            assert result.similarity >= 0.7

    def test_search_chunks_metadata(self, doc_store, searcher, test_collection):
        """Test that chunk metadata is preserved."""
        content = "Document with metadata. " * 100
        metadata = {"category": "test", "priority": "high"}

        doc_store.ingest_document(
            content=content,
            filename="metadata_test.txt",
            collection_name=test_collection,
            metadata=metadata,
        )

        results = searcher.search_chunks(
            "document metadata",
            limit=3,
            collection_name=test_collection,
        )

        assert len(results) > 0
        # Chunk metadata should include the document metadata
        assert "category" in results[0].metadata or results[0].metadata != {}

    def test_search_chunks_with_metadata_filter(self, doc_store, searcher, test_collection):
        """Test chunk search with metadata filtering."""
        # Ingest documents with different metadata
        doc_store.ingest_document(
            content="Python programming guide. " * 100,
            filename="python_guide.txt",
            collection_name=test_collection,
            metadata={"language": "python", "level": "beginner"},
        )

        doc_store.ingest_document(
            content="Advanced Python techniques. " * 100,
            filename="python_advanced.txt",
            collection_name=test_collection,
            metadata={"language": "python", "level": "advanced"},
        )

        doc_store.ingest_document(
            content="JavaScript basics. " * 100,
            filename="js_basics.txt",
            collection_name=test_collection,
            metadata={"language": "javascript", "level": "beginner"},
        )

        # Search for Python documents only
        python_results = searcher.search_chunks(
            "programming",
            limit=10,
            collection_name=test_collection,
            metadata_filter={"language": "python"},
        )

        # Should only return Python documents
        assert len(python_results) > 0
        for result in python_results:
            assert result.metadata.get("language") == "python"

        # Search for beginner level only
        beginner_results = searcher.search_chunks(
            "guide",
            limit=10,
            collection_name=test_collection,
            metadata_filter={"level": "beginner"},
        )

        assert len(beginner_results) > 0
        for result in beginner_results:
            assert result.metadata.get("level") == "beginner"

        # Search with multiple metadata filters (both must match)
        python_beginner = searcher.search_chunks(
            "programming guide",
            limit=10,
            collection_name=test_collection,
            metadata_filter={"language": "python", "level": "beginner"},
        )

        assert len(python_beginner) > 0
        for result in python_beginner:
            assert result.metadata.get("language") == "python"
            assert result.metadata.get("level") == "beginner"

    def test_search_chunks_metadata_filter_without_collection(self, doc_store, searcher, test_collection):
        """Test metadata filtering without collection filter."""
        # Ingest document with specific metadata
        doc_store.ingest_document(
            content="Tagged document content. " * 100,
            filename="tagged.txt",
            collection_name=test_collection,
            metadata={"tag": "important", "status": "published"},
        )

        # Search across all collections with metadata filter
        results = searcher.search_chunks(
            "tagged content",
            limit=10,
            metadata_filter={"tag": "important"},
        )

        assert len(results) > 0
        for result in results:
            assert result.metadata.get("tag") == "important"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_document_chunker(self):
        """Test get_document_chunker factory."""
        chunker = get_document_chunker()
        assert isinstance(chunker, DocumentChunker)

        config = ChunkingConfig(chunk_size=500)
        chunker_custom = get_document_chunker(config)
        assert chunker_custom.config.chunk_size == 500

    def test_get_document_store(self, db, embedder, coll_mgr):
        """Test get_document_store factory."""
        doc_store = get_document_store(db, embedder, coll_mgr)
        assert doc_store is not None
        assert doc_store.db == db
        assert doc_store.embedder == embedder
        assert doc_store.collection_mgr == coll_mgr
