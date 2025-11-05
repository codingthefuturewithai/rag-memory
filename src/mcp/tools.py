"""
Tool implementation functions for MCP server.

These are wrappers around existing RAG functionality, converting to/from
MCP-compatible formats (JSON-serializable dicts).
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.database import Database
from src.core.collections import CollectionManager
from src.retrieval.search import SimilaritySearch
from src.ingestion.document_store import DocumentStore
from src.ingestion.web_crawler import WebCrawler, crawl_single_page
from src.ingestion.website_analyzer import analyze_website_async
from src.unified.graph_store import GraphStore
from src.mcp.deduplication import deduplicate_request

logger = logging.getLogger(__name__)

# ============================================================================
# Analysis Token Store (in-memory, ephemeral)
# ============================================================================
# Tokens are reusable, expire after 4 hours
# Long expiry accounts for real-world usage: user reviews analysis, gets
# distracted, comes back hours later to approve crawl
# Reusable design supports multiple targeted crawls of same site without
# redundant analysis calls


async def ensure_databases_healthy(
    db: Database, graph_store: Optional[GraphStore] = None
) -> Optional[Dict[str, Any]]:
    """
    Check both PostgreSQL and Neo4j are reachable before any write operation.

    This middleware function provides fail-fast validation with clear error
    messages when databases are unavailable.

    Args:
        db: Database instance (always required)
        graph_store: GraphStore instance (required for Option B: Mandatory Graph)

    Returns:
        None if both databases are healthy (operation can proceed).
        Otherwise returns error response dict for MCP client:
            {
                "error": str,                    # Error category
                "status": str,                   # MCP status code
                "message": str,                  # Human-readable message
                "details": {                     # Debug info (internal use)
                    "postgres": {...},           # PostgreSQL health result
                    "neo4j": {...},              # Neo4j health result
                    "retry_after_seconds": int
                }
            }

    Note:
        - PostgreSQL check is always mandatory
        - Neo4j check is mandatory per Gap 2.1 (Option B: All or Nothing)
        - Health check latency: ~5-30ms local, ~50-200ms cloud
    """
    # Check PostgreSQL (ALWAYS REQUIRED)
    pg_health = await db.health_check(timeout_ms=2000)
    if pg_health["status"] != "healthy":
        return {
            "error": "Database unavailable",
            "status": "service_unavailable",
            "message": "PostgreSQL is temporarily unavailable. Please try again in 30 seconds.",
            "details": {
                "postgres": pg_health,
                "retry_after_seconds": 30,
            },
        }

    # Check Neo4j if initialized (REQUIRED for Option B: Mandatory Graph)
    if graph_store is not None:
        graph_health = await graph_store.health_check(timeout_ms=2000)

        # "unavailable" status = Graphiti not initialized (graceful, not an error)
        # "unhealthy" status = Neo4j reachable but not responding (ERROR)
        if graph_health["status"] == "unhealthy":
            return {
                "error": "Knowledge graph unavailable",
                "status": "service_unavailable",
                "message": "Neo4j is temporarily unavailable. Please try again in 30 seconds.",
                "details": {
                    "postgres": pg_health,
                    "neo4j": graph_health,
                    "retry_after_seconds": 30,
                },
            }

    return None  # All checks passed, operation can proceed


def search_documents_impl(
    searcher: SimilaritySearch,
    query: str,
    collection_name: Optional[str],
    limit: int,
    threshold: float,
    include_source: bool,
    include_metadata: bool,
    metadata_filter: dict | None = None,
) -> List[Dict[str, Any]]:
    """Implementation of search_documents tool."""
    try:
        # Execute search
        results = searcher.search_chunks(
            query=query,
            limit=min(limit, 50),  # Cap at 50
            threshold=threshold if threshold is not None else 0.0,
            collection_name=collection_name,
            include_source=include_source,
            metadata_filter=metadata_filter,
        )

        # Convert ChunkSearchResult objects to dicts
        # Minimal response by default (optimized for AI agent context windows)
        results_list = []
        for r in results:
            result = {
                "content": r.content,
                "similarity": float(r.similarity),
                "source_document_id": r.source_document_id,
                "source_filename": r.source_filename,
            }

            # Optionally include extended metadata (chunk details)
            if include_metadata:
                result.update({
                    "chunk_id": r.chunk_id,
                    "chunk_index": r.chunk_index,
                    "char_start": r.char_start,
                    "char_end": r.char_end,
                    "metadata": r.metadata or {},
                })

            # Optionally include full source document content
            if include_source:
                result["source_content"] = r.source_content

            results_list.append(result)

        return results_list
    except Exception as e:
        logger.error(f"search_documents failed: {e}")
        raise


def list_collections_impl(coll_mgr: CollectionManager) -> List[Dict[str, Any]]:
    """Implementation of list_collections tool."""
    try:
        collections = coll_mgr.list_collections()

        # Convert datetime to ISO 8601 string
        return [
            {
                "name": c["name"],
                "description": c["description"] or "",
                "document_count": c["document_count"],
                "created_at": (
                    c["created_at"].isoformat() if c.get("created_at") else None
                ),
            }
            for c in collections
        ]
    except Exception as e:
        logger.error(f"list_collections failed: {e}")
        raise


def update_collection_metadata_impl(
    coll_mgr: CollectionManager,
    collection_name: str,
    new_fields: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Implementation of update_collection_metadata MCP tool.

    Updates a collection's metadata schema (additive only, mandatory fields immutable).

    MANDATORY FIELD UPDATE RULES:

    domain and domain_scope: IMMUTABLE - cannot be changed after creation.
        Attempting to change these fields will raise ValueError.

    topics: ADDITIVE-ONLY - new topics can be added, existing topics preserved.
        When updating topics, provide the new topics to ADD:
        {
            "mandatory": {
                "topics": ["new_topic_1", "new_topic_2"]
            }
        }
        System will merge new topics with existing (deduplicating), so you don't need to
        provide the full list - just the new ones you want to add.

    CUSTOM FIELD UPDATE RULES:

    New custom fields can be added (required=false, additive-only).
    Existing custom fields cannot be removed or have types changed.

    Args:
        coll_mgr: CollectionManager instance
        collection_name: Collection name to update
        new_fields: New schema fields to add/merge. Format:
            {
                "mandatory": {
                    "topics": ["new_topic_1", "new_topic_2"]  # Merged with existing
                },
                "custom": {
                    "new_field": {"type": "string", "required": false}
                }
            }

    Returns:
        {
            "name": str,
            "description": str,
            "metadata_schema": dict,
            "fields_added": int,
            "total_custom_fields": int
        }

    Raises:
        ValueError: If trying to change immutable fields (domain, domain_scope),
                   remove custom fields, or violate additive-only constraints
    """
    try:
        # Wrap new_fields in custom if it's just bare fields (backward compatibility)
        if "custom" not in new_fields and "mandatory" not in new_fields:
            new_fields = {"custom": new_fields}

        # Get current state before update
        current = coll_mgr.get_collection(collection_name)
        if not current:
            raise ValueError(f"Collection '{collection_name}' not found")

        current_custom_count = len(current["metadata_schema"].get("custom", {}))

        # Update the schema (handles mandatory validation)
        updated = coll_mgr.update_collection_metadata_schema(collection_name, new_fields)

        new_custom_count = len(updated["metadata_schema"].get("custom", {}))

        return {
            "name": updated["name"],
            "description": updated["description"],
            "metadata_schema": updated["metadata_schema"],
            "fields_added": new_custom_count - current_custom_count,
            "total_custom_fields": new_custom_count
        }
    except ValueError as e:
        logger.warning(f"update_collection_metadata failed: {e}")
        raise
    except Exception as e:
        logger.error(f"update_collection_metadata error: {e}")
        raise


