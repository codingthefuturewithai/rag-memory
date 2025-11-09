# Cloud Deployment Reference Guide

**For interactive step-by-step guidance, run:** `/cloud-setup` custom command

This document is the detailed reference for cloud deployment. It includes detailed information about each service, troubleshooting, costs, and advanced configuration.

---

## Overview

RAG Memory can run in three configurations:

| Configuration | Best For | Setup Time |
|---|---|---|
| **Local Docker** | Development, testing, learning | 30 minutes |
| **Cloud Production** | Production, team access, remote agents | 1 hour |
| **Hybrid** | Local + cloud together | 1.5 hours |

This guide covers **Cloud Production** (Supabase + Neo4j Aura + Fly.io).

---

## Architecture: What You're Building

```
Your Cloud Setup:
├─ Supabase (us-east-1 or your choice)
│  ├─ PostgreSQL 17
│  ├─ pgvector extension
│  └─ Session pooler (persistent connections)
│
├─ Neo4j Aura (same region as Supabase)
│  ├─ Knowledge graph database
│  └─ Graphiti schema (auto-initialized)
│
└─ Fly.io (iad region, Ashburn VA)
   ├─ Docker container (MCP server)
   ├─ SSE transport (HTTP + WebSocket)
   ├─ Streamable HTTP (for webhooks)
   └─ Auto-stop/start (scale-to-zero)
```

All three services connect securely:
- Fly.io → Supabase (via DATABASE_URL)
- Fly.io → Neo4j Aura (via NEO4J_URI)
- Cloud agents → Fly.io (via HTTPS)

---

## Service 1: Supabase (PostgreSQL + pgvector)

### What is Supabase?

PostgreSQL with pgvector extension hosted in the cloud. Replaces your local Docker PostgreSQL.

### Create Account & Project

1. Go to: https://supabase.com/dashboard
2. Sign up (GitHub or email)
3. Click "New Project"
4. Choose:
   - **Name:** `rag-memory` or your choice
   - **Region:** Pick one close to your location
     - US users: `us-east-1` (Ashburn, VA) — closest to Fly.io
     - EU users: `eu-west-1` (Ireland)
     - Asia users: `ap-southeast-1` (Singapore)
   - **Database Password:** Generate strong password, save in password manager
5. Wait for project startup (~2 minutes)

### Get Connection Details

**From Supabase Dashboard:**
1. Go to: **Settings → Database → Connection Strings**
2. Select: **Session Pooler** (NOT "Direct Connection")
3. Copy: `postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`
4. Replace `[PASSWORD]` with your actual password

**Why Session Pooler?** Fly.io can have transient connections. Session pooler handles this.

### Initialize Schema

Use Alembic to create the RAG Memory schema:

```bash
export DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
cd /path/to/rag-memory
uv run alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001_baseline, baseline_fresh_schema
```

### Verify Schema Created

```bash
psql "$DATABASE_URL" -c "\dt"
```

Should show:
```
public | alembic_version       | table | postgres
public | chunk_collections     | table | postgres
public | collections           | table | postgres
public | document_chunks       | table | postgres
public | source_documents      | table | postgres
```

### Verify pgvector Installed

```bash
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Should show: `vector`

### Costs

| Tier | Storage | Cost | When to Use |
|---|---|---|---|
| **Free** | 500 MB | $0 | Personal, testing, small projects |
| **Pro** | 8 GB | $25/month | Production with regular updates |

For current pricing details, visit: https://supabase.com/pricing

**Typical RAG Memory usage:** 50,000 documents = ~50-100 MB storage. Most users stay on free tier.

### Troubleshooting

**"Connection refused"**
- Verify Session Pooler URL (not Direct Connection)
- Check password is correct
- Verify region in URL matches what you selected

**"pgvector extension not found"**
- Supabase pre-installs pgvector
- If missing, run: `psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"`

**"Pool limit exceeded"**
- Session Pooler default: 25 connections
- RAG Memory uses 1-2, so this shouldn't happen
- If it does, upgrade to Pro tier

---

## Service 2: Neo4j Aura (Knowledge Graph)

### What is Neo4j Aura?

