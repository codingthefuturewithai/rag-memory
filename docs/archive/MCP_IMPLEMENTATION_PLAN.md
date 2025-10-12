# MCP Server Implementation Plan

**Date:** 2025-10-11
**Branch:** `feature/mcp-server`
**Goal:** Expose RAG functionality via Model Context Protocol (MCP) for AI agents

---

## Executive Summary

Implement an MCP server that exposes this RAG system's core functionality to any MCP-compatible AI agent (Claude Desktop, Cursor, OpenAI agents, etc.). Focus on **tools only** (no prompts/resources initially) using **vector-only search** (baseline, not hybrid).

**Key Decision:** Only expose baseline vector search - hybrid/multi-query search remain CLI-only until proven valuable.

**Total Tools:** 12 (3 essential, 9 enhanced)
- **NEW:** Complete CRUD operations added - `list_documents`, `update_document`, `delete_document` for agent memory management

---

## Model Context Protocol (MCP) Overview

### What is MCP?

MCP is Anthropic's open standard for connecting AI agents to external systems. Think "USB-C for AI" - provides standardized way for agents to discover and use capabilities.

**Officially adopted by:**
- Anthropic (Claude Desktop, Claude Code)
- OpenAI (ChatGPT Desktop, Agents SDK - March 2025)
- Google DeepMind (Gemini - April 2025)

### Core MCP Concepts

1. **Tools**: Functions agents can call (like `search_documents`, `ingest_text`)
2. **Resources**: Static/dynamic data agents can request (future: `collection://{name}`)
3. **Prompts**: Templated guidance for agents (future: `search_and_answer`)

**This implementation: Tools only.**

### Python MCP SDK

**Installation:**
```bash
uv add "mcp[cli]"
```

**Official SDK:** `modelcontextprotocol/python-sdk` on GitHub

**Architecture:**
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ServerName")

@mcp.tool()
def my_tool(param: str) -> dict:
    """Tool description for agents"""
    return {"result": "value"}
```

**Key Features:**
- Auto-generates tool definitions from Python type hints and docstrings
- Handles protocol compliance and message routing
- Supports multiple transports (stdio, SSE, HTTP)
- Easy integration with existing Python code

---

## MCP Tools to Implement

### Priority: High (MVP - Core RAG Operations)

#### 1. `search_documents` ⭐ ESSENTIAL

**Purpose:** Core RAG retrieval - vector similarity search

```python
@mcp.tool()
def search_documents(
    query: str,
    collection_name: str | None = None,
    limit: int = 5,
    threshold: float = 0.7,
    include_source: bool = False
) -> list[dict]:
    """
    Search for relevant document chunks using vector similarity.

    This is the primary RAG retrieval method. Uses OpenAI text-embedding-3-small
    embeddings with pgvector HNSW indexing for fast, accurate semantic search.

    Args:
        query: Natural language search query (e.g., "How do I configure GitHub Actions?")
        collection_name: Optional collection to scope search. If None, searches all collections.
        limit: Maximum number of results to return (default: 5, max: 50)
        threshold: Minimum similarity score 0-1 (default: 0.7). Lower = more permissive.
        include_source: If True, includes full source document content in results

    Returns:
        List of matching chunks ordered by similarity (highest first):
        [
            {
                "chunk_id": int,
                "source_document_id": int,
                "source_filename": str,
                "chunk_index": int,
                "similarity": float,  # 0-1, higher is better
                "content": str,  # Chunk content (~1000 chars)
                "char_start": int,  # Position in source document
                "char_end": int,
                "metadata": dict,  # Custom metadata
                "source_content": str  # Full document (if include_source=True)
            }
        ]

    Example:
        results = search_documents(
            query="Python async programming",
            collection_name="tutorials",
            limit=3
        )

    Performance: ~400-500ms per query (includes embedding generation + vector search)
    """
