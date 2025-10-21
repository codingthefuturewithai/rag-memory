# Liveness Check Best Practices for PostgreSQL and Neo4j

**Research Date:** 2025-10-21
**Purpose:** Document lightweight liveness checks for MCP server health monitoring

## Executive Summary

**PostgreSQL (psycopg3):** Use `connection.closed` property for instant checks, or `SELECT 1` for network round-trip validation. Typical latency: 0.1-1ms (local), 1-20ms (network).

**Neo4j (Python driver):** Use `driver.verify_connectivity()` for initial setup checks. For ongoing health monitoring, use simple Cypher query `RETURN 1` via `execute_query()`. Typical latency: 1-10ms (local), 10-50ms (network).

**Recommendation:** Start with property checks (instant, no network), fall back to query-based checks only if property indicates connection is alive but you need to verify server responsiveness.

---

## 1. PostgreSQL (psycopg3) Liveness Checks

### Connection Status Properties

**Fastest option - No network round-trip:**
```python
import psycopg

conn = psycopg.connect(connection_string)

# Check if connection is closed (instant, no query)
if conn.closed:
    # Connection is not usable
    raise ConnectionError("PostgreSQL connection is closed")

# Check if connection was interrupted abnormally
if conn.broken:
    # Connection was closed uncleanly (network issue, server crash, etc.)
    raise ConnectionError("PostgreSQL connection is broken")
```

**Key Properties:**
- `connection.closed` - Returns `True` if connection has been terminated
- `connection.broken` - Returns `True` if connection was interrupted abnormally
- **Latency:** ~0ms (instant property check, no network I/O)
- **Use case:** Quick check before attempting database operations

### SELECT 1 Query

**Network round-trip validation:**
```python
import psycopg

def check_postgres_health(connection_string: str, timeout_ms: int = 1000) -> bool:
    """
    Lightweight PostgreSQL health check using SELECT 1.

    Args:
        connection_string: PostgreSQL connection string
        timeout_ms: Query timeout in milliseconds (default: 1000ms)

    Returns:
        True if database is reachable and responsive, False otherwise
    """
    try:
        # Create connection with timeout
        conn = psycopg.connect(
            connection_string,
            autocommit=True,
            options=f"-c statement_timeout={timeout_ms}"
        )

        # Quick property check first (no network)
        if conn.closed or conn.broken:
            return False

        # Execute minimal query to verify server responsiveness
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()

        conn.close()
        return result[0] == 1

    except psycopg.OperationalError as e:
        # Connection failed (network issue, server down, wrong credentials)
        logger.warning(f"PostgreSQL health check failed: {e}")
        return False
    except psycopg.DatabaseError as e:
        # Database-level error (server responded but query failed)
        logger.error(f"PostgreSQL database error: {e}")
        return False
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in PostgreSQL health check: {e}")
        return False
```

**Query Performance:**
- **Server execution time:** ~0.1ms (trivial query, no I/O)
- **Network latency:** 0.01-300ms depending on environment
  - Localhost: ~0.01ms
  - LAN: ~0.5ms
  - WiFi: ~5ms
  - Cloud (same region): ~1-5ms
  - Cloud (cross-region): ~20-100ms
  - Internet/VPN: ~50-300ms
- **Total latency:** Server time + (2 × network latency)

**When to use:**
- Initial connection validation
- Periodic health checks (e.g., every 30-60 seconds)
- Before critical operations where stale connections are unacceptable
- In Kubernetes liveness/readiness probes

**When NOT to use:**
- On every database operation (adds unnecessary overhead)
- When connection pooling handles validation (pools test connections on checkout)
- When property checks (`closed`, `broken`) are sufficient

### Connection Pooling Considerations

If using psycopg3's built-in connection pool (`psycopg.pool`):

```python
from psycopg_pool import ConnectionPool

# Pool automatically tests connections on checkout (pessimistic mode)
pool = ConnectionPool(
    connection_string,
    min_size=5,
    max_size=20,
    check=ConnectionPool.check_connection,  # Test connection before returning
    timeout=30.0  # Wait up to 30 seconds for connection
)

# Pool handles health checks automatically
with pool.connection() as conn:
    # Connection is guaranteed to be live
    pass
```

