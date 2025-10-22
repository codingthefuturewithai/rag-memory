# Supabase Schema Setup - Complete Guide

**Last updated:** 2025-10-13
**Status:** TESTED AND WORKING

This is the ONE correct way to set up RAG Memory schema on Supabase.

## Prerequisites

- Supabase project created
- Database password saved
- `psql` CLI installed (`brew install postgresql` on macOS)

## Steps

### 1. Get connection string

Go to Supabase Dashboard → Settings → Database → Connection Strings

Copy the **Session Pooler** string (NOT Direct Connection):
```
postgresql://postgres.[YOUR-PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
```

**IMPORTANT:** Use single quotes if your password has special characters:
```bash
export SUPABASE_DB_URL='postgresql://postgres.abc123:[p@ssw!rd]@aws-0-us-east-1.pooler.supabase.com:5432/postgres'
```

### 2. Verify pgvector installed

```bash
psql "$SUPABASE_DB_URL" -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

**Expected:** Shows `vector` in output.

**If empty:** Run this:
```bash
psql "$SUPABASE_DB_URL" -c "CREATE EXTENSION vector;"
```

### 3. Run Alembic migrations

```bash
export DATABASE_URL="$SUPABASE_DB_URL"
uv run alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> 8050f9547e64, baseline_schema
INFO  [alembic.runtime.migration] Running upgrade 8050f9547e64 -> 555255565f74, require_collection_description
```

### 4. Verify tables created

```bash
psql "$SUPABASE_DB_URL" -c "\dt"
```

**Expected:** 5 tables: `alembic_version`, `chunk_collections`, `collections`, `document_chunks`, `source_documents`

### 5. Verify schema correct

```bash
psql "$SUPABASE_DB_URL" -c "\d collections"
```

**Expected:** Line showing `description | text | not null`

### 6. Verify indexes created

```bash
psql "$SUPABASE_DB_URL" -c "\di"
```

**Expected:** Index named `document_chunks_embedding_idx` with type `hnsw`

## Done

Schema is set up correctly. Future migrations will work with:
```bash
export DATABASE_URL='your-supabase-url'
uv run alembic upgrade head
```

## Troubleshooting

**"relation does not exist" error during migration:**
- The baseline migration file is broken
- Fix: Edit `alembic/versions/8050f9547e64_baseline_schema.py` and ensure it reads `init.sql`

**"could not translate host name" error:**
- You're using Direct Connection URL which requires paid IPv4 add-on
- Fix: Use Session Pooler URL instead (port should be 5432 on `pooler.supabase.com`)

**Tables created but description is nullable:**
- Second migration didn't run
- Check: `uv run alembic current` (should show `555255565f74 (head)`)
- If not at head: `uv run alembic upgrade head`
