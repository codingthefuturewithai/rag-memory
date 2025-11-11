# Cloud Deployment Guide for Render

**For interactive guidance, run:** `/cloud-setup` slash command

This is the complete technical reference for deploying RAG Memory to Render using the automated deployment script.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Automated Deployment Script](#automated-deployment-script)
4. [Running the Deployment](#running-the-deployment)
5. [MCP Server Setup](#mcp-server-setup)
6. [Verification and Testing](#verification-and-testing)
7. [Troubleshooting](#troubleshooting)
8. [Manual Deployment (Fallback)](#manual-deployment-fallback)
9. [Cost Estimates](#cost-estimates)

---

## Overview

RAG Memory can be deployed to Render using the **automated deployment script** which handles:

- ✅ Creates Render Project to organize resources
- ✅ Creates production environment within project
- ✅ Creates PostgreSQL database in project environment via Render REST API
- ✅ Enables pgvector extension automatically
- ✅ Creates Neo4j Docker service in project environment via Render REST API
- ✅ Configures all environment variables programmatically
- ✅ Detects local Docker data and offers migration
- ✅ Migrates PostgreSQL data (pg_dump → psql)
- ✅ Migrates Neo4j data (APOC export → SSH/SCP → import)
- ✅ Verifies data integrity after migration
- ✅ All resources properly organized within a single project
- ✅ No manual dashboard steps required for databases

**What's NOT automated (yet):**
- MCP Server creation (manual step after databases are ready)

**Script location:** `scripts/deploy_to_render.py`

---

## Prerequisites

### Required for All Deployments

**Render Account with API Key:**
- **AI Assistant:** If user doesn't have Render account, guide them to https://render.com to create one
- **API Key Creation:**
  - **AI Assistant:** Direct user to create API key at https://dashboard.render.com/u/settings#api-keys
  - User will need this key for the deployment script
  - API key grants access to user's workspaces for programmatic service creation

**Payment Method:**
- Render API requires paid plans (free tier not available via API)
- **AI Assistant:** Research current Render plan pricing at https://render.com/pricing
- Minimum estimated cost: $15-20/month for all services

**OpenAI API Key:**
- Required for embeddings
- Get from: https://platform.openai.com/api-keys

**Python Environment:**
- Python 3.8+ (already included in RAG Memory project via uv)

### Additional Requirements for Data Migration

**Only needed if migrating from local Docker:**

- **docker** - Verify: `docker --version`
- **psql** - PostgreSQL client
  - macOS: `brew install postgresql`
  - Ubuntu/Debian: `sudo apt-get install postgresql-client`
  - Windows: Install from https://www.postgresql.org/download/windows/
  - Alternative: Use Docker: `alias psql='docker run --rm -i postgres:16 psql'`
- **ssh** and **scp** - Usually pre-installed on macOS/Linux
  - Windows: Use WSL or Git Bash
- **Local Docker deployment running** with RAG Memory containers

### System Tools (Auto-Detected by Script)

The script will check for these and report if missing:
- curl (for API calls)
- jq (for JSON parsing - auto-installs if missing)

---

## Automated Deployment Script

### When to Use the Script

**AI Assistant: Guide user to run the automated deployment script in these scenarios:**

1. **Fresh Deployment** - User wants to set up RAG Memory on Render from scratch
2. **Migration** - User has local Docker data and wants to move it to Render
3. **Both** - Script automatically detects local data and asks user which path to take

### What the Script Does Automatically

**Phase 1: Environment Detection**
- Checks if Docker is running (skip if fresh deployment)
- Detects local PostgreSQL and Neo4j containers
- Counts documents, chunks, nodes, relationships
- Asks user: migrate data or fresh deployment?

**Phase 2: Render API Authentication**
- Prompts for Render API key (or uses `RENDER_API_KEY` env var)
- Retrieves workspace/owner ID from Render API
- If multiple workspaces, lets user choose

**Phase 3: Project Creation**
- Creates Render Project via `POST /projects` API call
- Creates production environment within project
- Extracts environment ID for associating resources
- All subsequent resources will be created within this project

**Phase 4: Configuration Collection**
- Prompts user to select:
  - Region (oregon, ohio, virginia, frankfurt, singapore)
  - PostgreSQL plan (user checks https://render.com/pricing for current options)
  - Neo4j web service plan (user checks pricing for current options)
  - Neo4j password (user chooses secure password)
- **AI Assistant: Direct user to check current Render pricing for plan names**

**Phase 5: Service Creation via API**
- **PostgreSQL:**
  - Creates database via `POST /postgres` API call with `environmentId`
  - Associates database with project environment
  - Automatically enables pgvector extension
  - Retrieves External and Internal connection URLs
  - Waits for connection strings to be available (may take up to 2 minutes)
- **Neo4j:**
  - Creates Docker web service via `POST /services` API call with `environmentId`
  - Associates service with project environment
  - Configures environment variables (NEO4J_AUTH, APOC plugins, memory settings)
  - Attaches persistent disk (1GB) mounted at `/data`
  - Polls service status until "available"

**Phase 6: Data Migration (if user chose to migrate)**
- **PostgreSQL Migration:**
  - Exports local data using `docker exec pg_dump`
  - Imports to Render using `psql --single-transaction`
  - Verifies document and chunk counts match
- **Neo4j Migration:**
  - Exports local graph using APOC `apoc.export.cypher.all()`
  - Copies export file out of local container
  - Transfers to Render via SSH/SCP
  - Imports via SSH using `cypher-shell`
  - **Note:** Uses SSH workaround because Neo4j port 7687 not externally accessible on Render

**Phase 7: Display Connection Information**
- Shows project name and environment
- Shows External and Internal URLs for both databases
- Provides environment variables for MCP server
- Lists next steps

### What User Must Provide During Script Execution

The script will prompt for:
1. **Render API key** (or set `RENDER_API_KEY` env var beforehand)
2. **Region selection** (numbered list 1-5, default 1)
3. **PostgreSQL plan** - MUST use UNDERSCORES (default: `basic_256mb`)
   - PostgreSQL uses flexible plans with underscores: `basic_256mb`, `basic_1gb`, `pro_4gb`, etc.
4. **Neo4j web service plan** (default: `starter`)
   - Web services use standard plan names: `starter`, `starter_plus`, `standard`, `pro`, etc.
5. **Neo4j password** (user creates secure password for Render Neo4j)
6. **If migrating:** Confirmation at each step

**CRITICAL - Plan Names Use UNDERSCORES (not hyphens):**
- Pricing page shows: `Basic-256mb` (with hyphen, display name)
- Blueprint YAML uses: `basic-256mb` (with hyphen, Infrastructure as Code format)
- REST API requires: `basic_256mb` (with UNDERSCORE, programmatic name)
- **The deployment script uses REST API, so UNDERSCORES are required**

**Valid PostgreSQL Plans (REST API format with underscores):**
- Basic: `basic_256mb`, `basic_1gb`, `basic_4gb`
- Pro: `pro_4gb`, `pro_8gb`, `pro_16gb`, ... `pro_512gb`
- Accelerated: `accelerated_16gb`, ... `accelerated_1024gb`

**Note:** Legacy plans (`starter`, `standard`, `pro`, `pro_plus`) are NO LONGER ACCEPTED by the API for new databases. Use flexible plans only.

**Valid Web Service Plans (for Neo4j, REST API format with underscores):**
- `free`, `starter`, `starter_plus`, `standard`, `standard_plus`, `pro`, `pro_plus`, `pro_max`, `pro_ultra`

---

## Running the Deployment

### Step 1: Navigate to Project Directory

```bash
cd /path/to/rag-memory
```

### Step 2: Set API Key (Optional)

```bash
# Optional: Set API key to avoid interactive prompt
export RENDER_API_KEY="your-render-api-key-here"
```

**AI Assistant: Guide user to create API key at https://dashboard.render.com/u/settings#api-keys if they don't have one.**

### Step 3: Run Deployment Script

```bash
uv run python scripts/deploy_to_render.py
```

### Step 4: Follow Interactive Prompts

**The script will guide you through:**

1. **Detection Phase:**
   ```
   🔍 Detecting local Docker deployment...
   ✓ PostgreSQL container: Running
     → PostgreSQL: 15 documents, 342 chunks
   ✓ Neo4j container: Running
     → Neo4j: 89 nodes, 124 relationships

   📊 Local data detected!
   Do you want to migrate your local data to Render? [Y/n]:
   ```

   **AI Assistant: If user has local data, explain their options:**
   - Yes → Migrate all data to Render (recommended if data is important)
   - No → Fresh deployment (start clean, local data stays in Docker)

2. **API Authentication:**
   ```
   📋 Render API Key Required
   Create one at: https://dashboard.render.com/u/settings#api-keys

   Enter your Render API key: ********

   🔍 Fetching workspace ID...
   ✓ Using workspace: My Workspace (own-abc123)
   ```

3. **Configuration:**
   ```
   ⚙️  Deployment Configuration

   Select region:
     1. oregon
     2. ohio
     3. virginia
     4. frankfurt
     5. singapore
   Region [1]: 1

   PostgreSQL Plan:
   IMPORTANT: Use UNDERSCORES not hyphens (e.g., basic_256mb not basic-256mb)
   Valid plans: basic_256mb, basic_1gb, basic_4gb, pro_4gb, pro_8gb, ...
   Plan [basic_256mb]:

   Neo4j Web Service Plan:
   IMPORTANT: Plan names are case-sensitive (must be lowercase)
   Check current valid plan names at:
     - https://render.com/docs/blueprint-spec (search 'Web Service plan')
     - https://api-docs.render.com/reference/create-service
   Note: SSH access required for migration (starter or higher)
   Plan [starter]:

   Neo4j Configuration:
   Neo4j password (will be set on Render): ********
   ```

   **AI Assistant: Guide user on plan selection:**
   - PostgreSQL: Recommend `basic_256mb` for small deployments (UNDERSCORE not hyphen)
   - Neo4j: Recommend `starter` (includes SSH for migration)
   - **CRITICAL**: Remind user to use UNDERSCORES (basic_256mb not basic-256mb)

4. **Confirmation:**
   ```
   Deployment Summary:
     Region: oregon
     PostgreSQL: Basic-256mb
     Neo4j: Starter
     Migrate data: Yes

   Proceed with deployment? [Y/n]:
   ```

5. **Service Creation:**
   ```
   🗄️  Creating PostgreSQL database...
   ✓ PostgreSQL created: rag-memory-db
     Database ID: postgres-abc123

   🔌 Enabling pgvector extension...
   ✓ pgvector extension enabled

   🔗 Creating Neo4j service...
   ✓ Neo4j service created: rag-memory-neo4j
     Service ID: srv-xyz789
     Region: oregon

   ⏳ Waiting for service srv-xyz789 to be ready...
     Status: starting
   ✓ Service is ready
   ```

6. **Migration (if data selected):**
   ```
   📦 Exporting PostgreSQL data...
   ✓ PostgreSQL exported (2.34 MB)

   📤 Importing PostgreSQL to Render...
     → Enabling pgvector extension...
     ✓ pgvector enabled
     → Importing data (this may take a few minutes)...
   ✓ PostgreSQL imported successfully

   🔍 Verifying PostgreSQL...
     Documents: 15 (expected 15) ✓
     Chunks: 342 (expected 342) ✓

   📦 Exporting Neo4j data...
     → Running APOC export...
     → Copying export file from container...
   ✓ Neo4j exported (0.45 MB)

   🚀 Transferring data to Render via SSH...
     → Uploading to ssh.oregon.render.com...
   ✓ File transferred successfully

   📥 Importing Neo4j data via SSH...
     → Running cypher-shell import...
   ✓ Neo4j data imported successfully
   ```

   **AI Assistant: If migration takes long time (>5 minutes), this is normal for large datasets. Guide user to be patient.**

7. **Success:**
   ```
   ✅ Deployment Complete!

   PostgreSQL:
     External URL: postgresql://user:pass@hostname.render.com/ragmemory
     Database: ragmemory

   Neo4j:
     Internal URL (for MCP): neo4j://rag-memory-neo4j:7687
     Username: neo4j
     Password: <your configured password>

   Next Steps:
   1. Create MCP Server service (manual or API)
   2. Configure MCP Server environment variables:
      - DATABASE_URL=<internal-postgresql-url>
      - NEO4J_URI=neo4j://rag-memory-neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=<your password>
      - OPENAI_API_KEY=<your key>
   3. Test deployment
   4. Update Claude Desktop/Cursor MCP config
   ```

### Script Execution Time

**AI Assistant: Set user expectations for timing:**

- Fresh deployment (no data): 5-10 minutes
- Small dataset (<100 docs, <1000 nodes): 10-15 minutes
- Medium dataset (100-1000 docs, 1000-10000 nodes): 15-30 minutes
- Large dataset (>1000 docs, >10000 nodes): 30-60+ minutes

Most time spent waiting for:
- Neo4j service to become available (2-5 minutes)
- Data transfer over network
- Neo4j import processing

---

## MCP Server Setup

**Current Status:** MCP Server creation not yet automated in script. Manual setup required.

**AI Assistant: Guide user through MCP server creation by:**
1. WebFetching https://render.com/docs for current GitHub web service deployment process
2. Following the configuration below

### Configuration Requirements

- **Service Type:** Web Service
- **Name:** `rag-memory-mcp`
- **Repository:** User's RAG Memory GitHub repo
- **Branch:** `main` (or deployment branch)
- **Root Directory:** Leave empty (Dockerfile is at repo root)
- **Runtime:** Docker (auto-detected from Dockerfile)
- **Region:** Same as databases (important - reduces latency)
- **Plan:** Paid plan recommended
  - **AI Assistant:** Research current Render web service plans
  - Minimum: 512MB RAM recommended
  - Free tier may suspend after inactivity (not recommended for production)

### Environment Variables Required

**AI Assistant Instructions:**
1. Guide user to environment variables section in Render's MCP service dashboard
   - **Do NOT provide specific UI paths** - WebFetch current Render docs for how to set environment variables
2. Tell user which variables to configure (list below)
3. Tell user where to get each value
4. **NEVER ask user to provide any values to you in chat**
5. User will enter all values directly in Render's UI

**Variables user must configure:**

```bash
# PostgreSQL - Use INTERNAL URL for service-to-service
# User gets this from script output or Render PostgreSQL dashboard
DATABASE_URL=<internal-postgresql-url>

# Neo4j - Use internal connection (service-to-service)
NEO4J_URI=neo4j://rag-memory-neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<password-configured-in-script>

# OpenAI
OPENAI_API_KEY=<user-openai-api-key>

# Server configuration
PORT=8000
FASTMCP_HOST=0.0.0.0
ENVIRONMENT=production
```

**Critical:** PostgreSQL and Neo4j must use **Internal URLs** (service-to-service within Render network).

### Deployment

First build takes 5-10 minutes.

**AI Assistant: Guide user to check build logs for progress and any errors.**

---

## Verification and Testing

### Step 1: Verify Services in Render Dashboard

**AI Assistant: Guide user to check each service status:**

1. **PostgreSQL** should show "Available"
2. **Neo4j** should show "Available"
3. **MCP Server** should show "Available"

**AI Assistant: If any service shows error status:**
- Guide user to check service logs
- WebFetch Render docs for service troubleshooting
- See Troubleshooting section below

### Step 2: Test MCP Server Health

```bash
# Replace with your actual MCP server URL
curl https://rag-memory-mcp.onrender.com/health
```

Should return: `{"status": "healthy"}`

**AI Assistant: If health check fails:**
- Guide user to check MCP server logs for errors
- Verify environment variables are set correctly
- Check PostgreSQL and Neo4j services are running

### Step 3: Test with CLI (Optional)

```bash
# Set environment to use Render services
export DATABASE_URL="<external-postgresql-url>"
export NEO4J_URI="<external-neo4j-uri>"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<neo4j-password>"
export OPENAI_API_KEY="<openai-api-key>"

# Test basic operations
uv run rag collection list
uv run rag collection create test-collection "Test collection" "Testing" "Render deployment test"
uv run rag ingest text "This is a test document" test-collection
uv run rag search test-collection "test"
```

**Note:** Use External URLs for CLI testing from local machine.

### Step 4: Connect AI Agents

**Claude Code:**
```bash
claude mcp add --transport sse --scope user rag-memory https://rag-memory-mcp.onrender.com/sse
```

Restart Claude Code, then test:
```
List my RAG Memory collections
Create a collection called "render-test" for testing deployment
Search for "test" in render-test collection
```

**Claude Desktop:**

**AI Assistant: Guide user to edit Claude Desktop config file:**
- WebFetch Claude Desktop docs for config file location
- Add rag-memory MCP server configuration

Config to add:
```json
{
  "mcpServers": {
    "rag-memory": {
      "url": "https://rag-memory-mcp.onrender.com/sse"
    }
  }
}
```

**Other AI agents:** Use SSE endpoint: `https://rag-memory-mcp.onrender.com/sse`

---

## Troubleshooting

### Script Fails: "Prerequisites check failed"

**Problem:** Script reports missing tools

**Solution:**
```bash
# Check what's missing
docker --version
psql --version
ssh -V
scp -h

# Install missing tools (macOS example)
brew install postgresql  # for psql
```

**AI Assistant: Guide user to install specific missing tool for their OS.**

### Script Fails: "Failed to get workspace ID"

**Problem:** API authentication failed

**Solutions:**
1. Verify API key is correct (no extra spaces)
2. Check API key has not been revoked
3. Create new API key at https://dashboard.render.com/u/settings#api-keys

### Script Fails: "Failed to create PostgreSQL"

**Problem:** API call to create database returned error

**Common Causes:**
1. **Plan name uses hyphens** - API requires UNDERSCORES: `basic_256mb` not `basic-256mb`
2. **Legacy plan for new database** - `starter`, `standard`, `pro`, `pro_plus` NOT supported for new databases
3. **Plan name invalid** - Use valid flexible plan with underscores:
   - Basic: `basic_256mb`, `basic_1gb`, `basic_4gb`
   - Pro: `pro_4gb`, `pro_8gb`, ... `pro_512gb`
   - Accelerated: `accelerated_16gb`, ... `accelerated_1024gb`
4. **Region invalid** - Use one of: oregon, ohio, virginia, frankfurt, singapore
5. **Insufficient permissions** - Verify API key has workspace owner/admin access
6. **Billing issue** - Verify Render account has valid payment method

### Script Fails: "Failed to create Neo4j"

**Problem:** API call to create service returned error

**Common Causes:**
1. **Plan name uses hyphens or spaces** - API requires underscores: `pro_plus` not `pro plus` or `pro-plus`
2. **Plan name invalid** - Use valid plan with underscores:
   - `free`, `starter`, `starter_plus`, `standard`, `standard_plus`, `pro`, `pro_plus`, `pro_max`, `pro_ultra`
3. **Docker image not found** - Verify `neo4j:5-community` exists on Docker Hub
4. **Resource limits** - Plan may not support persistent disks
5. **Region issues** - Verify region is consistent with PostgreSQL

### Script Fails: "PostgreSQL connection failed"

**Problem:** Cannot connect to Render PostgreSQL during migration

**Solutions:**
1. **Check External URL** - Script needs External URL for connection from local machine
2. **Wait for service** - PostgreSQL may still be initializing (wait 2-3 minutes)
3. **Verify password** - Check URL has correct password embedded
4. **Test manually:**
   ```bash
   psql "<your-external-url>" -c "SELECT 1"
   ```

### Script Fails: "Neo4j connection failed"

**Problem:** Cannot connect to Render Neo4j during migration

**Solutions:**
1. **Port 7687 not externally accessible** - This is expected on Render
   - Migration uses SSH/SCP workaround (automated in script)
   - If script says "connection failed", verify Neo4j service is running first
2. **Service not ready** - Check Render dashboard, wait 3-5 minutes for startup
3. **Password mismatch** - Verify password matches what you configured in script
4. **SSH access not available** - Verify using paid plan (SSH requires paid tier)

### Script Fails: "SSH/SCP transfer failed"

**Problem:** Cannot transfer Neo4j export file via SSH

**Solutions:**
1. **SSH key authentication** - Render may require SSH key setup
   - **AI Assistant:** Guide user to set up SSH keys with Render
   - WebFetch https://render.com/docs for SSH key setup instructions
2. **Service ID incorrect** - Verify Neo4j service ID from Render dashboard
3. **Region mismatch** - SSH host must match service region
4. **Network/firewall** - Check SSH port 22 is not blocked

### Script Fails: "Import failed"

**Problem:** Data import to Render failed

**Solutions:**

**PostgreSQL:**
1. Check disk space on Render database
2. Verify pgvector extension was enabled
3. Check for schema conflicts (script includes `--clean --if-exists`)
4. Review import errors in script output

**Neo4j:**
1. Check Neo4j logs for out-of-memory errors
2. Verify persistent disk is attached
3. Check APOC plugin is loaded
4. Verify cypher-shell is accessible via SSH

### Migration: Data Counts Don't Match

**Problem:** Verification shows mismatched counts after migration

**Solutions:**
1. **Re-run migration** - Script is safe to retry
2. **Check local data didn't change** - Ensure local containers weren't modified during migration
3. **Manual verification:**
   ```bash
   # PostgreSQL
   psql "<external-url>" -c "SELECT COUNT(*) FROM source_documents; SELECT COUNT(*) FROM document_chunks;"

   # Neo4j
   docker run --rm neo4j:5-community \
     cypher-shell -a "neo4j://rag-memory-neo4j.onrender.com:7687" -u neo4j \
     "MATCH (n) RETURN count(n); MATCH ()-[r]->() RETURN count(r);"
   ```

### MCP Server: Health Check Returns 503

**Problem:** `/health` endpoint not responding or returns error

**Solutions:**
1. **Check environment variables** - All required vars must be set
2. **Verify Internal URLs** - DATABASE_URL and NEO4J_URI must use Internal URLs
3. **Check logs** - Look for database connection errors
4. **Verify databases running** - PostgreSQL and Neo4j must be "Available"
5. **Build failed** - Check build logs for Docker build errors

### General Debugging Strategy

**AI Assistant: When user encounters errors:**

1. **Read error message carefully** - Often contains specific solution
2. **Check service logs** - Most issues visible in logs
   - Guide user to Render dashboard logs section
   - WebFetch Render docs for log access if needed
3. **Verify prerequisites** - Ensure all required tools installed
4. **Test connectivity independently** - Isolate which service is failing
5. **WebFetch current documentation** - Render's UI/API may have changed
6. **Do NOT guess at solutions** - Research before advising

---

## Manual Deployment (Fallback)

**AI Assistant: Only recommend manual deployment if:**
- User explicitly requests it
- Automated script fails repeatedly despite troubleshooting
- User wants more control over specific configuration

### Manual PostgreSQL Creation

1. **AI Assistant: WebFetch https://render.com/docs** for current PostgreSQL database creation process
2. Guide user through creation with these requirements:
   - Name: `rag-memory-db`
   - Database: `ragmemory`
   - Region: User's choice (keep consistent)
   - Plan: Paid plan with backups
3. Enable pgvector:
   ```bash
   export DATABASE_URL="<external-url>"
   psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```
4. Initialize schema:
   ```bash
   cd /path/to/rag-memory
   uv run alembic upgrade head
   ```

### Manual Neo4j Creation

1. **AI Assistant: WebFetch https://render.com/docs** for current Docker web service deployment
2. Guide user through creation with these requirements:
   - Service Type: Web Service
   - Image: `neo4j:5-community`
   - Name: `rag-memory-neo4j`
   - Environment variables: `NEO4J_AUTH`, `NEO4J_PLUGINS`, memory settings
   - Persistent disk: `/data` mount, 1GB minimum
3. Wait for service to start (2-5 minutes)
4. Test connection

### Manual Migration

Use `scripts/migrate_to_render.py` for data migration even if services created manually:
- Script detects existing services
- Handles all data transfer logic
- Includes verification

**Or manually migrate:**

**PostgreSQL:**
```bash
# Export
docker exec rag-memory-postgres-local pg_dump -U raguser -d rag_memory --clean --if-exists > backup.sql

# Import
export DATABASE_URL="<external-url>"
psql "$DATABASE_URL" --single-transaction < backup.sql
```

**Neo4j:**
See `scripts/deploy_to_render.py` for Python-based Neo4j migration code.

---

## Cost Estimates

**AI Assistant: ALWAYS check https://render.com/pricing for current costs before advising user.**

### Typical Monthly Costs

| Service | Requirements | Estimated Range |
|---|---|---|
| PostgreSQL | Automated backups, 256MB-1GB | $5-15/month |
| Neo4j Docker | Persistent disk, 512MB-1GB RAM | $5-15/month |
| MCP Server | Always-on, 512MB-1GB RAM | $5-15/month |
| **Total** | Production-ready setup | **$15-45/month** |

**Plus:**
- OpenAI API: ~$1-5/month (embeddings only, not search)
- Data transfer: Usually <$1/month (included in most plans)

### Free Tier Limitations (Why Not Recommended)

- ⚠️ **Not available via API** - Automated script requires paid plans
- ⚠️ PostgreSQL: NO automated backups (data loss risk)
- ⚠️ Neo4j: NO persistent disk (data lost on redeploy)
- ⚠️ Services suspend after inactivity (slow cold starts)
- ⚠️ Neo4j: NO SSH access (migration impossible)

### Production Recommendations

**AI Assistant: Strongly recommend paid plans for:**
- Automated backups (PostgreSQL)
- Persistent storage (Neo4j)
- Always-on availability (all services)
- SSH access (Neo4j - required for migration)

**Minimum viable production setup:**
- PostgreSQL: Lowest paid tier with automated backups
- Neo4j: Lowest paid tier with persistent disk and SSH access
- MCP Server: Lowest paid tier without suspension

---

## Reference Links

### Documentation

- **Render API Documentation:** https://api-docs.render.com
- **Render Pricing:** https://render.com/pricing
- **Render General Docs:** https://render.com/docs (start here for UI-based tasks)

### RAG Memory

- **Deployment Script:** `scripts/deploy_to_render.py`
- **Migration Script:** `scripts/migrate_to_render.py` (legacy, use deploy_to_render.py instead)
- **Slash Command:** `/cloud-setup` (interactive guidance from AI assistant)

### Getting Help

- **RAG Memory:** GitHub Issues
- **Render:** Community forums and support documentation

---

## Production Checklist

Before going live:

- [ ] All services deployed via script or manual process
- [ ] All services on PAID plans (not free tier)
- [ ] PostgreSQL automated backups enabled
- [ ] Neo4j persistent disk attached and verified (mount path `/data`)
- [ ] MCP server health check returns `{"status": "healthy"}`
- [ ] Environment variables configured correctly in MCP server
- [ ] Using Internal URLs for service-to-service connections
- [ ] Database schema initialized (fresh) or migrated (existing data)
- [ ] At least one AI agent connected and tested
- [ ] Data integrity verified (create/search/list works)
- [ ] Monitoring enabled (Render dashboard)
- [ ] Cost tracking reviewed and acceptable
- [ ] Backup strategy confirmed (automated backups enabled)

---

**This guide supports the automated deployment script approach. For step-by-step interactive assistance, use the `/cloud-setup` slash command which will guide you through this documentation.**
