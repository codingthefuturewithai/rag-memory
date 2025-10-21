# Fly.io Test Deployment - Quick Start

**Complete isolation. No interference with existing rag-memory-mcp app.**

---

## What's Ready

All artifacts created. Nothing for you to create manually.

✅ `docker-compose.prod.yml` - Production compose file
✅ `fly.test.toml` - Fly.io config for test app (rag-memory-test)
✅ `backup.env` - Backup scheduling config
✅ `docker-compose.override.yml` - Local backup sidecar (optional, gitignored)
✅ `scripts/deploy-fly-test.sh` - Deployment automation script
✅ `docs/FLYIO_TEST_VERIFICATION.md` - Complete verification guide

---

## Deploy in 3 Steps

### Step 1: Run deployment script

```bash
./scripts/deploy-fly-test.sh
```

This will interactively guide you through:
1. Creating app: rag-memory-test
2. Creating 3 volumes
3. Setting OPENAI_API_KEY secret
4. Deploying to Fly.io

**Takes about 15-20 minutes total.**

### Step 2: Monitor deployment

```bash
./scripts/deploy-fly-test.sh logs
```

Wait for this message:
```
All startup validations passed - server ready ✓
```

### Step 3: Verify everything works

Follow `docs/FLYIO_TEST_VERIFICATION.md` (10-point checklist)

---

## Key Points

✅ **Completely isolated** - Test app `rag-memory-test` doesn't touch your production `rag-memory-mcp`
✅ **No manual file creation** - Everything already created, just run the script
✅ **Easy cleanup** - Run `./scripts/deploy-fly-test.sh destroy` when done
✅ **Full database access** - SSH tunnels let you access PostgreSQL and Neo4j
✅ **Daily backups** - Automatic Fly.io snapshots
✅ **Cheap** - ~$5-7/month, scales to zero when idle

---

## What the Artifacts Do

**docker-compose.prod.yml:**
- Used by deployment script
- References existing init.sql for schema
- Health checks on all services

**fly.test.toml:**
- App name: rag-memory-test (not rag-memory-mcp!)
- Mount configuration for volumes
- Everything needed for Fly.io deploy

**backup.env:**
- Local backup schedule (2 AM daily, customizable)
- Retention (7 days by default)

**docker-compose.override.yml:**
- Local-only (gitignored, not tracked)
- Adds backup sidecar container
- Only runs when you use docker-compose locally
- Never pushed to Fly.io

**scripts/deploy-fly-test.sh:**
- Full automation for all deployment phases
- Interactive if you run without arguments
- Can run individual steps: launch, volumes, secrets, deploy, status, logs, shell, destroy

**docs/FLYIO_TEST_VERIFICATION.md:**
- 10-point checklist to verify everything works
- Tests PostgreSQL, Neo4j, MCP server
- SSH tunnel instructions
- Troubleshooting guide

---

## One Command to Rule Them All

```bash
./scripts/deploy-fly-test.sh
```

That's it. Follow the prompts.

---

## After Deployment

**Test everything:**
```bash
./scripts/deploy-fly-test.sh status     # Check health
./scripts/deploy-fly-test.sh logs       # View logs
```

**Then follow verification guide:**
```bash
# docs/FLYIO_TEST_VERIFICATION.md
# 10 tests to run
```

**When done testing:**
```bash
./scripts/deploy-fly-test.sh destroy    # Clean up
```

---

## Important Notes

⚠️ **Don't edit these files manually** - They work as-is
⚠️ **Keep fly.test.toml** - Deployment script needs it
⚠️ **docker-compose.override.yml is gitignored** - That's intentional (local-only)
⚠️ **OPENAI_API_KEY is required** - Script will prompt for it

---

## What You're Testing

1. PostgreSQL initialization (pgvector, HNSW indexes)
2. Neo4j initialization (Graphiti schema)
3. MCP server deployment
4. All 17 MCP tools operational
5. Database access via SSH tunnels
6. Automatic daily backups

---

## Success Indicator

When `./scripts/deploy-fly-test.sh status` shows:
```
STATUS: started
3 health checks passed
```

And logs show:
```
All startup validations passed - server ready ✓
```

**You're ready to test!**

---

## Next: Detailed Verification

See `docs/FLYIO_TEST_VERIFICATION.md` for:
- How to connect to PostgreSQL
- How to access Neo4j Browser
- How to test MCP tools
- How to verify backups
- Troubleshooting if anything fails

---

**Ready? Run this:**

```bash
./scripts/deploy-fly-test.sh
```
