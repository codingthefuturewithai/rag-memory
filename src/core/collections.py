"""Collection management for organizing documents."""

import logging
from typing import List, Optional
from psycopg.types.json import Jsonb

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

    def create_collection(
        self, name: str, description: str, metadata_schema: dict = None
    ) -> int:
        """
        Create a new collection with a fixed metadata schema.

        Args:
            name: Unique name for the collection.
            description: Description of the collection (mandatory).
            metadata_schema: Optional metadata schema for custom fields.
                Format: {
                    "custom": {
                        "field_name": {
                            "type": "string|number|boolean|array|object",
                            "description": "optional",
                            "required": false,
                            "enum": ["value1", "value2"]  # optional
                        },
                        ...
                    }
                }
                Note: System metadata (domain, crawl_depth, etc.) is added
                automatically when ingesting from URLs/files.
                Defaults to: {"custom": {}}

        Returns:
            Collection ID.

        Raises:
            ValueError: If collection with same name already exists or schema is invalid.
        """
        # Validate description is provided
        if not description or description.strip() == "":
            raise ValueError("Collection description is mandatory")

        # Validate and normalize metadata_schema
        schema = self._validate_metadata_schema(metadata_schema)

        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collections (name, description, metadata_schema)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (name, description, Jsonb(schema)),
                )
                collection_id = cur.fetchone()[0]
                logger.info(
                    f"Created collection '{name}' with ID {collection_id}, "
                    f"schema: {schema}"
                )
                return collection_id
        except Exception as e:
            if "unique" in str(e).lower():
                raise ValueError(f"Collection '{name}' already exists")
            logger.error(f"Failed to create collection: {e}")
            raise

    def list_collections(self) -> List[dict]:
        """
        List all collections with their metadata and schemas.

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
                    c.metadata_schema,
                    c.created_at,
                    COUNT(DISTINCT cc.chunk_id) as document_count
                FROM collections c
                LEFT JOIN chunk_collections cc ON c.id = cc.collection_id
                GROUP BY c.id, c.name, c.description, c.metadata_schema, c.created_at
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
                        "metadata_schema": row[3],
                        "created_at": row[4],
                        "document_count": row[5],
                    }
                )

            logger.info(f"Listed {len(collections)} collections")
            return collections

    def get_collection(self, name: str) -> Optional[dict]:
        """
        Get a collection by name including its metadata schema.

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
                    c.metadata_schema,
                    c.created_at,
                    COUNT(DISTINCT cc.chunk_id) as document_count
                FROM collections c
                LEFT JOIN chunk_collections cc ON c.id = cc.collection_id
                WHERE c.name = %s
                GROUP BY c.id, c.name, c.description, c.metadata_schema, c.created_at;
                """,
                (name,),
            )
            result = cur.fetchone()

            if result:
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "metadata_schema": result[3],
                    "created_at": result[4],
                    "document_count": result[5],
                }
            return None

    def _validate_metadata_schema(self, schema: dict = None) -> dict:
        """
        Validate and normalize metadata schema.

        Args:
            schema: Raw schema dict from user (may be None).

        Returns:
            Normalized schema dict ready for storage.

        Raises:
            ValueError: If schema is invalid.
        """
        if schema is None:
            return {"custom": {}, "system": []}

        if not isinstance(schema, dict):
            raise ValueError("metadata_schema must be a dictionary")

        if "custom" not in schema:
            raise ValueError("metadata_schema must have 'custom' key")

        # System field is optional - defaults to empty array
        # (System metadata like domain, crawl_depth are always added automatically)
        if "system" not in schema:
            schema["system"] = []

        # Validate custom schema structure
        if not isinstance(schema["custom"], dict):
            raise ValueError("metadata_schema.custom must be a dictionary")

        for field_name, field_def in schema["custom"].items():
            if not isinstance(field_def, dict):
                # Allow shorthand: {"name": "string"}
                field_def = {"type": str(field_def)}

            if "type" not in field_def:
                raise ValueError(f"Field '{field_name}' missing required 'type' key")

            allowed_types = {"string", "number", "boolean", "array", "object"}
            if field_def["type"] not in allowed_types:
                raise ValueError(
                    f"Field '{field_name}' has invalid type '{field_def['type']}'. "
                    f"Allowed: {allowed_types}"
                )

        # Validate system metadata fields
        if not isinstance(schema["system"], list):
            raise ValueError("metadata_schema.system must be a list")

        allowed_system_fields = {
            "file_type",
            "source_type",
            "ingested_at",
            "domain",
            "status_code",
            "content_type",
            "file_path",
            "crawl_depth",
            "crawl_root_url",
        }

        for field in schema["system"]:
            if field not in allowed_system_fields:
                raise ValueError(
                    f"Unknown system field: '{field}'. "
                    f"Allowed: {allowed_system_fields}"
                )

        return schema

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
