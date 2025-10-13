# Supabase Migration Guide

Complete guide to migrate RAG Memory from Docker Compose (local) to Supabase (cloud).

## Table of Contents

1. [Why Supabase?](#why-supabase)
2. [Prerequisites](#prerequisites)
3. [Phase 1: Supabase Project Setup](#phase-1-supabase-project-setup)
4. [Phase 2: Database Migration](#phase-2-database-migration)
5. [Phase 3: Testing & Validation](#phase-3-testing--validation)
6. [Phase 4: Row Level Security (Optional)](#phase-4-row-level-security-optional)
7. [Rollback Plan](#rollback-plan)
8. [Cost Monitoring](#cost-monitoring)
9. [Troubleshooting](#troubleshooting)

---

## Why Supabase?

**Key benefits:**
- ✅ **Access anywhere**: No more localhost-only database
- ✅ **Zero maintenance**: Automated backups, updates, monitoring
- ✅ **Free tier**: 500MB database, perfect for personal use
- ✅ **pgvector built-in**: No manual extension installation
- ✅ **Row Level Security**: Per-user collection isolation (optional)
- ✅ **Simple migration**: Just update connection string

**Cost:**
- Personal use: **FREE** (500MB limit)
- With backups: **$25/month** (Pro plan, up to 8GB comfortably)
- Small team: **$25-50/month** depending on data size

---

## Prerequisites

Before starting, ensure you have:

- [ ] Active Docker Compose setup with data you want to migrate
- [ ] Supabase account (sign up at https://supabase.com - free)
- [ ] Your current DATABASE_URL from `.env` file
- [ ] `psql` CLI installed (for migration)
  ```bash
  # macOS
  brew install postgresql

  # Ubuntu/Debian
  sudo apt-get install postgresql-client
  ```

---

## Phase 1: Supabase Project Setup

### Step 1.1: Create Supabase Project

1. **Go to https://supabase.com and sign up** (free, no credit card required)

2. **Click "New Project"**
   - Organization: Create new or use existing
   - Project name: `rag-memory` (or any name you prefer)
   - Database password: **SAVE THIS!** (e.g., use 1Password to generate strong password)
   - Region: Choose closest to you (e.g., `us-east-1` for East Coast US)
   - Pricing plan: **Free** (start here, upgrade later if needed)

3. **Wait for project creation** (~2 minutes)
   - You'll see "Setting up project..." progress indicator
   - When done, you'll land on the project dashboard

### Step 1.2: Get Connection Strings

1. **Navigate to Project Settings** (gear icon in left sidebar)

2. **Go to "Database" section**

3. **Copy Connection Strings** - You'll need these:

   **Session Mode (Recommended for RAG Memory):**
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```

   **Transaction Mode (Alternative if you have connection issues):**
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

   **Direct Connection (For pg_dump/restore only):**
   ```
   postgresql://postgres.[project-ref]:[password]@db.[project-ref].supabase.co:5432/postgres
   ```

   **Notes:**
   - Use **Session mode** for RAG Memory (port 5432) - best for persistent connections
   - Use **Transaction mode** (port 6543) if you hit connection limits
   - Use **Direct connection** only for `pg_dump` and `pg_restore` operations
   - Replace `[password]` with your actual database password

### Step 1.3: Verify pgvector is Installed

1. **Go to SQL Editor** (in left sidebar)

2. **Run this query:**
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

3. **If pgvector is NOT installed** (empty result), run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

   ✅ **Good news**: Supabase usually has pgvector pre-installed!

---

## Phase 2: Database Migration

### Strategy Overview

We'll use a **blue-green migration** approach:
1. Keep Docker running (blue/old)
2. Set up Supabase (green/new)
3. Migrate data
4. Test Supabase
5. Switch connection string
6. Optionally shut down Docker

### Step 2.1: Backup Current Docker Database

**CRITICAL: Always backup before migration!**

```bash
# Navigate to your project
cd /Users/timkitchens/projects/ai-projects/rag-memory

# Create backups directory
mkdir -p backups

# Export full database
docker exec rag-memory-postgres-1 pg_dump -U postgres rag_memory > backups/rag_memory_$(date +%Y%m%d_%H%M%S).sql

# Verify backup file exists and has content
ls -lh backups/
head -20 backups/rag_memory_*.sql
```

✅ **Success indicator**: You should see SQL CREATE TABLE statements in the backup file

### Step 2.2: Initialize Supabase Database Schema

**Option A: Fresh initialization (recommended if starting fresh)**

```bash
# Update .env temporarily to point to Supabase
cp .env .env.backup  # Backup current .env
nano .env  # Edit DATABASE_URL to Supabase connection string

# Run initialization (creates tables, indexes, installs pgvector)
uv run rag init

# Verify tables were created
# Go to Supabase Dashboard → Table Editor
# You should see: collections, source_documents, document_chunks, chunk_collections
```

**Option B: Restore from Docker backup (if you have existing data)**

```bash
# Set Supabase connection string
export SUPABASE_DB_URL="postgresql://postgres.[project-ref]:[password]@db.[project-ref].supabase.co:5432/postgres"

# Restore backup to Supabase
# Note: Use DIRECT connection (db.[project-ref].supabase.co) for pg_restore
psql "$SUPABASE_DB_URL" < backups/rag_memory_YYYYMMDD_HHMMSS.sql

# Handle errors (common issues):
# - "role postgres already exists" - IGNORE (safe)
# - "extension vector already exists" - IGNORE (safe)
# - Permission errors - make sure using correct connection string
```

### Step 2.3: Verify Migration Success

Run these checks to ensure everything migrated correctly:

```bash
# Check table exists and has data
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM collections;"
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM source_documents;"
psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM document_chunks;"

# Check indexes exist (CRITICAL for performance!)
psql "$SUPABASE_DB_URL" -c "\di"  # List all indexes

# Verify pgvector extension
psql "$SUPABASE_DB_URL" -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

# Check sample data
psql "$SUPABASE_DB_URL" -c "SELECT id, filename, file_type FROM source_documents LIMIT 5;"
```

**Expected results:**
- Row counts should match your Docker database
- You should see HNSW indexes on `embedding` columns
- pgvector version should be 0.7.0 or higher
- Sample documents should display correctly

---

## Phase 3: Testing & Validation

### Step 3.1: Update Environment Variables

```bash
# Edit .env file
nano .env

# Change DATABASE_URL to Supabase (Session Mode recommended)
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:5432/postgres

# Keep OPENAI_API_KEY unchanged
OPENAI_API_KEY=your-existing-key
```

### Step 3.2: Test RAG Memory Functionality

Run comprehensive tests to ensure everything works:

```bash
# 1. Test database connection
uv run rag status

# Expected output:
# ✅ Database connection successful
# ✅ pgvector extension installed (version X.X.X)
# Statistics: X collections, Y documents, Z chunks

# 2. Test similarity search (if you have data)
uv run rag search "test query" --collection your-collection-name --chunks --limit 3

# Expected: Returns relevant chunks with similarity scores

# 3. Test ingestion (create test collection)
uv run rag collection create test-supabase-migration --description "Testing Supabase migration"
uv run rag ingest text "Supabase migration test document" --collection test-supabase-migration

# Expected: Document ingested successfully

# 4. Test MCP server (if using)
uv run python -m src.mcp.server

# Expected: Server starts without connection errors
```

### Step 3.3: Verify MCP Server Integration

If you use the MCP server with Claude Desktop/agents:

```bash
# Start MCP server
uv run python -m src.mcp.server

# In another terminal, test with MCP Inspector (if installed)
npx @modelcontextprotocol/inspector

# Or test directly with Claude Desktop
# Your agents should be able to search/ingest without errors
```

### Step 3.4: Performance Validation

Test query performance to ensure indexes are working:

```bash
# Run a vector search and check timing
time uv run rag search "your test query" --collection your-collection --chunks --limit 5

# Expected timing:
# - First query: ~500-800ms (cold start, includes embedding generation)
# - Subsequent queries: ~300-500ms
# - If slower than 1s, check indexes: psql $DATABASE_URL -c "\di"
```

---

## Phase 4: Row Level Security (Optional)

**When to use RLS:**
- ✅ You want to share RAG Memory with multiple users
- ✅ Each user should only see their own collections/documents
- ✅ You plan to build a multi-tenant application

**When to skip RLS:**
- Personal use only (just you)
- All users in your team should see all data
- You're using RAG Memory locally (not exposing to network)

### Step 4.1: Add User ID Column to Tables

```sql
-- Run in Supabase SQL Editor
-- Add user_id column to collections table
ALTER TABLE collections
ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add user_id column to source_documents table
ALTER TABLE source_documents
ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Create indexes for performance
CREATE INDEX idx_collections_user_id ON collections(user_id);
CREATE INDEX idx_source_documents_user_id ON source_documents(user_id);
```

### Step 4.2: Enable RLS on Tables

```sql
-- Enable Row Level Security
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunk_collections ENABLE ROW LEVEL SECURITY;
```

### Step 4.3: Create RLS Policies

**Policy for Collections (users can only see their own):**

```sql
-- SELECT policy: Users can read their own collections
CREATE POLICY "Users can view own collections"
ON collections FOR SELECT
USING (auth.uid() = user_id);

-- INSERT policy: Users can create collections with their own user_id
CREATE POLICY "Users can create own collections"
ON collections FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- UPDATE policy: Users can update their own collections
CREATE POLICY "Users can update own collections"
ON collections FOR UPDATE
USING (auth.uid() = user_id);

-- DELETE policy: Users can delete their own collections
CREATE POLICY "Users can delete own collections"
ON collections FOR DELETE
USING (auth.uid() = user_id);
```

**Policy for Source Documents:**

```sql
-- SELECT policy: Users can read their own documents
CREATE POLICY "Users can view own documents"
ON source_documents FOR SELECT
USING (auth.uid() = user_id);

-- INSERT policy: Users can create documents with their own user_id
CREATE POLICY "Users can create own documents"
ON source_documents FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- UPDATE policy: Users can update their own documents
CREATE POLICY "Users can update own documents"
ON source_documents FOR UPDATE
USING (auth.uid() = user_id);

-- DELETE policy: Users can delete their own documents
CREATE POLICY "Users can delete own documents"
ON source_documents FOR DELETE
USING (auth.uid() = user_id);
```

**Policy for Document Chunks (inherit from source_documents):**

```sql
-- SELECT policy: Users can read chunks from their own documents
CREATE POLICY "Users can view chunks from own documents"
ON document_chunks FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM source_documents
    WHERE source_documents.id = document_chunks.source_document_id
    AND source_documents.user_id = auth.uid()
  )
);

-- INSERT policy: Users can create chunks for their own documents
CREATE POLICY "Users can create chunks for own documents"
ON document_chunks FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM source_documents
    WHERE source_documents.id = document_chunks.source_document_id
    AND source_documents.user_id = auth.uid()
  )
);

-- DELETE policy: Users can delete chunks from their own documents
CREATE POLICY "Users can delete chunks from own documents"
ON document_chunks FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM source_documents
    WHERE source_documents.id = document_chunks.source_document_id
    AND source_documents.user_id = auth.uid()
  )
);
```

**Policy for Chunk Collections (junction table):**

```sql
-- SELECT policy: Users can view chunk-collection relationships for their own collections
CREATE POLICY "Users can view chunk_collections for own collections"
ON chunk_collections FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM collections
    WHERE collections.id = chunk_collections.collection_id
    AND collections.user_id = auth.uid()
  )
);

-- INSERT policy: Users can link chunks to their own collections
CREATE POLICY "Users can add chunk_collections for own collections"
ON chunk_collections FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM collections
    WHERE collections.id = chunk_collections.collection_id
    AND collections.user_id = auth.uid()
  )
);

