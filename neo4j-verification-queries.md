# Neo4j Verification Queries

## How to Access Neo4j Browser

1. **Open Neo4j Browser**: http://localhost:7474
2. **Login Credentials**:
   - Username: `neo4j`
   - Password: `graphiti-password`

## Verification Queries

### 1. Count All Episode Nodes (Should be 5)
```cypher
MATCH (n:Episodic)
RETURN count(n) as episode_count
```
**Expected**: 5 episodes (doc_1, doc_2, doc_3, doc_4, doc_5)

**Note**: We should only have 4 episodes after recrawl (doc_1, doc_2, doc_3, doc_5), but doc_4 will still exist as an orphan because Graph cleanup is not yet implemented (Phase 4 gap).

---

### 2. List All Episodes with Names
```cypher
MATCH (n:Episodic)
RETURN n.name as episode_name, n.source_description as source, n.created_at as created
ORDER BY n.created_at
```
**Expected Episodes**:
- `doc_1` - test-company-vision.txt
- `doc_2` - product-roadmap.txt
- `doc_3` - team-structure.txt
- `doc_4` - Acme Corporation - Company Info (ORPHAN - should be deleted but isn't)
- `doc_5` - Acme Corporation - Company Info (UPDATED)

---

### 3. Count All Entities
```cypher
MATCH (n:Entity)
RETURN count(n) as entity_count
```
**Expected**: ~71+ entities total across all episodes

---

### 4. List Top 20 Entities by Name
```cypher
MATCH (n:Entity)
RETURN n.name as entity_name, n.summary as summary
ORDER BY n.name
LIMIT 20
```
**Expected Entities** (sample):
- Acme Corporation
- Jane Smith
- Bob Johnson
- TaskMaster AI
- Microsoft Azure
- OpenAI
- Sarah Chen
- Dr. Michael Torres
- Lisa Martinez
- ProjectVision AI
- Google Gemini
- Meta
- Anthropic
- etc.

---

### 5. Find All Entities from a Specific Episode
```cypher
// Entities from doc_1 (test-company-vision.txt)
MATCH (e:Episodic {name: "doc_1"})-[:MENTIONS]->(entity:Entity)
RETURN entity.name as entity_name, entity.summary as summary
ORDER BY entity.name
```

**Expected from doc_1** (8 entities):
- Acme Corporation
- Bob Johnson (CTO)
- Jane Smith (CEO)
- Microsoft Azure
- OpenAI
- TaskMaster AI
- (and a few more)

---

### 6. Find All Relationships Between Entities
```cypher
MATCH (e1:Entity)-[r:RELATES_TO]->(e2:Entity)
RETURN e1.name as source, r.fact as relationship, e2.name as target
LIMIT 25
```
**Expected**: Relationships like:
- "Jane Smith" -> "is CEO of" -> "Acme Corporation"
- "Bob Johnson" -> "is CTO of" -> "Acme Corporation"
- "TaskMaster AI" -> "developed by" -> "Acme Corporation"
- "Acme Corporation" -> "partners with" -> "Microsoft Azure"
- etc.

---

### 7. Find Entity by Name (Case-Insensitive)
```cypher
MATCH (n:Entity)
WHERE toLower(n.name) CONTAINS "acme"
RETURN n.name as entity_name, n.summary as summary
```
**Expected**: Find "Acme Corporation" entity

---

### 8. Find All Episodes That Mention "TaskMaster AI"
```cypher
MATCH (e:Episodic)-[:MENTIONS]->(entity:Entity)
WHERE toLower(entity.name) CONTAINS "taskmaster"
RETURN e.name as episode, e.source_description as source, entity.name as entity_name
```
**Expected**: doc_1, doc_2, doc_4, doc_5 (all mention TaskMaster AI)

---

### 9. Visualize Entity Graph (Jane Smith's Network)
```cypher
MATCH path = (e:Entity {name: "Jane Smith"})-[:RELATES_TO*1..2]-(other:Entity)
RETURN path
LIMIT 50
```
**Expected**: Visual graph showing Jane Smith connected to:
- Acme Corporation
- Bob Johnson
- TaskMaster AI
- Other related entities

---

### 10. Find Orphan Episodes (Episodes with No Entity Mentions)
```cypher
MATCH (e:Episodic)
WHERE NOT (e)-[:MENTIONS]->(:Entity)
RETURN e.name as episode, e.source_description as source
```
**Expected**: If doc_4 has entities, this should return 0 results. If entity extraction failed for any episode, those will show here.

---

### 11. Show Episode Content and Entity Count
```cypher
MATCH (e:Episodic)
OPTIONAL MATCH (e)-[:MENTIONS]->(entity:Entity)
RETURN e.name as episode,
       e.source_description as source,
       substring(e.content, 0, 100) + "..." as content_preview,
       count(entity) as entity_count
ORDER BY e.created_at
```
**Expected**:
- doc_1: 8 entities
- doc_2: 11 entities
- doc_3: 20 entities
- doc_4: 14 entities (orphan)
- doc_5: 18 entities

---

### 12. Find All Entities Added in Latest Episode (doc_5)
```cypher
MATCH (e:Episodic {name: "doc_5"})-[:MENTIONS]->(entity:Entity)
RETURN entity.name as entity_name, entity.summary as summary
ORDER BY entity.name
```
**Expected from doc_5** (18 entities - updated page):
- Acme Corporation
- Jane Smith
- Bob Johnson
- Lisa Martinez
- Dr. Sarah Chen (NEW)
- TaskMaster AI
- ProjectVision AI (NEW)
- OpenAI
- Anthropic
- Google DeepMind (NEW)
- Microsoft Azure
- AWS (NEW)
- OpenAI GPT-4 (NEW)
- Anthropic Claude (NEW)
- Google Gemini (NEW)
- Meta (NEW)
- LLaMA (NEW)

---

## MCP Inspector Testing

### Setup MCP Inspector

1. **Install MCP Inspector** (if not already installed):
   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```

2. **Start MCP Server** (in project directory):
   ```bash
   uv run python -m src.mcp.server
   ```

3. **Start MCP Inspector** (in a new terminal):
   ```bash
   npx @modelcontextprotocol/inspector
   ```

4. **Connect to Server**:
   - URL: `http://localhost:3000`
   - The inspector should detect the MCP server automatically

---

### MCP Inspector Test Queries

#### Test 1: Search Documents (RAG Only)
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "What is Acme Corporation's vision for 2025?",
    "limit": 5
  }
}
```
**Expected Result**:
- Returns chunks from test-company-vision.txt, product-roadmap.txt, team-structure.txt, updated web page
- Similarity scores ~0.5-0.8
- Should find mentions of TaskMaster AI, Q2 2025 launch, etc.

---

#### Test 2: Query Relationships (Knowledge Graph)
```json
{
  "tool": "query_relationships",
  "arguments": {
    "query": "How is Jane Smith related to Acme Corporation?",
    "num_results": 5
  }
}
```
**Expected Result**:
```json
{
  "status": "success",
  "relationships": [
    {
      "relationship_type": "RELATES_TO",
      "fact": "Jane Smith is the CEO of Acme Corporation",
      "source_node_id": "...",
      "target_node_id": "...",
      "valid_from": "2025-10-19T...",
      "valid_until": null
    }
  ]
}
```

---

#### Test 3: Query Temporal (Knowledge Graph Evolution)
```json
{
  "tool": "query_temporal",
  "arguments": {
    "query": "How has Acme Corporation's product strategy evolved?",
    "num_results": 10
  }
}
```
**Expected Result**:
- Timeline showing TaskMaster AI launch info from different documents
- Evolution from initial vision (doc_1) to roadmap (doc_2) to updated status (doc_5)
- Should show valid_from timestamps for each fact

---

#### Test 4: Search with Collection Filter
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "product roadmap features",
    "collection_name": "cli-dir-test",
    "limit": 3
  }
}
```
**Expected Result**:
- Only returns results from cli-dir-test collection
- Should find product-roadmap.txt and team-structure.txt chunks
- No results from cli-file-test or cli-url-test

