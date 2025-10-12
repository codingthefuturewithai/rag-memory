"""
Hybrid Search: Combines vector similarity search with keyword-based full-text search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
"""

import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

import numpy as np
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.retrieval.search import ChunkSearchResult

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    rankings: List[List[int]],
    k: int = 60
) -> Dict[int, float]:
    """
    Reciprocal Rank Fusion (RRF) algorithm.

    Combines multiple ranked lists into a single ranking.
    Formula: RRF_score(d) = sum over all rankings of 1/(k + rank(d))

    Args:
        rankings: List of ranked lists, where each list contains chunk IDs in rank order
        k: Constant for RRF formula (default 60, from research papers)

    Returns:
        Dict mapping chunk_id to RRF score (higher is better)
    """
    rrf_scores = defaultdict(float)

    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            rrf_scores[chunk_id] += 1.0 / (k + rank)

    return dict(rrf_scores)


class HybridSearch:
    """
    Performs hybrid search combining vector similarity and full-text search.
    """

    def __init__(
        self,
        database: Database,
        embedding_generator: EmbeddingGenerator,
        collection_manager: CollectionManager,
    ):
        """
        Initialize hybrid search.

        Args:
            database: Database instance
            embedding_generator: Embedding generator instance
            collection_manager: Collection manager instance
        """
        self.db = database
        self.embedder = embedding_generator
        self.collection_mgr = collection_manager

        # Register pgvector type
        conn = self.db.connect()
        register_vector(conn)
        logger.info("HybridSearch initialized")

    def keyword_search(
        self,
        query: str,
        limit: int = 20,
        collection_name: Optional[str] = None,
        metadata_filter: Optional[Dict] = None,
    ) -> List[Tuple[int, float]]:
        """
        Perform keyword-based full-text search using PostgreSQL.

        Args:
            query: Search query text
            limit: Maximum number of results
            collection_name: Optional collection filter
            metadata_filter: Optional metadata filter

        Returns:
            List of (chunk_id, rank_score) tuples ordered by relevance
        """
        conn = self.db.connect()

        # Build WHERE clause
        where_conditions = []
        params = [query]  # First param is always the query

        if collection_name:
            collection = self.collection_mgr.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' not found")
            where_conditions.append(f"cc.collection_id = %s")
            params.append(collection["id"])

        if metadata_filter:
            where_conditions.append(f"dc.metadata @> %s::jsonb")
            params.append(Jsonb(metadata_filter))

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Build query based on collection filter
        if collection_name:
            sql_query = f"""
                SELECT
                    dc.id as chunk_id,
                    ts_rank(dc.content_tsv, plainto_tsquery('english', %s)) as rank_score
                FROM document_chunks dc
                INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                {where_clause}
                AND dc.content_tsv @@ plainto_tsquery('english', %s)
                ORDER BY rank_score DESC
                LIMIT %s;
            """
        else:
            sql_query = f"""
                SELECT
                    dc.id as chunk_id,
                    ts_rank(dc.content_tsv, plainto_tsquery('english', %s)) as rank_score
                FROM document_chunks dc
                {where_clause}
                {"AND" if where_conditions else "WHERE"} dc.content_tsv @@ plainto_tsquery('english', %s)
                ORDER BY rank_score DESC
                LIMIT %s;
            """

        # Add query again for the second plainto_tsquery call and limit
        params.extend([query, limit])

        logger.debug(f"Keyword search for: {query[:50]}...")

        with conn.cursor() as cur:
            cur.execute(sql_query, tuple(params))
            results = cur.fetchall()

        keyword_results = [(row[0], float(row[1])) for row in results]
        logger.info(f"Keyword search found {len(keyword_results)} results")

        return keyword_results

    def vector_search(
        self,
        query: str,
        limit: int = 20,
        collection_name: Optional[str] = None,
        metadata_filter: Optional[Dict] = None,
    ) -> List[Tuple[int, float]]:
        """
        Perform vector similarity search (same as baseline, but returns just IDs + scores).

        Args:
            query: Search query text
            limit: Maximum number of results
            collection_name: Optional collection filter
            metadata_filter: Optional metadata filter

        Returns:
            List of (chunk_id, similarity) tuples ordered by similarity
        """
        # Generate normalized query embedding
        query_embedding = self.embedder.generate_embedding(query, normalize=True)
        query_embedding = np.array(query_embedding)

        conn = self.db.connect()

        # Build WHERE clause
        where_conditions = []
        params = [query_embedding]

        if collection_name:
            collection = self.collection_mgr.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' not found")
            where_conditions.append("cc.collection_id = %s")
            params.append(collection["id"])

        if metadata_filter:
            where_conditions.append("dc.metadata @> %s::jsonb")
            params.append(Jsonb(metadata_filter))

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Build query
        if collection_name:
            sql_query = f"""
                SELECT
                    dc.id as chunk_id,
                    dc.embedding <=> %s AS distance
                FROM document_chunks dc
                INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                {where_clause}
                ORDER BY distance
                LIMIT %s;
            """
        else:
            sql_query = f"""
                SELECT
                    dc.id as chunk_id,
                    dc.embedding <=> %s AS distance
                FROM document_chunks dc
                {where_clause}
                ORDER BY distance
                LIMIT %s;
            """

        params.append(limit)

        logger.debug(f"Vector search for: {query[:50]}...")

        with conn.cursor() as cur:
            cur.execute(sql_query, tuple(params))
            results = cur.fetchall()

        # Convert distance to similarity
        vector_results = [(row[0], 1.0 - float(row[1])) for row in results]
        logger.info(f"Vector search found {len(vector_results)} results")

        return vector_results

    def fetch_chunk_details(
        self,
        chunk_ids: List[int],
        include_source: bool = False
    ) -> Dict[int, ChunkSearchResult]:
        """
        Fetch full chunk details for given chunk IDs.

        Args:
            chunk_ids: List of chunk IDs to fetch
            include_source: Whether to include full source document content

        Returns:
            Dict mapping chunk_id to ChunkSearchResult object
        """
        if not chunk_ids:
            return {}

        conn = self.db.connect()

        # Build query
        if include_source:
            sql_query = """
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
                WHERE dc.id = ANY(%s);
            """
        else:
            sql_query = """
                SELECT
                    dc.id,
                    dc.content,
                    dc.metadata,
                    0.0 AS distance,
                    dc.source_document_id,
                    sd.filename,
                    dc.chunk_index,
                    dc.char_start,
                    dc.char_end
                FROM document_chunks dc
                INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                WHERE dc.id = ANY(%s);
            """

        # Use a dummy embedding vector for distance calculation (not used in hybrid search)
        dummy_embedding = np.zeros(1536) if include_source else None

        params = (dummy_embedding, chunk_ids) if include_source else (chunk_ids,)

        with conn.cursor() as cur:
            cur.execute(sql_query, params)
            results = cur.fetchall()

        # Build result dictionary
        chunk_details = {}
        for row in results:
            if include_source:
                (chunk_id, content, metadata, distance, source_id, filename,
                 chunk_idx, char_start, char_end, source_content) = row
            else:
                (chunk_id, content, metadata, distance, source_id, filename,
                 chunk_idx, char_start, char_end) = row
                source_content = None

            # Create ChunkSearchResult with placeholder similarity
            # (will be updated with RRF score later)
            result = ChunkSearchResult(
                chunk_id=chunk_id,
                content=content,
                metadata=metadata or {},
                similarity=0.0,  # Placeholder
                distance=distance,
                source_document_id=source_id,
                source_filename=filename,
                chunk_index=chunk_idx,
                char_start=char_start,
                char_end=char_end,
                source_content=source_content,
            )
            chunk_details[chunk_id] = result

        return chunk_details

    def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        collection_name: Optional[str] = None,
        metadata_filter: Optional[Dict] = None,
        include_source: bool = False,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> List[ChunkSearchResult]:
        """
        Perform hybrid search combining vector and keyword search with RRF.

        Args:
            query: Search query text
            limit: Maximum number of final results to return
            collection_name: Optional collection filter
            metadata_filter: Optional metadata filter
            include_source: Whether to include full source document content
            vector_weight: Weight for vector search (not used in RRF, for future tuning)
            keyword_weight: Weight for keyword search (not used in RRF, for future tuning)
            rrf_k: RRF constant (default 60)

        Returns:
            List of ChunkSearchResult objects ordered by RRF score
        """
        logger.info(f"Starting hybrid search for: {query[:50]}...")

        # Run both searches in parallel (conceptually - sequential for now)
        # Retrieve more results than needed for better fusion
        retrieval_limit = limit * 3

        keyword_results = self.keyword_search(
            query,
            limit=retrieval_limit,
            collection_name=collection_name,
            metadata_filter=metadata_filter
        )

        vector_results = self.vector_search(
            query,
            limit=retrieval_limit,
            collection_name=collection_name,
            metadata_filter=metadata_filter
        )

        # Extract rankings (lists of chunk_ids in order)
        keyword_ranking = [chunk_id for chunk_id, score in keyword_results]
        vector_ranking = [chunk_id for chunk_id, score in vector_results]

        logger.debug(f"Keyword found {len(keyword_ranking)} results, "
                    f"Vector found {len(vector_ranking)} results")

        # Apply Reciprocal Rank Fusion
        rrf_scores = reciprocal_rank_fusion(
            [keyword_ranking, vector_ranking],
            k=rrf_k
        )

        # Sort by RRF score descending
        ranked_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Take top results
        top_chunk_ids = [chunk_id for chunk_id, score in ranked_chunks[:limit]]

        # Fetch full details for top results
        chunk_details = self.fetch_chunk_details(top_chunk_ids, include_source=include_source)

        # Build final results with RRF scores
        final_results = []
        for chunk_id, rrf_score in ranked_chunks[:limit]:
            if chunk_id in chunk_details:
                result = chunk_details[chunk_id]
                # Update similarity with RRF score (normalized to 0-1 range)
                # RRF scores typically range from 0 to ~0.1, so scale for readability
                result.similarity = rrf_score
                final_results.append(result)

        logger.info(f"Hybrid search returned {len(final_results)} results")

        return final_results


def get_hybrid_search(
    database: Database,
    embedding_generator: EmbeddingGenerator,
    collection_manager: CollectionManager,
) -> HybridSearch:
    """
    Factory function to get a HybridSearch instance.

    Args:
        database: Database instance
        embedding_generator: Embedding generator instance
        collection_manager: Collection manager instance

    Returns:
        Configured HybridSearch instance
    """
    return HybridSearch(database, embedding_generator, collection_manager)
