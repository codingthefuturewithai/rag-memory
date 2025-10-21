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
uv run rag init
```

### Common Commands

**Running the CLI:**
```bash
# All commands use: uv run rag <command>
uv run rag status              # Check database connection
uv run rag test-similarity     # Validate similarity scores (key test!)
uv run rag benchmark          # Performance benchmarks

# Collection management
uv run rag collection create <name> [--description TEXT]
uv run rag collection list
uv run rag collection delete <name>

# Document ingestion (with automatic chunking by default)
uv run rag ingest text "content" --collection <name> [--metadata JSON]
uv run rag ingest file <path> --collection <name>  # Auto-chunks documents
uv run rag ingest file <path> --collection <name> --no-chunking  # Store whole document
uv run rag ingest directory <path> --collection <name> --extensions .txt,.md
uv run rag ingest directory <path> --collection <name> --recursive

# Web page ingestion (uses Crawl4AI for web scraping)
uv run rag ingest url <url> --collection <name>  # Crawl single page
uv run rag ingest url <url> --collection <name> --follow-links  # Follow internal links (depth=1)
uv run rag ingest url <url> --collection <name> --follow-links --max-depth 2  # Follow links 2 levels deep
uv run rag ingest url <url> --collection <name> --chunk-size 2500 --chunk-overlap 300  # Custom chunking

# Re-crawl web pages (delete old, re-ingest new)
# Only deletes pages matching crawl_root_url - other documents in collection unaffected
uv run rag recrawl <url> --collection <name>  # Re-crawl single page
uv run rag recrawl <url> --collection <name> --follow-links --max-depth 2  # Re-crawl with link following

# Document management
uv run rag document list [--collection NAME]  # List all source documents
uv run rag document view <ID> [--show-chunks] [--show-content]  # View document details

# Search (now supports both whole documents and chunks)
uv run rag search "query" [--collection NAME] [--limit N] [--threshold FLOAT] [--verbose]
uv run rag search "query" --chunks  # Search document chunks (recommended for chunked docs)
uv run rag search "query" --chunks --show-source  # Include full source document info
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
   - Search scoped to collection: `uv run rag search "query" --collection tech-docs`

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
uv run rag ingest url https://docs.example.com --collection api-docs --follow-links --max-depth 2

# Later, re-crawl to update content
uv run rag recrawl https://docs.example.com --collection api-docs --follow-links --max-depth 2

# Add different docs to same collection (unaffected by recrawl above)
uv run rag ingest url https://guides.example.com --collection api-docs --follow-links
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

## MCP Server (Model Context Protocol)

### Overview

The RAG system exposes an MCP server for AI agent integration. This enables Claude Desktop, OpenAI agents, and other MCP-compatible agents to access the RAG functionality.

**Status:** ✅ Fully implemented and tested (2025-10-12)
- 12 tools registered and functional
- Complete CRUD operations for document management
- All tests passing

### Quick Start

**Start the server:**
```bash
uv run python -m src.mcp.server
```

**Connect with Claude Desktop:**
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/Users/timkitchens/projects/ai-projects/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Available Tools (12 total)

**Core RAG Operations (3 essential):**
1. `search_documents` - Vector similarity search
2. `list_collections` - Discover knowledge bases
3. `ingest_text` - Add text content with auto-chunking

**Document Management (3 CRUD - ESSENTIAL for agent memory):**
4. `list_documents` - List documents with pagination
5. `update_document` - Edit content/metadata (triggers re-chunking/re-embedding)
6. `delete_document` - Remove outdated documents

**Enhanced Ingestion (6 advanced):**
7. `get_document_by_id` - Retrieve full source document
8. `get_collection_info` - Detailed collection statistics
9. `ingest_url` - Crawl web pages (Crawl4AI integration)
10. `ingest_file` - Ingest from file system
11. `ingest_directory` - Batch ingest from directory
12. `recrawl_url` - Update web documentation (delete + re-ingest)

