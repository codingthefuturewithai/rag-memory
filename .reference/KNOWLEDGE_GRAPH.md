# Knowledge Graph Integration - Graphiti + Neo4j

## Overview

RAG Memory supports optional **Knowledge Graph** integration via Graphiti and Neo4j, enabling entity extraction, relationship tracking, and temporal reasoning on top of vector search.

**Current Status:** Phase 3 Complete (2025-10-17), Phase 4 In Progress
**Recommendation:** Use for research/experimentation only, not production until Phase 4 complete

---

## What is a Knowledge Graph?

### Traditional RAG (Vector Search)
```
User Question
    ↓
Semantic Search (pgvector)
    ↓
"Here are the top 10 most similar documents"
```

### With Knowledge Graph
```
User Question
    ↓
Vector Search (for content) + Graph Queries (for relationships)
    ↓
"Here are the top documents, AND here are the entities connected to them"
```

### Example

**Without Graph:**
```
Query: "Which projects depend on the authentication service?"
RAG Search: Returns 3 documents mentioning "authentication"
Agent: "The documents are about auth, but I don't know dependencies..."
```

**With Graph:**
```
Query: "Which projects depend on the authentication service?"
Graph Query: "Find all entities connected to 'authentication-service'"
Result: [ProjectA, ProjectB, ProjectC] → [dependencies] → [auth-service]
Agent: "These three projects depend on auth service, let me get details..."
RAG Search: Returns detailed docs for ProjectA, ProjectB, ProjectC
```

---

## Architecture

### Dual Storage System

```
Ingestion
    ↓
┌─────────────────────────────────┐
│  UnifiedIngestionMediator       │
│  (src/unified/mediator.py)      │
└──────────────┬──────────────────┘
    ├─→ RAG Store      ← ← ← ← → MCP Tool: search_documents
    │   (pgvector)       ← ← ← → MCP Tool: list_documents, etc.
    │
    └─→ Graph Store    ← ← ← ← → MCP Tool: query_relationships
        (Neo4j+         ← ← ← → MCP Tool: query_temporal
         Graphiti)
```

### What Gets Stored Where

**RAG Store (PostgreSQL + pgvector):**
- Full document content
- Document chunks
- Vector embeddings
- Metadata (JSONB)
- Search optimized

**Graph Store (Neo4j + Graphiti):**
- Extracted entities (nouns, concepts)
- Relationships between entities
- Temporal information (when things changed)
- Metadata embedded in episode descriptions

### They're Complementary, Not Competing

- **RAG:** "What information exists?"
- **Graph:** "How is information related?"
- **Together:** Complete knowledge system

---

## Current Implementation Status

### ✅ Implemented (Phase 1-3)

**Ingestion Paths (All Dual-Store):**
- ✅ `ingest_text()` - Text → RAG + Graph
- ✅ `ingest_file()` - File → RAG + Graph
- ✅ `ingest_directory()` - Directory → RAG + Graph
- ✅ `ingest_url()` - Web pages → RAG + Graph

**Graph Queries:**
- ✅ `query_relationships()` - Find entity relationships
- ✅ `query_temporal()` - Track knowledge evolution

**Graceful Degradation:**
- ✅ If Neo4j unavailable, falls back to RAG-only
- ✅ No errors thrown, just informative status

### ⚠️ Implemented But Incomplete (Phase 4 Gap)

**Document Updates - PROBLEM:**
- ❌ `update_document()` - RAG-only, graph not updated
  - Consequence: Graph has stale entities
  - Status: Waiting for Phase 4

**Document Deletion - PROBLEM:**
- ❌ `delete_document()` - RAG-only, graph not cleaned
  - Consequence: Orphaned episode nodes accumulate
  - Status: Waiting for Phase 4

**Re-Crawl - PROBLEM:**
- ❌ `recrawl()` - Deletes old RAG docs, graph not cleaned
  - Consequence: Graph accumulates orphaned episodes
  - Status: Waiting for Phase 4

### ❌ Not Implemented

- Atomic transactions (two-phase commit)
- Graph-specific search filters
- Entity deduplication
- Graph visualization

---

## Setup & Prerequisites

### Option 1: Local Development with Docker

**Start Neo4j + Graphiti:**
```bash
# From cloned repo directory
docker-compose -f docker-compose.graphiti.yml up -d
```

**Verify Running:**
```bash
docker-compose -f docker-compose.graphiti.yml ps
```