---

#### Test 5: Get Collection Info
```json
{
  "tool": "get_collection_info",
  "arguments": {
    "collection_name": "cli-file-test"
  }
}
```
**Expected Result**:
```json
{
  "name": "cli-file-test",
  "description": "Test file ingestion with Knowledge Graph",
  "document_count": 1,
  "chunk_count": 1,
  "sample_documents": ["test-company-vision.txt"],
  "crawled_urls": []
}
```

---

#### Test 6: Get Collection Info (URL Collection)
```json
{
  "tool": "get_collection_info",
  "arguments": {
    "collection_name": "cli-url-test"
  }
}
```
**Expected Result**:
```json
{
  "name": "cli-url-test",
  "description": "Test URL ingestion with Knowledge Graph",
  "document_count": 1,
  "chunk_count": 1,
  "sample_documents": ["Acme Corporation - Company Info (UPDATED)"],
  "crawled_urls": [
    {
      "url": "http://localhost:8888/test-page.html",
      "timestamp": "2025-10-19T...",
      "page_count": 1,
      "chunk_count": 1
    }
  ]
}
```

---

#### Test 7: Get Document by ID
```json
{
  "tool": "get_document_by_id",
  "arguments": {
    "document_id": 1,
    "include_chunks": true
  }
}
```
**Expected Result**:
- Full content of test-company-vision.txt
- Metadata with file_type, file_size
- List of 1 chunk with content, char_start, char_end