### Implementation Details

**Server Name:** `rag-memory`
**Location:** `src/mcp/server.py` (FastMCP)
**Tool Implementations:** `src/mcp/tools.py` (all 12 tools)
**Testing:** `test_mcp_invocation.py` - validates all tools

**Key Features:**
- Auto-initialization of RAG components on startup
- JSON-serializable response format
- Comprehensive error handling
- Support for agent memory use cases (update/delete critical)

**Use Cases:**
- **Agent memory management:** Update company vision, coding standards, personal info
- **Knowledge base construction:** Crawl docs, search, retrieve context
- **Document lifecycle:** Create, read, update, delete with re-chunking

**Testing:**
```bash
# Validate all tools
uv run python test_mcp_invocation.py

# List registered tools
uv run python test_mcp_tools.py

# Test with MCP Inspector
npx @modelcontextprotocol/inspector
```

**Documentation:** See `MCP_IMPLEMENTATION_PLAN.md` for complete specifications and implementation details.

---

## Fly.io Deployment

### Overview

The MCP server is deployed to Fly.io at `https://rag-memory-mcp.fly.dev/sse` for remote AI agent access. The deployment connects to Supabase PostgreSQL and scales to zero when idle.

**Deployment Script:** `scripts/deploy.sh`

### Quick Commands

```bash
# Deploy to Fly.io (primary command)
./scripts/deploy.sh

# Or deploy directly with flyctl
~/.fly/bin/flyctl deploy --wait-timeout 300 --app rag-memory-mcp

# View logs
./scripts/deploy.sh logs

# Check deployment status
./scripts/deploy.sh status

# Restart the app
./scripts/deploy.sh restart

# SSH into container
./scripts/deploy.sh shell

# List secrets (values hidden)
./scripts/deploy.sh secrets
```

### Deployment Configuration

**Files:**
- `Dockerfile` - Multi-stage build with Playwright base image
- `fly.toml` - App configuration (region: iad, auto-scaling enabled)
- `.dockerignore` - Excludes unnecessary files from build

**Environment Variables (Fly.io Secrets):**
```bash
# Set secrets with flyctl
~/.fly/bin/flyctl secrets set DATABASE_URL="postgresql://..." --app rag-memory-mcp
~/.fly/bin/flyctl secrets set OPENAI_API_KEY="sk-..." --app rag-memory-mcp

# List secrets (values hidden for security)
~/.fly/bin/flyctl secrets list --app rag-memory-mcp
```

**Regions:**
- Primary: `iad` (Ashburn, VA) - closest to Supabase us-east-1

### Testing Deployment

```bash
# Test SSE endpoint
curl https://rag-memory-mcp.fly.dev/sse

# Test health endpoint (if implemented)
curl https://rag-memory-mcp.fly.dev/health
```

### Auto-Scaling

The deployment is configured to scale to zero when idle:
- **Min machines:** 0
- **Auto-stop:** 5 minutes idle
- **Auto-start:** On incoming request
- **Cost:** ~$3-5/month (vs $40/month always-on)

### Troubleshooting

**Check logs:**
```bash
./scripts/deploy.sh logs
# Or with flyctl directly
~/.fly/bin/flyctl logs --app rag-memory-mcp
```

**Check machine status:**
```bash
./scripts/deploy.sh status
```

**Restart if needed:**
```bash
./scripts/deploy.sh restart
```

**SSH into container for debugging:**
```bash
./scripts/deploy.sh shell
```

**Complete Documentation:**
- Deployment plan: `docs/FLYIO_DEPLOYMENT_PLAN.md`
- Implementation checklist: `docs/FLYIO_IMPLEMENTATION_CHECKLIST.md`
- Deployment summary: `docs/FLYIO_DEPLOYMENT_SUMMARY.md`

---

## RAG Search Optimization Results (2025-10-11)

**TL;DR: Baseline vector-only search is optimal. Both attempted optimizations decreased performance.**

