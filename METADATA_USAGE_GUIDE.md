# Metadata Usage Guide

Quick reference for using metadata in the RAG + Knowledge Graph system.

---

## Quick Start

### 1. Ingest with Metadata (All Methods)

**Text Ingestion:**
```python
from src.unified.mediator import UnifiedIngestionMediator

result = await mediator.ingest_text(
    content="Your content here",
    collection_name="my-collection",
    document_title="Document Title",
    metadata={
        "domain": "backend",
        "content_type": "documentation",
        "version": "2.0",
        "author": "team-x"
    }
)
```

**File Ingestion:**
```python
from src.ingestion.document_store import get_document_store

source_id, chunk_ids = doc_store.ingest_document(
    content="File content",
    filename="myfile.txt",
    collection_name="my-collection",
    metadata={"domain": "frontend", "source": "local"},
    file_type="text"
)
```

**URL Ingestion (Web Crawling):**
```python
source_id, chunk_ids = doc_store.ingest_url(
    url="https://docs.example.com/api",
    collection_name="web-docs",
    metadata={"content_type": "api-docs"}  # Optional, crawl adds crawl_* fields
)
```

### 2. Search with Metadata Filtering (RAG)

**Single Filter:**
```python
results = searcher.search_chunks(
    query="authentication",
    collection_name="my-collection",
    metadata_filter={"domain": "backend"},
    limit=10,
    threshold=0.7
)
```

**Multiple Filters (AND Logic):**
```python
results = searcher.search_chunks(
    query="API endpoints",
    collection_name="my-collection",
    metadata_filter={
        "domain": "backend",
        "content_type": "documentation"
    },
    limit=10
)
```

**Web Crawl Filtering:**
```python
# Only from specific site
results = searcher.search_chunks(
    query="features",
    metadata_filter={"crawl_root_url": "https://docs.example.com"},
    limit=10
)

# Only root pages
results = searcher.search_chunks(
    query="features",
    metadata_filter={"crawl_depth": 0},
    limit=10
)

# Only from specific crawl session
results = searcher.search_chunks(
    query="features",
    metadata_filter={"crawl_session_id": "abc-123-def"},
    limit=10
)
```

### 3. Search for Relationships (Knowledge Graph)

**Query Relationships:**
```python
relationships = await graph_store.search_relationships(
    query="How do company A and company B relate?",
    num_results=5
)

for rel in relationships:
    print(rel)  # Each result contains relationship info
```

**Track Temporal Evolution:**
```python
timeline = await graph_store.query_temporal(
    query="How has the strategy changed?",
    num_results=10
)

for item in timeline:
    print(f"Timeline: {item['fact']}")
    print(f"Valid from: {item['valid_from']}")
    print(f"Valid until: {item['valid_until']}")
```

---

## Metadata Field Reference

### Standard Fields (All Ingestion Methods)

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| domain | string | Content domain/category | "backend", "frontend", "devops" |
| content_type | string | Type of content | "documentation", "guide", "api-docs", "tutorial" |
| version | string | Version identifier | "2.0", "3.1", "alpha" |
| author | string | Document author/creator | "team-x", "john-doe" |
| created_date | string | Creation date (ISO 8601) | "2025-10-20T10:30:00Z" |
| topic | string | Primary topic | "authentication", "deployment" |
| concepts | list | Related concepts | ["OAuth", "JWT", "token"] |

### Web Crawling Fields (Auto-added)

| Field | Type | Description | Set By |
|-------|------|-------------|--------|
| crawl_root_url | string | Starting URL of crawl | Web crawler |
| crawl_session_id | string | UUID identifying crawl session | Web crawler |
| crawl_depth | integer | Distance from root (0=root) | Web crawler |
| crawl_timestamp | string | When crawl occurred (ISO 8601) | Web crawler |
| parent_url | string | URL of parent page (if depth > 0) | Web crawler |

### System Fields (Auto-set)

| Field | Type | Description |
|-------|------|-------------|
| source_document_id | integer | RAG store document ID |
| filename | string | Document filename |
| collection_name | string | Collection name |

---

## Common Patterns

### Pattern 1: Domain-Based Organization

Organize content by domain:

```python
# Ingest backend docs
await mediator.ingest_text(
    content="...",
    collection_name="api-docs",
    document_title="Authentication",
    metadata={"domain": "backend", "content_type": "documentation"}
)

# Ingest frontend docs
await mediator.ingest_text(
    content="...",
    collection_name="api-docs",
    document_title="UI Components",
    metadata={"domain": "frontend", "content_type": "documentation"}
)

# Query backend only
results = searcher.search_chunks(
    query="authentication",
    collection_name="api-docs",
    metadata_filter={"domain": "backend"}
)
```

