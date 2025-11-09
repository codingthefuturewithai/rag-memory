# Knowledge Graph

RAG Memory includes knowledge graph capabilities via Graphiti and Neo4j. This enables entity extraction, relationship tracking, and temporal reasoning alongside vector search.

## What is a Knowledge Graph?

A knowledge graph extracts entities and relationships from text, storing them as nodes and edges in a graph database. This complements vector search by providing structured relationship data.

### Vector Search vs Knowledge Graph

**Vector Search (RAG):**
- Finds similar content by meaning
- Returns: "Here are documents about authentication"
- Good for: "What information exists?"

**Knowledge Graph:**
- Finds connections between concepts
- Returns: "Authentication service connects to these 5 services"
- Good for: "How are things related?"

**Together:**
- Vector search finds content
- Graph reveals relationships
- Complete knowledge system

## Architecture

### Dual Storage

Both PostgreSQL and Neo4j are required. Every document ingested goes to both stores:

```
Document Ingestion
    ↓
RAG Store (PostgreSQL)     Graph Store (Neo4j)
  - Full text               - Entities
  - Chunks                  - Relationships
  - Embeddings              - Temporal data
```

Both stores stay synchronized automatically on all create, update, and delete operations.

### What Gets Stored

**RAG Store (PostgreSQL):**
- Source documents (full text)
- Document chunks
- Vector embeddings (1536 dimensions)
- Metadata as JSONB

**Graph Store (Neo4j):**
- Entities extracted from text
- Relationships between entities
- Temporal information (valid_from, valid_until)
- Episode nodes linking to source documents

## Setup

### Local (Docker)

```bash
# Start Neo4j container
docker-compose -f deploy/docker/compose/docker-compose.dev.yml up -d

# Verify running
docker ps | grep neo4j

# Access Neo4j Browser
# URL: http://localhost:7474
# Username: neo4j
# Password: graphiti-password
```

### Environment Variables

Required configuration:

```bash
# In config.yaml or environment
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=graphiti-password
```

### Graphiti Models

Configure which models Graphiti uses for entity extraction. See Graphiti documentation for available models and recommendations: https://docs.graphiti.ai/

```yaml
# In config.yaml
server:
  graphiti_model: "your-model-choice"
  graphiti_small_model: "your-model-choice"
```

Or via environment:
```bash
export GRAPHITI_MODEL="your-model-choice"
export GRAPHITI_SMALL_MODEL="your-model-choice"
```

## How It Works

### Ingestion Flow

When you ingest a document:

1. **RAG Processing:**
   - Document split into chunks
   - Each chunk embedded
   - Stored in PostgreSQL with vectors

2. **Graph Processing:**
   - Entities extracted via LLM
   - Relationships identified
   - Episode node created
   - Stored in Neo4j graph

3. **Synchronization:**
   - Both processes happen automatically
   - No manual coordination needed

Example:

```bash
rag ingest text "React is a JavaScript library for building UIs with hooks" \
  --collection tech-docs
```

**RAG creates:**
- Source document record
- Chunks with embeddings
- Searchable via similarity

**Graph creates:**
- Entities: React, JavaScript, hooks, UIs
- Relationships: React -[USES]-> hooks
- Episode: doc_42 linking to source

### Automatic Synchronization

All operations keep RAG and Graph in sync:

**Document Update:**
```bash
rag document update 42 --content "Updated content"
```
- RAG: Re-chunks and re-embeds
- Graph: Deletes old episode, creates new one

**Document Delete:**
```bash
rag document delete 42
```
- RAG: Removes document and chunks
- Graph: Removes episode and relationships

**Re-Crawl:**
```bash
rag ingest url https://docs.example.com --mode recrawl
```
- RAG: Deletes old pages, ingests new
- Graph: Deletes old episodes, creates new

## Query Tools

### query_relationships

Find entity relationships using natural language.

**Usage:**
```bash
rag graph query-relationships "Which services depend on authentication?"
```

**Parameters:**
- `query` - Natural language question
- `collection_name` - Optional collection filter
- `num_results` - Max results (default: 5)
- `threshold` - Relevance filter (default: 0.35)

**Returns:**
```
Relationships Found: 3

[1] UserService → DEPENDS_ON → AuthenticationAPI
    Fact: UserService depends on AuthenticationAPI for login validation
    Valid: 2025-10-20 to present

[2] PaymentService → USES → AuthenticationAPI
    Fact: PaymentService uses AuthenticationAPI to verify user identity
    Valid: 2025-10-15 to present

[3] AdminPanel → REQUIRES → AuthenticationAPI
    Fact: AdminPanel requires AuthenticationAPI for access control
    Valid: 2025-10-01 to present
```

