"""
MCP Server for RAG Memory.

Exposes RAG functionality via Model Context Protocol for AI agents.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.core.first_run import ensure_config_or_exit
from src.core.config_loader import load_environment_variables
from src.retrieval.search import get_similarity_search
from src.ingestion.document_store import get_document_store
from src.unified import GraphStore, UnifiedIngestionMediator
from src.mcp.tools import (
    search_documents_impl,
    list_collections_impl,
    create_collection_impl,
    get_collection_metadata_schema_impl,
    delete_collection_impl,
    ingest_text_impl,
    get_document_by_id_impl,
    get_collection_info_impl,
    analyze_website_impl,
    ingest_url_impl,
    ingest_file_impl,
    ingest_directory_impl,
    update_document_impl,
    delete_document_impl,
    list_documents_impl,
    query_relationships_impl,
    query_temporal_impl,
)

# Configure cross-platform file logging
log_dir = Path(__file__).parent.parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "mcp_server.log"),
        logging.StreamHandler()  # Also log to stderr for debugging
    ]
)
logger = logging.getLogger(__name__)

# Global variables to hold RAG components (initialized by lifespan)
db = None
embedder = None
coll_mgr = None
searcher = None
doc_store = None

# Global variables for Knowledge Graph components
graph_store = None
unified_mediator = None


@asynccontextmanager
async def lifespan(app: FastMCP):
    """
    Lifespan context manager for MCP server initialization and teardown.

    This initializes RAG components when the server starts, making them
    available to all tools. Components are initialized lazily here rather
    than at module import time to avoid issues with MCP client startup.
    """
    global db, embedder, coll_mgr, searcher, doc_store
    global graph_store, unified_mediator

    # Load configuration from YAML files before initializing components
    load_environment_variables()

    # Initialize RAG components when server starts (MANDATORY per Gap 2.1)
    logger.info("Initializing RAG components...")
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        searcher = get_similarity_search(db, embedder, coll_mgr)
        doc_store = get_document_store(db, embedder, coll_mgr)
        logger.info("RAG components initialized successfully")
    except Exception as e:
        # FAIL-FAST per Gap 2.1 (Option B): PostgreSQL is mandatory
        # Do not start server if PostgreSQL is unreachable
        logger.error(f"FATAL: RAG initialization failed (PostgreSQL unavailable): {e}")
        logger.error("Gap 2.1 (Option B: Mandatory Graph) requires both PostgreSQL and Neo4j to be operational.")
        logger.error("Please ensure PostgreSQL is running and accessible, then restart the server.")
        raise SystemExit(1)

    # Initialize Knowledge Graph components (MANDATORY per Gap 2.1, Option B: All or Nothing)
    logger.info("Initializing Knowledge Graph components...")
    try:
        from graphiti_core import Graphiti

        # Read Neo4j connection details from environment (docker-compose.graphiti.yml)
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        await graphiti.build_indices_and_constraints()

        graph_store = GraphStore(graphiti)
        unified_mediator = UnifiedIngestionMediator(db, embedder, coll_mgr, graph_store)
        logger.info("Knowledge Graph components initialized successfully")
    except Exception as e:
        # FAIL-FAST per Gap 2.1 (Option B): Knowledge Graph is mandatory
        # Do not start server if Neo4j is unreachable
        logger.error(f"FATAL: Knowledge Graph initialization failed (Neo4j unavailable): {e}")
        logger.error("Gap 2.1 (Option B: Mandatory Graph) requires both PostgreSQL and Neo4j to be operational.")
        logger.error("Please ensure Neo4j is running and accessible, then restart the server.")
        raise SystemExit(1)

    # Validate PostgreSQL schema (only at startup)
    logger.info("Validating PostgreSQL schema...")
    try:
        pg_validation = await db.validate_schema()
        if pg_validation["status"] != "valid":
            logger.error("FATAL: PostgreSQL schema validation failed")
            for error in pg_validation["errors"]:
                logger.error(f"  - {error}")
            raise SystemExit(1)
        logger.info(
            f"PostgreSQL schema valid ✓ "
            f"(tables: 3/3, pgvector: {'✓' if pg_validation['pgvector_loaded'] else '✗'}, "
            f"indexes: {pg_validation['hnsw_indexes']}/2)"
        )
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"FATAL: PostgreSQL schema validation error: {e}")
        raise SystemExit(1)

    # Validate Neo4j schema (only at startup)
    logger.info("Validating Neo4j schema...")
    try:
        graph_validation = await graph_store.validate_schema()
        if graph_validation["status"] != "valid":
            logger.error("FATAL: Neo4j schema validation failed")
            for error in graph_validation["errors"]:
                logger.error(f"  - {error}")
            raise SystemExit(1)
        logger.info(
            f"Neo4j schema valid ✓ "
            f"(indexes: {graph_validation['indexes_found']}, queryable: "
            f"{'✓' if graph_validation['can_query_nodes'] else '✗'})"
        )
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"FATAL: Neo4j schema validation error: {e}")
        raise SystemExit(1)

    logger.info("All startup validations passed - server ready ✓")

    yield {}  # Server runs here

    # Cleanup on shutdown
    logger.info("Shutting down MCP server...")
    if graph_store:
        await graph_store.close()
    if db:
        db.close()


# Initialize FastMCP server (no authentication)
mcp = FastMCP("rag-memory", lifespan=lifespan)


# Tool definitions (FastMCP auto-generates from type hints + docstrings)


@mcp.tool()
def search_documents(
    query: str,
    collection_name: str | None = None,
    limit: int = 5,
    threshold: float = 0.35,
    include_source: bool = False,
    include_metadata: bool = False,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """
    Search for relevant document chunks using vector similarity.

    This is the primary RAG retrieval method. Uses OpenAI text-embedding-3-small
    embeddings with pgvector HNSW indexing for fast, accurate semantic search.

    **IMPORTANT - Query Format:**
    This tool uses SEMANTIC SEARCH with vector embeddings, NOT keyword search.
    You MUST use natural language queries (complete sentences/questions), not keywords.

    ✅ GOOD QUERIES (natural language):
        - "How do I create custom tools in the Agent SDK?"
        - "What's the best way to handle errors in my code?"
        - "Show me examples of parallel subagent execution"

    ❌ BAD QUERIES (keywords - these will fail):
        - "custom tools register createTool implementation"
        - "error handling exceptions try catch"
        - "subagent parallel concurrent execution"

    TIP: Ask questions as if talking to a person. The system understands meaning,
    not just matching words.

    By default, returns minimal response optimized for AI agent context windows
    (only content, similarity, source_document_id, and source_filename). Use
    include_metadata=True to get extended chunk details.

    Args:
        query: (REQUIRED) Natural language search query - use complete sentences, not keywords!
        collection_name: Optional collection to scope search. If None, searches all collections.
        limit: Maximum number of results to return (default: 5, max: 50)
        threshold: Minimum similarity score 0-1 (default: 0.35). Lower = more permissive.
                  Score interpretation for text-embedding-3-small:
                  - 0.60+: Excellent match (highly relevant)
                  - 0.40-0.60: Good match (semantically related)
                  - 0.25-0.40: Moderate match (may be relevant)
                  - <0.25: Weak match (likely not relevant)
                  Results are always sorted by similarity (best first).
                  Set threshold=None to return all results ranked by relevance.
        include_source: If True, includes full source document content in results
        include_metadata: If True, includes chunk_id, chunk_index, char_start, char_end,
                         and metadata dict. Default: False (minimal response).
        metadata_filter: Optional dict for filtering by custom metadata fields (e.g., {"domain": "backend"}).
                        All fields must match (AND logic). Default: None (no filtering).

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
        searcher, query, collection_name, limit, threshold, include_source, include_metadata, metadata_filter
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
def create_collection(
    name: str, description: str, metadata_schema: dict = None
) -> dict:
    """
    Create a new collection with an optional metadata schema.

    Collections are required before ingesting documents. Each collection must
    have a meaningful description to help users understand its purpose.

    Once created, collections are immutable - you cannot change the description or schema.
    If you need to change it, delete the collection and create a new one.

    Args:
        name: (REQUIRED) Collection identifier (unique, lowercase recommended)
        description: (REQUIRED) Human-readable description of the collection's purpose.
                    Collections without descriptions are not allowed.
        metadata_schema: (OPTIONAL) Fixed metadata schema declaration.
                        Format: {
                            "custom": {
                                "field_name": {
                                    "type": "string|number|boolean|array|object",
                                    "required": false,
                                    "enum": ["value1", "value2"]
                                }
                            },
                            "system": ["field1", "field2"]
                        }
                        Defaults to empty schema if not provided.

    Returns:
        {
            "collection_id": int,
            "name": str,
            "description": str,
            "metadata_schema": dict,
            "created": bool  # Always True on success
        }

    Raises:
        ValueError: If collection with this name already exists or schema is invalid

    Example:
        result = create_collection(
            name="python-docs",
            description="Official Python documentation and tutorials",
            metadata_schema={
                "custom": {
                    "version": {"type": "string"},
                    "status": {"type": "string", "enum": ["draft", "published"]}
                },
                "system": ["file_type", "ingested_at"]
            }
        )
    """
    return create_collection_impl(coll_mgr, name, description, metadata_schema)


