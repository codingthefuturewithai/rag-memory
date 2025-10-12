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

logger = logging.getLogger(__name__)


def search_documents_impl(
    searcher: SimilaritySearch,
    query: str,
    collection_name: Optional[str],
    limit: int,
    threshold: float,
    include_source: bool,
    include_metadata: bool,
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


def ingest_text_impl(
    doc_store: DocumentStore,
    content: str,
    collection_name: str,
    document_title: Optional[str],
    metadata: Optional[Dict[str, Any]],
    auto_create_collection: bool,
    include_chunk_ids: bool,
) -> Dict[str, Any]:
    """Implementation of ingest_text tool."""
    try:
        # Auto-generate title if not provided
        if not document_title:
            document_title = f"Agent-Text-{datetime.now().isoformat()}"

        # Check if collection exists
        collection = doc_store.collection_mgr.get_collection(collection_name)
        collection_created = False

        if not collection and not auto_create_collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist and auto_create_collection=False"
            )

        if not collection:
            collection_created = True

        # Ingest document (auto-creates collection if needed)
        source_id, chunk_ids = doc_store.ingest_document(
            content=content,
            filename=document_title,
            collection_name=collection_name,
            metadata=metadata,
            file_type="text",
        )

        result = {
            "source_document_id": source_id,
            "num_chunks": len(chunk_ids),
            "collection_name": collection_name,
            "collection_created": collection_created,
        }

        if include_chunk_ids:
            result["chunk_ids"] = chunk_ids

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
    doc_store: DocumentStore,
    db: Database,
    url: str,
    collection_name: str,
    follow_links: bool,
    max_depth: int,
    mode: str,
    auto_create_collection: bool,
    include_document_ids: bool,
) -> Dict[str, Any]:
    """
    Implementation of ingest_url tool with mode support.

    Args:
        mode: "crawl" (new crawl, error if exists) or "recrawl" (update existing)
    """
    try:
        # Validate mode
        if mode not in ["crawl", "recrawl"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'crawl' or 'recrawl'")

        # Check collection
        collection = doc_store.collection_mgr.get_collection(collection_name)
        collection_created = False

        if not collection and not auto_create_collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist and auto_create_collection=False"
            )

        if not collection:
            collection_created = True

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

                # Delete old documents and chunks
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

        # Ingest each page
        document_ids = []
        total_chunks = 0
        successful_ingests = 0

        for result in results:
            if not result.success:
                continue

            try:
                source_id, chunk_ids = doc_store.ingest_document(
                    content=result.content,
                    filename=result.metadata.get("title", result.url),
                    collection_name=collection_name,
                    metadata=result.metadata,
                    file_type="web_page",
                )
                document_ids.append(source_id)
                total_chunks += len(chunk_ids)
                successful_ingests += 1
            except Exception as e:
                logger.warning(f"Failed to ingest page {result.url}: {e}")

        response = {
            "mode": mode,
            "pages_crawled": len(results),
            "pages_ingested": successful_ingests,
            "total_chunks": total_chunks,
            "collection_name": collection_name,
            "collection_created": collection_created,
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


def ingest_file_impl(
    doc_store: DocumentStore,
    file_path: str,
    collection_name: str,
    metadata: Optional[Dict[str, Any]],
    auto_create_collection: bool,
    include_chunk_ids: bool,
) -> Dict[str, Any]:
    """Implementation of ingest_file tool."""
    try:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check collection
        collection = doc_store.collection_mgr.get_collection(collection_name)
        collection_created = False

        if not collection and not auto_create_collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist and auto_create_collection=False"
            )

        if not collection:
            collection_created = True

        # Ingest file
        source_id, chunk_ids = doc_store.ingest_file(
            file_path=file_path, collection_name=collection_name, metadata=metadata
        )

        result = {
            "source_document_id": source_id,
            "num_chunks": len(chunk_ids),
            "filename": path.name,
            "file_type": path.suffix.lstrip(".").lower() or "text",
            "file_size": path.stat().st_size,
            "collection_name": collection_name,
            "collection_created": collection_created,
        }

        if include_chunk_ids:
            result["chunk_ids"] = chunk_ids

        return result
    except Exception as e:
        logger.error(f"ingest_file failed: {e}")
        raise


