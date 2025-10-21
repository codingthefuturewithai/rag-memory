# MCP Server - Quick Start

## Prerequisites

Before configuring the MCP server, ensure:

1. **RAG Memory installed globally:**
   ```bash
   # Install from PyPI (recommended)
   uv tool install rag-memory

   # Or install from cloned repo (for development)
   # cd /path/to/rag-memory && uv tool install -e .
   ```

2. **Database is running:**
   ```bash
   # Clone repo to get docker-compose.yml
   git clone https://github.com/YOUR-USERNAME/rag-memory.git
   cd rag-memory

   # Start database
   docker-compose up -d
   docker-compose ps  # Verify running
   ```

3. **Environment variables configured:**

   **For MCP server usage:** Environment variables are set in your MCP client config (see configuration sections below). You'll need:
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `DATABASE_URL` - Database connection (default: `postgresql://raguser:ragpass@localhost:54320/rag_poc`)

   **For CLI usage:** RAG Memory uses a **first-run setup wizard** that creates `~/.rag-memory-env` automatically:
   - Run any CLI command (e.g., `rag status`)
   - Setup wizard will prompt for DATABASE_URL and OPENAI_API_KEY
   - Configuration is saved to `~/.rag-memory-env` with secure permissions
   - No manual file creation needed!

   **Three-tier priority system:**
   1. Environment variables (highest priority)
   2. Project `.env` file (current directory only - for developers)
   3. Global `~/.rag-memory-env` file (lowest priority - for end users)

   See [docs/ENVIRONMENT_VARIABLES.md](../docs/ENVIRONMENT_VARIABLES.md) for complete details.

   **IMPORTANT:**
   - Never expose API keys to AI assistants
   - The DATABASE_URL shown is for the default Docker setup (port 54320)
   - MCP server gets config from MCP client, NOT from `~/.rag-memory-env`

## Start the MCP Server

**Three convenience commands available:**

```bash
uv run rag-mcp-stdio    # For Claude Desktop/Cursor/Claude Code (stdio transport)
uv run rag-mcp-sse      # For MCP Inspector (SSE transport, port 3001)
uv run rag-mcp-http     # For web integrations (HTTP transport, port 3001)
```

**Or use the general command:**
```bash
uv run python -m src.mcp.server --transport stdio
uv run python -m src.mcp.server --transport sse --port 3001
uv run python -m src.mcp.server --transport streamable-http --port 3001
```

## Configure Your AI Agent

### Claude Desktop

**Config file location:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Add this configuration:**

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

**CRITICAL:**
1. Replace `sk-your-api-key-here` with your actual OpenAI API key
2. The DATABASE_URL is pre-configured for the default Docker setup (port 54320)
3. If you changed Docker settings, update the DATABASE_URL accordingly
4. Ensure JSON syntax is correct (no trailing commas!)
5. This assumes you installed globally with `uv tool install rag-memory`

**Note:** The `rag-mcp-stdio` command is available globally after installation. No need to specify paths to the cloned repository.

### Claude Code

Claude Code has its own CLI command for adding MCP servers. **CRITICAL: Use `--scope user` flag to make the server available globally.**

**Run this command in your terminal:**

```bash
claude mcp add-json --scope user rag-memory '{"type":"stdio","command":"rag-mcp-stdio","args":[],"env":{"OPENAI_API_KEY":"sk-your-api-key-here","DATABASE_URL":"postgresql://raguser:ragpass@localhost:54320/rag_poc"}}'
```

**Why `--scope user` is REQUIRED:**
- ❌ Without `--scope user`: Server only works in current directory (local scope)
- ✅ With `--scope user`: Server available globally across all projects
- This ensures the MCP server works everywhere, not tied to any specific repo

**Steps:**
1. Replace `sk-your-api-key-here` with your actual OpenAI API key
2. Run the command in your terminal
3. Restart Claude Code (quit and reopen)
4. Test by asking: "List available RAG collections"

### Cursor

Cursor may support MCP through its settings. Check Cursor's documentation for MCP server configuration. The server command is the same:

```bash
uv --directory /FULL/PATH/TO/rag-memory run rag-mcp-stdio
```

### Custom MCP Client

If your client supports stdio transport:

```json
{
  "command": "rag-mcp-stdio",
  "args": [],
  "env": {
    "OPENAI_API_KEY": "sk-your-api-key-here",
    "DATABASE_URL": "postgresql://raguser:ragpass@localhost:54320/rag_poc"
  }
}
```

## Test the Connection

### Method 1: Using Your AI Agent

1. **Restart your AI agent** (quit completely and reopen)
2. Look for the MCP server indicator (🔌 icon in Claude Desktop)
3. Ask your agent: "List available RAG collections"
4. You should see it call the `list_collections` tool
5. Success! Your agent can now use all 14 RAG tools

### Method 2: Using MCP Inspector (Recommended for Testing)

