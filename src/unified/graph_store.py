"""
GraphStore - Wrapper for Graphiti knowledge graph operations.

This module abstracts Graphiti complexity, providing a simple interface for:
- Adding knowledge episodes (automatic entity extraction)
- Searching relationships
- Querying temporal evolution of knowledge
"""

import logging
import time
from datetime import datetime
from typing import Optional, Any
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from neo4j import exceptions

logger = logging.getLogger(__name__)


class GraphStore:
    """Wrapper for Graphiti operations, abstracts Neo4j complexity."""

    def __init__(self, graphiti: Graphiti):
        """
        Initialize GraphStore with a Graphiti instance.

        Args:
            graphiti: Initialized Graphiti instance (already connected to Neo4j)
        """
        self.graphiti = graphiti

    async def health_check(self, timeout_ms: int = 2000) -> dict:
        """
        Lightweight Neo4j liveness check via Graphiti driver.

        Performs a simple RETURN 1 query to verify Neo4j is reachable and responsive.

        Returns:
            Dictionary with health status:
                {
                    "status": "healthy" | "unhealthy" | "unavailable",
                    "latency_ms": float or None,
                    "error": str or None
                }

        Note:
            - Returns "unavailable" if Graphiti not initialized (graceful degradation allowed)
            - Returns "unhealthy" if Neo4j connection fails
            - Latency: ~1-10ms local, ~10-30ms cloud, ~20-50ms Fly.io
            - Designed to fail-fast on unreachable Neo4j before expensive operations
        """
        # Check if Graphiti is initialized at all
        if self.graphiti is None:
            return {
                "status": "unavailable",
                "latency_ms": None,
                "error": "Graphiti not initialized",
            }

        start = time.perf_counter()

        try:
            # Simple query to verify Neo4j is reachable
            result = await self.graphiti.driver.execute_query("RETURN 1 AS num")

            # Verify we got a result
            if not result.records or result.records[0]["num"] != 1:
                latency = (time.perf_counter() - start) * 1000
                return {
                    "status": "unhealthy",
                    "latency_ms": round(latency, 2),
                    "error": "Unexpected query result (expected 1)",
                }

            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "error": None,
            }

        except exceptions.ServiceUnavailable as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": f"Neo4j service unavailable: {str(e)}",
            }

        except exceptions.AuthError as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": f"Neo4j authentication failed: {str(e)}",
            }

        except exceptions.SessionExpired as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": f"Neo4j session expired: {str(e)}",
            }

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": f"Unexpected error: {str(e)}",
            }

    async def validate_schema(self) -> dict:
        """
        Validate Neo4j graph is properly initialized (startup only).

        Performs lightweight checks:
        1. Indexes and constraints exist (validates Graphiti initialization)
        2. Can query nodes (validates graph operability)

        Returns:
            Dictionary with validation status:
                {
                    "status": "valid" | "invalid",
                    "latency_ms": float,
                    "indexes_found": int,
                    "can_query_nodes": bool,
                    "errors": list[str]
                }

        Note:
            - Only called at server startup
            - Latency: ~5-15ms local, ~20-40ms cloud
            - Provides early failure if Neo4j not initialized
        """
        if self.graphiti is None:
            return {
                "status": "invalid",
                "latency_ms": None,
                "indexes_found": 0,
                "can_query_nodes": False,
                "errors": ["Graphiti not initialized"],
            }

        start = time.perf_counter()
        errors = []
        indexes_found = 0
        can_query_nodes = False

        try:
            # Check 1: Indexes and constraints exist
            try:
                result = await self.graphiti.driver.execute_query(
                    "SHOW INDEXES YIELD name"
                )
                indexes_found = len(result.records) if result.records else 0

                if indexes_found == 0:
                    errors.append(
                        "No Neo4j indexes found. "
                        "Graphiti schema may not be initialized. "
                        "Restart the server to trigger Graphiti initialization."
                    )
            except Exception as e:
                errors.append(f"Failed to check indexes: {str(e)}")

            # Check 2: Can query nodes
            try:
                result = await self.graphiti.driver.execute_query(
                    "MATCH (n) RETURN COUNT(n) AS count LIMIT 1"
                )
                if result.records:
                    can_query_nodes = True
                else:
                    # Empty graph is still valid (just no data yet)
                    can_query_nodes = True
            except Exception as e:
                errors.append(f"Cannot query Neo4j nodes: {str(e)}")

        except Exception as e:
            errors.append(f"Schema validation error: {str(e)}")

        latency = (time.perf_counter() - start) * 1000

        return {
            "status": "valid" if not errors else "invalid",
            "latency_ms": round(latency, 2),
            "indexes_found": indexes_found,
            "can_query_nodes": can_query_nodes,
            "errors": errors,
        }

    async def add_knowledge(
        self,
        content: str,
        source_document_id: int,
        metadata: Optional[dict[str, Any]] = None,
        group_id: Optional[str] = None,
        ingestion_timestamp: Optional[datetime] = None
    ) -> list[Any]:
        """
        Add knowledge to the graph with automatic entity extraction.

        Args:
            content: Text content to analyze for entities and relationships
            source_document_id: ID of source document in RAG store (for linking)
            metadata: Optional metadata from RAG ingestion (e.g., collection_name, tags)
            group_id: Collection identifier (links episode to collection in Graphiti)
            ingestion_timestamp: When the document was ingested (for temporal tracking)

        Returns:
            List of extracted entity nodes
        """
        logger.info(f"📊 GraphStore.add_knowledge() - Starting entity extraction for doc_id={source_document_id}")
        logger.info(f"   Content length: {len(content)} chars")
        if metadata:
            logger.info(f"   Metadata: {metadata}")

        # Build episode name from source document ID
        episode_name = f"doc_{source_document_id}"

        # Build source description with ALL metadata embedded
        # This ensures metadata is searchable in Neo4j and visible in graph queries
        source_desc = f"RAG document {source_document_id}"
        if metadata:
            # Core identification
            if "collection_name" in metadata:
                source_desc += f" (collection: {metadata['collection_name']})"
            if "document_title" in metadata:
                source_desc += f" - {metadata['document_title']}"

            # Rich metadata for better searchability
            if "topic" in metadata:
                source_desc += f" | topic: {metadata['topic']}"
            if "content_type" in metadata:
                source_desc += f" | type: {metadata['content_type']}"
            if "author" in metadata:
                source_desc += f" | author: {metadata['author']}"
            if "created_date" in metadata:
                source_desc += f" | created: {metadata['created_date']}"
            if "concepts" in metadata:
                # Handle list of concepts
                concepts = metadata['concepts']
                if isinstance(concepts, list):
                    source_desc += f" | concepts: {', '.join(concepts)}"
                else:
                    source_desc += f" | concepts: {concepts}"

            # Web crawl metadata (for URL ingestion)
            if "crawl_root_url" in metadata:
                source_desc += f" | crawl_root: {metadata['crawl_root_url']}"
            if "crawl_session_id" in metadata:
                source_desc += f" | crawl_session: {metadata['crawl_session_id']}"
            if "crawl_depth" in metadata:
                source_desc += f" | depth: {metadata['crawl_depth']}"

        logger.info(f"   Episode: {episode_name}, Source: {source_desc}")
        if group_id:
            logger.info(f"   Group/Collection: {group_id}")
        logger.info(f"⏳ Calling Graphiti.add_episode() - This may take 30-60 seconds for LLM entity extraction...")

        # Add episode to graph with all metadata
        result = await self.graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.message,
            source_description=source_desc,
            reference_time=ingestion_timestamp or datetime.now(),
            group_id=group_id
        )

        num_entities = len(result.nodes) if result.nodes else 0
        logger.info(f"✅ Graphiti.add_episode() completed - Extracted {num_entities} entities")

        return result.nodes

    async def get_episode_uuid_by_name(self, episode_name: str) -> Optional[str]:
        """
        Look up episode UUID by name using direct Neo4j query.

        Args:
            episode_name: Name of the episode (e.g., "doc_42")

        Returns:
            Episode UUID if found, None if not found
        """
        logger.info(f"🔍 Looking up episode UUID for name: {episode_name}")

        try:
            # Direct Neo4j query to find episode by name
            query = """
            MATCH (e:Episodic {name: $name})
            RETURN e.uuid as uuid
            LIMIT 1
            """

            # Execute query using Graphiti's driver
            result = await self.graphiti.driver.execute_query(
                query,
                name=episode_name
            )

            records = result.records
            if not records:
                logger.warning(f"⚠️  Episode '{episode_name}' not found in graph")
                return None

            uuid = records[0]['uuid']
            logger.info(f"✅ Found episode UUID: {uuid}")
            return uuid

        except Exception as e:
            logger.error(f"❌ Error looking up episode UUID: {e}")
            return None

    async def delete_episode_by_name(self, episode_name: str) -> bool:
        """
        Delete episode by name (looks up UUID first, then deletes).

        This removes the episode and its associated data, including edges
        and orphaned nodes, from the knowledge graph. Entities shared with
        other episodes are preserved.

        Args:
            episode_name: Name of the episode (e.g., "doc_42")

        Returns:
            True if deleted successfully, False if episode not found or error occurred
        """
        logger.info(f"🗑️  GraphStore.delete_episode_by_name() - Deleting episode: {episode_name}")

        # Look up UUID
        episode_uuid = await self.get_episode_uuid_by_name(episode_name)

        if not episode_uuid:
            logger.warning(f"⚠️  Cannot delete - episode '{episode_name}' not found")
            return False

        try:
            # Delete using Graphiti's remove_episode (handles orphaned entity cleanup)
            await self.graphiti.remove_episode(episode_uuid)
            logger.info(f"✅ Successfully deleted episode '{episode_name}' (UUID: {episode_uuid})")
            logger.info(f"   Graphiti automatically cleaned up orphaned entities and edges")
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting episode '{episode_name}': {e}")
            return False

    async def search_relationships(
        self,
        query: str,
        num_results: int = 5,
        reranker_min_score: float = None,
        group_ids: list[str] = None,
    ) -> list[Any]:
        """
        Search for relationships in the knowledge graph.

        Uses configurable search strategy (MMR, RRF, or cross-encoder) with both
        node and edge search for comprehensive results.

        Args:
            query: Natural language query (e.g., "How does my YouTube channel relate to my business?")
            num_results: Number of results to return (applies to both nodes and edges)
            reranker_min_score: Minimum relevance score threshold (0.0-1.0).
                               If None, uses strategy-specific default:
                               - MMR: 0.2 (balanced filtering)
                               - RRF: 0.2 (balanced filtering)
                               - cross_encoder: 0.35 (needs stricter filtering)
                               Can be explicitly set to override defaults.
                               Higher = stricter filtering, Lower = more permissive
            group_ids: (OPTIONAL) List of group IDs (collection names) to filter by.
                      Only return results from episodes with these group IDs.

        Returns:
            List of search results (edges) from the knowledge graph.
            Uses both nodes and edges for comprehensive context.
        """
        import os
        from graphiti_core.search.search_config_recipes import (
            COMBINED_HYBRID_SEARCH_MMR,
            COMBINED_HYBRID_SEARCH_RRF,
            COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
        )

        # Get strategy from environment (set from config.yaml)
        strategy = os.getenv('SEARCH_STRATEGY', 'mmr').lower()

        # Map strategy name to recipe
        strategy_map = {
            'mmr': COMBINED_HYBRID_SEARCH_MMR,
            'rrf': COMBINED_HYBRID_SEARCH_RRF,
            'cross_encoder': COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
        }

        # Get the recipe (default to MMR if invalid strategy)
        recipe = strategy_map.get(strategy, COMBINED_HYBRID_SEARCH_MMR)

        # Use strategy-specific default threshold if not provided
        if reranker_min_score is None:
            default_thresholds = {
                'mmr': 0.2,            # MMR with balanced filtering
                'rrf': 0.2,            # RRF with balanced filtering
                'cross_encoder': 0.35  # Cross-encoder needs stricter filtering
            }
            reranker_min_score = default_thresholds.get(strategy, 0.2)

        # Create config from recipe
        config = recipe.model_copy(deep=True)
        config.limit = num_results
        config.reranker_min_score = reranker_min_score

        # Execute search
        results = await self.graphiti.search_(
            query,
            config=config,
            search_filter=None,
            group_ids=group_ids
        )

        # Return edges (primary relationship data)
        # Note: results also contains .nodes which may have useful context,
        # but MCP tool returns edges for relationship queries
        return results.edges if hasattr(results, 'edges') else []

    async def search_temporal(
        self,
        query: str,
        num_results: int = 10,
        reranker_min_score: float = None,
        group_ids: list[str] = None,
        valid_from: str = None,
        valid_until: str = None,
    ) -> list[Any]:
        """
        Search for temporal knowledge evolution in the knowledge graph.

        Uses configurable search strategy (MMR, RRF, or cross-encoder) with temporal
        filtering to show how facts changed over time.

        Args:
            query: Natural language query about temporal changes
            num_results: Number of results to return
            reranker_min_score: Minimum relevance score threshold (0.0-1.0).
                               If None, uses strategy-specific default (same as search_relationships)
            group_ids: (OPTIONAL) List of group IDs (collection names) to filter by
            valid_from: (OPTIONAL) ISO 8601 date - filter facts valid after this date
            valid_until: (OPTIONAL) ISO 8601 date - filter facts valid before this date

        Returns:
            List of search results (edges) with temporal validity information.
        """
        import os
        from graphiti_core.search.search_config_recipes import (
            COMBINED_HYBRID_SEARCH_MMR,
            COMBINED_HYBRID_SEARCH_RRF,
            COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
        )
        from graphiti_core.search.search_filters import SearchFilters, DateFilter
        from datetime import datetime

        # Get strategy from environment (can be overridden with TEMPORAL_SEARCH_STRATEGY in future)
        strategy = os.getenv('TEMPORAL_SEARCH_STRATEGY') or os.getenv('SEARCH_STRATEGY', 'mmr')
        strategy = strategy.lower()

        # Map strategy name to recipe
        strategy_map = {
            'mmr': COMBINED_HYBRID_SEARCH_MMR,
            'rrf': COMBINED_HYBRID_SEARCH_RRF,
            'cross_encoder': COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
        }

        # Get the recipe (default to MMR if invalid strategy)
        recipe = strategy_map.get(strategy, COMBINED_HYBRID_SEARCH_MMR)

        # Use strategy-specific default threshold if not provided
        if reranker_min_score is None:
            default_thresholds = {
                'mmr': 0.2,            # MMR with balanced filtering
                'rrf': 0.2,            # RRF with balanced filtering
                'cross_encoder': 0.35  # Cross-encoder needs stricter filtering
            }
            reranker_min_score = default_thresholds.get(strategy, 0.2)

        # Build temporal filters if date parameters provided
        search_filter = None
        if valid_from or valid_until:
            filter_dict = {}

            if valid_until:
                # Facts must have started on or before valid_until
                # valid_at <= valid_until
                valid_until_dt = datetime.fromisoformat(valid_until)
                filter_dict['valid_at'] = [[DateFilter(date=valid_until_dt, comparison_operator='<=')]]

            if valid_from:
                # Facts must not have ended before valid_from
                # (invalid_at >= valid_from) OR (invalid_at IS NULL)
                valid_from_dt = datetime.fromisoformat(valid_from)
                filter_dict['invalid_at'] = [
                    [DateFilter(date=valid_from_dt, comparison_operator='>=')],  # OR
                    [DateFilter(date=None, comparison_operator='IS NULL')]       # still valid
                ]

            search_filter = SearchFilters(**filter_dict)

        # Create config from recipe
        config = recipe.model_copy(deep=True)
        config.limit = num_results
        config.reranker_min_score = reranker_min_score

        # Execute search with temporal filter
        results = await self.graphiti.search_(
            query,
            config=config,
            search_filter=search_filter,
            group_ids=group_ids
        )

        # Return edges with temporal information
        return results.edges if hasattr(results, 'edges') else []

    async def close(self):
        """Close the Graphiti connection."""
        await self.graphiti.close()
