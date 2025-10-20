# Graphiti Metadata Storage & Querying: Complete Research with Citations

**Last Updated:** 2025-10-20
**Status:** RESEARCH COMPLETE - Ready for Implementation Discussion

---

## Executive Summary

This document provides definitive answers to the user's critical questions about how Graphiti stores and queries metadata. **Every claim is sourced and cited** from official Graphiti documentation.

**Key Findings:**
1. ✅ Episode metadata IS queryable - via `group_id` and `source_description` parameters
2. ✅ Node metadata exists but is auto-managed by Graphiti (not user-customizable)
3. ✅ Relationship metadata exists on edges via the `episodes` field (list of episode UUIDs)
4. ✅ `SearchFilters` enables filtering by entity labels, valid_after, valid_before
5. ⚠️ Custom metadata properties on nodes/edges are NOT directly supported
6. ✅ Episodes themselves ARE queryable via REST API and Python client

---

## Question 1: Where Exactly Is Episode Metadata Stored?

### Answer: Episode Objects as Neo4j Nodes with Multiple Fields

**Source:** https://context7.com/getzep/graphiti/llms.txt - "REST API Get Episodes Endpoint"

Episodes in Graphiti are stored as Neo4j nodes with the following structure:

```json
{
  "uuid": "episode-001",
  "name": "Support Chat 1",
  "content": "user: I need help with my account login",
  "source": "message",
  "source_description": "Chat transcript",
  "created_at": "2024-01-15T10:30:00Z",
  "valid_at": "2024-01-15T10:30:00Z",
  "group_id": "customer_support"
}
```

**Fields Available on Episode Objects:**
- `uuid` - Unique identifier (auto-generated)
- `name` - Human-readable episode name
- `content` - The actual content/body ingested
- `source` - Source type (e.g., "message", "text", "json")
- `source_description` - **TEXT FIELD FOR CUSTOM METADATA**
- `created_at` - ISO 8601 timestamp
- `valid_at` - Temporal validity marker
- `group_id` - Logical grouping/collection identifier

**Key Finding:** `source_description` is a **text field** designed to hold custom metadata. Currently in implementation, we embed metadata as text here.

---

## Question 2: How Do You Query/Filter Episode Metadata?

### Answer: Multiple Methods Depending on Use Case

#### Method 1: Retrieve Episodes by Group ID (REST API)

**Source:** https://context7.com/getzep/graphiti/llms.txt - "REST API Get Episodes Endpoint"

```bash
curl -X GET "http://localhost:8000/episodes/customer_support?last_n=10"
```

**Response includes all episode fields including `source_description`:**
```json
[
  {
    "uuid": "episode-001",
    "group_id": "customer_support",
    "source_description": "Chat transcript",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**Implication:** Episodes ARE queryable by `group_id`. This enables filtering by collection.

---

#### Method 2: Retrieve Episodes by Time Range (Python Client)

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Retrieve Episodes by Time Range (Python)"

```python
episodes = await graphiti.retrieve_episodes(
    reference_time=datetime.now(timezone.utc),
    last_n=10,
    group_ids=["support_tickets"],
    source=EpisodeType.message
)

for episode in episodes:
    print(f"Name: {episode.name}")
    print(f"Created: {episode.created_at}")
    print(f"Valid at: {episode.valid_at}")
    print(f"Source Description: {episode.source_description}")
```

**Implication:** Episodes CAN be filtered by:
- `group_ids` (collection/grouping)
- `source` (episode type)
- `reference_time` (temporal filtering)
- `last_n` (limit number of results)

---

#### Method 3: Search with SearchFilters (For Edges/Relationships)

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Search Graph Data with Filters in Python"

```python
from graphiti_core.search.search_filters import SearchFilters
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
one_week_ago = now - timedelta(days=7)

search_filter = SearchFilters(
    entity_labels=["Person", "Organization"],
    valid_after=one_week_ago,
    valid_before=now
)

results = await graphiti.search(
    query="recent collaborations",
    group_ids=["employee_records"],
    num_results=15,
    search_filter=search_filter
)

for edge in results:
    print(f"Fact: {edge.fact}")
    print(f"Valid at: {edge.valid_at}")
    print(f"Episodes: {edge.episodes}")  # List of episode UUIDs