**MCP Inspector** is an official tool for testing MCP servers without an AI client.

**Quick test:**
```bash
uv run mcp dev src/mcp/server.py
```

This will:
1. Start the MCP Inspector in your browser
2. Start your RAG Memory server
3. Connect them automatically
4. Show all 14 available tools

**In the Inspector UI:**
- **Tools Tab**: See all 14 tools with descriptions
- Click any tool to test it
- View tool call history and responses

### Method 3: Using CLI (Direct Verification)

Test the server components directly (requires .env file in cloned repo):

```bash
# Check database connection
rag status

# List collections
rag collection list

# Create test collection
rag collection create test-collection --description "Test collection"

# Ingest test document
rag ingest text "PostgreSQL with pgvector enables semantic search for AI agents" --collection test-collection

# Search
rag search "semantic search" --collection test-collection
```

**Note:** CLI commands look for `.env` file in the current directory or the cloned repo directory. Make sure you've configured the `.env` file as described in Prerequisites.

## Troubleshooting

### Server Not Showing in AI Agent

**Check config file syntax:**
- No trailing commas in JSON
- All quotes are double quotes (`"` not `'`)
- Path uses forward slashes on all platforms

**Verify file path:**
```bash
cd /path/to/rag-memory
pwd  # Copy this exact path into config
```

**Check logs:**
- **macOS**: `~/Library/Logs/Claude/mcp*.log`
- **Windows**: `%APPDATA%\Claude\Logs\mcp*.log`
- Look for error messages about the rag-memory server

### Database Connection Errors

```bash
# Verify database is running
docker-compose ps

# Check database logs
docker-compose logs postgres

# Restart database if needed
docker-compose restart

# Test connection
rag status
```

**If you get "DATABASE_URL not found" error:**
- For MCP server: Check that your MCP config includes DATABASE_URL in env vars
- For CLI: Make sure .env file exists in cloned repo with DATABASE_URL setting
- Default DATABASE_URL: `postgresql://raguser:ragpass@localhost:54320/rag_poc`

### OpenAI API Key Errors

**Check .env file exists:**
```bash
ls -la .env  # Should exist
cat .env | grep OPENAI_API_KEY  # Should show OPENAI_API_KEY=sk-...
```

**Do NOT run this command** (exposes key):
```bash
echo $OPENAI_API_KEY  # ❌ NEVER DO THIS with AI assistants
```

**Instead, tell the user:**
"Check your `.env` file contains `OPENAI_API_KEY=sk-your-key-here`"

### Tools Not Working

**Verify database connection:**
```bash
rag status
```

**Check you have collections:**
```bash
rag collection list
```

**Test search with existing data:**
```bash
# Create test data if needed
rag collection create test-collection --description "Test collection"
rag ingest text "Test document" --collection test-collection
rag search "test" --collection test-collection
```

## Available Tools (17 Total)

### 1. Search & Discovery (4 tools)

**search_documents** - Semantic vector similarity search
- Parameters: query, collection_name (optional), limit, threshold (optional), include_source (bool)
- Returns: List of chunks with similarity scores (0.0-1.0)
- Example: "Find docs about PostgreSQL performance"
- Similarity Interpretation: 0.7+ = high confidence, 0.5-0.7 = related, 0.3-0.5 = marginal

**list_collections** - Discover all knowledge bases
- Parameters: None
- Returns: List of collections with document counts and descriptions
- Example: "What knowledge bases do I have?"

**get_collection_info** - Detailed collection statistics
- Parameters: collection_name
- Returns: Document count, chunk count, creation date, crawl metadata
- Example: "Show me stats for my AI documentation"

**analyze_website** - Parse sitemap and understand site structure
- Parameters: url, timeout (optional), include_url_lists (bool), max_urls_per_pattern (int)
- Returns: URL patterns, statistics, sample URLs
- Example: "How many pages on docs.python.org?" (helps plan crawls)

### 2. Document Management - Read Operations (3 tools)

**list_documents** - Browse documents with pagination
- Parameters: collection_name (optional), limit, offset
- Returns: Document IDs, filenames, titles, metadata, created dates
- Example: "Show me the documents in my collection"
- Use Case: Inventory management, finding duplicate documents

**get_document_by_id** - Retrieve full source document
- Parameters: document_id, include_chunks (bool)
- Returns: Full document content, metadata, chunk details (if requested)
- Example: "Show me the full content of document 42"
- Use Case: Reviewing full source after chunk search finds it

**ingest_text** - Add text content with auto-chunking
- Parameters: content (string), collection_name, metadata (JSON)
- Returns: source_document_id, num_chunks, entities_extracted
- Example: "Store this PostgreSQL guide in my tech docs"
- Auto-chunks: 1000 chars per chunk, 200 char overlap
- Auto-embeds to both RAG (pgvector) and Graph (Graphiti) if available

### 3. Document Management - Write Operations (2 tools)

