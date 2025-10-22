# Liveness Check Implementation Summary

**Quick Reference Guide** - See `LIVENESS_CHECK_BEST_PRACTICES.md` for complete details

## TL;DR - What to Implement

### PostgreSQL Health Check (Recommended)

```python
# Fast check (instant, no network)
if conn.closed or conn.broken:
    return {"status": "unhealthy", "error": "Connection closed/broken"}

# Network validation (1-5ms typically)
with conn.cursor() as cur:
    cur.execute("SELECT 1")
    cur.fetchone()
```

**Latency:** 0.1-5ms (local/cloud), 10-50ms (cross-region)

### Neo4j Health Check (Recommended)

```python
# Startup validation only (use once)
driver.verify_connectivity()

# Ongoing health monitoring (lightweight)
result = await driver.execute_query("RETURN 1 AS num")
```

**Latency:** 1-10ms (local), 10-50ms (cloud)

---

## Implementation Checklist

### For PostgreSQL (psycopg3)

- [x] Use `connection.closed` property for instant checks
- [x] Use `connection.broken` to detect abnormal disconnects
- [x] Execute `SELECT 1` for network round-trip validation
- [x] Set query timeout: 1-5 seconds recommended
- [x] Catch `OperationalError` (connection), `DatabaseError` (server)
- [x] Return structured response: `{status, latency_ms, error}`

### For Neo4j (Python Driver)

