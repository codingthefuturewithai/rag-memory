# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG Memory is a production-ready knowledge management system combining PostgreSQL+pgvector (semantic search) with Neo4j (knowledge graphs). It operates as both an MCP server for AI agents and a standalone CLI tool.

**Key Architecture:**
- **Dual Storage:** Vector embeddings in PostgreSQL (RAG layer) + Entity relationships in Neo4j (Knowledge Graph layer)
- **Unified Ingestion:** `UnifiedIngestionMediator` (src/unified/mediator.py) orchestrates sequential writes to both stores
- **MCP Server:** Exposes 17 tools via FastMCP for AI agent integration
- **CLI Tool:** Direct command-line access for testing and automation

## Development Commands

### Environment Setup
```bash
# Install dependencies (uses uv package manager)
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your OPENAI_API_KEY and database URLs
```

### Database Management
```bash
# Start services (PostgreSQL + Neo4j in Docker)
uv run rag start

# Check system status
uv run rag status

# View service logs
uv run rag logs [postgres|neo4j|mcp]

# Stop services
uv run rag stop
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_embeddings.py

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run integration tests only
uv run pytest tests/integration/

# Run unit tests only
uv run pytest tests/unit/
```

### Code Quality
```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking (if configured)
uv run mypy src/
```

### MCP Server Development
```bash
# Run MCP server in stdio mode (for Claude Desktop/Cursor)
uv run rag-mcp-stdio

# Run MCP server in SSE mode (for debugging/testing)
uv run rag-mcp-sse

# Test MCP server with MCP Inspector
uv run rag-mcp-sse  # Terminal 1
# Then open http://localhost:3001 in MCP Inspector
```

## Architecture & Code Organization

### Configuration System (Three-Tier Priority)
1. **Environment variables** (highest priority) - Set in shell
2. **Project .env file** (development) - Current directory only
3. **System config** (lowest priority) - OS-standard locations via platformdirs
   - macOS: `~/Library/Application Support/rag-memory/config.yaml`
   - Linux: `~/.config/rag-memory/config.yaml`
   - Windows: `%LOCALAPPDATA%\rag-memory\config.yaml`

**Key module:** `src/core/config_loader.py`

### Dual Storage Architecture

**RAG Store (PostgreSQL + pgvector):**
- Tables: `source_documents`, `document_chunks`, `collections`, `chunk_collections`
- HNSW index on embeddings for fast vector search
- Managed by: `src/ingestion/document_store.py`, `src/retrieval/search.py`

**Knowledge Graph (Neo4j):**
- Powered by Graphiti (graphiti-core library)
- Extracts entities and relationships from ingested content
- Managed by: `src/unified/graph_store.py`

**Unified Ingestion:**
- `src/unified/mediator.py` - Orchestrates sequential writes (RAG first, then Graph)
- **Important:** Not truly atomic yet - potential for inconsistency if second write fails
- Future enhancement: Two-phase commit

### CLI Command Structure

**Thin orchestrator pattern:** `src/cli.py` imports and registers command groups from `src/cli_commands/`:
- `service.py` - start/stop/restart/status
- `collection.py` - create/list/info/delete collections
- `ingest.py` - text/file/directory/url ingestion
- `document.py` - list/view/update/delete documents
- `search.py` - semantic search
- `graph.py` - query-relationships/query-temporal
- `analyze.py` - website structure analysis
- `config.py` - show/edit configuration
- `logs.py` - view service logs

### MCP Server Architecture

**Entry point:** `src/mcp/server.py`
- Uses FastMCP framework
- Lifespan manager initializes RAG + Graph components at startup
- **Fail-fast design:** Server won't start if PostgreSQL OR Neo4j unavailable
- Startup validations: Schema checks for both databases
- Health check endpoint: `/health` (for Docker healthchecks)

**Tool implementations:** `src/mcp/tools.py`
- 17 MCP tools exposed to AI agents
- All tools follow pattern: `@mcp.tool()` decorator → calls `*_impl()` function
- **CRITICAL:** MCP tool parameters must NOT use `Optional[T]` type hints
  - ✅ Correct: `param: str | None = None`
  - ❌ Wrong: `param: Optional[str] = None`
  - Reason: MCP/Pydantic frameworks reject Optional[] wrappers

### Web Crawling

**Key modules:**
- `src/ingestion/web_crawler.py` - Crawl4AI-based crawler with link following
- `src/ingestion/website_analyzer.py` - Sitemap analysis and URL pattern discovery

**Crawl modes:**
- `mode="ingest"` - New crawl, errors if URL already exists
- `mode="reingest"` - Update existing, deletes old pages first

**Duplicate prevention:** `src/mcp/deduplication.py` prevents concurrent identical operations

### Database Migrations

**Alembic-based:** Migrations in `deploy/alembic/versions/`
```bash
# Run migrations
uv run rag migrate

# Create new migration
uv run alembic revision --autogenerate -m "description"
```

**Migration guide:** `docs/DATABASE_MIGRATION_GUIDE.md`

## Important Implementation Details

### Document Chunking
- Hierarchical splitting: headers → paragraphs → sentences
- ~1000 chars per chunk, 200 char overlap
- Module: `src/core/chunking.py`
- Each chunk independently embedded and stored with position metadata