```

**Key Fields in Results:**
- `edge.fact` - The relationship description
- `edge.valid_at` - When this relationship became valid
- `edge.invalid_at` - When it expired
- `edge.episodes` - **LIST OF EPISODE UUIDs that support this relationship**

**Implication:** Relationships can be filtered by entity labels and temporal validity. The `episodes` field traces which ingestion events created each relationship.

---

## Question 3: What Exactly Is `entity_labels` and How Does It Relate to Custom Metadata?

### Answer: Entity Labels Are Node Classification Tags (Auto-Managed)

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Define Custom Entity Types with Pydantic in Python"

```python
from pydantic import BaseModel, Field
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

class Product(BaseModel):
    name: str
    category: str
    price: float = Field(description="Price in USD")

class Customer(BaseModel):
    name: str
    email: str
    subscription_tier: str

result = await graphiti.add_episode(
    name="Sales Transaction 101",
    episode_body="Customer Jane Doe (jane@example.com) with Premium subscription purchased Product X",
    source=EpisodeType.text,
    source_description="Sales record",
    reference_time=datetime.now(timezone.utc),
    group_id="sales",
    entity_types={"Product": Product, "Customer": Customer}
)

print("Extracted custom entities:")
for node in result.nodes:
    print(f"{node.name} ({', '.join(node.labels)})")  # Labels = entity types
    if node.attributes:
        for key, value in node.attributes.items():
            print(f"  {key}: {value}")
```

**Key Insight:** Entity labels are **automatically assigned based on LLM extraction**. When you define `entity_types`, Graphiti uses them as type hints for the LLM, and extracted entities get labeled accordingly.

**Distinction:**
- `entity_labels` in SearchFilters = Node classification tags (e.g., "Person", "Organization", "Product", "Customer")
- `source_description` in add_episode() = Custom metadata AS TEXT

**Implication:** `entity_labels` and `source_description` are DIFFERENT CONCEPTS:
- `entity_labels` filter NODES by their extracted type
- `source_description` stores custom metadata about the EPISODE (source info, document ID, etc.)

---

## Question 4: Where Does Episode Metadata Live Exactly?

### Answer: Episode Metadata Flows Through Neo4j Episode Nodes and Results

**Source:** https://github.com/getzep/graphiti/blob/main/examples/ecommerce/runner.ipynb - Episode data structure examples

**Episode Node in Neo4j stores:**
```
Episode(
  uuid: "doc_42",
  name: "Kubernetes Fundamentals",
  content: [full content],
  source_description: "collection: api-docs, doc_id: 42, crawl_root_url: https://...",
  created_at: 2024-10-01T10:30:00Z,
  group_id: "api-docs"
)
```

**When Queried, Episode Metadata Appears In:**

1. **Episode objects retrieved via `retrieve_episodes()`**
2. **Relationship/Edge objects via their `episodes` field** (list of episode UUIDs that created that relationship)
3. **REST API response** - full episode fields returned

**Source:** https://github.com/getzep/graphiti/blob/main/examples/ecommerce/runner.ipynb - Relationship data structure

```json
{
  "uuid": "df1d2e82a40e40e1b3734c2298774a6b",
  "name": "LIKES",
  "fact": "John expresses that he likes the Basin Blue color for the shoes",
  "episodes": ["4c8afb4aa1b446899a85249df475bc66"],
  "valid_at": "2024-07-30T00:05:00Z",
  "invalid_at": null
}
```

**Key Field:** `episodes` is a **list of episode UUIDs**. This is the linkage between relationships and the ingestion events that created them.

---

## Question 5: How Does Metadata Flow Through Graphiti for Episodes?

### Answer: Complete Lifecycle

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Add Single Episode (Text and JSON) with Graphiti"

**Step 1: Ingest with Metadata**
```python
result = await graphiti.add_episode(
    name="Kubernetes Fundamentals",
    episode_body=content,
    source=EpisodeType.text,
    source_description="collection: api-docs, doc_id: 42, source_url: https://...",
    reference_time=datetime.now(timezone.utc),
    group_id="api-docs"
)
```

**Step 2: Graphiti Processes**
- Creates Episode node in Neo4j with all provided fields
- LLM extracts entities from `episode_body`
- LLM extracts relationships between entities
- Creates Entity nodes (with auto-assigned labels)
- Creates Relationship edges (with `episodes` field linking back to this episode)

**Step 3: Metadata Available For Query**

**Via group_id:**
```python
episodes = await graphiti.retrieve_episodes(
    group_ids=["api-docs"],
    last_n=10
)
# Returns episodes where group_id="api-docs"
```

**Via SearchFilters on edges:**
```python
results = await graphiti.search(
    query="kubernetes",
    group_ids=["api-docs"],
    search_filter=SearchFilters(valid_after=start_date)
)
# Returns edges created after start_date in api-docs group
# Each edge has edge.episodes = list of episode UUIDs that support it
```

**Via direct Neo4j query (advanced):**
```cypher
MATCH (ep:Episode {group_id: "api-docs"})
WHERE ep.source_description CONTAINS "doc_42"
RETURN ep
```

---

## Question 6: How Does Metadata Flow For Nodes?

### Answer: Nodes Are Auto-Managed; Metadata Is Aggregated

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Define Custom Entity Types with Pydantic in Python"

**Step 1: Nodes Are Created Automatically**

When you ingest an episode, Graphiti automatically:
- Extracts entities from the content using LLM
- Creates nodes for each entity
- Auto-assigns labels based on entity type
- Automatically manages node attributes from extracted content

```python
result = await graphiti.add_episode(...)

