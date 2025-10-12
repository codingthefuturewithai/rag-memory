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

Claude Code uses the same MCP configuration as Claude Desktop. Follow the Claude Desktop instructions above.

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
5. Success! Your agent can now use all 11 RAG tools

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
4. Show all 11 available tools

**In the Inspector UI:**
- **Tools Tab**: See all 11 tools with descriptions
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
rag collection create test-collection

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
rag collection create test-collection
rag ingest text "Test document" --collection test-collection
rag search "test" --collection test-collection
```

## Available Tools (11 Total)

### Core RAG (3 tools)
1. **search_documents** - Semantic search with vector similarity
2. **list_collections** - Discover available knowledge bases
3. **ingest_text** - Add text content with auto-chunking

### Document Management (4 tools)
4. **list_documents** - Browse documents with pagination
5. **get_document_by_id** - Retrieve full source document
6. **update_document** ⭐ - Edit existing documents
7. **delete_document** ⭐ - Remove outdated content

### Advanced Ingestion (4 tools)
8. **get_collection_info** - Collection stats + crawl history
9. **analyze_website** ⭐ NEW - Sitemap analysis for planning crawls
10. **ingest_url** - Crawl web pages with duplicate prevention
11. **ingest_file** - Ingest text files from filesystem

## Complete Documentation

For detailed tool reference, workflows, and advanced configuration:

**[docs/MCP_SERVER_GUIDE.md](../docs/MCP_SERVER_GUIDE.md)** - Complete MCP server documentation

Other resources:
- [README.md](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - CLI commands and development
- [OVERVIEW.md](OVERVIEW.md) - What is RAG Memory