### Test Environment
- **Dataset:** claude-agent-sdk collection (391 documents, 2,093 chunks)
- **Test Queries:** 20 queries across 4 categories (7 with ground truth labels)
- **Embedding Model:** text-embedding-3-small (1536 dimensions)
- **Evaluation Metrics:** Recall@5, Precision@5, MRR, nDCG@10

### Implemented Search Methods

#### ✅ Baseline (Vector-Only Search) - RECOMMENDED
**Implementation:** `src/retrieval/search.py`
```bash
uv run rag search "query" --collection name --limit 10
```

**Performance:**
- Recall@5: **81.0%** (any relevant), **78.6%** (highly relevant)
- Precision@5: **57.1%** (any relevant), **54.3%** (highly relevant)
- MRR: **0.679**
- nDCG@10: **1.471**
- Avg Latency: **413.6ms**

**Why it works so well:**
- High-quality documentation dataset with clear structure
- text-embedding-3-small effectively captures semantic meaning
- Proper chunking (~1000 chars, 200 overlap) with hierarchical splitting
- HNSW indexing provides fast, accurate retrieval

#### ❌ Phase 1: Hybrid Search (Vector + Keyword + RRF) - NOT RECOMMENDED
**Implementation:** `src/retrieval/hybrid_search.py`
```bash
uv run rag search "query" --collection name --hybrid
```

**Components:**
- PostgreSQL full-text search (tsvector + GIN index)
- Vector similarity search
- Reciprocal Rank Fusion (RRF, k=60) to merge rankings

**Performance:**
- Recall@5: 76.2% (↓ 4.8%)
- Precision@5: 45.7% (↓ 11.4%)
- MRR: 0.583 (↓ 14.1%)
- nDCG@10: 1.159 (↓ 21.2%)
- Avg Latency: 684.3ms (↑ 65%)

**Why it failed:**
- Keyword search adds noise for well-structured documentation
- Technical terms and abbreviations don't benefit from full-text matching
- Semantic embeddings already capture meaning better than keywords
- Added complexity and latency without quality improvement

**Database changes:**
- Migration: `migrations/001_add_fulltext_search.sql`
- Added `content_tsv tsvector` column to `document_chunks`
- Created GIN index on `content_tsv` (664 KB for 391 chunks)

**Status:** Code preserved but not recommended for production use.

#### ❌ Phase 2: Multi-Query Retrieval (Query Expansion + RRF) - NOT RECOMMENDED
**Implementation:** `src/retrieval/multi_query.py`
```bash
uv run rag search "query" --collection name --multi-query
```

**Components:**
- Rule-based query expansion (3 variations per query)
  - Add "documentation guide" context
  - Rephrase as question/statement
  - Add "setup configuration" specificity
- Vector search for each variation (3x API calls)
- RRF fusion of all results

**Performance:**
- Recall@5: 76.2% (↓ 4.8%)
- Recall@5 (highly relevant): 71.4% (↓ 7.2%)
- Precision@5: 51.4% (↓ 5.7%)
- MRR: 0.560 (↓ 17.5%)
- nDCG@10: 1.315 (↓ 10.6%)
- Avg Latency: 982.5ms (↑ 138%)

**Why it failed:**
- Simple rule-based query expansion is too naive
- Variations don't capture semantic nuances
- 3x embedding API calls = 3x latency and cost
- Original queries already well-formed enough for embeddings

**Status:** Code preserved but not recommended for production use.

#### ⏭️ Phase 3: Re-Ranking (Cross-Encoder) - SKIPPED
**Not implemented.** Analysis of benchmark results shows re-ranking would not help:

**Why we skipped re-ranking:**
1. **MRR is already high (0.679)** - First relevant doc appears at rank ~1.5 on average
2. **Top-5 recall is 81%** - Relevant docs are already in top positions
3. **Re-ranking can't fix retrieval failures** - The queries that fail (0% recall) don't have relevant docs in top 20
4. **Cost/benefit is poor** - Would add 50-200ms latency for minimal quality gain (~10% MRR improvement)