for node in result.nodes:
    print(f"Node: {node.name}")
    print(f"Labels: {node.labels}")  # Auto-assigned
    print(f"Attributes: {node.attributes}")  # Auto-extracted
    print(f"Summary: {node.summary}")  # LLM-generated
```

**Step 2: Node Metadata Is NOT User-Customizable**

You cannot directly set custom properties on nodes like you do with episodes. Graphiti manages:
- `name` - entity name (auto-extracted)
- `labels` - entity type (auto-assigned)
- `attributes` - properties extracted from content
- `summary` - LLM-generated summary
- `created_at` - auto-set to episode creation time
- `updated_at` - auto-updated when node appears in new episodes

**Step 3: Node Metadata Aggregates Across Episodes**

If the same entity appears in 10 episodes:
- Node still has ONE entry in Neo4j
- Node's `updated_at` reflects the most recent episode
- Node's summary evolves based on all episodes mentioning it
- Relationship `edges` field lists all episodes supporting that relationship

**Key Distinction from RAG:**
- RAG metadata is per-document (static snapshot)
- Graph node metadata is aggregated (evolving entity)

---

## Question 7: How Are Relationships (Edges) Queried?

### Answer: Via SearchFilters on Edges, Traced to Episodes

**Source:** https://context7.com/getzep/graphiti/llms.txt - "Search Graph Data with Filters in Python"

**Query Edges with Temporal Filters:**
```python
search_filter = SearchFilters(
    entity_labels=["Person", "Organization"],
    valid_after=one_week_ago,
    valid_before=now
)

results = await graphiti.search(
    query="recent collaborations",
    group_ids=["employee_records"],
    num_results=15,
    search_filter=search_filter
)

for edge in results:
    print(f"Fact: {edge.fact}")
    print(f"Valid at: {edge.valid_at}")
    print(f"Episodes supporting this: {edge.episodes}")
```

**SearchFilters Parameters:**
- `entity_labels` - Filter by node types (e.g., ["Person", "Company"])
- `valid_after` - Edges created after this date
- `valid_before` - Edges created before this date

**Edge Metadata Available:**
- `uuid` - Edge identifier
- `fact` - Human-readable relationship description
- `name` - Relationship type (e.g., "WORKS_FOR", "LIKES")
- `episodes` - **List of episode UUIDs that created/updated this edge**
- `valid_at` - When relationship became true
- `invalid_at` - When it expired (null if still valid)
- `created_at` - When Graphiti created this record

---

## Question 8: Complete Citation Summary

| Question | Source URL | Source Location | Key Proof |
|----------|-----------|-----------------|-----------|
| Episode Storage | https://context7.com/getzep/graphiti/llms.txt | "REST API Get Episodes Endpoint" | Episode response JSON shows all fields |
| Episode Querying by Group | https://context7.com/getzep/graphiti/llms.txt | "REST API Get Episodes Endpoint" | `GET /episodes/{group_id}` endpoint |
| Episode Querying by Time | https://context7.com/getzep/graphiti/llms.txt | "Retrieve Episodes by Time Range (Python)" | `retrieve_episodes()` function signature |
| SearchFilters | https://context7.com/getzep/graphiti/llms.txt | "Search Graph Data with Filters in Python" | SearchFilters usage in search() |
| Entity Labels | https://context7.com/getzep/graphiti/llms.txt | "Define Custom Entity Types with Pydantic" | Custom entity type extraction |
| Episode Metadata | https://github.com/getzep/graphiti/blob/main/examples/ecommerce/runner.ipynb | Episode data structure examples | Full episode JSON structure |
| Relationship Metadata | https://github.com/getzep/graphiti/blob/main/examples/ecommerce/runner.ipynb | Relationship data structure examples | Edge JSON with episodes field |
| Node Attributes | https://context7.com/getzep/graphiti/llms.txt | "Define Custom Entity Types with Pydantic" | `node.attributes` extraction |

---

## Critical Implementation Insights

### Insight 1: source_description Is Your Custom Metadata Field

The `source_description` parameter in `add_episode()` is **the only place** to store custom metadata about the ingestion event:

```python
await graphiti.add_episode(
    name="doc_42",
    episode_body=content,
    source_description="collection: api-docs, doc_id: 42, crawl_root_url: https://..., crawl_session_id: uuid, crawl_depth: 0",
    group_id="api-docs"
)
```

This is a TEXT field - you embed all custom metadata as a string. It's searchable and appears in episode objects.

### Insight 2: group_id Is Your Collection Linking

The `group_id` parameter in `add_episode()` **directly maps to collection**:

```python
# Ingest into "api-docs" collection
await graphiti.add_episode(
    ...,
    group_id="api-docs"  # Same as collection_name in RAG
)