**Note:** The current codebase does NOT use connection pooling (simple single-connection model in `src/core/database.py`).

### Best Practice for Current Implementation

Based on `src/core/database.py` pattern:

```python
class Database:
    def health_check(self, timeout_ms: int = 1000) -> dict:
        """
        Check PostgreSQL health with minimal overhead.

        Returns:
            {
                "status": "healthy" | "unhealthy",
                "latency_ms": float,
                "error": str | None
            }
        """
        import time

        start = time.perf_counter()

        try:
            # Fast property check first
            if self._connection and (self._connection.closed or self._connection.broken):
                return {
                    "status": "unhealthy",
                    "latency_ms": 0.0,
                    "error": "Connection is closed or broken"
                }

            # Establish connection if needed
            conn = self.connect()

            # Verify server responsiveness
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

---

## 2. Neo4j (Python Driver) Liveness Checks

### verify_connectivity() Method

**Recommended for initial setup:**
```python
from neo4j import GraphDatabase, exceptions

def verify_neo4j_connection(uri: str, user: str, password: str) -> bool:
    """
    Verify Neo4j connectivity during initialization.

    This should be called once at startup, not repeatedly.
    """
    driver = None
    try:
        driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=10.0,  # 10 second timeout
            connection_acquisition_timeout=30.0
        )

        # Test connectivity (exchanges data with server)
        driver.verify_connectivity()
        return True

    except exceptions.ServiceUnavailable as e:
        logger.error(f"Neo4j service unavailable: {e}")
        return False
    except exceptions.AuthError as e:
        logger.error(f"Neo4j authentication failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Neo4j connection error: {e}")
        return False
    finally:
        if driver:
            driver.close()
```

**Characteristics:**
- Returns `None` on success, raises exception on failure
- Exchanges some data with server (not just TCP handshake)
- More thorough than simple query but slower
- **Latency:** ~10-100ms depending on network
- **Use case:** Startup validation, not ongoing monitoring

### Lightweight Health Check Query

**Recommended for ongoing health monitoring:**
```python
from neo4j import GraphDatabase, exceptions
import time

def check_neo4j_health(driver, timeout_ms: int = 5000) -> dict:
    """
    Lightweight Neo4j health check using RETURN 1 query.

    Args:
        driver: Neo4j driver instance (reuse existing driver)
        timeout_ms: Query timeout in milliseconds (default: 5000ms)

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "latency_ms": float,
            "error": str | None
        }
    """
    start = time.perf_counter()

    try:
        # Execute simple query to verify connectivity
        result = driver.execute_query(
            "RETURN 1 AS num",
            database_="neo4j",  # Default database
            routing_="r",  # Read routing (lighter than write)
        )

        # Verify result
        records = result.records
        if not records or records[0]["num"] != 1:
            raise ValueError("Unexpected query result")

        latency = (time.perf_counter() - start) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency, 2),
            "error": None
        }

    except exceptions.ServiceUnavailable as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": f"Service unavailable: {e}"
        }
    except exceptions.SessionExpired as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": f"Session expired: {e}"
        }
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": f"Unexpected error: {e}"
        }
```

**Query Performance:**
- **Server execution time:** ~1-5ms (simple RETURN, no graph traversal)
- **Network latency:** Same as PostgreSQL (0.01-300ms)
- **Total latency:** Typically 1-10ms (local), 10-50ms (cloud)

**Why `RETURN 1` over `verify_connectivity()`:**
- Faster (no driver initialization overhead)
- Reuses existing driver connection
- Validates actual query execution path
- Lower resource usage on server

### Graphiti Integration

For the current implementation using Graphiti:

```python
from graphiti_core import Graphiti
from graphiti_core.driver import Neo4jDriver

