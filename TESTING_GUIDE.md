# CLI Unified Mediator Testing Guide

## Quick Summary

All CLI ingestion commands now use the unified mediator pattern for dual RAG + Knowledge Graph ingestion:
- ✅ `uv run rag ingest file` - Working
- ✅ `uv run rag ingest directory` - Working
- ✅ `uv run rag ingest url` - Working
- ✅ `uv run rag recrawl` - Working

**Test Results**: 4 documents ingested, 71 entities extracted, 53 relationships found

---

## 1. Neo4j Browser Verification

### Access Neo4j Browser
1. Open: http://localhost:7474
2. Login: `neo4j` / `graphiti-password`

### Quick Verification Queries

**Count Everything:**
```cypher
// Episodes (should be 5 - includes orphan doc_4)
MATCH (n:Episodic) RETURN count(n) as episodes

// Entities (should be ~31)
MATCH (n:Entity) RETURN count(n) as entities

// Relationships (should be ~53)
MATCH ()-[r:RELATES_TO]->() RETURN count(r) as relationships
```

**List All Episodes:**
```cypher
MATCH (e:Episodic)
RETURN e.name as episode,
       e.source_description as source,
       e.created_at as created
ORDER BY e.created_at
```

**Expected Episodes:**
- `doc_1` - test-company-vision.txt (8 entities)
- `doc_2` - product-roadmap.txt (11 entities)
- `doc_3` - team-structure.txt (20 entities)
- `doc_4` - Acme Corporation - Company Info (14 entities) ⚠️ ORPHAN
- `doc_5` - Acme Corporation - Company Info (UPDATED) (18 entities)

**Find Key Entities:**
```cypher
MATCH (n:Entity)
WHERE n.name IN ['Acme Corporation', 'Jane Smith', 'Bob Johnson', 'TaskMaster AI', 'ProjectVision AI']
RETURN n.name as name, n.summary as summary
```

**Visualize Jane Smith's Network:**
```cypher
MATCH path = (e:Entity {name: "Jane Smith"})-[:RELATES_TO*1..2]-(other:Entity)
RETURN path
LIMIT 50
```

**Check for Orphan Episode (doc_4):**
```cypher
// This should return doc_4 (orphan that should have been deleted)
MATCH (e:Episodic {name: "doc_4"})
RETURN e.name, e.source_description
```

---

## 2. MCP Inspector Testing

### Start MCP Server
```bash
cd /Users/timkitchens/projects/ai-projects/rag-memory
uv run python -m src.mcp.server
```

### Start MCP Inspector (in new terminal)
```bash
npx @modelcontextprotocol/inspector
```

### Open in Browser
http://localhost:3000

---

### Test Queries for MCP Inspector

#### Test 1: Basic RAG Search
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "What is Acme Corporation's vision and product strategy?",
    "limit": 5
  }
}
```

**Expected**:
- 4-5 results from different documents
- Mentions TaskMaster AI, Q2 2025, ProductVision AI
- Similarity scores 0.5-0.8

---

#### Test 2: Knowledge Graph Relationships
```json
{
  "tool": "query_relationships",
  "arguments": {
    "query": "How is Jane Smith related to Acme Corporation?",
    "num_results": 5
  }
}
```

**Expected**:
```json
{
  "status": "success",
  "relationships": [
    {
      "relationship_type": "RELATES_TO",
      "fact": "Jane Smith is the CEO of Acme Corporation",
      "valid_from": "2025-10-19T...",
      "valid_until": null
    }
  ]
}
```

---

#### Test 3: Temporal Knowledge Evolution
```json
{
  "tool": "query_temporal",
  "arguments": {
    "query": "How has Acme Corporation's product strategy evolved?",
    "num_results": 10
  }
}
```

**Expected**:
- Timeline of facts about TaskMaster AI, ProductVision AI
- Facts with valid_from timestamps
- Shows evolution from vision → roadmap → launch

---

#### Test 4: Collection-Scoped Search
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "product roadmap Q2 Q3 Q4 features",
    "collection_name": "cli-dir-test",
    "limit": 3
  }
}
```

