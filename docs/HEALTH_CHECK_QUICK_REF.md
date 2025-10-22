# Health Check Quick Reference Card

**One-page cheat sheet for implementing health checks**

## PostgreSQL (psycopg3)

### Option 1: Property Check (Instant, No Network)
```python
if conn.closed or conn.broken:
    return "unhealthy"
```
**Latency:** 0ms | **Use:** Quick validation before operations

### Option 2: SELECT 1 (Network Round-Trip)
```python
with conn.cursor() as cur:
    cur.execute("SELECT 1")
    cur.fetchone()
```
**Latency:** 0.1-5ms | **Use:** Verify server responsiveness

### Exceptions to Catch
```python
from psycopg import OperationalError, DatabaseError

try:
    # ... database operation
except OperationalError:  # Connection/network issues
    pass
except DatabaseError:     # SQL/permission errors
    pass
```

---

## Neo4j (Python Driver)

### Option 1: verify_connectivity() (Startup Only)
```python
driver.verify_connectivity()  # Raises exception on failure
```
**Latency:** 10-100ms | **Use:** Initial setup validation

### Option 2: RETURN 1 Query (Ongoing Monitoring)
```python
result = await driver.execute_query("RETURN 1 AS num")
records = result.records  # Verify records[0]["num"] == 1
```
**Latency:** 1-10ms | **Use:** Lightweight health checks

### Exceptions to Catch
```python
from neo4j import exceptions

try:
    # ... neo4j operation
except exceptions.ServiceUnavailable:  # Server unreachable
    pass
except exceptions.AuthError:          # Wrong credentials
    pass
except exceptions.SessionExpired:     # Timeout/reconfiguration
    pass
```

---

## Graphiti (Neo4j Wrapper)

### Check if Available
```python
if graphiti is None:
    return {"status": "unavailable"}
```

### Access Neo4j Driver
```python
result = await graphiti.driver.execute_query("RETURN 1 AS num")
# All Neo4j driver methods available via graphiti.driver
```

---

## Recommended Timeouts

| Operation | PostgreSQL | Neo4j | Environment |
|-----------|-----------|-------|-------------|
| Property check | 0ms | N/A | All |
| Query timeout | 1-5s | 1-5s | Local/cloud |
| Connection timeout | 10-30s | 10-30s | Initial connection |
| Health check (total) | 2s | 2s | Production |
| Cold start (Fly.io) | 10-30s | 10-30s | Auto-scaling |

---

## Response Format

```python
{
    "status": "healthy" | "degraded" | "unhealthy",
    "timestamp": "2025-10-21T12:34:56.789Z",
    "components": {
        "postgres": {
            "status": "healthy",
            "latency_ms": 1.23,
            "error": None
        },
        "neo4j": {
            "status": "unavailable",  # or healthy/unhealthy
            "latency_ms": None,       # or float
            "error": None             # or str
        }
    },
    "message": "PostgreSQL healthy, Neo4j unavailable (RAG-only mode)"
}
```

**Status Logic:**
- `healthy` = PostgreSQL healthy + (Neo4j healthy OR unavailable)
- `degraded` = PostgreSQL healthy + Neo4j unhealthy
- `unhealthy` = PostgreSQL unhealthy

---

## Complete Example (Copy-Paste Ready)

```python
import time
from datetime import datetime
from psycopg import OperationalError, DatabaseError
from neo4j import exceptions

def check_postgres_health(db, timeout_ms=2000):
    """Check PostgreSQL health."""
    start = time.perf_counter()
    try:
        if db._connection and (db._connection.closed or db._connection.broken):
            return {"status": "unhealthy", "latency_ms": 0.0, "error": "Connection closed"}

        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

        latency = (time.perf_counter() - start) * 1000
        return {"status": "healthy", "latency_ms": round(latency, 2), "error": None}
    except (OperationalError, DatabaseError) as e:
        latency = (time.perf_counter() - start) * 1000
        return {"status": "unhealthy", "latency_ms": round(latency, 2), "error": str(e)}

async def check_neo4j_health(graphiti, timeout_ms=2000):
    """Check Neo4j health via Graphiti."""
    if graphiti is None:
        return {"status": "unavailable", "latency_ms": None, "error": "Not initialized"}

    start = time.perf_counter()
    try:
        result = await graphiti.driver.execute_query("RETURN 1 AS num")
        if not result.records or result.records[0]["num"] != 1:
            raise ValueError("Unexpected result")

        latency = (time.perf_counter() - start) * 1000
        return {"status": "healthy", "latency_ms": round(latency, 2), "error": None}
    except exceptions.ServiceUnavailable as e:
        latency = (time.perf_counter() - start) * 1000
        return {"status": "unhealthy", "latency_ms": round(latency, 2), "error": str(e)}

async def health_check(db, graphiti=None):
    """Combined health check."""
    components = {
        "postgres": check_postgres_health(db, timeout_ms=2000),
        "neo4j": await check_neo4j_health(graphiti, timeout_ms=2000)
    }

    pg_ok = components["postgres"]["status"] == "healthy"
    neo4j_status = components["neo4j"]["status"]

    if pg_ok and neo4j_status in ["healthy", "unavailable"]:
        overall = "healthy"
    elif pg_ok:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": components
    }
```

---

## Latency Cheat Sheet

| Environment | PostgreSQL | Neo4j |
|-------------|-----------|-------|
| Localhost | 0.1-1ms | 1-5ms |
| Docker (local) | 0.5-2ms | 2-10ms |
| Cloud (same region) | 2-10ms | 10-30ms |
| Fly.io (warm) | 5-20ms | 20-50ms |
| Fly.io (cold start) | 2-5s | 3-8s |

---

## When to Use Each Check

### Property Check (`conn.closed`)
- Before every critical operation
- When network latency is unacceptable
- In tight loops
- **Cost:** Free (instant)

### SELECT 1 / RETURN 1
- Periodic health monitoring (30-60s interval)
- Load balancer probes
- Startup validation
- **Cost:** ~1-10ms + network latency

### verify_connectivity()
- One-time startup validation
- After configuration changes
- **Cost:** ~10-100ms (heavier than query)

---

## Don't Do This

❌ Create new driver per health check (reuse existing!)
❌ Retry inside health check (fail-fast, let caller retry)
❌ Execute complex queries (SELECT 1 / RETURN 1 only)
❌ Cache for >60 seconds (stale data)
❌ Skip error handling (always catch exceptions)
❌ Use in high-frequency loops (adds overhead)

---

## See Also

- Full documentation: `LIVENESS_CHECK_BEST_PRACTICES.md` (28KB)
- Summary: `LIVENESS_CHECK_SUMMARY.md` (9KB)
- Flow diagram: `HEALTH_CHECK_FLOW.md` (2KB)
