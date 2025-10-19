# Multi-Environment Infrastructure Guide

## Overview

RAG Memory now supports **three distinct environments** with complete isolation and safety protection:

1. **TEST** - Ephemeral test servers for pytest (docker-compose.test.yml)
2. **DEVELOPMENT** - Persistent dev servers for manual exploration (docker-compose.dev.yml)
3. **SUPABASE** - Remote production database for production-level testing (.env.supabase)

## Quick Start

### Start Development Environment

```bash
# Start persistent dev servers (Postgres + Neo4j)
docker-compose -f docker-compose.dev.yml up -d

# Verify servers are healthy
docker-compose -f docker-compose.dev.yml ps

# Load dev environment variables
source .env.dev

# Test the connection
uv run rag status
```

### Run Tests (Isolated)

```bash
# Start test servers (clean slate each time)
docker-compose -f docker-compose.test.yml up -d

# Verify test servers are healthy
docker-compose -f docker-compose.test.yml ps

# Run all tests (conftest.py auto-loads .env.test)
uv run pytest tests/

# After testing, clean up (optional but recommended)
docker-compose -f docker-compose.test.yml down -v
```

### Access Development Servers

```bash
# PostgreSQL Development
psql postgresql://raguser:ragpassword@localhost:54320/rag_memory_dev

# Neo4j Browser Development
open http://localhost:7474
# Username: neo4j
# Password: dev-password

# PostgreSQL Test
psql postgresql://raguser:ragpassword@localhost:54323/rag_memory_test

# Neo4j Browser Test
open http://localhost:7476
# Username: neo4j
# Password: test-password
```

## Environment Configuration

### Files

| File | Purpose | Auto-Loaded | For |
|------|---------|-------------|-----|
| `.env.dev` | Development config | Manual | Manual CLI/exploration |
| `.env.test` | Test config | By pytest conftest.py | Automated pytest |
| `.env.supabase` | Production config | Manual only | Explicit production testing |
| `.env.example` | Template | Reference | Documentation |

### Loading Environments

**Development (Manual):**
```bash
source .env.dev
uv run rag search "query"
```

**Testing (Automatic):**
```bash
# conftest.py auto-loads .env.test
uv run pytest tests/
```

**Production/Supabase (Explicit):**
```bash
# ONLY when you explicitly want production data testing
source .env.supabase
uv run rag search "query"
```

## Server Details

### Development Environment (docker-compose.dev.yml)

**Purpose:** Manual testing, exploration, and development

**Persistence:** ✅ Data persists across container restarts

**Ports:**
- PostgreSQL: `localhost:54320`
- Neo4j HTTP: `http://localhost:7474`
- Neo4j Bolt: `localhost:7687`

**Database Names:**
- PostgreSQL: `rag_memory_dev`
- Neo4j: Default graph

**Credentials:**
- Postgres: `raguser / ragpassword`
- Neo4j: `neo4j / dev-password`

**Commands:**
```bash
# Start
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f postgres-dev

# Stop (data persists)
docker-compose -f docker-compose.dev.yml stop

# Remove (data deleted)
docker-compose -f docker-compose.dev.yml down

# Hard reset (delete all data and volumes)
docker-compose -f docker-compose.dev.yml down -v
```

### Test Environment (docker-compose.test.yml)

**Purpose:** Automated pytest tests with guaranteed isolation

**Persistence:** ❌ Data is EPHEMERAL (not persisted)

**Ports (completely isolated from all other environments):**
- PostgreSQL: `localhost:54323`
- Neo4j HTTP: `http://localhost:7476`
- Neo4j Bolt: `localhost:7689`

**Database Names:**
- PostgreSQL: `rag_memory_test`
- Neo4j: Default graph

**Credentials:**
- Postgres: `raguser / ragpassword`
- Neo4j: `neo4j / test-password`

**Commands:**
```bash
# Start test servers
docker-compose -f docker-compose.test.yml up -d

# Run tests (conftest.py enforces test environment)
uv run pytest tests/ -v

# Stop (keeps volumes, allows inspection)
docker-compose -f docker-compose.test.yml down

# Hard reset (deletes all test data and volumes)
docker-compose -f docker-compose.test.yml down -v

# Inspect test data before cleanup
psql postgresql://raguser:ragpassword@localhost:54321/rag_memory_test
open http://localhost:7475  # Neo4j Browser
```