- [x] Use `driver.verify_connectivity()` once at startup
- [x] Use `execute_query("RETURN 1")` for ongoing monitoring
- [x] Reuse driver instance (don't create new drivers per check)
- [x] Set connection timeout: 10-30 seconds
- [x] Catch `ServiceUnavailable`, `AuthError`, `SessionExpired`
- [x] Return structured response: `{status, latency_ms, error}`

### For Graphiti

- [x] Access Neo4j driver via `graphiti.driver`
- [x] All Neo4j driver methods available (verify_connectivity, execute_query)
- [x] Handle gracefully if graph_store is None (RAG-only mode)
- [x] Return `{status: "unavailable"}` if not initialized

---

## Key Design Decisions

### 1. Timeout Values

**PostgreSQL:**
- Property checks: No timeout (instant)
- Query timeout: 1-5 seconds
- Connection timeout: 10-30 seconds

**Neo4j:**
- `verify_connectivity()`: 10-30 seconds (startup only)
- Query timeout: 1-5 seconds
- Driver `connection_timeout`: 10-30 seconds

### 2. Retry Strategy

**Fail-fast approach (recommended):**
- Health checks return status immediately
- Don't retry inside health check
- Let caller decide retry strategy
- Prevents cascading delays

**When to retry (application-level):**
- Transient network issues (2-3 retries with backoff)
- Fly.io cold starts (1-2 retries with 5s delay)
- Connection pool exhausted (wait and retry)

### 3. Caching

**Short-term caching (30-60 seconds):**
- Development: 60 seconds OK
- Production monitoring: 10-30 seconds
- Load balancer probes: No cache (always fresh)

**Don't cache:**
- Before critical operations
- After detecting failures
- In CI/CD checks

### 4. Response Format

**Standardized structure:**
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
- `healthy`: All configured components working
- `degraded`: Core (PostgreSQL) working, optional (Neo4j) unavailable
- `unhealthy`: Core component failed

---

## Code Examples

### PostgreSQL Health Check

```python
def check_postgres_health(db: Database, timeout_ms: int = 2000) -> dict:
    """Lightweight PostgreSQL health check."""
    import time
    start = time.perf_counter()

    try:
        # Fast property check first
        if db._connection and (db._connection.closed or db._connection.broken):
            return {
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": "Connection closed/broken"
            }

        # Verify server responsiveness
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "error": None
        }

    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": str(e)
        }
```

### Neo4j Health Check

```python
async def check_neo4j_health(graphiti: Graphiti, timeout_ms: int = 2000) -> dict:
    """Lightweight Neo4j health check via Graphiti."""
    import time

    if graphiti is None:
        return {
            "status": "unavailable",
            "latency_ms": None,
            "error": "Knowledge Graph not initialized"
        }

    start = time.perf_counter()

    try:
        result = await graphiti.driver.execute_query("RETURN 1 AS num")
        records = result.records
        if not records or records[0]["num"] != 1:
            raise ValueError("Unexpected query result")

        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "error": None
        }

    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": str(e)
        }
```

### Combined Health Check (MCP Tool)

```python
@mcp.tool()
async def health_check(include_neo4j: bool = True) -> dict:
    """
    Check health of RAG memory databases.

    Returns overall system health status with component details.
    """
    from datetime import datetime

    components = {}

    # PostgreSQL check
    components["postgres"] = check_postgres_health(db, timeout_ms=2000)

    # Neo4j check (if enabled)
    if include_neo4j and graph_store:
        components["neo4j"] = await check_neo4j_health(
            graph_store.graphiti,
            timeout_ms=2000
        )
    else:
        components["neo4j"] = {
            "status": "unavailable",
            "latency_ms": None,
            "error": "Not initialized"
        }

    # Determine overall status
    postgres_healthy = components["postgres"]["status"] == "healthy"
    neo4j_status = components["neo4j"]["status"]

    if postgres_healthy and neo4j_status in ["healthy", "unavailable"]:
        overall = "healthy"
    elif postgres_healthy:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": components,
        "message": _format_message(components)
    }
```

---

## Environment-Specific Notes

### Supabase (Production PostgreSQL)

- Network latency: ~10-50ms (AWS us-east-1)
- Uses pgBouncer (transaction pooling)
- Requires `autocommit=True` and `sslmode="require"`
- Timeout: 5-10 seconds recommended

### Local Docker (Development)

- PostgreSQL: localhost:54320
- Neo4j: bolt://localhost:7687
- Network latency: ~0.1-1ms
- Timeout: 1-3 seconds sufficient

### Fly.io (Production Deployment)

- Auto-scaling with sleep mode
- Cold start: 2-8 seconds (first request)
- Warm: 5-20ms (same region as Supabase)
- Timeout: 10-30 seconds (account for cold starts)
- Retry strategy: 1-2 retries with 5s delay

---

## Performance Expectations

| Environment | PostgreSQL | Neo4j | Notes |
|-------------|-----------|-------|-------|
| Localhost | 0.1-1ms | 1-5ms | Same machine |
| Docker (local) | 0.5-2ms | 2-10ms | Container overhead |
| Cloud (same region) | 2-10ms | 10-30ms | Supabase + Fly.io |
| Fly.io (cold start) | 2-5s | 3-8s | First request after sleep |

---

## Exception Handling Reference

### PostgreSQL

```python
from psycopg import OperationalError, DatabaseError, InterfaceError

try:
    # Database operation
    pass
except OperationalError:
    # Connection/network issues
    return "Cannot connect to database"
except DatabaseError:
    # SQL errors, permissions
    return "Database error"
except InterfaceError:
    # Client-side errors
    return "Client error"
```

### Neo4j

```python
from neo4j import exceptions

try:
    # Neo4j operation
    pass
except exceptions.ServiceUnavailable:
    # Server unreachable
    return "Cannot connect to Neo4j"
except exceptions.AuthError:
    # Wrong credentials
    return "Authentication failed"
except exceptions.SessionExpired:
    # Session timeout
    return "Session expired"
except exceptions.TransientError:
    # Temporary error (retryable)
    return "Temporary error"
```

---

## Next Steps

1. **Add health_check MCP tool** to `src/mcp/tools.py`
2. **Add health CLI command** to `src/cli.py`
3. **Test in all environments:**
   - Local Docker
   - Supabase production
   - Fly.io deployment
4. **Document in MCP_SERVER_GUIDE.md**
5. **Add to monitoring/observability pipeline**

---

## References

- Full documentation: `docs/LIVENESS_CHECK_BEST_PRACTICES.md`
- psycopg3 API: https://www.psycopg.org/psycopg3/docs/api/connections.html
- Neo4j Python Driver: https://neo4j.com/docs/python-manual/current/
- Graphiti: https://github.com/getzep/graphiti
