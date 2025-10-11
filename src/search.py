"""Similarity search with pgvector and proper distance-to-similarity conversion."""

import logging
from typing import Dict, List, Optional

import numpy as np
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from src.collections import CollectionManager
from src.database import Database
from src.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class SearchResult:
    """Represents a single search result."""

    def __init__(
        self,
        document_id: int,
        content: str,
        metadata: Dict,
        similarity: float,
        distance: float,
    ):
        """
        Initialize search result.

        Args:
            document_id: Document ID.
            content: Document content.
            metadata: Document metadata.
            similarity: Similarity score (0-1, higher is better).
            distance: Cosine distance from query (0-2, lower is better).
        """
        self.document_id = document_id
        self.content = content
        self.metadata = metadata
        self.similarity = similarity
        self.distance = distance

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.metadata,
            "similarity": round(self.similarity, 4),
            "distance": round(self.distance, 4),
        }

    def __repr__(self):
        return (
            f"SearchResult(id={self.document_id}, similarity={self.similarity:.4f})"
        )


class SimilaritySearch:
    """Performs similarity search using pgvector."""

    def __init__(
        self,
        database: Database,
        embedding_generator: EmbeddingGenerator,
        collection_manager: CollectionManager,
    ):
        """
        Initialize similarity search.

        Args:
            database: Database instance.
            embedding_generator: Embedding generator instance.
            collection_manager: Collection manager instance.
        """
        self.db = database
        self.embedder = embedding_generator
        self.collection_mgr = collection_manager

        # Register pgvector type with psycopg
        conn = self.db.connect()
        register_vector(conn)
        logger.info("SimilaritySearch initialized")

    def search(
        self,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
        collection_name: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Perform similarity search.

        Args:
            query: Query text.
            limit: Maximum number of results to return.
            threshold: Minimum similarity score (0-1). Results below this are filtered out.
            collection_name: Optional collection name to limit search scope.

        Returns:
            List of SearchResult objects, sorted by similarity (highest first).
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Generate normalized query embedding
        logger.debug(f"Generating embedding for query: {query[:100]}...")
        query_embedding = self.embedder.generate_embedding(query, normalize=True)

        # Verify normalization
        if not self.embedder.verify_normalization(query_embedding):
            logger.warning("Query embedding normalization verification failed!")

        # Convert to numpy array for pgvector
        query_embedding = np.array(query_embedding)

        conn = self.db.connect()

        # Build query based on whether collection filter is specified
        if collection_name:
            collection = self.collection_mgr.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' not found")

            # Search within specific collection
            sql_query = """
                SELECT
                    d.id,
                    d.content,
                    d.metadata,
                    d.embedding <=> %s AS distance
                FROM documents d
                INNER JOIN document_collections dc ON d.id = dc.document_id
                WHERE dc.collection_id = %s
                ORDER BY distance
                LIMIT %s;
            """
            params = (query_embedding, collection["id"], limit)
            logger.debug(f"Searching in collection '{collection_name}'")
        else:
            # Search all documents
            sql_query = """
                SELECT
                    id,
                    content,
                    metadata,
                    embedding <=> %s AS distance
                FROM documents
                ORDER BY distance
                LIMIT %s;
            """
            params = (query_embedding, limit)
            logger.debug("Searching all documents")

        # Execute search
        with conn.cursor() as cur:
            cur.execute(sql_query, params)
            results = cur.fetchall()

        # Convert to SearchResult objects
        search_results = []
        for row in results:
            doc_id, content, metadata, distance = row

            # Convert distance to similarity: similarity = 1 - distance
            # pgvector's <=> operator returns cosine distance (0-2)
            # We convert to similarity score (0-1) where 1 is identical
            similarity = 1.0 - distance

            # Metadata comes as dict from JSONB column - no parsing needed
            metadata = metadata or {}

            # Apply threshold filter if specified
            if threshold is not None and similarity < threshold:
                continue

            result = SearchResult(
                document_id=doc_id,
                content=content,
                metadata=metadata,
                similarity=similarity,
                distance=distance,
            )
            search_results.append(result)

        logger.info(
            f"Found {len(search_results)} results for query (limit={limit}, "
            f"threshold={threshold}, collection={collection_name})"
        )

        if search_results:
            logger.debug(
                f"Top result: similarity={search_results[0].similarity:.4f}, "
                f"distance={search_results[0].distance:.4f}"
            )

        return search_results

    def search_with_metadata_filter(
        self,
        query: str,
        metadata_filter: Dict,
        limit: int = 10,
        threshold: Optional[float] = None,
    ) -> List[SearchResult]:
        """
        Perform similarity search with metadata filtering.

        Args:
            query: Query text.
            metadata_filter: Dictionary of metadata key-value pairs to filter by.
            limit: Maximum number of results to return.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of SearchResult objects.
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Generate normalized query embedding
        query_embedding = self.embedder.generate_embedding(query, normalize=True)

        # Convert to numpy array for pgvector
        query_embedding = np.array(query_embedding)

        conn = self.db.connect()

        # Build metadata filter condition
        # Using JSONB @> operator for containment check
        sql_query = """
            SELECT
                id,
                content,
                metadata,
                embedding <=> %s AS distance
            FROM documents
            WHERE metadata @> %s::jsonb
            ORDER BY distance
            LIMIT %s;
        """

        # Wrap metadata_filter with Jsonb() for psycopg3 JSONB comparison
        params = (query_embedding, Jsonb(metadata_filter), limit)

        logger.debug(f"Searching with metadata filter: {metadata_filter}")

        # Execute search
        with conn.cursor() as cur:
            cur.execute(sql_query, params)
            results = cur.fetchall()

        # Convert to SearchResult objects
        search_results = []
        for row in results:
            doc_id, content, metadata, distance = row
            similarity = 1.0 - distance
            # Metadata comes as dict from JSONB column
            metadata = metadata or {}

            if threshold is not None and similarity < threshold:
                continue

            result = SearchResult(
                document_id=doc_id,
                content=content,
                metadata=metadata,
                similarity=similarity,
                distance=distance,
            )
            search_results.append(result)

        logger.info(
            f"Found {len(search_results)} results with metadata filter"
        )
        return search_results

    def get_document_by_id(self, document_id: int) -> Optional[Dict]:
        """
        Retrieve a document by its ID.

        Args:
            document_id: Document ID.

        Returns:
            Dictionary with document information, or None if not found.
        """
        conn = self.db.connect()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, content, metadata, created_at, updated_at
                FROM documents
                WHERE id = %s;
                """,
                (document_id,),
            )
            result = cur.fetchone()

            if result:
                doc_id, content, metadata, created_at, updated_at = result
                # Metadata comes as dict from JSONB column
                metadata = metadata or {}

                return {
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            return None


def get_similarity_search(
    database: Database,
    embedding_generator: EmbeddingGenerator,
    collection_manager: CollectionManager,
) -> SimilaritySearch:
    """
    Factory function to get a SimilaritySearch instance.

    Args:
        database: Database instance.
        embedding_generator: Embedding generator instance.
        collection_manager: Collection manager instance.

    Returns:
        Configured SimilaritySearch instance.
    """
    return SimilaritySearch(database, embedding_generator, collection_manager)
