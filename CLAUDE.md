# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a proof-of-concept for PostgreSQL with pgvector extension as a replacement for ChromaDB in RAG (Retrieval-Augmented Generation) systems. The goal is to validate that pgvector provides better similarity search accuracy (0.7-0.95 range) compared to ChromaDB's low scores (~0.3 range).

**Key Achievement**: Proper vector normalization + HNSW indexing = 0.73 similarity for near-identical content (vs 0.3 with ChromaDB).

## Development Setup

### Prerequisites
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (creates .venv automatically)
uv sync

# Configure environment
cp .env.example .env
# Add OPENAI_API_KEY to .env

# Start PostgreSQL with pgvector (port 54320)
docker-compose up -d

# Initialize database
uv run poc init
```

### Common Commands

**Running the CLI:**
```bash
# All commands use: uv run poc <command>
uv run poc status              # Check database connection
uv run poc test-similarity     # Validate similarity scores (key test!)
uv run poc benchmark          # Performance benchmarks

# Collection management
uv run poc collection create <name> [--description TEXT]
uv run poc collection list
uv run poc collection delete <name>

# Document ingestion (with automatic chunking by default)
uv run poc ingest text "content" --collection <name> [--metadata JSON]
uv run poc ingest file <path> --collection <name>  # Auto-chunks documents
uv run poc ingest file <path> --collection <name> --no-chunking  # Store whole document
uv run poc ingest directory <path> --collection <name> --extensions .txt,.md
uv run poc ingest directory <path> --collection <name> --recursive

# Web page ingestion (uses Crawl4AI for web scraping)
uv run poc ingest url <url> --collection <name>  # Crawl single page
uv run poc ingest url <url> --collection <name> --follow-links  # Follow internal links (depth=1)
uv run poc ingest url <url> --collection <name> --follow-links --max-depth 2  # Follow links 2 levels deep
uv run poc ingest url <url> --collection <name> --chunk-size 2500 --chunk-overlap 300  # Custom chunking

# Re-crawl web pages (delete old, re-ingest new)
# Only deletes pages matching crawl_root_url - other documents in collection unaffected
uv run poc recrawl <url> --collection <name>  # Re-crawl single page
uv run poc recrawl <url> --collection <name> --follow-links --max-depth 2  # Re-crawl with link following

# Document management
uv run poc document list [--collection NAME]  # List all source documents
uv run poc document view <ID> [--show-chunks] [--show-content]  # View document details

# Search (now supports both whole documents and chunks)
uv run poc search "query" [--collection NAME] [--limit N] [--threshold FLOAT] [--verbose]
uv run poc search "query" --chunks  # Search document chunks (recommended for chunked docs)
uv run poc search "query" --chunks --show-source  # Include full source document info
```

**Testing:**
```bash
# Run all tests (requires DB + OpenAI API key)
uv run pytest

# Run specific test file
uv run pytest tests/test_embeddings.py -v

