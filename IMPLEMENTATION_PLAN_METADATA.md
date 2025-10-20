# Implementation Plan: Metadata & Testing

**Based on:** GRAPHITI_METADATA_RESEARCH.md with full citations
**Status:** Research Complete - Ready for Implementation
**Last Updated:** 2025-10-20

---

## Confirmed Findings from Graphiti API Research

### Episode Metadata Storage
✅ **Source:** https://context7.com/getzep/graphiti/llms.txt - "REST API Get Episodes Endpoint"

Episodes are Neo4j nodes storing:
- `uuid` - Auto-generated unique ID
- `name` - Human-readable episode identifier
- `content` - The ingested body/content
- `source` - Source type (text, json, message)
- **`source_description`** - **TEXT FIELD FOR CUSTOM METADATA** ← We use this for collection/doc/crawl metadata
- `created_at` - Timestamp
- `valid_at` - Temporal validity marker
- **`group_id`** - **COLLECTION IDENTIFIER** ← Maps episodes to collections

### Episode Metadata Querying
✅ **Source:** https://context7.com/getzep/graphiti/llms.txt - "Retrieve Episodes by Time Range (Python)"

Episodes are queryable via Python client:
```python
episodes = await graphiti.retrieve_episodes(
    reference_time=datetime.now(timezone.utc),
    last_n=10,
    group_ids=["api-docs"],  # Filter by collection
    source=EpisodeType.message
)

for episode in episodes:
    print(episode.source_description)  # Access custom metadata
```

**REST API also available:**
```bash
GET /episodes/api-docs?last_n=10
```

### Relationship Provenance (Critical Feature)
✅ **Source:** https://github.com/getzep/graphiti/blob/main/examples/ecommerce/runner.ipynb

Each relationship (edge) stores:
```json
{
  "uuid": "rel-123",
  "fact": "Richard Feynman studied under Niels Bohr",
  "episodes": ["doc_42", "doc_51", "doc_67"],  // ← Which episodes created this
  "valid_at": "2024-01-15",
  "invalid_at": null
}
```

**Implication:** We can trace relationships back to source documents via episode UUIDs.

### Entity Labels vs Custom Metadata
✅ **Source:** https://context7.com/getzep/graphiti/llms.txt - "Define Custom Entity Types with Pydantic"

- **`entity_labels`** = Auto-assigned node types (extracted by LLM, used in SearchFilters)
- **`source_description`** = Custom metadata about the ingestion event
- **They are different:** `entity_labels` filter NODES, `source_description` stores EPISODE metadata

### Node Metadata (Read-Only from User Perspective)
✅ **Source:** https://context7.com/getzep/graphiti/llms.txt - "Define Custom Entity Types with Pydantic"

Nodes are auto-managed with:
- `name` - Entity name (auto-extracted)
- `labels` - Entity types (auto-assigned, e.g., ["Person", "Organization"])
- `attributes` - Properties extracted from content
- `summary` - LLM-generated summary
- `updated_at` - When node last appeared in new episode

**Important:** Node metadata is NOT directly user-customizable. Custom metadata goes on episodes.

### SearchFilters for Relationships
✅ **Source:** https://context7.com/getzep/graphiti/llms.txt - "Search Graph Data with Filters in Python"

```python
from graphiti_core.search.search_filters import SearchFilters

search_filter = SearchFilters(
    entity_labels=["Person", "Organization"],  # Filter by node types
    valid_after=one_week_ago,                   # Filter by validity period
    valid_before=now
)

results = await graphiti.search(
    query="recent collaborations",
    group_ids=["employee_records"],
    num_results=15,
    search_filter=search_filter
)

for edge in results:
    print(edge.fact)
    print(edge.episodes)  # Trace back to source episodes
```

---

## Implementation Strategy: Two Layers

### Layer 1: RAG Store (PostgreSQL + pgvector)

**What to verify:**
- ✅ Metadata filtering works: `search_chunks(metadata_filter={"domain": "backend"})`
- ✅ Web ingestion adds crawl metadata: `crawl_root_url`, `crawl_session_id`, `crawl_depth`
- ✅ Metadata persists in search results: `result.metadata`

**Status:** Should already work (no code changes needed)

### Layer 2: Graph Store (Neo4j + Graphiti)

**What to implement:**

**Phase 0: Enhance Episode Metadata** (Code Change Required)

Modify `src/unified/mediator.py` and `src/unified/graph_store.py` to populate episode fields:

```python
# When calling graphiti.add_episode(), pass complete metadata:

result = await self.graphiti.add_episode(
    name=f"doc_{source_document_id}",
    episode_body=content,
    source=EpisodeType.text,

    # Custom metadata as text - this is the only place for custom metadata
    source_description=f"""collection: {collection_name}
doc_id: {source_document_id}
doc_title: {document_title}
domain: {metadata.get('domain', 'unknown')}
content_type: {metadata.get('content_type', 'text')}
created_date: {datetime.now().isoformat()}
crawl_root_url: {metadata.get('crawl_root_url', '')}
crawl_session_id: {metadata.get('crawl_session_id', '')}
crawl_depth: {metadata.get('crawl_depth', -1)}
""",

    reference_time=datetime.now(timezone.utc),  # For temporal tracking
    group_id=collection_name                     # Links to collection
)
```

**Why:**
- `group_id` directly maps episodes to collections (enables collection-scoped queries)
- `source_description` stores all custom metadata (the only extensible field for episodes)
- `reference_time` enables temporal queries
- `episodes` field on relationships enables provenance tracking