Managed Neo4j database in the cloud for entity relationships and temporal tracking. Optional but recommended for production.

### Create Account & Instance

1. Go to: https://neo4j.com/cloud/platform/
2. Sign up (Google, GitHub, or email)
3. Click "New Instance"
4. Configure:
   - **Instance Name:** `rag-memory` or your choice
   - **Instance Type:**
     - Free tier: `Aura Free` (4 GB)
     - Paid tier: `AuraDB Professional` (starts at 4 GB)
   - **Region:** Same as Supabase if possible (us-east-1, eu-west-1, etc.)
5. Click "Create"
6. Wait for instance startup (~5 minutes)

### Get Connection Details

**From Neo4j Aura Dashboard:**
1. Instance details show connection information
2. Copy these three values:
   - **Connection URI:** `neo4j+s://abc123xyz.databases.neo4j.io` or `bolt://`
   - **Username:** `neo4j` (default)
   - **Password:** Auto-generated, shown once. Save in password manager!

### Verify Connection

**Option 1: Neo4j Browser (Web)**
1. Go to: https://[YOUR-INSTANCE-ID].databases.neo4j.io
2. Username: `neo4j`
3. Password: Your auto-generated password
4. Run query:
   ```cypher
   MATCH (n) RETURN count(n) as total_nodes
   ```
5. Should return `0` (empty is normal for new instance)

**Option 2: Command Line (if cypher-shell installed)**
```bash
cypher-shell -a "neo4j://abc123xyz.databases.neo4j.io:7687" -u neo4j -p "your-password" \
  "MATCH (n) RETURN count(n) as total_nodes"
```

### Initialize Graphiti Schema

RAG Memory uses Graphiti for automatic entity extraction. Graphiti schema initializes automatically when you first ingest documents.

No manual initialization needed.

### Costs

| Tier | Storage | Cost | When to Use |
|---|---|---|---|
| **Free** | 4 GB | $0 | Personal, testing, small projects |
| **Professional** | 10+ GB | $42-150/month | Production, larger projects |

For current pricing details, visit: https://neo4j.com/pricing/

**Typical RAG Memory usage:** 50,000 documents = ~500 MB to 2 GB in graph. Most users stay on free tier.

### Troubleshooting

**"Connection refused"**
- Verify URI uses `neo4j+s://` (secure) or `bolt://`
- Check password is correct
- Instance might still be starting, wait 5 minutes

**"Graphiti schema not initialized"**
- Schema initializes automatically on first ingest
- If issues occur, check logs in MCP server

---

## Service 3: Fly.io (MCP Server)

### What is Fly.io?

Container hosting platform. Runs your MCP server so cloud agents can access it.

### Create Account

1. Go to: https://fly.io
2. Sign up (GitHub or email)
3. Add payment method (charges only for usage)

### Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
```

Verify:
```bash
fly version
```

### Authenticate

```bash
fly auth login
```

Opens browser for login.

### Create App

From rag-memory directory:

```bash
fly launch --region iad --name rag-memory-mcp --no-deploy
```

This creates the app definition but doesn't deploy yet.

**What `--region iad` means:**
- `iad` = Ashburn, Virginia (US East)
- Closest to Supabase us-east-1 (low latency)
- Choose other regions if deploying elsewhere

### Set Secrets (Credentials)

```bash
fly secrets set \
  OPENAI_API_KEY="sk-your-actual-api-key" \
  DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres" \
  NEO4J_URI="neo4j+s://[YOUR-INSTANCE-ID].databases.neo4j.io" \
  NEO4J_USER="neo4j" \
  NEO4J_PASSWORD="your-neo4j-password" \
  --app rag-memory-mcp
```

**Important:**
- `DATABASE_URL` should be exactly what you used with `alembic upgrade`
- Use `neo4j+s://` for Aura (secure)
- All credentials stored securely in Fly's vault

### Deploy

```bash
fly deploy --app rag-memory-mcp
```

**What happens:**
1. Docker image builds (includes Playwright, Crawl4AI, dependencies)
2. Pushed to Fly.io registry
3. Container starts on VM
4. Exposed on https://rag-memory-mcp.fly.dev