---

#### Test 8: List Documents
```json
{
  "tool": "list_documents",
  "arguments": {
    "collection_name": "cli-dir-test",
    "limit": 10
  }
}
```
**Expected Result**:
```json
{
  "documents": [
    {"id": 2, "filename": "product-roadmap.txt", "chunk_count": 1},
    {"id": 3, "filename": "team-structure.txt", "chunk_count": 1}
  ],
  "total_count": 2,
  "returned_count": 2,
  "has_more": false
}
```

---

#### Test 9: Search for New Entities (from doc_5 recrawl)
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "ProjectVision AI and Google Gemini partnership",
    "collection_name": "cli-url-test",
    "limit": 3
  }
}
```
**Expected Result**:
- Should find the updated page content (doc_5)
- Should NOT find the old page content (doc_4 was deleted from RAG)
- Mentions ProjectVision AI, Google Gemini, Meta, AWS

---

#### Test 10: Query Relationships (Multi-Hop)
```json
{
  "tool": "query_relationships",
  "arguments": {
    "query": "What partnerships does Acme Corporation have for AI technology?",
    "num_results": 10
  }
}
```
**Expected Result**:
- Relationships showing Acme Corporation → OpenAI
- Acme Corporation → Anthropic
- Acme Corporation → Google DeepMind
- Acme Corporation → Microsoft Azure
- Possibly relationships like TaskMaster AI → uses → OpenAI GPT-4

---

## Verification Checklist

### RAG Store (PostgreSQL) ✅
- [ ] 4 source documents exist (doc_1, doc_2, doc_3, doc_5)
- [ ] 4 chunks exist (1 per document)
- [ ] 3 collections exist (cli-file-test, cli-dir-test, cli-url-test)
- [ ] search_documents() returns relevant results
- [ ] get_collection_info() shows crawled_urls for cli-url-test

### Knowledge Graph (Neo4j) ⚠️
- [ ] 5 Episodic nodes exist (doc_1 through doc_5)
- [ ] doc_4 is an orphan (should be deleted but isn't - Phase 4 gap)
- [ ] ~71 Entity nodes exist total
- [ ] Entities include: Acme Corporation, Jane Smith, Bob Johnson, TaskMaster AI, ProjectVision AI, etc.
- [ ] RELATES_TO relationships exist between entities
- [ ] MENTIONS relationships connect episodes to entities
- [ ] query_relationships() returns entity relationships
- [ ] query_temporal() returns timeline of facts

### Recrawl Verification ✅/⚠️
- [ ] RAG: doc_4 deleted, doc_5 created (CORRECT)
- [ ] Graph: doc_4 orphan exists, doc_5 created (INCORRECT - doc_4 should be deleted)
- [ ] New entities from doc_5 searchable (ProjectVision AI, Google Gemini, Meta)
- [ ] Old content (14 entities) vs new content (18 entities)

---

## Known Issues (Phase 4 Gap)

**Graph Orphan Problem**:
```cypher
// This will show doc_4 as an orphan (should have been deleted during recrawl)
MATCH (e:Episodic)
WHERE e.name = "doc_4"
RETURN e.name, e.source_description
```

**Why it exists**:
- Recrawl command deletes old RAG documents correctly
- But does NOT delete corresponding Graph episodes (not implemented yet)
- This is documented in CLAUDE.md Phase 4 work

**Impact**:
- Orphan episodes accumulate with each recrawl
- Old/stale entities remain in graph alongside new ones
- Can cause confusion in temporal queries
- Needs Graph cleanup implementation in Phase 4

---

## Quick Test Script

Run all verifications at once:

```bash
# Neo4j counts
echo "Episode count:" && uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'graphiti-password'))
with driver.session() as session:
    result = session.run('MATCH (n:Episodic) RETURN count(n) as count')
    print(result.single()['count'])
driver.close()
"

echo "Entity count:" && uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'graphiti-password'))
with driver.session() as session:
    result = session.run('MATCH (n:Entity) RETURN count(n) as count')
    print(result.single()['count'])
driver.close()
"

# RAG counts
uv run rag status
uv run rag collection list
```
