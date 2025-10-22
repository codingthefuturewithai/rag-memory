# Gap 2.1 Implementation Plan: Mandatory Knowledge Graph

**Decision:** Option B - Make Knowledge Graph Mandatory (All or Nothing)
**Status:** Planning Phase
**Date:** 2025-10-21

---

## Overview

Transform the system from optional-with-fallback to truly mandatory graph, enforced through:

1. **Lightweight liveness checks** before ANY ingestion/update/delete operation
2. **Fail-fast responses** if databases are unreachable
3. **Cleaned-up docstrings** that focus on LLM contract, not implementation
4. **Removed fallback paths** that allowed RAG-only operation

---

## Phase 1: Liveness Checks (FOUNDATION)

### 1.1 Add Health Check to Database Class

**File:** `src/core/database.py`

**What to add:**
```python
async def health_check(self, timeout_ms: int = 2000) -> dict:
    """
    Lightweight PostgreSQL liveness check.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "latency_ms": float,
            "error": str or None
        }
    """
    # Property check first (instant, no network)
    if self._connection and (self._connection.closed or self._connection.broken):
        return {"status": "unhealthy", "latency_ms": 0.0, "error": "Connection closed"}

    # SELECT 1 network validation
    try:
        start = time.perf_counter()
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

        latency = (time.perf_counter() - start) * 1000
        return {"status": "healthy", "latency_ms": round(latency, 2), "error": None}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {"status": "unhealthy", "latency_ms": round(latency, 2), "error": str(e)}
```

**Use cases:**
- Before any ingestion operation
- Before update_document
- Before delete_document
- Before delete_collection

### 1.2 Add Health Check to GraphStore Class

**File:** `src/unified/graph_store.py`

**What to add:**
```python
async def health_check(self, timeout_ms: int = 2000) -> dict:
    """
    Lightweight Neo4j liveness check via Graphiti driver.

    Returns:
        {
            "status": "healthy" | "unhealthy" | "unavailable",
            "latency_ms": float or None,
            "error": str or None
        }
    """
    if self.graphiti is None:
        return {"status": "unavailable", "latency_ms": None, "error": "Not initialized"}

    try:
        start = time.perf_counter()
        result = await self.graphiti.driver.execute_query("RETURN 1 AS num")

        if not result.records or result.records[0]["num"] != 1:
            raise ValueError("Unexpected query result")

        latency = (time.perf_counter() - start) * 1000
        return {"status": "healthy", "latency_ms": round(latency, 2), "error": None}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {"status": "unhealthy", "latency_ms": round(latency, 2), "error": str(e)}
```

**Use cases:**
- Before any ingestion operation
- Before update_document
- Before delete_document
- Before delete_collection

### 1.3 Create Health Check Middleware Function

**File:** `src/mcp/tools.py` (new section at top)

**What to add:**
```python
async def ensure_databases_healthy(db: Database, graph_store: GraphStore = None) -> dict:
    """
    Check both databases are reachable before any write operation.

    Returns:
        None if healthy, otherwise returns error response dict for MCP client
    """
    # Check PostgreSQL (REQUIRED)
    pg_health = await db.health_check(timeout_ms=2000)
    if pg_health["status"] != "healthy":
        return {
            "error": "Database unavailable",
            "status": "service_unavailable",
            "message": f"PostgreSQL is {pg_health['status']}. Please wait and try again.",
            "details": {
                "postgres": pg_health,
                "retry_after_seconds": 30
            }
        }

    # Check Neo4j if initialized (REQUIRED for Option B)
    if graph_store is not None:
        graph_health = await graph_store.health_check(timeout_ms=2000)
        if graph_health["status"] == "unhealthy":
            return {
                "error": "Knowledge Graph unavailable",
                "status": "service_unavailable",
                "message": "Neo4j is temporarily unavailable. Please wait and try again.",
                "details": {
                    "postgres": pg_health,
                    "neo4j": graph_health,
                    "retry_after_seconds": 30
                }
            }

    return None  # All healthy
```

**Use in every ingestion/update/delete tool:**
```python
async def ingest_text_impl(...) -> Dict[str, Any]:
    # Check databases first
    health_error = await ensure_databases_healthy(db, graph_store)
    if health_error:
        return health_error

    # ... continue with normal logic
```

---

## Phase 2: Fail-Fast Server Initialization

### 2.1 Update MCP Server Lifespan

**File:** `src/mcp/server.py` (lifespan initialization)

**Current behavior:** Gracefully falls back to RAG-only if graph fails
**New behavior:** FAIL SERVER STARTUP if databases unavailable

