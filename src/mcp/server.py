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
    update_collection_metadata_impl,
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


# Load server instructions from file
_instructions_path = Path(__file__).parent / "server_instructions.txt"
_server_instructions = _instructions_path.read_text() if _instructions_path.exists() else None

# Initialize FastMCP server (no authentication)
mcp = FastMCP("rag-memory", instructions=_server_instructions, lifespan=lifespan)


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

    **Collection Scoping:**
    Specifying collection_name limits search to that domain's vector embeddings.
    For relationship queries in the same domain, use query_graph_relationships
    with the same collection_name.

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
    name: str,
    description: str,
    domain: str,
    domain_scope: str,
    metadata_schema: dict = None
) -> dict:
    """
    Create a new collection for organizing documents by domain.

    **CRITICAL - Collection Discipline:**
    Collections partition BOTH vector search and knowledge graph. Create separate collections
    for different domains (e.g., "api-docs", "meeting-notes", "project-x") rather than mixing
    unrelated content. This ensures better search relevance and isolated knowledge graphs.

    Args:
        name: Collection identifier (unique, lowercase recommended)
        description: Human-readable purpose (REQUIRED, cannot be empty)
        domain: High-level category (e.g., "engineering", "finance")
        domain_scope: Scope description (e.g., "Internal API documentation")
        metadata_schema: Optional schema for custom fields. Format: {"custom": {"field": {"type": "string"}}}

    Returns:
        {"collection_id": int, "name": str, "description": str, "metadata_schema": dict, "created": bool}

    Best Practices (see server instructions: Collection Discipline):
    - One collection per domain/topic (don't mix unrelated content)
    - Use descriptive names and clear descriptions
    - Define metadata schema upfront (can only add fields later, not remove)
    - Check existing collections with list_collections() first

    Note: Free operation (no API calls).
    """
    return create_collection_impl(coll_mgr, name, description, domain, domain_scope, metadata_schema)


@mcp.tool()
def get_collection_metadata_schema(collection_name: str) -> dict:
    """
    Get metadata schema for a collection to discover required/optional fields before ingestion.

    Args:
        collection_name: Collection name

    Returns:
        {"collection_name": str, "description": str, "metadata_schema": dict,
         "custom_fields": dict, "system_fields": list, "document_count": int}

    Best Practices:
    - Use before ingesting to check required metadata fields
    - Helps avoid schema validation errors during ingest

    Note: Free operation (no API calls).
    """
    return get_collection_metadata_schema_impl(coll_mgr, collection_name)


@mcp.tool()
async def delete_collection(name: str, confirm: bool = False) -> dict:
    """
    Permanently delete a collection and all its documents.

    **⚠️ DESTRUCTIVE - Cannot be undone. Two-step confirmation required.**

    Workflow:
    1. Call with confirm=False (default) → Returns error requiring confirmation
    2. Review what will be deleted
    3. Call with confirm=True → Permanently deletes

    Args:
        name: Collection to delete (must exist)
        confirm: Must be True to proceed (default: False)

    Returns:
        {"name": str, "deleted": bool, "message": str}

    Best Practices (see server instructions: Collection Discipline):
    - Verify collection contents with get_collection_info() first
    - Ensure no other collections reference this data
    - Two-step confirmation prevents accidents

    Note: Free operation (deletes data, no API calls).
    """
    return await delete_collection_impl(coll_mgr, name, confirm, graph_store, db)


@mcp.tool()
def update_collection_metadata(
    collection_name: str,
    new_fields: dict
) -> dict:
    """
    Add new optional metadata fields to existing collection (additive only).

    **IMPORTANT:** Can only ADD fields, cannot remove or change types.

    Args:
        collection_name: Collection to update
        new_fields: New fields to add. Format: {"field": {"type": "string"}} or {"field": "string"}

    Returns:
        {"name": str, "description": str, "metadata_schema": dict,
         "fields_added": int, "total_fields": int}

    Best Practices:
    - All new fields automatically become optional
    - Existing documents won't have new fields until re-ingestion
    - Plan schema upfront to minimize updates

    Note: Free operation (no API calls).
    """
    return update_collection_metadata_impl(coll_mgr, collection_name, new_fields)


