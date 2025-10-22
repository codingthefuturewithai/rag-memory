# Fly.io Test Deployment - Summary & Quick Reference

**Created:** 2025-10-21
**Status:** Ready for testing
**Estimated Time:** 20 minutes setup + 5-10 minutes deployment

---

## What's Included

### 📋 Main Deployment Plan
**File:** `docs/FLYIO_TEST_DEPLOYMENT_PLAN.md` (1 page, comprehensive)

Contains:
- ✅ New infrastructure files (docker-compose.prod.yml, fly.toml, backup.env, .dockerignore)
- ✅ Step-by-step setup (authentication, volumes, secrets)
- ✅ Deployment process with monitoring
- ✅ Backup strategy (Fly.io native snapshots + optional local backups)
- ✅ Database access instructions (PostgreSQL, Neo4j via SSH tunnels)
- ✅ Testing verification steps
- ✅ Cleanup instructions
- ✅ Troubleshooting guide
- ✅ Cost estimation ($5-7/month)

### 🔧 Files to Create

All files reference existing repository assets (no new dependencies):

1. **docker-compose.prod.yml**
   - PostgreSQL (pgvector/pgvector:pg16)
   - Neo4j (neo4j:5-community)
   - RAG MCP server (built from existing Dockerfile)
   - Volumes: postgres_data, neo4j_data, neo4j_logs

2. **fly.toml**
   - App configuration for rag-memory-test
   - Region: iad (Ashburn, VA)
   - Internal port: 8000 (matches Dockerfile)
   - Volume mounts for persistence

3. **backup.env** (optional, for local backups)
   - Cron schedule: 0 2 * * * (2 AM daily, customizable)
   - Retention: 7 days
   - Output: ./backups/rag-memory-backup-*.tar.gz

4. **.dockerignore**
   - Excludes docker-compose files, tests, docs, etc.
   - Reduces image size and build time

### ✅ Verification Checklist

All dependencies already exist in repository:

- ✓ `Dockerfile` - exists and configured correctly
- ✓ `init.sql` - schema initialization file exists
- ✓ `src/mcp/server.py` - MCP server implementation
- ✓ `pyproject.toml` - dependencies and configuration
- ✓ All MCP tools (17 total) implemented and tested

---

## Key Architecture Decisions

### Why docker-compose.prod.yml (separate file)?

```
Local Development (docker-compose.yml)
    └─ stays unchanged
    └─ current environment
    └─ existing .env files work

Fly.io Test (docker-compose.prod.yml)
    └─ NEW file for test deployment
    └─ can reference this separately
    └─ doesn't interfere with local setup
    └─ easy to delete after testing
```

**Result:** Zero risk to existing local setup. Test independently.

### Why Fly.io volumes instead of Supabase?

**Before (Supabase on Fly.io):**
- ❌ Supabase on Fly.io deprecated April 2025
- ❌ Managed database with limited access
- ❌ No Neo4j option (had to use external service)

**After (Self-hosted with Fly.io volumes):**
- ✅ Full control over both PostgreSQL and Neo4j
- ✅ Complete database access for admin/debugging
- ✅ Native Fly.io snapshots (daily, 5 days retention)
- ✅ Optional local backups via docker-volume-backup sidecar
- ✅ Much simpler deployment (single docker-compose file)

### Why health checks on all services?

```
PostgreSQL: pg_isready -U raguser
    └─ Verifies connection pool ready
    └─ Prevents startup race conditions

Neo4j: cypher-shell 'RETURN 1'
    └─ Verifies graph is queryable
    └─ Ensures Graphiti schema initialized

MCP Server: depends_on both with service_healthy
    └─ Doesn't start until databases ready
    └─ Eliminates startup validation errors
    └─ Matches Gap 2.1 "All or Nothing" design
```

---

## Deployment Flow (Quick Reference)

```
1. Authenticate
   fly auth login

2. Create App
   fly launch --copy-config --name rag-memory-test

3. Create Volumes (CRITICAL)
   fly volumes create postgres_data --size 10
   fly volumes create neo4j_data --size 10
   fly volumes create neo4j_logs --size 5

4. Set Secrets
   fly secrets set OPENAI_API_KEY="sk-..."

5. Deploy
   fly deploy --wait-timeout 300

6. Verify
   fly status --app rag-memory-test
   fly logs --app rag-memory-test

7. Test Database Access
   fly proxy 5432:5432 --app rag-memory-test
   psql postgresql://raguser:ragpassword@localhost/rag_memory

8. Test Neo4j
   fly proxy 7474:7474 7687:7687 --app rag-memory-test
   open http://localhost:7474

9. Test MCP Server
   curl https://rag-memory-test.fly.dev/sse

10. Cleanup (when done)
    fly apps destroy rag-memory-test
```

---

## Daily Backup Strategy

### Local Development (docker-compose.override.yml - optional)

```
Schedule: 2 AM daily (configurable)
Method: offen/docker-volume-backup sidecar
Output: ./backups/rag-memory-backup-YYYYMMDD-HHMMSS.tar.gz
Retention: 7 days (auto-rotated)
Size: ~100MB per backup for intermediate DB
Duration: ~1-2 minutes
Cost: $0 (included in Docker Desktop)
```

