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

# Maximum content size for Graphiti processing to avoid MCP timeouts
# Graphiti's GPT-4o entity extraction takes ~2 seconds per 1KB of content
# MCP client timeout is 60 seconds, so 50KB = ~100 seconds (too close)
# Safe limit: 50KB = ~100 seconds of processing (with 60s timeout, we chunk)
MAX_GRAPHITI_CONTENT = 50000  # 50KB - safe for <60s MCP timeout


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

        Automatically chunks large content to prevent MCP timeout issues.
        Content larger than MAX_GRAPHITI_CONTENT (50KB) is split into chunks,
        each processed separately to stay within the 60-second MCP timeout.

        Args:
            content: Text content to analyze for entities and relationships
            source_document_id: ID of source document in RAG store (for linking)
            metadata: Optional metadata from RAG ingestion (e.g., collection_name, tags)

        Returns:
            List of extracted entity nodes from all chunks
        """
        logger.info(f"📊 GraphStore.add_knowledge() - Starting entity extraction for doc_id={source_document_id}")
        logger.info(f"   Content length: {len(content)} chars")
        if metadata:
            logger.info(f"   Metadata: {metadata}")

        # Check if content exceeds safe limit
        if len(content) > MAX_GRAPHITI_CONTENT:
            logger.warning(f"⚠️  Content too large ({len(content)} chars) - splitting into chunks")
            logger.warning(f"   Each chunk: {MAX_GRAPHITI_CONTENT} chars max")

            # Calculate number of chunks needed
            num_chunks = (len(content) + MAX_GRAPHITI_CONTENT - 1) // MAX_GRAPHITI_CONTENT
            logger.info(f"   Will create {num_chunks} episodes: doc_{source_document_id}_part1of{num_chunks} ... part{num_chunks}of{num_chunks}")

            all_nodes = []

            for idx in range(num_chunks):
                start = idx * MAX_GRAPHITI_CONTENT
                end = min((idx + 1) * MAX_GRAPHITI_CONTENT, len(content))
                chunk = content[start:end]

                episode_name = f"doc_{source_document_id}_part{idx+1}of{num_chunks}"
                logger.info(f"   📄 Processing chunk {idx+1}/{num_chunks} ({len(chunk)} chars)")

                # Build source description with metadata
                source_desc = self._build_source_description(
                    source_document_id,
                    metadata,
                    part=idx+1,
                    total_parts=num_chunks
                )

                logger.info(f"   ⏳ Calling Graphiti.add_episode() for chunk {idx+1}/{num_chunks}...")

                # Add episode for this chunk
                try:
                    result = await self.graphiti.add_episode(
                        name=episode_name,
                        episode_body=chunk,
                        source=EpisodeType.message,
                        source_description=source_desc,
                        reference_time=datetime.now()
                    )

                    num_entities = len(result.nodes) if result.nodes else 0
                    all_nodes.extend(result.nodes if result.nodes else [])
                    logger.info(f"   ✅ Chunk {idx+1}/{num_chunks} completed - {num_entities} entities extracted")

                except Exception as e:
                    logger.error(f"   ❌ Chunk {idx+1}/{num_chunks} failed: {e}")
                    # Continue with next chunk despite failure

            logger.info(f"✅ Chunked ingestion completed - {len(all_nodes)} total entities across {num_chunks} episodes")
            return all_nodes

        else:
            # Content is small enough - use original single-episode logic
            episode_name = f"doc_{source_document_id}"
            source_desc = self._build_source_description(source_document_id, metadata)

            logger.info(f"   Episode: {episode_name}")
            logger.info(f"   Source: {source_desc}")
            logger.info(f"⏳ Calling Graphiti.add_episode() - This may take 30-60 seconds for LLM entity extraction...")

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

    def _build_source_description(
        self,
        source_document_id: int,
        metadata: Optional[dict[str, Any]] = None,
        part: Optional[int] = None,
        total_parts: Optional[int] = None
    ) -> str:
        """
        Build source description with all metadata embedded.

        This ensures metadata is searchable in Neo4j and visible in graph queries.

        Args:
            source_document_id: ID of source document
            metadata: Optional metadata dict
            part: Part number if chunked (1-indexed)
            total_parts: Total number of parts if chunked

        Returns:
            Formatted source description string
        """
        if part and total_parts:
            source_desc = f"RAG document {source_document_id} (part {part}/{total_parts})"
        else:
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

        return source_desc

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
