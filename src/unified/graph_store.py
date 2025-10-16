"""
GraphStore - Wrapper for Graphiti knowledge graph operations.

This module abstracts Graphiti complexity, providing a simple interface for:
- Adding knowledge episodes (automatic entity extraction)
- Searching relationships
- Querying temporal evolution of knowledge
"""

from datetime import datetime
from typing import Optional, Any
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType


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
        # Build episode name from source document ID
        episode_name = f"doc_{source_document_id}"

        # Build source description with metadata context
        source_desc = f"RAG document {source_document_id}"
        if metadata:
            if "collection_name" in metadata:
                source_desc += f" (collection: {metadata['collection_name']})"
            if "document_title" in metadata:
                source_desc += f" - {metadata['document_title']}"

        # Add episode to graph
        result = await self.graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.message,
            source_description=source_desc,
            reference_time=datetime.now()
        )

        return result.nodes

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