@mcp.tool()
async def ingest_text(
    content: str,
    collection_name: str,
    document_title: str | None = None,
    metadata: dict | None = None,
    include_chunk_ids: bool = False,
) -> dict:
    """
    Ingest text content into both vector store and knowledge graph with automatic chunking.

    **IMPORTANT:** Collection must exist. Use create_collection() first.

    **Workflow (see server instructions: Ingestion Workflows):**
    1. list_documents() - Check for duplicates
    2. If exists: update_document() instead
    3. If new: ingest_text()

    Args:
        content: Text to ingest (any length, auto-chunked)
        collection_name: Target collection (must exist)
        document_title: Optional title (auto-generated if None)
        metadata: Optional metadata dict
        include_chunk_ids: If True, returns chunk IDs (default: False for minimal response)

    Returns:
        {"source_document_id": int, "num_chunks": int, "collection_name": str,
         "chunk_ids": list (only if include_chunk_ids=True)}

    Best Practices (see server instructions: Ingestion Workflows):
    - Check for duplicates before ingesting
    - Use meaningful document titles for search results
    - Add metadata to enable filtered searches

    Note: Uses AI models, has cost (embeddings + graph extraction).
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
    Retrieve full document by ID (from search results).

    Args:
        document_id: Source document ID (from search_documents results)
        include_chunks: If True, includes chunk details (default: False)

    Returns:
        {"id": int, "filename": str, "content": str, "file_type": str, "file_size": int,
         "metadata": dict, "created_at": str, "updated_at": str,
         "chunks": list (only if include_chunks=True)}

    Best Practices:
    - Use when search chunk needs full document context
    - Document IDs come from search results (source_document_id field)

    Note: Free operation (no API calls).
    """
    return get_document_by_id_impl(doc_store, document_id, include_chunks)


@mcp.tool()
def get_collection_info(collection_name: str) -> dict:
    """
    Get detailed collection stats including crawled URLs history.

    **Use before ingesting** to check existing content and avoid duplicates.

    Args:
        collection_name: Collection name

    Returns:
        {"name": str, "description": str, "document_count": int, "chunk_count": int,
         "created_at": str, "sample_documents": list, "crawled_urls": list}

    Best Practices (see server instructions: Ingestion Workflows):
    - Check before ingesting to avoid duplicates
    - Review crawled_urls to see if website already ingested
    - Use sample_documents to verify collection content

    Note: Free operation (no API calls).
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
    Analyze website structure before crawling (fetches sitemap, identifies URL patterns).

    **CRITICAL - Always use before large crawls** (see server instructions: Analyze Before Large Crawls)

    **Workflow:**
    1. analyze_website(url) - Get sitemap data
    2. Review total_urls and pattern_stats
    3. If large (dozens/hundreds): Present "at least N pages" to user, get confirmation
    4. Decide: single crawl vs multiple targeted crawls
    5. ingest_url(follow_links=True)

    Args:
        base_url: Website ROOT (e.g., "https://docs.example.com", NOT specific page)
        timeout: Request timeout seconds (default: 10)
        include_url_lists: If True, includes full URL lists (default: False, pattern stats only)
        max_urls_per_pattern: Max URLs per pattern when include_url_lists=True (default: 10)

    Returns:
        {"base_url": str, "analysis_method": str, "total_urls": int (minimum from sitemap),
         "pattern_stats": dict, "notes": str, "url_groups": dict (only if include_url_lists=True)}

    Best Practices (see server instructions: Analyze Before Large Crawls):
    - MUST use for large sites before crawling
    - Present scope to user: "at least N pages"
    - Note: actual crawl may discover MORE pages with follow_links
    - Get user confirmation for large operations

    Note: Free operation (no API calls, just HTTP request for sitemap).
    """
    return analyze_website_impl(base_url, timeout, include_url_lists, max_urls_per_pattern)