**Takes 3-5 minutes first time (includes Docker build), 30-60 seconds after.**

### Get Your Public URL

```bash
fly status --app rag-memory-mcp
```

Look for `URL:` line. Should be something like:
```
https://rag-memory-mcp.fly.dev
```

### Verify Deployment

```bash
# Check if container is running
fly status --app rag-memory-mcp

# View logs
fly logs --app rag-memory-mcp

# Test MCP endpoint
curl https://rag-memory-mcp.fly.dev/sse
```

### Costs

| Configuration | CPU | Memory | Idle Cost | Active Cost |
|---|---|---|---|---|
| **Current Setup** | shared (1) | 1 GB | $0/month* | ~$3-10/month |
| **Upgraded** | shared (2) | 2 GB | $0/month* | ~$7-20/month |
| **Large** | 4-CPU | 8 GB | $0/month* | $30-100+/month |

*With scale-to-zero enabled (default in fly.toml)

**Breakdown for current setup:**
- Machine active: $0.0000008/second
- ~60 hours/month active: $1.73
- Plus fixed IP (if added): ~$2/month
- Plus data transfer (usually minimal): <$1/month
- **Total: ~$3-5/month for typical usage**

For detailed pricing: https://fly.io/docs/about/pricing/

### Auto-Stop Configuration

Fly.io's `fly.toml` includes:
```toml
[http_service]
auto_stop_machines = "suspend"
auto_start_machines = true
```

**What this does:**
- After 5 minutes idle: Container suspends (costs $0)
- On request: Automatically starts (2-5 second cold start)
- Perfect for low-usage scenarios

### Updating After Deployment

When you update code locally:

```bash
# Pull latest changes
git pull

# Redeploy
fly deploy --app rag-memory-mcp
```

Takes 30-60 seconds (just rebuilds Docker, no cold start).

### Troubleshooting

**"Port 8000 already in use"**
- Previous container didn't shut down
- Solution: `fly restart --app rag-memory-mcp`

**"Dockerfile not found"**
- Make sure you're running from rag-memory directory
- Verify `Dockerfile` exists: `ls -la Dockerfile`

**"Connection refused" from Fly.io to Supabase**
- Check `DATABASE_URL` secret is set correctly
- Verify Supabase Session Pooler URL (not Direct Connection)
- Test locally: `psql "$DATABASE_URL" -c "SELECT 1"`

**"Neo4j connection timeout"**
- Check `NEO4J_URI` secret format (should be `neo4j+s://...`)
- Verify Aura instance is running (check dashboard)
- Test timeout: `fly logs --app rag-memory-mcp | grep -i neo4j`

---

## Connecting AI Agents to Your Cloud Server

### Claude Code

```bash
claude mcp add --transport sse --scope user rag-memory https://rag-memory-mcp.fly.dev/sse
```

Restart Claude Code, then test:
```
"List my RAG Memory collections"
```

### Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/Users/you/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key",
        "DATABASE_URL": "postgresql://...",
        "NEO4J_URI": "neo4j+s://...",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "..."
      }
    }
  }
}
```

Restart Claude Desktop.

### ChatGPT, Make.com, Zapier, Custom Agents

Use the SSE endpoint:
```
https://rag-memory-mcp.fly.dev/sse
```

With Bearer token (if required):
```
Authorization: Bearer sk-your-openai-api-key
```

---

## Cost Summary

| Service | Free Tier | Typical Monthly | When You'd Pay |
|---|---|---|---|
| **OpenAI** | $5 credit (3 months) | <$1 | Only on ingestion, not search |
| **Supabase** | 500 MB (unlimited ops) | $0-25 | Exceeding 500 MB storage |
| **Neo4j Aura** | 4 GB (free tier) | $0-42 | Exceeding 4 GB storage |
| **Fly.io** | Included credits | $3-10 | Usage beyond free credits |
| **Total** | All free tier | **~$3-10/month** | **Only if high usage** |

Most personal and team deployments stay entirely on free tiers.

---

## Production Checklist

Before going to production:

- [ ] Supabase project created with strong database password
- [ ] PostgreSQL schema initialized with `alembic upgrade head`
- [ ] Neo4j Aura instance created with saved password
- [ ] Fly.io app created and secrets configured
- [ ] MCP server deployed successfully
- [ ] Public URL working (`curl https://rag-memory-mcp.fly.dev/sse`)
- [ ] At least one agent connected and tested
- [ ] PostgreSQL and Neo4j health checked
- [ ] Cost monitoring dashboard set up (optional)

