# Health Check Research Documentation Index

**Research completed:** 2025-10-21
**Purpose:** Document best practices for lightweight liveness checks in RAG memory MCP server

## Documentation Files

### 1. Quick Reference Card (START HERE)
**File:** `HEALTH_CHECK_QUICK_REF.md` (5KB)
**Purpose:** One-page cheat sheet with copy-paste code examples
**Contents:**
- PostgreSQL property checks vs SELECT 1
- Neo4j verify_connectivity() vs RETURN 1
- Complete working example (copy-paste ready)
- Timeout recommendations
- Latency expectations
- Common mistakes to avoid

**Best for:** Developers implementing health checks (5 min read)

---

### 2. Implementation Summary
**File:** `LIVENESS_CHECK_SUMMARY.md` (9KB)
**Purpose:** Condensed implementation guide with code examples
**Contents:**
- TL;DR recommendations
- Implementation checklist
- Key design decisions (timeouts, retry, caching, response format)
- PostgreSQL and Neo4j code examples
- Environment-specific notes (Supabase, Docker, Fly.io)
- Performance expectations table
- Exception handling reference

**Best for:** Engineers planning implementation (10 min read)

---

### 3. Comprehensive Best Practices (DEEP DIVE)
**File:** `LIVENESS_CHECK_BEST_PRACTICES.md` (28KB)
**Purpose:** Complete research documentation with rationale
**Contents:**
- Executive summary
- PostgreSQL (psycopg3) deep dive
  - Connection status properties (closed, broken)
  - SELECT 1 query performance
  - Connection pooling considerations
  - Best practice for current implementation
- Neo4j (Python driver) deep dive
  - verify_connectivity() method
  - Lightweight health check queries
  - Graphiti integration
- Best practices summary
  - Timeout recommendations
  - Retry vs fail-fast
  - Connection pooling/reuse
  - Caching results
- Error handling (full exception taxonomy)
- Environment-specific considerations
  - Supabase (production)
  - Local Docker (development)
  - Fly.io (auto-scaling deployment)
- Implementation examples
  - MCP server health check tool
  - CLI health check command
- References and citations
- Appendix: Latency expectations table

**Best for:** Understanding rationale, troubleshooting, production tuning (30 min read)

---

### 4. Flow Diagram
**File:** `HEALTH_CHECK_FLOW.md` (2KB)
**Purpose:** Visual representation of health check logic
**Contents:**
- Mermaid diagram showing decision flow
- Response scenarios (healthy, degraded, unhealthy, unavailable)
- JSON response examples for each scenario

**Best for:** Understanding overall architecture (5 min read)

---

## Key Findings Summary

### PostgreSQL (psycopg3)

**Lightest check:** `connection.closed` property (instant, no network)
**Network validation:** `SELECT 1` query (0.1-5ms typical)
**Typical latency:**
- Local: 0.1-1ms
- Cloud (same region): 2-10ms
- Fly.io (warm): 5-20ms
- Fly.io (cold start): 2-5 seconds

**Recommendation:** Check `closed` property first, then `SELECT 1` if needed.

### Neo4j (Python Driver / Graphiti)

**Startup validation:** `driver.verify_connectivity()` (10-100ms, use once)
**Ongoing monitoring:** `RETURN 1` query via `execute_query()` (1-10ms typical)
**Typical latency:**
- Local: 1-5ms
- Cloud (same region): 10-30ms
- Fly.io (warm): 20-50ms
- Fly.io (cold start): 3-8 seconds

**Recommendation:** Use `verify_connectivity()` once at startup, then `RETURN 1` for monitoring.

### Graphiti Integration

- Access Neo4j driver via `graphiti.driver`
- All driver methods available (verify_connectivity, execute_query)
- Return `{status: "unavailable"}` if graph_store is None (RAG-only mode)

---

## Implementation Checklist

### PostgreSQL
- [ ] Use `connection.closed` for instant checks
- [ ] Use `connection.broken` to detect abnormal disconnects
- [ ] Execute `SELECT 1` for network validation
- [ ] Set query timeout: 1-5 seconds
- [ ] Catch `OperationalError` (connection) and `DatabaseError` (server)
- [ ] Return structured response: `{status, latency_ms, error}`

