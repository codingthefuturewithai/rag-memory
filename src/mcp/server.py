"""
MCP Server for RAG pgvector POC.

Exposes RAG functionality via Model Context Protocol for AI agents.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.retrieval.search import get_similarity_search
from src.ingestion.document_store import get_document_store
from src.mcp.tools import (
    search_documents_impl,
    list_collections_impl,
    ingest_text_impl,
    get_document_by_id_impl,
    get_collection_info_impl,
    ingest_url_impl,
    ingest_file_impl,
    ingest_directory_impl,
    recrawl_url_impl,
    update_document_impl,
    delete_document_impl,
    list_documents_impl,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("rag-memory")

# Initialize RAG components once (reused across tool calls)
logger.info("Initializing RAG components...")
db = get_database()
embedder = get_embedding_generator()
coll_mgr = get_collection_manager(db)
searcher = get_similarity_search(db, embedder, coll_mgr)
doc_store = get_document_store(db, embedder, coll_mgr)

logger.info("MCP server initialized with RAG components")


# Tool definitions (FastMCP auto-generates from type hints + docstrings)


@mcp.tool()
def search_documents(
    query: str,
    collection_name: Optional[str] = None,
    limit: int = 5,
    threshold: float = 0.7,
    include_source: bool = False,
    include_metadata: bool = False,
) -> list[dict]:
    """
    Search for relevant document chunks using vector similarity.

    This is the primary RAG retrieval method. Uses OpenAI text-embedding-3-small
    embeddings with pgvector HNSW indexing for fast, accurate semantic search.

    By default, returns minimal response optimized for AI agent context windows
    (only content, similarity, source_document_id, and source_filename). Use
    include_metadata=True to get extended chunk details.

    Args:
        query: Natural language search query (e.g., "How do I configure GitHub Actions?")
        collection_name: Optional collection to scope search. If None, searches all collections.
        limit: Maximum number of results to return (default: 5, max: 50)
        threshold: Minimum similarity score 0-1 (default: 0.7). Lower = more permissive.
        include_source: If True, includes full source document content in results
        include_metadata: If True, includes chunk_id, chunk_index, char_start, char_end,
                         and metadata dict. Default: False (minimal response).

    Returns:
        List of matching chunks ordered by similarity (highest first).

        Minimal response (default, include_metadata=False):
        [
            {
                "content": str,  # Chunk content (~1000 chars)
                "similarity": float,  # 0-1, higher is better
                "source_document_id": int,  # For calling get_document_by_id()
                "source_filename": str,  # Document title/filename
                "source_content": str  # Full document (only if include_source=True)
            }
        ]

        Extended response (include_metadata=True):
        [
            {
                "content": str,
                "similarity": float,
                "source_document_id": int,
                "source_filename": str,
                "chunk_id": int,  # Internal chunk ID
                "chunk_index": int,  # Position in document (0-based)
                "char_start": int,  # Character position in source
                "char_end": int,
                "metadata": dict,  # Custom metadata from ingestion
                "source_content": str  # Only if include_source=True
            }
        ]

    Example:
        # Minimal response (recommended for most queries)
        results = search_documents(
            query="Python async programming",
            collection_name="tutorials",
            limit=3
        )

        # Extended response with all metadata
        results = search_documents(
            query="Python async programming",
            collection_name="tutorials",
            limit=3,
            include_metadata=True
        )

    Performance: ~400-500ms per query (includes embedding generation + vector search)
    """
    return search_documents_impl(
        searcher, query, collection_name, limit, threshold, include_source, include_metadata
    )


@mcp.tool()
def list_collections() -> list[dict]:
    """
    List all available document collections.

    Collections are named groups of documents (like folders for knowledge).
    Use this to discover what knowledge bases are available before searching.

    Returns:
        List of collections with metadata:
        [
            {
                "name": str,  # Collection identifier
                "description": str,  # Human-readable description
                "document_count": int,  # Number of source documents
                "created_at": str  # ISO 8601 timestamp
            }
        ]

    Example:
        collections = list_collections()
        # Find collection about Python
        python_colls = [c for c in collections if 'python' in c['name'].lower()]
    """
    return list_collections_impl(coll_mgr)


@mcp.tool()
def ingest_text(
    content: str,
    collection_name: str,
    document_title: Optional[str] = None,
    metadata: Optional[dict] = None,
    auto_create_collection: bool = True,
) -> dict:
    """
    Ingest text content into a collection with automatic chunking.

    This is the primary way for agents to add knowledge to the RAG system.
    Content is automatically chunked (~1000 chars with 200 char overlap),
    embedded with OpenAI, and stored for future retrieval.

    Args:
        content: Text content to ingest (any length, will be automatically chunked)
        collection_name: Collection to add content to
        document_title: Optional human-readable title for this document.
                       If not provided, auto-generates from timestamp.
                       Appears in search results as "Source: {document_title}"
        metadata: Optional metadata dict (e.g., {"topic": "python", "author": "agent"})
        auto_create_collection: If True, creates collection if it doesn't exist (default: True).
                               If False and collection doesn't exist, raises error.

    Returns:
        {
            "source_document_id": int,  # ID for retrieving full document later
            "chunk_ids": list[int],  # IDs of generated chunks
            "num_chunks": int,
            "collection_name": str,
            "collection_created": bool  # True if collection was auto-created
        }

    Example:
        result = ingest_text(
            content="Python is a high-level programming language...",
            collection_name="programming-tutorials",
            document_title="Python Basics",
            metadata={"language": "python", "level": "beginner"}
        )

    Note: This triggers OpenAI API calls for embeddings (~$0.00003 per document).
    """
    return ingest_text_impl(
        doc_store,
        content,
        collection_name,
        document_title,
        metadata,
        auto_create_collection,
    )


@mcp.tool()
def get_document_by_id(document_id: int, include_chunks: bool = False) -> dict:
    """
    Get a specific source document by ID.

    Useful when search returns a chunk and agent needs full document context.
    Document IDs come from search_documents() results (source_document_id field).

    Args:
        document_id: Source document ID (from search results)
        include_chunks: If True, includes list of all chunks with details

    Returns:
        {
            "id": int,
            "filename": str,  # Document title/identifier
            "content": str,  # Full document content
            "file_type": str,  # text, markdown, web_page, etc.
            "file_size": int,  # Bytes
            "metadata": dict,  # Custom metadata
            "created_at": str,  # ISO 8601
            "updated_at": str,  # ISO 8601
            "chunks": [  # Only if include_chunks=True
                {
                    "chunk_id": int,
                    "chunk_index": int,
                    "content": str,
                    "char_start": int,
                    "char_end": int
                }
            ]
        }

    Raises:
        ValueError: If document_id doesn't exist

    Example:
        # After search returns chunk with source_document_id=42
        doc = get_document_by_id(42)
        print(f"Full document: {doc['content']}")
    """
    return get_document_by_id_impl(doc_store, document_id, include_chunks)


@mcp.tool()
def get_collection_info(collection_name: str) -> dict:
    """
    Get detailed information about a specific collection.

    Helps agents understand collection scope before searching or adding content.

    Args:
        collection_name: Name of the collection

    Returns:
        {
            "name": str,
            "description": str,
            "document_count": int,  # Number of source documents
            "chunk_count": int,  # Total searchable chunks
            "created_at": str,  # ISO 8601
            "sample_documents": [str]  # First 5 document filenames
        }

    Raises:
        ValueError: If collection doesn't exist

    Example:
        info = get_collection_info("python-docs")
        print(f"Collection has {info['chunk_count']} searchable chunks")
    """
    return get_collection_info_impl(db, coll_mgr, collection_name)


@mcp.tool()
def ingest_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1,
    auto_create_collection: bool = True,
) -> dict:
    """
    Crawl and ingest content from a web URL.

    Uses Crawl4AI for web scraping. Supports single-page or multi-page crawling
    with link following. Automatically chunks content (~2500 chars for web pages).

    Args:
        url: URL to crawl and ingest (e.g., "https://docs.python.org/3/")
        collection_name: Collection to add content to
        follow_links: If True, follows internal links for multi-page crawl (default: False)
        max_depth: Maximum crawl depth when following links (default: 1, max: 3)
        auto_create_collection: Create collection if doesn't exist (default: True)

    Returns:
        {
            "pages_crawled": int,
            "pages_ingested": int,  # May be less if some pages failed
            "total_chunks": int,
            "document_ids": list[int],
            "collection_name": str,
            "collection_created": bool,
            "crawl_metadata": {
                "crawl_root_url": str,  # Starting URL
                "crawl_session_id": str,  # UUID for this crawl session
                "crawl_timestamp": str  # ISO 8601
            }
        }

    Example:
        # Single page
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs"
        )

        # Follow links 2 levels deep
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs",
            follow_links=True,
            max_depth=2
        )

    Note: Web crawling can be slow (1-5 seconds per page). Use follow_links sparingly.
    Metadata includes crawl_root_url for use with recrawl_url() later.
    """
    return ingest_url_impl(
        doc_store, url, collection_name, follow_links, max_depth, auto_create_collection
    )


@mcp.tool()
def ingest_file(
    file_path: str,
    collection_name: str,
    metadata: Optional[dict] = None,
    auto_create_collection: bool = True,
) -> dict:
    """
    Ingest a text-based file from the file system.

    IMPORTANT: Requires file system access. Most MCP agents should use
    ingest_text() or ingest_url() instead unless they have local file access.

    Supported file types (text-based only):
        ✓ Plain text (.txt, .md, .rst)
        ✓ Source code (.py, .js, .java, .go, .rs, .cpp, etc.)
        ✓ Config files (.json, .yaml, .xml, .toml, .ini, .env)
        ✓ Web files (.html, .css, .svg)
        ✓ Any UTF-8 or latin-1 encoded text file

    NOT supported (binary formats):
        ✗ PDF files (.pdf)
        ✗ Microsoft Office (.docx, .xlsx, .pptx)
        ✗ Images, videos, archives

    Args:
        file_path: Absolute path to the file (e.g., "/path/to/document.txt")
        collection_name: Collection to add to
        metadata: Optional metadata dict
        auto_create_collection: Create collection if doesn't exist (default: True)

    Returns:
        {
            "source_document_id": int,
            "chunk_ids": list[int],
            "num_chunks": int,
            "filename": str,  # Extracted from path
            "file_type": str,  # Extracted from extension
            "file_size": int,  # Bytes
            "collection_name": str,
            "collection_created": bool
        }

    Raises:
        FileNotFoundError: If file doesn't exist
        UnicodeDecodeError: If file is binary/not text

    Example:
        result = ingest_file(
            file_path="/Users/agent/documents/report.txt",
            collection_name="reports",
            metadata={"year": 2025, "department": "engineering"}
        )
    """
    return ingest_file_impl(
        doc_store, file_path, collection_name, metadata, auto_create_collection
    )


@mcp.tool()
def ingest_directory(
    directory_path: str,
    collection_name: str,
    file_extensions: Optional[list[str]] = None,
    recursive: bool = False,
    auto_create_collection: bool = True,
) -> dict:
    """
    Ingest multiple text-based files from a directory.

    IMPORTANT: Requires file system access. Most MCP agents should use
    ingest_text() or ingest_url() instead unless they have local file access.

    Only processes text-based files (see ingest_file for supported types).
    Binary files and files without matching extensions are skipped.

    Args:
        directory_path: Absolute path to directory (e.g., "/path/to/docs")
        collection_name: Collection to add all files to
        file_extensions: List of extensions to process (e.g., [".txt", ".md"]).
                        If None, defaults to [".txt", ".md"]
        recursive: If True, searches subdirectories (default: False)
        auto_create_collection: Create collection if doesn't exist (default: True)

    Returns:
        {
            "files_found": int,
            "files_ingested": int,
            "files_failed": int,
            "total_chunks": int,
            "document_ids": list[int],
            "collection_name": str,
            "collection_created": bool,
            "failed_files": [  # Only if files_failed > 0
                {
                    "filename": str,
                    "error": str
                }
            ]
        }

    Example:
        # Ingest all markdown files in directory
        result = ingest_directory(
            directory_path="/Users/agent/knowledge-base",
            collection_name="kb",
            file_extensions=[".md", ".txt"],
            recursive=True
        )

        print(f"Ingested {result['files_ingested']} files with {result['total_chunks']} chunks")
    """
    return ingest_directory_impl(
        doc_store,
        directory_path,
        collection_name,
        file_extensions,
        recursive,
        auto_create_collection,
    )


@mcp.tool()
def recrawl_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1,
) -> dict:
    """
    Re-crawl a URL by deleting old pages and re-ingesting fresh content.

    This is the "nuclear option" for keeping web documentation up-to-date.
    Finds all documents where metadata.crawl_root_url matches the specified URL,
    deletes those documents and chunks, then re-crawls and re-ingests.

    Other documents in the collection (from different URLs or manual ingestion)
    are unaffected. This allows multiple documentation sources in one collection.

    Args:
        url: URL to re-crawl (must match original crawl_root_url)
        collection_name: Collection containing the documents
        follow_links: If True, follows internal links (default: False)
        max_depth: Maximum crawl depth when following links (default: 1)

    Returns:
        {
            "old_pages_deleted": int,
            "new_pages_crawled": int,
            "new_pages_ingested": int,
            "total_chunks": int,
            "document_ids": list[int],
            "collection_name": str
        }

    Example:
        # Re-crawl documentation site
        result = recrawl_url(
            url="https://docs.example.com",
            collection_name="example-docs",
            follow_links=True,
            max_depth=2
        )

        print(f"Replaced {result['old_pages_deleted']} old pages with {result['new_pages_ingested']} new pages")

    Note: Only deletes documents from this specific crawl_root_url.
    Safe for collections with multiple documentation sources.
    """
    return recrawl_url_impl(
        doc_store, db, url, collection_name, follow_links, max_depth
    )


@mcp.tool()
def update_document(
    document_id: int,
    content: Optional[str] = None,
    title: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Update an existing document's content, title, or metadata.

    This is essential for agent memory management. When information changes
    (e.g., company vision updates, personal info corrections), agents can
    update existing knowledge rather than creating duplicates.

    If content is provided, the document is automatically re-chunked and
    re-embedded with new vectors. Old chunks are deleted and replaced.
    Collection membership is preserved across updates.

    Args:
        document_id: ID of document to update (from search results or list_documents)
        content: New content (optional). Triggers full re-chunking and re-embedding.
        title: New title/filename (optional)
        metadata: New metadata (optional). Merged with existing metadata, not replaced.

    Returns:
        {
            "document_id": int,
            "updated_fields": list[str],  # e.g., ["content", "metadata"]
            "old_chunk_count": int,  # Only if content updated
            "new_chunk_count": int   # Only if content updated
        }

    Example:
        # Update company vision
        result = update_document(
            document_id=42,
            content="New company vision: We focus on AI agent development...",
            metadata={"status": "approved", "version": "2.0"}
        )

        # Just update metadata
        result = update_document(
            document_id=42,
            metadata={"last_reviewed": "2025-10-12"}
        )

    Raises:
        ValueError: If document_id doesn't exist or no fields provided

    Note: Metadata is merged with existing values. To remove a key,
    use delete_document and re-ingest instead.
    """
    return update_document_impl(doc_store, document_id, content, title, metadata)