## Production Safety Features

### 1. Test Server Isolation

Tests **NEVER** touch dev or production servers:

```
Pytest runs
   ↓
conftest.py loads .env.test
   ↓
DATABASE_URL = postgresql://...localhost:54321... (test)
NEO4J_URI = bolt://...7688... (test)
   ↓
Tests use ephemeral test servers
   ↓
Development/production servers completely untouched
```

### 2. Production Detection & Prevention

conftest.py includes anti-Supabase protection:

```python
# FATAL if you try to run tests against Supabase
if "supabase.com" in database_url:
    print("❌ FATAL: Tests configured to run against Supabase!")
    sys.exit(1)
```

**Result:** Cannot accidentally run pytest against production

### 3. Environment Verification

On test startup, conftest.py logs:

```
✅ Loaded .env.test for test environment
ℹ️  Test Environment: test
ℹ️  Postgres: localhost:54321/rag_memory_test
ℹ️  Neo4j: bolt://localhost:7688
```

If something is wrong:

```
❌ FATAL: Tests configured to run against Supabase production database!
```

## Switching Environments

### From Dev to Test

```bash
# Stop dev servers (optional, keeping data)
docker-compose -f docker-compose.dev.yml down

# Start test servers
docker-compose -f docker-compose.test.yml up -d

# Run tests (conftest.py auto-loads .env.test)
uv run pytest tests/

# After testing, cleanup
docker-compose -f docker-compose.test.yml down -v
```

### From Dev to Production/Supabase

```bash
# When you explicitly want to test against production data:

# 1. VERIFY you're switching intentionally
# 2. Load Supabase config
source .env.supabase

# 3. Run development commands (NOT tests)
uv run rag search "query"

# 4. IMPORTANT: Switch back to dev when done
source .env.dev
```

### From Production Back to Dev

```bash
# Always switch back after production testing
source .env.dev

# Verify you're back
uv run rag status
# Should say: Connected to rag_memory_dev
```

## Database Cleanup

### Automatic Test Cleanup

Tests use database/graph cleanup patterns:

**PostgreSQL:**
```python
# Each test cleanup:
DELETE FROM document_chunks WHERE source_document_id IN (test_ids)
DELETE FROM source_documents WHERE id IN (test_ids)
DELETE FROM chunk_collections WHERE chunk_id IN (test_ids)
```

**Neo4j:**
```python
# After each test:
await graphiti.driver.execute_query("MATCH (e:Episodic) WHERE e.name STARTS WITH 'doc_' DELETE e")
```

### Manual Cleanup

**Delete test data completely:**
```bash
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

**Keep test data for inspection:**
```bash
# Stop containers but keep volumes
docker-compose -f docker-compose.test.yml down

# Inspect
psql postgresql://raguser:ragpassword@localhost:54321/rag_memory_test

# Then cleanup
docker-compose -f docker-compose.test.yml down -v
```

**Development cleanup (manual control):**
```bash
# You decide when to clean dev data
# Option 1: Keep all data indefinitely
docker-compose -f docker-compose.dev.yml stop

# Option 2: Hard reset when ready
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
```

## Troubleshooting

### "Connection refused" on port 54321

**Problem:** Test servers not running

**Solution:**
```bash
docker-compose -f docker-compose.test.yml up -d
docker-compose -f docker-compose.test.yml logs
```

### "FATAL: Tests configured to run against Supabase"

**Problem:** Trying to run tests with Supabase DATABASE_URL

**Solution:**
```bash
# Ensure test servers are running
docker-compose -f docker-compose.test.yml up -d

# Unload any custom environment
unset DATABASE_URL
unset NEO4J_URI