async def check_graphiti_health(graphiti: Graphiti, timeout_ms: int = 5000) -> dict:
    """
    Health check for Graphiti/Neo4j connection.

    Args:
        graphiti: Graphiti instance
        timeout_ms: Query timeout in milliseconds

    Returns:
        {
            "status": "healthy" | "unhealthy" | "unavailable",
            "latency_ms": float | None,
            "error": str | None
        }
    """
    import time

    # Check if graph_store exists
    if graphiti is None:
        return {
            "status": "unavailable",
            "latency_ms": None,
            "error": "Knowledge Graph not initialized"
        }

    start = time.perf_counter()

    try:
        # Execute simple query via Graphiti's driver
        result = await graphiti.driver.execute_query(
            "RETURN 1 AS num"
        )

        # Verify result
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

**Note:** Graphiti's `Neo4jDriver` wraps the official neo4j Python driver, so all driver methods (`verify_connectivity()`, `execute_query()`) are available via `graphiti.driver`.

---

## 3. Best Practices Summary

### Timeout Recommendations

**PostgreSQL:**
- Property checks (`closed`, `broken`): No timeout needed (instant)
- `SELECT 1` query timeout: 1000-5000ms (1-5 seconds)
- Connection timeout: 10-30 seconds (initial connection only)

**Neo4j:**
- `verify_connectivity()`: 10-30 seconds (startup only)
- `RETURN 1` query timeout: 1000-5000ms (1-5 seconds)
- Connection timeout: 10-30 seconds (driver creation)
- `liveness_check_timeout`: 0 (always test) or 1000ms (test if idle >1s)

### Retry vs Fail-Fast

**Recommended: Fail-fast with graceful degradation**

```python
def get_database_health() -> dict:
    """
    Check all database health with fail-fast approach.
    """
    # PostgreSQL check
    postgres_health = check_postgres_health(connection_string, timeout_ms=2000)

    # Neo4j check (if available)
    neo4j_health = {"status": "unavailable"}
    if graph_store:
        neo4j_health = await check_neo4j_health(graph_store.graphiti.driver, timeout_ms=2000)

    return {
        "postgres": postgres_health,
        "neo4j": neo4j_health,
        "overall": "healthy" if postgres_health["status"] == "healthy" else "degraded"
    }
```

**Why fail-fast:**
- Health checks should not retry (that's the application's job)
- Timeouts prevent hanging indefinitely
- Return status quickly so caller can decide retry strategy
- Allows for graceful degradation (RAG-only mode if graph unavailable)

**When to retry (application-level, not health check):**
- Transient network issues (retry 2-3 times with backoff)
- Server temporarily overloaded (retry after delay)
- Connection pool exhausted (wait and retry)

### Connection Pooling/Reuse

**PostgreSQL (current implementation):**
- Simple single connection model in `src/core/database.py`
- Connection cached in `self._connection`
- Reused across operations
- **No pooling currently implemented**

**Recommendation for production:**
Consider adding psycopg3 connection pooling for better resource management:
```python
from psycopg_pool import ConnectionPool

pool = ConnectionPool(
    connection_string,
    min_size=5,
    max_size=20,
    check=ConnectionPool.check_connection  # Auto-validates on checkout
)
```

**Neo4j (current implementation):**
- Single driver instance created in `lifespan()` (MCP server)
- Driver internally manages connection pool
- **Already using connection pooling** (driver default behavior)

**Best practice:**
- Create driver once at startup
- Reuse driver for entire application lifetime
- Let driver manage pool internally
- Don't create new drivers for health checks

### Caching Results

**Short-term caching recommended:**
```python
from datetime import datetime, timedelta

class HealthCheckCache:
    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds
        self._cache = {}

    def get(self, key: str):
        if key in self._cache:
            result, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return result
        return None

    def set(self, key: str, value: dict):
        self._cache[key] = (value, datetime.now())

# Usage
health_cache = HealthCheckCache(ttl_seconds=30)

def get_cached_health():
    # Check cache first
    cached = health_cache.get("postgres")
    if cached:
        return cached

    # Run actual check
    result = check_postgres_health(...)
    health_cache.set("postgres", result)
    return result
```

**Cache TTL recommendations:**
- Development: 30-60 seconds
- Production (internal monitoring): 10-30 seconds
- Production (user-facing health endpoint): 5-10 seconds
- Load balancer health checks: No cache (always fresh)

