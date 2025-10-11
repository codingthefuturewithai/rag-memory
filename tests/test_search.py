"""Tests for similarity search functionality."""

import pytest

from tests.sample_documents import (
    HIGH_SIMILARITY_TESTS,
    LOW_SIMILARITY_TESTS,
    MEDIUM_SIMILARITY_TESTS,
    TECHNICAL_DOCUMENTS,
    TECHNICAL_QUERIES,
)


class TestSimilarityScores:
    """Test that similarity scores are in expected ranges."""

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_high_similarity_scores(self):
        """Test that semantically similar content produces high scores (0.7-0.95)."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_high_similarity"
        coll_mgr.create_collection(collection_name)

        for test_case in HIGH_SIMILARITY_TESTS:
            # Ingest document
            ingestion.ingest_text(
                test_case["document"],
                collection_name,
                {"test_name": test_case["name"]},
            )

            # Search
            results = searcher.search(
                test_case["query"], limit=1, collection_name=collection_name
            )

            assert len(results) > 0, f"No results for {test_case['name']}"

            similarity = results[0].similarity
            assert (
                test_case["expected_min"] <= similarity <= test_case["expected_max"]
            ), (
                f"{test_case['name']}: Expected similarity {test_case['expected_min']}-"
                f"{test_case['expected_max']}, got {similarity:.4f}"
            )

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_medium_similarity_scores(self):
        """Test that related but not identical content produces medium scores (0.5-0.75)."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_medium_similarity"
        coll_mgr.create_collection(collection_name)

        for test_case in MEDIUM_SIMILARITY_TESTS:
            ingestion.ingest_text(
                test_case["document"],
                collection_name,
                {"test_name": test_case["name"]},
            )

            results = searcher.search(
                test_case["query"], limit=1, collection_name=collection_name
            )

            assert len(results) > 0, f"No results for {test_case['name']}"

            similarity = results[0].similarity
            assert (
                test_case["expected_min"] <= similarity <= test_case["expected_max"]
            ), (
                f"{test_case['name']}: Expected similarity {test_case['expected_min']}-"
                f"{test_case['expected_max']}, got {similarity:.4f}"
            )

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_low_similarity_scores(self):
        """Test that unrelated content produces low scores (0.0-0.4)."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_low_similarity"
        coll_mgr.create_collection(collection_name)

        for test_case in LOW_SIMILARITY_TESTS:
            ingestion.ingest_text(
                test_case["document"],
                collection_name,
                {"test_name": test_case["name"]},
            )

            results = searcher.search(
                test_case["query"], limit=1, collection_name=collection_name
            )

            assert len(results) > 0, f"No results for {test_case['name']}"

            similarity = results[0].similarity
            assert (
                test_case["expected_min"] <= similarity <= test_case["expected_max"]
            ), (
                f"{test_case['name']}: Expected similarity {test_case['expected_min']}-"
                f"{test_case['expected_max']}, got {similarity:.4f}"
            )


class TestSearchFunctionality:
    """Test search functionality and features."""

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_search_with_limit(self):
        """Test that search respects limit parameter."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_limit"
        coll_mgr.create_collection(collection_name)

        # Ingest multiple documents
        ingestion.ingest_batch(
            [doc["content"] for doc in TECHNICAL_DOCUMENTS],
            collection_name,
        )

        # Search with different limits
        results_3 = searcher.search("vector databases", limit=3, collection_name=collection_name)
        results_5 = searcher.search("vector databases", limit=5, collection_name=collection_name)

        assert len(results_3) == 3
        assert len(results_5) == 5

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_search_with_threshold(self):
        """Test that search filters by threshold."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_threshold"
        coll_mgr.create_collection(collection_name)

        # Ingest documents
        ingestion.ingest_batch(
            [doc["content"] for doc in TECHNICAL_DOCUMENTS],
            collection_name,
        )

        # Search with high threshold
        results = searcher.search(
            "vector databases",
            limit=10,
            threshold=0.7,
            collection_name=collection_name,
        )

        # All results should have similarity >= 0.7
        for result in results:
            assert result.similarity >= 0.7

    @pytest.mark.skip(reason="Requires database and OpenAI API key")
    def test_search_returns_correct_documents(self):
        """Test that search returns most relevant documents."""
        from src.collections import get_collection_manager
        from src.database import get_database
        from src.embeddings import get_embedding_generator
        from src.ingestion import get_document_ingestion
        from src.search import get_similarity_search

        # Setup
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        collection_name = "test_relevance"
        coll_mgr.create_collection(collection_name)

        # Ingest documents
        doc_ids = ingestion.ingest_batch(
            [doc["content"] for doc in TECHNICAL_DOCUMENTS],
            collection_name,
        )

        # Test queries
        for query_info in TECHNICAL_QUERIES:
            results = searcher.search(
                query_info["query"], limit=3, collection_name=collection_name
            )

            # Check that top result has minimum expected similarity
            assert results[0].similarity >= query_info["min_similarity"]

            # Check that results are sorted by similarity (descending)
            for i in range(len(results) - 1):
                assert results[i].similarity >= results[i + 1].similarity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