**When to reconsider:**
- If users complain that "the answer is there but not at the top" (ranking problem)
- If expanding to much larger, noisier corpus (precision becomes critical)
- If MRR drops significantly in production (ordering degraded)

**What WOULD help instead:**
- Better documentation structure/consolidation
- Synthetic Q&A pairs for common questions
- Improved metadata tagging
- Real user feedback on failed queries

### Final Recommendation

**✅ Use baseline vector-only search for production.**

**Comparison table:**

| Metric | Baseline | Hybrid | Multi-Query | Winner |
|--------|----------|--------|-------------|--------|
| Recall@5 (any) | 81.0% | 76.2% | 76.2% | **Baseline** |
| Recall@5 (high) | 78.6% | 78.6% | 71.4% | **Baseline** |
| Precision@5 | 57.1% | 45.7% | 51.4% | **Baseline** |
| MRR | 0.679 | 0.583 | 0.560 | **Baseline** |
| nDCG@10 | 1.471 | 1.159 | 1.315 | **Baseline** |
| Latency | 414ms | 684ms | 983ms | **Baseline** |

**Key insights:**
- 81% recall is excellent for this use case
- Simple solution (vector-only) outperforms complex optimizations
- High-quality dataset + strong embeddings = no need for advanced retrieval
- Scientific measurement prevented wasted optimization effort

**Documentation:**
- Detailed analysis: `RAG_OPTIMIZATION_RESULTS.md`
- Benchmark runners: `tests/benchmark/test_runner.py`, `run_phase1.py`, `run_phase2.py`
- Ground truth labels: `test-data/ground-truth-simple.yaml`
- Test queries: `test-data/test-queries.yaml`

### Search Method Selection Guide

**Use baseline (default) when:**
- ✅ Standard documentation/knowledge base queries
- ✅ Production deployment (best quality, lowest latency)
- ✅ Cost-sensitive applications (1 API call vs 3)

**Consider hybrid (--hybrid) when:**
- ⚠️ Experimenting with keyword matching
- ⚠️ Dataset has many exact-match technical terms
- ⚠️ You're willing to sacrifice quality for keyword coverage

**Consider multi-query (--multi-query) when:**
- ⚠️ Experimenting with query expansion
- ⚠️ Queries are extremely poorly worded
- ⚠️ Latency and cost are not concerns

**Recommendation:** Stick with baseline unless you have specific evidence it's failing in production.

---

## Knowledge Graph Integration (Graphiti + Neo4j)

### Overview

**Status:** 🚧 Phase 3 Complete, Phase 4 In Progress (as of 2025-10-17)

The system now supports **hybrid RAG + Knowledge Graph** architecture, combining:
- **RAG (pgvector)**: Semantic search for content retrieval
- **Knowledge Graph (Neo4j/Graphiti)**: Entity relationships and temporal reasoning

**Architecture:**
```
AI Agent Request
       ↓
  MCP Server
       ↓
UnifiedIngestionMediator
   ↓           ↓
RAG Store   Graph Store
(pgvector)  (Graphiti/Neo4j)
```

### Setup

**Prerequisites:**
```bash
# Start Neo4j via Docker
docker-compose -f docker-compose.graphiti.yml up -d

# Neo4j Browser: http://localhost:7474
# Username: neo4j
# Password: graphiti-password
```

**Environment Variables:**
```bash
# In .env (optional, defaults to localhost)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphiti-password
```

### Implementation Phases

#### ✅ Phase 1: Core Unified Ingestion (Completed)
- **File:** `src/unified/mediator.py`
- **What it does:** Routes `ingest_text()` to both RAG and Graph stores
- **Status:** Working - Test 1 passed with fictional data
- **Logging:** Comprehensive INFO-level logging added for debugging

