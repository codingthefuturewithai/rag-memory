"""
Multi-Query Retrieval: Generate query variations and merge results.

Improves retrieval by expanding user queries into multiple perspectives,
helping handle poorly-worded queries and capturing different semantic angles.
"""

import logging
from typing import List, Dict, Optional
from collections import defaultdict

from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.retrieval.search import ChunkSearchResult, SimilaritySearch

logger = logging.getLogger(__name__)


def generate_query_variations(query: str, num_variations: int = 3) -> List[str]:
    """
    Generate variations of the original query to capture different perspectives.

    This is a simple rule-based approach. In production, you'd use an LLM
    to generate more sophisticated variations.

    Args:
        query: Original user query
        num_variations: Number of variations to generate (default: 3)

    Returns:
        List of query variations including the original
    """
    variations = [query]  # Always include original

    # Variation 1: Add context about documentation/guide
    if "how" in query.lower() or "what" in query.lower():
        variations.append(f"{query} documentation guide")
    else:
        variations.append(f"guide for {query}")

    # Variation 2: Rephrase as a question
    if not query.strip().endswith("?"):
        if query.lower().startswith(("how", "what", "when", "where", "why", "who")):
            variations.append(f"{query}?")
        else:
            variations.append(f"how to {query}")
    else:
        # Already a question, make it a statement
        variations.append(query.rstrip("?"))

    # Variation 3: Add specificity
    if len(query.split()) <= 3:  # Short query
        variations.append(f"{query} setup configuration")
    else:
        # Longer query, try to extract key terms
        words = query.lower().split()
        key_words = [w for w in words if len(w) > 4 and w not in
                     ["the", "with", "from", "that", "this", "have", "will"]]
        if key_words:
            variations.append(" ".join(key_words[:3]))

    # Return requested number of variations (including original)
    return variations[:num_variations]


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


class MultiQueryRetrieval:
    """
    Performs multi-query retrieval by generating query variations and merging results.
    """

    def __init__(
        self,
        database: Database,
        embedding_generator: EmbeddingGenerator,
        collection_manager: CollectionManager,
    ):
        """
        Initialize multi-query retrieval.

        Args:
            database: Database instance
            embedding_generator: Embedding generator instance
            collection_manager: Collection manager instance
        """
        self.db = database
        self.embedder = embedding_generator
        self.collection_mgr = collection_manager
        self.base_searcher = SimilaritySearch(database, embedding_generator, collection_manager)

        logger.info("MultiQueryRetrieval initialized")

    def multi_query_search(
        self,
        query: str,
        limit: int = 10,
        num_variations: int = 3,
        retrieval_limit: int = 20,
        collection_name: Optional[str] = None,
        metadata_filter: Optional[Dict] = None,
        include_source: bool = False,
        rrf_k: int = 60,
    ) -> List[ChunkSearchResult]:
        """
        Perform multi-query retrieval with query expansion and RRF fusion.

        Args:
            query: Original search query
            limit: Maximum number of final results to return
            num_variations: Number of query variations to generate
            retrieval_limit: Number of results to retrieve per variation
            collection_name: Optional collection filter
            metadata_filter: Optional metadata filter
            include_source: Whether to include full source document content
            rrf_k: RRF constant (default 60)

        Returns:
            List of ChunkSearchResult objects ordered by RRF score
        """
        logger.info(f"Starting multi-query search for: {query[:50]}...")

        # Generate query variations
        variations = generate_query_variations(query, num_variations)
        logger.info(f"Generated {len(variations)} query variations")
        for i, var in enumerate(variations, 1):
            logger.debug(f"  Variation {i}: {var}")

        # Retrieve results for each variation
        all_rankings = []
        for variation in variations:
            results = self.base_searcher.search_chunks(
                query=variation,
                limit=retrieval_limit,
                threshold=0.0,  # No threshold, we want all results
                collection_name=collection_name,
                metadata_filter=metadata_filter,
                include_source=False  # We'll fetch details later
            )

            # Extract ranking (list of chunk IDs in order)
            ranking = [r.chunk_id for r in results]
            all_rankings.append(ranking)
            logger.debug(f"  Variation retrieved {len(results)} results")

        # Apply Reciprocal Rank Fusion
        rrf_scores = reciprocal_rank_fusion(all_rankings, k=rrf_k)
        logger.info(f"RRF produced {len(rrf_scores)} unique chunks")

        # Sort by RRF score descending
        ranked_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Take top results
        top_chunk_ids = [chunk_id for chunk_id, score in ranked_chunks[:limit]]

        # Fetch full details for top results
        chunk_details = self._fetch_chunk_details(top_chunk_ids, include_source)

        # Build final results with RRF scores
        final_results = []
        for chunk_id, rrf_score in ranked_chunks[:limit]:
            if chunk_id in chunk_details:
                result = chunk_details[chunk_id]
                # Update similarity with RRF score
                result.similarity = rrf_score
                final_results.append(result)

        logger.info(f"Multi-query search returned {len(final_results)} results")

        return final_results

    def _fetch_chunk_details(
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
                    dc.source_document_id,
                    sd.filename,
                    dc.chunk_index,
                    dc.char_start,
                    dc.char_end
                FROM document_chunks dc
                INNER JOIN source_documents sd ON dc.source_document_id = sd.id
                WHERE dc.id = ANY(%s);
            """

        with conn.cursor() as cur:
            cur.execute(sql_query, (chunk_ids,))
            results = cur.fetchall()

        # Build result dictionary
        chunk_details = {}
        for row in results:
            if include_source:
                (chunk_id, content, metadata, source_id, filename,
                 chunk_idx, char_start, char_end, source_content) = row
            else:
                (chunk_id, content, metadata, source_id, filename,
                 chunk_idx, char_start, char_end) = row
                source_content = None

            # Create ChunkSearchResult with placeholder similarity
            # (will be updated with RRF score)
            result = ChunkSearchResult(
                chunk_id=chunk_id,
                content=content,
                metadata=metadata or {},
                similarity=0.0,  # Placeholder
                distance=0.0,    # Not used in multi-query
                source_document_id=source_id,
                source_filename=filename,
                chunk_index=chunk_idx,
                char_start=char_start,
                char_end=char_end,
                source_content=source_content,
            )
            chunk_details[chunk_id] = result

        return chunk_details


def get_multi_query_search(
    database: Database,
    embedding_generator: EmbeddingGenerator,
    collection_manager: CollectionManager,
) -> MultiQueryRetrieval:
    """
    Factory function to get a MultiQueryRetrieval instance.

    Args:
        database: Database instance
        embedding_generator: Embedding generator instance
        collection_manager: Collection manager instance

    Returns:
        Configured MultiQueryRetrieval instance
    """
    return MultiQueryRetrieval(database, embedding_generator, collection_manager)
