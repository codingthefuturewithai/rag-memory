# RAG Memory Render Migration - Implementation Plan

**Goal:** Create reliable, safe migration system from local Docker to Render cloud

**Principle:** Research first, verify assumptions, then implement. No cascading errors.

---

## Phase 1: Research & Validation

### 1.1 PostgreSQL Migration Research
**Questions to answer:**
- [ ] What's the correct pg_dump command for our schema?
- [ ] Does Render PostgreSQL accept standard pg_dump output?
- [ ] Are there any Render-specific connection requirements?
- [ ] How do we verify the import succeeded?
- [ ] What about extensions (pgvector) - are they preserved?
- [ ] Does the alembic_version table need special handling?

**Research tasks:**
- WebSearch: Render PostgreSQL import methods 2025
- WebFetch: https://render.com/docs/postgresql
- Read: our local docker-compose.yml for exact PostgreSQL config
- Read: our alembic migrations to understand schema structure

### 1.2 Neo4j Migration Research
**Questions to answer:**
- [ ] What's the correct neo4j-admin dump command for Docker?
- [ ] How do we access Neo4j container in Render to run restore?
- [ ] Does Render Neo4j support neo4j-admin commands?
- [ ] Can we access the persistent disk to upload dumps?
- [ ] What about Graphiti schema - is it preserved?
- [ ] Does Neo4j need to be stopped during restore?

**Research tasks:**
- WebSearch: Render Docker persistent disk file upload 2025
- WebSearch: Neo4j docker container backup restore 2025
- WebFetch: https://render.com/docs/disks
- WebFetch: Neo4j backup/restore documentation

### 1.3 Render Infrastructure Research
**Questions to answer:**
- [ ] How do we execute commands in Render Docker containers?
- [ ] Can we upload files to persistent disks programmatically?
- [ ] What's the Render API for this? Or is it manual?
- [ ] Are there SSH/shell access to Render services?
- [ ] What about temporary maintenance mode?

**Research tasks:**
- WebSearch: Render shell access Docker container 2025
- WebFetch: https://render.com/docs/docker
- WebSearch: Render CLI commands for container access
- Check: Does Render have a CLI tool?

### 1.4 Script Dependencies Research
**Questions to answer:**
- [ ] What Python libraries do we need? (psycopg2? neo4j driver?)
- [ ] Can we use subprocess for docker/psql commands?
- [ ] What CLI tools must be installed? (psql, docker, render CLI?)
- [ ] How do we handle credentials securely?
- [ ] What's the cross-platform compatibility? (macOS, Linux, Windows)

**Research tasks:**
- Check: our existing pyproject.toml for database libraries
- Review: what tools are already installed in user's environment

---

## Phase 2: Design

### 2.1 Migration Script Architecture (REVISED - Full Automation)
**After research, final design:**
```
scripts/migrate_to_render.py
├─ Phase 0: Detect local data
│  ├─ Check Docker running
│  ├─ Check local containers exist
│  ├─ Check local data exists (counts > 0)
│  └─ ASK USER: Migrate data or start fresh? (even if data exists)
│
├─ Phase 1: Pre-flight checks (if migrating)
│  ├─ Check required CLI tools (psql, docker)
│  └─ Check Python dependencies (neo4j driver)
│
├─ Phase 2: Gather Render credentials (interactive prompts)
│  ├─ Prompt for Render PostgreSQL URL
│  ├─ Prompt for Render Neo4j URI
│  ├─ Prompt for Render Neo4j user
│  └─ Prompt for Render Neo4j password (masked)
│
├─ Phase 3: Test Render connectivity
│  ├─ Test PostgreSQL connection
│  ├─ Test Neo4j connection
│  └─ Verify services are empty (or warn if not)
│
├─ Phase 4: Dry run preview (if migrating)
│  └─ Show user what will happen
│
├─ Phase 5: Export from local (if migrating)
│  ├─ Create timestamped backup directory
│  ├─ Export PostgreSQL (docker exec pg_dump)
│  ├─ Export Neo4j (Python driver - all nodes/relationships)
│  └─ Verify backup files exist and non-empty
│
├─ Phase 6: Import to Render (if migrating)
│  ├─ Enable pgvector extension on Render
│  ├─ Import PostgreSQL (psql --single-transaction)
│  ├─ Import Neo4j (Python driver - batched transactions)
│  └─ Verify each import with progress bars
│
├─ Phase 7: Verification
│  ├─ Count PostgreSQL records (match local if migrated)
│  ├─ Count Neo4j nodes (match local if migrated)
│  └─ Report success/failure
│
└─ Phase 8: Next steps
   ├─ Tell user to test Render deployment
   ├─ Remind: Local data kept safe until confirmed
   └─ Guide to connect AI agents to Render
```