-- DELETE policy: Users can remove chunk-collection relationships for their own collections
CREATE POLICY "Users can delete chunk_collections for own collections"
ON chunk_collections FOR DELETE
USING (
  EXISTS (
    SELECT 1 FROM collections
    WHERE collections.id = chunk_collections.collection_id
    AND collections.user_id = auth.uid()
  )
);
```

### Step 4.4: Test RLS Policies

```sql
-- Test as authenticated user (replace 'test-user-uuid' with real user ID)
SET request.jwt.claims = '{"sub": "test-user-uuid"}';

-- Try to select collections (should only see user's own collections)
SELECT * FROM collections;

-- Try to select documents (should only see user's own documents)
SELECT * FROM source_documents;

-- Test vector search (should only return user's chunks)
SELECT dc.content, dc.embedding <=> '[...]'::vector AS similarity
FROM document_chunks dc
JOIN chunk_collections cc ON cc.chunk_id = dc.id
JOIN collections c ON c.id = cc.collection_id
WHERE c.user_id = auth.uid()
ORDER BY similarity LIMIT 5;
```

### Step 4.5: Update Application Code for RLS

**For personal use (single user), set a default user_id:**

```python
# Add to src/core/database.py or environment
import os

# Set a default user UUID for personal use
DEFAULT_USER_ID = os.getenv("RAG_USER_ID", "00000000-0000-0000-0000-000000000001")

# When creating collections/documents, include user_id:
# In src/core/collections.py:
def create_collection(self, name: str, description: str = None, user_id: str = None):
    user_id = user_id or DEFAULT_USER_ID
    # ... rest of code, include user_id in INSERT
```

**For multi-user applications:**
- Use Supabase Auth for user authentication
- Pass authenticated user's ID from JWT to queries
- Use service role key for admin operations

---

## Rollback Plan

If something goes wrong, you can easily roll back:

### Option 1: Switch Back to Docker

```bash
# Restore .env from backup
cp .env.backup .env

# Verify Docker is still running
docker-compose ps

# Test connection
uv run rag status
```

### Option 2: Restore Supabase from Backup

```bash
# Drop all tables in Supabase
psql "$SUPABASE_DB_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Restore from backup
psql "$SUPABASE_DB_URL" < backups/rag_memory_YYYYMMDD_HHMMSS.sql
```

---

## Cost Monitoring

### Free Tier Limits (What you get for $0/month)

- **Database size**: 500MB
- **Projects**: 2
- **Bandwidth**: 5GB egress
- **API requests**: Unlimited (but rate limited)

**How to monitor usage:**

1. **Go to Supabase Dashboard** → Settings → Usage

2. **Check metrics:**
   - Database size: Should stay under 500MB for free tier
   - Bandwidth: Monitor if using MCP server frequently
   - API requests: Track if you're hitting rate limits

3. **Set up alerts** (optional):
   - Go to Settings → Billing
   - Set up email alerts for 80% usage

### When to Upgrade to Pro ($25/mo)

Upgrade when you hit any of these:
- ✅ Database size > 450MB (stay safe, upgrade at 90%)
- ✅ Need automated backups (daily snapshots)
- ✅ Want better performance (more resources)
- ✅ Need more than 2 projects
- ✅ Higher bandwidth needs

**Pro plan includes:**
- 8GB database (16x more than free)
- $10 compute credits/month
- Daily automated backups with 7-day retention
- Better performance (dedicated resources)

---

## Troubleshooting

### Issue: "Too many connections" error

**Cause**: Connection pool exhausted

**Solution 1**: Use Transaction Mode (port 6543) instead of Session Mode
```bash
# In .env, change port 5432 to 6543
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Solution 2**: Close connections properly in code
```python
# Ensure database connections are closed after use
# RAG Memory already does this, but verify in custom code
```

### Issue: "Extension 'vector' does not exist"

**Cause**: pgvector not installed

**Solution**:
```sql
-- Run in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS vector;
```

### Issue: Slow queries (>1s for vector search)

**Cause**: Missing HNSW indexes

**Solution**:
```sql
-- Check if indexes exist
\di

-- If missing, create HNSW indexes
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Issue: Migration fails with "permission denied"

**Cause**: Using wrong connection string or insufficient privileges

**Solution**:
- Use **Direct Connection** for `pg_dump`/`pg_restore`:
  ```
  postgresql://postgres.[project-ref]:[password]@db.[project-ref].supabase.co:5432/postgres
  ```
- Verify password is correct
- Check Supabase dashboard for connection string

### Issue: RLS policies blocking legitimate queries

**Cause**: User ID not set correctly or policies too restrictive

**Solution 1**: Check current user context
```sql
SELECT auth.uid();  -- Should return your user UUID
```

**Solution 2**: Temporarily disable RLS for testing
```sql
ALTER TABLE collections DISABLE ROW LEVEL SECURITY;
-- Run your test
ALTER TABLE collections ENABLE ROW LEVEL SECURITY;
```

**Solution 3**: Use service role for admin queries
```bash
# Use service_role key from Supabase dashboard
# Settings → API → service_role key (secret!)
```

### Issue: "FATAL: password authentication failed"

**Cause**: Wrong password in connection string

**Solution**:
1. Go to Supabase Dashboard → Settings → Database
2. Click "Reset Database Password"
3. Update `.env` with new password
4. Update connection string

### Issue: High latency (>500ms queries)

**Cause**: Region mismatch or network issues

**Solution**:
1. Check your Supabase project region (Settings → General)
2. If far from your location, consider creating new project in closer region
3. Use `ping` to test latency:
   ```bash
   ping db.[project-ref].supabase.co
   ```

---

## Next Steps After Migration

1. ✅ **Test everything thoroughly** (run full test suite)
2. ✅ **Monitor costs** (check usage weekly for first month)
3. ✅ **Set up backups** (upgrade to Pro if you need automated backups)
4. ✅ **Update documentation** for your team
5. ✅ **Shut down Docker** (once confident Supabase is working):
   ```bash
   docker-compose down
   # Keep docker-compose.yml for local dev if needed
   ```

6. ✅ **Share with users** (if applicable):
   - Provide connection instructions
   - Document RLS setup if multi-tenant
   - Share cost expectations

---

## Support Resources

- **Supabase Documentation**: https://supabase.com/docs
- **RAG with Permissions Guide**: https://supabase.com/docs/guides/ai/rag-with-permissions
- **Supabase Discord**: https://discord.supabase.com
- **RAG Memory Issues**: https://github.com/your-repo/issues (replace with actual repo)

---

**Congratulations!** 🎉 You've successfully migrated RAG Memory to Supabase. Your vector database is now accessible from anywhere, automatically backed up, and ready to scale.
