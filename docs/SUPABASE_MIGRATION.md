# Supabase Migration Guide

Complete guide to migrate RAG Memory from Docker Compose (local) to Supabase (cloud).

**Last updated:** 2025-10-13

---

## Table of Contents

1. [Why Supabase?](#why-supabase)
2. [Prerequisites](#prerequisites)
3. [Phase 1: Create Supabase Project](#phase-1-create-supabase-project)
4. [Phase 2: Set Up Schema](#phase-2-set-up-schema)
5. [Phase 3: Multi-Environment Usage](#phase-3-multi-environment-usage)
6. [Phase 4: Future Migrations](#phase-4-future-migrations)
7. [Phase 5: MCP Server Configuration](#phase-5-mcp-server-configuration)
8. [Phase 6: Data Migration (Optional)](#phase-6-data-migration-optional)

---

## Why Supabase?

**Benefits:**
- Access anywhere (not localhost-only)
- Zero maintenance (automated backups, updates)
- Free tier: 500MB database
- pgvector built-in
- Simple migration (just update connection string)

**Cost:**
- Personal use: **FREE** (500MB limit)
- Pro plan: **$25/month** (8GB, automated backups)

---

## Prerequisites

- Supabase account (sign up at https://supabase.com - free)
- `psql` CLI installed: `brew install postgresql` (macOS)
- Docker running with your current RAG Memory database

---

## Phase 1: Create Supabase Project

1. Go to https://supabase.com and sign up
2. Click "New Project"
   - Project name: `rag-memory`
   - Database password: **SAVE THIS** (use password manager)
   - Region: Choose closest to you (e.g., `us-east-1`)
   - Pricing plan: **Free**
3. Wait ~2 minutes for project creation

---

## Phase 2: Set Up Schema

**See [SUPABASE_SCHEMA_SETUP.md](./SUPABASE_SCHEMA_SETUP.md) for complete instructions.**

Quick version:

```bash
# 1. Get Session Pooler connection string from Supabase Dashboard
export SUPABASE_DB_URL='postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres'

# 2. Enable pgvector
psql "$SUPABASE_DB_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 3. Run migrations
export DATABASE_URL="$SUPABASE_DB_URL"
uv run alembic upgrade head

# 4. Verify
psql "$SUPABASE_DB_URL" -c "\dt"
```

Expected: 5 tables created (`collections`, `source_documents`, `document_chunks`, `chunk_collections`, `alembic_version`)

---

## Phase 3: Multi-Environment Usage

You can run both Docker (local) and Supabase (remote) and switch between them.

### Switching Environments

**Docker (Local):**
```bash
# Edit ~/.rag-memory-env or .env
DATABASE_URL=postgresql://raguser:ragpassword@localhost:54320/rag_memory

# Use it
uv run rag status
uv run rag search "query"
```

**Supabase (Remote):**
```bash
# Edit ~/.rag-memory-env or .env
DATABASE_URL=postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres

# Use it
uv run rag status
uv run rag search "query"
```

**Key points:**
- Both databases stay independent
- Schema must match (use Alembic on both)
- No automatic sync
- Just update DATABASE_URL and restart

---

## Phase 4: Future Migrations

When you add columns or change schema:

**1. Develop locally:**
```bash
export DATABASE_URL="postgresql://raguser:ragpassword@localhost:54320/rag_memory"
uv run alembic revision --autogenerate -m "add feature X"
uv run alembic upgrade head
```

**2. Apply to Supabase:**
```bash
export DATABASE_URL='postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres'
uv run alembic upgrade head
```

**3. Verify both match:**
```bash
# Check versions
DATABASE_URL="..." uv run alembic current
```

Both should show the same revision ID.

---

## Phase 5: MCP Server Configuration

The MCP server can connect to either Docker or Supabase by changing DATABASE_URL.

### Claude Desktop Config

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

**For Docker:**
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/path/to/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "DATABASE_URL": "postgresql://raguser:ragpassword@localhost:54320/rag_memory",
        "OPENAI_API_KEY": "sk-your-key"
      }
    }
  }
}
```

**For Supabase:**
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/path/to/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "DATABASE_URL": "postgresql://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres",
        "OPENAI_API_KEY": "sk-your-key"
      }
    }
  }
}
```

**To switch:** Edit DATABASE_URL, quit Claude Desktop completely, restart.

### Alternative: Global Config

If you don't want credentials in Claude config:

1. Edit `~/.rag-memory-env` with DATABASE_URL and OPENAI_API_KEY
2. Remove `env` section from Claude config
3. MCP server will read from global config file

---

## Phase 6: Data Migration (Optional)

If you want to move existing data from Docker to Supabase:

### Option A: Export/Import Data Only

**After schema is set up via Alembic**, export just the data:

```bash
# Export data from Docker (no schema)
docker exec rag-memory pg_dump -U raguser --data-only rag_memory > backups/data_$(date +%Y%m%d).sql

# Import to Supabase
psql "$SUPABASE_DB_URL" < backups/data_YYYYMMDD.sql

# Verify
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM collections;"
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM source_documents;"
```

### Option B: Sync from Supabase to Docker

To copy production data back to local for testing:

```bash
# Use the helper script
./scripts/sync-from-supabase.sh
```

This script:
1. Exports from Supabase
2. Drops local database
3. Imports to Docker
4. Verifies success

**Warning:** Destroys all local Docker data!

---

## Troubleshooting

### "could not translate host name" error
- You're using Direct Connection URL (requires paid IPv4 add-on)
- Fix: Use Session Pooler URL instead (`pooler.supabase.com`)

### "relation does not exist" during migration
- Baseline migration is broken
- Check: `alembic/versions/8050f9547e64_baseline_schema.py` should read `init.sql`

### Tables created but description is nullable
- Second migration didn't run
- Fix: `uv run alembic upgrade head`
- Verify: `psql "$SUPABASE_DB_URL" -c "\d collections"` (should show `not null`)

### Slow queries (>1s)
- Missing indexes
- Check: `psql "$SUPABASE_DB_URL" -c "\di"` (should see `hnsw` index on embeddings)

### Password authentication failed
- Wrong password or special characters not escaped
- Fix: Use single quotes around entire connection string: `export SUPABASE_DB_URL='postgresql://...'`

---

## Next Steps

1. Test thoroughly: `uv run rag status`
2. Test search: `uv run rag search "test" --chunks`
3. Test MCP server: `uv run python -m src.mcp.server`
4. Monitor usage: Supabase Dashboard → Settings → Usage
5. Set up alerts at 80% usage

---

## Support Resources

- **Schema Setup Guide:** [SUPABASE_SCHEMA_SETUP.md](./SUPABASE_SCHEMA_SETUP.md)
- **Supabase Docs:** https://supabase.com/docs
- **RAG with pgvector:** https://supabase.com/docs/guides/ai/rag-with-permissions

---

**Done!** Your RAG Memory is now on Supabase and accessible from anywhere.
