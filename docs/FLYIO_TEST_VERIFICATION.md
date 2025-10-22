# Fly.io Test Deployment - Verification Guide

**App Name:** rag-memory-test (completely separate from rag-memory-mcp production)
**Status:** Ready to test after deployment

---

## Verification Checklist

Run these commands after deployment to verify everything works.

### 1. Check App Status

```bash
./scripts/deploy-fly-test.sh status
```

**Expected output:**
```
Machines
ID             IMAGE                              REGION  STATUS  CHECKS
abc123...      sha256:xyz...  iad     started 3 health checks passed
```

✅ **Pass:** Status is "started" and health checks passed
❌ **Fail:** Status is "pending" or health checks failing

---

### 2. Check Startup Logs

```bash
./scripts/deploy-fly-test.sh logs
```

**Look for this critical message:**
```
All startup validations passed - server ready ✓
```

Also check for:
```
PostgreSQL schema valid ✓ (tables: 3/3, pgvector: ✓, indexes: 2/2)
Neo4j schema valid ✓ (indexes: X, queryable: ✓)
```

✅ **Pass:** See all three "✓" messages
❌ **Fail:** See "FATAL" or errors about schema validation

---

### 3. Test PostgreSQL Connection

**Terminal 1: Create SSH tunnel to PostgreSQL**

```bash
flyctl proxy 5432:5432 --app rag-memory-test
```

This creates a local tunnel: `localhost:5432` → Fly.io PostgreSQL

**Terminal 2: Connect with psql**

```bash
psql postgresql://raguser:ragpassword@localhost:5432/rag_memory
```

**Inside psql, run:**

```sql
-- Check tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

**Expected output:**
```
         table_name
--------------------------
 chunk_collections
 collections
 document_chunks
 source_documents
```

**Check pgvector extension:**

```sql
-- Verify pgvector is loaded
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

**Expected output:**
```
 extname | extversion
---------+------------
 vector  | 0.x.x
```

**Check HNSW indexes:**

```sql
-- Verify HNSW indexes exist
SELECT indexname, indexdef
FROM pg_indexes
WHERE indexdef ILIKE '%hnsw%';
```

**Expected output:**
```
             indexname             |                              indexdef
------------------------------------+--------------------------------------------------------------------
 document_chunks_embedding_idx      | CREATE INDEX document_chunks_embedding_idx ON document_chunks USING hnsw...
```

**Exit psql:**

```sql
\q
```

✅ **Pass:** All 4 tables visible, pgvector loaded, HNSW indexes present
❌ **Fail:** Missing tables, pgvector not found, or indexes missing

---

### 4. Test Neo4j Connection

**Terminal 1: Create SSH tunnel to Neo4j**

```bash
flyctl proxy 7474:7474 7687:7687 --app rag-memory-test
```

This creates:
- `localhost:7474` → Neo4j Browser (web UI)
- `localhost:7687` → Neo4j Bolt protocol (driver access)

**Option A: Use Neo4j Browser (recommended)**

1. Open browser: http://localhost:7474
2. Wait for "Connect to a database" screen
3. Enter connection details:
   - Connection URL: bolt://localhost:7687
   - Username: neo4j
   - Password: graphiti-password
4. Click "Connect"

**In Neo4j Browser, run:**

```cypher
MATCH (n) RETURN COUNT(n) LIMIT 1;
```

**Expected output:**
```
0  (or any number - empty graph is OK)
```

**Check indexes:**

```cypher
SHOW INDEXES;
```

**Expected output:** Multiple indexes including Graphiti-specific ones

**Option B: Use cypher-shell via SSH**

```bash
./scripts/deploy-fly-test.sh shell
```

Inside container:

```bash
cypher-shell -u neo4j -p graphiti-password

# Test query
MATCH (n) RETURN COUNT(n);

# Check indexes
SHOW INDEXES;

# Exit
:exit
```

✅ **Pass:** Can connect, query returns result, indexes visible
❌ **Fail:** Connection refused, authentication error, or no indexes

---

### 5. Test MCP Server HTTP Endpoint

Get the app URL:

```bash
flyctl info --app rag-memory-test | grep "App URL"
```

Example output: `rag-memory-test.fly.dev`

**Test MCP server is responding:**

```bash
curl https://rag-memory-test.fly.dev/sse
```

**Expected output:** JSON response with tool list (may be long)

✅ **Pass:** HTTP 200 with JSON response
❌ **Fail:** HTTP 404, 500, or connection timeout

---

### 6. Test MCP Tool - Create Collection

This tests that the MCP server can actually do operations.

```bash
APP_URL="https://rag-memory-test.fly.dev"

# Create test collection
curl -X POST "$APP_URL/sse" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_collection",
      "arguments": {
        "name": "fly-test-collection",
        "description": "Test collection for Fly.io deployment verification"
      }
    }
  }'
```

**Expected output:** Success response (may be verbose)

✅ **Pass:** Response contains collection name and description
❌ **Fail:** Error response or timeout

---

### 7. Test MCP Tool - List Collections

```bash
APP_URL="https://rag-memory-test.fly.dev"

# List all collections
curl -X POST "$APP_URL/sse" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "list_collections",
      "arguments": {}
    }
  }'
```

