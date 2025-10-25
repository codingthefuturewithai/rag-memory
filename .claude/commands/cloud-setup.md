---
description: Deploy RAG Memory to cloud - Supabase, Neo4j Aura, and Fly.io
allowed-tools: ["Read", "Bash"]
---

# Deploy RAG Memory to the Cloud

You're about to deploy RAG Memory to production so cloud-hosted AI agents can access your knowledge base from anywhere.

**We'll do this in order:**
1. Create Supabase account and initialize PostgreSQL schema
2. Create Neo4j Aura account and initialize graph database
3. Deploy MCP server to Fly.io
4. Verify everything and connect your agents

**Estimated time:** 45-60 minutes active work + 15-20 minutes waiting for services to start

---

## ✅ BEFORE YOU START

Make sure you have:
- [ ] OpenAI API key (from https://platform.openai.com/api-keys) — you already have this
- [ ] A credit card (all services have free tiers, but verification required)
- [ ] Your local RAG Memory repo cloned (you just finished `/getting-started`)
- [ ] ~1 hour of uninterrupted time

**Have you gathered everything? Ready to start? (yes/no)**

---

## PART 1: SUPABASE SETUP (PostgreSQL + pgvector)

### Your Task: Create Supabase Project

1. Go to: **https://supabase.com/dashboard**
2. Click **"New Project"**
3. Fill in:
   - **Project Name:** `rag-memory` (or your choice)
   - **Region:** Choose one closest to you (us-east-1, eu-west-1, ap-southeast-1, etc.)
   - **Database Password:** Auto-generated or create a strong one. **SAVE THIS IN A PASSWORD MANAGER.**

4. Wait for the project to start (~2 minutes)

### Save These Three Values

After your project is created, you'll need:

1. **Project Reference ID** — Find it in:
   - Dashboard → Settings → General → Reference ID
   - Looks like: `abc123def456`

2. **Database Password** — The one you created/generated above

3. **Region** — The one you selected (us-east-1, eu-west-1, etc.)

**⏱️ This takes about 2-3 minutes.**

**Have you completed Supabase setup and saved those three values? (yes/no)**

---

### Initialize PostgreSQL Schema

Once you've confirmed yes, we'll initialize the schema:

```bash
export DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
cd /path/to/rag-memory
uv run alembic upgrade head
```

Replace:
- `[REF]` with your Project Reference ID
- `[PASSWORD]` with your database password
- `[REGION]` with your region (us-east-1, eu-west-1, etc.)

**Example:**
```bash
export DATABASE_URL="postgresql://postgres.abc123def456:MySecurePassword123@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
uv run alembic upgrade head
```

This command runs the baseline migration and creates all RAG Memory tables in Supabase.

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001_baseline, baseline_fresh_schema
```

**Did the migration complete successfully? (yes/no)**

---

## PART 2: NEO4J AURA SETUP (Knowledge Graph)

### Your Task: Create Neo4j Aura Instance

1. Go to: **https://neo4j.com/cloud/platform/**
2. Sign in or create a Neo4j account
3. Click **"New Instance"**
4. Configure:
   - **Instance Name:** `rag-memory` (or your choice)
   - **Instance Type:** Select free tier if available, or `AuraDB Professional`
   - **Region:** Choose same region as Supabase if possible (for latency)
   - Click **"Create"**

5. Wait for instance to start (~5 minutes)

### Save These Four Values

After your instance is created:

1. **Connection URI** — Copy from dashboard
   - Looks like: `neo4j+s://abc123xyz.databases.neo4j.io`
   - Should include `neo4j+s://` (secure) or `bolt://`

2. **Username** — Default is `neo4j`

3. **Password** — Auto-generated on instance creation. **SAVE THIS IN A PASSWORD MANAGER.**

4. **Region** — The one you selected

**Have you completed Neo4j Aura setup and saved those four values? (yes/no)**

---

### Verify Neo4j Connection

We can verify the Neo4j connection, but we don't need to initialize schema — it auto-initializes.

To verify (optional, but recommended):
- Go to Neo4j Browser: **https://[YOUR-INSTANCE-ID].databases.neo4j.io**
- Username: `neo4j`
- Password: The one you created
- Run this query:
  ```cypher
  MATCH (n) RETURN count(n) as total_nodes
  ```
- Should return 0 if new (that's normal)

**Did verification work? (yes/no)**

---

## PART 3: FLY.IO DEPLOYMENT (MCP Server)

### Prerequisites

1. Install Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Create Fly.io account at **https://fly.io** (free tier available)

3. Authenticate:
```bash
fly auth login
```

### Deploy to Fly.io

From your rag-memory directory:

```bash
# Create a new Fly.io app (don't deploy yet)
fly launch --region iad --name rag-memory-mcp --no-deploy
```

The `iad` region is Ashburn, VA (closest to Supabase us-east-1).

**Did `fly launch` complete successfully? (yes/no)**

---

### Set Secrets

Now set the environment variables (your database credentials):

```bash
fly secrets set \
  OPENAI_API_KEY="sk-your-actual-api-key" \
  DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres" \
  NEO4J_URI="neo4j+s://[YOUR-INSTANCE-ID].databases.neo4j.io" \
  NEO4J_USER="neo4j" \
  NEO4J_PASSWORD="your-neo4j-password" \
  --app rag-memory-mcp
```

Replace all bracketed values with your actual credentials.

**Important:** Use the exact same `DATABASE_URL` from PART 1 above.

**Did `fly secrets set` complete successfully? (yes/no)**

---

### Deploy

```bash
fly deploy --app rag-memory-mcp
```

This builds the Docker image and deploys to Fly.io. **Takes 3-5 minutes.**

**Did deployment complete successfully? (yes/no)**

---

## PART 4: VERIFY EVERYTHING WORKS

### Get Your Fly.io URL

```bash
fly status --app rag-memory-mcp
```

Look for the URL in output. It'll be something like:
```
https://rag-memory-mcp.fly.dev
```

**Save this URL — you'll need it to connect agents.**

### Test PostgreSQL Connection

From your local machine:

```bash
export DB_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
psql "$DB_URL" -c "SELECT count(*) as tables FROM information_schema.tables WHERE table_schema='public';"
```

Should return: `5` (collections, source_documents, document_chunks, chunk_collections, alembic_version)

**Did PostgreSQL test pass? (yes/no)**

---

### Test MCP Server

```bash
curl https://rag-memory-mcp.fly.dev/sse
```

Should get a response (might be streaming). If you get a response without errors, it's working!

**Did MCP server test pass? (yes/no)**

---

## ✅ YOU'RE DONE!

Your RAG Memory cloud stack is live.

**Your cloud deployment includes:**
- ✅ Supabase PostgreSQL with pgvector (for semantic search)
- ✅ Neo4j Aura (for knowledge graphs)
- ✅ Fly.io MCP Server (accessible from anywhere)

---

## NEXT: CONNECT YOUR AI AGENTS

### For Claude Code

```bash
claude mcp add rag-memory --type sse --url https://rag-memory-mcp.fly.dev/sse
```

Replace `rag-memory-mcp.fly.dev` with your actual Fly.io URL.

Restart Claude Code, then ask:
```
"List my RAG Memory collections"
```

### For Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add:
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/path/to/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key",
        "DATABASE_URL": "your-supabase-url",
        "NEO4J_URI": "your-neo4j-uri",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your-neo4j-password"
      }
    }
  }
}
```

Restart Claude Desktop.

### For Other AI Agents (ChatGPT, Make.com, Zapier)

Use this endpoint:
```
https://rag-memory-mcp.fly.dev/sse
```

With header:
```
Authorization: Bearer [your-openai-api-key]
```

---

## 📚 DETAILED REFERENCE

For more details, troubleshooting, and advanced configuration:
- See: `.reference/CLOUD_DEPLOYMENT.md`

This document has the complete cloud setup guide with pricing, troubleshooting, and detailed information.

---

**🎉 Congratulations! You now have RAG Memory in production, accessible from anywhere.**
