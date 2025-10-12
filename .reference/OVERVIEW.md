# RAG Memory - Overview

## What Is This?

RAG Memory is a **PostgreSQL + pgvector based RAG (Retrieval-Augmented Generation) system** that works as both an MCP server for AI agents AND a standalone CLI tool.

**RAG = Retrieval-Augmented Generation**
- Store documents in a vector database
- Search semantically for relevant context
- Retrieve full documents based on chunk matches
- Keep knowledge bases up-to-date

**Two ways to use it:**
1. **MCP Server** - AI agents (Claude Desktop, Claude Code, Cursor) use 11 tools to manage knowledge
2. **CLI Tool** - Direct command-line access for testing, bulk operations, and automation

**This tool provides:**
- Document storage with vector embeddings (OpenAI text-embedding-3-small)
- Semantic search (find relevant content, not just keywords)
- MCP server with 11 tools for AI agents
- CLI commands for all operations
- Web crawling (ingest documentation from websites)
- Document chunking (split large docs into searchable pieces)
- Collection management (organize knowledge by topic)

## Why MCP Server?

**MCP = Model Context Protocol** (Anthropic's open standard for AI agent integrations)

**Supported AI agents:**
- Claude Desktop
- Claude Code
- Cursor
- Custom agents with MCP support
- Any MCP-compatible client

**11 Tools Available:**

### Core RAG Operations (3 tools)
1. `search_documents` - Semantic search across knowledge base
2. `list_collections` - Discover available collections
3. `ingest_text` - Add text content with auto-chunking

### Document Management (4 tools)
4. `list_documents` - Browse documents with pagination
5. `get_document_by_id` - Retrieve full source document
6. `update_document` - Edit existing documents (re-chunks and re-embeds)
7. `delete_document` - Remove outdated documents

### Advanced Ingestion (4 tools)
8. `get_collection_info` - Collection statistics and crawl history
9. `analyze_website` - Sitemap analysis for planning crawls
10. `ingest_url` - Crawl web pages with duplicate prevention
11. `ingest_file` - Ingest from file system

## Use Cases

### Agent Memory
- Store company vision, coding standards, personal preferences
- Agent retrieves context across sessions
- Update knowledge as information changes

### Knowledge Base
- Ingest documentation (files, websites)
- Agent searches when answering questions
- Always has up-to-date context

### Documentation Management
- Crawl docs websites, track changes
- Re-crawl to update content
- Search across multiple doc sources

## How to Use It

### Option 1: MCP Server (For AI Agents)

**Install:**
```bash
uv tool install rag-memory
```

**Configure your AI agent:**
- Add MCP server config with DATABASE_URL and OPENAI_API_KEY
- See [MCP Quick Start](MCP_QUICK_START.md) for detailed setup

**Your agent can now:**
- Search your knowledge base
- Ingest new documents (text, files, URLs)
- Update/delete documents
- Manage collections

### Option 2: CLI Tool (For Direct Use)

**Install:**
```bash
uv tool install rag-memory
```

**First run (interactive setup):**
```bash
rag status  # Prompts for DATABASE_URL and OPENAI_API_KEY
```

**Common commands:**
```bash
rag collection create my-docs
rag ingest file document.pdf --collection my-docs
rag ingest url https://docs.example.com --collection my-docs --follow-links
rag search "how to configure X" --collection my-docs
rag document list --collection my-docs
```

See [CLAUDE.md](../CLAUDE.md) for complete CLI reference.

## Quick Architecture

1. **Database:** PostgreSQL 17 + pgvector extension (vector similarity search)
2. **Embeddings:** OpenAI text-embedding-3-small (converts text → vectors)
3. **Chunking:** Splits large docs (~1000 chars per chunk, 200 overlap)
4. **MCP Server:** Exposes 11 tools via Model Context Protocol
5. **CLI:** Direct command-line interface for all operations
6. **Config:** Three-tier env loading (env vars → .env → ~/.rag-memory-env)

## Key Features

### Vector Normalization
- All embeddings normalized to unit length
- Enables accurate cosine similarity search
- Critical for consistent similarity scores

### Document Chunking
- Hierarchical splitting (headers → paragraphs → sentences)
- ~1000 chars per chunk with 200 char overlap
- Preserves context across chunk boundaries
- Each chunk independently embedded and searchable

### Web Crawling
- Follow internal links (configurable depth)
- Sitemap.xml parsing for comprehensive crawls
- Duplicate prevention (mode="crawl" vs "recrawl")
- Crawl metadata tracking (root URL, session ID, timestamp)

### Collection Management
- Organize documents by topic/domain
- Many-to-many: documents can belong to multiple collections
- Search can be scoped to specific collection

### HNSW Indexing
- Fast approximate nearest neighbor search
- Optimized parameters for recall
- Handles large document collections efficiently

## Next Steps

### For MCP Server Setup
See [MCP Quick Start](MCP_QUICK_START.md) for AI agent configuration.

### For CLI Usage
1. Install: `uv tool install rag-memory`
2. Start database: Clone repo, run `docker-compose up -d`
3. First run: `rag status` (interactive setup)
4. Create collection: `rag collection create my-docs`
5. Ingest data: `rag ingest file document.txt --collection my-docs`
6. Search: `rag search "query" --collection my-docs`

### Complete Documentation
- [MCP Quick Start](MCP_QUICK_START.md) - MCP server setup for AI agents
- [ENVIRONMENT_VARIABLES.md](../ENVIRONMENT_VARIABLES.md) - Config system explained
- [CLAUDE.md](../CLAUDE.md) - Complete CLI commands reference
- [docs/MCP_SERVER_GUIDE.md](../docs/MCP_SERVER_GUIDE.md) - All 11 MCP tools detailed
- [README.md](../README.md) - Full project documentation