---

## Hybrid Setup (Local + Cloud)

You can run both local and cloud simultaneously:

**Local config:**
```bash
export DATABASE_URL="postgresql://raguser:pass@localhost:54320/rag_memory"
export NEO4J_URI="bolt://localhost:7687"
rag status  # Uses local
```

**Cloud config:**
```bash
export DATABASE_URL="postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres"
export NEO4J_URI="neo4j+s://[INSTANCE].databases.neo4j.io"
rag status  # Uses cloud
```

Switch between them by changing environment variables. Both can coexist.

---

## Updating Your Deployment

### Update RAG Memory Code

```bash
cd /path/to/rag-memory
git pull  # Get latest code

# Redeploy to Fly.io
fly deploy --app rag-memory-mcp
```

### Update Secrets

```bash
fly secrets set \
  OPENAI_API_KEY="sk-new-key" \
  --app rag-memory-mcp
```

Changed secrets apply on next deployment.

### Rollback Deployment

```bash
fly releases --app rag-memory-mcp  # See release history
fly scale count 1 --app rag-memory-mcp  # Revert to previous version
```

---

## Monitoring & Maintenance

### Check Logs

```bash
fly logs --app rag-memory-mcp --recent
fly logs --app rag-memory-mcp --follow  # Real-time
```

### Check Database Usage

**Supabase:**
- Dashboard → Database → Usage
- Shows storage, connections, queries

**Neo4j Aura:**
- Dashboard → Instance details → Metrics
- Shows storage, operations, queries

**Fly.io:**
- Dashboard → Machines
- Shows CPU, memory, network usage

### Backup Strategy

**PostgreSQL:**
- Supabase includes automated daily backups
- Dashboard → Database → Backups
- No action needed, automatic

**Neo4j Aura:**
- Aura Free: No automatic backups
- Aura Professional: Daily backups
- Manual backup via Neo4j Browser dump

---

## Next Steps

1. **Get started:** Run `/cloud-setup` command for interactive guidance
2. **Verify:** Use health check commands in each service
3. **Connect agents:** Add MCP server to Claude Code/Desktop
4. **Monitor:** Set up dashboards for cost and performance
5. **Scale:** If needed, upgrade machine size or database tiers

---

## Frequently Asked Questions

**Q: Can I migrate from local to cloud?**
A: Yes. Export local PostgreSQL dump, import to Supabase. See DATABASE_MIGRATION_GUIDE.md (if applicable).

**Q: Can I use different regions for each service?**
A: Yes, but latency will be higher. Recommended: US East region for all (iad on Fly, us-east-1 on Supabase/Aura).

**Q: What if a service goes down?**
A: MCP server requires both databases ("All or Nothing" architecture). If either Neo4j or PostgreSQL is unavailable, the server refuses to start. There is no graceful degradation or RAG-only fallback mode.

**Q: Can I scale to multiple Fly.io machines?**
A: Yes. Fly.io handles load balancing automatically. Update fly.toml `min_machines_running`.

**Q: How much does data transfer cost?**
A: Fly.io: Free within regions, $0.02/GB out. Supabase: Included. Neo4j: Included.

**Q: Do I need to restart the server after updating?**
A: `fly deploy` automatically restarts. Downtime: 30-60 seconds.

---

## Resources

- **Fly.io Docs:** https://fly.io/docs/
- **Supabase Docs:** https://supabase.com/docs
- **Neo4j Aura:** https://neo4j.com/docs/aura/
- **OpenAI Pricing:** https://openai.com/api/pricing/
- **RAG Memory CLI Reference:** See CLAUDE.md or run `rag --help`

---

**Last Updated:** 2025-11-08
**Version:** 0.13.0