```

**Implementation:**
- Wraps `SimilaritySearch.search_chunks()` from `src/retrieval/search.py`
- Uses existing baseline vector search (proven 81% recall)
- Returns serializable dict format (convert `ChunkSearchResult` objects)

---

#### 2. `list_collections` ⭐ ESSENTIAL

**Purpose:** Discover available knowledge bases

```python
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
```

**Implementation:**
- Wraps `CollectionManager.list_collections()` from `src/core/collections.py`
- Already returns dict format
- Convert datetime to ISO 8601 string

---

#### 3. `ingest_text` ⭐ ESSENTIAL

**Purpose:** Add raw text content to knowledge base

```python
@mcp.tool()
def ingest_text(
    content: str,
    collection_name: str,
    document_title: str | None = None,
    metadata: dict | None = None,
    auto_create_collection: bool = True
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
```

**Implementation:**
- Wraps `DocumentStore.ingest_document()` from `src/ingestion/document_store.py`
- Auto-generate `document_title` if not provided: `f"Agent-Text-{datetime.now().isoformat()}"`
- Collection auto-creation already implemented in `DocumentStore.ingest_document()`
- Add `collection_created` flag to return value

---

### Priority: Medium (Enhanced Functionality)

#### 4. `get_document_by_id`

**Purpose:** Retrieve full source document from search results

```python
@mcp.tool()
def get_document_by_id(
    document_id: int,
    include_chunks: bool = False
) -> dict:
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
```

**Implementation:**
- Wraps `DocumentStore.get_source_document()` and `DocumentStore.get_document_chunks()`
- Convert datetime objects to ISO 8601 strings
- Raise `ValueError` if document not found

---

#### 5. `get_collection_info`

**Purpose:** Detailed collection statistics

```python
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
```

**Implementation:**
- Wraps `CollectionManager.get_collection()`
- Add custom queries for `chunk_count` and `sample_documents`
- Raise `ValueError` if collection not found

---

#### 6. `ingest_url`

**Purpose:** Crawl and ingest web content

```python
@mcp.tool()
def ingest_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1,
    auto_create_collection: bool = True
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
```

**Implementation:**
- Wraps web crawler from `src/ingestion/web_crawler.py`
- Uses same logic as CLI `ingest url` command
- Return crawl metadata for recrawl tracking

---

#### 7. `ingest_file`

**Purpose:** Ingest text file from file system

```python
@mcp.tool()
def ingest_file(
    file_path: str,
    collection_name: str,
    metadata: dict | None = None,
    auto_create_collection: bool = True
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
```

**Implementation:**
- Wraps `DocumentStore.ingest_file()` from `src/ingestion/document_store.py`
- Already handles UTF-8/latin-1 fallback
- Return enriched result with file metadata

---

#### 8. `ingest_directory`

**Purpose:** Batch ingest files from directory

```python
@mcp.tool()
def ingest_directory(
    directory_path: str,
    collection_name: str,
    file_extensions: list[str] | None = None,
    recursive: bool = False,
    auto_create_collection: bool = True
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
```

**Implementation:**
- Wraps CLI `ingest directory` logic from `src/cli.py`
- Uses `Path.glob()` and `Path.rglob()` for file discovery
- Track failures and report them

---

#### 9. `recrawl_url`

**Purpose:** Update web documentation (delete old + re-ingest)

```python
@mcp.tool()
def recrawl_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1
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
```

**Implementation:**
- Wraps CLI `recrawl` command logic from `src/cli.py`
- Query `source_documents` where `metadata->>'crawl_root_url' = url`
- Delete old docs, then call `ingest_url()`

---

#### 10. `update_document` ⭐ NEW - ESSENTIAL

**Purpose:** Edit existing document content, title, or metadata

```python
@mcp.tool()
def update_document(
    document_id: int,
    content: str | None = None,
    title: str | None = None,
    metadata: dict | None = None
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
```

**Implementation:**
- Wraps `DocumentStore.update_document()` from `src/ingestion/document_store.py:345-476`
- Handles content updates with automatic re-chunking and re-embedding
- Preserves collection links across chunk replacement
- Metadata merge strategy prevents accidental data loss

---

#### 11. `delete_document` ⭐ NEW - ESSENTIAL

**Purpose:** Remove outdated or incorrect documents

```python
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
```

**Implementation:**
- Wraps `DocumentStore.delete_document()` from `src/ingestion/document_store.py:478-534`
- Cascade deletion of chunks (handled by database foreign key)
- Provides feedback on affected collections
- No confirmation prompt (caller should handle if needed)

---

#### 12. `list_documents`

**Purpose:** Discover available documents for update/delete operations

```python
@mcp.tool()
def list_documents(
    collection_name: str | None = None,
    limit: int = 50,
    offset: int = 0
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
```

**Implementation:**
- Query `source_documents` with optional collection join
- Include chunk count per document
- Support pagination for large document sets
- Return collection names for each document

---

## Implementation Architecture

### File Structure

```
rag-pgvector-poc/
├── src/
│   └── mcp/
│       ├── __init__.py
│       ├── server.py           # Main MCP server with FastMCP
│       └── tools.py            # Tool implementations (wrappers)
├── pyproject.toml              # Add mcp dependency
├── MCP_IMPLEMENTATION_PLAN.md  # This document
└── README.md                   # Update with MCP usage
```

### Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing ...
    "mcp>=1.0.0",  # Official MCP SDK
]
```

### Core Implementation: `src/mcp/server.py`

```python
"""
MCP Server for RAG pgvector POC.

Exposes RAG functionality via Model Context Protocol for AI agents.
"""

import logging
from datetime import datetime
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

logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("RAG-pgvector")

# Initialize RAG components once (reused across tool calls)
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
    collection_name: str | None = None,
    limit: int = 5,
    threshold: float = 0.7,
    include_source: bool = False
) -> list[dict]:
    """
    Search for relevant document chunks using vector similarity.
    [Full docstring from plan above]
    """
    return search_documents_impl(
        searcher, query, collection_name, limit, threshold, include_source
    )


@mcp.tool()
def list_collections() -> list[dict]:
    """
    List all available document collections.
    [Full docstring from plan above]
    """
    return list_collections_impl(coll_mgr)


@mcp.tool()
def ingest_text(
    content: str,
    collection_name: str,
    document_title: str | None = None,
    metadata: dict | None = None,
    auto_create_collection: bool = True
) -> dict:
    """
    Ingest text content into a collection with automatic chunking.
    [Full docstring from plan above]
    """
    return ingest_text_impl(
        doc_store, content, collection_name, document_title, metadata, auto_create_collection
    )


@mcp.tool()
def get_document_by_id(
    document_id: int,
    include_chunks: bool = False
) -> dict:
    """
    Get a specific source document by ID.
    [Full docstring from plan above]
    """
    return get_document_by_id_impl(doc_store, document_id, include_chunks)


@mcp.tool()
def get_collection_info(collection_name: str) -> dict:
    """
    Get detailed information about a specific collection.
    [Full docstring from plan above]
    """
    return get_collection_info_impl(db, coll_mgr, collection_name)


@mcp.tool()
def ingest_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1,
    auto_create_collection: bool = True
) -> dict:
    """
    Crawl and ingest content from a web URL.
    [Full docstring from plan above]
    """
    return ingest_url_impl(
        doc_store, url, collection_name, follow_links, max_depth, auto_create_collection
    )


@mcp.tool()
def ingest_file(
    file_path: str,
    collection_name: str,
    metadata: dict | None = None,
    auto_create_collection: bool = True
) -> dict:
    """
    Ingest a text-based file from the file system.
    [Full docstring from plan above]
    """
    return ingest_file_impl(doc_store, file_path, collection_name, metadata, auto_create_collection)


@mcp.tool()
def ingest_directory(
    directory_path: str,
    collection_name: str,
    file_extensions: list[str] | None = None,
    recursive: bool = False,
    auto_create_collection: bool = True
) -> dict:
    """
    Ingest multiple text-based files from a directory.
    [Full docstring from plan above]
    """
    return ingest_directory_impl(
        doc_store, directory_path, collection_name, file_extensions, recursive, auto_create_collection
    )


@mcp.tool()
def recrawl_url(
    url: str,
    collection_name: str,
    follow_links: bool = False,
    max_depth: int = 1
) -> dict:
    """
    Re-crawl a URL by deleting old pages and re-ingesting fresh content.
    [Full docstring from plan above]
    """
    return recrawl_url_impl(doc_store, db, url, collection_name, follow_links, max_depth)


@mcp.tool()
def update_document(
    document_id: int,
    content: str | None = None,
    title: str | None = None,
    metadata: dict | None = None
) -> dict:
    """
    Update an existing document's content, title, or metadata.
    [Full docstring from plan above]
    """
    return update_document_impl(doc_store, document_id, content, title, metadata)


@mcp.tool()
def delete_document(document_id: int) -> dict:
    """
    Delete a source document and all its chunks permanently.
    [Full docstring from plan above]
    """
    return delete_document_impl(doc_store, document_id)


@mcp.tool()
def list_documents(
    collection_name: str | None = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """
    List source documents in the knowledge base.
    [Full docstring from plan above]
    """
    return list_documents_impl(db, coll_mgr, collection_name, limit, offset)


def main():
    """Run the MCP server."""
    logger.info("Starting RAG pgvector MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
```

### Tool Implementations: `src/mcp/tools.py`

```python
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

logger = logging.getLogger(__name__)


def search_documents_impl(
    searcher: SimilaritySearch,
    query: str,
    collection_name: Optional[str],
    limit: int,
    threshold: float,
    include_source: bool
) -> List[Dict[str, Any]]:
    """Implementation of search_documents tool."""
    try:
        # Execute search
        results = searcher.search_chunks(
            query=query,
            limit=min(limit, 50),  # Cap at 50
            threshold=threshold if threshold is not None else 0.0,
            collection_name=collection_name,
            include_source=include_source
        )

        # Convert ChunkSearchResult objects to dicts
        return [
            {
                "chunk_id": r.chunk_id,
                "source_document_id": r.source_document_id,
                "source_filename": r.source_filename,
                "chunk_index": r.chunk_index,
                "similarity": float(r.similarity),
                "content": r.content,
                "char_start": r.char_start,
                "char_end": r.char_end,
                "metadata": r.metadata or {},
                "source_content": r.source_content if include_source else None
            }
            for r in results
        ]
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
                "created_at": c["created_at"].isoformat() if c.get("created_at") else None
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
    auto_create_collection: bool
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
            raise ValueError(f"Collection '{collection_name}' does not exist and auto_create_collection=False")

        if not collection:
            collection_created = True

        # Ingest document (auto-creates collection if needed)
        source_id, chunk_ids = doc_store.ingest_document(
            content=content,
            filename=document_title,
            collection_name=collection_name,
            metadata=metadata,
            file_type="text"
        )

        return {
            "source_document_id": source_id,
            "chunk_ids": chunk_ids,
            "num_chunks": len(chunk_ids),
            "collection_name": collection_name,
            "collection_created": collection_created
        }
    except Exception as e:
        logger.error(f"ingest_text failed: {e}")
        raise


def get_document_by_id_impl(
    doc_store: DocumentStore,
    document_id: int,
    include_chunks: bool
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
            "updated_at": doc["updated_at"].isoformat()
        }

        if include_chunks:
            chunks = doc_store.get_document_chunks(document_id)
            result["chunks"] = [
                {
                    "chunk_id": c["id"],
                    "chunk_index": c["chunk_index"],
                    "content": c["content"],
                    "char_start": c["char_start"],
                    "char_end": c["char_end"]
                }
                for c in chunks
            ]

        return result
    except Exception as e:
        logger.error(f"get_document_by_id failed: {e}")
        raise


def get_collection_info_impl(
    db: Database,
    coll_mgr: CollectionManager,
    collection_name: str
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
                (collection["id"],)
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
                (collection["id"],)
            )
            sample_docs = [row[0] for row in cur.fetchall()]

        return {
            "name": collection["name"],
            "description": collection["description"] or "",
            "document_count": collection.get("document_count", 0),
            "chunk_count": chunk_count,
            "created_at": collection["created_at"].isoformat(),
            "sample_documents": sample_docs
        }
    except Exception as e:
        logger.error(f"get_collection_info failed: {e}")
        raise


def ingest_url_impl(
    doc_store: DocumentStore,
    url: str,
    collection_name: str,
    follow_links: bool,
    max_depth: int,
    auto_create_collection: bool
) -> Dict[str, Any]:
    """Implementation of ingest_url tool."""
    try:
        # Check collection
        collection = doc_store.collection_mgr.get_collection(collection_name)
        collection_created = False

        if not collection and not auto_create_collection:
            raise ValueError(f"Collection '{collection_name}' does not exist and auto_create_collection=False")

        if not collection:
            collection_created = True

        # Crawl web pages
        if follow_links:
            crawler = WebCrawler(headless=True, verbose=False)
            results = asyncio.run(crawler.crawl_with_depth(url, max_depth=max_depth))
        else:
            result = asyncio.run(crawl_single_page(url, headless=True, verbose=False))
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
                    file_type="web_page"
                )
                document_ids.append(source_id)
                total_chunks += len(chunk_ids)
                successful_ingests += 1
            except Exception as e:
                logger.warning(f"Failed to ingest page {result.url}: {e}")

        return {
            "pages_crawled": len(results),
            "pages_ingested": successful_ingests,
            "total_chunks": total_chunks,
            "document_ids": document_ids,
            "collection_name": collection_name,
            "collection_created": collection_created,
            "crawl_metadata": {
                "crawl_root_url": url,
                "crawl_session_id": results[0].metadata.get("crawl_session_id") if results else None,
                "crawl_timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"ingest_url failed: {e}")
        raise


def ingest_file_impl(
    doc_store: DocumentStore,
    file_path: str,
    collection_name: str,
    metadata: Optional[Dict[str, Any]],
    auto_create_collection: bool
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
            raise ValueError(f"Collection '{collection_name}' does not exist and auto_create_collection=False")

        if not collection:
            collection_created = True

        # Ingest file
        source_id, chunk_ids = doc_store.ingest_file(
            file_path=file_path,
            collection_name=collection_name,
            metadata=metadata
        )

        return {
            "source_document_id": source_id,
            "chunk_ids": chunk_ids,
            "num_chunks": len(chunk_ids),
            "filename": path.name,
            "file_type": path.suffix.lstrip(".").lower() or "text",
            "file_size": path.stat().st_size,
            "collection_name": collection_name,
            "collection_created": collection_created
        }
    except Exception as e:
        logger.error(f"ingest_file failed: {e}")
        raise


def ingest_directory_impl(
    doc_store: DocumentStore,
    directory_path: str,
    collection_name: str,
    file_extensions: Optional[List[str]],
    recursive: bool,
    auto_create_collection: bool
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
            raise ValueError(f"Collection '{collection_name}' does not exist and auto_create_collection=False")

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
                    file_path=str(file_path),
                    collection_name=collection_name
                )
                document_ids.append(source_id)
                total_chunks += len(chunk_ids)
            except Exception as e:
                failed_files.append({
                    "filename": file_path.name,
                    "error": str(e)
                })

        result = {
            "files_found": len(files),
            "files_ingested": len(document_ids),
            "files_failed": len(failed_files),
            "total_chunks": total_chunks,
            "document_ids": document_ids,
            "collection_name": collection_name,
            "collection_created": collection_created
        }

        if failed_files:
            result["failed_files"] = failed_files

        return result
    except Exception as e:
        logger.error(f"ingest_directory failed: {e}")
        raise


def recrawl_url_impl(
    doc_store: DocumentStore,
    db: Database,
    url: str,
    collection_name: str,
    follow_links: bool,
    max_depth: int
) -> Dict[str, Any]:
    """Implementation of recrawl_url tool."""
    try:
        # Find existing documents with matching crawl_root_url
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, filename
                FROM source_documents
                WHERE metadata->>'crawl_root_url' = %s
                """,
                (url,)
            )
            existing_docs = cur.fetchall()

        old_pages_deleted = len(existing_docs)

        # Delete old documents and chunks
        for doc_id, filename in existing_docs:
            with conn.cursor() as cur:
                # Delete chunks
                cur.execute(
                    "DELETE FROM document_chunks WHERE source_document_id = %s",
                    (doc_id,)
                )
                # Delete source document
                cur.execute(
                    "DELETE FROM source_documents WHERE id = %s",
                    (doc_id,)
                )

        # Re-crawl and ingest
        ingest_result = ingest_url_impl(
            doc_store, url, collection_name, follow_links, max_depth, auto_create_collection=False
        )

        return {
            "old_pages_deleted": old_pages_deleted,
            "new_pages_crawled": ingest_result["pages_crawled"],
            "new_pages_ingested": ingest_result["pages_ingested"],
            "total_chunks": ingest_result["total_chunks"],
            "document_ids": ingest_result["document_ids"],
            "collection_name": collection_name
        }
    except Exception as e:
        logger.error(f"recrawl_url failed: {e}")
        raise


def update_document_impl(
    doc_store: DocumentStore,
    document_id: int,
    content: Optional[str],
    title: Optional[str],
    metadata: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Implementation of update_document tool."""
    try:
        if not content and not title and not metadata:
            raise ValueError("At least one of content, title, or metadata must be provided")

        result = doc_store.update_document(
            document_id=document_id,
            content=content,
            filename=title,
            metadata=metadata
        )

        return result
    except Exception as e:
        logger.error(f"update_document failed: {e}")
        raise


def delete_document_impl(
    doc_store: DocumentStore,
    document_id: int
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
    offset: int
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
                    (collection["id"],)
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
                    (collection["id"], limit, offset)
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
                    (limit, offset)
                )
                rows = cur.fetchall()

        # For each document, get its collections
        documents = []
        for row in rows:
            doc_id, filename, file_type, file_size, created_at, updated_at, metadata, chunk_count = row

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
                    (doc_id,)
                )
                collections = [c[0] for c in cur.fetchall()]

            documents.append({
                "id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                "chunk_count": chunk_count,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
                "collections": collections,
                "metadata": metadata or {}
            })

        return {
            "documents": documents,
            "total_count": total_count,
            "returned_count": len(documents),
            "has_more": (offset + len(documents)) < total_count
        }
    except Exception as e:
        logger.error(f"list_documents failed: {e}")
        raise
```

---

## Testing Strategy

### Manual Testing with MCP Inspector

MCP Inspector is a GUI tool for testing MCP servers without integrating with AI agents.

**Install:**
```bash
npx @modelcontextprotocol/inspector
```

**Test each tool:**
1. `search_documents` - Search existing `claude-agent-sdk` collection
2. `list_collections` - Should return all collections
3. `ingest_text` - Add test content, verify searchable
4. `get_document_by_id` - Retrieve document from step 3
5. `get_collection_info` - Get stats for test collection
6. `list_documents` - List documents in test collection
7. `update_document` - Update document from step 3, verify re-chunking
8. `delete_document` - Delete test document, verify removal
9. File-based tools - Test with temp files (if agent has file access)

### Integration Testing with Claude Desktop

1. Configure Claude Desktop to use MCP server
2. Test natural language queries: "Search for Python tutorials"
3. Test agent workflows: "Find docs on X, then add summary to Y collection"

---

## Future Enhancements (Not Implementing Now)

### Resources (Phase 2)

Passive data access without side effects:

```python
@mcp.resource("collection://{name}")
def get_collection(name: str) -> str:
    """Get collection details as formatted text"""

@mcp.resource("document://{id}")
def get_document(id: int) -> str:
    """Get full document content"""
```

### Prompts (Phase 2)

Guidance templates for agents:

```python
@mcp.prompt()
def search_and_answer(question: str, collection: str | None = None) -> str:
    """
    Prompt template for RAG-based question answering.
    Guides agent to search, review results, synthesize answer, cite sources.
    """
```

---

## Documentation Updates

### Update `README.md`

Add section:

```markdown
## MCP Server Usage

This RAG system can be accessed by AI agents via Model Context Protocol (MCP).

### Starting the MCP Server

```bash
uv run python -m src.mcp.server
```

### Connecting with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-pgvector": {
      "command": "uv",
      "args": ["run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

### Available Tools

**Core RAG Operations:**
- `search_documents` - Vector similarity search
- `list_collections` - Discover knowledge bases
- `ingest_text` - Add content from agent
- `ingest_url` - Crawl web documentation

**Document Management (NEW):**
- `list_documents` - List available documents
- `update_document` - Edit existing documents (re-chunks & re-embeds)
- `delete_document` - Remove outdated documents

**And 5 more...** See `MCP_IMPLEMENTATION_PLAN.md` for full documentation.
```

### Update `CLAUDE.md`

Add section on MCP server for future Claude Code sessions.

---

## Implementation Checklist

### Phase 1: Setup & Core Tools (MVP)
- [ ] Create feature branch `feature/mcp-server`
- [ ] Add `mcp` dependency to `pyproject.toml`
- [ ] Create `src/mcp/__init__.py`
- [ ] Implement `src/mcp/tools.py` with all tool implementations
- [ ] Implement `src/mcp/server.py` with FastMCP
- [ ] Test with MCP Inspector:
  - [ ] `search_documents`
  - [ ] `list_collections`
  - [ ] `ingest_text`

### Phase 2: Extended Tools
- [ ] Test remaining tools with MCP Inspector:
  - [ ] `get_document_by_id`
  - [ ] `get_collection_info`
  - [ ] `list_documents` ⭐ NEW
  - [ ] `update_document` ⭐ NEW - ESSENTIAL
  - [ ] `delete_document` ⭐ NEW - ESSENTIAL
  - [ ] `ingest_url`
  - [ ] `ingest_file`
  - [ ] `ingest_directory`
  - [ ] `recrawl_url`

### Phase 3: Documentation & Integration
- [ ] Update `README.md` with MCP usage
- [ ] Update `CLAUDE.md` with MCP server info
- [ ] Test with Claude Desktop integration
- [ ] Document any issues or limitations discovered

### Phase 4: Merge
- [ ] Commit all changes
- [ ] Merge `feature/mcp-server` to `main`
- [ ] Tag release: `v0.4.0-mcp-server`

---

## Success Criteria

✅ **MVP Complete When:**
1. MCP server starts without errors
2. Claude Desktop can discover and call tools
3. `search_documents` successfully retrieves results
4. `ingest_text` successfully adds content
5. `list_collections` returns current collections

✅ **Full Implementation Complete When:**
1. All 12 tools tested and working (9 original + 3 new CRUD tools)
2. Documentation updated
3. Integration tested with Claude Desktop
4. Merged to main

---

## Notes

- **Vector-only search**: Only baseline search exposed. Hybrid/multi-query remain CLI-only per project decision.
- **Text files only**: File ingestion limited to text-based formats (no PDF/Office docs).
- **Auto-create collections**: Default behavior, optional parameter to disable.
- **Comprehensive docstrings**: Every tool must have detailed docstring for agent understanding.
- **Error handling**: All tool implementations should catch and re-raise with clear error messages.

---

**End of Implementation Plan**

This document will be used as the reference for implementing the MCP server overnight.
