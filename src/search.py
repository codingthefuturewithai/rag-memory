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


class ChunkSearchResult:
    """Represents a search result for a document chunk."""

    def __init__(
        self,
        chunk_id: int,
        content: str,
        metadata: Dict,
        similarity: float,
        distance: float,
        source_document_id: int,
        source_filename: str,
        chunk_index: int,
        char_start: int,
        char_end: int,
        source_content: Optional[str] = None,
    ):
        """
        Initialize chunk search result.

        Args:
            chunk_id: Chunk ID
            content: Chunk content
            metadata: Chunk metadata
            similarity: Similarity score (0-1, higher is better)
            distance: Cosine distance from query (0-2, lower is better)
            source_document_id: Source document ID
            source_filename: Source document filename
            chunk_index: Chunk index within document
            char_start: Character start position in source
            char_end: Character end position in source
            source_content: Optional full source document content
        """
        self.chunk_id = chunk_id
        self.content = content
        self.metadata = metadata
        self.similarity = similarity
        self.distance = distance
        self.source_document_id = source_document_id
        self.source_filename = source_filename
        self.chunk_index = chunk_index
        self.char_start = char_start
        self.char_end = char_end
        self.source_content = source_content

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        result = {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
            "similarity": round(self.similarity, 4),
            "distance": round(self.distance, 4),
            "source_document_id": self.source_document_id,
            "source_filename": self.source_filename,
            "chunk_index": self.chunk_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }
        if self.source_content is not None:
            result["source_content"] = self.source_content
        return result

    def __repr__(self):
        return (
            f"ChunkSearchResult(chunk_id={self.chunk_id}, "
            f"similarity={self.similarity:.4f}, "
            f"source={self.source_filename})"
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

    def search_chunks(
        self,
        query: str,
        limit: int = 10,
        threshold: Optional[float] = None,
        collection_name: Optional[str] = None,
        include_source: bool = False,
        metadata_filter: Optional[Dict] = None,
    ) -> List[ChunkSearchResult]:
        """
        Search document chunks using similarity search.

        Args:
            query: Query text
            limit: Maximum number of results
            threshold: Minimum similarity score (0-1)
            collection_name: Optional collection filter
            include_source: Include full source document content in results
            metadata_filter: Optional metadata filter (JSONB containment check)

        Returns:
            List of ChunkSearchResult objects
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        # Generate normalized query embedding
        logger.debug(f"Generating embedding for chunk query: {query[:100]}...")
        query_embedding = self.embedder.generate_embedding(query, normalize=True)

        # Verify normalization
        if not self.embedder.verify_normalization(query_embedding):
            logger.warning("Query embedding normalization verification failed!")

        # Convert to numpy array for pgvector
        query_embedding = np.array(query_embedding)

        conn = self.db.connect()

        # Build query based on filters
        # Determine which filters are active
        has_collection = collection_name is not None
        has_metadata = metadata_filter is not None

        # Build WHERE clause conditions
        where_conditions = []
        params = [query_embedding]

        if has_collection:
            collection = self.collection_mgr.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' not found")
            where_conditions.append("cc.collection_id = %s")
            params.append(collection["id"])

        if has_metadata:
            where_conditions.append("dc.metadata @> %s::jsonb")
            params.append(Jsonb(metadata_filter))

        # Build WHERE clause
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Build complete query based on include_source and collection filter
        if has_collection:
            # Need to join chunk_collections table
            if include_source:
                sql_query = f"""
                    SELECT
                        dc.id,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s AS distance,
                        dc.source_document_id,
                        sd.filename,
                        dc.chunk_index,
                        dc.char_start,
                        dc.char_end,
                        sd.content AS source_content
                    FROM document_chunks dc
                    INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                    INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                    {where_clause}
                    ORDER BY distance
                    LIMIT %s;
                """
            else:
                sql_query = f"""
                    SELECT
                        dc.id,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s AS distance,
                        dc.source_document_id,
                        sd.filename,
                        dc.chunk_index,
                        dc.char_start,
                        dc.char_end
                    FROM document_chunks dc
                    INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                    INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                    {where_clause}
                    ORDER BY distance
                    LIMIT %s;
                """
        else:
            # No collection filter, no need to join chunk_collections
            if include_source:
                sql_query = f"""
                    SELECT
                        dc.id,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s AS distance,
                        dc.source_document_id,
                        sd.filename,
                        dc.chunk_index,
                        dc.char_start,
                        dc.char_end,
                        sd.content AS source_content
                    FROM document_chunks dc
                    INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                    {where_clause}
                    ORDER BY distance
                    LIMIT %s;
                """
            else:
                sql_query = f"""
                    SELECT
                        dc.id,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s AS distance,
                        dc.source_document_id,
                        sd.filename,
                        dc.chunk_index,
                        dc.char_start,
                        dc.char_end
                    FROM document_chunks dc
                    INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                    {where_clause}
                    ORDER BY distance
                    LIMIT %s;
                """

        # Add limit to params
        params.append(limit)
        params = tuple(params)

        # Log search parameters
        log_msg = f"Searching chunks"
        if has_collection:
            log_msg += f" in collection '{collection_name}'"
        if has_metadata:
            log_msg += f" with metadata filter: {metadata_filter}"
        logger.debug(log_msg)

        # Execute search
        with conn.cursor() as cur:
            cur.execute(sql_query, params)
            results = cur.fetchall()

        # Convert to ChunkSearchResult objects
        chunk_results = []
        for row in results:
            if include_source:
                (
                    chunk_id,
                    content,
                    metadata,
                    distance,
                    source_id,
                    filename,
                    chunk_idx,
                    char_start,
                    char_end,
                    source_content,
                ) = row
            else:
                (
                    chunk_id,
                    content,
                    metadata,
                    distance,
                    source_id,
                    filename,
                    chunk_idx,
                    char_start,
                    char_end,
                ) = row
                source_content = None

            # Convert distance to similarity
            similarity = 1.0 - distance

            # Metadata comes as dict from JSONB column
            metadata = metadata or {}

            # Apply threshold filter if specified
            if threshold is not None and similarity < threshold:
                continue

            result = ChunkSearchResult(
                chunk_id=chunk_id,
                content=content,
                metadata=metadata,
                similarity=similarity,
                distance=distance,
                source_document_id=source_id,
                source_filename=filename,
                chunk_index=chunk_idx,
                char_start=char_start,
                char_end=char_end,
                source_content=source_content,
            )
            chunk_results.append(result)

        logger.info(
            f"Found {len(chunk_results)} chunk results for query (limit={limit}, "
            f"threshold={threshold}, collection={collection_name})"
        )

        if chunk_results:
            logger.debug(
                f"Top chunk: similarity={chunk_results[0].similarity:.4f}, "
                f"source={chunk_results[0].source_filename}, "
                f"chunk_index={chunk_results[0].chunk_index}"
            )

        return chunk_results


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