@mcp.tool()
def get_collection_metadata_schema(collection_name: str) -> dict:
    """
    Get the metadata schema for a collection.

    Allows clients to discover what metadata fields are available and required
    for ingesting documents into a collection before attempting ingest.

    Args:
        collection_name: (REQUIRED) Name of the collection

    Returns:
        {
            "collection_name": str,
            "description": str,
            "metadata_schema": {
                "custom": {...},
                "system": [...]
            },
            "custom_fields": {
                "field_name": "type",
                ...
            },
            "system_fields": [...],
            "document_count": int
        }

    Raises:
        ValueError: If collection doesn't exist

    Example:
        result = get_collection_metadata_schema("python-docs")
        # Use result["custom_fields"] to discover available metadata fields
    """
    return get_collection_metadata_schema_impl(coll_mgr, collection_name)


@mcp.tool()
async def delete_collection(name: str, confirm: bool = False) -> dict:
    """
    ⚠️ DESTRUCTIVE: Permanently delete a collection and all its documents.

    This operation CANNOT be undone. Deletes the collection, all associated documents,
    and all their indexed content.

    **REQUIRED: Two-Step Confirmation**
    1. Call with `confirm=False` (default) → Returns error requiring explicit confirmation
    2. Call with `confirm=True` → Actually deletes (prevents accidental deletion)

    **What gets deleted:**
    - The collection itself
    - All documents in this collection
    - All indexed content from those documents
    - All associated metadata

    **What stays:**
    - Other collections (unaffected)
    - Documents also in other collections (collection link removed, documents preserved)

    **Important Notes:**
    - If a document only belongs to this collection, it is completely removed
    - If a document is in multiple collections, only this collection link is removed
    - The two-step confirmation process exists specifically to prevent accidents

    Args:
        name: Collection name to delete (must exist)
        confirm: Must be exactly True to proceed. Default False.
                 False → Returns error. True → Performs deletion.

    Returns:
        On success:
        {
            "name": str,      # Collection that was deleted
            "deleted": bool,  # True
            "message": str    # Confirmation message with operation details
        }

    Raises:
        ValueError: If confirm != True or collection doesn't exist

    Example:
        # Step 1: Get confirmation requirement
        result = delete_collection(name="old-docs")  # Returns error, requires confirm=True

        # Step 2: Explicit deletion
        result = delete_collection(name="old-docs", confirm=True)  # Permanently deletes
        print(result["message"])  # Confirmation with details
    """
    return await delete_collection_impl(coll_mgr, name, confirm, graph_store, db)