#### ✅ Phase 2: Graph Query Tools (Completed)
- **Files:** `src/mcp/tools.py` (query_relationships_impl, query_temporal_impl)
- **Tools:**
  - `query_relationships()` - Search for entity relationships
  - `query_temporal()` - Track how knowledge evolved over time
- **Status:** Tools registered, tested with existing data

#### ✅ Phase 3: Extended Unified Ingestion (Completed 2025-10-17)
- **Extended to:** `ingest_url()`, `ingest_file()`, `ingest_directory()`
- **What changed:**
  - All three now route through `UnifiedIngestionMediator`
  - Web crawling, file ingestion, and directory ingestion update both stores
  - Graceful fallback to RAG-only if Graph unavailable
- **Status:** Code complete, partial testing done

#### 🚧 Phase 4: Consistency & Cleanup (In Progress)
**CRITICAL GAPS IDENTIFIED:**

1. **update_document() - RAG-only** ❌
   - Currently only updates RAG store
   - Graph keeps old entities/relationships
   - **Result:** Stale graph data when documents are edited

2. **delete_document() - RAG-only** ❌
   - Currently only deletes from RAG store
   - Graph keeps orphaned episode nodes
   - **Result:** Graph accumulates zombie episodes

3. **recrawl mode - RAG-only cleanup** ❌
   - Deletes old RAG documents before re-crawling
   - Graph episodes remain (no cleanup)
   - **Result:** Orphaned episodes accumulate with each recrawl

### Current Issues & Debugging (2025-10-17)

#### Issue 1: Wikipedia Ingestion Timeout
**Test:** Ingesting `https://en.wikipedia.org/wiki/Quantum_computing`

**What happened:**
- ✅ RAG ingestion succeeded (searchable via `search_documents`)
- ⏰ MCP Inspector timed out after 60 seconds
- ❌ Neo4j shows 4 episode nodes (`doc_290-294`) with **ZERO entities**
- ❓ Unknown if Graph ingestion completed or failed

**Observations:**
- Episode nodes exist → Graphiti.add_episode() was called
- No entities extracted → Either timeout or LLM returned empty
- RAG search works fine for quantum computing queries
- Graph queries return nothing quantum-related

**Possible causes:**
1. Graphiti LLM call (GPT-4o) took >60 seconds
2. Content too large for entity extraction
3. OpenAI API error/timeout
4. Wikipedia content format confused the LLM

**Debugging added:**
- Added comprehensive logging to:
  - `src/unified/graph_store.py` - tracks Graphiti calls
  - `src/unified/mediator.py` - tracks dual ingestion flow
  - `src/mcp/server.py` - logs to `logs/mcp_server.log`
- Fixed Crawl4AI stdout pollution (redirected to stderr)

**Next steps:**
1. Use `mode="recrawl"` to retry (avoids RAG duplicate error)
2. Monitor `logs/mcp_server.log` during ingestion
3. Determine if Graph ingestion completes or times out
4. Consider testing with smaller Wikipedia page

#### Issue 2: Graph Orphan Accumulation
**Problem:** Partial ingestions leave orphaned episode nodes

**Example:**
```
Ingestion attempt #1:
├─ RAG: ✅ doc_290 created
└─ Graph: ⏰ Episode "doc_290" created, but 0 entities

Recrawl attempt #2:
├─ RAG: ✅ doc_290 deleted, doc_295 created
└─ Graph: ❌ Episode "doc_290" still exists (orphan!)
            ✅ Episode "doc_295" created

Result: Graph has both doc_290 (empty) and doc_295 (with entities)
```

**Solution (Phase 4):**
Implement Graph cleanup in recrawl logic:
```python
if mode == "recrawl" and unified_mediator:
    # Get old documents
    old_docs = get_documents_by_crawl_url(url, collection_name)

    # Delete from Graph first
    for doc in old_docs:
        await graph_store.delete_episode(f"doc_{doc['id']}")

    # Then delete from RAG
    for doc in old_docs:
        delete_document(doc['id'])
```