### Neo4j
- [ ] Use `driver.verify_connectivity()` once at startup
- [ ] Use `execute_query("RETURN 1")` for ongoing checks
- [ ] Reuse driver instance (don't create new drivers per check)
- [ ] Set connection timeout: 10-30 seconds
- [ ] Catch `ServiceUnavailable`, `AuthError`, `SessionExpired`
- [ ] Return structured response: `{status, latency_ms, error}`

### Overall System
- [ ] Combine PostgreSQL + Neo4j results
- [ ] Determine overall status (healthy/degraded/unhealthy)
- [ ] Include timestamp in ISO 8601 format
- [ ] Provide human-readable message
- [ ] Handle gracefully when Neo4j unavailable (RAG-only mode)

---

## Recommended Timeouts

| Operation | PostgreSQL | Neo4j |
|-----------|-----------|-------|
| Property check | 0ms (instant) | N/A |
| Query timeout | 1-5 seconds | 1-5 seconds |
| Connection timeout | 10-30 seconds | 10-30 seconds |
| Health check (total) | 2 seconds | 2 seconds |
| Cold start (Fly.io) | 10-30 seconds | 10-30 seconds |

---

## Response Format Standard

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-10-21T12:34:56.789Z",
  "components": {
    "postgres": {
      "status": "healthy",
      "latency_ms": 1.23,
      "error": null
    },
    "neo4j": {
      "status": "unavailable",
      "latency_ms": null,
      "error": "Not initialized"
    }
  },
  "message": "PostgreSQL healthy, Neo4j unavailable (RAG-only mode)"
}
```

**Status levels:**
- `healthy` = Core (PostgreSQL) working + (Neo4j working OR unavailable)
- `degraded` = Core working + Neo4j unhealthy
- `unhealthy` = Core component failed

---

## Next Steps (Implementation)

1. **Add health_check MCP tool** to `src/mcp/tools.py`
   - Use code from `HEALTH_CHECK_QUICK_REF.md`
   - Register as `@mcp.tool()`
   - Return standardized JSON response

2. **Add health CLI command** to `src/cli.py`
   - Use code from `LIVENESS_CHECK_BEST_PRACTICES.md` section 6
   - Add `@cli.command()` decorator
   - Pretty-print results with Rich

3. **Test in all environments:**
   - Local Docker (PostgreSQL + Neo4j)
   - Supabase production (PostgreSQL only)
   - Fly.io deployment (Supabase + optional Neo4j)

4. **Document in existing guides:**
   - Add health check section to `MCP_SERVER_GUIDE.md`
   - Update `README.md` with CLI health command
   - Add to deployment documentation

5. **Add to monitoring pipeline:**
   - Kubernetes liveness/readiness probes (if using k8s)
   - Load balancer health checks (if using LB)
   - Observability dashboard (Grafana, etc.)

---

## Research Methodology

This research was conducted by:
1. Analyzing current codebase (`src/core/database.py`, `src/unified/graph_store.py`, `src/mcp/server.py`)
2. Reviewing official documentation (psycopg3, Neo4j Python driver, Graphiti)
3. Searching best practices (Stack Overflow, AWS, Kubernetes guides)
4. Testing library APIs (inspecting available methods)
5. Synthesizing findings into actionable recommendations

---

## References

- psycopg3 Connection API: https://www.psycopg.org/psycopg3/docs/api/connections.html
- Neo4j Python Driver Manual: https://neo4j.com/docs/python-manual/current/
- Neo4j Python Driver API: https://neo4j.com/docs/api/python-driver/current/api.html
- Graphiti GitHub: https://github.com/getzep/graphiti
- Stack Overflow: Making sure psycopg2 database connection alive
- Stack Overflow: How to check connection from Python to Neo4j
- Neo4j Blog: Driver Best Practices
- AWS Builders Library: Implementing Health Checks
- Google Cloud: Kubernetes Health Check Best Practices

---

**Last updated:** 2025-10-21
**Researcher:** Claude (Anthropic AI)
**Project:** rag-memory (MCP server for RAG with PostgreSQL + Neo4j)
