"""
GraphStore - Wrapper for Graphiti knowledge graph operations.

This module abstracts Graphiti complexity, providing a simple interface for:
- Adding knowledge episodes (automatic entity extraction)
- Searching relationships
- Querying temporal evolution of knowledge
"""

import logging
from datetime import datetime
from typing import Optional, Any
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

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

    async def add_knowledge(
        self,
        content: str,
        source_document_id: int,
        metadata: Optional[dict[str, Any]] = None
    ) -> list[Any]:
        """
        Add knowledge to the graph with automatic entity extraction.

        Args:
            content: Text content to analyze for entities and relationships
            source_document_id: ID of source document in RAG store (for linking)
            metadata: Optional metadata from RAG ingestion (e.g., collection_name, tags)

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
        logger.info(f"⏳ Calling Graphiti.add_episode() - This may take 30-60 seconds for LLM entity extraction...")

        # Add episode to graph
        result = await self.graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.message,
            source_description=source_desc,
            reference_time=datetime.now()
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
        num_results: int = 5
    ) -> list[Any]:
        """
        Search for relationships in the knowledge graph.

        Args:
            query: Natural language query (e.g., "How does my YouTube channel relate to my business?")
            num_results: Number of results to return

        Returns:
            List of search results (structure depends on Graphiti version)
            Note: API changed - now returns list directly instead of object with .edges
        """
        results = await self.graphiti.search(query, num_results=num_results)
        return results

    async def close(self):
        """Close the Graphiti connection."""
        await self.graphiti.close()
