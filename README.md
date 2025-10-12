# RAG Memory

[![PyPI package](https://img.shields.io/pypi/v/rag-memory?color=brightgreen&label=pypi%20package)](https://pypi.org/project/rag-memory/)
[![Python](https://img.shields.io/pypi/pyversions/rag-memory?color=blue)](https://pypi.org/project/rag-memory/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A production-ready PostgreSQL + pgvector RAG (Retrieval-Augmented Generation) system that works as both an **MCP server for AI agents** and a **standalone CLI tool**.

## What Is This?

RAG Memory gives AI agents and developers a powerful memory system for storing and retrieving documents semantically. It combines vector search with full document retrieval, allowing you to find the right information and get the complete context.

**Two ways to use it:**
1. **MCP Server** - Connect AI agents (Claude Desktop, Claude Code, Cursor) with 11 tools
2. **CLI Tool** - Direct command-line access for testing, automation, and bulk operations

**Key capabilities:**
- Semantic search across documents with vector embeddings
- Web crawling and documentation ingestion
- Document chunking for large files
- Collection management for organizing knowledge
- Full document lifecycle (create, read, update, delete)
- Cross-platform configuration system

## Getting Started

### 🚀 Recommended: Use the Claude Code Slash Command

**If you have Claude Code or Claude Desktop:**

1. Run the command: `/getting-started`
2. Follow the interactive guide that will:
   - Explain what RAG Memory does
   - Help you choose MCP server, CLI, or both
   - Guide you through installation and configuration
   - Test your setup with sample data

This is the easiest way to get started!

### 📦 Manual Installation

**For end users (install from PyPI):**

```bash
# Install globally
uv tool install rag-memory

# Start database (requires cloning repo for docker-compose.yml)
git clone https://github.com/YOUR-USERNAME/rag-memory.git
cd rag-memory
docker-compose up -d

# Run any command - first-run wizard will prompt for config
rag status
```

The first time you run any `rag` command, an interactive wizard will prompt you for:
- `DATABASE_URL` (defaults to local Docker: `postgresql://raguser:ragpass@localhost:54320/rag_poc`)
- `OPENAI_API_KEY` (get from https://platform.openai.com/api-keys)

Configuration is saved to `~/.rag-memory-env` with secure permissions.

**For developers (clone and develop):**

```bash
# Clone repository
git clone https://github.com/YOUR-USERNAME/rag-memory.git
cd rag-memory

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY

# Start database
docker-compose up -d

# Run CLI (uses .env in current directory)
uv run rag status
```

## CLI Commands

### Database & Status
```bash
rag init                      # Initialize database schema
rag status                    # Check database connection and stats
```

### Collection Management
```bash
rag collection create <name> [--description TEXT]
rag collection list
rag collection info <name>    # View stats and crawl history
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

### Search
```bash
# Basic search
rag search "query" --collection <name>

# Advanced options
rag search "query" --collection <name> --limit 10 --threshold 0.7 --verbose --show-source

# Search with metadata filter
rag search "query" --metadata '{"topic":"python"}'
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

RAG Memory exposes 11 tools via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for AI agent integration.

### Quick Setup

**1. Install globally:**
```bash
uv tool install rag-memory
```

**2. Start database:**
```bash
git clone https://github.com/YOUR-USERNAME/rag-memory.git
cd rag-memory
docker-compose up -d
```

**3. Configure your AI agent:**

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "args": [],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key-here",
        "DATABASE_URL": "postgresql://raguser:ragpass@localhost:54320/rag_poc"
      }
    }
  }
}
```

**4. Restart your AI agent** (quit and reopen)

**5. Test:** Ask your agent "List available RAG collections"

### Available MCP Tools (11 Total)

**Core RAG (3 tools):**
- `search_documents` - Semantic search across knowledge base
- `list_collections` - Discover available collections
- `ingest_text` - Add text content with auto-chunking

**Document Management (4 tools):**
- `list_documents` - Browse documents with pagination
- `get_document_by_id` - Retrieve full source document
- `update_document` - Edit existing documents (triggers re-chunking/re-embedding)
- `delete_document` - Remove outdated documents

**Advanced Ingestion (4 tools):**
- `get_collection_info` - Collection stats and crawl history
- `analyze_website` - Sitemap analysis for planning crawls
- `ingest_url` - Crawl web pages with duplicate prevention
- `ingest_file` - Ingest from file system

See [docs/MCP_SERVER_GUIDE.md](./docs/MCP_SERVER_GUIDE.md) for complete tool reference and examples.

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
- `collections` - Named groupings
- `chunk_collections` - Junction table (N:M relationship)

**Indexes:**
- HNSW on `document_chunks.embedding` for fast vector search
- GIN on metadata columns for efficient JSONB queries

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
    ├── server.py          # MCP server (FastMCP)
    └── tools.py           # 11 MCP tool implementations
```

## Documentation

- **[.reference/OVERVIEW.md](./.reference/OVERVIEW.md)** - Quick overview for slash command
- **[.reference/MCP_QUICK_START.md](./.reference/MCP_QUICK_START.md)** - MCP setup guide
- **[docs/ENVIRONMENT_VARIABLES.md](./docs/ENVIRONMENT_VARIABLES.md)** - Configuration system explained
- **[docs/MCP_SERVER_GUIDE.md](./docs/MCP_SERVER_GUIDE.md)** - Complete MCP tool reference
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
- See [.reference/MCP_QUICK_START.md](./.reference/MCP_QUICK_START.md)
- Read [docs/MCP_SERVER_GUIDE.md](./docs/MCP_SERVER_GUIDE.md)

**For issues:**
- Check troubleshooting sections above
- Review documentation in docs/ directory
- Check database logs: `docker-compose logs -f`

---

**Built with PostgreSQL + pgvector for production-grade semantic search.**
