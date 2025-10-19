"""Store and manage full documents with chunking."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from src.core.chunking import DocumentChunker, get_document_chunker
from src.core.collections import CollectionManager
from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class DocumentStore:
    """Manage full documents and their chunks."""

    def __init__(
        self,
        database: Database,
        embedding_generator: EmbeddingGenerator,
        collection_manager: CollectionManager,
        chunker: Optional[DocumentChunker] = None,
    ):
        """
        Initialize document store.

        Args:
            database: Database instance
            embedding_generator: Embedding generator instance
            collection_manager: Collection manager instance
            chunker: Optional DocumentChunker (uses default if None)
        """
        self.db = database
        self.embedder = embedding_generator
        self.collection_mgr = collection_manager
        self.chunker = chunker or get_document_chunker()

        # Register pgvector type with psycopg
        conn = self.db.connect()
        register_vector(conn)
        logger.info("DocumentStore initialized with pgvector support")

    def ingest_document(
        self,
        content: str,
        filename: str,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        file_type: str = "text",
    ) -> Tuple[int, List[int]]:
        """
        Ingest a document: store full text, chunk it, generate embeddings.

        Args:
            content: Full document text
            filename: Document filename/identifier
            collection_name: Collection to add chunks to
            metadata: Optional metadata for the document
            file_type: File type (text, markdown, pdf, etc.)

        Returns:
            Tuple of (source_document_id, list_of_chunk_ids)
        """
        conn = self.db.connect()

        # 1. Store the full source document
        logger.info(f"Storing source document: {filename}")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_documents
                (filename, content, file_type, file_size, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    filename,
                    content,
                    file_type,
                    len(content),
                    Jsonb(metadata or {}),
                ),
            )
            source_id = cur.fetchone()[0]

        # 2. Verify collection exists
        collection = self.collection_mgr.get_collection(collection_name)
        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Collections must be created explicitly with a description before ingesting documents."
            )

        # 3. Chunk the document
        logger.info(f"Chunking document ({len(content)} chars)...")
        chunks = self.chunker.chunk_text(content, metadata)

        stats = self.chunker.get_stats(chunks)
        logger.info(
            f"Created {stats['num_chunks']} chunks. "
            f"Avg: {stats['avg_chunk_size']:.0f} chars, "
            f"Range: {stats['min_chunk_size']}-{stats['max_chunk_size']}"
        )

        # 4. Generate embeddings and store chunks
        chunk_ids = []
        for chunk_doc in chunks:
            # Generate embedding for this chunk
            embedding = self.embedder.generate_embedding(
                chunk_doc.page_content, normalize=True
            )

            # Convert to numpy array for pgvector
            embedding_array = np.array(embedding)

            # Store chunk
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_chunks
                    (source_document_id, chunk_index, content,
                     char_start, char_end, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        source_id,
                        chunk_doc.metadata.get("chunk_index", 0),
                        chunk_doc.page_content,
                        chunk_doc.metadata.get("char_start", 0),
                        chunk_doc.metadata.get("char_end", 0),
                        Jsonb(chunk_doc.metadata),
                        embedding_array,
                    ),
                )
                chunk_id = cur.fetchone()[0]
                chunk_ids.append(chunk_id)

            # Link chunk to collection
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chunk_collections (chunk_id, collection_id)
                    VALUES (%s, %s)
                    """,
                    (chunk_id, collection["id"]),
                )

        logger.info(f"✅ Ingested document {source_id} with {len(chunk_ids)} chunks")

        return source_id, chunk_ids

    def ingest_file(
        self,
        file_path: str,
        collection_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, List[int]]:
        """
        Read a file from disk and ingest it.

        Args:
            file_path: Path to the file
            collection_name: Collection to add to
            metadata: Optional metadata

        Returns:
            Tuple of (source_document_id, list_of_chunk_ids)
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with latin-1 as fallback
            content = path.read_text(encoding="latin-1")

        # Determine file type from extension
        file_type = path.suffix.lstrip(".").lower() or "text"

        # Add file info to metadata
        file_metadata = metadata or {}
        file_metadata.update(
            {
                "filename": path.name,
                "file_path": str(path.absolute()),
                "file_type": file_type,
            }
        )

        return self.ingest_document(
            content=content,
            filename=path.name,
            collection_name=collection_name,
            metadata=file_metadata,
            file_type=file_type,
        )

    def get_source_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a full source document.

        Args:
            doc_id: Source document ID

        Returns:
            Document dictionary or None if not found
        """
        conn = self.db.connect()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename, content, file_type, file_size,
                       metadata, created_at, updated_at
                FROM source_documents
                WHERE id = %s
                """,
                (doc_id,),
            )
            result = cur.fetchone()

            if result:
                return {
                    "id": result[0],
                    "filename": result[1],
                    "content": result[2],
                    "file_type": result[3],
                    "file_size": result[4],
                    "metadata": result[5] or {},
                    "created_at": result[6],
                    "updated_at": result[7],
                }
            return None

    def list_source_documents(
        self,
        collection_name: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """
        List all source documents, optionally filtered by collection, with pagination.

        Args:
            collection_name: Optional collection filter
            limit: Maximum number of documents to return (None = all)
            offset: Number of documents to skip for pagination
            include_details: If True, includes file_type, file_size, timestamps, collections, metadata

        Returns:
            Dictionary with:
            - documents: List of document dictionaries
            - total_count: Total documents matching filter
            - returned_count: Documents in this response
            - has_more: Whether more pages available
        """
        conn = self.db.connect()

        # Get total count first
        with conn.cursor() as cur:
            if collection_name:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT sd.id)
                    FROM source_documents sd
                    JOIN document_chunks dc ON dc.source_document_id = sd.id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    JOIN collections c ON c.id = cc.collection_id
                    WHERE c.name = %s
                    """,
                    (collection_name,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM source_documents")

            total_count = cur.fetchone()[0]

        # Build query based on include_details flag
        if include_details:
            # Extended query with all metadata
            base_select = """
                SELECT
                    sd.id, sd.filename, sd.file_type,
                    sd.file_size, sd.created_at, sd.updated_at,
                    sd.metadata, COUNT(dc.id) as chunk_count
                FROM source_documents sd
                LEFT JOIN document_chunks dc ON dc.source_document_id = sd.id
            """
        else:
            # Minimal query
            base_select = """
                SELECT
                    sd.id, sd.filename, COUNT(dc.id) as chunk_count
                FROM source_documents sd
                LEFT JOIN document_chunks dc ON dc.source_document_id = sd.id
            """

        # Add collection filter if specified
        if collection_name:
            if include_details:
                group_by = "GROUP BY sd.id, sd.filename, sd.file_type, sd.file_size, sd.created_at, sd.updated_at, sd.metadata"
            else:
                group_by = "GROUP BY sd.id, sd.filename"

            query = base_select + """
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                JOIN collections c ON c.id = cc.collection_id
                WHERE c.name = %s
                """ + group_by + """
                ORDER BY sd.created_at DESC
            """
            params = [collection_name]
        else:
            if include_details:
                group_by = "GROUP BY sd.id, sd.filename, sd.file_type, sd.file_size, sd.created_at, sd.updated_at, sd.metadata"
            else:
                group_by = "GROUP BY sd.id, sd.filename"

            query = base_select + group_by + """
                ORDER BY sd.created_at DESC
            """
            params = []

        # Add pagination
        if limit is not None:
            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])

        # Execute query
        with conn.cursor() as cur:
            cur.execute(query, params)
            results = cur.fetchall()

        # Build document list
        documents = []
        for row in results:
            if include_details:
                doc = {
                    "id": row[0],
                    "filename": row[1],
                    "file_type": row[2],
                    "file_size": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                    "metadata": row[6] or {},
                    "chunk_count": row[7],
                }

                # Get collections for this document
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT c.name
                        FROM collections c
                        JOIN chunk_collections cc ON cc.collection_id = c.id
                        JOIN document_chunks dc ON dc.id = cc.chunk_id
                        WHERE dc.source_document_id = %s
                        """,
                        (row[0],)
                    )
                    doc["collections"] = [r[0] for r in cur.fetchall()]
            else:
                # Minimal response
                doc = {
                    "id": row[0],
                    "filename": row[1],
                    "chunk_count": row[2],
                }

            documents.append(doc)

        returned_count = len(documents)
        has_more = (offset + returned_count) < total_count

        return {
            "documents": documents,
            "total_count": total_count,
            "returned_count": returned_count,
            "has_more": has_more
        }

    def get_document_chunks(self, source_id: int) -> List[Dict[str, Any]]:
        """
        Get all chunks for a source document.

        Args:
            source_id: Source document ID

        Returns:
            List of chunk dictionaries
        """
        conn = self.db.connect()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, chunk_index, content, char_start, char_end, metadata
                FROM document_chunks
                WHERE source_document_id = %s
                ORDER BY chunk_index
                """,
                (source_id,),
            )
            results = cur.fetchall()

            chunks = []
            for row in results:
                chunks.append(
                    {
                        "id": row[0],
                        "chunk_index": row[1],
                        "content": row[2],
                        "char_start": row[3],
                        "char_end": row[4],
                        "metadata": row[5] or {},
                    }
                )

            return chunks

    async def update_document(
        self,
        document_id: int,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        graph_store: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Update an existing document's content, title, or metadata.

        If content is provided, the document is re-chunked and re-embedded automatically.
        Old chunks are deleted and replaced with new ones.

        If graph_store is provided and content is being updated, deletes the old
        Graph episode and creates a new one (handled by caller after this returns).

        Args:
            document_id: ID of document to update
            content: New content (if provided, triggers re-chunking/re-embedding)
            filename: New title/filename
            metadata: New or updated metadata (merged with existing)
            graph_store: Optional GraphStore instance for Knowledge Graph cleanup

        Returns:
            Dictionary with update results:
            {
                "document_id": int,
                "updated_fields": list[str],
                "old_chunk_count": int,
                "new_chunk_count": int,
                "graph_episode_deleted": bool  # True if old episode was deleted
            }

        Raises:
            ValueError: If document_id doesn't exist
        """
        conn = self.db.connect()

        # Get current document
        doc = self.get_source_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        graph_episode_deleted = False

        # If content is being updated and we have a graph store, delete old episode
        if content is not None and graph_store is not None:
            episode_name = f"doc_{document_id}"
            logger.info(f"🗑️  Deleting old Graph episode '{episode_name}' before updating content")
            deleted = await graph_store.delete_episode_by_name(episode_name)
            if deleted:
                graph_episode_deleted = True
                logger.info(f"✅ Old Graph episode deleted successfully")
            else:
                logger.warning(f"⚠️  Old Graph episode '{episode_name}' not found (may not have been indexed)")


        updated_fields = []

        # Update metadata if provided (merge with existing)
        if metadata is not None:
            merged_metadata = {**doc['metadata'], **metadata}
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE source_documents SET metadata = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (Jsonb(merged_metadata), document_id)
                )
            updated_fields.append("metadata")
            logger.info(f"Updated metadata for document {document_id}")

        # Update filename if provided
        if filename is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE source_documents SET filename = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (filename, document_id)
                )
            updated_fields.append("title")
            logger.info(f"Updated filename for document {document_id} to '{filename}'")

        # Update content if provided (requires re-chunking)
        old_chunk_count = 0
        new_chunk_count = 0

        if content is not None:
            # Get old chunk count and collections
            old_chunks = self.get_document_chunks(document_id)
            old_chunk_count = len(old_chunks)

            # Get collections this document belongs to (before deleting chunks)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT c.id, c.name
                    FROM collections c
                    JOIN chunk_collections cc ON cc.collection_id = c.id
                    JOIN document_chunks dc ON dc.id = cc.chunk_id
                    WHERE dc.source_document_id = %s
                    """,
                    (document_id,)
                )
                collections = cur.fetchall()

            logger.info(f"Deleting {old_chunk_count} old chunks for document {document_id}")

            # Delete old chunks (cascade deletes chunk_collections entries)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM document_chunks WHERE source_document_id = %s",
                    (document_id,)
                )

            # Update document content
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE source_documents SET content = %s, file_size = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (content, len(content), document_id)
                )

            logger.info(f"Re-chunking document {document_id} ({len(content)} chars)...")

            # Re-chunk the document
            chunks = self.chunker.chunk_text(content, doc['metadata'])

            stats = self.chunker.get_stats(chunks)
            logger.info(
                f"Created {stats['num_chunks']} new chunks. "
                f"Avg: {stats['avg_chunk_size']:.0f} chars, "
                f"Range: {stats['min_chunk_size']}-{stats['max_chunk_size']}"
            )

            # Store new chunks with embeddings
            new_chunk_ids = []
            for chunk_doc in chunks:
                # Generate embedding
                embedding = self.embedder.generate_embedding(
                    chunk_doc.page_content, normalize=True
                )

                embedding_array = np.array(embedding)

                # Insert chunk
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO document_chunks
                        (source_document_id, chunk_index, content,
                         char_start, char_end, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            document_id,
                            chunk_doc.metadata.get("chunk_index", 0),
                            chunk_doc.page_content,
                            chunk_doc.metadata.get("char_start", 0),
                            chunk_doc.metadata.get("char_end", 0),
                            Jsonb(chunk_doc.metadata),
                            embedding_array,
                        ),
                    )
                    chunk_id = cur.fetchone()[0]
                    new_chunk_ids.append(chunk_id)

                # Re-link to all collections the document belonged to
                for coll_id, coll_name in collections:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO chunk_collections (chunk_id, collection_id) VALUES (%s, %s)",
                            (chunk_id, coll_id)
                        )

            new_chunk_count = len(new_chunk_ids)
            updated_fields.append("content")
            logger.info(f"✅ Updated document {document_id}: replaced {old_chunk_count} chunks with {new_chunk_count} new chunks")

        return {
            "document_id": document_id,
            "updated_fields": updated_fields,
            "old_chunk_count": old_chunk_count,
            "new_chunk_count": new_chunk_count,
            "graph_episode_deleted": graph_episode_deleted
        }

    async def delete_document(self, document_id: int, graph_store: Optional[Any] = None) -> Dict[str, Any]:
        """
        Delete a source document and all its chunks.

        This removes:
        - The source document
        - All document chunks
        - All chunk-collection links (via cascade)
        - The corresponding Knowledge Graph episode (if graph_store provided)

        The document is permanently deleted and cannot be recovered.

        Args:
            document_id: ID of document to delete
            graph_store: Optional GraphStore instance for Knowledge Graph cleanup

        Returns:
            Dictionary with deletion results:
            {
                "document_id": int,
                "document_title": str,
                "chunks_deleted": int,
                "collections_affected": list[str],
                "graph_episode_deleted": bool  # True if Graph episode was deleted
            }

        Raises:
            ValueError: If document_id doesn't exist
        """
        conn = self.db.connect()

        # Get document info before deletion
        doc = self.get_source_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Delete from Knowledge Graph first (if available)
        graph_episode_deleted = False
        if graph_store is not None:
            episode_name = f"doc_{document_id}"
            logger.info(f"🗑️  Deleting Graph episode '{episode_name}' for document {document_id}")
            deleted = await graph_store.delete_episode_by_name(episode_name)
            if deleted:
                graph_episode_deleted = True
                logger.info(f"✅ Graph episode deleted successfully")
            else:
                logger.warning(f"⚠️  Graph episode '{episode_name}' not found (may not have been indexed)")


        chunks = self.get_document_chunks(document_id)

        # Get affected collections
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT c.name
                FROM collections c
                JOIN chunk_collections cc ON cc.collection_id = c.id
                JOIN document_chunks dc ON dc.id = cc.chunk_id
                WHERE dc.source_document_id = %s
                """,
                (document_id,)
            )
            collections_affected = [row[0] for row in cur.fetchall()]

        logger.info(f"Deleting document {document_id} ('{doc['filename']}') with {len(chunks)} chunks")

        # Delete chunks (cascade will handle chunk_collections)
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM document_chunks WHERE source_document_id = %s",
                (document_id,)
            )

        # Delete source document
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM source_documents WHERE id = %s",
                (document_id,)
            )

        logger.info(f"✅ Deleted document {document_id} from collections: {collections_affected}")

        return {
            "document_id": document_id,
            "document_title": doc["filename"],
            "chunks_deleted": len(chunks),
            "collections_affected": collections_affected,
            "graph_episode_deleted": graph_episode_deleted
        }


def get_document_store(
    database: Database,
    embedding_generator: EmbeddingGenerator,
    collection_manager: CollectionManager,
    chunker: Optional[DocumentChunker] = None,
) -> DocumentStore:
    """
    Factory function to get a DocumentStore instance.

    Args:
        database: Database instance
        embedding_generator: Embedding generator instance
        collection_manager: Collection manager instance
        chunker: Optional DocumentChunker

    Returns:
        Configured DocumentStore instance
    """
    return DocumentStore(database, embedding_generator, collection_manager, chunker)