**NOT pushed to Fly.io** - only runs locally.

### Fly.io Production (fly.toml)

```
Method: Native volume snapshots
Schedule: Automatic daily
Retention: 5 days default (can change to 1-60 days)
Durability: Multi-region by default
Cost: $0 (included with volumes)
Admin Access: Via web dashboard + CLI
Restore: Can restore to new volume if needed
```

**Why both?**
- Local: Easy backup for developer machines (optional)
- Cloud: Automatic protection for deployed app (mandatory)

---

## Testing Verification Checklist

After deployment, verify:

- [ ] `fly status` shows all machines started and healthy
- [ ] Logs show "All startup validations passed - server ready ✓"
- [ ] PostgreSQL accessible via `fly proxy 5432:5432` + psql
- [ ] Can query PostgreSQL schema (tables, indexes visible)
- [ ] Neo4j Browser accessible via `fly proxy 7474:7474` + http://localhost:7474
- [ ] Can run Neo4j queries (MATCH (n) RETURN COUNT(n))
- [ ] MCP server responds to HTTP requests
- [ ] Can create collection via MCP tool
- [ ] Can search documents via MCP tool
- [ ] Fly.io dashboard shows daily snapshots created

---

## Important Notes for Users

### 🎯 Constraints (by design)

✅ **Single environment:** Same docker-compose pattern works locally AND on Fly.io
✅ **No manual setup:** All initialization happens automatically at startup
✅ **Easy cleanup:** Test deployment is isolated, can be deleted without affecting local setup
✅ **No AWS required:** Backups handled by Fly.io native snapshots + optional local sidecar
✅ **Full database access:** Both PostgreSQL and Neo4j fully accessible for admin/debugging

### ⚠️ Important Limits

- **Max volume size (Fly.io):** 500 GB per volume
- **Snapshot retention:** Default 5 days, configurable 1-60 days
- **Auto-scaling:** Set to scale-to-zero by default (cost optimization)
- **Health check timeout:** 30 seconds (failure after 5 retries = restart)
- **Database connections:** Fly.io default limit is reasonable for test app

### 🔐 Security Notes

- PostgreSQL user/password in docker-compose.prod.yml is example values
- OPENAI_API_KEY stored as Fly.io secret (not in code/compose files)
- Neo4j password: graphiti-password (same as local dev setup)
- All databases only accessible from within app network (except via `fly proxy`)
- HTTPS enforced for all external HTTP traffic (automatic)

---

## Success Criteria ✅

After following the deployment plan, you should be able to:

✅ Deploy to Fly.io in <15 minutes
✅ Access all three services (PostgreSQL, Neo4j, MCP) remotely
✅ Create and search documents via MCP tools
✅ View database schemas via SSH tunnels
✅ Verify daily snapshots created in Fly.io dashboard
✅ Delete test app cleanly without affecting local setup

---

## Next Steps (After Successful Test)

**If test is successful:**

1. Create production app: `fly launch --name rag-memory-prod`
2. Set up monitoring: Fly.io dashboard alerts
3. Document connection strings for end users
4. Create backup/restore runbook
5. Test failover scenarios

**If issues occur:**

1. Check logs: `fly logs --app rag-memory-test --lines 100`
2. SSH into container: `fly ssh console --app rag-memory-test`
3. Check volume status: `fly volumes list --app rag-memory-test`
4. Restart machines: `fly machines restart [id]`
5. See troubleshooting section in main plan

---

## Files Reference

**Created for this deployment:**
- `docs/FLYIO_TEST_DEPLOYMENT_PLAN.md` - Full deployment guide (1 page)
- `docs/FLYIO_TEST_DEPLOYMENT_SUMMARY.md` - This file (quick reference)

**To create before deploying:**
- `docker-compose.prod.yml` (copy from plan)
- `fly.toml` (copy from plan)
- `.dockerignore` (copy from plan)
- `backup.env` (optional, for local backups)

**Already exist (no changes needed):**
- `Dockerfile` ✓
- `init.sql` ✓
- `src/mcp/server.py` ✓
- `pyproject.toml` ✓
- All source code ✓

---

## Cost Breakdown

| Component | Cost | Notes |
|-----------|------|-------|
| App compute (3 services) | $2-5/mo | Scales to zero when idle |
| PostgreSQL volume (10GB) | $1.50/mo | Auto-snapshots included |
| Neo4j volumes (15GB) | $2.25/mo | Auto-snapshots included |
| **Total** | **~$5-7/mo** | **Scales to zero = minimal cost** |

**Compare to alternatives:**
- Always-on Heroku: $40-100/month
- AWS RDS + EC2: $20-50/month
- Fly.io with auto-scale: $0-7/month (you control)

---

## Time Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Preparation (files) | 5 min | Copy code from plan |
| Authenticate | 1 min | One-time setup |
| Create app | 2 min | `fly launch` |
| Create volumes | 2 min | 3 volume creation commands |
| Set secrets | 1 min | 1 API key |
| Deploy | 5-10 min | Build image + start services |
| Verification | 5 min | Run test queries |
| **Total** | **~20-25 min** | First time only |

---

**Ready to deploy?** Follow `FLYIO_TEST_DEPLOYMENT_PLAN.md` step by step.

Questions? Refer to troubleshooting section in main plan.