def ingest_directory_impl(
    doc_store: DocumentStore,
    directory_path: str,
    collection_name: str,
    file_extensions: Optional[List[str]],
    recursive: bool,
    auto_create_collection: bool,
    include_document_ids: bool,
) -> Dict[str, Any]:
    """Implementation of ingest_directory tool."""
    try:
        path = Path(directory_path)

        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")

        # Check collection
        collection = doc_store.collection_mgr.get_collection(collection_name)
        collection_created = False

        if not collection and not auto_create_collection:
            raise ValueError(
                f"Collection '{collection_name}' does not exist and auto_create_collection=False"
            )

        if not collection:
            collection_created = True

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

        # Ingest each file
        document_ids = []
        total_chunks = 0
        failed_files = []

        for file_path in files:
            try:
                source_id, chunk_ids = doc_store.ingest_file(
                    file_path=str(file_path), collection_name=collection_name
                )
                document_ids.append(source_id)
                total_chunks += len(chunk_ids)
            except Exception as e:
                failed_files.append({"filename": file_path.name, "error": str(e)})

        result = {
            "files_found": len(files),
            "files_ingested": len(document_ids),
            "files_failed": len(failed_files),
            "total_chunks": total_chunks,
            "collection_name": collection_name,
            "collection_created": collection_created,
        }

        if include_document_ids:
            result["document_ids"] = document_ids

        if failed_files:
            result["failed_files"] = failed_files

        return result
    except Exception as e:
        logger.error(f"ingest_directory failed: {e}")
        raise


def update_document_impl(
    doc_store: DocumentStore,
    document_id: int,
    content: Optional[str],
    title: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Implementation of update_document tool."""
    try:
        if not content and not title and not metadata:
            raise ValueError(
                "At least one of content, title, or metadata must be provided"
            )

        result = doc_store.update_document(
            document_id=document_id, content=content, filename=title, metadata=metadata
        )

        return result
    except Exception as e:
        logger.error(f"update_document failed: {e}")
        raise


def delete_document_impl(
    doc_store: DocumentStore, document_id: int
) -> Dict[str, Any]:
    """Implementation of delete_document tool."""
    try:
        result = doc_store.delete_document(document_id)
        return result
    except Exception as e:
        logger.error(f"delete_document failed: {e}")
        raise


def list_documents_impl(
    db: Database,
    coll_mgr: CollectionManager,
    collection_name: Optional[str],
    limit: int,
    offset: int,
    include_details: bool,
) -> Dict[str, Any]:
    """Implementation of list_documents tool."""
    try:
        # Cap limit at 200
        limit = min(limit, 200)

        conn = db.connect()

        # Build query based on collection filter
        if collection_name:
            # Get collection ID
            collection = coll_mgr.get_collection(collection_name)
            if not collection:
                raise ValueError(f"Collection '{collection_name}' not found")

            # Query documents in specific collection
            with conn.cursor() as cur:
                # Get total count
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT sd.id)
                    FROM source_documents sd
                    JOIN document_chunks dc ON dc.source_document_id = sd.id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    WHERE cc.collection_id = %s
                    """,
                    (collection["id"],),
                )
                total_count = cur.fetchone()[0]

                # Get paginated documents
                cur.execute(
                    """
                    SELECT DISTINCT
                        sd.id,
                        sd.filename,
                        sd.file_type,
                        sd.file_size,
                        sd.created_at,
                        sd.updated_at,
                        sd.metadata,
                        (SELECT COUNT(*) FROM document_chunks WHERE source_document_id = sd.id) as chunk_count
                    FROM source_documents sd
                    JOIN document_chunks dc ON dc.source_document_id = sd.id
                    JOIN chunk_collections cc ON cc.chunk_id = dc.id
                    WHERE cc.collection_id = %s
                    ORDER BY sd.updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (collection["id"], limit, offset),
                )
                rows = cur.fetchall()
        else:
            # Query all documents
            with conn.cursor() as cur:
                # Get total count
                cur.execute("SELECT COUNT(*) FROM source_documents")
                total_count = cur.fetchone()[0]

                # Get paginated documents
                cur.execute(
                    """
                    SELECT
                        sd.id,
                        sd.filename,
                        sd.file_type,
                        sd.file_size,
                        sd.created_at,
                        sd.updated_at,
                        sd.metadata,
                        (SELECT COUNT(*) FROM document_chunks WHERE source_document_id = sd.id) as chunk_count
                    FROM source_documents sd
                    ORDER BY sd.updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()

        # For each document, get its collections
        documents = []
        for row in rows:
            (
                doc_id,
                filename,
                file_type,
                file_size,
                created_at,
                updated_at,
                metadata,
                chunk_count,
            ) = row

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
                    (doc_id,),
                )
                collections = [c[0] for c in cur.fetchall()]

            # Minimal response by default (optimized for AI agent context windows)
            doc_dict = {
                "id": doc_id,
                "filename": filename,
                "chunk_count": chunk_count,
            }

            # Optionally include extended details
            if include_details:
                doc_dict.update({
                    "file_type": file_type,
                    "file_size": file_size,
                    "created_at": created_at.isoformat(),
                    "updated_at": updated_at.isoformat(),
                    "collections": collections,
                    "metadata": metadata or {},
                })

            documents.append(doc_dict)

        return {
            "documents": documents,
            "total_count": total_count,
            "returned_count": len(documents),
            "has_more": (offset + len(documents)) < total_count,
        }
    except Exception as e:
        logger.error(f"list_documents failed: {e}")
        raise