@mcp.tool()
async def ingest_text(
    content: str,
    collection_name: str,
    document_title: str | None = None,
    metadata: dict | None = None,
    include_chunk_ids: bool = False,
) -> dict:
    """
    Ingest text content into a collection with automatic chunking.

    This is the primary way for agents to add knowledge to the RAG system.
    Content is chunked, embedded, and ingested into both vector store and knowledge graph.

    IMPORTANT: Collection must exist before ingesting. Use create_collection() first.

    IMPORTANT - PROCESSING TIME:
    Processing time depends on content size:
    - Small content (<10KB): Typically completes in seconds
    - Large content (>50KB): Can take a minute or longer

    The MCP server will continue processing even if your client times out. You may need
    to configure longer timeout values when ingesting large amounts of content.

    By default, returns minimal response (source_document_id and num_chunks).
    Use include_chunk_ids=True to get the list of chunk IDs (may be large).

    Args:
        content: (REQUIRED) Text content to ingest (any length, will be automatically chunked)
        collection_name: (REQUIRED) Collection to add content to (must already exist)
        document_title: Optional human-readable title for this document.
                       If not provided, auto-generates from timestamp.
                       Appears in search results as "Source: {document_title}"
        metadata: Optional metadata dict (e.g., {"topic": "python", "author": "agent"})
        include_chunk_ids: If True, includes list of chunk IDs. Default: False (minimal response).

    Returns:
        Minimal response (default):
        {
            "source_document_id": int,  # ID for retrieving full document later
            "num_chunks": int,
            "collection_name": str
        }

        Extended response (include_chunk_ids=True):
        {
            "source_document_id": int,
            "num_chunks": int,
            "collection_name": str,
            "chunk_ids": list[int]  # IDs of generated chunks
        }

    Raises:
        ValueError: If collection doesn't exist

    Example:
        # First, create collection
        create_collection("programming-tutorials", "Python programming examples")

        # Then ingest content
        result = ingest_text(
            content="Python is a high-level programming language...",
            collection_name="programming-tutorials",
            document_title="Python Basics",
            metadata={"language": "python", "level": "beginner"}
        )

    Note: This triggers OpenAI API calls for embeddings (~$0.00003 per document).
    """
    return await ingest_text_impl(
        db,
        doc_store,
        unified_mediator,
        graph_store,
        content,
        collection_name,
        document_title,
        metadata,
        include_chunk_ids,
    )


@mcp.tool()
def get_document_by_id(document_id: int, include_chunks: bool = False) -> dict:
    """
    Get a specific source document by ID.

    Useful when search returns a chunk and agent needs full document context.
    Document IDs come from search_documents() results (source_document_id field).

    Args:
        document_id: (REQUIRED) Source document ID (from search results)
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
    Includes crawl history to help avoid duplicate crawls.

    Args:
        collection_name: (REQUIRED) Name of the collection

    Returns:
        {
            "name": str,
            "description": str,
            "document_count": int,  # Number of source documents
            "chunk_count": int,  # Total searchable chunks
            "created_at": str,  # ISO 8601
            "sample_documents": [str],  # First 5 document filenames
            "crawled_urls": [  # Web pages that have been crawled into this collection
                {
                    "url": str,  # crawl_root_url
                    "timestamp": str,  # When crawled
                    "page_count": int,  # Number of pages from this URL
                    "chunk_count": int  # Number of chunks from this URL
                }
            ]
        }

    Raises:
        ValueError: If collection doesn't exist

    Example:
        info = get_collection_info("python-docs")
        print(f"Collection has {info['chunk_count']} searchable chunks")

        # Check if URL already crawled
        for crawl in info['crawled_urls']:
            print(f"Previously crawled: {crawl['url']} ({crawl['page_count']} pages)")
    """
    return get_collection_info_impl(db, coll_mgr, collection_name)