**Change:**
```python
@asynccontextmanager
async def lifespan(app: FastMCP):
    # ... RAG initialization (mandatory)

    # Graph initialization (NOW MANDATORY)
    try:
        graphiti = Graphiti(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
        graph_store = GraphStore(graphiti)
        unified_mediator = UnifiedIngestionMediator(db, embedder, coll_mgr, graph_store)
        logger.info("✅ Knowledge Graph components initialized")
    except Exception as e:
        logger.error(f"❌ FATAL: Knowledge Graph initialization failed: {e}")
        logger.error("Neo4j must be running. Check:")
        logger.error(f"  - NEO4J_URI: {neo4j_uri}")
        logger.error(f"  - NEO4J_USER: {neo4j_user}")
        logger.error("  - Neo4j server is running and accepting connections")
        raise SystemExit(1)  # FAIL - don't boot

    yield {}
```

**Rationale:** If graph is mandatory, we can't start without it. Fail early.

---

## Phase 3: Remove Fallback Paths

### 3.1 Remove RAG-Only Fallback from Ingestion Tools

**Files affected:**
- `src/mcp/tools.py` - ingest_text_impl (lines 298-331)
- `src/mcp/tools.py` - ingest_url_impl (lines 656-667)
- `src/mcp/tools.py` - ingest_file_impl (lines 773-775)
- `src/mcp/tools.py` - ingest_directory_impl (lines 876-882)

**Current pattern:**
```python
if unified_mediator:
    result = await unified_mediator.ingest_text(...)
else:
    result = doc_store.ingest_document(...)  # ← REMOVE THIS
```

**New pattern:**
```python
# unified_mediator is guaranteed to exist (fail-fast in lifespan)
result = await unified_mediator.ingest_text(...)
```

### 3.2 Remove Optional Checks from Update/Delete

**File:** `src/ingestion/document_store.py`

**update_document() changes:**
- Change `graph_store: Optional[GraphStore] = None` to `graph_store: GraphStore`
- Remove `if graph_store is not None:` checks - always call graph cleanup
- Change comments from "optional" to "required"

**delete_document() changes:**
- Same as above

---

## Phase 4: Update MCP Docstrings

### 4.1 Docstring Refactoring Principles

**REMOVE (Implementation Details):**
- ❌ "Neo4j episodes"
- ❌ "Graphiti"
- ❌ "Knowledge graph"
- ❌ "Episode naming convention"
- ❌ "doc_{id}"
- ❌ Any mention of backend architecture

**KEEP (LLM Contract):**
- ✅ What this tool does
- ✅ Parameters and their impact on results
- ✅ What happens on success/failure
- ✅ Important caveats (requires confirmation, destructive, etc.)
- ✅ How results should be used
- ✅ Retry recommendations

### 4.2 Example Docstring Refactoring

**BEFORE (Implementation-focused):**
```python
def delete_collection(name: str, confirm: bool = False) -> dict:
    """
    Delete a collection and all its documents permanently.

    This operation cannot be undone. The collection, all documents, chunks,
    and graph episodes linked to those documents are permanently deleted.

    The system uses Neo4j episodes (named doc_{id}) which are cleaned up via
    Graphiti. Episode metadata contains document_id.

    Args:
        name: Collection name
        confirm: Must be True to proceed (prevents accidental deletion)

    Returns:
        {
            "deleted": bool,
            "name": str,
            "message": str (includes "N graph episodes cleaned"),
            "documents_affected": int
        }
    """
```

**AFTER (LLM Contract-focused):**
```python
def delete_collection(name: str, confirm: bool = False) -> dict:
    """
    ⚠️ DESTRUCTIVE: Permanently delete a collection and all its documents.

    This operation CANNOT be undone. Deletion includes:
    - The collection itself
    - All documents in this collection (if not in other collections)
    - All metadata and context associated with these documents

    **REQUIRED:** You must explicitly set confirm=True to proceed. This
    double-confirmation requirement exists to prevent accidental data loss.

    **Use Case:** Call this after explicit user confirmation. Never auto-delete.

    Args:
        name: Name of the collection to delete (must exist)
        confirm: Set to True only after user explicitly requests deletion
                 Set to False to get a preview of what will be deleted

    Returns:
        Success: {
            "deleted": true,
            "name": str,
            "message": str (e.g., "Collection 'X' and N documents deleted"),
            "documents_affected": int
        }
        Failure: {
            "error": str,
            "status": str (e.g., "not_found", "confirmation_required")
        }
    """
```

### 4.3 Docstrings to Update

