---
description: Get started with RAG Memory - local setup with Docker, CLI tool, and MCP server
allowed-tools: ["Read", "Bash"]
---

# Welcome to RAG Memory!

This guide will walk you through setting up RAG Memory locally. You'll have a Docker-based knowledge store with both a command-line tool and an MCP server that works with Claude Code, Claude Desktop, and other AI agents.

**Estimated time:** 30-40 minutes

---

## PHASE 1: EDUCATION - Understand What RAG Memory Is

### Step 1: What is RAG Memory?

RAG Memory is a knowledge management system that stores documents (text, PDFs, web pages, code) and lets you search them semantically with AI. It uses PostgreSQL with vector search and Neo4j for relationship mapping.

**Two ways to use it:**
1. **MCP Server** - Connect from Claude Code, Claude Desktop, Cursor (the AI agent way)
2. **CLI Tool** - Use `rag` commands directly from your terminal (the power-user way)

You can use both at the same time - they talk to the same local databases.

**Ready to learn more, or do you have questions?**

---

### Step 2: How Does It Work Locally?

When you set up RAG Memory locally, you get:
- **PostgreSQL + pgvector** (database for document storage and semantic search)
- **Neo4j** (graph database for entity relationships)
- **MCP Server** (connects your AI agents to the databases)
- **Automated backups** (daily encrypted backups of your data)

All running in Docker containers, so nothing else on your machine needs to be installed.

**Does this make sense? Ready to proceed to setup?**

---

### Step 3: Cost

**Cost is ZERO for local usage.** You run everything on your machine.

If you later want to move to cloud (Supabase + Neo4j Aura + Fly.io), you'll have optional costs (~$3-15/month for small usage).

**Ready to set up locally?**

---

## PHASE 2: LOCAL SETUP - Get It Running

### Step 4: Clone the Repository

```bash
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
```

Replace `yourusername` with your GitHub username if you're using a fork, or use the official repository.

This gives you the Docker Compose files and everything else you need.

**Done with clone? Continue to next step.**

---

### Step 5: Run the Setup Script

RAG Memory provides a single setup script that handles everything:

```bash
python scripts/setup.py
```

This script will:
1. Check if Docker is installed and running
2. Start PostgreSQL and Neo4j containers
3. Create your local configuration file
4. Ask for your OpenAI API key
5. Initialize the databases
6. Install the CLI tool globally
7. Verify everything works

**Follow the prompts. If you don't have Docker running, the script will guide you through that first.**

**Completed setup.py? Continue to next step.**

---

### Step 6: Verify Everything Works

Let's verify the setup completed successfully:

```bash
rag status
```

Should show:
- PostgreSQL connection: ✅ OK
- Neo4j connection: ✅ OK
- Collections: 0 (empty for now, that's normal)
- Documents: 0

**See success for both databases? Good! Continue to next step.**

---

## PHASE 4: CONNECT YOUR MCP SERVER - Use from Claude Code/Desktop

### Step 7: Connect RAG Memory to Claude Code

RAG Memory includes an MCP server that's already running in Docker. Now connect it to Claude Code:

```bash
claude mcp add rag-memory --type sse --url http://localhost:8000/sse
```

This registers RAG Memory as an available MCP server in Claude Code.

**Note:** You may need to restart Claude Code for it to recognize the new server.

**Done? Continue to next step.**

---

### Step 8: Connect RAG Memory to Claude Desktop (Optional)

If you also use Claude Desktop, add it there too:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Add this JSON:**
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

**Note:** Claude Desktop runs RAG Memory as a subprocess (stdio transport), while Claude Code connects via HTTP (SSE transport). Both access the same local databases.

**Done? Continue to testing.**

---

## PHASE 5: TEST IT OUT

### Step 13: Test the CLI Tool

In your terminal:

```bash
rag search "artificial intelligence"
```

You'll get:
```
No results found (empty database)
```

This is normal - you haven't ingested any documents yet. The important thing is that the command ran without errors.

**Worked? Continue to test MCP.**

---

### Step 14: Test the MCP Server in Claude Code

In Claude Code, ask your AI agent:

```
"List my RAG Memory collections"
```

Or:

```
"Show me RAG Memory status"
```

If it works, you'll get a response about your empty knowledge base.

**Works? Congrats! Local setup is complete.**

---

## NEXT STEPS - Start Using RAG Memory

Now that you have RAG Memory running, you can:

### Add Documents
```bash
rag ingest text "Your text here"
rag ingest file path/to/document.txt
rag ingest url https://example.com/article
```

### Search
```bash
rag search "what is machine learning"
```

### Use from AI Agents
Ask Claude Code or Claude Desktop:
- "Create a RAG Memory collection called 'my-notes'"
- "Add this document to my collection"
- "Search my knowledge base for..."

### Manage Collections
```bash
rag collection list
rag collection create my-new-collection
rag collection delete my-old-collection
```

---

## TROUBLESHOOTING

### "Connection refused" error
The Docker containers might not be running:
```bash
docker-compose -f docker-compose.dev.yml ps
```

If any are stopped, restart them:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### "rag: command not found"
The CLI tool wasn't installed globally:
```bash
uv tool install .
```

Then verify:
```bash
which rag
```

### "Configuration not found"
First-run wizard didn't complete. Run:
```bash
rag status
```

And follow the prompts to create `~/.rag-memory-env`.

### MCP server not appearing in Claude Code
Try restarting Claude Code completely (quit and reopen).

If it still doesn't work:
```bash
docker-compose -f docker-compose.dev.yml logs
```

Look for errors in the output.

---

## WHAT HAPPENS NEXT?

Now that RAG Memory is running locally, check out the documentation:

**For detailed CLI commands:**
- Run: `rag --help`
- Or see `.reference/OVERVIEW.md` for complete reference

**For MCP tool reference:**
- See `.reference/MCP_QUICK_START.md`
- Lists all 17 tools available for AI agents

**For cloud deployment (when ready):**
- See `.reference/CLOUD_DEPLOYMENT.md`
- Covers Supabase PostgreSQL, Neo4j Aura, Fly.io MCP server
- Data migration guide (move your local documents to cloud)

**For architecture details:**
- See `CLAUDE.md` for development reference
- Explains PostgreSQL + Neo4j dual storage, vector normalization, etc.

---

**You're all set! Start ingesting documents and exploring your knowledge base with AI agents.**