@mcp.tool()
def analyze_website(
    base_url: str,
    timeout: int = 10,
    include_url_lists: bool = False,
    max_urls_per_pattern: int = 10
) -> dict:
    """
    Analyze website structure to help plan comprehensive crawling.

    Fetches sitemap.xml and extracts URL patterns to help agents understand
    website organization BEFORE crawling. This prevents incomplete crawls
    by revealing all sections of a site (e.g., /api/*, /docs/*, /guides/*).

    Returns RAW DATA only - NO recommendations or heuristics. The AI agent
    uses its LLM to interpret the URL patterns and decide what to crawl.

    IMPORTANT: Must provide the website ROOT URL, not a specific page.
    - ✓ CORRECT: "https://docs.example.com" or "https://docs.example.com/"
    - ✗ WRONG: "https://docs.example.com/en/api/overview"

    The tool looks for sitemap.xml at the root (e.g., /sitemap.xml). Providing
    a specific page URL will fail to find the sitemap.

    VOLUME CONTROL: By default, returns only pattern_stats summary (lightweight,
    optimized for context window). For large sites with 1000s of URLs, this
    prevents overwhelming the agent. Set include_url_lists=True only if you
    need specific URLs from patterns.

    Args:
        base_url: (REQUIRED) Website ROOT URL (e.g., "https://docs.example.com")
                 Must be the domain root, not a specific page path.
        timeout: Request timeout in seconds (default: 10)
        include_url_lists: If True, includes full URL lists per pattern (default: False).
                          Only use for sites with <1000 URLs or when you need specific URLs.
        max_urls_per_pattern: Max URLs per pattern when include_url_lists=True (default: 10).
                             Returns shortest URLs first (often index/overview pages).

    Returns:
        Minimal response (default, include_url_lists=False):
        {
            "base_url": str,
            "analysis_method": str,  # "sitemap" or "not_found"
            "total_urls": int,  # Total URLs found in sitemap
            "pattern_stats": {  # Lightweight summary - ALWAYS included
                "/pattern": {
                    "count": int,  # Number of URLs in this pattern
                    "avg_depth": float,  # Average path depth (2.3 = ~2-3 segments deep)
                    "example_urls": [str]  # Up to 3 shortest URLs (often entry points)
                }
            },
            "notes": str  # Context about data quality and completeness
        }

        Extended response (include_url_lists=True):
        {
            ...same as above...
            "url_groups": {  # Full URL lists per pattern (limited by max_urls_per_pattern)
                "/pattern": ["url1", "url2", ...]
            }
        }

    Example workflow:
        # 1. Analyze website structure
        analysis = analyze_website("https://docs.claude.com")

        # 2. Agent interprets the patterns:
        # - /api: 45 URLs, avg depth 2.3 → API documentation section
        # - /docs: 120 URLs, avg depth 3.1 → User guide section
        # - /guides: 30 URLs, avg depth 2.5 → Tutorial section

        # 3. Agent decides to crawl each section separately:
        ingest_url("https://docs.claude.com/en/api/overview",
                   collection="claude-docs", mode="crawl",
                   follow_links=True, max_depth=2)

        ingest_url("https://docs.claude.com/en/docs/intro",
                   collection="claude-docs", mode="crawl",
                   follow_links=True, max_depth=2)

    Notes:
        - Requires sitemap.xml (tries /sitemap.xml, /sitemap_index.xml)
        - If no sitemap found, returns analysis_method="not_found"
        - URL grouping is simple path-based (no AI inference)
        - Agent should use its LLM to identify which patterns to crawl
        - Common patterns: /api, /docs, /guides, /blog, /reference
        - For large sites (3000+ URLs), use default settings (pattern_stats only)
    """
    return analyze_website_impl(base_url, timeout, include_url_lists, max_urls_per_pattern)