@mcp.tool()
def delete_document(document_id: int) -> dict:
    """
    Delete a source document and all its chunks permanently.

    Essential for agent memory management. When information becomes outdated,
    incorrect, or no longer relevant, agents can remove it to prevent
    retrieval of stale knowledge.

    This is a permanent operation and cannot be undone. All chunks derived
    from the document are also deleted (cascade). However, other documents
    in the same collections are unaffected.

    Args:
        document_id: ID of document to delete (from search results or list_documents)

    Returns:
        {
            "document_id": int,
            "document_title": str,
            "chunks_deleted": int,
            "collections_affected": list[str]  # Collections that had this document
        }

    Example:
        # Delete outdated documentation
        result = delete_document(42)
        print(f"Deleted '{result['document_title']}' with {result['chunks_deleted']} chunks")
        print(f"Affected collections: {result['collections_affected']}")

    Raises:
        ValueError: If document_id doesn't exist

    Note: This does NOT delete collections, only removes the document from them.
    Use with caution - deletion is permanent.
    """
    return delete_document_impl(doc_store, document_id)


@mcp.tool()
def list_documents(
    collection_name: Optional[str] = None, limit: int = 50, offset: int = 0
) -> dict:
    """
    List source documents in the knowledge base.

    Useful for agents to discover what documents exist before updating or
    deleting them. Can be scoped to a specific collection or list all documents.

    Args:
        collection_name: Optional collection to filter by. If None, lists all documents.
        limit: Maximum number of documents to return (default: 50, max: 200)
        offset: Number of documents to skip for pagination (default: 0)

    Returns:
        {
            "documents": [
                {
                    "id": int,
                    "filename": str,
                    "file_type": str,
                    "file_size": int,
                    "chunk_count": int,
                    "created_at": str,  # ISO 8601
                    "updated_at": str,  # ISO 8601
                    "collections": list[str],  # Collections this document belongs to
                    "metadata": dict  # Custom metadata
                }
            ],
            "total_count": int,  # Total documents matching filter
            "returned_count": int,  # Documents in this response
            "has_more": bool  # Whether more pages available
        }

    Example:
        # List all documents in collection
        result = list_documents(collection_name="company-knowledge")
        for doc in result['documents']:
            print(f"{doc['id']}: {doc['filename']} ({doc['chunk_count']} chunks)")

        # Paginate through all documents
        result = list_documents(limit=50, offset=0)
        while result['has_more']:
            # Process documents
            result = list_documents(limit=50, offset=result['returned_count'])
    """
    return list_documents_impl(db, coll_mgr, collection_name, limit, offset)


def main():
    """Run the MCP server."""
    logger.info("Starting RAG memory MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
