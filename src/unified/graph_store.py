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
        reranker_min_score: float = 0.35,
        group_ids: list[str] = None,
    ) -> list[Any]:
        """
        Search for relationships in the knowledge graph.

        Uses cross-encoder reranking for relevance filtering.

        Args:
            query: Natural language query (e.g., "How does my YouTube channel relate to my business?")
            num_results: Number of results to return
            reranker_min_score: Cross-encoder confidence threshold (0.0-1.0, default 0.35).
                               Higher values filter more strictly (fewer, more accurate results).
                               Lower values are more permissive (more results, including potentially less relevant ones).
            group_ids: (OPTIONAL) List of group IDs (collection names) to filter by.
                      Only return relationships from episodes with these group IDs.

        Returns:
            List of search results (edges) with cross-encoder scores >= reranker_min_score.
        """
        from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_CROSS_ENCODER

        # Use search_() (with underscore) for advanced search with custom config
        # search_() supports the config parameter, search() does not
        config = COMBINED_HYBRID_SEARCH_CROSS_ENCODER.model_copy(deep=True)
        config.reranker_min_score = reranker_min_score

        results = await self.graphiti.search_(query, config=config, search_filter=None, group_ids=group_ids)

        # search_() returns SearchResults object with .edges, .nodes, .episodes, .communities
        # Graphiti internally filters by reranker_min_score, so we just return edges
        return results.edges if hasattr(results, 'edges') else []

    async def close(self):
        """Close the Graphiti connection."""
        await self.graphiti.close()
