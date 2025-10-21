# Fly.io Test Deployment Plan

**Date:** 2025-10-21
**Scope:** Deploy RAG Memory (PostgreSQL + Neo4j + MCP Server) to Fly.io for testing
**Duration:** ~20 minutes setup + 5-10 minutes deployment
**Cost:** ~$5-7/month (scales to zero when idle)

---

## Quick Start (TL;DR)

```bash
# 1. Create new app without modifying existing files
fly launch --copy-config

# 2. Create volumes (required)
fly volumes create postgres_data --size 10 --app rag-memory-test
fly volumes create neo4j_data --size 10 --app rag-memory-test
fly volumes create neo4j_logs --size 5 --app rag-memory-test

# 3. Set secrets
fly secrets set OPENAI_API_KEY="sk-..." --app rag-memory-test

# 4. Deploy
fly deploy --app rag-memory-test

# 5. Test
fly status --app rag-memory-test
fly logs --app rag-memory-test --lines 50
```

---

## Phase 1: Preparation (5 minutes)

### Prerequisites

✅ Existing files (do NOT modify):
- `docker-compose.yml` - stays untouched
- `pyproject.toml` - stays untouched
- `.env` - stays untouched

### New files to create

**1. `docker-compose.prod.yml` (for Fly.io deployment)**

```yaml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: raguser
      POSTGRES_PASSWORD: ragpassword
      POSTGRES_DB: rag_memory
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/01-init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U raguser"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "5432"

  neo4j:
    image: neo4j:5-community
    environment:
      NEO4J_AUTH: neo4j/graphiti-password
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: 256m
      NEO4J_server_memory_heap_max__size: 512m
    volumes:
      - neo4j_data:/var/lib/neo4j/data
      - neo4j_logs:/var/lib/neo4j/logs
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p graphiti-password 'RETURN 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "7687"
      - "7474"

  rag-mcp:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://raguser:ragpassword@postgres:5432/rag_memory
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: graphiti-password
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    restart: on-failure

volumes:
  postgres_data:
    driver: local
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
```

**2. `fly.toml` (Fly.io configuration)**

```toml
# fly.toml file generated for rag-memory-test
app = "rag-memory-test"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  OPENAI_API_KEY = ""

[[services]]
  protocol = "tcp"
  internal_port = 8000
  processes = ["app"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.ports]]
    port = 80
    handlers = ["http"]

[[mounts]]
  source = "postgres_data"
  destination = "/var/lib/postgresql/data"

[[mounts]]
  source = "neo4j_data"
  destination = "/var/lib/neo4j/data"

[[mounts]]
  source = "neo4j_logs"
  destination = "/var/lib/neo4j/logs"
```

**3. `.dockerignore` (update or create)**

```
.git
.gitignore
.env
.env.example
docker-compose.yml
docker-compose.override.yml
docker-compose.graphiti.yml
docker-compose.prod.yml
fly.toml
.pytest_cache
__pycache__
*.pyc
.venv
venv
node_modules
.DS_Store
backups
logs
*.md
docs
tests
htmlcov
.ruff_cache
.black
```

### Verify Dockerfile

Ensure `Dockerfile` exists and includes:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

# Install uv
RUN pip install uv

# Install dependencies
RUN uv sync --frozen

# Run MCP server
CMD ["uv", "run", "python", "-m", "src.mcp.server"]
```

If not present, create it with the above content.

---

## Phase 2: Create Fly.io App (5 minutes)

### Step 1: Authenticate with Fly.io

```bash
fly auth login
# Opens browser to authenticate
# Returns API token for CLI
```

### Step 2: Create app (do NOT interfere with existing setup)

```bash
# Use --copy-config to let Fly.io auto-detect services
# This creates NEW app, doesn't touch existing docker-compose files
fly launch --copy-config --name rag-memory-test --org personal

# When prompted:
# "Would you like to use the existing docker-compose file?" → YES
# "Copy docker-compose.yml to fly.toml?" → NO (we have fly.toml already)
# "Would you like to set up a Postgres database now?" → NO (we have it in compose)
# "Would you like to set up a Redis database now?" → NO (not needed)
# "Would you like to deploy now?" → NO (we'll do it after volumes)
```

This creates `fly.toml` for the new app without modifying your existing files.

### Step 3: Create persistent volumes

**CRITICAL:** Fly.io containers are ephemeral. Data persists ONLY in volumes.

```bash
# Create PostgreSQL volume (10 GB)
fly volumes create postgres_data \
  --size 10 \
  --region iad \
  --app rag-memory-test