**Key changes:**
- **User choice** added even when local data exists
- **Neo4j migration** via Python driver (no SSH)
- **Interactive prompts** for all credentials
- **Progress bars** for long operations
- **No testing mode** (user will test on their system)

**Decision points based on research:**
- If Render doesn't allow direct container access, we may need manual steps
- If Neo4j restore requires stopping service, document downtime
- If any step requires Render CLI, check if it exists

### 2.2 Error Handling Strategy
**For each operation:**
- Try/except with specific error messages
- Rollback guidance (what to do if this step fails)
- Continue vs. abort decision (some failures are recoverable)
- Log everything to a file for debugging

### 2.3 Documentation Structure
**docs/MIGRATE_TO_CLOUD.md:**
1. When to use (decision tree)
2. Prerequisites checklist
3. Quick start (automated script)
4. Step-by-step walkthrough (what script does)
5. Manual migration (if script fails)
6. Verification checklist
7. Troubleshooting
8. Rollback instructions

**.reference/CLOUD_SETUP.md:**
- Add "Migration from Local" section
- Link to detailed migration guide
- Include in cost comparison (free local → paid Render)

**.claude/commands/cloud-setup.md:**
- Add Step 0: Detect local data
- Branch logic (fresh vs. migration)
- Guide user through script prompts
- Verification together

---

## Phase 3: Implementation

### 3.1 Create Migration Script
**Order:**
1. Skeleton with all phases (no-op)
2. Phase 1: Pre-flight checks
3. Phase 2-3: Credential gathering and testing
4. Phase 4: Dry run
5. Phase 5: PostgreSQL export (test locally)
6. Phase 6: PostgreSQL import (test with Render)
7. Phase 5: Neo4j export (test locally)
8. Phase 6: Neo4j import (test with Render)
9. Phase 7: Verification
10. Polish: Error handling, logging, progress messages

**Test after each phase before moving to next**

### 3.2 Create Documentation
**Order:**
1. docs/MIGRATE_TO_CLOUD.md (full guide)
2. .reference/CLOUD_SETUP.md (update with migration section)
3. .claude/commands/cloud-setup.md (update with detection logic)
4. CLAUDE.md (update if needed)

**Cross-reference check after all docs written**

### 3.3 Testing
**Test scenarios:**
1. Fresh deployment (no local data)
2. Migration with small dataset
3. Migration with large dataset
4. Migration failure scenarios (wrong credentials, network issue)
5. Script interruption (Ctrl+C) and retry
6. Cross-platform (macOS, Linux if possible)

---

## Phase 4: Verification

### 4.1 Documentation Review
**Checklist:**
- [ ] All docs mention same Render service names
- [ ] All docs use same environment variable names
- [ ] All docs link to each other correctly
- [ ] All docs have accurate cost estimates
- [ ] All docs reference current Render URLs
- [ ] No contradictions between docs

### 4.2 Script Review
**Checklist:**
- [ ] All error messages are actionable
- [ ] All prompts are clear
- [ ] Credentials never logged/printed
- [ ] Backup files have clear names with timestamps
- [ ] Verification is thorough (not just "success" message)
- [ ] Works on empty databases (fresh start)
- [ ] Works on populated databases (migration)

---

## Research Findings Log

### Finding 1: PostgreSQL Migration (pg_dump/psql)
**Research done:**
- WebSearch: Render PostgreSQL import/restore
- WebFetch: https://render.com/docs/postgresql-backups
- WebSearch: psql import restore SQL dump
- Read: docker-compose.yml (local setup)

**Result:**
- ✅ Render accepts standard pg_dump SQL files
- ✅ Export command: `docker exec rag-memory-postgres-local pg_dump -U raguser -d rag_memory --clean --if-exists > backup.sql`
- ✅ Import command: `psql "$RENDER_DATABASE_URL" --single-transaction < backup.sql`
- ✅ pgvector extension should be preserved (but ensure `CREATE EXTENSION vector;` runs first on Render)
- ✅ alembic_version table included automatically
- ✅ Use `--single-transaction` for atomic restore (rollback on error)