### MCP Tools for Knowledge Graph

**New tools (Phase 2):**

1. **`query_relationships(query, num_results=5)`**
   - Search for entity relationships using natural language
   - Example: "How does my YouTube channel relate to my business?"
   - Returns: List of relationships with fact descriptions, types, timestamps

2. **`query_temporal(query, num_results=10)`**
   - Track how knowledge evolved over time
   - Example: "How has my business strategy changed?"
   - Returns: Timeline of facts with valid_from/valid_until timestamps

**Graceful degradation:**
- Both tools return `status="unavailable"` if Neo4j not running
- System falls back to RAG-only mode automatically
- No errors thrown, just informative status message

### Testing

**Test data ingestion:**
```bash
# Manual test script with fictional data
uv run python test_unified_ingestion.py
```

**Test graph queries:**
```bash
# Test relationship and temporal queries
uv run python test_graph_query_tools.py
```

**Neo4j Browser queries:**
```cypher
// View all entities and relationships
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25

// Find episode nodes
MATCH (n) WHERE n.name CONTAINS 'doc_' RETURN n

// Search for specific entities
MATCH (n) WHERE toLower(n.name) CONTAINS 'quantum' RETURN n
```

### Documentation

- **Implementation plan:** `docs/KNOWLEDGE_GRAPH_INTEGRATION.md`
- **Research:** `knowledge-graph-research-report.md`
- **Test scripts:** `test_unified_ingestion.py`, `test_graph_query_tools.py`

### Known Limitations

1. **No atomic transactions** - RAG and Graph updated sequentially (Phase 1 limitation)
2. **No rollback on failure** - If Graph fails, RAG changes persist
3. **No Graph cleanup** - update/delete/recrawl don't touch Graph (Phase 4 gap)
4. **Performance** - Entity extraction is LLM-heavy (30-60 seconds per document)
5. **Orphan accumulation** - Failed ingestions leave empty episode nodes

### When to Use Graph vs RAG

**Use RAG search when:**
- ✅ "What" questions - "What is my YouTube strategy?"
- ✅ Content retrieval - Need exact text passages
- ✅ Semantic similarity - Find similar documents
- ✅ Fast queries - Sub-second response time

**Use Graph queries when:**
- ✅ "How" questions - "How do my projects relate?"
- ✅ Relationship discovery - Connect entities across documents
- ✅ Temporal reasoning - "How has my thinking evolved?"
- ✅ Multi-hop questions - "What connects A to B to C?"

**Use both:**
- ✅ Graph finds entities → RAG retrieves detailed context
- ✅ RAG finds relevant docs → Graph maps relationships
- ✅ Complete memory system for AI agents

### Future Work (Phase 4+)

**Critical:**
1. ❌ Implement Graph cleanup in `update_document()`
2. ✅ Implement Graph cleanup in `delete_collection()` (Gap 1.1 - COMPLETE)
3. ❌ Implement Graph cleanup in `delete_document()`
4. ❌ Implement Graph cleanup in recrawl logic
5. ❌ Add two-phase commit for atomicity

**Nice to have:**
6. Optimize entity extraction for large documents
7. Batch entity extraction for directory ingestion
8. Add Graph-specific search filters to `search_documents()`
9. Implement Graph deduplication (merge similar entities)
10. Add Graph visualization tools
11. Performance profiling for Graph ingestion

---

## Implementation Gaps & Roadmap

**Full documentation:** `docs/IMPLEMENTATION_GAPS_AND_ROADMAP.md`

This document captures critical gaps and design issues identified during development. The gaps are prioritized by impact and complexity, with a clear roadmap for addressing them.

### Gap Status Summary (as of 2025-10-21)

