# Health Check Flow Diagram

```mermaid
graph TD
    A[MCP Client] -->|calls health_check tool| B[MCP Server]
    B --> C{Check PostgreSQL}
    B --> D{Check Neo4j}
    
    C --> C1[Check conn.closed]
    C1 -->|closed| C2[Return unhealthy]
    C1 -->|open| C3[Execute SELECT 1]
    C3 -->|success| C4[Return healthy + latency]
    C3 -->|timeout/error| C5[Return unhealthy + error]
    
    D --> D1{graph_store exists?}
    D1 -->|no| D2[Return unavailable]
    D1 -->|yes| D3[Execute RETURN 1]
    D3 -->|success| D4[Return healthy + latency]
    D3 -->|timeout/error| D5[Return unhealthy + error]
    
    C2 --> E[Combine Results]
    C4 --> E
    C5 --> E
    D2 --> E
    D4 --> E
    D5 --> E
    
    E --> F{Determine Overall Status}
    F -->|PG healthy + Neo4j healthy/unavailable| G[Status: healthy]
    F -->|PG healthy + Neo4j unhealthy| H[Status: degraded]
    F -->|PG unhealthy| I[Status: unhealthy]
    
    G --> J[Return JSON Response]
    H --> J
    I --> J
    J --> A
```

## Response Flow

### Scenario 1: All Systems Healthy
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T12:34:56.789Z",
  "components": {
    "postgres": {"status": "healthy", "latency_ms": 1.23},
    "neo4j": {"status": "healthy", "latency_ms": 5.67}
  },
  "message": "All systems operational"
}
```

### Scenario 2: RAG-Only Mode (Neo4j Not Configured)
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T12:34:56.789Z",
  "components": {
    "postgres": {"status": "healthy", "latency_ms": 1.23},
    "neo4j": {"status": "unavailable", "latency_ms": null}
  },
  "message": "PostgreSQL healthy, Neo4j unavailable (RAG-only mode)"
}
```

### Scenario 3: Degraded (Neo4j Down)
```json
{
  "status": "degraded",
  "timestamp": "2025-10-21T12:34:56.789Z",
  "components": {
    "postgres": {"status": "healthy", "latency_ms": 1.23},
    "neo4j": {"status": "unhealthy", "latency_ms": 50.0, "error": "Service unavailable"}
  },
  "message": "PostgreSQL healthy, Neo4j unhealthy (degraded)"
}
```

### Scenario 4: System Down (PostgreSQL Failed)
```json
{
  "status": "unhealthy",
  "timestamp": "2025-10-21T12:34:56.789Z",
  "components": {
    "postgres": {"status": "unhealthy", "latency_ms": 100.0, "error": "Connection refused"},
    "neo4j": {"status": "unavailable", "latency_ms": null}
  },
  "message": "PostgreSQL unhealthy (system unavailable)"
}
```
