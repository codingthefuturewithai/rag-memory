# CLAUDE.md - RAG Memory Project Memory

**For complete details, see `.reference/` files. This file documents critical project memories only.**

---

## Project Overview

RAG Memory is a **PostgreSQL pgvector + Neo4j + MCP server** system for managing AI agent knowledge bases.

- **Purpose:** Replace ChromaDB with pgvector for better similarity accuracy (0.7-0.95 vs ChromaDB's 0.3)
- **Architecture:** Dual storage (RAG + Knowledge Graph)
- **Distribution:** git clone (NOT PyPI)

**Key Achievement:** Proper vector normalization + HNSW indexing achieves 0.73 similarity for near-identical content.

---

## Deployment Strategy (CRITICAL DECISION)

**Distribution:** Users `git clone` the repo (NOT `uv tool install`).

**Three Supported Scenarios:**

1. **Local MCP Server:** Docker Compose (PostgreSQL + Neo4j local) → AI agents connect to localhost:8000
2. **Cloud MCP Server:** Supabase + Neo4j Aura + Fly.io → AI agents connect to https://rag-memory-mcp.fly.dev/sse
3. **CLI Tool:** Command-line interface (connects to local OR cloud databases, never both)

**Key Principle:** ONE knowledge store at a time. Users pick LOCAL or CLOUD, not both.

**See:** `.reference/CLOUD_DEPLOYMENT.md` for complete setup guide.

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
- ✅ Decided: git clone distribution (NOT PyPI package)
- ✅ Decided: Local OR Cloud, never both (single environment at a time)
- ✅ Mandatory Knowledge Graph architecture ("All or Nothing")
- ✅ Startup validation for both PostgreSQL and Neo4j
- ✅ MCP tool count: 17 tools registered and functional
- ✅ Delete collection tool with graph cleanup

**Pending:**
- Create `scripts/deploy-to-fly.sh` (manual deployment with test pre-checks)
- Create `.reference/DATA_MIGRATION.md` (guide for local → cloud migration)
- Create `/rag-migrate` custom command (guided migration in Claude Code)

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
- Config file (`~/.config/rag-memory/config.yaml`) is portable, shared between both

**Key Principle:** Config file is the single source of truth, separate from both repo and PyPI distribution.

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