# Run only normalization tests (no API calls)
uv run pytest tests/test_embeddings.py::TestEmbeddingNormalization -v
```

**Code Quality:**
```bash
uv run black src/ tests/      # Format
uv run ruff check src/ tests/  # Lint
```

**Docker Management:**
```bash
docker-compose ps              # Check status
docker-compose logs -f         # View logs
docker-compose restart         # Restart
docker-compose down -v         # Reset (deletes data!)
```

## Architecture

### Core Components

**Database Layer (src/database.py)**
- Manages psycopg3 connections to PostgreSQL
- Health checks and stats reporting
- Simple connection model (no pooling in POC)

**Embeddings Layer (src/embeddings.py)**
- OpenAI text-embedding-3-small integration (1536 dims)
- **Critical**: `normalize_embedding()` - converts vectors to unit length
- Without normalization, similarity scores are artificially low (0.3 vs 0.73)

**Collections Layer (src/collections.py)**
- ChromaDB-style collection management
- Many-to-many relationship: documents can belong to multiple collections
- Search can be scoped to specific collection

**Chunking Layer (src/chunking.py)**
- Splits large documents into ~1000 char chunks with 200 char overlap
- Uses LangChain's RecursiveCharacterTextSplitter
- Hierarchical separators: markdown headers → paragraphs → sentences → words
- Preserves document metadata across all chunks
- Configurable chunk size and overlap for optimization

**Document Store Layer (src/document_store.py)**
- High-level document management with automatic chunking
- Stores full source documents + generates searchable chunks
- Tracks relationships: source_documents → document_chunks → collections
- Each chunk independently embedded and searchable
- Enables context retrieval (chunk + source document)

**Ingestion Layer (src/ingestion.py)**
- Legacy layer for whole-document storage (still available with --no-chunking)
- Handles document → embedding → storage pipeline
- Supports single docs, files, directories, and batch operations
- **Important**: Uses `Jsonb()` wrapper for metadata (psycopg3 requirement)

**Search Layer (src/search.py)**
- Executes similarity searches using pgvector
- **Critical conversions**:
  - Wraps query embeddings with `np.array()` for pgvector
  - Converts distance to similarity: `similarity = 1 - distance`
- pgvector's `<=>` operator returns cosine distance (0-2), not similarity (0-1)

**CLI Layer (src/cli.py)**
- Click-based interface with Rich formatting
- Entry point defined in pyproject.toml: `poc = "src.cli:main"`

### Database Schema

**Legacy tables (whole document storage):**
1. **documents** - stores content, metadata (JSONB), embeddings (vector[1536])
2. **collections** - named groupings (like ChromaDB collections)
3. **document_collections** - junction table for many-to-many relationships

**Chunking tables (recommended for large documents):**
1. **source_documents** - full original documents (filename, content, file_type, metadata)
2. **document_chunks** - searchable chunks (content, embedding, char positions, chunk_index)
3. **chunk_collections** - junction table linking chunks to collections

**Key relationships:**
- One source_document → many document_chunks (1:N)
- One chunk → many collections (N:M via chunk_collections)
- Each chunk has: content, embedding, char_start/end, chunk_index, metadata

**Indexes:**
- HNSW on documents.embedding: `m=16, ef_construction=64` (optimized for recall)
- HNSW on document_chunks.embedding: same parameters for chunk search
- GIN on metadata columns for efficient JSONB queries
- Index on document_chunks.source_document_id for fast chunk retrieval

## Critical Implementation Details

### 1. Vector Normalization (THE KEY TO SUCCESS)
```python
# src/embeddings.py:33-46
def normalize_embedding(embedding: list[float]) -> list[float]:
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    return (arr / norm).tolist() if norm > 0 else arr.tolist()
```
- **Always normalize** before storage and queries
- Without this, you get ChromaDB's 0.3 scores
- With this, you get proper 0.7-0.95 scores

### 2. psycopg3 + JSONB Handling
```python
from psycopg.types.json import Jsonb

# When inserting metadata
cur.execute("INSERT INTO documents (content, metadata, ...) VALUES (%s, %s, ...)",
            (content, Jsonb(metadata), ...))
```
- **Must wrap dicts with `Jsonb()`** when inserting/comparing JSONB columns
- Retrieved metadata comes as dict (no parsing needed)

### 3. pgvector Integration
```python
import numpy as np
from pgvector.psycopg import register_vector

# Register once per connection
conn = psycopg.connect(...)
register_vector(conn)

# Convert query embeddings to numpy arrays
query_embedding = np.array(embedding_list)

# Use in SQL
cur.execute("SELECT ... WHERE embedding <=> %s ...", (query_embedding,))
```

### 4. Distance to Similarity Conversion
```python
# pgvector returns cosine distance (0-2)
distance = row[3]
similarity = 1.0 - distance  # Convert to 0-1 scale
```

### 5. Document Chunking (Recommended for Large Documents)
```python
# src/chunking.py - Configurable text splitting
from src.chunking import ChunkingConfig, DocumentChunker

config = ChunkingConfig(
    chunk_size=1000,      # Target chunk size in characters
    chunk_overlap=200,    # Overlap to maintain context
    separators=[          # Hierarchical splitting
        "\n## ",          # Markdown H2
        "\n### ",         # Markdown H3
        "\n\n",           # Paragraphs
        "\n",             # Lines
        ". ",             # Sentences
        " ",              # Words
        ""                # Character-level fallback
    ]
)
chunker = DocumentChunker(config)

# src/document_store.py - High-level document management
from src.document_store import get_document_store

doc_store = get_document_store(db, embedder, collection_mgr)

# Ingest with automatic chunking
source_id, chunk_ids = doc_store.ingest_file(
    file_path="document.txt",
    collection_name="my_collection",
    metadata={"category": "technical"}
)
# Returns: source document ID + list of chunk IDs

# Search chunks (not whole documents)
from src.search import get_similarity_search

searcher = get_similarity_search(db, embedder, collection_mgr)
results = searcher.search_chunks(
    query="technical question",
    limit=5,
    threshold=0.7,
    collection_name="my_collection",
    include_source=True  # Includes full source document content
)