### query_temporal

Track how knowledge evolved over time.

**Usage:**
```bash
rag graph query-temporal "How has authentication changed?"
```

**Parameters:**
- `query` - Question about evolution
- `collection_name` - Optional collection filter
- `num_results` - Max timeline items (default: 10)
- `threshold` - Relevance filter (default: 0.35)
- `valid_from` - Start date (ISO 8601)
- `valid_until` - End date (ISO 8601)

**Returns:**
```
Timeline: 3 events

[1] CURRENT (2025-10-15 - present)
    Fact: API uses OAuth 2.0 authentication
    Relationship: API → USES → OAuth 2.0
    Status: current

[2] SUPERSEDED (2025-09-01 - 2025-10-15)
    Fact: API used Basic Authentication
    Relationship: API → USES → Basic Auth
    Status: superseded

[3] SUPERSEDED (2025-01-01 - 2025-09-01)
    Fact: API used API key authentication
    Relationship: API → USES → API Keys
    Status: superseded
```

## Use Cases

### Relationship Discovery

Understand how concepts connect:

```
Query: "Which projects depend on the authentication service?"
Result: ProjectA, ProjectB, ProjectC all connect to AuthService
Action: Examine each project's integration details
```

### Temporal Reasoning

Track system evolution:

```
Query: "When did we add rate limiting?"
Result: Timeline showing rate limiting added 2025-10-15
Action: Review documentation from that time
```

### Multi-Hop Queries

Find indirect connections:

```
Query: "Which services using payment processor also connect to notifications?"
Result: OrderService connects to both
Action: Review OrderService architecture
```

## Configuration Options

### Reflexion

Graphiti supports recursive entity extraction. After initial extraction, the LLM reviews results and re-extracts with hints about missed entities.

**Configuration:**
```yaml
server:
  max_reflexion_iterations: 0  # 0-3 recommended
```

**Trade-offs:**

**0 iterations (default):**
- Fast processing
- Lower cost
- May miss some entities

**1 iteration:**
- Moderate quality improvement
- 2x slower and more expensive

**2-3 iterations:**
- High quality extraction
- 3-4x slower and more expensive

See Graphiti documentation for details: https://docs.graphiti.ai/

## Debugging

### Check Neo4j Connection

```bash
# Test connection
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password

# Should connect successfully
```

### Query Graph Directly

```cypher
# Count episodes (should roughly match document count)
MATCH (e:Episode) RETURN count(e)

# Show entities
MATCH (n:Entity) RETURN n LIMIT 10

# Show relationships
MATCH (n1)-[r]-(n2) RETURN n1, r, n2 LIMIT 10

# Find specific entity
MATCH (n:Entity) WHERE n.name CONTAINS 'React' RETURN n
```

### Check Synchronization

```cypher
# Find episodes with no entities (rare, usually means extraction failed)
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
RETURN count(e)
```

Empty episodes can occur if content had no extractable entities.

## Limitations

### Processing Time

Entity extraction uses LLM calls which take time:
- Per document: 30-60 seconds
- Large batches: hours
- Not suitable for real-time ingestion

### Storage

Graph stores more data than RAG:
- 1000 documents RAG: ~5-10 MB
- 1000 documents Graph: ~0.5-1 GB
- Graph adds 50-100x storage

### Query Speed

Graph queries are slower than vector search:
- Simple relationship: 100-500ms
- Complex multi-hop: 1-5 seconds
- Temporal query: 500ms-2s

## Best Practices

### Use for Relationship Questions

**Good for graph:**
- "Which services depend on X?"
- "How has X evolved?"
- "What connects X to Y?"

**Better for RAG:**
- "What is X?"
- "How do I configure X?"
- "Show me examples of X"

### Monitor Graph Health

Occasionally check synchronization:

```cypher
# Episode count should match document count (roughly)
MATCH (e:Episode) RETURN count(e)
```

```bash
# Compare to document count
rag collection list
```

### Understand Automatic Sync

Trust the synchronization:
- Updates automatically clean old graph data
- Deletes remove graph episodes
- Re-crawls refresh graph content
- No manual cleanup needed

## Resources

**Neo4j:**
- Documentation: https://neo4j.com/docs/
- Cypher Language: https://neo4j.com/docs/cypher-manual/
- Browser: http://localhost:7474 (local)

**Graphiti:**
- Documentation: https://docs.graphiti.ai/
- GitHub: https://github.com/getzep/graphiti

**Implementation:**
- Graph Store: `/src/unified/graph_store.py`
- Mediator: `/src/unified/mediator.py`
- MCP Tools: `/src/mcp/tools.py`