**When NOT to cache:**
- Before critical operations (e.g., financial transactions)
- After detecting connection issues (need fresh status)
- In CI/CD health checks (accuracy over speed)

---

## 4. Error Handling

### PostgreSQL Exceptions

```python
import psycopg
from psycopg import OperationalError, DatabaseError, InterfaceError

try:
    # Database operation
    pass
except OperationalError as e:
    # Connection/network issues
    # - Server not reachable
    # - Authentication failed
    # - Network timeout
    logger.error(f"PostgreSQL connection error: {e}")
    return {"status": "unhealthy", "error": "Cannot connect to database"}

except DatabaseError as e:
    # Database-level errors
    # - SQL syntax error
    # - Permission denied
    # - Constraint violation
    logger.error(f"PostgreSQL database error: {e}")
    return {"status": "unhealthy", "error": "Database error"}

except InterfaceError as e:
    # Client-side errors
    # - Invalid parameter
    # - Programming error
    logger.error(f"PostgreSQL interface error: {e}")
    return {"status": "unhealthy", "error": "Client error"}

except Exception as e:
    # Unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return {"status": "unhealthy", "error": "Unknown error"}
```

### Neo4j Exceptions

```python
from neo4j import exceptions

try:
    # Neo4j operation
    pass
except exceptions.ServiceUnavailable as e:
    # Server not reachable
    # - Network down
    # - Server stopped
    # - Wrong URI
    logger.error(f"Neo4j service unavailable: {e}")
    return {"status": "unhealthy", "error": "Cannot connect to Neo4j"}

except exceptions.AuthError as e:
    # Authentication failed
    # - Wrong username/password
    # - Expired credentials
    logger.error(f"Neo4j auth error: {e}")
    return {"status": "unhealthy", "error": "Authentication failed"}

except exceptions.SessionExpired as e:
    # Session/transaction expired
    # - Long-running transaction timeout
    # - Cluster reconfiguration
    logger.error(f"Neo4j session expired: {e}")
    return {"status": "unhealthy", "error": "Session expired"}

except exceptions.TransientError as e:
    # Temporary error (safe to retry)
    # - Cluster leader changed
    # - Temporary resource unavailable
    logger.warning(f"Neo4j transient error: {e}")
    return {"status": "unhealthy", "error": "Temporary error (retryable)"}

except Exception as e:
    # Unexpected errors
    logger.error(f"Unexpected Neo4j error: {e}", exc_info=True)
    return {"status": "unhealthy", "error": "Unknown error"}
```

### MCP Client Response Format

**Recommended response structure:**
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
            "status": "unavailable",  # Not configured
            "latency_ms": None,
            "error": "Knowledge Graph not initialized"
        }
    },
    "message": "PostgreSQL healthy, Neo4j unavailable (RAG-only mode)"
}
```

**Status definitions:**
- `healthy`: All configured components working
- `degraded`: Core component (PostgreSQL) working, optional components unavailable
- `unhealthy`: Core component failed

---

## 5. Environment-Specific Considerations

### Supabase (Production)

**Connection characteristics:**
- Network latency: ~10-50ms (AWS us-east-1)
- Connection pooling: Managed by Supabase (pgBouncer)
- SSL/TLS: Required
- Timeout recommendations: 5-10 seconds

**Special considerations:**
- Supabase uses connection pooling (pgBouncer in transaction mode)
- Some PostgreSQL features unavailable in transaction mode
- Health checks should use simple `SELECT 1` (no session state)

**Example:**
```python
# Supabase-friendly health check
conn = psycopg.connect(
    connection_string,
    autocommit=True,  # Required for transaction-mode pooling
    sslmode="require"  # Required by Supabase
)
```

### Local Docker (Development)

**Connection characteristics:**
- Network latency: ~0.1-1ms (localhost)
- Direct connection: No pooling layer
- Timeout recommendations: 1-3 seconds

**PostgreSQL (port 54320):**
```python
connection_string = "postgresql://postgres:postgres@localhost:54320/rag_memory"
```

**Neo4j (port 7687):**
```python
uri = "bolt://localhost:7687"
user = "neo4j"
password = "graphiti-password"
```

### Fly.io (Production Deployment)

**Connection characteristics:**
- Same region: ~5-20ms
- Cross-region: ~50-200ms
- Auto-scaling: Machines can sleep (cold start)
- Timeout recommendations: 10-30 seconds (account for cold starts)

**Cold start handling:**
```python
def check_flyio_health(max_retries=2, retry_delay=5.0):
    """
    Health check with retry for Fly.io cold starts.
    """
    for attempt in range(max_retries + 1):
        result = check_postgres_health(timeout_ms=10000)

        if result["status"] == "healthy":
            return result

        if attempt < max_retries:
            logger.info(f"Retry {attempt + 1}/{max_retries} after {retry_delay}s...")
            time.sleep(retry_delay)

    return result