def create_collection_impl(
    coll_mgr: CollectionManager,
    name: str,
    description: str,
    domain: str,
    domain_scope: str | None = None,
    metadata_schema: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Implementation of create_collection MCP tool.

    Creates a collection with mandatory scope fields (domain, domain_scope) and optional custom metadata fields.

    MANDATORY FIELDS (required at creation, define collection scope):

    domain (string, required):
        Single knowledge domain for this collection. Examples: "quantum computing", "molecular biology", "aviation"
        Immutable - cannot be changed after creation.
        Purpose: Partitions knowledge graph by meaningful knowledge areas.

    domain_scope (string, required):
        Natural language specification of collection boundaries.
        Example: "Covers quantum computing theory and applications. Excludes quantum biology, quantum cryptography outside computing."
        Immutable - cannot be changed after creation.
        Purpose: Helps LLMs understand scope when deciding what documents to ingest.

    CUSTOM FIELDS (optional, user-defined):

    metadata_schema (dict, optional):
        Declare custom metadata fields for documents in this collection. Format:
        {
            "custom": {
                "doc_type": {
                    "type": "string",
                    "description": "Type of document",
                    "required": false,
                    "enum": ["article", "paper", "book"]
                },
                "priority": {
                    "type": "string",
                    "required": false
                }
            }
        }
        New fields must be optional (required=false or omitted).
        Custom fields are additive-only - new fields can be added later but never removed.

    Args:
        coll_mgr: CollectionManager instance
        name: Unique collection name
        description: Collection description (mandatory, non-empty)
        domain: Knowledge domain (mandatory, singular, immutable)
        domain_scope: Domain boundary description (mandatory, immutable)
        metadata_schema: Optional custom field declarations

    Returns:
        {
            "collection_id": int,
            "name": str,
            "description": str,
            "domain": str,
            "domain_scope": str,
            "metadata_schema": dict,
            "created": true
        }

    Raises:
        ValueError: If mandatory fields invalid, custom schema invalid, or collection already exists
    """
    try:
        # Validate mandatory fields
        if not domain or not isinstance(domain, str):
            raise ValueError("domain must be a non-empty string")
        if not domain_scope or not isinstance(domain_scope, str):
            raise ValueError("domain_scope must be a non-empty string")

        # Call updated create_collection with mandatory fields
        collection_id = coll_mgr.create_collection(
            name=name,
            description=description,
            domain=domain,
            domain_scope=domain_scope,
            metadata_schema=metadata_schema,
        )

        collection = coll_mgr.get_collection(name)

        return {
            "collection_id": collection_id,
            "name": name,
            "description": description,
            "domain": domain,
            "domain_scope": domain_scope,
            "metadata_schema": collection.get("metadata_schema"),
            "created": True,
        }
    except ValueError as e:
        logger.warning(f"create_collection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"create_collection failed: {e}")
        raise


def get_collection_metadata_schema_impl(
    coll_mgr: CollectionManager, collection_name: str
) -> Dict[str, Any]:
    """
    Implementation of get_collection_metadata_schema MCP tool.

    Returns the metadata schema for a collection showing what fields to use when ingesting
    and what fields define the collection's scope.

    MANDATORY FIELDS (collection-scoped, immutable):
    - domain: Single knowledge domain (immutable)
    - domain_scope: Domain boundaries description (immutable)
    These define what the collection is about. Domain and domain_scope are automatically applied
    to all documents ingested into this collection.

    CUSTOM FIELDS (user-defined, required/optional):
    - User-declared fields for metadata on documents
    - Each field specifies type and whether it's required when ingesting
    - New fields can be added later, existing ones never removed

    Note: System fields are NOT included in this response. They are internal implementation
    details auto-generated during ingestion. LLMs should NOT provide system fields when ingesting.

    Args:
        coll_mgr: CollectionManager instance
        collection_name: Collection name to retrieve schema for

    Returns:
        {
            "collection_name": str,
            "description": str,
            "document_count": int,
            "metadata_schema": {
                "mandatory_fields": {
                    "domain": {
                        "type": "string",
                        "value": str,
                        "immutable": true,
                        "description": "..."
                    },
                    "domain_scope": {
                        "type": "string",
                        "value": str,
                        "immutable": true,
                        "description": "..."
                    }
                },
                "custom_fields": {
                    "field_name": {
                        "type": "string|number|array|object|boolean",
                        "required": true|false,
                        "enum": [...],
                        "description": "..."
                    },
                    ...
                }
            }
        }

    Raises:
        ValueError: If collection not found
    """
    try:
        collection = coll_mgr.get_collection(collection_name)
        if not collection:
            raise ValueError(f"Collection '{collection_name}' not found")

        schema = collection.get("metadata_schema", {})
        mandatory = schema.get("mandatory", {})
        custom = schema.get("custom", {})

        # Build mandatory fields section
        mandatory_fields = {}
        if mandatory:
            mandatory_fields["domain"] = {
                "type": "string",
                "value": mandatory.get("domain"),
                "immutable": True,
                "description": "Single knowledge domain for this collection. Set at creation, cannot be changed. Automatically applied to all ingested documents."
            }
            mandatory_fields["domain_scope"] = {
                "type": "string",
                "value": mandatory.get("domain_scope"),
                "immutable": True,
                "description": "Natural language definition of domain boundaries (what is/isn't in scope). Set at creation, cannot be changed. Automatically applied to all ingested documents."
            }

        # Build custom fields section
        custom_fields = {}
        for name, field_def in custom.items():
            custom_fields[name] = {
                "type": field_def.get("type", "string"),
                "required": field_def.get("required", False),
                "description": field_def.get("description", "")
            }
            # Include enum if present
            if "enum" in field_def:
                custom_fields[name]["enum"] = field_def["enum"]

        return {
            "collection_name": collection_name,
            "description": collection["description"],
            "document_count": collection["document_count"],
            "metadata_schema": {
                "mandatory_fields": mandatory_fields,
                "custom_fields": custom_fields
            }
        }
    except ValueError as e:
        logger.warning(f"get_collection_metadata_schema failed: {e}")
        raise
    except Exception as e:
        logger.error(f"get_collection_metadata_schema failed: {e}")
        raise


async def delete_collection_impl(
    coll_mgr: CollectionManager,
    name: str,
    confirm: bool = False,
    graph_store = None,
    db = None,
) -> Dict[str, Any]:
    """
    Implementation of delete_collection tool.

    Deletes a collection and all its documents permanently.
    Requires explicit confirmation to prevent accidental data loss.

    If graph_store is provided, also cleans up all episode nodes linked to documents
    in this collection (Phase 4 cleanup).

    Args:
        coll_mgr: CollectionManager instance
        name: Collection name to delete
        confirm: MUST be True to proceed (prevents accidental deletion)
        graph_store: Optional GraphStore for episode cleanup
        db: Optional Database instance (needed if graph_store provided)

    Returns:
        {
            "name": str,
            "deleted": bool,
            "message": str
        }

    Raises:
        ValueError: If collection not found or confirm not set
    """
    try:
        # Require explicit confirmation
        if not confirm:
            raise ValueError(
                f"Deletion requires confirmation. Use confirm=True to proceed. "
                f"WARNING: This will permanently delete collection '{name}' and all its documents."
            )

        # First, get collection info to report what's being deleted
        collection_info = coll_mgr.get_collection(name)
        if not collection_info:
            raise ValueError(f"Collection '{name}' not found")

        doc_count = collection_info.get("document_count", 0)

        # Get source document IDs for graph cleanup BEFORE deletion
        source_doc_ids = []
        if graph_store and db:
            try:
                conn = db.connect()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT DISTINCT dc.source_document_id
                        FROM document_chunks dc
                        INNER JOIN chunk_collections cc ON dc.id = cc.chunk_id
                        INNER JOIN collections c ON cc.collection_id = c.id
                        WHERE c.name = %s
                        """,
                        (name,),
                    )
                    source_doc_ids = [row[0] for row in cur.fetchall()]
                logger.info(
                    f"Found {len(source_doc_ids)} source documents to clean from graph"
                )
            except Exception as e:
                logger.warning(f"Could not fetch source_doc_ids for graph cleanup: {e}")
                source_doc_ids = []

        # Perform RAG deletion
        deleted = await coll_mgr.delete_collection(name)

        if not deleted:
            raise ValueError(f"Collection '{name}' not found")

        logger.info(f"Deleted collection '{name}' with {doc_count} documents")

        # Clean up graph episodes (Phase 4 implementation)
        deleted_episodes = 0
        if graph_store and source_doc_ids:
            try:
                logger.info(f"Cleaning up {len(source_doc_ids)} episodes from graph...")
                for doc_id in source_doc_ids:
                    episode_name = f"doc_{doc_id}"
                    deleted = await graph_store.delete_episode_by_name(episode_name)
                    if deleted:
                        deleted_episodes += 1
                logger.info(
                    f"✅ Graph cleanup complete - {deleted_episodes} episodes deleted"
                )
            except Exception as e:
                logger.warning(
                    f"Graph cleanup encountered issues: {e}. "
                    "RAG data is clean, but some graph episodes may remain."
                )

        message = (
            f"Collection '{name}' and {doc_count} document(s) permanently deleted."
        )
        if deleted_episodes > 0:
            message += f" ({deleted_episodes} graph episodes cleaned)"
        elif graph_store and source_doc_ids:
            message += " (⚠️ Graph cleanup attempted but may have issues)"

        return {
            "name": name,
            "deleted": True,
            "message": message,
        }
    except ValueError as e:
        logger.warning(f"delete_collection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"delete_collection failed: {e}")
        raise


@deduplicate_request()
async def ingest_text_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    content: str,
    collection_name: str,
    document_title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    include_chunk_ids: bool = False,
    progress_callback=None,
    mode: str = "ingest",
) -> Dict[str, Any]:
    """
    Implementation of ingest_text tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).

    Args:
        progress_callback: Optional async callback for MCP progress notifications
    """
    try:
        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        # Auto-generate title if not provided
        if not document_title:
            document_title = f"Agent-Text-{datetime.now().isoformat()}"

        # Check if collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Create it first using create_collection('{collection_name}', 'description')."
            )

        # Check for existing document with same title in this collection
        existing_doc = check_existing_title(db, document_title, collection_name)

        if mode not in ["ingest", "reingest"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'ingest' or 'reingest'")

        if mode == "ingest" and existing_doc:
            raise ValueError(
                f"A document with title '{document_title}' has already been ingested into collection '{collection_name}'.\n"
                f"Existing document: ID={existing_doc['doc_id']}, "
                f"ingested: {existing_doc['created_at']}\n"
                f"To overwrite existing content, use mode='reingest'."
            )

        # If reingest mode, delete old document first
        if mode == "reingest" and existing_doc:
            if progress_callback:
                await progress_callback(5, 100, f"Deleting old version of '{document_title}'...")

            logger.info(f"Reingest mode: Deleting old document ID={existing_doc['doc_id']}")

            # Delete graph episode
            if graph_store:
                episode_name = f"doc_{existing_doc['doc_id']}"
                await graph_store.delete_episode_by_name(episode_name)

            # Delete RAG document
            await doc_store.delete_document(existing_doc['doc_id'])

        # Route through unified mediator (RAG + Graph) with progress callback
        logger.info("Ingesting text through unified mediator (RAG + Graph)")
        result = await unified_mediator.ingest_text(
            content=content,
            collection_name=collection_name,
            document_title=document_title,
            metadata=metadata,
            progress_callback=progress_callback
        )

        # Remove chunk_ids if not requested (minimize response size)
        if not include_chunk_ids:
            result.pop("chunk_ids", None)

        return result
    except Exception as e:
        logger.error(f"ingest_text failed: {e}")
        raise


def get_document_by_id_impl(
    doc_store: DocumentStore, document_id: int, include_chunks: bool
) -> Dict[str, Any]:
    """Implementation of get_document_by_id tool."""
    try:
        doc = doc_store.get_source_document(document_id)

        if not doc:
            raise ValueError(f"Document {document_id} not found")

        result = {
            "id": doc["id"],
            "filename": doc["filename"],
            "content": doc["content"],
            "file_type": doc["file_type"],
            "file_size": doc["file_size"],
            "metadata": doc["metadata"],
            "created_at": doc["created_at"].isoformat(),
            "updated_at": doc["updated_at"].isoformat(),
        }

        if include_chunks:
            chunks = doc_store.get_document_chunks(document_id)
            result["chunks"] = [
                {
                    "chunk_id": c["id"],
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "char_start": c["char_start"],
                    "char_end": c["char_end"],
                }
                for c in chunks
            ]

        return result
    except Exception as e:
        logger.error(f"get_document_by_id failed: {e}")
        raise


def get_collection_info_impl(
    db: Database, coll_mgr: CollectionManager, collection_name: str
) -> Dict[str, Any]:
    """Implementation of get_collection_info tool."""
    try:
        collection = coll_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(f"Collection '{collection_name}' not found")

        # Get chunk count
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT dc.id)
                FROM document_chunks dc
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                """,
                (collection["id"],),
            )
            chunk_count = cur.fetchone()[0]

            # Get sample documents
            cur.execute(
                """
                SELECT DISTINCT sd.filename
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                LIMIT 5
                """,
                (collection["id"],),
            )
            sample_docs = [row[0] for row in cur.fetchall()]

            # Get crawl history (web pages with crawl_root_url metadata)
            cur.execute(
                """
                SELECT DISTINCT
                    sd.metadata->>'crawl_root_url' as crawl_url,
                    sd.metadata->>'crawl_timestamp' as crawl_time,
                    COUNT(DISTINCT sd.id) as page_count,
                    COUNT(DISTINCT dc.id) as chunk_count
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                  AND sd.metadata->>'crawl_root_url' IS NOT NULL
                GROUP BY sd.metadata->>'crawl_root_url', sd.metadata->>'crawl_timestamp'
                ORDER BY sd.metadata->>'crawl_timestamp' DESC
                LIMIT 10
                """,
                (collection["id"],),
            )
            crawled_urls = [
                {
                    "url": row[0],
                    "timestamp": row[1],
                    "page_count": row[2],
                    "chunk_count": row[3],
                }
                for row in cur.fetchall()
            ]

        return {
            "name": collection["name"],
            "description": collection["description"] or "",
            "document_count": collection.get("document_count", 0),
            "chunk_count": chunk_count,
            "created_at": collection["created_at"].isoformat(),
            "sample_documents": sample_docs,
            "crawled_urls": crawled_urls,
        }
    except Exception as e:
        logger.error(f"get_collection_info failed: {e}")
        raise


async def analyze_website_impl(
    base_url: str,
    timeout: int = 10,
    include_url_lists: bool = False,
    max_urls_per_pattern: int = 10
) -> Dict[str, Any]:
    """
    Implementation of analyze_website tool.

    Discovers URL patterns for a website from public sources.
    Includes 50-second hard timeout with graceful error handling.

    GUARANTEED to return structured response in ALL scenarios:
    - Success: URL patterns and statistics
    - Timeout: Informative message about site size
    - Error: Description of what went wrong
    - Tool unavailable: Setup instructions

    NO recommendations or heuristics - just facts for AI agent to reason about.

    By default, returns only pattern_stats summary (lightweight). Agent can request
    full URL lists if needed by setting include_url_lists=True.

    Args:
        base_url: The website URL to analyze (root domain or specific path)
        timeout: DEPRECATED - kept for backward compatibility, ignored
                (actual timeout is 50 seconds, hard-coded for reliability)
        include_url_lists: If True, includes full URL lists per pattern
        max_urls_per_pattern: Max URLs per pattern when include_url_lists=True

    Returns:
        Dictionary with analysis results. ALWAYS includes:
        - base_url: Input URL
        - status: "asyncurlseeder", "timeout", "error", or "not_available"
        - total_urls: Number of URLs discovered (0 on error)
        - pattern_stats: Dictionary of URL patterns (empty on error)
        - notes: Informative message describing results or error
        - elapsed_seconds: Time taken for analysis

        May include (on success):
        - url_groups: Full URL lists per pattern if include_url_lists=True
        - domains: List of domains found in results
        - url_patterns: Number of URL pattern groups found
    """
    try:
        # Call the async analyzer (ignoring deprecated timeout parameter)
        result = await analyze_website_async(base_url, include_url_lists, max_urls_per_pattern)
        return result
    except Exception as e:
        # Fallback error response (should not happen, analyzer handles all errors internally)
        logger.error(f"Unexpected error in analyze_website_impl: {e}")
        return {
            "base_url": base_url,
            "status": "error",
            "error": "unexpected",
            "total_urls": 0,
            "pattern_stats": {},
            "notes": f"Unexpected error during analysis: {str(e)}",
            "elapsed_seconds": 0,
        }


def check_existing_crawl(
    db: Database, url: str, collection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Check if a URL has already been crawled into a collection.

    Args:
        db: Database connection
        url: The crawl root URL to check
        collection_name: The collection name to check

    Returns:
        Dict with crawl info if found, None otherwise
    """
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    sd.metadata->>'crawl_session_id' as session_id,
                    sd.metadata->>'crawl_timestamp' as timestamp,
                    COUNT(DISTINCT sd.id) as page_count,
                    COUNT(DISTINCT dc.id) as chunk_count
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                JOIN collections c ON c.id = cc.collection_id
                WHERE sd.metadata->>'crawl_root_url' = %s
                  AND c.name = %s
                GROUP BY sd.metadata->>'crawl_session_id', sd.metadata->>'crawl_timestamp'
                ORDER BY sd.metadata->>'crawl_timestamp' DESC
                LIMIT 1
                """,
                (url, collection_name),
            )
            row = cur.fetchone()

            if row:
                return {
                    "crawl_session_id": row[0],
                    "crawl_timestamp": row[1],
                    "page_count": row[2],
                    "chunk_count": row[3],
                }
            return None
    except Exception as e:
        logger.error(f"check_existing_crawl failed: {e}")
        raise


def check_existing_file(
    db: Database, file_path: str, collection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Check if a file path has already been ingested into a collection.

    Args:
        db: Database connection
        file_path: Absolute file path to check
        collection_name: Collection name to check within

    Returns:
        Dict with doc info if found, None otherwise
    """
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    sd.id as doc_id,
                    sd.filename,
                    sd.created_at
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                JOIN collections c ON c.id = cc.collection_id
                WHERE sd.metadata->>'file_path' = %s
                  AND c.name = %s
                LIMIT 1
                """,
                (file_path, collection_name),
            )
            row = cur.fetchone()

            if row:
                return {
                    "doc_id": row[0],
                    "filename": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                }
            return None
    except Exception as e:
        logger.error(f"check_existing_file failed: {e}")
        raise


def check_existing_files_batch(
    db: Database, file_paths: List[str], collection_name: str
) -> List[Dict[str, Any]]:
    """
    Check if multiple file paths have already been ingested into a collection.

    Args:
        db: Database connection
        file_paths: List of absolute file paths to check
        collection_name: Collection name to check within

    Returns:
        List of existing documents (empty list if none found)
    """
    if not file_paths:
        return []

    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    sd.id as doc_id,
                    sd.filename,
                    sd.metadata->>'file_path' as file_path
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                JOIN collections c ON c.id = cc.collection_id
                WHERE sd.metadata->>'file_path' = ANY(%s)
                  AND c.name = %s
                """,
                (file_paths, collection_name),
            )
            return [
                {
                    "doc_id": row[0],
                    "filename": row[1],
                    "file_path": row[2],
                }
                for row in cur.fetchall()
            ]
    except Exception as e:
        logger.error(f"check_existing_files_batch failed: {e}")
        raise