@mcp.tool()
async def ingest_url(
    url: str,
    collection_name: str,
    mode: str = "crawl",
    follow_links: bool = False,
    max_depth: int = 1,
    include_document_ids: bool = False,
) -> dict:
    """
    Crawl and ingest content from a web URL with duplicate prevention.

    Scrapes web pages, processes the content, and ingests into both vector store
    and knowledge graph. Supports single-page or multi-page crawling with link following.

    IMPORTANT: Collection must exist before ingesting. Use create_collection() first.

    IMPORTANT - PROCESSING TIME:
    This operation scrapes web pages, processes content, and ingests data. Processing
    time varies based on crawl scope:

    - Single page (follow_links=False, max_depth=0): Typically completes in seconds
    - Multi-page crawl (follow_links=True, max_depth=1+): Can take several minutes

    Factors affecting duration:
    - Number of pages crawled (controlled by follow_links and max_depth)
    - Content size per page
    - Network latency for page fetches

    The MCP server will continue processing even if your client times out. You may need
    to configure longer timeout values or poll for completion when crawling large sites.

    IMPORTANT DUPLICATE PREVENTION:
    - mode="crawl": New crawl. Raises error if URL already crawled into collection.
    - mode="recrawl": Update existing crawl. Deletes old pages and re-ingests.

    This prevents agents from accidentally duplicating data, which causes
    outdated information to persist alongside new information.

    By default, returns minimal response without document_ids array (may be large for multi-page crawls).
    Use include_document_ids=True to get the list of document IDs.

    Args:
        url: (REQUIRED) URL to crawl and ingest (e.g., "https://docs.python.org/3/")
        collection_name: (REQUIRED) Collection to add content to (must already exist)
        mode: Crawl mode - "crawl" or "recrawl" (default: "crawl").
              - "crawl": New crawl. ERROR if this exact URL already crawled into this collection.
              - "recrawl": Update existing. Deletes old pages from this URL and re-ingests fresh content.
        follow_links: If True, follows internal links for multi-page crawl (default: False)
        max_depth: Maximum crawl depth when following links (default: 1, max: 3)
        include_document_ids: If True, includes list of document IDs. Default: False (minimal response).

    Returns:
        Minimal response (default, mode="crawl"):
        {
            "mode": str,  # "crawl" or "recrawl"
            "pages_crawled": int,
            "pages_ingested": int,  # May be less if some pages failed
            "total_chunks": int,
            "collection_name": str,
            "crawl_metadata": {
                "crawl_root_url": str,  # Starting URL
                "crawl_session_id": str,  # UUID for this crawl session
                "crawl_timestamp": str  # ISO 8601
            }
        }

        Recrawl response (mode="recrawl"):
        {
            ...same as above...
            "old_pages_deleted": int  # Pages removed before re-crawling
        }

        Extended response (include_document_ids=True):
        {
            ...same as above...
            "document_ids": list[int]  # IDs of ingested documents
        }

    Raises:
        ValueError: If collection doesn't exist, or if mode="crawl" and URL already
                   crawled into this collection. Error message suggests using
                   mode="recrawl" to update.

    Example:
        # First, create collection
        create_collection("example-docs", "Example.com documentation")

        # New crawl (will error if URL already crawled)
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs",
            mode="crawl"
        )

        # Update existing crawl
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs",
            mode="recrawl",
            follow_links=True,
            max_depth=2
        )

        # Check collection info to see if URL already crawled
        info = get_collection_info("example-docs")
        for crawl in info['crawled_urls']:
            print(f"Already crawled: {crawl['url']}")

    Recommendation: Use analyze_website() first to understand site structure and plan
    your crawling strategy (single large crawl vs multiple smaller crawls).
    """
    return await ingest_url_impl(
        db, doc_store, unified_mediator, graph_store, url, collection_name, follow_links, max_depth, mode, include_document_ids
    )


@mcp.tool()
async def ingest_file(
    file_path: str,
    collection_name: str,
    metadata: dict | None = None,
    include_chunk_ids: bool = False,
) -> dict:
    """
    Ingest a text-based file from the file system.

    **FILE SYSTEM ACCESS REQUIREMENT:**
    This tool requires the MCP server to have access to the file path you provide.

    Depending on how this MCP server is hosted, it may or may not have access to files
    or directories. If file access fails, you will receive:

    FileNotFoundError: "File not found: {file_path}"

    When you see this error, read the file content through other means and use
    ingest_text() instead.

    IMPORTANT: Collection must exist before ingesting. Use create_collection() first.

    IMPORTANT - PROCESSING TIME:
    Processing time depends on file size:
    - Small files (<100KB): Typically completes in seconds
    - Large files (>1MB): Can take a minute or longer

    The MCP server will continue processing even if your client times out. You may need
    to configure longer timeout values when ingesting large files.

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

    By default, returns minimal response without chunk_ids array (may be large for big files).
    Use include_chunk_ids=True to get the list of chunk IDs.

    Args:
        file_path: (REQUIRED) Absolute path to the file (e.g., "/path/to/document.txt")
        collection_name: (REQUIRED) Collection to add to (must already exist)
        metadata: Optional metadata dict
        include_chunk_ids: If True, includes list of chunk IDs. Default: False (minimal response).

    Returns:
        Minimal response (default):
        {
            "source_document_id": int,
            "num_chunks": int,
            "filename": str,  # Extracted from path
            "file_type": str,  # Extracted from extension
            "file_size": int,  # Bytes
            "collection_name": str
        }

        Extended response (include_chunk_ids=True):
        {
            ...same as above...
            "chunk_ids": list[int]  # IDs of generated chunks
        }

    Raises:
        FileNotFoundError: If file doesn't exist - "File not found: {file_path}"
        UnicodeDecodeError: If file is binary/not text
        ValueError: If collection doesn't exist - "Collection '{collection_name}' does not exist. Create it first using create_collection('{collection_name}', 'description')."

    Example:
        # First, create collection
        create_collection("reports", "Engineering reports and documentation")

        # Then ingest file
        result = ingest_file(
            file_path="/Users/agent/documents/report.txt",
            collection_name="reports",
            metadata={"year": 2025, "department": "engineering"}
        )
    """
    return await ingest_file_impl(
        db, doc_store, unified_mediator, graph_store, file_path, collection_name, metadata, include_chunk_ids
    )