**Access Neo4j Browser:**
- URL: http://localhost:7474
- Username: `neo4j`
- Password: `graphiti-password`

**Stop When Done:**
```bash
docker-compose -f docker-compose.graphiti.yml down
```

### Option 2: Cloud Neo4j (Aura)

**Setup:**
1. Create account at neo4j.com/aura
2. Create free instance (US or Europe)
3. Get connection string: `bolt://[instance-id].[region].neo4j.io:7687`
4. Set environment variables

**Environment Variables:**
```bash
export NEO4J_URI="bolt://YOUR-INSTANCE.neo4j.io:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
```

### Option 3: Production Deployment

**Fly.io + Managed Neo4j:**
- Database: Supabase PostgreSQL (same as RAG)
- Graph: Neo4j Aura (managed)
- Configure in `fly.toml` secrets

---

## How It Works: Ingestion Flow

### Step 1: User Ingests Document

```bash
rag ingest text "PostgreSQL is a powerful database with pgvector extension..." \
    --collection tech-docs
```

### Step 2: UnifiedIngestionMediator Routes to Both Stores

```python
# Inside mediator.ingest_text()

# Step A: RAG Store (pgvector)
source_id, chunk_ids = rag_store.ingest_document(
    content="PostgreSQL is a powerful...",
    collection_name="tech-docs",
    metadata={"topic": "databases"}
)
# Returns: source_id=42, chunk_ids=[101, 102, 103]

# Step B: Graph Store (Neo4j + Graphiti)
if graph_store_available:
    entities = await graph_store.add_knowledge(
        content="PostgreSQL is a powerful...",
        source_document_id=42,
        metadata={"topic": "databases"}
    )
    # Returns: [Entity(name="PostgreSQL", type="DATABASE"),
    #           Entity(name="pgvector", type="EXTENSION"),
    #           ...]
```

### Step 3: Graph Ingestion Details

**What Graphiti Does:**
1. Calls OpenAI GPT-4o for entity extraction
2. Identifies entities: PostgreSQL, pgvector, database, extension...
3. Infers relationships: PostgreSQL -[HAS]-> pgvector
4. Creates episode node: `doc_42`
5. Connects entities to episode

**Metadata Embedding:**
```python
episode_description = f"""
Collection: tech-docs
Title: PostgreSQL Basics
Metadata: {{"topic": "databases", "category": "infrastructure"}}
Key Concepts: PostgreSQL, pgvector, database, search, indexing
...
"""
# This description is searchable in Neo4j
```

### Step 4: Result

**RAG Ready:**
```python
# Can search immediately
results = search_documents("PostgreSQL", "tech-docs")
# Returns: content from source_id=42, chunks 101-103
```

**Graph Ready:**
```python
# Can query relationships
results = query_relationships("What entities relate to PostgreSQL?")
# Returns: {pgvector, database, search, indexing, ...}
```

---

## API Reference: 16 Tools (2 Graph-Specific)

### Tool 1: query_relationships()

**Purpose:** Search for entity relationships using natural language

**Signature:**
```python
query_relationships(
    query: str,
    num_results: int = 5
) -> dict
```

**Parameters:**
- `query` - Natural language question about relationships
- `num_results` - Number of relationship results (default: 5)

**Example Queries:**
- "Which projects depend on authentication?"
- "What is related to PostgreSQL?"
- "How do my services connect?"
- "Which entities are used in database operations?"

**Returns:**
```python
{
    "status": "available",  # or "unavailable" if Neo4j down
    "relationships": [
        {
            "entity_a": "PostgreSQL",
            "relationship": "HAS_EXTENSION",
            "entity_b": "pgvector",
            "description": "PostgreSQL has the pgvector extension for vector search",
            "timestamp": "2025-10-20T14:30:00Z"
        },
        ...
    ],
    "query": "What relates to PostgreSQL?",
    "count": 5
}
```

**CLI (if available):**
```bash
rag graph-query "Which projects depend on authentication?"
```

**MCP Usage:**
```python
# Via Claude Desktop or other MCP client
# Agent can call: query_relationships("Which entities relate to RAG?")
```

### Tool 2: query_temporal()

**Purpose:** Track how knowledge evolved over time

**Signature:**
```python
query_temporal(
    query: str,
    num_results: int = 10
) -> dict
```

**Parameters:**
- `query` - Question about how things changed
- `num_results` - Number of timeline entries (default: 10)