### Pattern 2: Version Control

Track content by version:

```python
# Ingest v1.0 docs
await mediator.ingest_url(
    url="https://docs.example.com/v1.0",
    collection_name="docs",
    metadata={"version": "1.0"}
)

# Ingest v2.0 docs
await mediator.ingest_url(
    url="https://docs.example.com/v2.0",
    collection_name="docs",
    metadata={"version": "2.0"}
)

# Query specific version
results = searcher.search_chunks(
    query="API endpoints",
    metadata_filter={"version": "2.0"}
)
```

### Pattern 3: Multi-Site Content

Manage multiple sites in one collection:

```python
# Crawl site A
ingest_url(
    url="https://site-a.com/docs",
    collection_name="all-docs"
)

# Crawl site B
ingest_url(
    url="https://site-b.com/docs",
    collection_name="all-docs"
)

# Query site A only
results = searcher.search_chunks(
    query="features",
    metadata_filter={"crawl_root_url": "https://site-a.com/docs"}
)

# Recrawl site A (updates without affecting site B)
ingest_url(
    url="https://site-a.com/docs",
    collection_name="all-docs",
    mode="recrawl"
)
```

### Pattern 4: Relationship Discovery

Find connections across documents:

```python
# Ingest document about Company A
await mediator.ingest_text(
    content="Company A founded by Person X, specializes in cloud services",
    collection_name="companies",
    metadata={"content_type": "company-profile"}
)

# Ingest document about Company B
await mediator.ingest_text(
    content="Company B competes with Company A in cloud market",
    collection_name="companies",
    metadata={"content_type": "company-profile"}
)

# Find relationships
relationships = await graph_store.search_relationships(
    query="Which companies are competitors?",
    num_results=10
)
```

### Pattern 5: Temporal Tracking

Track evolution of knowledge:

```python
# Ingest current strategy
await mediator.ingest_text(
    content="Current strategy focuses on X, Y, Z",
    collection_name="strategy",
    document_title="Q4 2025 Strategy",
    metadata={"quarter": "Q4", "year": "2025"}
)

# Track how it evolved
timeline = await graph_store.query_temporal(
    query="How has our strategy changed?",
    num_results=20
)

# See what was true when
for item in timeline:
    if item['status'] == 'current':
        print(f"Current: {item['fact']}")
    else:
        print(f"Previous: {item['fact']} (until {item['valid_until']})")
```

---

## Filtering Rules

### Supported Operators

Currently, metadata filtering uses **equality matching only**:

```python
# ✅ Works: Exact match
{"domain": "backend"}
{"version": "2.0"}
{"crawl_depth": 0}

# ❌ Not supported: Ranges, wildcards, operators
# {"version": ">= 2.0"}        # Not supported
# {"domain": "back*"}          # Not supported
# {"crawl_depth": {"$gt": 0}}  # Not supported
```

### Filter Combinations

**AND Logic** (multiple fields all must match):

```python
# All must match:
{
    "domain": "backend",           # AND
    "content_type": "documentation"  # AND
}
```

**OR Logic** (not directly supported, use multiple queries):

```python
# Query 1: backend domain
results1 = searcher.search_chunks(..., metadata_filter={"domain": "backend"})

# Query 2: frontend domain
results2 = searcher.search_chunks(..., metadata_filter={"domain": "frontend"})

# Combine results manually if needed
all_results = results1 + results2
```

---

## Data Flow Diagram

```
Ingestion Methods
    ↓
    ├─ ingest_text()
    ├─ ingest_url()
    ├─ ingest_file()
    └─ ingest_directory()
         ↓
UnifiedIngestionMediator
    ├─ RAG Store (PostgreSQL + pgvector)
    │  └─ metadata: JSONB column
    │     └─ Queryable via metadata_filter parameter
    │
    └─ Graph Store (Neo4j + Graphiti)
       └─ Metadata embedded in episode.source_description
          └─ Queryable via search_relationships() / query_temporal()
```

---

## Best Practices

### 1. Consistent Metadata Schema

Define metadata structure at collection level:

```python
# Document expected metadata for your collection
COLLECTION_METADATA = {
    "domain": "backend | frontend | devops",
    "content_type": "documentation | tutorial | example",
    "version": "string",
    "author": "string"
}

# Use consistently across all ingestions
for doc in documents:
    await mediator.ingest_text(
        content=doc["content"],
        collection_name="api-docs",
        metadata={
            "domain": determine_domain(doc),
            "content_type": determine_type(doc),
            "version": "2.0",
            "author": "team-x"
        }
    )
```

### 2. Semantic Metadata Values

Use meaningful, standardized values:

```python
# ✅ Good: Consistent, queryable
{"domain": "backend", "content_type": "api-docs", "version": "2.0"}

# ❌ Problematic: Inconsistent formatting
{"domain": "Back end", "content_type": "api doc", "version": "v2.0"}
```

### 3. Combine Collection + Metadata

Use collections for major divisions, metadata for attributes:

```python
# Collections: High-level grouping
- "customer-docs"
- "api-docs"
- "internal-wiki"

# Metadata: Fine-grained attributes
- domain: backend / frontend / devops
- version: 1.0 / 2.0 / 3.0
- content_type: documentation / tutorial / example
```

### 4. Web Crawl Strategy

Use metadata to manage multiple web sources:

```python
# Crawl site A (depth 2)
ingest_url(
    url="https://docs-a.com",
    collection_name="api-docs",
    follow_links=True,
    max_depth=2
)

# Crawl site B (depth 1)
ingest_url(
    url="https://guides-b.com",
    collection_name="api-docs",
    follow_links=True,
    max_depth=1
)

# Later: Recrawl site A to freshen content
ingest_url(
    url="https://docs-a.com",
    collection_name="api-docs",
    mode="recrawl",
    follow_links=True,
    max_depth=2
)
```

### 5. Relationship Queries

Ask specific questions about your data:

```python
# Find direct connections
await graph_store.search_relationships(
    query="What products does Company X make?"
)

# Find indirect connections
await graph_store.search_relationships(
    query="How do these projects relate?"
)

# Find changes over time
await graph_store.query_temporal(
    query="How has project scope evolved?"
)
```

---

## Troubleshooting

### Issue: Metadata filter returns no results

**Check:**
1. Is the metadata field spelled correctly?
2. Is the field value exact match (including capitalization)?
3. Does the document have that field?

```python
# Debug: Search without filter first
results = searcher.search_chunks(query="...", limit=1)
print(results[0].metadata)  # See actual metadata

# Then filter with correct field name/value
results = searcher.search_chunks(
    query="...",
    metadata_filter={"domain": results[0].metadata["domain"]}
)
```

### Issue: Web recrawl not deleting old pages

**Check:**
1. Are you using `mode="recrawl"`?
2. Does the URL exactly match `crawl_root_url`?

```python
# Correct: Deletes old pages from this URL
ingest_url(
    url="https://docs.example.com",
    collection_name="api-docs",
    mode="recrawl"
)

# Subpages must use same root URL
ingest_url(
    url="https://docs.example.com/api/v2",
    collection_name="api-docs",
    mode="recrawl"
)
```

### Issue: Relationships not found

**Check:**
1. Have you ingested content with entities?
2. Has Graphiti extracted entities? (Check Neo4j)
3. Are you using meaningful search queries?

```python
# Debug: Check entities in Neo4j
result = await graphiti.driver.execute_query(
    "MATCH (n) WHERE NOT (n:Episodic) RETURN n LIMIT 10"
)
print(result.records)  # See if entities exist
```

---

## Examples

See the test files for complete working examples:

- **RAG Filtering:** `tests/integration/test_metadata_rag_search.py`
- **Web Metadata:** `tests/integration/test_web_ingestion_metadata.py`
- **Graph Extraction:** `tests/integration/test_graph_entity_extraction.py`
- **Query Tools:** `tests/integration/test_query_tools_verification.py`
- **Cross-Store:** `tests/integration/test_metadata_consistency.py`

---

## Performance Notes

- **Metadata Filtering (RAG):** Sub-millisecond via database indexes
- **Entity Extraction (Graph):** 30-60 seconds per document (LLM-based)
- **Relationship Queries:** 2-10 seconds depending on graph size
- **Temporal Queries:** 2-10 seconds depending on timeline size

---

## Support

For issues or questions, check:
1. `METADATA_IMPLEMENTATION_SUMMARY.md` - Comprehensive overview
2. `IMPLEMENTATION_PLAN_METADATA.md` - Implementation details
3. `GRAPHITI_METADATA_RESEARCH.md` - Graphiti API research
4. Test files - Working examples

---

**Last Updated:** 2025-10-20
**Status:** ✅ Production Ready
