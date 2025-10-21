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
git clone https://github.com/YOUR-USERNAME/rag-memory.git
cd rag-memory
```

This gives you the Docker Compose files and everything else you need.

**Done with clone? Continue to next step.**

---

### Step 5: Start the Docker Containers

The Docker Compose setup includes:
- PostgreSQL database
- Neo4j graph database
- MCP server (runs on port 8000)
- Automated daily backups (saved to ./backups/)

Let me start these for you:

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This will take 30-60 seconds. It downloads container images, initializes databases, and starts everything.

**Wait for it to complete, then continue.**

---

### Step 6: Verify Containers Are Running

Let me check that everything started correctly:

```bash
docker-compose -f docker-compose.dev.yml ps
```

You should see three containers:
- `rag-memory-postgres-dev` (UP, healthy)
- `rag-memory-neo4j-dev` (UP, healthy)
- (MCP server runs inside rag-memory-postgres-dev)

**See all three healthy? Good! Continue to next step.**

---

### Step 7: Install the CLI Tool Globally

The `rag` command needs to be installed on your system so you can use it from anywhere:

```bash
uv tool install .
```

This installs the `rag` command globally to `~/.local/bin/` (same place system tools live).

**Done? Continue to next step.**

---

### Step 8: Verify CLI Installation

```bash
which rag
```

Should print: `/Users/YOUR-USERNAME/.local/bin/rag`

**See that path? Good! Continue to next step.**

---

## PHASE 3: FIRST-RUN CONFIGURATION - Set Up Your API Key

### Step 9: Create Configuration File

The first time you run the `rag` command, it will ask for configuration. Let's do that now:

```bash
rag status
```

You'll be prompted for:
1. **PostgreSQL Database URL** (default: `postgresql://raguser:ragpassword@localhost:54320/rag_memory_dev`)
   - Press Enter to accept default (you're using local Docker)

2. **Neo4j Connection URI** (default: `bolt://localhost:7687`)
   - Press Enter to accept default (Neo4j is running locally)

3. **Neo4j Username** (default: `neo4j`)
   - Press Enter to accept default

4. **Neo4j Password** (default: `graphiti-password`)
   - Press Enter to accept default

5. **OpenAI API Key** (no default - YOU MUST PROVIDE THIS)
   - Get your key: https://platform.openai.com/api-keys
   - Paste it here (it won't be displayed)

**Important:** The configuration is saved to `~/.rag-memory-env` with user-only permissions (chmod 600).

This is a one-time setup. Future runs will read from this file automatically.

**Completed the first-run wizard? Continue to next step.**

---

### Step 10: Verify Configuration

Let's verify everything works:

```bash
rag status
```

Should show:
- Database connection: OK
- Collections: 0 (empty for now, that's normal)
- Documents: 0

**See success? Continue to next step.**

---

## PHASE 4: CONNECT YOUR MCP SERVER - Use from Claude Code/Desktop

### Step 11: Add MCP Server to Claude Code

The MCP server is already running in Docker on port 8000. Now add it to Claude Code:

```bash
claude mcp add-json --scope user rag-memory '{"type":"sse","url":"http://localhost:8000/sse"}'
```

This registers RAG Memory as an MCP server. The `--scope user` flag makes it available globally (from any project).

**Note:** After running this, you may need to restart Claude Code for it to recognize the new server.

**Done? Continue to next step.**

---

### Step 12: Add MCP Server to Claude Desktop (Optional)

If you also use Claude Desktop, add it there too:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Add this JSON:**
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "args": [],
      "env": {
        "OPENAI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

Then restart Claude Desktop.

**Note:** Claude Desktop uses stdio transport (different from Claude Code's SSE), but both work with the same local databases.

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

For cloud deployment (later, when you're ready):
- See `.reference/CLOUD_DEPLOYMENT.md`
- Covers Supabase PostgreSQL, Neo4j Aura, Fly.io MCP server
- Data migration guide (move your local documents to cloud)

For detailed CLI command reference:
- See `.reference/OVERVIEW.md`

For MCP tool reference:
- See `.reference/MCP_QUICK_START.md`

---

**You're all set! Start ingesting documents and exploring your knowledge base.**