# Run tests (conftest.py will auto-load .env.test)
uv run pytest tests/
```

### Test data mixed with dev data

**Problem:** Ran tests with dev servers instead of test servers

**Solution:**
1. Start test servers: `docker-compose -f docker-compose.test.yml up -d`
2. Verify pytest uses test environment: `uv run pytest tests/ -v` (watch output)
3. Clean test servers: `docker-compose -f docker-compose.test.yml down -v`
4. Verify dev data is intact: `psql postgresql://raguser:ragpassword@localhost:54320/rag_memory_dev`

### Production data concern

**Problem:** Worried about accidentally modifying Supabase data

**Safety measures:**
1. ✅ Never run `pytest` with Supabase URL (conftest.py blocks it)
2. ✅ Supabase-specific credentials are in `.env.supabase` (not auto-loaded)
3. ✅ Must explicitly `source .env.supabase` to use production
4. ✅ Test servers on separate ports (54321, 7688) prevent accidental connection
5. ✅ Production database has its own backups and recovery

**Additional protection:**
```bash
# To be extra safe, never source .env.supabase in your shell
# Instead, use explicit commands:
OPENAI_API_KEY=sk-xxx source .env.supabase && uv run rag search "query"

# Then manually verify you're back in dev:
source .env.dev
uv run rag status
```

## Monitoring

### Check All Servers

```bash
# Development
docker-compose -f docker-compose.dev.yml ps

# Test
docker-compose -f docker-compose.test.yml ps

# Check ports are available
lsof -i :54320 :54321 :7474 :7475 :7687 :7688
```

### View Logs

```bash
# Development Postgres
docker-compose -f docker-compose.dev.yml logs postgres-dev

# Test Postgres
docker-compose -f docker-compose.test.yml logs postgres-test

# Development Neo4j
docker-compose -f docker-compose.dev.yml logs neo4j-dev

# Test Neo4j
docker-compose -f docker-compose.test.yml logs neo4j-test
```

### Health Checks

```bash
# PostgreSQL health
pg_isready -h localhost -p 54320 -U raguser  # Dev
pg_isready -h localhost -p 54323 -U raguser  # Test

# Neo4j health
curl http://localhost:7474/browser/           # Dev browser
curl http://localhost:7476/browser/           # Test browser
```

## Environment Variables Reference

### All Variables

| Variable | Dev | Test | Supabase |
|----------|-----|------|----------|
| DATABASE_URL | localhost:54320 | localhost:54323 | supabase.com |
| NEO4J_URI | localhost:7687 | localhost:7689 | localhost:7687 |
| POSTGRES_DB | rag_memory_dev | rag_memory_test | postgres (Supabase) |
| NEO4J_PASSWORD | dev-password | test-password | same as dev |
| ENV_NAME | development | test | supabase-dev |

### Priority Loading

pytest conftest.py loads in this order:

1. `.env.test` (if exists) ← PRIMARY for tests
2. `.env.dev` (fallback if no .env.test)
3. `~/.rag-memory-env` (overlay for credentials)
4. Shell environment variables (final override)

## Maintenance

### Daily Development

```bash
# Start day
source .env.dev
docker-compose -f docker-compose.dev.yml up -d
uv run rag status

# During day
uv run rag search "queries"
# ... manual testing ...

# End of day (optional)
docker-compose -f docker-compose.dev.yml stop
# Data persists until you manually clean it
```

### Running Tests

```bash
# Start test infrastructure
docker-compose -f docker-compose.test.yml up -d

# Run tests (auto-loads .env.test)
uv run pytest tests/ -v

# Cleanup
docker-compose -f docker-compose.test.yml down -v
```

### Full System Restart

```bash
# Stop everything
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.test.yml down

# Start fresh with dev
docker-compose -f docker-compose.dev.yml up -d

# Verify connection
source .env.dev
uv run rag status
```

## Files

- `docker-compose.dev.yml` - Development servers
- `docker-compose.test.yml` - Test servers
- `.env.dev` - Development configuration
- `.env.test` - Test configuration
- `.env.supabase` - Production configuration
- `tests/conftest.py` - pytest configuration with safety guards
- `src/core/config_loader.py` - Environment variable loading

---

**Last updated:** 2025-10-19
**Author:** Claude Code
**Status:** ✅ Ready for integration test development
