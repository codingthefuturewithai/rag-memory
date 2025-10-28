---
description: Get started with RAG Memory - local setup with Docker, CLI tool, and MCP server
allowed-tools: ["Read", "Bash"]
---

# Welcome to RAG Memory!

You're about to set up a local knowledge management system with PostgreSQL, Neo4j, and an MCP server. You'll be able to use it via command-line tools or AI agents like Claude Code and Claude Desktop.

**Estimated time:** 30-40 minutes (most of it is just waiting for Docker containers to start)

---

## What You're About to Set Up

- **PostgreSQL + pgvector** - For semantic search (finds documents by meaning, not keywords)
- **Neo4j** - For relationship mapping (what entities are connected to what)
- **MCP Server** - So Claude Code, Claude Desktop, and other AI agents can access your knowledge base
- **CLI Tool** - The `rag` command for terminal access

**Cost:** Zero for local usage (you run everything on your machine)

---

## PHASE 1: RUN THE SETUP SCRIPT

You already have the repository cloned. Now let's run the automated setup:

```bash
python scripts/setup.py
```

This script will:
1. ✅ Check if Docker is installed and running
2. ✅ Start PostgreSQL and Neo4j containers
3. ✅ Create your local configuration
4. ✅ Ask for your OpenAI API key (for embeddings)
5. ✅ Initialize the databases
6. ✅ Install the CLI tool globally
7. ✅ Verify everything works

**Follow the interactive prompts. If you don't have Docker running, the script will tell you to start it.**

---

**When setup.py completes, it will show you what you now have and suggest first commands to try.**

---

## PHASE 2: VERIFY THE MCP SERVER IS RUNNING

After setup.py completes, the MCP server is automatically running in Docker on **localhost:8000**. Let's verify it:

```bash
curl http://localhost:8000/sse
```

You should get a response (might be streaming data). If you get an error or no response, the MCP server didn't start. Check the troubleshooting section below.

---

## PHASE 3: TRY YOUR FIRST COMMANDS

Once setup completes and you've verified the MCP server, try these commands in your terminal to get a feel for how RAG Memory works:

### Create Your First Collection
```bash
rag collection create my-first-notes --description "My first RAG Memory collection"
```

This creates a named collection where you can organize your documents by topic.

### Add a Document
```bash
rag ingest text "RAG Memory combines PostgreSQL with pgvector for semantic search and Neo4j for knowledge graphs. You can store any text content and search by meaning." --collection my-first-notes
```

This adds a document to your collection and makes it searchable.

### Search Your Knowledge Base
```bash
rag search "semantic search" --collection my-first-notes
```

This searches your collection by meaning. You should see the document you just added with a similarity score.

### List What You Have
```bash
rag collection list
```

Shows all your collections.

---

## PHASE 4: CONNECT TO CLAUDE CODE OR CLAUDE DESKTOP

Now that the MCP server is running, you can connect it to AI agents:

### Option A: Claude Code

In your terminal:
```bash
claude mcp add rag-memory --type sse --url http://localhost:8000/sse
```

Restart Claude Code, then ask:
```
"List my RAG Memory collections"
```

Or:
```
"Search my knowledge base for semantic search"
```

### Option B: Claude Desktop (Optional)

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add this configuration:
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

Save the file, then restart Claude Desktop completely.

**Note:** Both Claude Code and Claude Desktop connect to the same local databases. You can use either or both.

---

## WHAT YOU NOW HAVE

Congratulations! Your RAG Memory setup is complete. Here's what's running:

✅ **PostgreSQL Database** - Stores documents and embeddings for semantic search
✅ **Neo4j Graph Database** - Tracks relationships between entities
✅ **MCP Server** - Running on localhost:8000, ready for AI agents
✅ **CLI Tool** - The `rag` command is available in your terminal from anywhere

---

## NEXT STEPS

### For Terminal Users (Power Users)

Use the `rag` command to ingest, search, and manage:
- See all commands: `rag --help`
- Complete reference: `.reference/OVERVIEW.md`

### For Claude Code / Claude Desktop Users

The MCP server gives your AI agent 17 tools:
- Create collections
- Search documents
- Ingest from web pages, files, directories
- Manage documents
- View entity relationships (knowledge graph)

See all tools: `.reference/MCP_QUICK_START.md`

### Common Next Steps

**I want to add more documents:**
```bash
rag ingest file /path/to/document.txt --collection my-first-notes
rag ingest url https://example.com/article --collection my-first-notes
rag ingest directory ~/my-documents --collection my-first-notes
```

**I want to search better:**
See `.reference/SEARCH_OPTIMIZATION.md` for tuning tips.

**I want to deploy to the cloud:**
When ready, run `/cloud-setup` for step-by-step guidance on Supabase, Neo4j Aura, and Fly.io.

---

## TROUBLESHOOTING

### "Connection refused" / "Can't connect to database"
Containers might not be running:
```bash
docker-compose -f deploy/docker/compose/docker-compose.dev.yml ps
```

If any show "Exited", restart:
```bash
docker-compose -f deploy/docker/compose/docker-compose.dev.yml up -d
```

### "rag: command not found"
CLI tool wasn't installed. From the repo directory:
```bash
uv tool install .
```

### "MCP server not responding"
Check if it's running:
```bash
docker-compose -f deploy/docker/compose/docker-compose.dev.yml logs mcp-server
```

Look for error messages.

### "Configuration not found"
The setup wizard didn't complete. Run:
```bash
rag status
```

And follow the prompts.

### "MCP server not appearing in Claude Code"
Try restarting Claude Code completely (quit and reopen). If it still doesn't show:
```bash
claude mcp list
```

Should show `rag-memory` with URL `http://localhost:8000/sse`.

---

## Documentation

- **CLI Commands:** `.reference/OVERVIEW.md`
- **MCP Tools (17 total):** `.reference/MCP_QUICK_START.md`
- **Search Optimization:** `.reference/SEARCH_OPTIMIZATION.md`
- **Knowledge Graphs:** `.reference/KNOWLEDGE_GRAPH.md`
- **Cloud Deployment:** `/cloud-setup` command or `.reference/CLOUD_DEPLOYMENT.md`

---

**You're all set! Start building your knowledge base. 🚀**
