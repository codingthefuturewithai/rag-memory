# Cloud Deployment Guide

**For interactive guidance, run:** `/cloud-setup` slash command

This is the complete technical reference for deploying RAG Memory to the cloud using the automated deployment script.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Running the Deployment](#running-the-deployment)
4. [What the Script Does](#what-the-script-does)
5. [Verification and Testing](#verification-and-testing)
6. [Troubleshooting](#troubleshooting)
7. [Cost Estimates](#cost-estimates)
8. [Reference Links](#reference-links)

---

## Overview

RAG Memory deploys to cloud infrastructure using the **automated deployment script** (`scripts/deploy_to_cloud.py`) which handles:

**Services Created:**
- ✅ **PostgreSQL database** (Render) - Vector storage with pgvector
- ✅ **Neo4j Aura** - Knowledge graph (managed cloud service)
- ✅ **MCP Server** (Render) - Docker web service with FastMCP

**Automated Tasks:**
- ✅ Creates all services via REST APIs
- ✅ Enables pgvector extension
- ✅ Runs database migrations
- ✅ Initializes Neo4j Graphiti schema (28 indexes/constraints)
- ✅ Configures all environment variables
- ✅ Detects and migrates local Docker data (optional)
- ✅ Verifies connectivity and data integrity

**Total deployment time:** 20-30 minutes (databases take ~5-10 min each, migrations vary by data size)

---

## Prerequisites

### Account Requirements

**Render Account:**
- Create account at: https://render.com
- Create API key at: https://dashboard.render.com/u/settings#api-keys
- **Payment method required** - Free tier not available via API
- Estimated cost: $15-25/month for all services

**Neo4j Aura Account:**
- Create account at: https://console.neo4j.io
- Create API credentials: Account → API Credentials
  - Client ID
  - Client Secret
- **Professional tier required** for 2GB instances ($65/month)
  - Free tier (512MB) available but limited
  - Aura Free works for testing but has strict limits

**OpenAI Account:**
- Create account at: https://platform.openai.com
- Create API key at: https://platform.openai.com/api-keys
- Cost: ~$1-5/month for embeddings

### Local Tools

**Python Environment:**
- Python 3.10+ (included in RAG Memory via `uv`)
- No manual installation needed - `uv` handles everything

**Data Migration (Optional - only if migrating from local Docker):**
- `docker` - Verify: `docker --version`
- `psql` - PostgreSQL client
  - macOS: `brew install postgresql`
  - Ubuntu/Debian: `sudo apt-get install postgresql-client`
  - Windows: https://www.postgresql.org/download/windows/
  - Alternative: `alias psql='docker run --rm -i postgres:16 psql'`

---

## Running the Deployment

### Step 1: Navigate to Project

```bash
cd /path/to/rag-memory
```

### Step 2: Set Environment Variables (Optional)

```bash
# Optional: Set credentials to avoid interactive prompts
export RENDER_API_KEY="rnd_xxx"
export AURA_CLIENT_ID="xxx"
export AURA_CLIENT_SECRET="xxx"
export OPENAI_API_KEY="sk-proj-xxx"
```

If not set, script will prompt for each.

### Step 3: Run Deployment Script

```bash
python scripts/deploy_to_cloud.py
```

### Step 4: Follow Interactive Prompts

**The script will guide you through:**

#### 1. Data Migration Detection

```
🔍 Detecting local Docker deployment...
✓ Found PostgreSQL container: 15 documents, 342 chunks
✓ Found Neo4j container: 89 nodes, 124 relationships

Migrate local data to cloud? [Y/n]:
```

- **Yes** - Migrates all data to cloud (recommended if data is important)
- **No** - Fresh deployment (local data stays in Docker)

#### 2. API Authentication

```
🔐 Render API Key
Create at: https://dashboard.render.com/u/settings#api-keys

Enter Render API key: ********

🔍 Fetching workspace ID...
✓ Using workspace: My Workspace (own-abc123)
```

```
🔐 Neo4j Aura API Credentials
Create at: https://console.neo4j.io → Account → API Credentials

Aura Client ID: ********
Aura Client Secret: ********
```

```
🔑 OpenAI API Key
Required for embeddings and knowledge graph

OpenAI API Key: ********
```

#### 3. Configuration

```
⚙️  Deployment Configuration

Region selection:
  1. oregon
  2. ohio
  3. virginia
  4. frankfurt
  5. singapore
Region (1): 3

PostgreSQL Plan:
Valid plans: basic_256mb, basic_1gb, basic_4gb, pro_4gb, etc.
Plan (basic_256mb):

Neo4j Aura Instance Size:
Valid sizes: 1GB, 2GB, 4GB, 8GB, 16GB
Memory (2GB): 2GB

Cloud Provider for Aura:
Options: aws, gcp, azure
Provider (aws):
```

**Plan Selection Guidance:**
- **PostgreSQL:** `basic_256mb` for small/test deployments, `basic_1gb` for production
- **Neo4j Aura:** 2GB minimum recommended for real workloads (Free tier = 512MB, very limited)
- **Cloud Provider:** AWS generally has best region availability

#### 4. Confirmation

```
Deployment Summary:
  Project: rag-memory
  Region: virginia
  PostgreSQL (Render): basic_256mb
  Neo4j (Aura): 2GB on aws
  Migrate data: Yes

Proceed with deployment? [y/n] (y):
```

#### 5. Service Creation & Migration

```
🚀 Creating PostgreSQL database on Render...
✓ PostgreSQL created: rag-memory-db
  Database ID: dpg-xxx
  Waiting for database to be ready...
  Status: creating, waiting... (0s)
  Status: available ✓

🔌 Enabling pgvector extension...
✓ pgvector extension enabled

⏳ Waiting 30s for PostgreSQL SSL initialization...

📊 Running database migrations...
✓ Alembic migrations complete

🔗 Creating Neo4j Aura instance...
✓ Aura instance created
  Instance ID: xxx
  Connection URL: neo4j+s://xxx.databases.neo4j.io
  Username: neo4j
  Password: <auto-generated-64-chars>

⏳ Waiting for Aura instance to be ready...
  Status: creating... (30s)
✓ Aura instance ready

🔧 Initializing Graphiti schema on Aura...
✓ Graphiti schema initialized (28 indexes/constraints)

📦 Migrating PostgreSQL data...
✓ Data exported (2.34 MB)
✓ Data imported
🔍 Verifying counts...
  Documents: 15/15 ✓
  Chunks: 342/342 ✓

📦 Migrating Neo4j data...
✓ Export complete (0.45 MB)
✓ Import complete via Bolt connection

🚀 Creating MCP server on Render...
  Repository: https://github.com/codingthefuturewithai/rag-memory
  Branch: main
  Plan: starter

✓ MCP server created: rag-memory-mcp
  Service ID: srv-xxx
  Building Docker image... (5-10 minutes)

✓ Build complete
✓ Service is LIVE
  URL: https://rag-memory-mcp.onrender.com
```

#### 6. Deployment Summary

```
✅ Deployment Complete!

PostgreSQL (Render):
  External URL: postgresql://user:pass@dpg-xxx.render.com/ragmemory
  Database: ragmemory

Neo4j (Aura):
  Connection URL: neo4j+s://xxx.databases.neo4j.io
  Username: neo4j
  Password: xlQOa8E5phSrtYOjRBPn... (first 20 chars shown)
  Console: https://console.neo4j.io/

MCP Server (Render):
  URL: https://rag-memory-mcp.onrender.com
  SSE Endpoint: https://rag-memory-mcp.onrender.com/sse
  Health Check: https://rag-memory-mcp.onrender.com/health

Next Steps:
  1. Save Neo4j password (check Neo4j-credentials-*.txt file)
  2. Test MCP server health: curl https://rag-memory-mcp.onrender.com/health
  3. Connect AI agent: claude mcp add --transport sse rag-memory https://rag-memory-mcp.onrender.com/sse
```

**CRITICAL:** Script saves Neo4j credentials to `Neo4j-credentials-RAG Memory MCP Server-Created-<timestamp>.txt` in project root

---

## What the Script Does

### Phase 1: Environment Detection

- Checks if Docker is running
- Detects local RAG Memory containers
- Counts documents, chunks, nodes, relationships
- Asks user if they want to migrate data

### Phase 2: Render Setup

**PostgreSQL Creation:**
1. Creates database via `POST /postgres` API
2. Polls until status = `available` (~2-5 minutes)
3. Retrieves External connection URL from API
4. Enables pgvector extension via `psql`
5. Waits 30 seconds for SSL cert initialization
6. Runs Alembic migrations to create schema

**Key Details:**
- Password auto-generated by Render (returned in API response)
- External URL format: `postgresql://user:pass@host.render.com/dbname`
- Tables created: `source_documents`, `document_chunks`, `collections`, `chunk_collections`
- HNSW index created for vector search

### Phase 3: Neo4j Aura Setup

**Instance Creation:**
1. Gets OAuth token using client credentials
2. Fetches tenant ID from account
3. Creates instance via `POST /v1/instances` API
4. API auto-generates password (64 characters)
5. Returns: instance ID, connection URL, username, password
6. Polls until status = `running` (~5-10 minutes)

**Schema Initialization:**
1. Connects via Bolt: `neo4j+s://xxx.databases.neo4j.io`
2. Initializes Graphiti using `graphiti-core` library
3. Creates 28 indexes and constraints for knowledge graph
4. Verifies schema with `SHOW INDEXES` query

**Key Details:**
- Connection uses Bolt with TLS (`neo4j+s://`)
- Password auto-generated (never manually typed)
- Username is always `neo4j` (Aura default)
- Bolt connections work perfectly (unlike Neo4j on Render Docker)

### Phase 4: Data Migration (Optional)

**PostgreSQL Migration:**
1. Exports using `docker exec pg_dump` with `--no-owner --no-privileges`
2. Imports using `psql` to External URL
3. Verifies document and chunk counts match

**Neo4j Migration:**
1. Connects to local Neo4j via Bolt
2. Uses Graphiti's export capabilities
3. Imports to Aura via Bolt connection
4. Verifies node and relationship counts match

**Key Details:**
- No SSH required (Bolt works for Aura)
- Migration safe to retry
- Verification catches discrepancies

### Phase 5: MCP Server Deployment

**Service Creation:**
1. Creates Docker web service via `POST /services` API
2. Sets environment variables:
   - `DATABASE_URL` - PostgreSQL External URL
   - `NEO4J_URI` - Aura connection URL
   - `NEO4J_USER` - `neo4j`
   - `NEO4J_PASSWORD` - Auto-generated password from Aura
   - `OPENAI_API_KEY` - User's API key
   - `PYTHONUNBUFFERED=1` - Immediate log output

**Dockerfile Configuration:**
```json
{
  "serviceDetails": {
    "runtime": "docker",
    "healthCheckPath": "/health",
    "envSpecificDetails": {
      "dockerfilePath": "deploy/docker/Dockerfile",
      "dockerContext": "."
    }
  }
}
```

**CRITICAL:** `dockerfilePath` must be in `envSpecificDetails` (not directly in `serviceDetails`)

**Build Process:**
1. Render clones GitHub repository
2. Runs multi-stage Docker build:
   - Builder stage: Installs dependencies with `uv`
   - Runtime stage: Copies code and runs server
3. Starts MCP server on port 10000
4. Runs health checks at `/health`
5. Service goes live (~7-10 minutes total)

**Startup Validation:**
- Connects to PostgreSQL (validates schema)
- Connects to Neo4j (validates schema with 28 indexes)
- Server exits if either database unavailable (fail-fast design)

---

## Verification and Testing

### Step 1: Check Service Status

Visit Render Dashboard: https://dashboard.render.com

**Expected Status:**
- PostgreSQL: `Available` (green)
- MCP Server: `Live` (green)

Visit Neo4j Aura Console: https://console.neo4j.io

**Expected Status:**
- Instance: `Running` (green)

### Step 2: Test MCP Server Health

```bash
curl https://rag-memory-mcp.onrender.com/health
```

**Expected Response:**
```json
{"status":"healthy"}
```

### Step 3: Connect AI Agent

**Claude Code:**
```bash
claude mcp add --transport sse --scope user rag-memory https://rag-memory-mcp.onrender.com/sse

# Restart Claude Code session
claude mcp list  # Verify rag-memory shows ✓ Connected
```

### Step 4: Test MCP Tools

Use the MCP server from Claude Code:

```
List my RAG Memory collections
```

Expected: Shows migrated collections (if data migrated) or empty list (if fresh deployment)

```
Search for "test" in <collection-name>
```

Expected: Returns relevant documents (if data migrated)

```
Query relationships: How does RAG Memory combine technologies?
```

Expected: Returns knowledge graph relationships (if data migrated)

### Step 5: Verify Data Migration (If Migrated)

**Document Count:**
- Use MCP tool: "List documents in <collection-name>"
- Compare count to local deployment
- Should match exactly

**Search Quality:**
- Run same search query on both local and cloud
- Results should be identical (same similarity scores)

**Knowledge Graph:**
- Query relationships on both deployments
- Same facts should be returned

---

## Troubleshooting

### Script Fails: "Failed to get workspace ID"

**Problem:** Render API authentication failed

**Solutions:**
1. Verify API key is correct (copy again from dashboard)
2. Check API key hasn't been revoked
3. Ensure API key has workspace access

**Create new key:** https://dashboard.render.com/u/settings#api-keys

### Script Fails: "Failed to create PostgreSQL"

**Problem:** Render API rejected database creation request

**Common Causes:**
1. **Invalid plan name** - Must use underscores: `basic_256mb` (not `basic-256mb`)
2. **Region invalid** - Use: `oregon`, `ohio`, `virginia`, `frankfurt`, or `singapore`
3. **No payment method** - Add card to Render account
4. **Insufficient permissions** - API key needs workspace owner/admin access

**Valid PostgreSQL Plans:**
- Basic: `basic_256mb`, `basic_1gb`, `basic_4gb`
- Pro: `pro_4gb`, `pro_8gb`, `pro_16gb`, ..., `pro_512gb`

### Script Fails: "Failed to get Aura OAuth token"

**Problem:** Neo4j Aura API authentication failed

**Solutions:**
1. Verify Client ID and Client Secret are correct
2. Check credentials haven't been revoked
3. Create new API credentials at: https://console.neo4j.io → Account → API Credentials

### Script Fails: "Failed to create Aura instance"

**Problem:** Aura API rejected instance creation

**Common Causes:**
1. **No payment method** - Aura requires billing for Professional tier (2GB+)
2. **Invalid memory size** - Use: `1GB`, `2GB`, `4GB`, `8GB`, `16GB`
3. **Invalid cloud provider** - Use: `aws`, `gcp`, or `azure`
4. **Region availability** - Some regions only available on certain providers

**Valid Aura Memory Sizes:**
- Free: `512MB` (very limited, good for testing only)
- Professional: `1GB`, `2GB` (recommended minimum), `4GB`, `8GB`, `16GB`

### Script Fails: "Graphiti schema initialization failed"

**Problem:** Cannot connect to Neo4j Aura or create indexes

**Solutions:**
1. **Wait longer** - Aura instance may still be initializing (can take 10 minutes)
2. **Check Aura console** - Verify instance status is "Running"
3. **Verify password** - Script uses auto-generated password from API (should always work)
4. **Network issue** - Check if Bolt port (7687) is blocked by firewall

**Manual verification:**
```bash
# Install neo4j driver
pip install neo4j

# Test connection
python << 'EOF'
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "neo4j+s://xxx.databases.neo4j.io",
    auth=("neo4j", "password-from-credentials-file")
)
with driver.session() as session:
    result = session.run("RETURN 1")
    print(result.single()[0])
driver.close()
EOF
```

Expected output: `1`

### Script Fails: "MCP server build failed"

**Problem:** Docker build failed on Render

**Solutions:**
1. **Check build logs** - Dashboard → Service → Logs (shows exact error)
2. **Missing uv.lock** - Verify file is committed to repository
3. **Dockerfile path wrong** - Must be `deploy/docker/Dockerfile`
4. **GitHub repo inaccessible** - Verify Render can access your repository

**Common build errors:**
- Missing `uv.lock`: Commit and push this file
- Invalid Dockerfile syntax: Test build locally first
- Missing dependencies: Check `pyproject.toml` is complete

### MCP Server: Authentication failures to Neo4j

**Problem:** Server logs show `Neo.ClientError.Security.Unauthorized`

**Symptoms:**
```
ERROR Neo4j schema validation failed
  - The client is unauthorized due to authentication failure
```

**Root Cause:** Wrong Neo4j password in environment variables

**This should NEVER happen with deploy_to_cloud.py because:**
- Password is auto-generated by Aura API
- Same password used for schema init and MCP server
- No manual typing involved

**If it happens anyway:**
1. Check `Neo4j-credentials-*.txt` file for correct password
2. Verify MCP server environment variables in Render dashboard
3. Compare passwords - they must match exactly
4. Update `NEO4J_PASSWORD` in Render dashboard if mismatch

### Data Migration: Counts don't match

**Problem:** Verification shows different counts after migration

**Solutions:**
1. **Check local data didn't change** - Ensure containers weren't modified during migration
2. **Re-run migration** - Script is safe to retry
3. **Manual verification:**

```bash
# PostgreSQL
psql "<external-url>" -c "SELECT COUNT(*) FROM source_documents; SELECT COUNT(*) FROM document_chunks;"

# Neo4j (from Python)
from neo4j import GraphDatabase
driver = GraphDatabase.driver("neo4j+s://xxx", auth=("neo4j", "pass"))
with driver.session() as session:
    nodes = session.run("MATCH (n) RETURN count(n)").single()[0]
    rels = session.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
    print(f"Nodes: {nodes}, Relationships: {rels}")
```

### MCP Server: Takes forever to start

**Problem:** Service builds successfully but never becomes "Live"

**Expected Behavior:**
- Build: 5-7 minutes
- Health checks: 1-2 minutes
- Total: 7-10 minutes

**If longer than 15 minutes:**
1. **Check logs** - Look for errors during startup
2. **Database connectivity** - Verify PostgreSQL and Neo4j are reachable
3. **Health check failing** - Server may be crashing after start

**Common causes:**
- Database connection refused (wrong URLs)
- Missing environment variables
- OpenAI API key invalid (server can't start without it)

### General Debugging Strategy

**Step 1: Identify which service is failing**
- PostgreSQL creation?
- Neo4j Aura creation?
- Schema initialization?
- Data migration?
- MCP server deployment?

**Step 2: Check service logs**
- Render: Dashboard → Service → Logs
- Aura: Console → Instance → Query Log

**Step 3: Verify environment variables**
- Render: Dashboard → Service → Environment
- Check all 6 required variables are set correctly

**Step 4: Test connectivity manually**
- Use `psql` for PostgreSQL
- Use Python `neo4j` driver for Aura
- Use `curl` for MCP server health

**Step 5: Consult documentation**
- Render API docs: https://api-docs.render.com
- Neo4j Aura docs: https://neo4j.com/docs/aura/
- RAG Memory issues: https://github.com/codingthefuturewithai/rag-memory/issues

---

## Cost Estimates

**Always check current pricing before deploying:**
- Render: https://render.com/pricing
- Neo4j Aura: https://neo4j.com/pricing
- OpenAI: https://openai.com/pricing

### Typical Monthly Costs

**Minimum Viable Production:**

| Service | Plan | Cost |
|---------|------|------|
| PostgreSQL (Render) | Basic 256MB | ~$7/month |
| Neo4j Aura | Professional 2GB | ~$65/month |
| MCP Server (Render) | Starter | ~$7/month |
| OpenAI API | Embeddings only | ~$1-5/month |
| **Total** | | **~$80-85/month** |

**Notes:**
- Largest cost is Neo4j Aura Professional tier
- Aura Free (512MB) available but very limited
- OpenAI cost varies with usage (search is free, only embeddings cost)
- Data transfer included in plans

**Cost Optimization:**
- Start with Aura Free for testing ($0/month)
- Upgrade to Aura Professional when ready for production
- Use smallest PostgreSQL plan that fits your data
- Starter MCP plan sufficient for most workloads

---

## Reference Links

### Required Accounts

- **Render:** https://render.com
  - API Keys: https://dashboard.render.com/u/settings#api-keys
  - Documentation: https://render.com/docs
  - API Docs: https://api-docs.render.com
  - Pricing: https://render.com/pricing

- **Neo4j Aura:** https://console.neo4j.io
  - API Credentials: Account → API Credentials
  - Documentation: https://neo4j.com/docs/aura/
  - Pricing: https://neo4j.com/pricing

- **OpenAI:** https://platform.openai.com
  - API Keys: https://platform.openai.com/api-keys
  - Pricing: https://openai.com/pricing

### RAG Memory

- **Repository:** https://github.com/codingthefuturewithai/rag-memory
- **Deployment Script:** `scripts/deploy_to_cloud.py`
- **Issues:** https://github.com/codingthefuturewithai/rag-memory/issues

---

## Production Checklist

Before going live with production data:

- [ ] All services created and showing "Live"/"Running"
- [ ] PostgreSQL on PAID plan (not free tier)
- [ ] Neo4j Aura on Professional plan (2GB+ for production workloads)
- [ ] MCP server on PAID plan (Starter minimum for always-on)
- [ ] MCP server health check returns `{"status":"healthy"}`
- [ ] Neo4j password saved securely (from credentials file)
- [ ] All environment variables verified in Render dashboard
- [ ] Database schema validated (28 Neo4j indexes confirmed)
- [ ] Data migration verified (if applicable) - counts match
- [ ] At least one AI agent connected and tested
- [ ] Search returns correct results
- [ ] Knowledge graph queries work
- [ ] Monitoring enabled (Render dashboard alerts)
- [ ] Cost tracking reviewed and acceptable
- [ ] Backup strategy confirmed (Render auto-backups enabled)

---

**This guide supports the automated deployment script (`scripts/deploy_to_cloud.py`). For step-by-step interactive assistance, use the `/cloud-setup` slash command.**