@mcp.tool()
async def ingest_directory(
    directory_path: str,
    collection_name: str,
    file_extensions: list | None = None,
    recursive: bool = False,
    include_document_ids: bool = False,
) -> dict:
    """
    Ingest multiple text-based files from a directory.

    **FILE SYSTEM ACCESS REQUIREMENT:**
    This tool requires the MCP server to have access to the directory path you provide.

    Depending on how this MCP server is hosted, it may or may not have access to files
    or directories. If directory access fails, you will receive:

    ValueError: "Directory not found: {directory_path}"

    When you see this error, read the file contents through other means and use
    ingest_text() for each document.

    IMPORTANT: Collection must exist before ingesting. Use create_collection() first.

    IMPORTANT - PROCESSING TIME:
    Processing time depends on directory size and recursive settings:
    - Small directories (few files, <1MB total): Typically completes in seconds
    - Large directories (many files, >10MB total): Can take several minutes
    - Recursive mode with deep hierarchies: Can take significantly longer

    Factors affecting duration:
    - Number of files to process
    - Total size of all files
    - Directory depth (when recursive=True)
    - Number of subdirectories scanned

    The MCP server will continue processing even if your client times out. You may need
    to configure longer timeout values when ingesting large directories or using recursive mode.

    Only processes text-based files (see ingest_file for supported types).
    Binary files and files without matching extensions are skipped.

    By default, returns minimal response without document_ids array (may be large for many files).
    Use include_document_ids=True to get the list of document IDs.

    Args:
        directory_path: (REQUIRED) Absolute path to directory (e.g., "/path/to/docs")
        collection_name: (REQUIRED) Collection to add all files to (must already exist)
        file_extensions: List of extensions to process (e.g., [".txt", ".md"]).
                        If None, defaults to [".txt", ".md"]
        recursive: If True, searches subdirectories (default: False)
        include_document_ids: If True, includes list of document IDs. Default: False (minimal response).

    Returns:
        Minimal response (default):
        {
            "files_found": int,
            "files_ingested": int,
            "files_failed": int,
            "total_chunks": int,
            "collection_name": str,
            "failed_files": [  # Only if files_failed > 0
                {
                    "filename": str,
                    "error": str
                }
            ]
        }

        Extended response (include_document_ids=True):
        {
            ...same as above...
            "document_ids": list[int]  # IDs of ingested documents
        }

    Raises:
        ValueError: If directory doesn't exist - "Directory not found: {directory_path}"
        ValueError: If collection doesn't exist - "Collection '{collection_name}' does not exist. Create it first using create_collection('{collection_name}', 'description')."

    Example:
        # First, create collection
        create_collection("kb", "Knowledge base articles and documentation")

        # Ingest all markdown files in directory
        result = ingest_directory(
            directory_path="/Users/agent/knowledge-base",
            collection_name="kb",
            file_extensions=[".md", ".txt"],
            recursive=True
        )

        print(f"Ingested {result['files_ingested']} files with {result['total_chunks']} chunks")
    """
    return await ingest_directory_impl(
        db,
        doc_store,
        unified_mediator,
        graph_store,
        directory_path,
        collection_name,
        file_extensions,
        recursive,
        include_document_ids,
    )