**Example Queries:**
- "How has the authentication service changed?"
- "What was updated about PostgreSQL?"
- "Show me the evolution of the API design"
- "When did we add rate limiting?"

**Returns:**
```python
{
    "status": "available",
    "timeline": [
        {
            "timestamp": "2025-10-15T10:00:00Z",
            "entity": "AuthenticationService",
            "fact": "Added OAuth2 support",
            "valid_from": "2025-10-15T10:00:00Z",
            "valid_until": None,  # Currently active
            "source_document": "doc_42"
        },
        {
            "timestamp": "2025-10-10T14:30:00Z",
            "entity": "AuthenticationService",
            "fact": "Implemented JWT token caching",
            "valid_from": "2025-10-10T14:30:00Z",
            "valid_until": "2025-10-15T10:00:00Z",  # Replaced by OAuth2
            "source_document": "doc_38"
        },
        ...
    ],
    "entity": "AuthenticationService",
    "total_changes": 7
}
```

**CLI (if available):**
```bash
rag graph-timeline "How has PostgreSQL evolved?"
```

### Other 14 Tools (RAG-Specific)

See [OVERVIEW.md](OVERVIEW.md) for complete list of 14 RAG tools.

---

## Use Cases & Examples

### Use Case 1: Research & Relationship Discovery

**Goal:** Understand how concepts connect

**Workflow:**
```
1. Ingest documents (both RAG + Graph)
2. Use query_relationships to map entity connections
3. Use RAG search to get details on specific entities
4. Build understanding of complex system

Example:
Agent: "Which services are involved in the payment flow?"
Graph:  [PaymentService] → [Stripe] → [WebhooksService] → [Database]
Agent: "Show me the PaymentService documentation"
RAG:    [Returns detailed docs]
```

**MCP Agent Example:**
```
User: "Help me understand our payment architecture"
Agent:
  1. Calls query_relationships("payment flow entities")
  2. Calls search_documents("PaymentService", limit=5)
  3. Calls search_documents("Stripe integration", limit=5)
  4. Synthesizes: "Your payment flow involves..."
```

### Use Case 2: Temporal Reasoning

**Goal:** Track how system evolved

**Workflow:**
```
1. Ingest documents over time
2. Graph auto-tracks valid_from/valid_until
3. Use query_temporal to see timeline
4. Understand decisions and changes

Example:
Agent: "When did we add rate limiting?"
Graph:  [Timeline showing 2025-10-15]
Agent: "What was the motivation?"
RAG:    [Returns PR/docs explaining decision]
```

### Use Case 3: Multi-Hop Reasoning

**Goal:** Find indirect connections

**Query Example:**
```
"Which services that use PostgreSQL also connect to the API?"

Graph Traversal:
  [PostgreSQL] ←[USES]← [Service A]
  [Service A] ←[CALLS]← [API]

Result: [Service A] is the answer
```

### Use Case 4: Compliance & Audit

**Goal:** Track dependencies and changes

**Queries:**
- "What changed in the authentication system in the last month?"
- "Which services depend on PII database?"
- "Show me all security-related entities and their relationships"

---

## Known Issues & Debugging

### Issue 1: Graph Not Updating (Phase 4 Gap)

**Problem:**
```
Step 1: Ingest "PostgreSQL is powerful"
        RAG ✅ stored, Graph ✅ entities extracted

Step 2: Edit document to "PostgreSQL 17 is powerful with pgvector"
        RAG ✅ updated, Graph ❌ STALE
```

**Status:** Waiting for Phase 4 implementation

**Workaround:**
- Don't use `update_document()` with unified ingestion
- Delete and re-ingest instead
- Or manually clean Neo4j episodes

**Cleanup Script (Manual):**
```bash
# SSH into Neo4j container
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password

# Find old episodes
MATCH (n) WHERE n.name = 'doc_42' RETURN n

# Delete episode and relationships
MATCH (n) WHERE n.name = 'doc_42'
DETACH DELETE n

# Verify deletion
MATCH (n) WHERE n.name = 'doc_42' RETURN n
# Should return no results
```

### Issue 2: Orphaned Episodes

**Problem:**
```
Initial Crawl:  Creates doc_290, doc_291, doc_292
Recrawl:        Deletes doc_290-292 from RAG
                Creates doc_295, doc_296, doc_297
Result:         Graph still has doc_290, doc_291, doc_292 (orphans)
```

