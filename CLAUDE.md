# CLAUDE.md - RAG Memory Project Memory

**For complete details, see `.reference/` files. This file documents critical project memories only.**

---

## WE DO NOT DO KEYWORD SEARCHES

**CRITICAL - READ THIS FIRST:**

THIS SYSTEM USES SEMANTIC SIMILARITY SEARCH, NOT KEYWORD SEARCH.

ALL SEARCH QUERIES (RAG, DOCUMENT, GRAPH) MUST BE:
- ✓ FULL QUESTIONS: "How do I authenticate users in the system?"
- ✓ ENGLISH STATEMENTS: "I need to troubleshoot database connection issues"
- ✓ COMPLETE SENTENCES: "What are the security best practices for user management?"

NEVER USE KEYWORD SEARCHES:
- ✗ "user authentication"
- ✗ "database connection troubleshooting"
- ✗ "API endpoints security"

This is SEMANTIC search. It matches MEANING, not keywords. Keyword searches produce poor results.

---

## Project Overview

RAG Memory is a **PostgreSQL pgvector + Neo4j + MCP server** system for managing AI agent knowledge bases.

- **Purpose:** Replace ChromaDB with pgvector for better similarity accuracy (0.7-0.95 vs ChromaDB's 0.3)
- **Architecture:** Dual storage (RAG + Knowledge Graph)
- **Distribution:** Published to PyPI (via `uv publish`), users install with `uv tool install rag-memory`

**Key Achievement:** Proper vector normalization + HNSW indexing achieves 0.73 similarity for near-identical content.

---

## Deployment Strategy (CRITICAL DECISION)

**Distribution:** Published to PyPI. Users install with `uv tool install rag-memory`.

**Three Supported Scenarios:**

1. **System CLI Tool:** User installs `uv tool install rag-memory`, runs commands daily
   - Config stored at OS-specific location (system-level, persistent)
     - macOS: `~/Library/Application Support/rag-memory/`
     - Linux: `~/.config/rag-memory/`
     - Windows: `%APPDATA%\rag-memory\`
   - Can delete repo anytime - config remains
   - Connects to LOCAL or CLOUD databases (user chooses one)

2. **Local Development (repo cloned):** Developer `git clone` for local customization/testing
   - Config stored at: `config/config.dev.yaml` + `.env` (repo-local, temporary)
   - Uses local Docker Compose (PostgreSQL + Neo4j)
   - Can delete repo safely - temporary configs

3. **Automated Tests (repo cloned):** Testing suite in the repo
   - Config stored at: `config/config.test.yaml` + `.env` (repo-local, isolated)
   - Uses test Docker Compose with ephemeral databases
   - Can delete repo safely - test configs

**Key Principle:** ONE environment at a time. System config is permanent, repo configs are temporary.

---

## Database Connectivity (MANDATORY - Both Required)

**Architecture Decision:** Knowledge Graph is mandatory ("All or Nothing").

- Both PostgreSQL and Neo4j MUST be operational at all times
- Server refuses to start if either database is unavailable
- No graceful degradation or RAG-only fallback modes
- All write operations require health checks on both databases

**Health Checks:**
- Database.health_check() - PostgreSQL liveness check (~5-20ms)
- GraphStore.health_check() - Neo4j liveness check (~5-20ms)

**Startup Validation:**
- PostgreSQL validates: tables exist, pgvector loaded, HNSW indexes present
- Neo4j validates: Graphiti schema initialized, graph queryable
- Server won't start if either validation fails

**See:** `docs/STARTUP_VALIDATION_IMPLEMENTATION.md` for implementation details.

---

## Critical Implementation Details

### 1. Vector Normalization (THE KEY)
```python
# src/embeddings.py:33-46
def normalize_embedding(embedding: list[float]) -> list[float]:
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    return (arr / norm).tolist() if norm > 0 else arr.tolist()
```
- **Always normalize** vectors before storage and queries
- Without this: ChromaDB's 0.3 scores (broken)
- With this: Proper 0.7-0.95 scores ✓

### 2. psycopg3 + JSONB Handling
- **Must wrap dicts with `Jsonb(metadata)`** when inserting/comparing JSONB columns
- Retrieved metadata comes as dict (no parsing needed)

### 3. pgvector Integration
- Convert query embeddings: `np.array(embedding_list)`
- pgvector `<=>` operator returns cosine DISTANCE (0-2), not similarity (0-1)
- Convert: `similarity = 1.0 - distance`

### 4. Document Chunking (Recommended for Large Documents)
- Hierarchical splitting: headers → paragraphs → sentences → words
- Target: ~1000 chars per chunk with 200 char overlap
- Stores: full source_document + searchable document_chunks
- Each chunk independently embedded and searchable

**See:** `.reference/OVERVIEW.md` for complete architecture and implementation details.

---

## Development Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <repo>
cd rag-memory
uv sync
cp .env.example .env
# Add OPENAI_API_KEY to .env

# Start databases
docker-compose up -d

# Initialize schema
uv run rag init
```

**Common Commands:**
```bash
uv run rag status                    # Check database connection
uv run pytest                         # Run all tests
uv run python -m src.mcp.server      # Start MCP server (localhost:8000)
```

**See:** `.reference/OVERVIEW.md` for complete CLI reference.

---

## MCP Server

**Location:** `src/mcp/server.py` (FastMCP-based)
**Tools:** 17 total (search, collections, ingestion, document management, graph queries)
**Status:** ✅ Fully implemented and tested

**Local setup:**
```bash
uv run python -m src.mcp.server    # Runs on localhost:8000
```

**Cloud deployment:** Fly.io at `https://rag-memory-mcp.fly.dev/sse`

**See:** `.reference/MCP_QUICK_START.md` for complete tool documentation.

---

## Port Configuration

PostgreSQL: **54320** (not 5432 or 5433, to avoid conflicts with local PostgreSQL)

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "cannot adapt type 'dict'" | Metadata not wrapped | Use `Jsonb(metadata)` |
| "operator does not exist: vector <=> double" | Embedding not numpy | Use `np.array(embedding)` |
| Low similarity scores | Missing normalization | Check `normalize_embedding()` is enabled |
| Connection refused on 54320 | Docker not running | `docker-compose up -d` |
| Server won't start | Neo4j or PostgreSQL unhealthy | Check Docker containers, run validation test |
| Neo4j warnings about missing properties | Missing vector indices | Run setup.py or manually create vector indices |

**Neo4j Vector Indices (2025-10-31):**
- **Required for Performance:** Graphiti's `build_indices_and_constraints()` creates range/fulltext indices but NOT vector indices
- **Vector Indices Needed:**
  - `Entity.name_embedding` (1024 dimensions, cosine similarity)
  - `RELATES_TO.fact_embedding` (1024 dimensions, cosine similarity)
- **Created by:** `setup.py` in STEP 14.5 (after Graphiti indices)
- **Why:** Without vector indices, Neo4j logs warnings during ingestion about missing properties. System works but performance is degraded.

---

## What NOT to Do

❌ **Do NOT make deployment decisions without asking first**
- No automatic CI/CD deployments
- No assumptions about use cases (personal, team, organizational)
- No cloud vendor choices without explicit approval

❌ **Do NOT assume graceful degradation**
- Both databases REQUIRED ("All or Nothing")
- No fallback to RAG-only mode
- No toggling between environments

❌ **Do NOT create unnecessary files/documents**
- Documentation belongs in `.reference/`
- This file is memory only (references everything else)

---

## Key References

| Need | See |
|------|-----|
| Complete CLI commands | `.reference/OVERVIEW.md` |
| MCP tools & usage | `.reference/MCP_QUICK_START.md` |
| Cloud deployment guide | `.reference/CLOUD_DEPLOYMENT.md` |
| Search optimization results | `.reference/SEARCH_OPTIMIZATION.md` |
| Knowledge Graph details | `.reference/KNOWLEDGE_GRAPH.md` |
| Pricing analysis | `.reference/PRICING.md` |
| Startup validation specs | `docs/STARTUP_VALIDATION_IMPLEMENTATION.md` |
| Implementation gaps | `docs/IMPLEMENTATION_GAPS_AND_ROADMAP.md` |

---

## Recent Work & Decisions (2025-10-21)

**Completed:**
- ✅ Removed automatic GitHub Actions CI/CD (manual deployment only)
- ✅ Decided: PyPI distribution via `uv publish`
- ✅ Decided: Local OR Cloud, never both (single environment at a time)
- ✅ Mandatory Knowledge Graph architecture ("All or Nothing")
- ✅ Startup validation for both PostgreSQL and Neo4j
- ✅ MCP tool count: 17 tools registered and functional
- ✅ Delete collection tool with graph cleanup
- ✅ Configuration system: YAML + environment variables (section 2025-10-22)

**Configuration Strategy (2025-10-22):**

Three scenarios, three configurations:

1. **System CLI (installed via setup.py):**
   - System config directory (OS-specific, permanent, created by setup.py)
     - macOS: `~/Library/Application Support/rag-memory/config.yaml`
     - Linux: `~/.config/rag-memory/config.yaml`
     - Windows: `%APPDATA%\rag-memory\config.yaml`
   - Mount paths: Configured by user during setup (could be anywhere on their system)
   - OPENAI_API_KEY in config.yaml

2. **Local Development (repo cloned):**
   - `.env` file (gitignored) - stores ONLY OPENAI_API_KEY
   - `config/config.dev.yaml` (committed) - database URLs, dev mounts
   - Mounts point to: `.reference/` directory in repo
   - conftest.py sets RAG_CONFIG_PATH to repo config directory

3. **Automated Tests (repo cloned):**
   - `.env` file (gitignored) - stores ONLY OPENAI_API_KEY
   - `config/config.test.yaml` (committed) - test database URLs, test mounts
   - Mounts point to: `test-data/` directory in repo (test documents)
   - conftest.py sets RAG_CONFIG_PATH to repo config directory

Key principle: `.env` is ONLY for secrets (OPENAI_API_KEY), everything else is in YAML. YAML files are committed and source-controlled. `.env` is gitignored.

**In Progress:**
- Create `scripts/setup.py` (interactive one-command setup for users)
- Update `.env.example` to show OPENAI_API_KEY only
- Update `config/config.dev.yaml` to use `.reference/` as default mount
- Create `config/config.test.yaml` to use `test-data/` as default mount
- Create `test-data/` directory with sample test documents
- Update conftest.py to load `.env` + YAML config

**Pending:**
- Verify end-to-end configuration works for all three scenarios
- Test fresh PyPI install in clean environment
- Create `.reference/DATA_MIGRATION.md` (guide for local → cloud migration)

---

## scripts/setup.py - One-Command User Setup (2025-10-22)

**Purpose:** User runs `python scripts/setup.py` once. Script handles entire setup: Docker, containers, system config, tool installation.

**User experience:** One command, interactive prompts, everything done. Then user can delete repo.

**Setup.py Flow (All-or-Nothing at Each Step):**

1. **Check Docker installed**
   - If NO: "Install Docker, open new terminal, re-run this script"
   - HALT and EXIT

2. **Check Docker daemon running**
   - If NO: "Start Docker, then press Enter to continue"
   - PAUSE/WAIT for user input, then retry check in same script

3. **Check if RAG Memory local containers running**
   - If YES: "Containers exist. Tear down and rebuild (volumes preserved)? (yes/no)"
     - If NO: HALT and EXIT
     - If YES: Run `docker-compose down`, continue
   - If NO: Continue

4. **Start containers**
   - Run `docker-compose up -d`
   - Wait for health checks to pass

5. **Check if system config exists**
   - If YES: "Config exists. Overwrite it? (yes/no)"
     - If NO: HALT and EXIT
     - If YES: Continue to overwrite
   - If NO: Continue

6. **Prompt for OPENAI_API_KEY**
   - Validate not empty
   - If invalid: re-prompt

7. **Prompt for database_url, neo4j_uri, neo4j_user, neo4j_password**
   - Validate connectivity or at least format
   - If invalid: re-prompt

8. **Create system config directory**
   - Ensure OS-specific config directory exists (using platformdirs)

9. **Write config.yaml**
   - Write config.yaml to system config directory with all settings
   - Set permissions to 0o600 (user-only)

10. **Install tool**
    - Run `uv tool install .`

11. **Verify installation**
    - Run `rag status` to confirm tool works

12. **Print success message**
    - "Setup complete! You can now delete this repository and use 'rag' commands anywhere."

---

## PyPI Distribution & CLI Tool Management (2025-10-22)

**Research Findings on `uv tool install` with Git:**
- ✅ Can specify git URLs and tags: `uv tool install git+https://github.com/user/rag-memory@v1.0.0`
- ❌ Installation can be flaky (observed malformed tool environments in testing)
- ❌ `uv tool upgrade` does NOT work with git-installed tools (documented limitation)
- ❌ Users would need to manually reinstall with new tags each time
- **Conclusion:** Git-based tool installation is NOT reliable for production upgrades

**Decision: Use PyPI for CLI Tool Distribution**
- MCP server code and Docker files stay in git repo (users git clone)
- CLI tool ONLY distributed via PyPI for reliable system-wide installation
- User workflow:
  1. `git clone` repo once
  2. `python scripts/setup.py` runs setup from repo
  3. `uv tool install rag-memory` installs CLI system-wide from PyPI (optional convenience)
  4. Later: `git pull` upgrades MCP server code, Docker files
  5. Later: `uv tool upgrade rag-memory` upgrades CLI tool
- Config file (in OS-specific location) is portable, shared between both

**Key Principle:** Config file (stored in OS-specific location via platformdirs) is the single source of truth, separate from both repo and PyPI distribution.

---

## Session Memory

**Important Lessons Learned (for future sessions):**

1. **ASK BEFORE DECIDING** - Don't make architectural choices without explicit permission
2. **Don't assume use cases** - Personal ≠ Team ≠ Organizational
3. **Don't create unnecessary documents** - Everything goes in `.reference/` or this file
4. **Keep CLAUDE.md focused** - It's for memories, not a manual
5. **Deployment is intentional** - No surprises (no automatic deployments)

---

**Last Updated:** 2025-10-21
**Status:** Production-ready for local and cloud deployment