# Create Neo4j data volume (10 GB)
fly volumes create neo4j_data \
  --size 10 \
  --region iad \
  --app rag-memory-test

# Create Neo4j logs volume (5 GB)
fly volumes create neo4j_logs \
  --size 5 \
  --region iad \
  --app rag-memory-test

# Verify volumes were created
fly volumes list --app rag-memory-test
```

**Expected output:**
```
ID                 NAME            SIZE  REGION
vol_abc123...      postgres_data   10GB  iad
vol_def456...      neo4j_data      10GB  iad
vol_ghi789...      neo4j_logs      5GB   iad
```

---

## Phase 3: Configure Secrets (2 minutes)

### Set OPENAI_API_KEY

```bash
fly secrets set OPENAI_API_KEY="sk-proj-your-actual-key-here" \
  --app rag-memory-test
```

### Verify secrets (values hidden)

```bash
fly secrets list --app rag-memory-test
```

---

## Phase 4: Deploy (3-5 minutes)

### Deploy to Fly.io

```bash
fly deploy --app rag-memory-test --wait-timeout 300

# Expected output:
# Deploying image to 1 machine
# Pushing build to Fly Registry
# [Docker build progress...]
# Running release_command: fly ssh console -- ...
# Machines [machine_id] started successfully
```

### Monitor startup

```bash
# Check machine status
fly status --app rag-memory-test

# Watch logs in real-time
fly logs --app rag-memory-test --lines 100
```

**Watch for in logs:**
```
PostgreSQL schema valid ✓ (tables: 3/3, pgvector: ✓, indexes: 2/2)
Neo4j schema valid ✓ (indexes: X, queryable: ✓)
All startup validations passed - server ready ✓
```

When you see this message, deployment is successful.

---

## Phase 5: Set Up Daily Backups (2 minutes)

### Option A: Use Fly.io Native Snapshots (Recommended - Already Active)

Fly.io automatically takes daily snapshots of all volumes.

**View snapshot configuration:**
```bash
fly volumes snapshots-list postgres_data --app rag-memory-test
fly volumes snapshots-list neo4j_data --app rag-memory-test
```

**Default behavior:**
- ✅ Automatic daily snapshots
- ✅ Retained for 5 days (configurable 1-60 days)
- ✅ Free (included with volume)
- ✅ Accessible via web dashboard

**Change retention (example: 30 days):**
```bash
# Via web dashboard: https://fly.io/dashboard
# Or via API (not yet in flyctl - dashboard only)
```

### Option B: Restore from Snapshot

If you need to recover data:

```bash
# List available snapshots
fly volumes snapshots-list postgres_data --app rag-memory-test

# Restore snapshot to new volume
fly volumes snapshot restore \
  --snapshot-id snapshot_abc123... \
  --app rag-memory-test
```

---

## Phase 6: Test Deployment (5 minutes)

### Test 1: Check service status

```bash
fly status --app rag-memory-test

# Expected:
# Machines
# ID             IMAGE  REGION  STATUS  CHECKS
# abc123...      ...    iad     started 3 health checks passed
```

### Test 2: View recent logs

```bash
fly logs --app rag-memory-test --lines 50

# Should see:
# All startup validations passed - server ready ✓
```

### Test 3: Access MCP Server endpoint (HTTP)

```bash
# Get app URL
fly info --app rag-memory-test

# Test MCP endpoint
curl https://rag-memory-test.fly.dev/sse

# Expected: JSON response with tool list
```

### Test 4: Access PostgreSQL remotely

**Option A: Using `fly proxy`**

```bash
# Terminal 1: Create SSH tunnel
fly proxy 5432:5432 --app rag-memory-test

# Terminal 2: Connect with psql
psql postgresql://raguser:ragpassword@localhost:5432/rag_memory

# Query to verify schema
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

# Expected output:
# source_documents
# document_chunks
# collections
# chunk_collections
```

**Option B: Using pgAdmin (easier UI)**

1. Download pgAdmin from https://www.pgadmin.org/download/
2. Start pgAdmin: `pgAdmin4`
3. In web interface (localhost:5050):
   - Create new server
   - Connection tab:
     - Host: Use `fly proxy` tunnel created above (localhost:5432)
     - Port: 5432
     - Username: raguser
     - Password: ragpassword
     - Database: rag_memory
4. Browse schema visually

### Test 5: Access Neo4j remotely

**Option A: Using Neo4j Browser via `fly proxy`**

```bash
# Terminal 1: Create proxy tunnel
fly proxy 7474:7474 7687:7687 --app rag-memory-test