@mcp.tool()
async def ingest_url(
    url: str,
    collection_name: str,
    mode: str = "crawl",
    follow_links: bool = False,
    max_depth: int = 1,
    metadata: dict | None = None,
    include_document_ids: bool = False,
) -> dict:
    """
    Crawl and ingest content from a web URL with duplicate prevention.

    **DOMAIN GUIDANCE:**
    Websites often contain diverse content types. Consider creating separate collections for:
    - Different documentation sections (API docs vs tutorials vs guides)
    - Different content purposes (blog posts vs product pages vs support articles)
    Use analyze_website() first to understand the site structure and plan your strategy.

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
        metadata: Custom metadata to apply to ALL crawled pages (merged with page metadata).
                  Must match collection's metadata_schema if defined.
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
        # First, create collection with metadata schema
        create_collection("example-docs", "Example.com documentation",
                         metadata_schema={"source": "str", "doc_type": "str"})

        # New crawl with metadata (will error if URL already crawled)
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs",
            mode="crawl",
            metadata={"source": "official", "doc_type": "api"}
        )

        # Update existing crawl with metadata
        result = ingest_url(
            url="https://example.com/docs",
            collection_name="example-docs",
            mode="recrawl",
            follow_links=True,
            max_depth=2,
            metadata={"source": "official", "doc_type": "api"}
        )

        # Check collection info to see if URL already crawled
        info = get_collection_info("example-docs")
        for crawl in info['crawled_urls']:
            print(f"Already crawled: {crawl['url']}")

    Recommendation: Use analyze_website() first to understand site structure and plan
    your crawling strategy (single large crawl vs multiple smaller crawls).
    """
    return await ingest_url_impl(
        db, doc_store, unified_mediator, graph_store, url, collection_name, follow_links, max_depth, mode, metadata, include_document_ids
    )