**Collection Management:**
- `create_collection` - Focus on what collection is, not backend
- `delete_collection` - Remove graph cleanup details
- `update_collection_description` - Straightforward, mostly fine
- `get_collection_info` - Remove internal structure details

**Ingestion:**
- `ingest_text` - Remove "chunking", "graph", "episodes"
- `ingest_url` - Remove "crawl metadata", "episodes", "recrawl strategy"
- `ingest_file` - Remove chunking details
- `ingest_directory` - Remove implementation details

**Document Management:**
- `update_document` - Remove graph sync details
- `delete_document` - Remove graph cleanup details
- `list_documents` - Mostly fine
- `get_document_by_id` - Mostly fine

**Graph Queries:**
- `query_relationships` - Remove "Neo4j", "episodes", "Graphiti"
- `query_temporal` - Remove implementation details

---

## Phase 5: Testing Strategy

### 5.1 Tests to Update

**Existing tests that will fail (need fixing):**
1. `tests/integration/mcp/test_collections.py` - Already passing, no changes needed
2. `tests/integration/test_delete_collection_graph_cleanup.py` - Already passing, no changes needed

**New tests to add:**
1. Health check tests for Database class
2. Health check tests for GraphStore class
3. Health check middleware tests (simulating database down scenarios)
4. Server startup tests (verify fail-fast on graph unavailable)

### 5.2 Manual Testing Checklist

- [ ] Start server with both PostgreSQL and Neo4j running → Should start successfully
- [ ] Start server with PostgreSQL running but Neo4j down → Should fail startup
- [ ] Call ingest_text when Neo4j goes down mid-operation → Should return service_unavailable
- [ ] Call update_document when Neo4j is unreachable → Should return service_unavailable
- [ ] All health checks work on:
  - [ ] Local Docker
  - [ ] Supabase production
  - [ ] Fly.io deployment

---

## Implementation Order

1. **Week 1:**
   - Add health_check() to Database class
   - Add health_check() to GraphStore class
   - Create ensure_databases_healthy() middleware

2. **Week 2:**
   - Update all ingestion/update/delete tools with health check
   - Update server lifespan to fail-fast on graph init failure
   - Remove RAG-only fallback paths

3. **Week 3:**
   - Refactor MCP docstrings to remove implementation details
   - Add tests for health checks
   - Update documentation for Option B decision

4. **Week 4:**
   - Manual testing in all environments
   - Documentation updates (CLAUDE.md, getting-started)
   - Code review and refinement

---

## Success Criteria

- ✅ Server refuses to start if Neo4j is unavailable
- ✅ All ingestion operations fail gracefully if either DB unreachable
- ✅ Health check latency < 100ms in local environment
- ✅ Health check latency < 500ms in cloud environment
- ✅ MCP docstrings contain no implementation details
- ✅ MCP docstrings focus on LLM contract (inputs, outputs, caveats)
- ✅ All tests pass
- ✅ Manual testing successful in all environments

---

## Risk Assessment

### Low Risk:
- Adding health checks (non-breaking, just provides info)
- Failing server on graph initialization (we control startup)

### Medium Risk:
- Removing fallback paths (changes behavior, but that's the goal)
- Docstring updates (visible to LLMs, must be accurate)

### Mitigation:
- Comprehensive testing in all environments
- Clear documentation of change
- Gradual rollout (test in dev first)

---

## Questions for User Review

1. **Health check latency:** Should we cache results? Or check every time?
   - Current recommendation: Check every time (safety > performance)
   - Alternative: Cache for 30 seconds

2. **Retry strategy:** Should LLM tools handle retries or just return error?
   - Current recommendation: Return error, let LLM decide
   - Alternative: Retry with exponential backoff

3. **Error responses:** Should we include retry_after header in MCP response?
   - Current recommendation: Include retry_after_seconds in JSON body
   - Alternative: Use standard HTTP headers (if MCP supports)

4. **Startup behavior:** Hard fail (current plan) or graceful degradation?
   - Current recommendation: Hard fail (enforces Option B)
   - Alternative: Log warning and start with graph tools disabled

---

## Documentation References

- **Health Check Research:** `docs/HEALTH_CHECK_QUICK_REF.md`
- **Best Practices:** `docs/LIVENESS_CHECK_BEST_PRACTICES.md`
- **Implementation Checklist:** `docs/LIVENESS_CHECK_SUMMARY.md`
- **Flow Diagrams:** `docs/HEALTH_CHECK_FLOW.md`

---

**Next Step:** Review this plan and approve to proceed with implementation.
