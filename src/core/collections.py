"""Collection management for organizing documents."""

import logging
from typing import List, Optional

from src.core.database import Database

logger = logging.getLogger(__name__)


class CollectionManager:
    """Manages collections for organizing documents."""

    def __init__(self, database: Database):
        """
        Initialize collection manager.

        Args:
            database: Database instance for connection management.
        """
        self.db = database

    def create_collection(self, name: str, description: Optional[str] = None) -> int:
        """
        Create a new collection.

        Args:
            name: Unique name for the collection.
            description: Optional description of the collection.

        Returns:
            Collection ID.

        Raises:
            ValueError: If collection with same name already exists.
        """
        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collections (name, description)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (name, description),
                )
                collection_id = cur.fetchone()[0]
                logger.info(f"Created collection '{name}' with ID {collection_id}")
                return collection_id
        except Exception as e:
            if "unique" in str(e).lower():
                raise ValueError(f"Collection '{name}' already exists")
            logger.error(f"Failed to create collection: {e}")
            raise

    def list_collections(self) -> List[dict]:
        """
        List all collections with their metadata.

        Returns:
            List of dictionaries with collection information.
        """
        conn = self.db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.description,
                    c.created_at,
                    COUNT(DISTINCT cc.chunk_id) as document_count
                FROM collections c
                LEFT JOIN chunk_collections cc ON c.id = cc.collection_id
                GROUP BY c.id, c.name, c.description, c.created_at
                ORDER BY c.created_at DESC;
                """
            )
            results = cur.fetchall()

            collections = []
            for row in results:
                collections.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "created_at": row[3],
                        "document_count": row[4],
                    }
                )

            logger.info(f"Listed {len(collections)} collections")
            return collections

    def get_collection(self, name: str) -> Optional[dict]:
        """
        Get a collection by name.

        Args:
            name: Collection name.

        Returns:
            Collection dictionary or None if not found.
        """
        conn = self.db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.description,
                    c.created_at,
                    COUNT(DISTINCT cc.chunk_id) as document_count
                FROM collections c
                LEFT JOIN chunk_collections cc ON c.id = cc.collection_id
                WHERE c.name = %s
                GROUP BY c.id, c.name, c.description, c.created_at;
                """,
                (name,),
            )
            result = cur.fetchone()

            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "created_at": result[3],
                    "document_count": result[4],
                }
            return None

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection by name and clean up orphaned documents.

        This performs a complete cleanup:
        1. Gets all source documents in this collection
        2. Deletes the collection (CASCADE removes chunk_collections entries)
        3. Deletes orphaned chunks (chunks not in any collection)
        4. Deletes orphaned source documents (documents with no chunks)

        Args:
            name: Collection name.

        Returns:
            True if collection was deleted, False if not found.
        """
        conn = self.db.connect()
        with conn.cursor() as cur:
            # Get collection ID first
            cur.execute("SELECT id FROM collections WHERE name = %s", (name,))
            result = cur.fetchone()

            if not result:
                logger.warning(f"Collection '{name}' not found")
                return False

            collection_id = result[0]

            # Get all source documents in this collection before deletion
            cur.execute(
                """
                SELECT DISTINCT dc.source_document_id
                FROM document_chunks dc
                INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                WHERE cc.collection_id = %s
                """,
                (collection_id,)
            )
            source_doc_ids = [row[0] for row in cur.fetchall()]

            # Delete the collection (CASCADE removes chunk_collections)
            cur.execute(
                "DELETE FROM collections WHERE id = %s",
                (collection_id,)
            )

            # Delete orphaned chunks (not in any collection anymore)
            cur.execute(
                """
                DELETE FROM document_chunks
                WHERE id NOT IN (SELECT chunk_id FROM chunk_collections)
                """
            )
            deleted_chunks = cur.rowcount

            # Delete orphaned source documents (no chunks left)
            cur.execute(
                """
                DELETE FROM source_documents
                WHERE id NOT IN (SELECT DISTINCT source_document_id FROM document_chunks)
                """
            )
            deleted_docs = cur.rowcount

            logger.info(
                f"Deleted collection '{name}' and cleaned up {deleted_docs} documents "
                f"with {deleted_chunks} chunks"
            )
            return True


def get_collection_manager(database: Database) -> CollectionManager:
    """
    Factory function to get a CollectionManager instance.

    Args:
        database: Database instance.

    Returns:
        Configured CollectionManager instance.
    """
    return CollectionManager(database)
