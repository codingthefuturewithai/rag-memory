# RAG Memory

[![PyPI package](https://img.shields.io/pypi/v/rag-memory?color=brightgreen&label=pypi%20package)](https://pypi.org/project/rag-memory/)
[![Python](https://img.shields.io/pypi/pyversions/rag-memory?color=blue)](https://pypi.org/project/rag-memory/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready **PostgreSQL + pgvector + Neo4j** knowledge management system with dual storage for semantic search (RAG) and knowledge graphs. Works as an **MCP server for AI agents** and a **standalone CLI tool**.

## ⚡ Quick Start (30 minutes)

Open a new terminal and run:

```bash
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
python scripts/setup.py
```

This setup script will:
- ✅ Check you have Docker installed
- ✅ Start PostgreSQL and Neo4j containers
- ✅ Ask for your OpenAI API key
- ✅ Initialize your local knowledge base
- ✅ Install the `rag` CLI tool

**That's it!** After setup completes, you'll have a working RAG Memory system ready to use.

---

## What Is This?

RAG Memory combines two powerful databases for knowledge management:

- **PostgreSQL + pgvector** - Semantic search across document content (RAG layer)
- **Neo4j** - Entity relationships and knowledge graphs (KG layer)

Both databases work together automatically - when you ingest a document, it's indexed in both systems simultaneously.

**Two ways to use it:**
1. **MCP Server** - Connect AI agents (Claude Desktop, Claude Code, Cursor) with 17 MCP tools
2. **CLI Tool** - Direct command-line access for testing, automation, and bulk operations

**Key capabilities:**
- Semantic search with vector embeddings (pgvector + HNSW indexing)
- Knowledge graph queries for relationships and entities
- Web crawling and documentation ingestion
- Document chunking for large files
- Collection management for organizing knowledge
- Full document lifecycle (create, read, update, delete)
- Cross-platform configuration system

**📚 Complete Documentation:** See [`.reference/`](./.reference/) directory for comprehensive guides (setup, MCP tools, pricing, search optimization, knowledge graphs)

### For Developers (Code Modifications)

If you want to modify the code:

```bash
# Clone repository
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory

# Install dependencies
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# Run tests or development commands
uv run pytest
uv run rag status
```

## CLI Commands

### Database & Status
```bash
rag status                    # Check database connection and stats
```

### Collection Management
```bash
rag collection create <name> --description TEXT  # Description now required
rag collection list
rag collection info <name>    # View stats and crawl history
rag collection update <name> --description TEXT  # Update collection description
rag collection delete <name>
```

### Document Ingestion

**Text:**
```bash
rag ingest text "content" --collection <name> [--metadata JSON]
```

**Files:**
```bash
rag ingest file <path> --collection <name>
rag ingest directory <path> --collection <name> --extensions .txt,.md [--recursive]
```

**Web Pages:**
```bash
# Analyze website structure first
rag analyze https://docs.example.com

# Crawl single page
rag ingest url https://docs.example.com --collection docs

# Crawl with link following
rag ingest url https://docs.example.com --collection docs --follow-links --max-depth 2

# Re-crawl to update content
rag recrawl https://docs.example.com --collection docs --follow-links --max-depth 2
```

### Semantic Search (RAG Layer)

**⚠️ IMPORTANT: Use Natural Language, Not Keywords**
This system uses **semantic similarity search**, not keyword matching. Always use complete questions or sentences:
- ✅ Good: `"How do I configure authentication in the system?"`
- ❌ Bad: `"authentication configuration"`

```bash
# Basic search
rag search "How do I configure authentication?" --collection <name>

# Advanced options
rag search "What are the best practices for error handling?" --collection <name> --limit 10 --threshold 0.7 --verbose --show-source

# Search with metadata filter
rag search "How do I use decorators in Python?" --metadata '{"topic":"python"}'
```

### Knowledge Graph Search

**Query Entity Relationships:**
```bash
# Find connections between concepts
rag graph query-relationships "How does PostgreSQL relate to semantic search?" --limit 5

# With threshold tuning
rag graph query-relationships "What connects Docker to Kubernetes?" --threshold 0.5

# Scoped to collection
rag graph query-relationships "How do transformers relate to attention mechanisms?" --collection ai-docs

# Verbose output (shows node IDs, timestamps)
rag graph query-relationships "How does Python relate to machine learning?" --verbose
```

**Query Temporal Evolution:**
```bash
# See how knowledge changed over time
rag graph query-temporal "How has my understanding of quantum computing evolved?" --limit 10

# Filter by time window
rag graph query-temporal "What decisions did I make in December?" \
  --valid-from "2025-12-01T00:00:00" \
  --valid-until "2025-12-31T23:59:59"

# With confidence threshold
rag graph query-temporal "How has my focus changed?" --threshold 0.5 --collection business-docs
```

### Document Management
```bash
# List documents
rag document list [--collection <name>]

# View document details
rag document view <ID> [--show-chunks] [--show-content]

# Update document (re-chunks and re-embeds)
rag document update <ID> --content "new content" [--title "title"] [--metadata JSON]

# Delete document
rag document delete <ID> [--confirm]
```

## MCP Server for AI Agents

RAG Memory exposes 17 tools via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for AI agent integration.

### Quick Setup

**1. Run the setup script:**
```bash
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
python scripts/setup.py
```

After setup, RAG Memory's MCP server is automatically running in Docker on port 8000.

**2. Connect to Claude Code:**
```bash
claude mcp add rag-memory --type sse --url http://localhost:8000/sse
```

**3. Connect to Claude Desktop** (optional):

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "args": []
    }
  }
}
```

Then restart Claude Desktop.

**4. Test:** Ask your agent "List RAG Memory collections"

### Available MCP Tools (18 Total)

**Core RAG (3 tools):**
- `search_documents` - Semantic search across knowledge base
- `list_collections` - Discover available collections
- `ingest_text` - Add text content with auto-chunking

**Knowledge Graph (2 tools):**
- `query_relationships` - Search entity relationships using natural language
- `query_temporal` - Query how knowledge evolved over time

**Collection Management (5 tools):**
- `create_collection` - Create new collections (description required)
- `get_collection_info` - Collection stats and crawl history
- `get_collection_metadata_schema` - View metadata schema for a collection
- `update_collection_metadata` - Update collection metadata schema (additive only)
- `delete_collection` - Delete collection and all its documents (admin function)

**Document Management (4 tools):**
- `list_documents` - Browse documents with pagination
- `get_document_by_id` - Retrieve full source document
- `update_document` - Edit existing documents (triggers re-chunking/re-embedding)
- `delete_document` - Remove outdated documents

**Advanced Ingestion (4 tools):**
- `analyze_website` - Sitemap analysis for planning crawls
- `ingest_url` - Crawl web pages with duplicate prevention (crawl/recrawl modes)
- `ingest_file` - Ingest from file system
- `ingest_directory` - Batch ingest from directories

See [`.reference/MCP_QUICK_START.md`](./.reference/MCP_QUICK_START.md) for complete tool reference and examples.

## Configuration System

RAG Memory uses a three-tier priority system for configuration:

1. **Environment variables** (highest priority) - Set in your shell
2. **Project `.env` file** (current directory only) - For developers
3. **Global `~/.rag-memory-env`** (lowest priority) - For end users

**For CLI usage:** First run triggers interactive setup wizard

**For MCP server:** Configuration comes from MCP client config (not files)

See [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md) for complete details.

## Key Features

### Vector Search with pgvector
- PostgreSQL 17 + pgvector extension
- HNSW indexing for fast approximate nearest neighbor search
- Vector normalization for accurate cosine similarity
- Optimized for 95%+ recall

### Document Chunking
- Hierarchical text splitting (headers → paragraphs → sentences)
- ~1000 chars per chunk with 200 char overlap
- Preserves context across boundaries
- Each chunk independently embedded and searchable
- Source documents preserved for full context retrieval

### Web Crawling
- Built on Crawl4AI for robust web scraping
- Sitemap.xml parsing for comprehensive crawls
- Follow internal links with configurable depth
- Duplicate prevention (crawl mode vs recrawl mode)
- Crawl metadata tracking (root URL, session ID, timestamp)

### Collection Management
- Organize documents by topic/domain
- Many-to-many relationships (documents can belong to multiple collections)
- Search can be scoped to specific collection
- Collection statistics and crawl history
- Required descriptions for better organization (enforced by database constraint)

### Full Document Lifecycle
- Create: Ingest from text, files, directories, URLs
- Read: Search chunks, retrieve full documents
- Update: Edit content with automatic re-chunking/re-embedding
- Delete: Remove outdated documents and their chunks

## Architecture

### Database Schema

**Source documents and chunks:**
- `source_documents` - Full original documents
- `document_chunks` - Searchable chunks with embeddings (vector[1536])
- `collections` - Named groupings (description required with NOT NULL constraint)
- `chunk_collections` - Junction table (N:M relationship)

**Indexes:**
- HNSW on `document_chunks.embedding` for fast vector search
- GIN on metadata columns for efficient JSONB queries

**Migrations:**
- Managed by Alembic (see `docs/DATABASE_MIGRATION_GUIDE.md`)
- Version tracking in `alembic_version` table
- Run migrations: `uv run rag migrate`

### Python Application

```
src/
├── cli.py                 # Command-line interface
├── core/
│   ├── config_loader.py   # Three-tier environment configuration
│   ├── first_run.py       # Interactive setup wizard
│   ├── database.py        # PostgreSQL connection management
│   ├── embeddings.py      # OpenAI embeddings with normalization
│   ├── collections.py     # Collection CRUD operations
│   └── chunking.py        # Document text splitting
├── ingestion/
│   ├── document_store.py  # High-level document management
│   ├── web_crawler.py     # Web page crawling (Crawl4AI)
│   └── website_analyzer.py # Sitemap analysis
├── retrieval/
│   └── search.py          # Semantic search with pgvector
└── mcp/
    ├── server.py          # MCP server (FastMCP) with 18 MCP tools
    └── tools.py           # 18 MCP tool implementations
```

## Documentation

- **[.reference/OVERVIEW.md](./.reference/OVERVIEW.md)** - Quick overview for slash command
- **[.reference/MCP_QUICK_START.md](./.reference/MCP_QUICK_START.md)** - MCP setup guide with all 18 tools documented
- **[docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md)** - Configuration system explained
- **[docs/DATABASE_MIGRATION_GUIDE.md](./docs/DATABASE_MIGRATION_GUIDE.md)** - Database schema migration guide (Alembic)
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - System architecture and design decisions
- **[CLAUDE.md](./CLAUDE.md)** - Development guide and CLI reference

## Prerequisites

- **Docker & Docker Compose** - For PostgreSQL database
- **uv** - Fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Python 3.12+** - Managed by uv
- **OpenAI API Key** - For embedding generation (https://platform.openai.com/api-keys)

## Technology Stack

- **Database:** PostgreSQL 17 + pgvector extension
- **Language:** Python 3.12
- **Package Manager:** uv (Astral)
- **Embedding Model:** OpenAI text-embedding-3-small (1536 dims)
- **Web Crawling:** Crawl4AI (Playwright-based)
- **MCP Server:** FastMCP (Anthropic)
- **CLI Framework:** Click + Rich
- **Testing:** pytest

## Cost Analysis

**OpenAI text-embedding-3-small:** $0.02 per 1M tokens

Example usage:
- 10,000 documents × 750 tokens avg = 7.5M tokens
- One-time embedding cost: **$0.15**
- Per-query cost: ~$0.00003 (negligible)

Extremely cost-effective for most use cases.

## Development

### Running Tests
```bash
uv run pytest                          # All tests
uv run pytest tests/test_embeddings.py # Specific file
```

### Code Quality
```bash
uv run black src/ tests/               # Format
uv run ruff check src/ tests/          # Lint
```

## Troubleshooting

### Database connection errors
```bash
docker-compose ps                      # Check if running
docker-compose logs postgres           # View logs
docker-compose restart                 # Restart
docker-compose down -v && docker-compose up -d  # Reset
```

### Configuration issues
```bash
# Check global config
cat ~/.rag-memory-env

# Re-run first-run wizard
rm ~/.rag-memory-env
rag status

# Check environment variables
env | grep -E '(DATABASE_URL|OPENAI_API_KEY)'
```

### MCP server not showing in agent
- Check JSON syntax in MCP config (no trailing commas!)
- Verify both DATABASE_URL and OPENAI_API_KEY in `env` section
- Check MCP logs: `~/Library/Logs/Claude/mcp*.log` (macOS)
- Restart AI agent completely (quit and reopen)

See [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md) troubleshooting section for more.

## License

MIT License - See LICENSE file for details.

## Support

**For help getting started:**
- Run `/getting-started` slash command in Claude Code
- Read [.reference/OVERVIEW.md](./.reference/OVERVIEW.md)
- Check [docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md)

**For MCP server setup:**
- See [.reference/MCP_QUICK_START.md](./.reference/MCP_QUICK_START.md) - Complete tool reference and examples

**For issues:**
- Check troubleshooting sections above
- Review documentation in docs/ directory
- Check database logs: `docker-compose logs -f`

---

**Built with PostgreSQL + pgvector for production-grade semantic search.**