```

---

## 6. Implementation Examples

### MCP Server Health Check Tool

**Add to `src/mcp/tools.py`:**

```python
@mcp.tool()
def health_check(include_neo4j: bool = True) -> dict:
    """
    Check health of RAG memory databases.

    Args:
        include_neo4j: Whether to check Neo4j (default: True)

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "timestamp": str,  # ISO 8601
            "components": {
                "postgres": {...},
                "neo4j": {...}
            }
        }
    """
    from datetime import datetime
    import time

    timestamp = datetime.utcnow().isoformat() + "Z"
    components = {}

    # PostgreSQL health check
    postgres_start = time.perf_counter()
    try:
        # Fast property check
        if db._connection and (db._connection.closed or db._connection.broken):
            components["postgres"] = {
                "status": "unhealthy",
                "latency_ms": 0.0,
                "error": "Connection is closed or broken"
            }
        else:
            # Verify server responsiveness
            conn = db.connect()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

            latency = (time.perf_counter() - postgres_start) * 1000
            components["postgres"] = {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "error": None
            }
    except Exception as e:
        latency = (time.perf_counter() - postgres_start) * 1000
        components["postgres"] = {
            "status": "unhealthy",
            "latency_ms": round(latency, 2),
            "error": str(e)
        }

    # Neo4j health check (if enabled)
    if include_neo4j and graph_store:
        neo4j_start = time.perf_counter()
        try:
            result = await graph_store.graphiti.driver.execute_query("RETURN 1 AS num")
            records = result.records
            if records and records[0]["num"] == 1:
                latency = (time.perf_counter() - neo4j_start) * 1000
                components["neo4j"] = {
                    "status": "healthy",
                    "latency_ms": round(latency, 2),
                    "error": None
                }
            else:
                raise ValueError("Unexpected query result")
        except Exception as e:
            latency = (time.perf_counter() - neo4j_start) * 1000
            components["neo4j"] = {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": str(e)
            }
    else:
        components["neo4j"] = {
            "status": "unavailable",
            "latency_ms": None,
            "error": "Knowledge Graph not initialized"
        }

    # Determine overall status
    postgres_healthy = components["postgres"]["status"] == "healthy"
    neo4j_status = components["neo4j"]["status"]

    if postgres_healthy and (neo4j_status in ["healthy", "unavailable"]):
        overall_status = "healthy"
    elif postgres_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "timestamp": timestamp,
        "components": components,
        "message": _format_health_message(components)
    }

def _format_health_message(components: dict) -> str:
    """Format human-readable health message."""
    postgres_status = components["postgres"]["status"]
    neo4j_status = components["neo4j"]["status"]

    if postgres_status == "healthy" and neo4j_status == "healthy":
        return "All systems operational"
    elif postgres_status == "healthy" and neo4j_status == "unavailable":
        return "PostgreSQL healthy, Neo4j unavailable (RAG-only mode)"
    elif postgres_status == "healthy" and neo4j_status == "unhealthy":
        return "PostgreSQL healthy, Neo4j unhealthy (degraded)"
    else:
        return "PostgreSQL unhealthy (system unavailable)"