**Status:** Known limitation, Phase 4 will fix

**Detection:**
```cypher
# Find orphaned episodes (no entities)
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
RETURN e

# Find episodes with no source documents
# (In RAG, the source doc was deleted)
MATCH (e:Episode)
RETURN e.name  # Manual verification needed
```

**Manual Cleanup:**
```cypher
# Delete orphaned episodes
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
DETACH DELETE e
```

### Issue 3: Wikipedia Ingestion Timeout (2025-10-17)

**What Happened:**
```
Ingest: https://en.wikipedia.org/wiki/Quantum_computing
RAG:    ✅ 4 chunks searchable
Graph:  ⏱️ Timed out (60 seconds), 4 episodes created with 0 entities
```

**Likely Cause:**
- Graphiti LLM call (GPT-4o) took > 60 seconds
- Page content too large/complex
- OpenAI API timeout

**Workaround:**
- Try smaller Wikipedia pages
- Use `mode="recrawl"` to retry (avoids RAG duplicate error)
- Monitor `/logs/mcp_server.log` during ingestion
- Manually clean up 0-entity episodes

**Debugging:**
```bash
# Check logs
tail -f /logs/mcp_server.log | grep -i graphiti

# Find 0-entity episodes in Neo4j
MATCH (e:Episode)
RETURN e, size((e)--()) as relationship_count
ORDER BY relationship_count
```

### Issue 4: Neo4j Connection Errors

**Error:** `"Connection refused: bolt://localhost:7687"`

**Solution:**
```bash
# Check Neo4j is running
docker-compose -f docker-compose.graphiti.yml ps

# Start if not running
docker-compose -f docker-compose.graphiti.yml up -d

# Check logs
docker-compose -f docker-compose.graphiti.yml logs neo4j | tail -20

# Verify connection
neo4j-shell -u neo4j -p graphiti-password
```

### Debugging Commands

**Query Neo4j Directly:**
```bash
# Via container
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password

# Or via Neo4j Browser
# http://localhost:7474
# Username: neo4j
# Password: graphiti-password
```

**Useful Cypher Queries:**
```cypher
# Show all episodes (documents)
MATCH (e:Episode) RETURN e LIMIT 10

# Show all entities
MATCH (n:Entity) RETURN n, size((n)--()) as connections LIMIT 10

# Show entities for specific episode
MATCH (e:Episode {name: 'doc_42'})--(n:Entity) RETURN n

# Show relationships
MATCH (n1)-[r]-(n2) RETURN n1, r, n2 LIMIT 10

# Find specific entity
MATCH (n:Entity) WHERE n.name CONTAINS 'PostgreSQL' RETURN n

# Count statistics
MATCH (e:Episode) RETURN count(e) as episodes
MATCH (n:Entity) RETURN count(n) as entities
MATCH ()-[r]-() RETURN count(r) as relationships
```

**Check Logs:**
```bash
# MCP Server logs
tail -f /logs/mcp_server.log | grep -i graph

# CLI logs
tail -f /logs/cli.log | grep -i graph

# Neo4j logs
docker-compose -f docker-compose.graphiti.yml logs neo4j -f
```

---

## Performance Considerations

### Entity Extraction Cost

**OpenAI GPT-4o Call:**
- Time per document: 30-60 seconds
- Cost: ~$0.01 per document (using GPT-4o turbo)
- Significant vs RAG embedding cost (~$0.000001)

**Implications:**
- Graph ingestion is 30-60x slower than RAG
- Large batch ingestion can take hours
- Not suitable for real-time ingestion

**Optimization Opportunities (Future):**
- Batch entity extraction
- Local entity models (smaller, faster)
- Caching of extracted entities
- Async extraction (background job)

### Storage Impact

**Neo4j Storage:**
- Typical: 100-500 entities per document
- Size per entity: ~1-2 KB
- 1,000 documents: ~500,000 entities = ~0.5-1 GB

**vs PostgreSQL:**
- Same 1,000 documents: ~5-10 MB (just embeddings)
- Graph adds ~50-100x storage

### Query Performance

**Graph Query Time:**
- Simple relationship: 100-500ms
- Complex multi-hop: 1-5 seconds
- Temporal query: 500ms-2s

**vs RAG Search:**
- Vector search: 100-500ms (same range)
- Advantage: No latency tradeoff

---

## Best Practices

### 1. Don't Use Graph Yet for Production