def check_existing_title(
    db: Database, title: str, collection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Check if a document title has already been ingested into a collection.

    Args:
        db: Database connection
        title: Document title to check (stored in filename field)
        collection_name: Collection name to check within

    Returns:
        Dict with doc info if found, None otherwise
    """
    try:
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    sd.id as doc_id,
                    sd.filename,
                    sd.created_at
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                JOIN collections c ON c.id = cc.collection_id
                WHERE sd.filename = %s
                  AND c.name = %s
                LIMIT 1
                """,
                (title, collection_name),
            )
            row = cur.fetchone()

            if row:
                return {
                    "doc_id": row[0],
                    "filename": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                }
            return None
    except Exception as e:
        logger.error(f"check_existing_title failed: {e}")
        raise


@deduplicate_request()
async def ingest_url_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_pages: int = 10,
    analysis_token: str | None = None,
    mode: str = "ingest",
    metadata: Optional[Dict[str, Any]] = None,
    include_document_ids: bool = False,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Implementation of ingest_url tool with mode support.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).

    Args:
        follow_links: If True, follows internal links for multi-page crawl
        max_pages: Maximum pages to crawl when follow_links=True (default=10, max=20)
        analysis_token: Optional. Deprecated parameter, kept for backward compatibility.
        mode: "ingest" (new ingest, error if exists) or "reingest" (update existing)
        progress_callback: Optional async callback for MCP progress notifications
    """
    try:
        # Progress: Starting
        if progress_callback:
            await progress_callback(0, 100, "Starting URL ingest...")

        # ============================================================================
        # COMPREHENSIVE PARAMETER VALIDATION
        # ============================================================================

        # Validate max_pages range
        if max_pages < 1:
            raise ValueError(
                f"Invalid max_pages={max_pages}. Must be >= 1."
            )
        if max_pages > 20:
            raise ValueError(
                f"Invalid max_pages={max_pages}. Maximum allowed is 20. "
                f"For large sites, run analyze_website() to plan multiple targeted crawls."
            )


        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        # Validate mode
        if mode not in ["ingest", "reingest"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'ingest' or 'reingest'")

        # Check collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Create it first using create_collection('{collection_name}', 'description')."
            )

        # Check for existing crawl
        existing_crawl = check_existing_crawl(db, url, collection_name)

        if mode == "ingest" and existing_crawl:
            raise ValueError(
                f"This URL has already been ingested into collection '{collection_name}'.\n"
                f"Existing ingest: {existing_crawl['page_count']} pages, "
                f"{existing_crawl['chunk_count']} chunks, "
                f"timestamp: {existing_crawl['crawl_timestamp']}\n"
                f"To overwrite existing content, use mode='reingest'."
            )

        # If reingest mode, delete old documents first
        old_pages_deleted = 0
        if mode == "reingest" and existing_crawl:
            if progress_callback:
                await progress_callback(5, 100, f"Deleting {existing_crawl['page_count']} old pages...")

            conn = db.connect()
            with conn.cursor() as cur:
                # Find all documents with matching crawl_root_url IN THIS COLLECTION ONLY
                cur.execute(
                    """
                    SELECT DISTINCT sd.id, sd.filename
                    FROM source_documents sd
                    JOIN document_chunks dc ON dc.source_document_id = sd.id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    JOIN collections c ON c.id = cc.collection_id
                    WHERE sd.metadata->>'crawl_root_url' = %s
                      AND c.name = %s
                    """,
                    (url, collection_name),
                )
                existing_docs = cur.fetchall()

                old_pages_deleted = len(existing_docs)

                # Delete Graph episodes first (if available)
                if graph_store:
                    logger.info(f"🗑️  Deleting {old_pages_deleted} Graph episodes for reingest of {url}")
                    for doc_id, filename in existing_docs:
                        episode_name = f"doc_{doc_id}"
                        deleted = await graph_store.delete_episode_by_name(episode_name)
                        if deleted:
                            logger.info(f"✅ Deleted Graph episode '{episode_name}' for {filename}")
                        else:
                            logger.warning(f"⚠️  Graph episode '{episode_name}' not found (may not have been indexed)")

                # Delete old RAG documents and chunks
                for doc_id, filename in existing_docs:
                    # Delete chunks
                    cur.execute(
                        "DELETE FROM document_chunks WHERE source_document_id = %s",
                        (doc_id,),
                    )
                    # Delete source document
                    cur.execute("DELETE FROM source_documents WHERE id = %s", (doc_id,))

        # Progress: Crawling web pages
        if progress_callback:
            crawl_msg = f"Crawling {url}" + (f" (max {max_pages} pages)" if follow_links else "")
            await progress_callback(10, 100, crawl_msg)

        # Crawl web pages
        if follow_links:
            crawler = WebCrawler(headless=True, verbose=False)
            # Use max_depth=1 (fixed depth), pass max_pages to BFSDeepCrawlStrategy
            results = await crawler.crawl_with_depth(url, max_depth=1, max_pages=max_pages)

            # Log if we hit the max_pages limit (crawler stopped early)
            if len(results) == max_pages:
                logger.info(
                    f"Crawl reached max_pages limit ({max_pages}). "
                    f"Consider multiple targeted crawls for complete coverage."
                )
        else:
            result = await crawl_single_page(url, headless=True, verbose=False)
            results = [result] if result.success else []

        # Progress: Web crawl complete, starting ingestion
        if progress_callback:
            await progress_callback(20, 100, f"Web crawl complete ({len(results)} pages), starting ingestion...")

        # Ingest each page (route through unified mediator if available)
        document_ids = []
        total_chunks = 0
        total_entities = 0
        successful_ingests = 0

        for idx, result in enumerate(results):
            if not result.success:
                continue

            # Progress: Per-page ingestion (20% to 90%)
            if progress_callback:
                page_progress = 20 + int((idx / len(results)) * 70)
                await progress_callback(
                    page_progress,
                    100,
                    f"Ingesting page {idx + 1}/{len(results)}: {result.metadata.get('title', result.url)[:50]}..."
                )

            try:
                page_title = result.metadata.get("title", result.url)

                # Merge user metadata with page metadata
                page_metadata = metadata.copy() if metadata else {}
                page_metadata.update(result.metadata)

                logger.info(f"Ingesting page through unified mediator: {page_title}")
                # Note: Don't pass progress_callback here - would conflict with parent progress
                ingest_result = await unified_mediator.ingest_text(
                    content=result.content,
                    collection_name=collection_name,
                    document_title=page_title,
                    metadata=page_metadata,
                    progress_callback=None  # Skip nested progress for multi-page crawls
                )
                document_ids.append(ingest_result["source_document_id"])
                total_chunks += ingest_result["num_chunks"]
                total_entities += ingest_result.get("entities_extracted", 0)
                successful_ingests += 1

            except Exception as e:
                logger.warning(f"Failed to ingest page {result.url}: {e}")

        response = {
            "mode": mode,
            "pages_crawled": len(results),
            "pages_ingested": successful_ingests,
            "total_chunks": total_chunks,
            "collection_name": collection_name,
            "entities_extracted": total_entities,
            "crawl_metadata": {
                "crawl_root_url": url,
                "crawl_session_id": (
                    results[0].metadata.get("crawl_session_id") if results else None
                ),
                "crawl_timestamp": datetime.now().isoformat(),
            },
        }

        if mode == "reingest":
            response["old_pages_deleted"] = old_pages_deleted

        if include_document_ids:
            response["document_ids"] = document_ids

        return response
    except Exception as e:
        logger.error(f"ingest_url failed: {e}")
        raise


@deduplicate_request()
async def ingest_file_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    file_path: str,
    collection_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    include_chunk_ids: bool = False,
    progress_callback=None,
    mode: str = "ingest",
) -> Dict[str, Any]:
    """
    Implementation of ingest_file tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).

    Args:
        progress_callback: Optional async callback for MCP progress notifications
    """
    try:
        # Progress: Starting
        if progress_callback:
            await progress_callback(0, 100, "Starting file ingestion...")

        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        # Validate path is within configured mounts
        from src.core.config_loader import is_path_in_mounts
        is_valid, mount_msg = is_path_in_mounts(file_path)
        if not is_valid:
            raise PermissionError(mount_msg)

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Create it first using create_collection('{collection_name}', 'description')."
            )

        # Check for existing file in this collection
        existing_doc = check_existing_file(db, file_path, collection_name)

        if mode not in ["ingest", "reingest"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'ingest' or 'reingest'")

        if mode == "ingest" and existing_doc:
            raise ValueError(
                f"This file has already been ingested into collection '{collection_name}'.\n"
                f"Existing document: ID={existing_doc['doc_id']}, "
                f"filename='{existing_doc['filename']}', "
                f"ingested: {existing_doc['created_at']}\n"
                f"To overwrite existing content, use mode='reingest'."
            )

        # If reingest mode, delete old document first
        if mode == "reingest" and existing_doc:
            if progress_callback:
                await progress_callback(5, 100, f"Deleting old version of {path.name}...")

            logger.info(f"Reingest mode: Deleting old document ID={existing_doc['doc_id']}")

            # Delete graph episode
            if graph_store:
                episode_name = f"doc_{existing_doc['doc_id']}"
                await graph_store.delete_episode_by_name(episode_name)

            # Delete RAG document
            await doc_store.delete_document(existing_doc['doc_id'])

        file_size = path.stat().st_size
        file_type = path.suffix.lstrip(".").lower() or "text"

        # Progress: Reading file
        if progress_callback:
            await progress_callback(5, 100, f"Reading file {path.name}...")

        logger.info(f"Ingesting file through unified mediator: {path.name}")

        # Read file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Merge file metadata with user metadata
        file_metadata = metadata.copy() if metadata else {}
        file_metadata.update({
            "file_type": file_type,
            "file_size": file_size,
            "file_path": file_path,  # NEW - for duplicate detection
        })

        # Progress: Ingesting (pass callback to mediator)
        if progress_callback:
            await progress_callback(10, 100, f"Processing {path.name}...")

        ingest_result = await unified_mediator.ingest_text(
            content=content,
            collection_name=collection_name,
            document_title=path.name,
            metadata=file_metadata,
            progress_callback=progress_callback
        )

        result = {
            "source_document_id": ingest_result["source_document_id"],
            "num_chunks": ingest_result["num_chunks"],
            "entities_extracted": ingest_result.get("entities_extracted", 0),
            "filename": path.name,
            "file_type": file_type,
            "file_size": file_size,
            "collection_name": collection_name,
        }

        if include_chunk_ids:
            result["chunk_ids"] = ingest_result.get("chunk_ids", [])

        return result
    except Exception as e:
        logger.error(f"ingest_file failed: {e}")
        raise


@deduplicate_request()
async def ingest_directory_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    directory_path: str,
    collection_name: str,
    file_extensions: Optional[List[str]] = None,
    recursive: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    include_document_ids: bool = False,
    progress_callback=None,
    mode: str = "ingest",
) -> Dict[str, Any]:
    """
    Implementation of ingest_directory tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).

    Args:
        progress_callback: Optional async callback for MCP progress notifications
    """
    try:
        # Progress: Starting
        if progress_callback:
            await progress_callback(0, 100, "Starting directory ingestion...")

        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        # Validate path is within configured mounts
        from src.core.config_loader import is_path_in_mounts
        is_valid, mount_msg = is_path_in_mounts(directory_path)
        if not is_valid:
            raise PermissionError(mount_msg)

        path = Path(directory_path)

        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")

        # Check collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Create it first using create_collection('{collection_name}', 'description')."
            )

        # Default extensions
        if not file_extensions:
            file_extensions = [".txt", ".md"]

        # Progress: Scanning directory
        if progress_callback:
            await progress_callback(5, 100, f"Scanning directory for {', '.join(file_extensions)} files...")

        # Find files
        files = []
        for ext in file_extensions:
            if recursive:
                files.extend(path.rglob(f"*{ext}"))
            else:
                files.extend(path.glob(f"*{ext}"))

        files = sorted(set(files))

        # Progress: Found files
        if progress_callback:
            await progress_callback(10, 100, f"Found {len(files)} files, checking for duplicates...")

        # Check for existing files in this collection (upfront batch check)
        file_paths_absolute = [str(f.absolute()) for f in files]
        existing_files = check_existing_files_batch(db, file_paths_absolute, collection_name)

        if mode not in ["ingest", "reingest"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'ingest' or 'reingest'")

        if mode == "ingest" and existing_files:
            file_list = '\n  - '.join(
                [f"'{f['filename']}' (ID={f['doc_id']})" for f in existing_files[:10]]
            )
            if len(existing_files) > 10:
                file_list += f"\n  ... and {len(existing_files) - 10} more"

            raise ValueError(
                f"{len(existing_files)} file(s) from this directory have already been ingested into collection '{collection_name}':\n"
                f"  {file_list}\n\n"
                f"To overwrite existing files, use mode='reingest'."
            )

        # If reingest mode, delete old documents first
        if mode == "reingest" and existing_files:
            if progress_callback:
                await progress_callback(5, 100, f"Deleting {len(existing_files)} old files...")

            logger.info(f"Reingest mode: Deleting {len(existing_files)} old documents")

            for existing_doc in existing_files:
                # Delete graph episode
                if graph_store:
                    episode_name = f"doc_{existing_doc['doc_id']}"
                    await graph_store.delete_episode_by_name(episode_name)

                # Delete RAG document
                await doc_store.delete_document(existing_doc['doc_id'])

        # Progress: Starting ingestion
        if progress_callback:
            await progress_callback(10, 100, f"Found {len(files)} files, starting ingestion...")

        # Ingest each file through unified mediator
        document_ids = []
        total_chunks = 0
        total_entities = 0
        failed_files = []

        for idx, file_path in enumerate(files):
            # Progress: Per-file ingestion (10% to 90%)
            if progress_callback:
                file_progress = 10 + int((idx / len(files)) * 80)
                await progress_callback(
                    file_progress,
                    100,
                    f"Ingesting file {idx + 1}/{len(files)}: {file_path.name}..."
                )

            try:
                file_size = file_path.stat().st_size
                file_type = file_path.suffix.lstrip(".").lower() or "text"

                logger.info(f"Ingesting file through unified mediator: {file_path.name}")

                # Read file content
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Build metadata: merge user metadata with file metadata
                file_metadata = metadata.copy() if metadata else {}
                file_metadata.update({
                    "file_type": file_type,
                    "file_size": file_size,
                    "file_path": str(file_path.absolute()),  # NEW - for duplicate detection
                })

                # Note: Don't pass progress_callback here - would conflict with parent progress
                ingest_result = await unified_mediator.ingest_text(
                    content=content,
                    collection_name=collection_name,
                    document_title=file_path.name,
                    metadata=file_metadata,
                    progress_callback=None  # Skip nested progress for batch operations
                )
                document_ids.append(ingest_result["source_document_id"])
                total_chunks += ingest_result["num_chunks"]
                total_entities += ingest_result.get("entities_extracted", 0)

            except Exception as e:
                failed_files.append({"filename": file_path.name, "error": str(e)})

        result = {
            "files_found": len(files),
            "files_ingested": len(document_ids),
            "files_failed": len(failed_files),
            "total_chunks": total_chunks,
            "collection_name": collection_name,
            "entities_extracted": total_entities,
        }

        if include_document_ids:
            result["document_ids"] = document_ids

        if failed_files:
            result["failed_files"] = failed_files

        return result
    except Exception as e:
        logger.error(f"ingest_directory failed: {e}")
        raise


async def update_document_impl(
    db: Database,
    doc_store: DocumentStore,
    document_id: int,
    content: Optional[str],
    title: Optional[str],
    metadata: Optional[Dict[str, Any]],
    graph_store: Optional[GraphStore] = None,
) -> Dict[str, Any]:
    """
    Implementation of update_document tool.

    Updates document content, title, or metadata with health checks.
    If content changes, Graph episode is cleaned up and re-indexed.
    Performs health checks on both databases before update (Option B: Mandatory).
    """
    try:
        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        if not content and not title and not metadata:
            raise ValueError(
                "At least one of content, title, or metadata must be provided"
            )

        # Update RAG store (also deletes old graph episode if content changed)
        result = await doc_store.update_document(
            document_id=document_id,
            content=content,
            filename=title,
            metadata=metadata,
            graph_store=graph_store
        )

        # If content was updated, re-index into knowledge graph
        if content and graph_store and result.get("graph_episode_deleted"):
            logger.info(f"🕸️  Re-indexing document {document_id} into Knowledge Graph after content update")

            # Get updated document with merged metadata
            updated_doc = doc_store.get_source_document(document_id)
            if not updated_doc:
                raise ValueError(f"Document {document_id} not found after update")

            # Get collection name from chunks (since doc might be in multiple collections)
            conn = db.connect()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT c.name
                    FROM collections c
                    JOIN chunk_collections cc ON cc.collection_id = c.id
                    JOIN document_chunks dc ON dc.id = cc.chunk_id
                    WHERE dc.source_document_id = %s
                    LIMIT 1
                    """,
                    (document_id,)
                )
                row = cur.fetchone()
                collection_name = row[0] if row else "unknown"

            # Build graph metadata
            graph_metadata = updated_doc["metadata"].copy() if updated_doc["metadata"] else {}
            graph_metadata["collection_name"] = collection_name
            graph_metadata["document_title"] = updated_doc["filename"]

            # Re-index into graph
            try:
                entities = await graph_store.add_knowledge(
                    content=content,
                    source_document_id=document_id,
                    metadata=graph_metadata,
                    group_id=collection_name,
                    ingestion_timestamp=datetime.now()
                )
                logger.info(f"✅ Graph re-indexing completed - {len(entities)} entities extracted")
                result["entities_extracted"] = len(entities)
            except Exception as e:
                logger.error(f"❌ Graph re-indexing FAILED after RAG update (doc_id={document_id})")
                logger.error(f"   Error: {e}", exc_info=True)
                raise Exception(
                    f"Graph re-indexing failed after RAG update (doc_id={document_id}). "
                    f"Stores may be inconsistent. Error: {e}"
                )

        return result
    except Exception as e:
        logger.error(f"update_document failed: {e}")
        raise