**update_document** - Edit document content/metadata (re-embeds)
- Parameters: document_id, content (optional), title (optional), metadata (JSON)
- Returns: Updated document_id, new chunk count
- Example: "Update document 42 with corrected content"
- ⚠️ WARNING: Graph not updated until Phase 4 - Graph will have stale data
- Use Case: Fixing errors, adding new information

**delete_document** - Remove documents
- Parameters: document_id
- Returns: Confirmation, deleted document_id
- Example: "Remove the outdated guide (doc 15)"
- ⚠️ WARNING: Graph not cleaned until Phase 4 - Orphaned episodes accumulate
- Use Case: Removing incorrect or duplicate documents

### 4. Collection Management (3 tools)

**create_collection** - Create new named collection
- Parameters: name, description (required)
- Returns: collection_id, name, created status
- Example: "Create a collection called 'Python Docs' for Python documentation"
- Description is MANDATORY (not optional)
- Use Case: Organizing knowledge by topic/domain

**update_collection_description** - Update collection metadata
- Parameters: collection_name, description
- Returns: collection_name, new description, updated status
- Example: "Update the AI docs description to add version info"
- Use Case: Keeping metadata current as collection evolves

**delete_collection** - ⚠️ DANGEROUS - Delete collection and all documents
- Parameters: name, confirm (REQUIRED: must be True)
- Returns: name, deleted status, message with document count
- Example: "Delete 'old-docs' (with confirm=True)"
- ⚠️ WARNING: This permanently deletes the collection and ALL its documents
- ⚠️ WARNING: Confirmation required (confirm=True) to prevent accidents
- ⚠️ WARNING: Graph episodes NOT cleaned until Phase 4 - cleanup planned
- Use Case: Removing obsolete collections and associated knowledge

### 5. Advanced Ingestion - Web Crawling (3 tools)

**ingest_url** - Crawl single web page or follow links
- Parameters: url, collection_name, follow_links (bool), max_depth (int), chunk_size (optional), chunk_overlap (optional)
- Returns: source_document_id, num_chunks, pages_crawled
- Examples:
  - Single page: "Ingest https://docs.example.com/intro"
  - Multi-page: "Crawl https://docs.example.com with link following, depth 2"
- Metadata: Tracks crawl_root_url, crawl_session_id, crawl_depth
- Use Case: Building knowledge bases from documentation sites

**ingest_file** - Add document from filesystem
- Parameters: file_path, collection_name, metadata (JSON, optional)
- Returns: source_document_id, num_chunks
- Supports: .txt, .md, .json, .pdf (and others)
- Auto-chunks by default (configurable)
- Example: "Add /docs/guide.md to my collection"
- Use Case: Ingesting local files, corporate documents

**ingest_directory** - Batch ingest entire directory
- Parameters: directory_path, collection_name, extensions (list), recursive (bool)
- Returns: List of (source_id, num_chunks) tuples
- Example: "Ingest all .md and .txt files from /my-docs recursively"
- Extensions filter: only matching files ingested
- Recursive: whether to descend into subdirectories
- Use Case: Bulk document import, building from existing libraries

### 6. Specialized Operations (2 tools)

**recrawl_url** - Update web documentation (delete old, re-crawl new)
- Parameters: url, collection_name, follow_links (bool), max_depth (int)
- Returns: documents_deleted, documents_created, updated_at
- Example: "Re-crawl https://docs.example.com with link following to update to latest version"
- Strategy: Finds docs by crawl_root_url, deletes them, re-crawls fresh
- ⚠️ WARNING: Graph not cleaned until Phase 4 - Orphaned episodes accumulate
- Use Case: Keeping documentation current after updates

### 7. Knowledge Graph Queries (2 tools - Optional, Experimental)

**query_relationships** - Search for entity relationships using natural language
- Parameters: query, num_results (optional, default 5)
- Returns: List of relationships with descriptions, types, timestamps
- Example: "Which projects depend on the authentication service?"
- Status: "available" (Neo4j running) or "unavailable" (fell back to RAG)
- Use Case: Understanding how entities connect, multi-hop reasoning
- ⚠️ EXPERIMENTAL: Phase 3 complete, Phase 4 in progress

**query_temporal** - Track how knowledge evolved over time
- Parameters: query, num_results (optional, default 10)
- Returns: Timeline with entities, facts, valid_from/until timestamps
- Example: "How has the API design changed?"
- Status: "available" or "unavailable"
- Use Case: Understanding system evolution, compliance tracking
- ⚠️ EXPERIMENTAL: Phase 3 complete, Phase 4 in progress

## Complete Documentation

For detailed tool reference, workflows, and advanced configuration:

**[docs/MCP_SERVER_GUIDE.md](../docs/MCP_SERVER_GUIDE.md)** - Complete MCP server documentation

Other resources:
- [README.md](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - CLI commands and development
- [OVERVIEW.md](OVERVIEW.md) - What is RAG Memory
