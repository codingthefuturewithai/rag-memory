# MCP Server Guide

Complete guide to running and using the RAG Memory MCP server.

## Table of Contents

- [Overview](#overview)
- [Starting the Server](#starting-the-server)
- [Transport Modes](#transport-modes)
- [Testing with MCP Inspector](#testing-with-mcp-inspector)
- [Connecting to Claude Desktop](#connecting-to-claude-desktop)
- [Available Tools](#available-tools)
- [Troubleshooting](#troubleshooting)

## Overview

The RAG Memory MCP server exposes 11 tools for AI agents to manage a persistent knowledge base using PostgreSQL with pgvector. It implements the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), Anthropic's open standard for connecting AI agents to external systems.

**Key features:**
- Vector similarity search with OpenAI embeddings
- Document lifecycle management (CRUD operations)
- Web crawling with duplicate prevention
- Collection-based organization
- Automatic chunking for large documents

## Starting the Server

### Prerequisites

1. **Database running**: Ensure PostgreSQL with pgvector is running:
   ```bash
   docker-compose up -d
   docker-compose ps  # Verify it's running
   ```

2. **Environment configured**: Set OpenAI API key in `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-api-key-here
   ```

3. **Dependencies installed**:
   ```bash
   uv sync
   ```

### Default Mode (stdio)

For use with Claude Desktop or other MCP clients:

```bash
uv run rag-mcp-stdio
```

The server starts in stdio mode (standard input/output transport) and waits for JSON-RPC messages.

## Transport Modes

The MCP server supports three transport modes for different use cases:

### 1. stdio (Default) - For Production

**Use case**: Claude Desktop, MCP clients

```bash
uv run rag-mcp-stdio
```

**Characteristics:**
- Communication via standard input/output
- JSON-RPC protocol over stdio
- No network ports required
- Most common for desktop integrations

### 2. SSE (Server-Sent Events) - For Browser Clients

**Use case**: MCP Inspector (browser-based testing)

```bash
uv run rag-mcp-sse    # Runs on port 3001
```

**Characteristics:**
- HTTP server with Server-Sent Events
- Suitable for browser-based clients
- Runs on specified port (default: 3001)
- Good for development/testing

### 3. Streamable HTTP - For Web Applications

**Use case**: Web integrations, HTTP-based clients

```bash
uv run rag-mcp-http    # Runs on port 3001
```

**Characteristics:**
- Full HTTP server with bidirectional streaming
- RESTful endpoint at `/mcp`
- Authentication handled automatically by FastMCP
- Best for web application integrations

**Verify server is running:**
```bash
# Should show Uvicorn running on http://127.0.0.1:3001
curl http://localhost:3001/mcp
```

## Testing with MCP Inspector

MCP Inspector is an official tool for testing MCP servers without integrating with AI clients.

### Installation

No installation needed! Use npx to run it directly:

```bash
npx @modelcontextprotocol/inspector
```

### Method 1: Using `mcp dev` (Recommended)

The `mcp dev` command automatically starts the server and launches the inspector:

```bash
uv run mcp dev src/mcp/server.py
```

**What it does:**
1. Starts MCP Inspector proxy server
2. Generates authentication token
3. Opens browser with inspector UI
4. Starts your MCP server with stdio transport
5. Connects them together automatically

**Output:**
```
Starting MCP inspector...
⚙️ Proxy server listening on localhost:6277
🔑 Session token: abc123...
🚀 MCP Inspector is up and running at:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=abc123...
🌐 Opening browser...
```

**Inspector UI:**
- **Server Status**: Shows connection status (green = connected)
- **Tools Tab**: Lists all 11 available tools with descriptions
- **Test Tool**: Click any tool to see its parameters and test it
- **History**: View all tool calls and responses

### Method 2: Manual Connection (HTTP Transports)

For SSE or Streamable HTTP testing:

**Step 1**: Start your server
```bash
uv run python -m src.mcp.server --transport streamable-http --port 3001
```

**Step 2**: Start MCP Inspector
```bash
npx @modelcontextprotocol/inspector
```

**Step 3**: In the Inspector UI:
- Select "Streamable HTTP" from Transport Type dropdown
- Enter URL: `http://localhost:3001/mcp`
- Click "Connect"

**For SSE transport:**
- Select "SSE" from dropdown
- Enter URL: `http://localhost:3001/sse` (SSE endpoint)
- Click "Connect"

### Testing Tools

Once connected, you can test any tool:

**Example: Search for documents**
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "PostgreSQL database features",
    "limit": 5,
    "threshold": 0.7
  }
}
```

**Example: Analyze website**
```json
{
  "tool": "analyze_website",
  "arguments": {
    "base_url": "https://docs.python.org"
  }
}
```

**Example: List collections**
```json
{
  "tool": "list_collections",
  "arguments": {}
}
```

The inspector will show:
- **Request**: JSON sent to server
- **Response**: Full response with data/errors
- **Timing**: How long the tool call took

## Connecting to Claude Desktop

### Configuration File Location

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Linux**: `~/.config/Claude/claude_desktop_config.json`

### Configuration

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/timkitchens/projects/ai-projects/rag-memory",
        "run",
        "rag-mcp-stdio"
      ],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

**IMPORTANT**: Update the `--directory` path to match your installation location!

### Getting Your Path

```bash
cd /path/to/rag-memory
pwd  # Copy this output
```

### Verify Configuration

1. **Restart Claude Desktop** completely (quit and reopen)
2. Look for the 🔌 icon in Claude's input area
3. Click it to see "rag-memory" server listed
4. If you see the server with 11 tools, it's working!

### Troubleshooting Claude Desktop

**Server not showing up:**
- Check JSON syntax (no trailing commas!)
- Verify file path is correct
- Check logs: `~/Library/Logs/Claude/mcp*.log`

**Connection errors:**
- Ensure database is running: `docker-compose ps`
- Check API key is set correctly
- Try testing with MCP Inspector first

**Tools not working:**
- Check database connection: `uv run rag status`
- Verify OpenAI API key is valid
- Look at Claude's error messages (hover over failed tool calls)

## Available Tools

### Core RAG Operations

1. **`search_documents`** - Semantic search across knowledge base
   - Query with natural language
   - Filter by collection, threshold
   - Optional: include full source documents
   - Default: returns minimal response (4 fields)
   - With `include_metadata=true`: returns extended response (10+ fields)

2. **`list_collections`** - Discover available collections
   - Returns all collections with metadata
   - Shows document/chunk counts
   - Use before searching to find relevant collections

3. **`ingest_text`** - Add text content to knowledge base
   - Automatic chunking (~1000 chars)
   - Auto-embedding with OpenAI
   - Auto-create collections
   - Minimal response by default

### Document Management

4. **`list_documents`** - Browse available documents
   - Filter by collection
   - Pagination support
   - Minimal response by default (id, filename, chunk_count)
   - With `include_details=true`: full metadata

5. **`get_document_by_id`** - Retrieve full source document
   - Get complete document by ID
   - Optional: include chunk breakdown
   - Useful after search returns relevant chunks

6. **`update_document`** - Edit existing documents ⭐
   - Update content (auto re-chunks and re-embeds)
   - Update title or metadata
   - Essential for keeping knowledge current

7. **`delete_document`** - Remove outdated content ⭐
   - Permanent deletion
   - Cascades to all chunks
   - Essential for memory management

### Advanced Ingestion

8. **`get_collection_info`** - Collection statistics
   - Document/chunk counts
   - Sample documents
   - **Crawl history** (shows previously crawled URLs)

9. **`analyze_website`** - Sitemap analysis ⭐ NEW
   - Parse sitemap.xml to understand site structure
   - Groups URLs by pattern (/api/*, /docs/*, etc.)
   - Volume control (default: pattern stats only)
   - Use BEFORE crawling to plan comprehensive ingestion

10. **`ingest_url`** - Crawl and ingest web pages
    - Single page or multi-page (follow links)
    - Automatic chunking for web content
    - **Duplicate prevention** (mode="crawl" vs "recrawl")
    - Crawl metadata tracking

11. **`ingest_file`** - Ingest from file system
    - Text-based files only
    - Requires file system access
    - Automatic chunking

12. **`ingest_directory`** - Batch ingest from directory
    - Filter by extensions
    - Recursive option
    - Skip binary files automatically

### Tool Count: 11 Total

- 3 core RAG operations
- 4 document management
- 4 advanced ingestion

## Common Workflows

### Agent Memory Management

```
1. Agent wants to add knowledge:
   → ingest_text("New company policy: ...", collection="company-policies")

2. Agent wants to find information:
   → search_documents("What's our vacation policy?", collection="company-policies")

3. Agent wants to update outdated info:
   → list_documents(collection="company-policies")
   → update_document(document_id=42, content="Updated policy: ...")

4. Agent wants to remove wrong information:
   → delete_document(document_id=15)
```

### Website Documentation Ingestion

```
1. Analyze website structure:
   → analyze_website("https://docs.python.org")
   → Returns: /library (300 URLs), /tutorial (45 URLs), /reference (120 URLs)

2. Agent interprets patterns and decides what to crawl:
   → ingest_url("https://docs.python.org/3/tutorial/index.html",
                collection="python-docs", mode="crawl",
                follow_links=True, max_depth=2)

3. Check collection to verify:
   → get_collection_info("python-docs")
   → Shows crawled URLs and page counts

4. Later, update documentation:
   → ingest_url("https://docs.python.org/3/tutorial/index.html",
                collection="python-docs", mode="recrawl",
                follow_links=True, max_depth=2)
```

### Research Assistant

```
1. Discover knowledge bases:
   → list_collections()

2. Search across topics:
   → search_documents("machine learning best practices", limit=10)

3. Get full context:
   → get_document_by_id(source_document_id, include_chunks=true)
```

## Troubleshooting

### Server Won't Start

**Error: Database connection failed**
```bash
# Check database is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart database
docker-compose restart
```

**Error: OpenAI API key not found**
```bash
# Check .env file exists
cat .env | grep OPENAI_API_KEY

# Verify key is loaded
uv run python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

**Error: Module not found**
```bash
# Reinstall dependencies
uv sync

# Verify installation
uv run python -c "import mcp; print('MCP installed')"
```

### MCP Inspector Issues

**Error: Address already in use**
- Another MCP Inspector is running
- Kill existing processes: `pkill -f "mcp dev"`

**Error: Can't connect to server**
- Verify server is running and port is correct
- For streamable-http: check `curl http://localhost:PORT/mcp`
- Check firewall isn't blocking the port

**Inspector shows 0 tools**
- Server initialization failed
- Check server logs for errors
- Verify database connection works: `uv run rag status`

### Tool Call Errors

**Error: Collection not found**
```bash
# List existing collections
uv run rag collection list

# Create collection first
uv run rag collection create my-collection
```

**Error: Document not found**
```bash
# List documents to find valid IDs
uv run rag document list --collection my-collection
```

**Error: URL already crawled**
- This is INTENTIONAL duplicate prevention
- Use `mode="recrawl"` to update existing crawl
- Or check collection info to see what's already crawled

### Performance Issues

**Slow embedding generation**
- OpenAI API rate limits (500 requests/min)
- Use batch operations when possible
- Consider caching for development

**Slow search queries**
- Check HNSW index exists: `uv run rag status`
- Verify database has resources (not memory constrained)
- Reduce result limit if fetching too many

**High memory usage**
- Large documents create many chunks
- Consider breaking into smaller documents
- Monitor database memory: `docker stats`

## Advanced Configuration

### Custom Port

```bash
# Use different port for HTTP transports
uv run python -m src.mcp.server --transport sse --port 8080
```

### Environment Variables

All environment variables from `.env` are automatically loaded:

```bash
# .env file
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql://...  # Optional override
LOG_LEVEL=INFO  # Optional: DEBUG, INFO, WARNING, ERROR
```

### Multiple MCP Servers

You can run multiple instances with different configs:

```json
{
  "mcpServers": {
    "rag-memory-prod": {
      "command": "uv",
      "args": ["--directory", "/path/to/prod", "run", "python", "-m", "src.mcp.server"]
    },
    "rag-memory-dev": {
      "command": "uv",
      "args": ["--directory", "/path/to/dev", "run", "python", "-m", "src.mcp.server"]
    }
  }
}
```

## Best Practices

### For AI Agents

1. **Check collection info before crawling** - Avoid duplicate crawls
2. **Use analyze_website first** - Understand site structure before crawling
3. **Prefer update over delete+ingest** - Preserves collection membership
4. **Use minimal responses by default** - Save context window tokens
5. **Clean up outdated documents** - Keep knowledge base current

### For Development

1. **Test with MCP Inspector first** - Verify tools work before integrating
2. **Use `mcp dev` for quick iteration** - Automatic reload on code changes
3. **Check server logs** - All tool calls are logged with INFO level
4. **Monitor database size** - Run `uv run rag status` regularly

### For Production

1. **Use stdio transport** - Most reliable for desktop clients
2. **Set proper API rate limits** - Avoid OpenAI throttling
3. **Monitor database backups** - Vector data is valuable
4. **Implement collection strategy** - Organize by topic/domain

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Claude Desktop MCP Guide](https://docs.anthropic.com/claude/docs/model-context-protocol)

## Support

**Issues?**
1. Check this guide's Troubleshooting section
2. Verify database: `uv run rag status`
3. Test with MCP Inspector first
4. Check server logs for detailed errors
5. Review `CLAUDE.md` for development guidance
