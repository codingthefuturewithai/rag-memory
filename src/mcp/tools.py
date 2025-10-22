"""
Tool implementation functions for MCP server.

These are wrappers around existing RAG functionality, converting to/from
MCP-compatible formats (JSON-serializable dicts).
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.database import Database
from src.core.collections import CollectionManager
from src.retrieval.search import SimilaritySearch
from src.ingestion.document_store import DocumentStore
from src.ingestion.web_crawler import WebCrawler, crawl_single_page
from src.ingestion.website_analyzer import analyze_website
from src.unified.graph_store import GraphStore

logger = logging.getLogger(__name__)


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


def create_collection_impl(
    coll_mgr: CollectionManager, name: str, description: str
) -> Dict[str, Any]:
    """Implementation of create_collection tool."""
    try:
        collection_id = coll_mgr.create_collection(name, description)

        return {
            "collection_id": collection_id,
            "name": name,
            "description": description,
            "created": True
        }
    except ValueError as e:
        # Collection already exists
        logger.warning(f"create_collection failed: {e}")
        raise
    except Exception as e:
        logger.error(f"create_collection failed: {e}")
        raise


def update_collection_description_impl(
    coll_mgr: CollectionManager, name: str, description: str
) -> Dict[str, Any]:
    """
    Implementation of update_collection_description tool.

    Thin facade over CollectionManager.update_description() business logic.
    """
    try:
        # Call business logic layer
        coll_mgr.update_description(name, description)

        return {
            "name": name,
            "description": description,
            "updated": True
        }
    except ValueError as e:
        logger.warning(f"update_collection_description failed: {e}")
        raise
    except Exception as e:
        logger.error(f"update_collection_description failed: {e}")
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
        deleted = coll_mgr.delete_collection(name)

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
) -> Dict[str, Any]:
    """
    Implementation of ingest_text tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).
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

        # Route through unified mediator (RAG + Graph)
        logger.info("Ingesting text through unified mediator (RAG + Graph)")
        result = await unified_mediator.ingest_text(
            content=content,
            collection_name=collection_name,
            document_title=document_title,
            metadata=metadata
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


def analyze_website_impl(
    base_url: str,
    timeout: int = 10,
    include_url_lists: bool = False,
    max_urls_per_pattern: int = 10
) -> Dict[str, Any]:
    """
    Implementation of analyze_website tool.

    Extracts raw data about website structure (sitemap parsing, URL grouping).
    NO recommendations or heuristics - just facts for AI agent to reason about.

    By default, returns only pattern_stats summary (lightweight). Agent can request
    full URL lists if needed by setting include_url_lists=True.
    """
    try:
        result = analyze_website(base_url, timeout, include_url_lists, max_urls_per_pattern)
        return result
    except Exception as e:
        logger.error(f"analyze_website failed: {e}")
        raise


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


async def ingest_url_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1,
    mode: str = "crawl",
    include_document_ids: bool = False,
) -> Dict[str, Any]:
    """
    Implementation of ingest_url tool with mode support.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before crawling (Option B: Mandatory).

    Args:
        mode: "crawl" (new crawl, error if exists) or "recrawl" (update existing)
    """
    try:
        # Health check: both PostgreSQL and Neo4j must be reachable
        health_error = await ensure_databases_healthy(db, graph_store)
        if health_error:
            return health_error

        # Validate mode
        if mode not in ["crawl", "recrawl"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'crawl' or 'recrawl'")

        # Check collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)

        if not collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist. "
                f"Create it first using create_collection('{collection_name}', 'description')."
            )

        # Check for existing crawl
        existing_crawl = check_existing_crawl(db, url, collection_name)

        if mode == "crawl" and existing_crawl:
            raise ValueError(
                f"URL '{url}' has already been crawled into collection '{collection_name}'.\n"
                f"Existing crawl: {existing_crawl['page_count']} pages, "
                f"{existing_crawl['chunk_count']} chunks, "
                f"timestamp: {existing_crawl['crawl_timestamp']}\n"
                f"To update existing content, use mode='recrawl'."
            )

        # If recrawl mode, delete old documents first
        old_pages_deleted = 0
        if mode == "recrawl" and existing_crawl:
            conn = db.connect()
            with conn.cursor() as cur:
                # Find all documents with matching crawl_root_url
                cur.execute(
                    """
                    SELECT id, filename
                    FROM source_documents
                    WHERE metadata->>'crawl_root_url' = %s
                    """,
                    (url,),
                )
                existing_docs = cur.fetchall()

                old_pages_deleted = len(existing_docs)

                # Delete Graph episodes first (if available)
                if graph_store:
                    logger.info(f"🗑️  Deleting {old_pages_deleted} Graph episodes for recrawl of {url}")
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

        # Crawl web pages
        if follow_links:
            crawler = WebCrawler(headless=True, verbose=False)
            results = await crawler.crawl_with_depth(url, max_depth=max_depth)
        else:
            result = await crawl_single_page(url, headless=True, verbose=False)
            results = [result] if result.success else []

        # Ingest each page (route through unified mediator if available)
        document_ids = []
        total_chunks = 0
        total_entities = 0
        successful_ingests = 0

        for result in results:
            if not result.success:
                continue

            try:
                page_title = result.metadata.get("title", result.url)

                logger.info(f"Ingesting page through unified mediator: {page_title}")
                ingest_result = await unified_mediator.ingest_text(
                    content=result.content,
                    collection_name=collection_name,
                    document_title=page_title,
                    metadata=result.metadata
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

        if mode == "recrawl":
            response["old_pages_deleted"] = old_pages_deleted

        if include_document_ids:
            response["document_ids"] = document_ids

        return response
    except Exception as e:
        logger.error(f"ingest_url failed: {e}")
        raise


async def ingest_file_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    file_path: str,
    collection_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    include_chunk_ids: bool = False,
) -> Dict[str, Any]:
    """
    Implementation of ingest_file tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).
    """
    try:
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

        file_size = path.stat().st_size
        file_type = path.suffix.lstrip(".").lower() or "text"

        logger.info(f"Ingesting file through unified mediator: {path.name}")

        # Read file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Merge file metadata with user metadata
        file_metadata = metadata.copy() if metadata else {}
        file_metadata.update({
            "file_type": file_type,
            "file_size": file_size,
        })

        ingest_result = await unified_mediator.ingest_text(
            content=content,
            collection_name=collection_name,
            document_title=path.name,
            metadata=file_metadata
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


async def ingest_directory_impl(
    db: Database,
    doc_store: DocumentStore,
    unified_mediator,
    graph_store: Optional[GraphStore],
    directory_path: str,
    collection_name: str,
    file_extensions: Optional[List[str]] = None,
    recursive: bool = False,
    include_document_ids: bool = False,
) -> Dict[str, Any]:
    """
    Implementation of ingest_directory tool.

    Routes through unified mediator to update both RAG and Knowledge Graph.
    Performs health checks on both databases before ingestion (Option B: Mandatory).
    """
    try:
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

        # Find files
        files = []
        for ext in file_extensions:
            if recursive:
                files.extend(path.rglob(f"*{ext}"))
            else:
                files.extend(path.glob(f"*{ext}"))

        files = sorted(set(files))

        # Ingest each file through unified mediator
        document_ids = []
        total_chunks = 0
        total_entities = 0
        failed_files = []

        for file_path in files:
            try:
                file_size = file_path.stat().st_size
                file_type = file_path.suffix.lstrip(".").lower() or "text"

                logger.info(f"Ingesting file through unified mediator: {file_path.name}")

                # Read file content
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Build metadata
                file_metadata = {
                    "file_type": file_type,
                    "file_size": file_size,
                }

                ingest_result = await unified_mediator.ingest_text(
                    content=content,
                    collection_name=collection_name,
                    document_title=file_path.name,
                    metadata=file_metadata
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

        result = await doc_store.update_document(
            document_id=document_id,
            content=content,
            filename=title,
            metadata=metadata,
            graph_store=graph_store
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
    num_results: int = 5,
) -> Dict[str, Any]:
    """
    Implementation of query_relationships tool.

    Searches the knowledge graph for entity relationships using natural language.
    Returns relationships (edges) between entities that match the query.
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph is not available. Only RAG search is enabled.",
                "relationships": []
            }

        # Search the knowledge graph
        results = await graph_store.search_relationships(query, num_results=num_results)

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
    num_results: int = 10,
) -> Dict[str, Any]:
    """
    Implementation of query_temporal tool.

    Queries how knowledge has evolved over time. Shows facts with their
    temporal validity intervals to understand how information changed.
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph is not available. Only RAG search is enabled.",
                "timeline": []
            }

        # Search the knowledge graph (Graphiti handles temporal queries automatically)
        results = await graph_store.search_relationships(query, num_results=num_results)

        # Handle both old API (object with .edges) and new API (returns list directly)
        if hasattr(results, 'edges'):
            edges = results.edges
        elif isinstance(results, list):
            edges = results
        else:
            edges = []

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
                    item["status"] = "expired"
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