async def delete_document_impl(
    db: Database,
    doc_store: DocumentStore,
    document_id: int,
    graph_store: Optional[GraphStore] = None,
) -> Dict[str, Any]:
    """
    Implementation of delete_document tool.

    Permanently removes document from RAG store and Graph.
    Performs health checks on both databases before deletion (Option B: Mandatory).

    ⚠️ WARNING: This operation is permanent and cannot be undone.
    """
    try:
        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        result = await doc_store.delete_document(document_id, graph_store=graph_store)
        return result
    except Exception as e:
        logger.error(f"delete_document failed: {e}")
        raise


def list_documents_impl(
    doc_store: DocumentStore,
    collection_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    include_details: bool = False,
) -> Dict[str, Any]:
    """
    Implementation of list_documents tool.

    Thin facade over DocumentStore.list_source_documents() business logic.
    """
    try:
        # Cap limit at 200
        if limit > 200:
            limit = 200

        # Call business logic layer
        result = doc_store.list_source_documents(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            include_details=include_details
        )

        # Convert datetime objects to ISO 8601 strings for JSON serialization
        for doc in result["documents"]:
            if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
                doc["created_at"] = doc["created_at"].isoformat()
            if "updated_at" in doc and hasattr(doc["updated_at"], "isoformat"):
                doc["updated_at"] = doc["updated_at"].isoformat()

        return result
    except Exception as e:
        logger.error(f"list_documents failed: {e}")
        raise