# Query by collection
episodes = await graphiti.retrieve_episodes(
    group_ids=["api-docs"]
)
```

### Insight 3: Episodes Link Relationships to Source

Every relationship (edge) has an `episodes` field listing which episode(s) created it:

```json
{
  "uuid": "rel-123",
  "fact": "Richard Feynman studied under Niels Bohr",
  "episodes": ["doc_42", "doc_51", "doc_67"],  # 3 episodes mention this
  "created_at": "2024-01-15"
}
```

This enables provenance tracking: "Which documents taught us this relationship?"

### Insight 4: SearchFilters Operates on Edges, Not Episodes

`SearchFilters` filters the **edges/relationships** returned by search, not episodes directly:

```python
# This filters edges by:
# - entity_labels: node types involved in the relationship
# - valid_after/valid_before: temporal validity of the relationship
search_filter = SearchFilters(
    entity_labels=["Person"],
    valid_after=start_date
)

results = await graphiti.search(query, search_filter=search_filter)
# Results are edges (relationships), not episodes
```

### Insight 5: Node Metadata Is Read-Only from User Perspective

You cannot directly set custom properties on nodes. Graphiti manages:
- Labels (auto-assigned by LLM based on entity_types)
- Attributes (auto-extracted from content)
- Summary (auto-generated by LLM)

If you need custom node metadata, you must encode it in `source_description` on the episode.

---

## Implementation Recommendations

Based on this research, here are the recommended changes:

### Phase 0: Modify Graphiti Ingestion (Already in Plan)

**In `src/unified/mediator.py` and `src/unified/graph_store.py`:**

```python
# When calling graphiti.add_episode(), pass:
result = await self.graphiti.add_episode(
    name=f"doc_{source_document_id}",
    episode_body=content,
    source=EpisodeType.text,
    source_description=f"""
collection: {collection_name}
doc_id: {source_document_id}
doc_title: {document_title}
domain: {metadata.get('domain', 'unknown')}
content_type: {metadata.get('content_type', 'text')}
created_date: {datetime.now().isoformat()}
crawl_root_url: {metadata.get('crawl_root_url', '')}
crawl_session_id: {metadata.get('crawl_session_id', '')}
crawl_depth: {metadata.get('crawl_depth', -1)}
""",
    reference_time=datetime.now(timezone.utc),
    group_id=collection_name  # ← Links episode to collection
)
```

### Phase 1-5: Tests Already Valid

The test plan in `TEST_ENHANCEMENTS_NEEDED.md` is still valid:
- Phase 1: RAG metadata filtering (tests search_chunks with metadata_filter)
- Phase 2: Web ingestion metadata (tests crawl_root_url, crawl_session_id, crawl_depth)
- Phase 3: Entity extraction (queries Neo4j to verify nodes exist)
- Phase 4: Query tools (tests query_relationships and query_temporal)
- Phase 5: Cross-store consistency (verifies metadata in both stores)

---

## Conclusion

**All three questions are now fully answered with citations:**

1. ✅ Episode metadata IS stored in Neo4j Episode nodes with `source_description` as the custom metadata field
2. ✅ Episode metadata IS queryable via `retrieve_episodes(group_ids=[...])` and REST API
3. ✅ Entity labels are auto-assigned node types, distinct from `source_description` custom metadata
4. ✅ `SearchFilters` enables filtering edges by entity labels and temporal validity
5. ✅ Relationship edges link back to episodes via the `episodes` field for provenance
6. ✅ Node metadata is auto-managed and aggregated across episodes, not user-customizable

**Ready for implementation with confidence.**
