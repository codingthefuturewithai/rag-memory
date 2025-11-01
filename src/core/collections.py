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
        self,
        name: str,
        description: str,
        domain: str,
        domain_scope: str,
        metadata_schema: dict = None
    ) -> int:
        """
        Create a new collection with mandatory scope fields and optional custom metadata schema.

        Mandatory Fields (required at creation, define collection scope):
            - domain: Single knowledge domain for this collection (e.g., "quantum computing")
              Cannot be changed after creation (immutable).
            - domain_scope: Natural language description of what is/isn't in this domain
              Cannot be changed after creation (immutable).

        Custom Fields (optional, user-defined):
            Declare custom metadata fields per-collection. Format:
            {
                "custom": {
                    "field_name": {
                        "type": "string|number|boolean|array|object",
                        "description": "optional",
                        "required": false,  # new fields must be optional
                        "enum": [...]       # optional
                    }
                }
            }

        Args:
            name: Unique collection name
            description: Collection description (mandatory, non-empty)
            domain: Knowledge domain (mandatory, singular, immutable)
            domain_scope: Description of domain boundaries (mandatory, immutable)
            metadata_schema: Optional custom fields schema (additive-only)

        Returns:
            Collection ID

        Raises:
            ValueError: If mandatory fields invalid, custom schema invalid, or collection already exists
        """
        # Validate description is provided
        if not description or description.strip() == "":
            raise ValueError("Collection description is mandatory")

        # Validate mandatory fields
        if not domain or not isinstance(domain, str) or not domain.strip():
            raise ValueError("Mandatory field 'domain' must be a non-empty string")

        if not domain_scope or not isinstance(domain_scope, str) or not domain_scope.strip():
            raise ValueError("Mandatory field 'domain_scope' must be a non-empty string")

        # Build complete schema with mandatory fields
        complete_schema = {
            "mandatory": {
                "domain": domain.strip(),
                "domain_scope": domain_scope.strip()
            },
            "custom": {},
            "system": []
        }

        # Validate and merge custom fields if provided
        if metadata_schema:
            validated_custom = self._validate_metadata_schema(metadata_schema)
            complete_schema["custom"] = validated_custom.get("custom", {})

        conn = self.db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO collections (name, description, metadata_schema)
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (name, description, Jsonb(complete_schema)),
                )
                collection_id = cur.fetchone()[0]
                logger.info(
                    f"Created collection '{name}' with ID {collection_id}, "
                    f"domain: {domain}, "
                    f"custom fields: {len(complete_schema['custom'])}"
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
            List of dictionaries with collection information including:
            - document_count: number of unique documents (NOT chunks)
            - chunk_count: total number of chunks across all documents
            - metadata_schema: collection's metadata schema
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
                    COUNT(DISTINCT dc.source_document_id) as document_count,
                    COUNT(DISTINCT cc.chunk_id) as chunk_count
                FROM collections c
                LEFT JOIN chunk_collections cc ON c.id = cc.collection_id
                LEFT JOIN document_chunks dc ON cc.chunk_id = dc.id
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
                        "chunk_count": row[6],
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
        Validate and normalize metadata schema (custom fields only).

        This method validates ONLY custom fields. Mandatory fields (domain, topics, domain_scope)
        are validated in create_collection() directly.

        CUSTOM FIELDS (user-defined, additive-only):
        - User-declared fields with type validation
        - Can be required or optional

        Args:
            schema: Raw schema dict from user (may be None). Expected format:
                {
                    "custom": {
                        "field_name": {
                            "type": "string|number|boolean|array|object",
                            "description": "optional",
                            "required": true|false,
                            "enum": [...]  # optional
                        }
                    }
                }

        Returns:
            Normalized schema dict with custom fields validated

        Raises:
            ValueError: If schema structure is invalid
        """
        if schema is None:
            return {"custom": {}}

        if not isinstance(schema, dict):
            raise ValueError("metadata_schema must be a dictionary")

        if "custom" not in schema:
            raise ValueError("metadata_schema must have 'custom' key")

        # Validate custom schema structure
        if not isinstance(schema["custom"], dict):
            raise ValueError("metadata_schema.custom must be a dictionary")

        for field_name, field_def in schema["custom"].items():
            if not isinstance(field_def, dict):
                # Allow shorthand: {"name": "string"}
                field_def = {"type": str(field_def)}
                schema["custom"][field_name] = field_def

            if "type" not in field_def:
                raise ValueError(f"Field '{field_name}' missing required 'type' key")

            allowed_types = {"string", "number", "boolean", "array", "object"}
            if field_def["type"] not in allowed_types:
                raise ValueError(
                    f"Field '{field_name}' has invalid type '{field_def['type']}'. "
                    f"Allowed: {allowed_types}"
                )

        return {"custom": schema["custom"]}

    def validate_document_mandatory_fields(
        self, collection_name: str, document_metadata: dict
    ) -> None:
        """
        Validate that document's domain matches collection's scope (guidance, not enforcement).

        This is a GUIDANCE mechanism, not a hard constraint:
        - LLM clients SHOULD provide domain matching the collection
        - System WILL NOT reject mismatches (helps with retroactive documents)
        - But validation helps LLMs understand collection scope

        Args:
            collection_name: Collection to validate against
            document_metadata: Metadata dict from ingested document

        Raises:
            ValueError: If collection not found
        """
        collection = self.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection '{collection_name}' not found")

        mandatory = collection.get("metadata_schema", {}).get("mandatory", {})
        if not mandatory:
            # No mandatory fields defined yet (old collection) - skip validation
            return

        # Get document's domain (may be missing - that's ok)
        doc_domain = document_metadata.get("domain")

        # Log warnings if mismatches (guidance only, not enforced)
        if doc_domain and doc_domain != mandatory.get("domain"):
            logger.warning(
                f"Document domain '{doc_domain}' does not match collection domain "
                f"'{mandatory.get('domain')}' - this may indicate scope mismatch"
            )

    def update_collection_metadata_schema(
        self, name: str, new_fields: dict
    ) -> dict:
        """
        Update a collection's metadata schema (additive only, mandatory fields immutable).

        MANDATORY FIELD UPDATE RULES:
        - domain: IMMUTABLE - cannot be changed after creation
        - domain_scope: IMMUTABLE - cannot be changed after creation

        CUSTOM FIELD UPDATE RULES:
        - New custom fields can be added
        - Existing custom fields cannot be removed (data integrity)
        - Existing custom field types cannot be changed

        Args:
            name: Collection name to update
            new_fields: New schema fields to add/update
                {
                    "custom": {
                        "new_field": {"type": "string"}
                    }
                }

        Returns:
            Updated collection info with merged schema

        Raises:
            ValueError: If trying to change immutable mandatory fields (domain, domain_scope),
                       remove custom fields, or violate other additive-only constraints
        """
        # Get existing collection
        collection = self.get_collection(name)
        if not collection:
            raise ValueError(f"Collection '{name}' not found")

        current_schema = collection["metadata_schema"]
        current_mandatory = current_schema.get("mandatory", {})

        # RULE 1: Block updates to immutable mandatory fields
        if "mandatory" in new_fields:
            new_mandatory = new_fields["mandatory"]

            # Block domain changes
            if "domain" in new_mandatory and new_mandatory["domain"] != current_mandatory.get("domain"):
                raise ValueError(
                    f"Cannot change mandatory field 'domain' from "
                    f"'{current_mandatory.get('domain')}' to '{new_mandatory['domain']}'. "
                    f"Domain is immutable and defines collection scope."
                )

            # Block domain_scope changes
            if "domain_scope" in new_mandatory and new_mandatory["domain_scope"] != current_mandatory.get("domain_scope"):
                raise ValueError(
                    f"Cannot change mandatory field 'domain_scope' once set. "
                    f"Domain scope is immutable and defines collection boundaries."
                )

        # Ensure new_fields has proper structure for custom fields
        if "custom" in new_fields:
            # Validate no custom field removals
            for field in current_schema.get("custom", {}):
                if field not in new_fields.get("custom", {}):
                    raise ValueError(
                        f"Cannot remove existing field '{field}'. "
                        f"Schema updates are additive-only to preserve data integrity."
                    )

            # Validate no type changes for custom fields
            for field, spec in current_schema.get("custom", {}).items():
                if field in new_fields.get("custom", {}):
                    new_spec = new_fields["custom"][field]
                    if not isinstance(new_spec, dict):
                        new_spec = {"type": str(new_spec)}

                    if spec.get("type") != new_spec.get("type"):
                        raise ValueError(
                            f"Cannot change type of field '{field}' from "
                            f"'{spec.get('type')}' to '{new_spec.get('type')}'. "
                            f"Type changes would break existing documents."
                        )

            # Force all new custom fields to be optional
            for field, spec in new_fields.get("custom", {}).items():
                if field not in current_schema.get("custom", {}):
                    if not isinstance(spec, dict):
                        spec = {"type": str(spec)}
                    spec["required"] = False
                    new_fields["custom"][field] = spec

        # Merge schemas
        updated_schema = current_schema.copy()

        # Update mandatory fields if provided
        if "mandatory" in new_fields:
            if "mandatory" not in updated_schema:
                updated_schema["mandatory"] = {}
            updated_schema["mandatory"].update(new_fields["mandatory"])

        # Update custom fields if provided
        if "custom" in new_fields:
            if "custom" not in updated_schema:
                updated_schema["custom"] = {}
            # Validate the custom fields
            validated_custom = self._validate_metadata_schema({"custom": new_fields["custom"]})
            updated_schema["custom"].update(validated_custom["custom"])

        # Update in database
        conn = self.db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE collections
                SET metadata_schema = %s
                WHERE name = %s
                RETURNING id
                """,
                (Jsonb(updated_schema), name)
            )

            if cur.rowcount == 0:
                raise ValueError(f"Failed to update collection '{name}'")

            collection_id = cur.fetchone()[0]

        custom_added = len(new_fields.get("custom", {})) - len(current_schema.get("custom", {})) if "custom" in new_fields else 0
        logger.info(
            f"Updated metadata schema for collection '{name}' (ID: {collection_id}). "
            f"Added {custom_added} new custom fields."
        )

        # Return updated collection info
        return self.get_collection(name)

    async def delete_collection(self, name: str, graph_store=None) -> bool:
        """
        Delete a collection by name and clean up orphaned documents.

        This performs a complete cleanup:
        1. Gets all source documents in this collection
        2. If graph_store provided: Deletes corresponding Neo4j episodes
        3. Deletes the collection (CASCADE removes chunk_collections entries)
        4. Deletes orphaned chunks (chunks not in any collection)
        5. Deletes orphaned source documents (documents with no chunks)

        Args:
            name: Collection name.
            graph_store: Optional GraphStore instance for cleaning up Neo4j episodes.
                        If provided, will delete graph data for all documents in collection.

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

            # Delete Neo4j episodes if graph_store provided
            if graph_store:
                import asyncio
                deleted_episodes = 0
                failed_episodes = 0

                logger.info(f"Deleting {len(source_doc_ids)} episodes from Knowledge Graph...")

                async def delete_all_episodes():
                    nonlocal deleted_episodes, failed_episodes
                    for doc_id in source_doc_ids:
                        episode_name = f"doc_{doc_id}"
                        try:
                            success = await graph_store.delete_episode_by_name(episode_name)
                            if success:
                                deleted_episodes += 1
                            else:
                                # Episode not found in graph (may not have been ingested)
                                logger.debug(f"Episode '{episode_name}' not found in graph (skipped)")
                        except Exception as e:
                            logger.warning(f"Failed to delete episode '{episode_name}': {e}")
                            failed_episodes += 1

                # Run async deletion
                await delete_all_episodes()

                logger.info(
                    f"Graph cleanup complete: {deleted_episodes} episodes deleted, "
                    f"{failed_episodes} failures, "
                    f"{len(source_doc_ids) - deleted_episodes - failed_episodes} not found"
                )

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