**Phase 4 Not Complete:**
- Document cleanup not implemented
- Orphan accumulation likely
- No atomic transactions

**Recommendation:**
- Use for research/experimentation
- Wait for Phase 4 completion
- Monitor GitHub releases for "Phase 4 Complete"

### 2. Monitor Orphan Accumulation

**Check Monthly:**
```cypher
# Find orphans
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
RETURN count(e) as orphan_episodes
```

**If Growing:**
```cypher
# Manually cleanup
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
DETACH DELETE e
```

### 3. Use Graceful Degradation

**Graph Optional:**
```python
# If Neo4j unavailable, system falls back to RAG
response = query_relationships("entities")
if response["status"] == "unavailable":
    # Fall back to RAG search
    results = search_documents(query="entities")
```

### 4. Separate Concerns

**Best Architecture:**
- RAG for "What" questions (content search)
- Graph for "How" questions (relationships)
- Don't expect graph to replace RAG search

### 5. Document Ingestion Strategy

**Until Phase 4:**
```
┌──────────────────────────────────┐
│ Ingest via Mediator              │
│ (dual RAG + Graph)               │
└──────────────────────────────────┘
         ↓
┌──────────────────────────────────┐
│ Searches via RAG                 │
│ (search_documents)               │
└──────────────────────────────────┘
         ↓
┌──────────────────────────────────┐
│ Relationships via Graph           │
│ (query_relationships, temporal)  │
└──────────────────────────────────┘
         ↓
┌──────────────────────────────────┐
│ NEVER update/delete docs         │
│ (until Phase 4 - re-ingest only) │
└──────────────────────────────────┘
```

---

## Phase 4: What's Coming

### Planned Implementations

**Priority 1 (Critical):**
1. `update_document()` Graph cleanup
2. `delete_document()` Graph cleanup
3. `recrawl()` Graph cleanup

**Priority 2 (Important):**
4. Two-phase commits (atomic transactions)
5. Graph consistency checks
6. Orphan detection/cleanup background job

**Priority 3 (Nice-to-Have):**
7. Graph-specific search filters
8. Entity deduplication
9. Graph visualization endpoint
10. Performance optimization

### Timeline

- **Current:** Phase 3 complete (2025-10-17)
- **Expected:** Phase 4 by end of 2025
- **Status:** Check GitHub releases for updates

---

## Resources & Links

**Project:**
- GitHub: (your repo)
- Documentation: [../CLAUDE.md](../CLAUDE.md)

**Neo4j:**
- Neo4j Browser: http://localhost:7474 (local)
- Neo4j Documentation: https://neo4j.com/docs/
- Cypher Query Language: https://neo4j.com/docs/cypher-manual/

**Graphiti:**
- GitHub: https://github.com/getzep/graphiti
- Documentation: https://docs.graphiti.ai/

**References in Codebase:**
- Implementation: `/src/unified/graph_store.py`
- Mediator: `/src/unified/mediator.py`
- Tools: `/src/mcp/tools.py` (query_relationships_impl, query_temporal_impl)
- Tests: `/tests/integration/backend/test_graph_*`

---

## Frequently Asked Questions

**Q: Why is graph ingestion so slow?**
A: Entity extraction uses GPT-4o which takes 30-60 seconds per document. It's the bottleneck.

**Q: Will my graph data be lost if I delete documents?**
A: Until Phase 4: Yes, orphaned episodes accumulate. Workaround: manually clean Neo4j. Phase 4 will fix this.

**Q: Can I use graph without RAG?**
A: Not yet. Graph depends on RAG for content storage. They're complementary.

**Q: What happens if Neo4j is down?**
A: System gracefully falls back to RAG-only. No errors thrown. Tools return `status: "unavailable"`.

**Q: Can I use a different graph database?**
A: Currently only Neo4j is supported. Other databases not planned.

**Q: Should I use graph for production now?**
A: No. Wait for Phase 4 completion. Current version has data consistency issues.

**Q: How do I migrate from Neo4j to another database?**
A: Not currently supported. Would need code changes.

**Q: Can graph queries be slow?**
A: Yes, complex multi-hop queries can take 1-5 seconds. This is expected for graph databases.

---

**Last Updated:** 2025-10-20
**Status:** Phase 3 Complete, Phase 4 In Progress
**Production Ready:** No (Wait for Phase 4)
**Use Case:** Research & Experimentation