# =============================================================================
# Knowledge Graph Query Tools
# =============================================================================


async def query_relationships_impl(
    graph_store,
    query: str,
    collection_name: str | None = None,
    num_results: int = 5,
    threshold: float = 0.2,
) -> Dict[str, Any]:
    """
    Implementation of query_relationships tool.

    Searches the knowledge graph for entity relationships using natural language.
    Returns relationships (edges) between entities that match the query.

    Args:
        graph_store: GraphStore instance
        query: Natural language query
        collection_name: Optional collection to scope search
        num_results: Maximum number of results to return
        threshold: Minimum relevance score (0.0-1.0, default 0.2)
                  Higher = stricter filtering (fewer, more relevant results)
                  Lower = more permissive (more results, may include less relevant)
                  Strategy-specific defaults apply if not overridden
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph is not available. Only RAG search is enabled.",
                "relationships": []
            }

        # Convert collection_name to group_ids for internal implementation
        group_ids = [collection_name] if collection_name else None

        # Search the knowledge graph with specified threshold and collection scope
        results = await graph_store.search_relationships(
            query,
            num_results=num_results,
            reranker_min_score=threshold,
            group_ids=group_ids
        )

        # Handle both old API (object with .edges) and new API (returns list directly)
        if hasattr(results, 'edges'):
            edges = results.edges
        elif isinstance(results, list):
            edges = results
        else:
            edges = []

        # Convert edge objects to JSON-serializable dicts
        relationships = []
        for edge in edges[:num_results]:
            try:
                rel = {
                    "id": str(getattr(edge, 'uuid', '')),
                    "relationship_type": getattr(edge, 'name', 'RELATED_TO'),
                    "fact": getattr(edge, 'fact', ''),
                }

                # Add source and target entity info if available
                if hasattr(edge, 'source_node_uuid'):
                    rel["source_node_id"] = str(edge.source_node_uuid)
                if hasattr(edge, 'target_node_uuid'):
                    rel["target_node_id"] = str(edge.target_node_uuid)

                # Add when relationship was established (temporal info is for query_temporal only)
                if hasattr(edge, 'valid_at') and edge.valid_at:
                    rel["valid_from"] = edge.valid_at.isoformat()

                relationships.append(rel)
            except Exception as e:
                logger.warning(f"Failed to serialize edge: {e}")
                continue

        return {
            "status": "success",
            "query": query,
            "num_results": len(relationships),
            "relationships": relationships
        }

    except Exception as e:
        logger.error(f"query_relationships failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "relationships": []
        }


async def query_temporal_impl(
    graph_store,
    query: str,
    collection_name: str | None = None,
    num_results: int = 10,
    threshold: float = 0.2,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> Dict[str, Any]:
    """
    Implementation of query_temporal tool.

    Queries how knowledge has evolved over time. Shows facts with their
    temporal validity intervals to understand how information changed.

    Args:
        graph_store: GraphStore instance
        query: Natural language query about temporal changes
        collection_name: Optional collection to scope search
        num_results: Max results to return
        valid_from: (OPTIONAL) ISO 8601 date - filter facts valid after this date
        valid_until: (OPTIONAL) ISO 8601 date - filter facts valid before this date
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph is not available. Only RAG search is enabled.",
                "timeline": []
            }

        # Convert collection_name to group_ids for internal implementation
        group_ids = [collection_name] if collection_name else None

        # Delegate to GraphStore.search_temporal() - no direct Graphiti calls
        edges = await graph_store.search_temporal(
            query,
            num_results=num_results,
            reranker_min_score=threshold,
            group_ids=group_ids,
            valid_from=valid_from,
            valid_until=valid_until
        )

        # Convert to timeline format, grouped by temporal validity
        timeline_items = []
        for edge in edges[:num_results]:
            try:
                item = {
                    "fact": getattr(edge, 'fact', ''),
                    "relationship_type": getattr(edge, 'name', 'RELATED_TO'),
                }

                # Add temporal validity
                if hasattr(edge, 'valid_at') and edge.valid_at:
                    item["valid_from"] = edge.valid_at.isoformat()
                else:
                    item["valid_from"] = None

                if hasattr(edge, 'invalid_at') and edge.invalid_at:
                    item["valid_until"] = edge.invalid_at.isoformat()
                    item["status"] = "superseded"
                else:
                    item["valid_until"] = None
                    item["status"] = "current"

                # Add creation/expiration timestamps
                if hasattr(edge, 'created_at') and edge.created_at:
                    item["created_at"] = edge.created_at.isoformat()
                if hasattr(edge, 'expired_at') and edge.expired_at:
                    item["expired_at"] = edge.expired_at.isoformat()

                timeline_items.append(item)
            except Exception as e:
                logger.warning(f"Failed to serialize temporal edge: {e}")
                continue

        # Sort by valid_from date (most recent first)
        timeline_items.sort(
            key=lambda x: x.get('valid_from') or '',
            reverse=True
        )

        return {
            "status": "success",
            "query": query,
            "num_results": len(timeline_items),
            "timeline": timeline_items
        }

    except Exception as e:
        logger.error(f"query_temporal failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timeline": []
        }