@mcp.tool()
async def update_document(
    document_id: int,
    content: str | None = None,
    title: str | None = None,
    metadata: dict | None = None,
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
        document_id: (REQUIRED) ID of document to update (from search results or list_documents)
        content: New content (optional). Triggers full re-chunking and re-embedding.
        title: New title/filename (optional)
        metadata: New metadata (optional). Merged with existing metadata, not replaced.

        **IMPORTANT: At least one of content, title, or metadata MUST be provided.**

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
    return await update_document_impl(db, doc_store, document_id, content, title, metadata, graph_store)


@mcp.tool()
async def delete_document(document_id: int) -> dict:
    """
    Delete a source document and all its chunks permanently.

    Essential for agent memory management. When information becomes outdated,
    incorrect, or no longer relevant, agents can remove it to prevent
    retrieval of stale knowledge.

    This is a permanent operation and cannot be undone. All chunks derived
    from the document are also deleted (cascade). However, other documents
    in the same collections are unaffected.

    Args:
        document_id: (REQUIRED) ID of document to delete (from search results or list_documents)

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
    return await delete_document_impl(db, doc_store, document_id, graph_store)


@mcp.tool()
def list_documents(
    collection_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_details: bool = False,
) -> dict:
    """
    List source documents in the knowledge base.

    Useful for agents to discover what documents exist before updating or
    deleting them. Can be scoped to a specific collection or list all documents.

    By default, returns minimal response (id, filename, chunk_count).
    Use include_details=True to get file_type, file_size, timestamps, collections, and metadata.

    Args:
        collection_name: Optional collection to filter by. If None, lists all documents.
        limit: Maximum number of documents to return (default: 50, max: 200)
        offset: Number of documents to skip for pagination (default: 0)
        include_details: If True, includes file_type, file_size, timestamps, collections, metadata.
                        Default: False (minimal response).

    Returns:
        Minimal response (default):
        {
            "documents": [
                {
                    "id": int,
                    "filename": str,
                    "chunk_count": int
                }
            ],
            "total_count": int,  # Total documents matching filter
            "returned_count": int,  # Documents in this response
            "has_more": bool  # Whether more pages available
        }

        Extended response (include_details=True):
        {
            "documents": [
                {
                    "id": int,
                    "filename": str,
                    "chunk_count": int,
                    "file_type": str,
                    "file_size": int,
                    "created_at": str,  # ISO 8601
                    "updated_at": str,  # ISO 8601
                    "collections": list[str],  # Collections this document belongs to
                    "metadata": dict  # Custom metadata
                }
            ],
            "total_count": int,
            "returned_count": int,
            "has_more": bool
        }

    Example:
        # Minimal listing (recommended for browsing)
        result = list_documents(collection_name="company-knowledge")
        for doc in result['documents']:
            print(f"{doc['id']}: {doc['filename']} ({doc['chunk_count']} chunks)")

        # Detailed listing with full metadata
        result = list_documents(collection_name="company-knowledge", include_details=True)
        for doc in result['documents']:
            print(f"{doc['id']}: {doc['filename']}")
            print(f"  Collections: {doc['collections']}")
            print(f"  Metadata: {doc['metadata']}")

        # Paginate through all documents
        offset = 0
        result = list_documents(limit=50, offset=offset)
        while result['has_more']:
            # Process documents
            offset += result['returned_count']
            result = list_documents(limit=50, offset=offset)
    """
    return list_documents_impl(doc_store, collection_name, limit, offset, include_details)


# =============================================================================
# Knowledge Graph Query Tools
# =============================================================================


@mcp.tool()
async def query_relationships(
    query: str,
    num_results: int = 5,
    threshold: float = 0.35,
) -> dict:
    """
    Search the knowledge graph for entity relationships using natural language.

    This tool searches for connections and relationships between entities in your
    knowledge graph. Use it to understand how concepts, people, projects, and ideas
    relate to each other.

    **What it does:**
    - Finds relationships between entities (e.g., "How does X relate to Y?")
    - Discovers connections across your knowledge base
    - Maps entity relationships automatically extracted from your content

    **Best for:**
    - "How" questions - "How does my YouTube channel relate to my business?"
    - Connection queries - "What connects project A to project B?"
    - Relationship discovery - "Show me relationships involving RAG systems"

    **Note:** Knowledge Graph must be enabled and available. If unavailable,
    returns status="unavailable" with an empty relationships list.

    **About the threshold parameter:**
    The threshold controls result relevance filtering (0.0 = permissive, 1.0 = strict):
    - **Lower values (0.0-0.3):** More results, including less certain matches
    - **Default (0.35):** Balanced - filters obvious mismatches while keeping good results
    - **Higher values (0.5-0.7):** Fewer results, only high-confidence matches
    Useful for tuning result quality vs quantity when defaults don't fit your needs.

    Args:
        query: (REQUIRED) Natural language query about relationships
               (e.g., "How does my content strategy support my business?")
        num_results: Maximum number of relationships to return (default: 5, max: 20)
        threshold: Relationship confidence threshold (default: 0.35, range: 0.0-1.0)
                  Controls relevance filtering - higher values = stricter filtering

    Returns:
        {
            "status": str,  # "success", "unavailable", or "error"
            "query": str,  # Echo of your query
            "num_results": int,  # Number of relationships found
            "relationships": [
                {
                    "id": str,  # Relationship ID
                    "relationship_type": str,  # Type of relationship (e.g., "RELATES_TO")
                    "fact": str,  # Human-readable description
                    "source_node_id": str,  # ID of source entity
                    "target_node_id": str,  # ID of target entity
                    "valid_from": str,  # ISO 8601 timestamp (when fact became valid)
                    "valid_until": str  # ISO 8601 timestamp (when fact expired, if applicable)
                }
            ]
        }

    Example:
        # Discover business relationships
        result = query_relationships(
            query="How does my YouTube channel relate to my product strategy?",
            num_results=5,
            threshold=0.35
        )

        for rel in result['relationships']:
            print(f"{rel['relationship_type']}: {rel['fact']}")

    Performance: ~500-800ms per query (includes LLM-based entity matching)
    """
    return await query_relationships_impl(
        graph_store,
        query,
        num_results,
        threshold=threshold,
    )


@mcp.tool()
async def query_temporal(
    query: str,
    num_results: int = 10,
    valid_from: str = None,
    valid_until: str = None,
) -> dict:
    """
    Query how knowledge has evolved over time using temporal reasoning.

    This tool reveals how your knowledge and understanding have changed over time.
    It shows facts with their validity periods, helping you understand what was
    true when, and how information has evolved.

    **What it does:**
    - Tracks how facts changed over time
    - Shows current vs superseded knowledge
    - Reveals evolution of your understanding
    - Identifies outdated vs current information

    **Temporal Filtering:**
    - **valid_from**: Filter to facts valid AFTER this ISO 8601 date
    - **valid_until**: Filter to facts valid BEFORE this ISO 8601 date
    - Both filters can be used together to find facts valid in a specific time window

    **Best for:**
    - Evolution queries - "How has my business strategy changed?"
    - Temporal tracking - "What was my focus in January vs March?"
    - Trend analysis - "Show me how my product priorities evolved"
    - Consistency checking - "What beliefs changed about X?"
    - Decision tracking - "What decisions did I make around December 2025?"

    **Note:** Knowledge Graph must be enabled and available. If unavailable,
    returns status="unavailable" with an empty timeline list.

    Args:
        query: (REQUIRED) Natural language query about temporal changes
               (e.g., "How has my business vision evolved?")
        num_results: Maximum number of timeline items to return (default: 10, max: 50)
        valid_from: (OPTIONAL) ISO 8601 date (e.g., "2025-12-01T00:00:00")
                   Only return facts valid after this date
        valid_until: (OPTIONAL) ISO 8601 date (e.g., "2025-12-31T23:59:59")
                    Only return facts valid before this date

    Returns:
        {
            "status": str,  # "success", "unavailable", or "error"
            "query": str,  # Echo of your query
            "num_results": int,  # Number of timeline items found
            "timeline": [  # Sorted by valid_from (most recent first)
                {
                    "fact": str,  # Human-readable description
                    "relationship_type": str,  # Type of relationship
                    "valid_from": str,  # ISO 8601 (when this became true)
                    "valid_until": str,  # ISO 8601 (when this no longer applied, null if current)
                    "status": str,  # "current" (still valid) or "superseded" (no longer the active version)
                    "created_at": str,  # ISO 8601 (when fact was added to graph)
                    "expired_at": str  # ISO 8601 (when fact was marked superseded)
                }
            ]
        }

    Examples:
        # Track business evolution
        result = query_temporal(
            query="How has my business strategy evolved?",
            num_results=10
        )

        for item in result['timeline']:
            status = "✅ Current" if item['status'] == "current" else "⏰ Expired"
            print(f"{status}: {item['fact']}")
            print(f"  Valid: {item['valid_from']} → {item['valid_until'] or 'present'}")

        # Find decisions made in specific time window
        result = query_temporal(
            query="What decisions did I make?",
            valid_from="2025-12-01T00:00:00",
            valid_until="2025-12-31T23:59:59"
        )

    Performance: ~500-800ms per query (includes LLM-based temporal matching)
    """
    return await query_temporal_impl(
        graph_store,
        query,
        num_results,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def main():
    """Run the MCP server with specified transport."""
    import sys
    import asyncio
    import click

    @click.command()
    @click.option(
        "--port",
        default=3001,
        help="Port to listen on for SSE or Streamable HTTP transport"
    )
    @click.option(
        "--transport",
        type=click.Choice(["stdio", "sse", "streamable-http"]),
        default="stdio",
        help="Transport type (stdio, sse, or streamable-http)"
    )
    def run_cli(port: int, transport: str):
        """Run the RAG memory MCP server with specified transport."""
        # Ensure all required configuration is set up before starting
        ensure_config_or_exit()

        async def run_server():
            """Inner async function to run the server and manage the event loop."""
            try:
                if transport == "stdio":
                    logger.info("Starting server with STDIO transport")
                    await mcp.run_stdio_async()
                elif transport == "sse":
                    logger.info(f"Starting server with SSE transport on port {port}")
                    mcp.settings.host = "0.0.0.0"
                    mcp.settings.port = port
                    await mcp.run_sse_async()
                elif transport == "streamable-http":
                    logger.info(f"Starting server with Streamable HTTP transport on port {port}")
                    mcp.settings.port = port
                    mcp.settings.streamable_http_path = "/mcp"
                    await mcp.run_streamable_http_async()
                else:
                    raise ValueError(f"Unknown transport: {transport}")
            except KeyboardInterrupt:
                logger.info("Server stopped by user")
            except Exception as e:
                logger.error(f"Failed to start server: {e}", exc_info=True)
                raise

        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            logger.info("Server interrupted")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    run_cli()


def main_stdio():
    """Run MCP server in stdio mode (for Claude Desktop/Cursor)."""
    import sys
    sys.argv = ['rag-mcp-stdio', '--transport', 'stdio']
    main()


def main_sse():
    """Run MCP server in SSE mode (for MCP Inspector)."""
    import sys
    sys.argv = ['rag-mcp-sse', '--transport', 'sse', '--port', '3001']
    main()


def main_http():
    """Run MCP server in HTTP mode (for web integrations)."""
    import sys
    sys.argv = ['rag-mcp-http', '--transport', 'streamable-http', '--port', '3001']
    main()


if __name__ == "__main__":
    main()