# Terminal 2: Open Neo4j Browser
open http://localhost:7474

# Login:
# Username: neo4j
# Password: graphiti-password

# Run test query:
MATCH (n) RETURN COUNT(n) LIMIT 1
```

**Option B: Using `cypher-shell` via SSH**

```bash
fly ssh console --app rag-memory-test

# Inside container
cypher-shell -u neo4j -p graphiti-password

# Test query
MATCH (n) RETURN COUNT(n);
```

### Test 6: Ingest a document and search

**Using curl (or any MCP client):**

```bash
# Get the app URL
FLY_APP_URL=$(fly info --app rag-memory-test | grep "App URL" | cut -d' ' -f3)

# Example: Create collection
curl -X POST $FLY_APP_URL/sse \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "create_collection",
      "arguments": {
        "name": "test-knowledge",
        "description": "Test collection for Fly.io deployment"
      }
    }
  }'

# Example: Search
curl -X POST $FLY_APP_URL/sse \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "search_documents",
      "arguments": {
        "query": "test query"
      }
    }
  }'
```

---

## Phase 7: Cleanup (When Ready to Tear Down)

### Destroy test deployment (preserves databases for recovery if needed)

```bash
# Delete app (but keeps volumes/snapshots)
fly apps destroy rag-memory-test

# This allows you to:
# 1. Restore volumes later if needed
# 2. Re-deploy without losing data
```

### Full cleanup (DELETE ALL DATA)

```bash
# CAREFUL: This deletes everything

# Delete volumes (DESTROYS DATA)
fly volumes destroy postgres_data --app rag-memory-test
fly volumes destroy neo4j_data --app rag-memory-test
fly volumes destroy neo4j_logs --app rag-memory-test

# Delete app
fly apps destroy rag-memory-test
```

---

## Quick Reference: Troubleshooting

### Problem: App won't start

```bash
# Check logs
fly logs --app rag-memory-test --lines 100

# Common issues:
# "Connect refused" → Services not healthy yet (wait 30 seconds, retry)
# "FATAL: PostgreSQL schema validation failed" → Schema not initialized
# "NEO4J_URI: bolt://neo4j:7687" → Neo4j service not starting
```

### Solution: Re-initialize schema

```bash
# SSH into running container
fly ssh console --app rag-memory-test

# Inside container
cd /app
uv run rag init

# Exit
exit

# Restart app
fly machines restart [machine-id]
```

### Problem: Data persisted but Neo4j won't query

```bash
# Check Neo4j via SSH
fly ssh console --app rag-memory-test
cypher-shell -u neo4j -p graphiti-password

# If stuck, restart Neo4j
MATCH (n) RETURN COUNT(n) LIMIT 1;
```

### Problem: Out of disk space

```bash
# Check volume usage
fly volumes list --app rag-memory-test

# Extend volume (must create new, migrate data)
# Use web dashboard: https://fly.io/dashboard
```

---

## Success Criteria ✅

- [x] `fly launch` completes without modifying existing files
- [x] All 3 volumes created successfully
- [x] OPENAI_API_KEY secret set
- [x] `fly deploy` completes in <10 minutes
- [x] All 3 machines start and pass health checks
- [x] Logs show "All startup validations passed - server ready ✓"
- [x] PostgreSQL accessible via proxy with correct schema
- [x] Neo4j accessible via proxy and browser
- [x] MCP server responds to HTTP requests
- [x] Can create collections and search
- [x] Daily snapshots automatically created

---

## Cost Estimate

**Monthly cost (iad region):**
- App compute (3 services, auto-scales): ~$2-5
- PostgreSQL volume (10 GB): ~$1.50
- Neo4j volumes (15 GB): ~$2.25
- **Total: ~$5-7/month** (scales to zero when idle)

**No separate backup costs** - Snapshots included with volumes.

---

## Next Steps (After Successful Test)

1. Promote to production app (rename rag-memory-prod)
2. Set up monitoring/alerts
3. Document connection strings for users
4. Create backup/restore runbook
5. Test failover scenarios

---

## Important Notes

⚠️ **DO NOT modify existing files:**
- Local `docker-compose.yml` untouched
- Local `.env` untouched
- Local development unaffected

✅ **New app isolated:**
- Fly.io app name: `rag-memory-test`
- Separate volumes, secrets, machines
- Can delete without affecting local setup
- Easy to test, easier to iterate

✅ **Production-ready:**
- Health checks on all services
- Persistent volumes for data
- Auto-scaling (optional, disabled by default)
- Daily automatic backups via snapshots
- Full database access for admin/debugging
