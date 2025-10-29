# RAG Memory - Comprehensive Overview

## What Is RAG Memory?

RAG Memory is a **production-ready PostgreSQL + pgvector based RAG (Retrieval-Augmented Generation) system** that works as both an MCP (Model Context Protocol) server for AI agents AND a standalone CLI tool.

It achieves **0.73 similarity scores** for near-identical content through proper vector normalization + HNSW indexing (vs ChromaDB's 0.3 baseline), enabling reliable semantic search for knowledge management and agent memory.

**Key Achievement:** 81% recall@5 for semantic search across documentation datasets.

### What Does RAG Mean?

- **R** = Retrieval - Find relevant documents from your knowledge base
- **A** = Augmented - Add those documents to your AI prompt
- **G** = Generation - Let the AI generate responses with full context

### RAG Memory Provides:

- **Vector Database** - PostgreSQL with pgvector (not ChromaDB)
- **Semantic Search** - Find relevant content, not just keywords
- **Document Storage** - Full documents + searchable chunks
- **Automatic Chunking** - Split large docs into context-sized pieces
- **Collection Management** - Create, update, and delete collections
- **Web Crawling** - Ingest entire documentation sites
- **MCP Server** - 17 tools for AI agents (Claude, Cursor, etc.)
- **CLI Tool** - Direct command-line access
- **Knowledge Graph** - Optional entity/relationship tracking (Graphiti + Neo4j)
- **Fly.io Deployment** - Remote MCP server with auto-scaling

---

## Two Ways to Use RAG Memory

### Option 1: MCP Server (For AI Agents)

Use RAG Memory as an MCP server that AI agents can talk to.

**Supported AI Agents:**
- Claude Desktop
- Claude Code
- Cursor
- Custom MCP-compatible clients

**Benefits:**
- Your AI agent has a memory of your documents
- Persistent across conversations
- Update knowledge anytime
- 17 powerful tools available to agents

**Example Agent Conversation:**
```
Agent: "Search for PostgreSQL performance tips in my knowledge base"
RAG Memory: "Found 5 relevant documents about PostgreSQL optimization..."
Agent: "Summarize and create a guide for me"
```

### Option 2: CLI Tool (Direct Command-Line)

Use RAG Memory directly from your terminal.

**Use Cases:**
- Testing and experimentation
- Automation and scripts
- Batch document ingestion
- Direct database queries
- Local development

**Example CLI:**
```bash
rag collection create tech-docs --description "Technical Documentation"
rag ingest url https://docs.python.org --collection tech-docs --follow-links --max-depth 2
rag search "how to use decorators" --collection tech-docs
```

### Option 3: Both (Recommended)

Use both the MCP server (for agents) and CLI (for management) simultaneously.

---

## Architecture & How It Works

### Data Flow

```
1. INGEST
   Your Content → Auto-Chunking → Vector Embeddings → PostgreSQL + Neo4j
   (files, URLs, text)

2. STORE
   Source Document (full)
   ↓
   Chunks (searchable pieces with embeddings)
   ↓
   Collections (organized by topic)

3. SEARCH
   User Query → Generate Embedding → Vector Search (pgvector) → Rank Results

4. RETRIEVE
   Return matching chunks + optionally full source documents
```

### Core Components

**Database Layer (PostgreSQL):**
- Vector storage using pgvector extension
- HNSW indexing for fast similarity search
- JSONB metadata for flexible storage
- Full-text search capability

**Embedding Layer (OpenAI):**
- Model: text-embedding-3-small (1536 dimensions)
- Critical: Vector normalization to unit length
- Why important: Enables 0.73 similarity scores (vs 0.3 without)

**Chunking Layer:**
- Splits large documents into ~1000 character chunks
- Hierarchical splitting (headers → paragraphs → sentences)
- 200 character overlap for context preservation

**Search Layer:**
- pgvector's HNSW algorithm for fast retrieval
- 81% recall@5 on typical documentation datasets
- Configurable similarity thresholds
- Metadata filtering support

**Knowledge Graph Layer (Optional):**
- Neo4j with Graphiti for entity extraction
- Tracks relationships between entities
- Temporal reasoning capabilities

---

## Key Features Explained

### 1. Vector Normalization (The Critical Success Factor)

**What It Is:**
Converting embeddings to unit length (magnitude = 1) before storing and querying.

**Why It Matters:**
- **Without normalization:** Similarity scores ~0.3 (artificially low)
- **With normalization:** Similarity scores 0.7-0.95 (accurate)
- **Result:** Clear distinction between good/mediocre/poor matches

**Implementation:**
```python
# Every embedding normalized before storage
embedding = np.array(embedding) / np.linalg.norm(embedding)
```

**This single operation is the difference between this working well and not working at all.**

### 2. Document Chunking

**Why Chunk?**
- Large documents (>5KB) often have low overall similarity
- Chunking lets you find the exact relevant section
- Each chunk embedded independently for precise matching
- Maintains context with overlap between chunks

**Default Strategy:**
- Size: ~1000 characters (typical paragraph)
- Overlap: 200 characters (prevents cutting concepts)
- Separators: Headers → Paragraphs → Sentences → Words

**Example:**
```
Original: 10,000-character document about PostgreSQL
          ↓
Chunks:   Chunk 1: chars 0-1000 (introduction)
          Chunk 2: chars 800-1800 (intro + setup)
          Chunk 3: chars 1600-2600 (setup + performance)
          ...
          Each chunk embedded separately and searchable
```

**For Web Pages:**
- Larger chunks (2500 chars) work better
- More overlap (300 chars) for navigation context

### 3. Collections (Organization Layer)

**What Are They?**
Named groupings for organizing documents by topic/domain.

**Many-to-Many:**
- Single document can belong to multiple collections
- No duplication needed
- Enables flexible organization

**Use Cases:**
1. **Topic-based:** docs, blog, tutorials, troubleshooting
2. **Source-based:** github-docs, slack-exports, internal-wiki
3. **Temporal:** 2024-q1, 2024-q2, 2024-q3
4. **Access-based:** public, private, internal

**Example:**
```bash
rag collection create ai-docs --description "AI & ML Documentation"
rag ingest url https://docs.anthropic.com --collection ai-docs --follow-links
rag ingest file company-training.pdf --collection ai-docs
rag search "embeddings" --collection ai-docs
```

### 4. Web Crawling & Link Following

**Single Page:**
```bash
rag ingest url https://example.com/page --collection my-docs
# Extracts text from that single page
```

**Multiple Pages (Follow Links):**
```bash
rag ingest url https://docs.example.com \
    --collection my-docs \
    --follow-links --max-depth 2
# Crawls root, then all links 1 level deep
```

**Metadata Captured:**
- `crawl_root_url` - Starting URL (used for re-crawl targeting)
- `crawl_session_id` - Unique ID for this crawl session
- `crawl_depth` - Distance from root (0 = start page, 1 = linked pages)
- `parent_url` - Which page linked to this one
- `crawl_timestamp` - When crawled (ISO 8601)

### 5. Re-Crawl for Updates

**Problem:** Documentation changes, old versions become stale

**Solution: Re-Crawl Command**
```bash
rag recrawl https://docs.example.com \
    --collection my-docs \
    --follow-links --max-depth 2
```

**What Happens:**
1. Finds all pages originally crawled from https://docs.example.com
2. Deletes them (but NOT other documents in collection)
3. Re-crawls fresh content from root URL
4. Ingests new pages into same collection
5. Reports: "Deleted 12 old pages, crawled 15 new pages"

**Why This Approach:**
- ✅ Safe for mixed collections (files + web pages)
- ✅ No duplicate pages
- ✅ Always fresh content
- ✅ Tracks history via crawl metadata

### 6. MCP Server: 17 Tools

The MCP server exposes RAG Memory's capabilities to AI agents.

**Search & Discovery (4 tools):**
- `search_documents` - Semantic search with similarity scoring
- `list_collections` - Discover available knowledge bases
- `get_collection_info` - Statistics (doc count, chunk count, etc.)
- `analyze_website` - Understand site structure before crawling

**Document Management (5 tools):**
- `list_documents` - Browse stored documents with pagination
- `get_document_by_id` - Retrieve full source document
- `update_document` - Edit content/metadata (re-embeds)
- `delete_document` - Remove outdated documents
- `ingest_text` - Add text content directly

**Collection Management (3 tools):**
- `create_collection` - Create new named collection
- `update_collection_description` - Update collection metadata
- `delete_collection` - Delete collection and all documents (requires confirmation)

**Ingestion (3 tools):**
- `ingest_file` - Add documents from filesystem
- `ingest_directory` - Batch ingest entire directories
- `ingest_url` - Crawl web pages with link following

**Knowledge Graph (2 tools - Optional):**
- `query_relationships` - Search entity relationships
- `query_temporal` - Track knowledge evolution over time

**Specialized (1 tool):**
- `recrawl_url` - Update web documentation (delete old, crawl new)

### 7. Search Optimization Results

**Extensive Testing (2025-10-11):**
- Dataset: 391 documents, 2,093 chunks
- Queries: 20 queries across multiple categories

**Baseline (Vector-Only) - RECOMMENDED:**
| Metric | Score |
|--------|-------|
| Recall@5 (any relevant) | 81.0% |
| Recall@5 (highly relevant) | 78.6% |
| Precision@5 | 57.1% |
| Mean Reciprocal Rank | 0.679 |
| Avg Query Time | 413ms |

**Why Baseline Wins:**
- Simple works better than complex
- No artificial noise from keyword matching
- Semantic embeddings already capture meaning well
- 81% recall is excellent for most use cases

**Attempted Optimizations (NOT Recommended):**
- ❌ Hybrid search (vector + keyword) - 21% worse
- ❌ Multi-query retrieval (query expansion) - 17.5% worse
- ❌ Re-ranking - Not needed (MRR already high)

**Key Finding:** For well-structured documentation, baseline vector search is optimal.

---

## Use Cases & When to Use What

### Use Case 1: Agent Memory

**Goal:** Give your AI agent persistent memory of your documents

**Setup:**
- MCP server mode
- Store company standards, personal preferences, knowledge
- Agent searches when needed

**Example:**
```
Agent: "What's our coding standard for error handling?"
RAG Memory: [Searches knowledge base]
Agent: "I found our error handling guide... [gives answer]"
```

**Benefits:**
- Context persists across conversations
- Easy to update knowledge
- No need for custom integrations

### Use Case 2: Knowledge Base / Documentation Search

**Goal:** Make documentation searchable and accessible

**Setup:**
- CLI or MCP server
- Crawl documentation websites
- Users search for answers

**Example:**
```bash
# Initial ingestion
rag ingest url https://docs.python.org --collection python-docs --follow-links --max-depth 3

# Later: re-crawl to update
rag recrawl https://docs.python.org --collection python-docs --follow-links --max-depth 3

# Search anytime
rag search "how to use type hints" --collection python-docs
```

**Benefits:**
- One-time crawl cost (~$0.03 for 500 pages)
- Unlimited free searches
- Updates tracked automatically

### Use Case 3: Technical Research

**Goal:** Extract relationships and insights from documents

**Setup:**
- Knowledge graph enabled (Neo4j + Graphiti)
- RAG search for content
- Graph queries for relationships

**Example:**
```
User: "Which projects depend on the authentication service?"
Graph Query: [Finds all related entities and relationships]
User: "Now show me details on project X"
RAG Search: [Returns relevant documentation]
```

**Benefits:**
- Multi-hop reasoning (A connects to B to C)
- Temporal tracking ("How has our architecture evolved?")
- Entity-level organization

### Use Case 4: Bulk Document Processing

**Goal:** Ingest large document collections

**Setup:**
- CLI mode
- Directory ingestion with filtering

**Example:**
```bash
# Ingest all .md and .txt files recursively
rag ingest directory ./my-docs \
    --collection my-knowledge \
    --extensions .md,.txt \
    --recursive
```

**Benefits:**
- Batch processing
- No UI needed
- Scriptable for automation

---

## Performance & Similarity Scores

### Understanding Similarity Scores

**Score Range:** 0.0 to 1.0

**Interpretation:**
- **0.90-1.00:** Near-identical (exact match or rephrasing)
- **0.70-0.89:** Highly relevant (exactly what you're looking for)
- **0.50-0.69:** Related (relevant but less direct)
- **0.30-0.49:** Somewhat related (might be useful)
- **0.00-0.29:** Loosely related or unrelated

**Typical Distribution:**
```
Very high (0.90+)        ████ (rare)
High (0.70-0.89)         ████████████████ (most matches)
Medium (0.50-0.69)       ██████████ (related docs)
Low (0.30-0.49)          ███ (marginal)
Very low (0.00-0.29)     ██ (noise)
```

### Threshold Tuning

**Default Behavior:**
- Return top 10 results regardless of score
- Good for exploring what's available

**Strict Matching:**
```bash
rag search "query" --threshold 0.7
```
- Only return high-confidence matches (0.7+)
- Useful when you want only exact answers

**Broad Search:**
```bash
rag search "query" --threshold 0.3
```
- Include loosely related documents
- Useful for exploratory searches

**Recommended Thresholds:**
- `0.7` - Production/strict mode
- `0.5` - Default/balanced mode
- `0.3` - Exploratory/research mode

---

## Deployment Options

### Option 1: Local Development

**Perfect for:** Testing, development, small teams

**Setup:**
```bash
# Clone and run setup script
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
python scripts/setup.py

# Setup handles everything: Docker, config, CLI installation, verification
```

**Cost:** Free (self-hosted)

**Considerations:**
- Database runs on your machine
- No cloud dependency
- Good for experimenting

### Option 2: Fly.io Deployment

**Perfect for:** Production AI agents, remote access

**Features:**
- Auto-scales to zero (costs $3-5/month idle)
- Remote SSE endpoint: `https://rag-memory-mcp.fly.dev/sse`
- Database in Supabase (managed PostgreSQL)

**Cost:** $3-5/month (auto-scaling) or $40+/month (always-on)

**Setup:**
```bash
./scripts/deploy.sh
```

**Considerations:**
- Requires Supabase PostgreSQL instance
- MCP server accessible from anywhere
- Can serve multiple AI agents

### Option 3: Hybrid

**Perfect for:** Teams wanting local + cloud

**Setup:**
- Local: CLI for administration
- Cloud: MCP server for agent access

**Benefits:**
- Full control locally
- Agent access from anywhere
- Backup and disaster recovery

---

## Costs & Budgets

### API Costs (OpenAI Embeddings)

**Model:** text-embedding-3-small
**Price:** $0.02 per 1 million tokens

**Typical Costs:**
| Dataset Size | One-Time Cost | Monthly (+ daily updates) |
|--------------|---------------|-------------------------|
| 1,000 docs | $0.02 | $0.02/month |
| 10,000 docs | $0.15 | $0.18/month |
| 100,000 docs | $1.50 | $1.80/month |
| 1,000 web pages | $0.06 | $0.09/month |

**Important:** Searches are FREE (use PostgreSQL locally, no API calls)

### Database Costs

**Local Development:**
- Docker: Free
- Storage: Your machine

**Supabase (Production):**
- $25-100/month depending on size

### Fly.io Deployment

- Auto-scale to zero: $3-5/month
- Always-on: $40/month per instance

### Total Budget Examples

**Individual Developer:**
- OpenAI: $0.20/month
- Database: Free (local) or $25/month (Supabase)
- Deployment: Free (local) or $5/month (Fly.io)
- **Total: Free - $30/month**

**Small Team (5 people):**
- OpenAI: $0.50/month
- Database: $25/month (Supabase)
- Deployment: $5/month (Fly.io)
- **Total: $30/month**

**Enterprise:**
- OpenAI: $5-20/month
- Database: $50-200/month (large Supabase)
- Deployment: $50-100/month (multiple instances)
- **Total: $100-320/month**

---

## Quick Comparisons

### RAG Memory vs Alternatives

| Feature | RAG Memory | Pinecone | Weaviate | ChromaDB |
|---------|-----------|----------|----------|----------|
| **Cost** | Cheap | Expensive | Moderate | Free |
| **Similarity Scores** | 0.73 (good) | Good | Good | 0.3 (poor) |
| **Web Crawling** | Yes | No | No | No |
| **Knowledge Graph** | Optional | No | Yes | No |
| **Self-Hosted** | Yes | No | Yes | Yes |
| **MCP Support** | Yes (native) | No | No | No |
| **Production Ready** | Yes | Yes | Yes | Beta |

### text-embedding-3-small vs Alternatives

| Model | Cost | Quality | Speed |
|-------|------|---------|-------|
| **text-embedding-3-small** | $0.02/1M tokens | High | Fast |
| text-embedding-3-large | $0.13/1M tokens | Very High | Fast |
| text-embedding-ada-002 | $0.10/1M tokens | Medium | Medium |
| Local (Sentence Transformers) | Free | Medium | Depends |

**Recommendation:** Start with text-embedding-3-small (best value)

---

## What's Included & What's Not

### ✅ Fully Implemented & Recommended

- PostgreSQL + pgvector vector database
- Vector normalization (critical!)
- Document chunking with overlap
- Collection management
- Web crawling with link following
- Re-crawl for updates
- 17 MCP tools
- CLI with 25+ commands
- Metadata filtering
- HNSW indexing
- 81%+ recall@5 performance

### ⚠️ Implemented But Experimental

- Knowledge Graph integration (Graphiti + Neo4j)
  - Text/file/directory/URL ingestion works
  - Query tools work (relationships, temporal)
  - ⚠️ NOT recommended for production until cleanup phase complete
  - ⚠️ No graph cleanup on document update/delete yet

### ❌ Analyzed But Not Recommended

- Hybrid search (vector + keyword) - Performs worse than baseline
- Multi-query retrieval - Performs worse than baseline
- Re-ranking with cross-encoders - Not needed for this use case

### ❌ Not Planned

- Custom embedding models (only OpenAI supported)
- Other databases (PostgreSQL only)
- Real-time streaming (batch ingestion only)

---

## Getting Started

### 5-Minute Setup

1. **Clone and setup:**
   ```bash
   git clone https://github.com/yourusername/rag-memory.git
   cd rag-memory
   python scripts/setup.py
   ```

2. **Create collection:**
   ```bash
   rag collection create my-docs --description "My Documentation"
   ```

5. **Ingest data:**
   ```bash
   rag ingest text "PostgreSQL is powerful" --collection my-docs
   ```

6. **Search:**
   ```bash
   rag search "PostgreSQL" --collection my-docs
   ```

### Next Steps

**For MCP Server Users:**
- See [MCP Quick Start](MCP_QUICK_START.md) for agent configuration

**For CLI Users:**
- See [CLAUDE.md](../CLAUDE.md) for complete command reference
- Try: `rag --help` for command overview

**For Cost Estimation:**
- See [PRICING.md](PRICING.md) for detailed calculations

**For Advanced Topics:**
- See [SEARCH_OPTIMIZATION.md](.reference/SEARCH_OPTIMIZATION.md) for optimization details
- See [KNOWLEDGE_GRAPH.md](.reference/KNOWLEDGE_GRAPH.md) for graph features

---

## Key Principles

1. **Vector Normalization is Critical** - Non-negotiable for good similarity scores
2. **Chunking Improves Search** - Larger documents benefit from strategic chunking
3. **Simple Works Best** - Baseline vector search outperforms complex optimizations
4. **Metadata is Powerful** - Use JSONB flexibility for organization
5. **Collections Scale** - Many-to-many design enables flexible organization
6. **Reproducibility** - Crawl metadata enables auditable, updatable ingestion

---

## Support & Resources

- **Project:** https://github.com/anthropics/rag-memory (or your fork)
- **Issues:** GitHub Issues for bug reports
- **Documentation:**
  - [MCP Quick Start](MCP_QUICK_START.md) - Agent setup
  - [PRICING.md](PRICING.md) - Cost analysis
  - [../CLAUDE.md](../CLAUDE.md) - CLI reference
  - [SEARCH_OPTIMIZATION.md](.reference/SEARCH_OPTIMIZATION.md) - Performance details
  - [KNOWLEDGE_GRAPH.md](.reference/KNOWLEDGE_GRAPH.md) - Graph features

---

**Last Updated:** 2025-10-20
**Status:** Production Ready
**Version:** 0.13.0