---

## Test Execution Plan

### Phase 1: Verify RAG Metadata Filtering

**File:** `tests/integration/test_metadata_rag_search.py`
**Status:** No code changes needed - tests existing functionality

```python
# Test that metadata filtering works
results = searcher.search_chunks(
    query="kubernetes",
    collection_name="api-docs",
    metadata_filter={"domain": "backend"}
)

assert all(r.metadata["domain"] == "backend" for r in results)
```

### Phase 2: Verify Web Ingestion Metadata

**File:** `tests/integration/test_web_ingestion_metadata.py`
**Status:** No code changes needed - web crawler already sets this

```python
# Verify crawl metadata exists
results = searcher.search_chunks(
    query="anything",
    collection_name="test",
    metadata_filter={"crawl_depth": 0}  # Only root pages
)

assert all(r.metadata["crawl_depth"] == 0 for r in results)
assert all(r.metadata["crawl_session_id"] for r in results)  # Exists
```

### Phase 3: Verify Graph Entity Extraction

**File:** `tests/integration/test_graph_entity_extraction.py`
**Status:** No code changes needed - Graphiti auto-extracts

```python
# Ingest content and verify entities extracted in Neo4j
await mediator.ingest_text(
    content="Richard Feynman studied under Niels Bohr",
    collection_name="test"
)

# Query Neo4j directly
result = await graphiti.driver.execute_query(
    """MATCH (n) WHERE n.name IN ["Feynman", "Bohr"] RETURN n"""
)

assert len(result[0]) >= 2  # Both entities exist
```

### Phase 4: Verify Query Tools Work

**File:** `tests/integration/test_query_tools_verification.py`
**Status:** Will reveal if query tools work after Phase 0

```python
# Test query_relationships
results = await query_relationships_impl(
    query="How do these entities relate?",
    num_results=5
)

assert len(results) > 0
assert all("relationship_type" in r for r in results)
assert all("fact" in r for r in results)
```

### Phase 5: Verify Cross-Store Consistency

**File:** `tests/integration/test_metadata_consistency.py`
**Status:** Depends on Phase 0 implementation

```python
# Ingest via mediator with metadata
await mediator.ingest_text(
    content="Test content",
    collection_name="test-collection",
    metadata={"domain": "backend", "author": "team-x"}
)

# Verify in RAG
rag_results = searcher.search_chunks(
    query="test",
    metadata_filter={"domain": "backend"}
)
assert len(rag_results) > 0

# Verify in Graph via episodes
episodes = await graphiti.retrieve_episodes(group_ids=["test-collection"])
assert len(episodes) > 0
assert "domain: backend" in episodes[0].source_description
```

---

## Code Changes Required

### File 1: `src/unified/graph_store.py`

**Change to `add_knowledge()` method signature:**
```python
async def add_knowledge(
    self,
    content: str,
    source_document_id: int,
    metadata: Optional[dict[str, Any]] = None,
    group_id: Optional[str] = None,        # NEW: collection identifier
    ingestion_timestamp: Optional[datetime] = None  # NEW: for temporal tracking
) -> list[Any]:

    # Format source_description with all metadata
    source_desc_lines = [
        f"collection: {group_id or 'unknown'}",
        f"doc_id: {source_document_id}",
        f"doc_title: {metadata.get('document_title', 'unknown') if metadata else 'unknown'}",
    ]

    if metadata:
        for key, value in metadata.items():
            if key not in ['document_title', 'collection_name']:
                source_desc_lines.append(f"{key}: {value}")

    source_description = "\n".join(source_desc_lines)

    # Call Graphiti with complete parameters
    result = await self.graphiti.add_episode(
        name=f"doc_{source_document_id}",
        episode_body=content,
        source=EpisodeType.text,
        source_description=source_description,      # NEW
        reference_time=ingestion_timestamp or datetime.now(timezone.utc),  # NEW
        group_id=group_id                           # NEW
    )

    return result
```

### File 2: `src/unified/mediator.py`

**Change all ingest methods to pass `group_id` and `ingestion_timestamp`:**
```python
async def ingest_text(self, content: str, collection_name: str, ...):
    # ... existing code ...

    entities = await self.graph_store.add_knowledge(
        content=content,
        source_document_id=source_id,
        metadata=metadata,
        group_id=collection_name,              # NEW
        ingestion_timestamp=datetime.now()     # NEW
    )
```

Do the same for `ingest_url()`, `ingest_file()`, and `ingest_directory()`.

---

## Expected Outcomes

| Phase | Expected | Status | Why |
|-------|----------|--------|-----|
| Phase 1 | ✅ Pass | Not started | RAG metadata filtering already implemented |
| Phase 2 | ✅ Pass | Not started | Web crawler already sets crawl metadata |
| Phase 3 | ✅ Pass | Not started | Graphiti auto-extracts entities (verified) |
| Phase 4 | ⚠️ Unknown | Not started | Will reveal query tool issues (if any) |
| Phase 0 | ✅ Pass | Not started | Code change is straightforward |
| Phase 5 | ✅ Pass | Not started | Should pass after Phase 0 implementation |

---

## Research Validation

All findings validated against official Graphiti documentation:
- ✅ https://context7.com/getzep/graphiti/llms.txt (official Graphiti docs)
- ✅ https://github.com/getzep/graphiti/blob/main/examples/ (official examples)
- ✅ Full details in GRAPHITI_METADATA_RESEARCH.md

Ready for implementation approval.