**Local Docker config:**
- Container: `rag-memory-postgres-local`
- User: `raguser` (default)
- Password: `ragpassword` (default)
- Database: `rag_memory`
- Port: 54320 → 5432

**Impact on design:**
- Script needs to run `CREATE EXTENSION vector;` on Render before restore
- Can use standard psql CLI tool (widely available)
- Single transaction restore = safe, can retry on failure
- Need to verify pgvector data (embeddings) after restore

### Finding 2: Neo4j Migration (neo4j-admin dump/load)
**Research done:**
- WebSearch: Neo4j docker backup restore neo4j-admin
- WebFetch: Neo4j Operations Manual dump/load documentation
- WebSearch: Render shell access and file upload
- WebFetch: Render SSH and persistent disk docs
- Read: docker-compose.yml (local Neo4j config)

**Result - Local Export:**
- ✅ Container: `rag-memory-neo4j-local`
- ✅ Requires STOPPING Neo4j first (offline dump only for Community Edition)
- ✅ Export command:
  ```bash
  docker stop rag-memory-neo4j-local
  docker run --rm \
    --volumes-from rag-memory-neo4j-local \
    --volume=$PWD/backups:/backups \
    neo4j/neo4j-admin:5-community \
    neo4j-admin database dump neo4j --to-path=/backups
  docker start rag-memory-neo4j-local
  ```
- ✅ Creates dump file: `neo4j.dump`

**Result - Render Import (COMPLEX):**
- ⚠️ Requires paid plan for SSH access ($7/month Starter - needed anyway)
- ⚠️ Requires SSH setup (generate keys, add to Render account)
- ⚠️ File upload options:
  1. magic-wormhole (requires installation in container)
  2. SCP via SSH (requires SSH configured)
- ⚠️ Must modify Neo4j Docker image to include openssh-server
- ⚠️ Must run neo4j-admin load command via SSH
- ⚠️ Requires stopping Neo4j service during restore

**Alternative - Python Driver Export/Import:**
- Use `neo4j` Python driver to export all nodes/relationships
- Export to JSON or Cypher statements
- Import via driver to Render
- Fully automated but slower
- No SSH or file uploads needed

**Local Neo4j config:**
- Image: `neo4j:5-community`
- APOC plugin enabled
- User: `neo4j` (default)
- Password: `graphiti-password` (default)
- Bolt port: 7687
- Data volume: `neo4j_data_local`

**Impact on design:**
THREE OPTIONS TO CONSIDER:
1. **Automated Neo4j migration** (complex): Requires SSH setup, file upload, custom Docker image
2. **Python driver-based** (slower): Fully automated, no SSH, works but slow for large graphs
3. **Manual Neo4j migration** (simple MVP): Document the process, user does it manually, script focuses on PostgreSQL

**REVISED: Full automation using Python driver**
- Use `neo4j` Python driver (already in dependencies via graphiti-core)
- Export all nodes/relationships via Cypher queries
- Import to Render Neo4j via driver transactions
- No SSH setup required
- Slower than neo4j-admin but fully automated

### Finding 3: Render-Specific Constraints
**Research done:**
- WebFetch: Render persistent disks documentation
- WebSearch: Render CLI and file upload
- WebFetch: Render SSH access documentation

**Result:**
- ✅ PostgreSQL: Fully managed, easy migration via psql
- ⚠️ Neo4j: Docker-based, requires SSH for admin commands
- ⚠️ Free plan: No persistent disks, no SSH access
- ✅ Starter plan ($7/month): Required for both persistent disk AND SSH
- ✅ Private networking: Services can connect via internal URLs
- ✅ Render CLI: Exists but doesn't have direct file upload to containers

**Impact on design:**
- Migration requires Starter plan minimum (~$21/month total)
- SSH setup is prerequisite for Neo4j migration
- PostgreSQL migration is straightforward
- Neo4j migration requires additional steps or automation complexity

### Finding 3: [Topic]
...

---

**Status:** Phase 1 - Ready to begin research
**Last updated:** 2025-01-10