**Expected output:** Collection list including "fly-test-collection"

✅ **Pass:** See your collection in the list
❌ **Fail:** Empty list or error

---

### 8. Test MCP Tool - Ingest Text

```bash
APP_URL="https://rag-memory-test.fly.dev"

# Ingest sample text
curl -X POST "$APP_URL/sse" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "ingest_text",
      "arguments": {
        "content": "PostgreSQL is a powerful open-source relational database. It supports advanced features like JSON, arrays, and custom types. pgvector extension adds vector similarity search capabilities.",
        "collection_name": "fly-test-collection",
        "document_title": "PostgreSQL Overview"
      }
    }
  }'
```

**Expected output:** Document ID and chunk count

✅ **Pass:** See source_document_id and num_chunks in response
❌ **Fail:** Error or empty response

---

### 9. Test MCP Tool - Search Documents

```bash
APP_URL="https://rag-memory-test.fly.dev"

# Search the ingested content
curl -X POST "$APP_URL/sse" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "search_documents",
      "arguments": {
        "query": "vector similarity search",
        "collection_name": "fly-test-collection",
        "limit": 5
      }
    }
  }'
```

**Expected output:** Search results with similarity scores

✅ **Pass:** See search results with similarity scores (0.5-0.9+)
❌ **Fail:** Empty results or error

---

### 10. Verify Fly.io Daily Backups

1. Go to Fly.io dashboard: https://fly.io/dashboard
2. Select your organization → rag-memory-test app
3. Click "Volumes" section
4. For each volume (postgres_data, neo4j_data, neo4j_logs):
   - Click volume name
   - Look for "Snapshots" section
   - Should show "Daily snapshots enabled" or similar

✅ **Pass:** All volumes have snapshots section visible
❌ **Fail:** No snapshots section or disabled

---

## Summary - What You're Testing

| Component | Test | Status |
|-----------|------|--------|
| PostgreSQL Connection | pg_isready via SSH tunnel | ✅/❌ |
| PostgreSQL Schema | Tables, pgvector, HNSW indexes | ✅/❌ |
| Neo4j Connection | Cypher query via SSH tunnel | ✅/❌ |
| Neo4j Schema | Indexes, graph queryable | ✅/❌ |
| MCP Server | HTTP endpoint responds | ✅/❌ |
| MCP Tools | Create, list, search operations | ✅/❌ |
| Daily Backups | Fly.io snapshots enabled | ✅/❌ |

**Success:** All checks pass ✅

---

## Troubleshooting

### Problem: "Cannot connect to postgres"

```bash
# Check if tunnel is still active
flyctl proxy 5432:5432 --app rag-memory-test

# In different terminal, try psql again
psql postgresql://raguser:ragpassword@localhost:5432/rag_memory
```

### Problem: "Neo4j authentication failed"

```bash
# Verify password is correct (should be: graphiti-password)
# Check Neo4j logs
./scripts/deploy-fly-test.sh logs | grep -i neo4j

# Try direct SSH
./scripts/deploy-fly-test.sh shell
cypher-shell -u neo4j -p graphiti-password
```

### Problem: "FATAL: PostgreSQL schema validation failed"

Schema wasn't initialized. Check if init.sql ran:

```bash
./scripts/deploy-fly-test.sh shell
psql postgresql://raguser:ragpassword@postgres:5432/rag_memory

# Inside psql:
\dt

# Should list tables, if empty then init failed
```

### Problem: MCP server timeout

The app may still be starting. Wait 30 seconds and try again:

```bash
./scripts/deploy-fly-test.sh status
# If health checks still pending, wait

./scripts/deploy-fly-test.sh logs
# Should show "ready ✓" when complete
```

### Problem: Everything works locally but deployment fails

Verify that docker-compose.prod.yml hasn't interfered with existing setup:

```bash
# Check that your original docker-compose.yml is untouched
git diff docker-compose.yml

# Should show no changes (or only whitespace)
```

---

## Clean Shutdown (When Testing Complete)

### Option 1: Keep app for later (preserve data)

```bash
# App will scale to zero automatically after idle period
# Data persists in volumes
# No ongoing costs (scales to zero)

# To check status later:
./scripts/deploy-fly-test.sh status
```

### Option 2: Delete app (free up resources)

```bash
# Delete app only (volumes remain for recovery)
./scripts/deploy-fly-test.sh destroy
```

### Option 3: Full cleanup (DELETE ALL DATA)

```bash
# SSH into Fly.io
./scripts/deploy-fly-test.sh shell

# Exit
exit

# Then destroy volumes from dashboard:
# https://fly.io/dashboard → rag-memory-test → Volumes → Delete each volume
```

---

## Success Indicator

When all 10 verification tests pass ✅, you have successfully:

1. ✅ Deployed RAG Memory to Fly.io in complete isolation
2. ✅ Both PostgreSQL and Neo4j are running and initialized
3. ✅ MCP server is operational with all tools functional
4. ✅ Full database access available via SSH tunnels
5. ✅ Daily backups automatically created by Fly.io
6. ✅ No interference with existing rag-memory-mcp production app

**You're ready to use this for testing, development, or as a base for production!**