| Gap # | Category | Issue | Priority | Status |
|-------|----------|-------|----------|--------|
| **1.1** | **Tools** | **delete_collection missing** | **HIGH** | **✅ COMPLETE** |
| **1.2** | **Tools** | **Tool count discrepancy** | **HIGH** | **✅ COMPLETE** |
| 2.1 | Architecture | Graph optionality complex | CRITICAL | Decision Needed |
| 2.2 | Installation | Setup too complex | HIGH | Decision Needed |
| 3.1 | Sync | delete_document → graph not cleaned | CRITICAL | Research ✓, Impl Needed |
| 3.2 | Sync | update_document → graph not synced | CRITICAL | Impl Needed |
| 3.3 | Sync | recrawl → graph orphans accumulate | CRITICAL | Impl Needed |
| 4.1 | Config | GPT-5 Nano model support | MEDIUM | Investigation Needed |
| 5.1 | Docs | Episode metadata not documented | HIGH | Doc Update Needed |
| 5.2 | Docs | RAG metadata incomplete | HIGH | Doc Update Needed |
| 6.1 | Architecture | Docker Compose clarity | MEDIUM | Audit Needed |
| 6.2 | Docs | Phase 4 terminology unclear | LOW | Clarification Needed |
| 7.0 | Audit | MCP tool graph assumptions | CRITICAL | Audit Needed |
| 8.1 | Planning | mcp_servers_workflow evaluation | HIGH | Review Needed |

### Completed Work: Gap 1.1 - Delete Collection Tool

**Status:** ✅ **COMPLETE** (2025-10-21)

**Requirements Met:**

1. ✅ **MCP Tool Created & Registered**
   - Tool name: `delete_collection`
   - Location: `src/mcp/server.py` + `src/mcp/tools.py`
   - Parameters: `name` (str, required), `confirm` (bool, default=False)
   - Returns: `{deleted, name, message, documents_affected}`

2. ✅ **Safety Implementation**
   - Strong warning in docstring: "⚠️ DANGEROUS OPERATION"
   - Two-step confirmation process:
     - `confirm=False`: Returns error "Confirmation required"
     - `confirm=True`: Actually deletes
   - Prevention of accidental deletion through explicit confirmation
   - Comprehensive docstring documenting what gets deleted

3. ✅ **Knowledge Graph Cleanup** (Phase 4 Implementation)
   - Queries `source_document_ids` BEFORE RAG deletion
   - Calls `graph_store.delete_episode_by_name(f"doc_{doc_id}")` for each document
   - Episodes verified deleted via Neo4j query in tests
   - Graceful error handling: RAG deletion always succeeds, graph cleanup is best-effort
   - Success message includes count: "N graph episodes cleaned"

4. ✅ **Testing Complete**
   - 5 MCP collection management tests (delete scenarios): **ALL PASS**
   - 1 comprehensive graph cleanup verification test: **PASS**
   - Test verifies episodes deleted from Neo4j via actual queries (not just message)
   - Test flow:
     1. Create collection + ingest 2 documents
     2. Query Neo4j to verify episodes exist (get UUIDs)
     3. Call delete_collection_impl
     4. Query Neo4j again with SAME method to verify episodes gone
     5. Assert `episodes_after == []`

5. ✅ **Documentation Updated**
   - Tool count: 15 → 17 tools
   - Updated: `.reference/MCP_QUICK_START.md`
   - Updated: `.reference/OVERVIEW.md`
   - Updated: Collection Management section (2 → 3 tools)

6. ✅ **Commits Made**
   - `c370b13` - Implement delete_collection MCP tool with safety confirmations
   - `cfa8728` - Add graph episode cleanup to delete_collection (Phase 4)
   - `a95c9bc` - Add comprehensive graph cleanup verification test
   - `7af4811` - Fix test fixture compatibility with pytest.mark.asyncio

**Key Implementation Details:**