**Expected**:
- Only results from cli-dir-test collection
- product-roadmap.txt and team-structure.txt chunks
- No results from cli-file-test or cli-url-test

---

#### Test 5: Get Collection Info (with Crawl Metadata)
```json
{
  "tool": "get_collection_info",
  "arguments": {
    "collection_name": "cli-url-test"
  }
}
```

**Expected**:
```json
{
  "name": "cli-url-test",
  "description": "Test URL ingestion with Knowledge Graph",
  "document_count": 1,
  "chunk_count": 1,
  "crawled_urls": [
    {
      "url": "http://localhost:8888/test-page.html",
      "timestamp": "2025-10-19T15:23:23...",
      "page_count": 1,
      "chunk_count": 1
    }
  ]
}
```

---

#### Test 6: Verify Recrawl (New Content Searchable)
```json
{
  "tool": "search_documents",
  "arguments": {
    "query": "ProjectVision AI Google Gemini Meta partnership 2026",
    "collection_name": "cli-url-test",
    "limit": 3
  }
}
```

**Expected**:
- Finds updated page (doc_5) with new content
- Mentions: ProjectVision AI, Google Gemini, Meta, AWS, Sarah Chen
- Old content (doc_4) NOT in RAG results (correctly deleted)

---

#### Test 7: List All Collections
```json
{
  "tool": "list_collections",
  "arguments": {}
}
```

**Expected**:
```json
[
  {
    "name": "cli-file-test",
    "description": "Test file ingestion with Knowledge Graph",
    "document_count": 1,
    "created_at": "2025-10-19T15:16:09..."
  },
  {
    "name": "cli-dir-test",
    "description": "Test directory ingestion with Knowledge Graph",
    "document_count": 2,
    "created_at": "2025-10-19T15:19:40..."
  },
  {
    "name": "cli-url-test",
    "description": "Test URL ingestion with Knowledge Graph",
    "document_count": 1,
    "created_at": "2025-10-19T15:21:34..."
  }
]
```

---

## 3. CLI Verification

### Check System Status
```bash
uv run rag status
```

**Expected**:
- Documents: 4 (doc_1, doc_2, doc_3, doc_5)
- Chunks: 4
- Collections: 3
- Database Size: ~8 MB

### List Collections
```bash
uv run rag collection list
```

**Expected**:
- cli-file-test: 1 document
- cli-dir-test: 2 documents
- cli-url-test: 1 document

### View Collection Details
```bash
uv run rag collection info cli-dir-test
```

**Expected**:
- 2 documents: product-roadmap.txt, team-structure.txt
- 2 chunks
- No web crawls

### Search Across Collections
```bash
uv run rag search "Jane Smith CEO TaskMaster AI" --limit 5
```

**Expected**:
- Results from all 3 collections
- High similarity for test-company-vision.txt
- Mentions of Jane Smith, CEO role, TaskMaster AI

---

## 4. Verification Checklist

### RAG Store (PostgreSQL) ✅
- [x] 4 source documents exist (IDs: 1, 2, 3, 5)
- [x] 4 chunks exist (1 per document)
- [x] 3 collections exist (cli-file-test, cli-dir-test, cli-url-test)
- [x] search_documents() returns relevant results
- [x] get_collection_info() shows crawled_urls for cli-url-test
- [x] Recrawl deleted old doc_4, created new doc_5

