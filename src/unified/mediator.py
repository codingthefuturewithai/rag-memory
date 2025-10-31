"""
UnifiedIngestionMediator - Orchestrates ingestion to both RAG and Graph stores.

This module provides a single entry point for content ingestion that ensures
both the vector-based RAG store and the knowledge graph are updated together.

Note: This is Phase 1 implementation without true atomic transactions.
Both stores are updated sequentially, with potential for inconsistency if
the second operation fails. Two-phase commit will be added in Phase 2.
"""

import logging
from datetime import datetime
from typing import Optional, Any, Callable, Awaitable
from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.ingestion.document_store import DocumentStore, get_document_store
from .graph_store import GraphStore

logger = logging.getLogger(__name__)


class UnifiedIngestionMediator:
    """
    Orchestrates content ingestion to both RAG and Graph stores.

    This mediator ensures that content is added to both:
    1. Vector-based RAG store (pgvector) - for semantic search
    2. Knowledge graph (Graphiti/Neo4j) - for relationship queries

    Currently uses sequential updates (RAG first, then Graph).
    Future enhancement: Add two-phase commit for atomicity.
    """

    def __init__(
        self,
        db: Database,
        embedder: EmbeddingGenerator,
        collection_mgr: CollectionManager,
        graph_store: GraphStore
    ):
        """
        Initialize the mediator with RAG and Graph dependencies.

        Args:
            db: Database connection
            embedder: Embeddings generator
            collection_mgr: Collection manager
            graph_store: Graph store wrapper (Graphiti)
        """
        self.rag_store: DocumentStore = get_document_store(db, embedder, collection_mgr)
        self.graph_store = graph_store

    async def ingest_text(
        self,
        content: str,
        collection_name: str,
        document_title: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, float, str], Awaitable[None]]] = None
    ) -> dict[str, Any]:
        """
        Ingest text content into both RAG and Graph stores.

        Args:
            content: Text content to ingest
            collection_name: Collection to add content to (must exist)
            document_title: Optional human-readable title
            metadata: Optional metadata dict
            progress_callback: Optional async callback(progress, total, message) for MCP progress notifications

        Returns:
            dict with:
                - source_document_id: ID of source document in RAG store
                - num_chunks: Number of chunks created
                - entities_extracted: Number of entities extracted by graph
                - collection_name: Collection name

        Raises:
            ValueError: If collection doesn't exist
            Exception: If either RAG or Graph ingestion fails
        """
        logger.info(f"🔄 UnifiedIngestionMediator.ingest_text() - Starting dual ingestion")
        logger.info(f"   Collection: {collection_name}")
        logger.info(f"   Title: {document_title}")
        logger.info(f"   Content length: {len(content)} chars")

        # Progress: Starting
        if progress_callback:
            await progress_callback(0, 100, "Starting ingestion...")

        # Step 1: Ingest into RAG store (existing functionality, unchanged)
        logger.info(f"📥 Step 1/2: Ingesting into RAG store (pgvector)...")

        # Progress: RAG phase
        if progress_callback:
            await progress_callback(10, 100, "Processing RAG embeddings...")

        source_id, chunk_ids = self.rag_store.ingest_document(
            content=content,
            filename=document_title or f"Agent-Text-{content[:20]}",
            collection_name=collection_name,
            metadata=metadata,
            file_type="text"
        )
        logger.info(f"✅ RAG ingestion completed - doc_id={source_id}, {len(chunk_ids)} chunks created")

        # Progress: RAG complete
        if progress_callback:
            await progress_callback(40, 100, "RAG complete, starting knowledge graph extraction...")

        # Validate document metadata against collection (guidance only, doesn't fail)
        try:
            self.rag_store.collection_mgr.validate_document_mandatory_fields(
                collection_name, metadata or {}
            )
        except ValueError:
            # Log but don't fail - validation is guidance only
            pass

        # Step 2: Ingest into Graph store (new functionality)
        logger.info(f"🕸️  Step 2/2: Ingesting into Knowledge Graph (Neo4j/Graphiti)...")

        # Progress: Graph extraction phase (this is the slow part!)
        if progress_callback:
            await progress_callback(50, 100, "Extracting entities and relationships (may take 1-2 minutes)...")

        # Build enhanced metadata with collection and title
        graph_metadata = metadata.copy() if metadata else {}
        graph_metadata["collection_name"] = collection_name
        if document_title:
            graph_metadata["document_title"] = document_title

        try:
            entities = await self.graph_store.add_knowledge(
                content=content,
                source_document_id=source_id,
                metadata=graph_metadata,
                group_id=collection_name,
                ingestion_timestamp=datetime.now()
            )
            logger.info(f"✅ Graph ingestion completed - {len(entities)} entities extracted")

            # Progress: Graph complete
            if progress_callback:
                await progress_callback(90, 100, f"Graph extraction complete ({len(entities)} entities)")

        except Exception as e:
            # Note: In Phase 1, we don't rollback RAG ingestion if graph fails
            # This is acceptable for POC but should be fixed in Phase 2
            logger.error(f"❌ Graph ingestion FAILED after RAG succeeded (doc_id={source_id})")
            logger.error(f"   Error: {e}", exc_info=True)
            raise Exception(
                f"Graph ingestion failed after RAG succeeded (doc_id={source_id}). "
                f"Stores may be inconsistent. Error: {e}"
            )

        logger.info(f"🎉 Unified ingestion completed successfully!")

        return {
            "source_document_id": source_id,
            "num_chunks": len(chunk_ids),
            "entities_extracted": len(entities),
            "collection_name": collection_name,
            "chunk_ids": chunk_ids  # Include for compatibility
        }

    async def close(self):
        """Close graph store connection (RAG store uses connection pool)."""
        await self.graph_store.close()
