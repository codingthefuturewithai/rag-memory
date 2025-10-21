# Cloud Deployment Guide

**For users who want to move RAG Memory from local to cloud.**

This guide assumes you have RAG Memory working locally. We'll help you set up the cloud versions of PostgreSQL, Neo4j, and the MCP server.

---

## Prerequisites

Before starting, you need:
- A working local RAG Memory setup (local Docker Compose)
- An OpenAI API key (already have one? Good)
- A Supabase account (or will create during setup)
- A Neo4j Aura account (or will create during setup)
- A Fly.io account (or will create during setup)

**Time required:** ~30 minutes of your time + ~15 minutes of waiting for services to start

---

## Overview: What You're Building

Your cloud setup will have:

```
Supabase (Cloud PostgreSQL + pgvector)
    ↓
RAG Memory Search & Storage

Neo4j Aura (Cloud Graph Database)
    ↓
Knowledge Graph & Relationships

Fly.io (MCP Server)
    ↓
Your AI agents access both databases
```

Each vendor is separate, but they work together seamlessly once connected.

---

## Step 1: Create Supabase Project (PostgreSQL + pgvector)

### What This Does
Supabase hosts PostgreSQL with pgvector extension pre-installed. This replaces your local Docker PostgreSQL.

### How to Do It

**1. Go to https://supabase.com**
- Sign up or log in
- Click "New Project"
- Choose:
  - Name: `rag-memory` (or whatever you want)
  - Region: Choose one close to you (us-east-1, eu-west-1, etc.)
  - Password: Generate a strong one (save it somewhere safe)

**2. Wait for project to start** (~2 minutes)

**3. Get your connection details:**
- Go to Project Settings → Database
- Find "Connection String" section
- Copy the `postgresql://` URL
- Replace `[YOUR-PASSWORD]` with the password you set

Example format: `postgresql://postgres:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres`

**4. Initialize schema:**
From your local rag-memory directory, run:

```bash
PGPASSWORD="[YOUR-PASSWORD]" psql "[CONNECTION-STRING]" < init.sql
```

(This creates the RAG tables in the cloud PostgreSQL)

**When you're done, save:**
- Project name
- Connection string (with password replaced)

---

## Step 2: Create Neo4j Aura Instance (Graph Database)

### What This Does
Neo4j Aura hosts the graph database for entity relationships. This replaces your local Docker Neo4j.

### How to Do It

**1. Go to https://neo4j.com/cloud/platform/**
- Sign up or log in with your Neo4j account

**2. Click "New Instance"**
- Name: `rag-memory` (or whatever you want)
- Type: Select "AuraDB Free" (free tier available)
- Region: Choose one close to you
- Click "Create"

**3. Wait for instance to start** (~5 minutes)

**4. Get your connection details:**
- Aura shows connection info on the dashboard
- Copy the connection URI (looks like: `neo4j+s://[ID].databases.neo4j.io`)
- Copy the password (shown once, save it!)
- Username is: `neo4j`

**When you're done, save:**
- Connection URI
- Username: `neo4j`
- Password

---

## Step 3: Deploy MCP Server to Fly.io

### What This Does
Deploys your RAG Memory MCP server to Fly.io so your AI agents can access it from anywhere.

### How to Do It

**1. Install Fly.io CLI:**

```bash
curl -L https://fly.io/install.sh | sh
```

**2. Log in to Fly.io:**

```bash
fly auth login
```

**3. From your rag-memory directory, create a Fly.io app:**

```bash
fly launch --name rag-memory-cloud --no-deploy
```

**4. Set environment secrets:**

```bash
fly secrets set \
  OPENAI_API_KEY="sk-your-api-key" \
  DATABASE_URL="postgresql://postgres:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres" \
  NEO4J_URI="neo4j+s://[ID].databases.neo4j.io" \
  NEO4J_USER="neo4j" \
  NEO4J_PASSWORD="[YOUR-NEO4J-PASSWORD]" \
  --app rag-memory-cloud
```

(Replace all bracketed values with your actual connection details)

**5. Deploy:**

```bash
fly deploy --app rag-memory-cloud
```

**6. Wait for deployment** (~3-5 minutes)

**7. Get your Fly.io app URL:**

```bash
fly status --app rag-memory-cloud
```

Look for the URL (something like: `https://rag-memory-cloud.fly.dev`)

**Save this URL - you'll need it next.**

---

## Step 4: Update Your AI Agent Configuration

### For Claude Code

The simplest approach: use the remote MCP server endpoint from Fly.io.

From your terminal, run:

```bash
claude mcp add-json --scope user rag-memory-cloud '{
  "type": "sse",
  "url": "https://rag-memory-cloud.fly.dev/sse",
  "env": {
    "OPENAI_API_KEY": "sk-your-api-key"
  }
}'
```

Replace:
- `https://rag-memory-cloud.fly.dev/sse` with your actual Fly.io URL + `/sse`
- `sk-your-api-key` with your OpenAI API key

Then restart Claude Code.

### For Claude Desktop

Claude Desktop cannot directly connect to remote MCP servers via SSE. You have two options:

**Option 1: Install RAG Memory locally and configure**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/path/to/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key",
        "DATABASE_URL": "your-supabase-connection-string",
        "NEO4J_URI": "your-neo4j-uri",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your-neo4j-password"
      }
    }
  }
}
```

Then restart Claude Desktop.

**Option 2: Use Claude Code instead (recommended)**

Claude Code has better support for remote MCP servers and is easier to configure. See "For Claude Code" section above.

### For Cursor or Other Agents

Add the Fly.io SSE endpoint as a remote MCP server:

```
https://rag-memory-cloud.fly.dev/sse
```

With header: `Authorization: Bearer [your-openai-api-key]`

---

## Step 5: Verify Everything Works

### Test 1: Supabase Connection

From your local rag-memory directory:

```bash
psql "[YOUR-CONNECTION-STRING]" -c "\dt"
```

(Should show the RAG tables)

### Test 2: Neo4j Connection

Go to the Neo4j Browser in your web browser:

```
neo4j+s://[ID].databases.neo4j.io
```

Then enter:
- Username: `neo4j`
- Password: Your Neo4j password

Run this query:
```cypher
MATCH (n) RETURN count(n) as count
```

(Should return 0 if new, or show existing nodes count)

### Test 3: MCP Server

In your AI agent, ask:

```
"Search RAG collections"
```

(Should return empty list if new, or show existing collections)

---

## Step 6: Migrate Your Local Data (Optional)

If you have documents already ingested locally, you can migrate them by creating a backup of your local PostgreSQL and restoring it to Supabase.

This is an advanced operation. For now, your cloud instance starts fresh. You can re-ingest documents using:
- `uv run rag ingest text "content"` - Text content
- `uv run rag ingest file path/to/file.txt` - Files
- `uv run rag ingest directory path/to/docs/` - Entire directories
- `uv run rag ingest url "https://example.com/docs"` - Web pages

Contact support if you need help migrating your existing data.

---

## Troubleshooting

### "Connection refused" on Supabase
- Check password is correct
- Check connection string includes `?ssl=require` at the end
- Verify you copied the pooler connection string, not direct connection

### "Neo4j connection timeout"
- Check Neo4j Aura instance is running (check dashboard)
- Verify connection URI is correct (includes `neo4j+s://`)
- Check firewall/network settings

### "MCP server not showing up in AI agent"
- Restart your AI agent (quit and reopen)
- Check Fly.io deployment logs: `fly logs --app rag-memory-cloud`
- Verify all environment secrets are set: `fly secrets list --app rag-memory-cloud`

### "Searches returning no results"
- Verify PostgreSQL connection working (Test 1 above)
- Ingest test data: Ask your AI agent to "Create test collection and add 5 documents"
- Check Neo4j is empty (that's normal - graph data is optional)

---

## Cost Breakdown

| Service | Free Tier | Cost |
|---------|-----------|------|
| Supabase | 500 MB database | $0-25/month if you exceed |
| Neo4j Aura | 4 GB free | $0-42/month if you exceed |
| Fly.io | $3/month minimum | $3-100+/month depending on usage |
| OpenAI | Usage-based | ~$0.02-5/month (search is free) |
| **Total** | **All free** | **~$3-10/month for small usage** |

All three services have generous free tiers. You only pay if you exceed limits.

---

## What Changed From Local?

| Component | Local | Cloud |
|-----------|-------|-------|
| PostgreSQL | Docker container | Supabase managed |
| Neo4j | Docker container | Neo4j Aura managed |
| MCP Server | Your laptop | Fly.io |
| Backups | docker-compose sidecar | Vendor automatic |
| Scaling | Manual | Automatic |

Everything else stays the same. Your documents, searches, and AI agents work identically.

---

## Next Steps

1. **After setup:** Ask your AI agent "Show me RAG Memory statistics"
2. **Start ingesting:** "Create a collection and ingest some documents"
3. **Use for real:** Integrate RAG Memory into your actual AI workflows

For detailed CLI commands, see `.reference/OVERVIEW.md` (CLI section).
For MCP tool details, see `.reference/MCP_QUICK_START.md`.