### Vector Search
- OpenAI `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens)
- HNSW index for approximate nearest neighbor search
- Cosine similarity with normalized vectors
- Module: `src/retrieval/search.py`

### Knowledge Graph
- Graphiti extracts entities and relationships during ingestion
- Graph queries use LLM for entity matching (~500-800ms)
- Collection scoping isolates graphs by domain
- Module: `src/unified/graph_store.py`

### Environment Detection
Configuration loader detects context automatically:
1. Check `RAG_CONFIG_PATH` env var (test override)
2. Check `./config/` (repo-local, for development)
3. Fall back to platformdirs (system-level, for end users)

**First-run wizard:** `src/core/first_run.py` - Interactive setup if config missing

## Testing Patterns

### Test Organization
- `tests/unit/` - Fast, isolated unit tests
- `tests/integration/` - Database-dependent integration tests
  - `integration/backend/` - RAG + Graph ingestion tests
  - `integration/cli/` - CLI command tests
  - `integration/mcp/` - MCP tool tests
  - `integration/web/` - Web crawler tests

### Test Configuration
- Uses `RAG_CONFIG_PATH` and `RAG_CONFIG_FILE` env vars to isolate test config
- Shared fixtures in `tests/conftest.py`
- Per-module fixtures in test subdirectories

### Common Test Patterns
```python
# Use test-specific config
os.environ['RAG_CONFIG_FILE'] = 'config.test.yaml'

# Clean up test data
db.execute("DELETE FROM collections WHERE name LIKE 'test_%'")

# Async test (for MCP tools)
@pytest.mark.asyncio
async def test_mcp_tool():
    result = await tool_function(...)
```

## Common Development Tasks

### Adding a New MCP Tool
1. Add tool implementation to `src/mcp/tools.py` as `new_tool_impl()`
2. Add tool wrapper in `src/mcp/server.py` with `@mcp.tool()` decorator
3. **Remember:** No `Optional[T]` in parameter type hints
4. Add integration test in `tests/integration/mcp/test_new_tool.py`
5. Update MCP tool count in README.md

### Adding a New CLI Command
1. Create command function in appropriate `src/cli_commands/*.py` module
2. Use `@click.command()` or `@click.group()` decorator
3. Import and register in `src/cli.py`
4. Add integration test in `tests/integration/cli/`
5. Update CLI reference in `.reference/CLI_GUIDE.md`

### Modifying Database Schema
1. Create migration: `uv run alembic revision --autogenerate -m "description"`
2. Review generated migration in `deploy/alembic/versions/`
3. Test migration: `uv run rag migrate`
4. Update validation logic in `src/core/database.py` (validate_schema method)
5. Add test in `tests/unit/test_database_health.py`

### Working with Knowledge Graph
- Graph is **mandatory** (fail-fast if Neo4j unavailable)
- All ingestion goes through `UnifiedIngestionMediator`
- Graph extraction happens automatically after RAG ingestion
- Use `graph_store.validate_schema()` to check Neo4j health
- See `docs/IMPLEMENTATION_GAPS_AND_ROADMAP.md` for Gap 2.1 details

## Debugging Tips

### Enable Verbose Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Database State
```bash
# Connect to PostgreSQL
docker exec -it rag-memory-postgres psql -U postgres -d ragmemory

# Useful queries
\dt  # List tables
SELECT COUNT(*) FROM source_documents;
SELECT COUNT(*) FROM document_chunks;
```

### Check Neo4j State
```bash
# Open Neo4j browser
open http://localhost:7474

# Cypher query examples
MATCH (n) RETURN count(n);  // Count all nodes
MATCH (e:Entity) RETURN e LIMIT 10;  // List entities
```

### MCP Server Logs
- File logs: `logs/mcp_server.log`
- Suppressed by default: Neo4j notifications, httpx verbose logs
- Temporarily enable crawl4ai logs in `src/mcp/server.py:67`

### Common Issues
- **"Database not found"** → Check `.env` has `DATABASE_URL`
- **"Neo4j connection failed"** → Run `uv run rag start`
- **"Collection doesn't exist"** → Collections require explicit creation
- **MCP tool parameter errors** → Check for `Optional[T]` type hints (not allowed)

## Documentation Structure

- **`.reference/`** - End-user guides (installation, MCP, troubleshooting)
- **`docs/`** - Technical documentation (architecture, migrations, environment vars)
- **`README.md`** - Quick start and feature overview
- **`CLAUDE.md`** (this file) - Developer onboarding

## Slash Commands

Located in `.claude/commands/`:
- `/getting-started` - Interactive RAG Memory introduction
- `/cloud-setup` - Deploy to Supabase/Neo4j Aura/Fly.io
- `/reference-audit` - Audit .reference/ directory for accuracy

## Package Distribution

**PyPI package:** `rag-memory`
```bash
# Build package
uv run python -m build

# Upload to PyPI
uv run twine upload dist/*
```

**Entry points** (defined in `pyproject.toml`):
- `rag` - Main CLI tool
- `rag-mcp` - MCP server (accepts CLI args)
- `rag-mcp-stdio` - MCP server for Claude Desktop/Cursor
- `rag-mcp-sse` - MCP server for MCP Inspector
- `rag-mcp-http` - MCP server for web integrations