```

### CLI Health Check Command

**Add to `src/cli.py`:**

```python
@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed health info")
def health(verbose: bool):
    """Check database health."""
    from datetime import datetime
    import time

    console.print("\n[bold]RAG Memory Health Check[/bold]\n")

    # PostgreSQL check
    console.print("[cyan]Checking PostgreSQL...[/cyan]")
    pg_start = time.perf_counter()
    try:
        db = get_database()
        conn = db.connect()

        if conn.closed or conn.broken:
            console.print("[red]✗ PostgreSQL: Connection closed/broken[/red]")
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

            latency = (time.perf_counter() - pg_start) * 1000
            console.print(f"[green]✓ PostgreSQL: Healthy ({latency:.2f}ms)[/green]")

            if verbose:
                stats = db.get_stats()
                console.print(f"  Documents: {stats['source_documents']}")
                console.print(f"  Chunks: {stats['chunks']}")
                console.print(f"  Collections: {stats['collections']}")
                console.print(f"  Size: {stats['database_size']}")
    except Exception as e:
        latency = (time.perf_counter() - pg_start) * 1000
        console.print(f"[red]✗ PostgreSQL: Unhealthy ({latency:.2f}ms)[/red]")
        console.print(f"  Error: {e}")

    # Neo4j check (if configured)
    console.print("\n[cyan]Checking Neo4j...[/cyan]")
    neo4j_uri = os.getenv("NEO4J_URI")
    if not neo4j_uri:
        console.print("[yellow]○ Neo4j: Not configured[/yellow]")
    else:
        neo4j_start = time.perf_counter()
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
                connection_timeout=5.0
            )

            result = driver.execute_query("RETURN 1 AS num")
            driver.close()

            latency = (time.perf_counter() - neo4j_start) * 1000
            console.print(f"[green]✓ Neo4j: Healthy ({latency:.2f}ms)[/green]")
        except Exception as e:
            latency = (time.perf_counter() - neo4j_start) * 1000
            console.print(f"[red]✗ Neo4j: Unhealthy ({latency:.2f}ms)[/red]")
            console.print(f"  Error: {e}")
```

---

## 7. References

### Documentation

- [psycopg3 Connection API](https://www.psycopg.org/psycopg3/docs/api/connections.html)
- [Neo4j Python Driver Manual](https://neo4j.com/docs/python-manual/current/)
- [Neo4j Python Driver API](https://neo4j.com/docs/api/python-driver/current/api.html)
- [Graphiti GitHub](https://github.com/getzep/graphiti)

### Stack Overflow Discussions

- [Making sure psycopg2 database connection alive](https://stackoverflow.com/questions/1281875/making-sure-that-psycopg2-database-connection-alive)
- [How to check connection from Python to Neo4j](https://stackoverflow.com/questions/56708423/how-to-check-connection-from-python-to-neo4j)

### Best Practices Articles

- [Neo4j Driver Best Practices](https://neo4j.com/blog/developer/neo4j-driver-best-practices/)
- [AWS Implementing Health Checks](https://aws.amazon.com/builders-library/implementing-health-checks/)
- [Kubernetes Health Check Best Practices](https://cloud.google.com/blog/products/containers-kubernetes/kubernetes-best-practices-setting-up-health-checks-with-readiness-and-liveness-probes)

---

## 8. Appendix: Latency Expectations Table

| Environment | PostgreSQL (SELECT 1) | Neo4j (RETURN 1) | Notes |
|-------------|----------------------|------------------|-------|
| Localhost | 0.1-1ms | 1-5ms | Same machine, no network |
| Docker (local) | 0.5-2ms | 2-10ms | Container overhead |
| LAN | 1-5ms | 5-20ms | Same physical network |
| WiFi | 5-20ms | 10-50ms | Wireless overhead |
| Cloud (same region) | 2-10ms | 10-30ms | AWS us-east-1, Supabase |
| Cloud (cross-region) | 20-100ms | 50-200ms | US East → US West |
| Internet/VPN | 50-300ms | 100-500ms | Variable, depends on route |
| Fly.io (warm) | 5-20ms | 20-50ms | Same region as Supabase |
| Fly.io (cold start) | 2000-5000ms | 3000-8000ms | First request after sleep |

**Note:** These are typical ranges. Actual latency varies based on:
- Server load
- Network congestion
- Query complexity
- Connection pool state
- SSL/TLS overhead
- Geographic distance