# Each result has:
# - chunk_id, content, similarity, chunk_index
# - source_document_id, source_filename
# - char_start, char_end (position in source)
# - source_content (if include_source=True)
```

**Why chunking matters:**
- Large documents (>10KB) often have low overall similarity scores
- Chunking enables precise retrieval of relevant sections
- Maintains context with overlap between chunks
- Each chunk embedded independently for accurate matching
- Source document preserved for full context retrieval

**Chunking strategy:**
1. Use hierarchical separators (headers → paragraphs → sentences)
2. Target ~1000 chars per chunk (fits context windows well)
3. 200 char overlap prevents breaking sentences/concepts
4. Store full source + chunks (best of both worlds)

## Document Organization

**Two approaches available:**

1. **Collections** (like ChromaDB): High-level grouping
   - Create separate collections per topic
   - Search scoped to collection: `uv run poc search "query" --collection tech-docs`

2. **Metadata** (JSONB): Fine-grained attributes
   - Add during ingestion: `--metadata '{"topic":"postgres","version":"2.0"}'`
   - Programmatic filtering via `search_with_metadata_filter()` (not in CLI yet)

3. **Both**: Use collections for major topics + metadata for attributes

## Web Crawling and Re-crawl Strategy

### Crawl Metadata
Every web page crawled gets these critical metadata fields:
- `crawl_root_url`: The starting URL of the crawl session (used for re-crawl matching)
- `crawl_session_id`: Unique UUID for this crawl session
- `crawl_timestamp`: ISO 8601 timestamp of when the crawl occurred
- `crawl_depth`: Distance from root URL (0 = starting page, 1 = direct links, etc.)
- `parent_url`: URL of the parent page (for depth > 0)

### Re-crawl Command
The `recrawl` command implements a "nuclear option" strategy:
1. Find all source documents where `metadata.crawl_root_url` matches the target URL
2. Delete those documents and their chunks (NOT the entire collection)
3. Re-crawl from the root URL with specified parameters
4. Ingest new pages into the same collection
5. Report: "Deleted X old pages, crawled Y new pages"

**Why this approach:**
- ✅ Safe for mixed collections (only deletes pages from specific crawl root)
- ✅ You can have multiple crawl roots in one collection
- ✅ You can mix web pages + file ingestion in same collection
- ✅ Handles site redesigns, URL changes, deleted pages automatically
- ✅ No risk of stale content or duplicate pages
- ✅ Predictable behavior (always fresh data)

**Example workflow:**
```bash
# Initial crawl of docs site (depth=2)
uv run poc ingest url https://docs.example.com --collection api-docs --follow-links --max-depth 2

# Later, re-crawl to update content
uv run poc recrawl https://docs.example.com --collection api-docs --follow-links --max-depth 2

# Add different docs to same collection (unaffected by recrawl above)
uv run poc ingest url https://guides.example.com --collection api-docs --follow-links
```

### Metadata Filtering
Search can filter by crawl metadata (programmatic API):
```python
# Find only content from specific crawl session
results = searcher.search_chunks(
    query="feature X",
    collection_name="docs",
    metadata_filter={"crawl_session_id": "abc-123"}
)

# Find only content from root URL (all pages from that crawl)
results = searcher.search_chunks(
    query="feature X",
    collection_name="docs",
    metadata_filter={"crawl_root_url": "https://docs.example.com"}
)

# Find only starting pages (depth=0)
results = searcher.search_chunks(
    query="feature X",
    collection_name="docs",
    metadata_filter={"crawl_depth": 0}
)
```

## Testing Philosophy

**The `test-similarity` command is the key validation:**
- Tests high/medium/low similarity scenarios
- High similarity (near-identical): should score 0.70-0.95
- Medium similarity (related): currently scores ~0.37 (may need range adjustment)
- Low similarity (unrelated): should score 0.10-0.40

**Success = high similarity test passes with >0.70 score**

## Port Configuration

PostgreSQL runs on **port 54320** (not standard 5432 or 5433) to avoid conflicts with other local PostgreSQL instances.

## Project Goals

This is a **proof-of-concept**, not production code:
- Validate pgvector > ChromaDB for similarity accuracy
- Demonstrate proper vector normalization
- Test HNSW indexing for recall
- Provide reference implementation for RAG Retriever migration

**Success Criteria:**
- ✅ Similarity scores 0.7-0.95 for good matches (vs ChromaDB's 0.3)
- ✅ <100ms query latency
- ✅ 95%+ recall with HNSW
- Migration path to RAG Retriever documented

## Common Issues

**"cannot adapt type 'dict'"** → Wrap with `Jsonb(metadata)`

**"operator does not exist: vector <=> double"** → Convert to numpy: `np.array(embedding)`

**Low similarity scores** → Check normalization is enabled and working

**Connection refused** → Check Docker container is running on port 54320

## Cost Considerations

- OpenAI text-embedding-3-small: $0.02 per 1M tokens
- 10K documents (~7.5M tokens): ~$0.15 total
- Per-query cost: negligible (~$0.00003)
- 6.5x cheaper than text-embedding-3-large with similar performance