@mcp.tool()
async def ingest_file(
    file_path: str,
    collection_name: str,
    metadata: dict | None = None,
    include_chunk_ids: bool = False,
) -> dict:
    """
    Ingest text-based file from file system (text/code/config only, not binary).

    **IMPORTANT - File system access:** MCP server must access file path. If fails, use ingest_text() instead.

    Args:
        file_path: Absolute path (e.g., "/path/to/document.txt")
        collection_name: Target collection (must exist)
        metadata: Optional metadata dict
        include_chunk_ids: If True, returns chunk IDs (default: False)

    Returns:
        {"source_document_id": int, "num_chunks": int, "filename": str, "file_type": str,
         "file_size": int, "collection_name": str, "chunk_ids": list (only if include_chunk_ids=True)}

    Best Practices (see server instructions: Ingestion Workflows):
    - Supports: .txt, .md, code files, .json, .yaml, .html, etc. (UTF-8 text)
    - NOT supported: PDF, Office docs, images, archives
    - Large files (>1MB) may take minutes to process

    Note: Uses AI models, has cost (embeddings + graph extraction).
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
    metadata: dict | None = None,
    include_document_ids: bool = False,
) -> dict:
    """
    Batch ingest multiple text files from directory (text-based only, skips binary).

    **DOMAIN GUIDANCE:** If directory has mixed content (code + docs + configs), create separate collections per domain or use file_extensions to filter.

    **IMPORTANT - File system access:** MCP server must access directory path. If fails, use ingest_text() for each file.

    Args:
        directory_path: Absolute path (e.g., "/path/to/docs")
        collection_name: Target collection (must exist)
        file_extensions: Extensions to process (default: [".txt", ".md"])
        recursive: If True, searches subdirectories (default: False)
        metadata: Metadata applied to ALL files (merged with file metadata)
        include_document_ids: If True, returns document IDs (default: False)

    Returns:
        {"files_found": int, "files_ingested": int, "files_failed": int, "total_chunks": int,
         "collection_name": str, "failed_files": list, "document_ids": list (only if include_document_ids=True)}

    Best Practices (see server instructions: Collection Discipline):
    - Assess domain consistency before batch ingesting
    - Large directories (>10MB) may take several minutes
    - Recursive mode with deep hierarchies takes significantly longer

    Note: Uses AI models, has cost (embeddings + graph extraction per file).
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
        metadata,
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
    Update existing document's content, title, or metadata (prevents duplicates).

    **IMPORTANT:** At least one field (content, title, or metadata) must be provided.

    Args:
        document_id: Document ID (from search results or list_documents)
        content: New content (triggers re-chunking and re-embedding)
        title: New title/filename
        metadata: New metadata (merged with existing, not replaced)

    Returns:
        {"document_id": int, "updated_fields": list, "old_chunk_count": int (if content updated),
         "new_chunk_count": int (if content updated)}

    Best Practices (see server instructions: Ingestion Workflows):
    - Essential for memory management (avoid duplicates)
    - Content updates trigger full re-chunking/re-embedding
    - Metadata is merged (to remove key, delete and re-ingest)

    Note: Content updates use AI models, has cost (embeddings + graph extraction).
    """
    return await update_document_impl(db, doc_store, document_id, content, title, metadata, graph_store)


@mcp.tool()
async def delete_document(document_id: int) -> dict:
    """
    Permanently delete document and all chunks (cannot be undone).

    **⚠️ PERMANENT - Essential for memory management** to remove outdated/incorrect knowledge.

    Args:
        document_id: Document ID (from search results or list_documents)

    Returns:
        {"document_id": int, "document_title": str, "chunks_deleted": int,
         "collections_affected": list (collections that had this document)}

    Best Practices:
    - Does NOT delete collections (only removes document from them)
    - Other documents in collections are unaffected
    - Use with caution - deletion is permanent

    Note: Free operation (no API calls, only database deletion).
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
    Browse documents in knowledge base (supports pagination).

    Args:
        collection_name: Filter by collection (if None, lists all)
        limit: Max documents to return (default: 50, max: 200)
        offset: Documents to skip for pagination (default: 0)
        include_details: If True, includes file_type, file_size, timestamps, collections, metadata (default: False)

    Returns:
        {"documents": list, "total_count": int, "returned_count": int, "has_more": bool}
        Each document: {"id": int, "filename": str, "chunk_count": int, ... (more if include_details=True)}

    Best Practices:
    - Discover documents before updating/deleting
    - Use pagination (has_more) for large collections
    - Default minimal response recommended for browsing

    Note: Free operation (no API calls).
    """
    return list_documents_impl(doc_store, collection_name, limit, offset, include_details)


# =============================================================================
# Knowledge Graph Query Tools
# =============================================================================


@mcp.tool()
async def query_relationships(
    query: str,
    collection_name: str | None = None,
    num_results: int = 5,
    threshold: float = 0.35,
) -> dict:
    """
    Query knowledge graph for entity relationships using natural language.

    **Best for:** "How" questions about connections (e.g., "How does X relate to Y?")

    Args:
        query: Natural language query (e.g., "How does my content strategy support my business?")
        collection_name: Scope to collection (if None, searches all)
        num_results: Max relationships to return (default: 5, max: 20)
        threshold: Relevance filter 0.0-1.0 (default: 0.35, higher = stricter)

    Returns:
        {"status": str, "query": str, "num_results": int, "relationships": list}
        Each relationship: {"id": str, "relationship_type": str, "fact": str, "source_node_id": str,
                           "target_node_id": str, "valid_from": str, "valid_until": str}

    Best Practices (see server instructions: Knowledge Graph):
    - Collection scoping isolates domains (same as search_documents)
    - Returns status="unavailable" if graph not enabled
    - Performance: ~500-800ms (includes LLM entity matching)

    Note: Uses AI models, has cost (LLM for entity matching).
    """
    return await query_relationships_impl(
        graph_store,
        query,
        collection_name,
        num_results,
        threshold=threshold,
    )


@mcp.tool()
async def query_temporal(
    query: str,
    collection_name: str | None = None,
    num_results: int = 10,
    threshold: float = 0.35,
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> dict:
    """
    Query how knowledge evolved over time (temporal reasoning on facts).

    **Best for:** Evolution queries (e.g., "How has my business strategy changed?")

    Args:
        query: Natural language query (e.g., "How has my business vision evolved?")
        collection_name: Scope to collection (if None, searches all)
        num_results: Max timeline items to return (default: 10, max: 50)
        threshold: Relevance filter 0.0-1.0 (default: 0.35, higher = stricter)
        valid_from: ISO 8601 date (return facts valid AFTER this date)
        valid_until: ISO 8601 date (return facts valid BEFORE this date)

    Returns:
        {"status": str, "query": str, "num_results": int, "timeline": list (sorted by valid_from, recent first)}
        Each item: {"fact": str, "relationship_type": str, "valid_from": str, "valid_until": str,
                   "status": str ("current" or "superseded"), "created_at": str, "expired_at": str}

    Best Practices (see server instructions: Knowledge Graph):
    - Tracks current vs superseded knowledge
    - Temporal filters can be combined for time windows
    - Returns status="unavailable" if graph not enabled
    - Performance: ~500-800ms (includes LLM temporal matching)

    Note: Uses AI models, has cost (LLM for temporal matching).
    """
    return await query_temporal_impl(
        graph_store,
        query,
        collection_name,
        num_results,
        threshold=threshold,
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
