"""Document ingestion with embedding generation and storage."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from src.collections import CollectionManager
from src.database import Database
from src.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


class DocumentIngestion:
    """Handles document ingestion with embedding generation."""

    def __init__(
        self,
        database: Database,
        embedding_generator: EmbeddingGenerator,
        collection_manager: CollectionManager,
    ):
        """
        Initialize document ingestion.

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
        logger.info("DocumentIngestion initialized")

    def ingest_text(
        self,
        content: str,
        collection_name: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Ingest a single text document.

        Args:
            content: Document text content.
            collection_name: Name of collection to add document to.
            metadata: Optional metadata dictionary.

        Returns:
            Document ID.
        """
        if not content or not content.strip():
            raise ValueError("Cannot ingest empty content")

        # Ensure collection exists
        collection = self.collection_mgr.get_collection(collection_name)
        if not collection:
            logger.info(f"Creating collection '{collection_name}'")
            self.collection_mgr.create_collection(collection_name)

        # Generate normalized embedding
        logger.debug(f"Generating embedding for content (length: {len(content)})")
        embedding = self.embedder.generate_embedding(content, normalize=True)

        # Verify normalization
        if not self.embedder.verify_normalization(embedding):
            logger.warning("Embedding normalization verification failed!")

        # Store document
        # Note: Wrap metadata dict with Jsonb() for psycopg3 JSONB column
        conn = self.db.connect()

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (content, metadata, embedding)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (content, Jsonb(metadata or {}), embedding),
            )
            doc_id = cur.fetchone()[0]

        # Add to collection
        self.collection_mgr.add_document_to_collection(doc_id, collection_name)

        logger.info(
            f"Ingested document {doc_id} to collection '{collection_name}'"
        )
        return doc_id

    def ingest_file(
        self,
        file_path: str,
        collection_name: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Ingest a document from a file.

        Args:
            file_path: Path to the file.
            collection_name: Name of collection to add document to.
            metadata: Optional metadata dictionary.

        Returns:
            Document ID.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file content
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encoding
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()

        # Add file metadata
        file_metadata = metadata or {}
        file_metadata.update(
            {
                "filename": path.name,
                "filepath": str(path.absolute()),
                "extension": path.suffix,
                "size_bytes": path.stat().st_size,
            }
        )

        logger.info(f"Ingesting file: {path.name}")
        return self.ingest_text(content, collection_name, file_metadata)

    def ingest_directory(
        self,
        directory_path: str,
        collection_name: str,
        extensions: Optional[List[str]] = None,
        recursive: bool = False,
    ) -> List[int]:
        """
        Ingest all files from a directory.

        Args:
            directory_path: Path to the directory.
            collection_name: Name of collection to add documents to.
            extensions: List of file extensions to include (e.g., ['.txt', '.md']).
            recursive: Whether to search subdirectories.

        Returns:
            List of document IDs.
        """
        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")

        extensions = extensions or [".txt", ".md"]
        extensions = [ext.lower() for ext in extensions]

        # Find matching files
        if recursive:
            files = [
                f
                for f in path.rglob("*")
                if f.is_file() and f.suffix.lower() in extensions
            ]
        else:
            files = [
                f
                for f in path.glob("*")
                if f.is_file() and f.suffix.lower() in extensions
            ]

        logger.info(
            f"Found {len(files)} files with extensions {extensions} in {directory_path}"
        )

        document_ids = []
        for file_path in files:
            try:
                doc_id = self.ingest_file(str(file_path), collection_name)
                document_ids.append(doc_id)
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e}")
                continue

        logger.info(
            f"Successfully ingested {len(document_ids)} documents from directory"
        )
        return document_ids

    def ingest_batch(
        self,
        texts: List[str],
        collection_name: str,
        metadatas: Optional[List[Dict]] = None,
    ) -> List[int]:
        """
        Ingest multiple texts in batch for better performance.

        Args:
            texts: List of text contents.
            collection_name: Name of collection to add documents to.
            metadatas: Optional list of metadata dictionaries (must match texts length).

        Returns:
            List of document IDs.
        """
        if not texts:
            raise ValueError("Cannot ingest empty text list")

        if metadatas and len(metadatas) != len(texts):
            raise ValueError("Metadatas list must match texts list length")

        # Ensure collection exists
        collection = self.collection_mgr.get_collection(collection_name)
        if not collection:
            logger.info(f"Creating collection '{collection_name}'")
            self.collection_mgr.create_collection(collection_name)

        # Generate embeddings in batch
        logger.info(f"Generating embeddings for {len(texts)} documents in batch")
        embeddings = self.embedder.generate_embeddings(texts, normalize=True)

        # Store documents
        conn = self.db.connect()
        document_ids = []

        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            metadata = metadatas[i] if metadatas else {}

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (content, metadata, embedding)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (text, Jsonb(metadata), embedding),
                )
                doc_id = cur.fetchone()[0]
                document_ids.append(doc_id)

            # Add to collection
            self.collection_mgr.add_document_to_collection(doc_id, collection_name)

        logger.info(
            f"Batch ingested {len(document_ids)} documents to collection '{collection_name}'"
        )
        return document_ids


def get_document_ingestion(
    database: Database,
    embedding_generator: EmbeddingGenerator,
    collection_manager: CollectionManager,
) -> DocumentIngestion:
    """
    Factory function to get a DocumentIngestion instance.

    Args:
        database: Database instance.
        embedding_generator: Embedding generator instance.
        collection_manager: Collection manager instance.

    Returns:
        Configured DocumentIngestion instance.
    """
    return DocumentIngestion(database, embedding_generator, collection_manager)