- **Episode naming convention:** `doc_{source_document_id}` (e.g., `doc_378`, `doc_379`)
- **Graph cleanup implementation:** `src/mcp/tools.py:delete_collection_impl()` (lines 148-265)
- **Test file:** `tests/integration/test_delete_collection_graph_cleanup.py`
- **MCP registration:** `src/mcp/server.py:delete_collection()` (async wrapper with graph_store parameter)

**Test Verification (Latest Run):**
```
✅ Created 2 documents: [382, 383]
✅ Found episode: doc_382 (UUID: 46094128-...)
✅ Found episode: doc_383 (UUID: 8c313cd5-...)
✅ Collection deleted: Collection 'graph_cleanup_test_4697160272' and 2 document(s) permanently deleted. (2 graph episodes cleaned)
✅ Graph cleanup verified - all 2 episodes deleted
PASSED
```

### Completed Work: Gap 1.2 - Tool Count Discrepancy

**Status:** ✅ **COMPLETE** (2025-10-21)

**Requirements Met:**

1. ✅ **Tool Count Verified**
   - Actual count: 17 tools (verified via `grep -c "@mcp.tool()" src/mcp/server.py`)
   - Before Gap 1.1: 15 tools
   - After Gap 1.1 (delete_collection): 16 tools ← WAIT, should be 17?
   - Actual after Gap 1.1: 17 tools (includes delete_collection + other recent additions)

2. ✅ **Documentation Updated**
   - `.reference/OVERVIEW.md`: Updated to "17 tools for AI agents"
   - `.reference/MCP_QUICK_START.md`: Updated tool count reference
   - Collection Management section: Now shows 3 tools (create, update, delete)

3. ✅ **All References Updated**
   - Tool descriptions accurate
   - Tool count consistent across documentation
   - Category counts correct (7 categories)

**Tools Now Registered (17 total):**
- `search_documents` - Vector similarity search
- `list_collections` - Discover knowledge bases
- `create_collection` - Create new collection
- `update_collection_description` - Update collection description
- `delete_collection` - Delete collection with confirmation ← NEW
- `get_collection_info` - Collection statistics
- `ingest_text` - Add text content
- `ingest_url` - Crawl web pages
- `ingest_file` - Ingest from file system
- `ingest_directory` - Batch ingest from directory
- `recrawl_url` - Update web documentation
- `list_documents` - List documents with pagination
- `get_document_by_id` - Retrieve full source document
- `update_document` - Edit content/metadata
- `delete_document` - Remove outdated documents
- `query_relationships` - Search entity relationships
- `query_temporal` - Track knowledge evolution

**Verification:**
```bash
$ grep -c "@mcp.tool()" src/mcp/server.py
17
```

### Next Priorities (Recommended Order)

**Phase A: Critical Blockers (Do Next)**

1. **Gap 3.1-3.3:** Fix delete/update/recrawl graph sync
   - Similar implementation to Gap 1.1 (delete_collection)
   - Blocking: Production use of document management
   - Effort: Medium

2. **Gap 7.0:** Audit MCP tools for graph assumptions
   - Verify all tools handle graph unavailability gracefully
   - Blocking: Confident release
   - Effort: High

3. **Gap 2.1:** Decide Knowledge Graph optionality
   - Choose: Mandatory vs Optional vs Hidden
   - Blocking: Setup documentation
   - Effort: Medium (decision + code)

**Phase B: Important (Do Second)**

4. **Gap 2.2:** Solve setup complexity
   - Choose path: Docker Compose vs Vendor MCP
   - Effort: High

5. **Gap 5.1-5.2:** Complete metadata documentation
   - Low effort, high value for users
   - Effort: Low

6. **Gap 6.1:** Clarify Docker Compose files
   - Improve setup experience
   - Effort: Medium

**Phase C: Nice-to-Have (Do Later)**

7. **Gap 4.1:** GPT-5 Nano support (cost optimization)
8. **Gap 6.2:** Phase terminology clarification
9. **Gap 8.1:** Evaluate vendor MCP servers