### Knowledge Graph (Neo4j) ⚠️
- [x] 5 Episodic nodes exist (doc_1, doc_2, doc_3, doc_4, doc_5)
- [x] ~31 Entity nodes exist
- [x] ~53 RELATES_TO relationships exist
- [x] Entities include: Acme Corporation, Jane Smith, Bob Johnson, TaskMaster AI, ProjectVision AI, etc.
- [x] query_relationships() returns entity relationships
- [x] query_temporal() returns timeline of facts
- [ ] ⚠️ **doc_4 is an orphan** (should be deleted but isn't - Phase 4 gap)

### Unified Mediator Integration ✅
- [x] ingest file command uses unified mediator
- [x] ingest directory command uses unified mediator
- [x] ingest url command uses unified mediator
- [x] recrawl command uses unified mediator
- [x] All commands show entity extraction counts
- [x] Logging shows dual ingestion flow (logs/cli.log)

---

## 5. Known Issues (Phase 4 Gap)

### Graph Orphan Problem

**Issue**: Recrawl deletes old RAG documents but NOT old Graph episodes

**Evidence**:
```cypher
// This will show doc_4 (should have been deleted during recrawl)
MATCH (e:Episodic {name: "doc_4"})
RETURN e.name, e.source_description, e.created_at
```

**Impact**:
- Orphan episodes accumulate with each recrawl
- Old/stale entities remain in graph alongside new ones
- Can cause confusion in temporal queries
- Graph cleanup not implemented yet (Phase 4 work)

**Workaround**:
Manual cleanup if needed:
```cypher
// Delete orphan episode and its mentions
MATCH (e:Episodic {name: "doc_4"})
DETACH DELETE e
```

---

## 6. Test Data Summary

### Collections Created
1. **cli-file-test** - Single file ingestion
   - Document: test-company-vision.txt (479 bytes)
   - Chunks: 1
   - Entities: 8 (Acme Corporation, Jane Smith, Bob Johnson, TaskMaster AI, Microsoft Azure, OpenAI)

2. **cli-dir-test** - Directory ingestion
   - Documents:
     - product-roadmap.txt (665 bytes) - 11 entities
     - team-structure.txt (630 bytes) - 20 entities
   - Chunks: 2
   - Total Entities: 31

3. **cli-url-test** - URL ingestion + recrawl
   - Document: Acme Corporation - Company Info (UPDATED) (741 bytes)
   - Chunks: 1
   - Entities: 18 (includes NEW: ProjectVision AI, Sarah Chen, Google Gemini, Meta, AWS, etc.)
   - Previous version (doc_4, 14 entities) deleted from RAG, orphaned in Graph

### Total Ingestion Stats
- **RAG Store**: 4 documents, 4 chunks, 3 collections
- **Knowledge Graph**: 5 episodes (1 orphan), 31 entities, 53 relationships
- **Entity Extraction**: 71 total entities across all episodes (includes orphan doc_4)
- **Processing Time**: ~2-3 minutes total for all ingestions

---

## 7. Files Reference

All test queries and documentation:
- `/tmp/neo4j-verification-queries.md` - Complete Neo4j query reference
- `/tmp/mcp-inspector-test-queries.json` - MCP Inspector test cases
- `/tmp/TESTING_GUIDE.md` - This file

Test data files (cleanup optional):
- `/tmp/test-company-vision.txt` - File ingestion test
- `/tmp/test-docs/` - Directory ingestion test
  - product-roadmap.txt
  - team-structure.txt
- `/tmp/test-page.html` - URL ingestion test (server stopped)

Logs:
- `logs/cli.log` - CLI execution logs (5.3 MB)
- `logs/mcp_server.log` - MCP server logs (if server running)

---

## 8. Next Steps

### Phase 4 Work (Graph Cleanup)
Implement Graph episode cleanup in:
1. `update_document()` - Delete old episode, create new one
2. `delete_document()` - Delete episode when RAG doc deleted
3. `recrawl` command - Delete old episodes before re-ingesting

### Production Readiness
1. Test RAG-only fallback mode (stop Neo4j, verify graceful degradation)
2. Add error handling for Graph failures during ingestion
3. Implement atomic transactions (rollback RAG if Graph fails)
4. Add Graph deduplication (merge similar entities)
5. Performance profiling (entity extraction takes 20-60s per document)

### Documentation
1. Update CLAUDE.md with Phase 3 completion status
2. Document Graph cleanup strategy for Phase 4
3. Add troubleshooting guide for common issues
4. Create user guide for Knowledge Graph queries
