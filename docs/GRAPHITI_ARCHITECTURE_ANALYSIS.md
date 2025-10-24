# Graphiti Integration - Comprehensive Architectural Analysis

**Document Type:** Architectural Decision Record + Integration Patterns + Production Readiness Guide
**Created:** 2025-10-23
**Status:** Definitive Reference for Graphiti Integration in RAG Memory
**Version:** 1.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Decision Record (ADR)](#architectural-decision-record-adr)
3. [Graphiti Integration Patterns](#graphiti-integration-patterns)
4. [Known Limitations & Workarounds](#known-limitations--workarounds)
5. [Production Readiness Checklist](#production-readiness-checklist)
6. [Future Enhancements](#future-enhancements)
7. [References](#references)

---

## Executive Summary

### System Overview

RAG Memory integrates **Graphiti** (temporal knowledge graph engine) with **Neo4j** to provide relationship tracking and temporal reasoning on top of PostgreSQL pgvector-based semantic search.

**Key Achievement:** Dual-store architecture enabling both "what information exists?" (RAG) and "how is information related?" (Graph) queries.

### Critical Findings

#### 1. Temporal Search Implementation Gap (HIGH PRIORITY)

**Problem Identified:**
Current `search_temporal()` method in `src/unified/graph_store.py` (lines 386-416) does **NOT** perform temporal search.

**Current Implementation:**
```python
# ❌ BROKEN - This is just looser filtering, not temporal search
async def search_temporal(query: str, num_results: int = 5):
    config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
        "limit": num_results,
        "reranker_min_score": 0.5  # Lower threshold
    })
    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=SearchFilters()  # ❌ Empty - no temporal filtering!
    )
```

**Root Cause:**
Graphiti does **NOT** automatically detect temporal intent from query text. Temporal search requires **explicit SearchFilters with valid_at/invalid_at date constraints**.

**Impact:**
- Temporal queries return 0 results despite relevant content existing
- Method name is misleading (implies temporal search capability)
- Lower threshold (0.5 vs 0.7) just returns lower-quality results, not temporal data

**Resolution Required:**
See Section 2.3 for complete fix implementation.

#### 2. Architecture Decision: Knowledge Graph Optionality

**Current State:** Phase 3 Complete, Phase 4 In Progress
**Deployment Mode:** ALL OR NOTHING (Option B)

**Decision:**
Both PostgreSQL and Neo4j MUST be operational at all times. No graceful degradation to RAG-only mode.

**Rationale:**
1. **Simpler Architecture:** No conditional logic, fewer failure modes
2. **Better UX:** Clear expectation: "You need both databases"
3. **Cleaner Code:** No complex fallback paths
4. **Reduced Testing Surface:** Single deployment mode to validate

**Consequences:**
- ✅ Cleaner codebase, predictable behavior
- ✅ Docker Compose sets up both automatically
- ❌ Cannot run RAG-only if Neo4j unavailable
- ❌ Higher infrastructure requirements

**Implementation Status:**
- Health checks validate both databases at startup
- Server refuses to start if either database unavailable
- All write operations require health checks on both databases

See `docs/STARTUP_VALIDATION_IMPLEMENTATION.md` for details.

#### 3. Phase 4 Implementation Gaps

**CRITICAL LIMITATIONS (Not Production-Ready):**

| Operation | RAG Status | Graph Status | Issue |
|-----------|-----------|--------------|-------|
| `update_document()` | ✅ Working | ❌ Not cleaned | Stale entities remain |
| `delete_document()` | ✅ Working | ❌ Not cleaned | Orphaned episodes accumulate |
| `recrawl()` | ✅ Working | ❌ Not cleaned | Old episodes remain |

**Workaround Until Phase 4:**
Manual Neo4j cleanup using Cypher queries (see Section 4.3).

**Production Recommendation:**
Wait for Phase 4 completion before production deployment.

---

## Architectural Decision Record (ADR)

### ADR-001: Temporal Search Design

**Status:** DECIDED
**Date:** 2025-10-23
**Decision Makers:** Development Team
**Tags:** temporal-search, graphiti, search-filters

#### Context

Graphiti provides temporal knowledge graph capabilities through bi-temporal data model:
- **Timeline T (Event Time):** `valid_at`, `invalid_at` - when facts occurred in reality
- **Timeline T' (Transaction Time):** `created_at`, `expired_at` - when system learned about facts

We need to enable temporal queries like:
- "When was machine learning first mentioned?"
- "What was the CEO structure on Jan 1, 2023?"
- "How did our architecture evolve in 2023?"

#### Problem

How should temporal search work in our system?

**Three Options Considered:**

1. **Explicit Temporal Parameters (Recommended)**
   - Accept `time_range_start`, `time_range_end` as method parameters
   - Construct SearchFilters with DateFilter objects
   - Clear, testable, predictable

2. **Auto-Detection from Query Text**
   - Parse queries for keywords: "when", "before", "after", "during"
   - Automatically apply temporal filtering
   - User-friendly but brittle and unpredictable

3. **Threshold-Based (Current Implementation - BROKEN)**
   - Lower reranker threshold to capture more results
   - Assume this reveals temporal patterns
   - **Problem:** Doesn't actually filter by time, just returns more low-quality results

#### Decision

**CHOSEN: Option 1 - Explicit Temporal Parameters**

**Implementation Pattern:**
```python
async def search_temporal(
    self,
    query: str,
    time_range_start: datetime | None = None,
    time_range_end: datetime | None = None,
    include_current_facts: bool = True,
    num_results: int = 5
) -> list[Any]:
    filters = SearchFilters()

    # Build temporal constraints if dates provided
    if time_range_end:
        filters.valid_at = [
            [DateFilter(
                date=time_range_end,
                comparison_operator=ComparisonOperator.less_than_equal
            )]
        ]

    if time_range_start:
        invalid_at_conditions = [
            [DateFilter(
                date=time_range_start,
                comparison_operator=ComparisonOperator.greater_than_equal
            )]
        ]
        if include_current_facts:
            invalid_at_conditions.append([
                DateFilter(
                    date=None,
                    comparison_operator=ComparisonOperator.is_null
                )
            ])
        filters.invalid_at = invalid_at_conditions

    # Use RRF for broader recall (vs cross-encoder precision)
    config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})

    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=filters
    )

    return search_results.edges if search_results.edges else []
```

#### Consequences

**Positive:**
- ✅ Explicit, clear API - no magic or guessing
- ✅ Testable with precise date ranges
- ✅ Language-independent (works across all MCP clients)
- ✅ No keyword parsing brittleness
- ✅ Supports all temporal query types (range, point-in-time, before/after)

**Negative:**
- ❌ Requires users to provide dates explicitly
- ❌ MCP tool callers must format ISO 8601 strings
- ❌ Slightly more verbose than auto-detection

**Trade-offs Accepted:**
- Verbosity over magic: Better for production systems
- Explicit over implicit: Clearer debugging and testing
- Type safety over convenience: Prevents runtime errors

#### Alternatives Explored

**Option 2 (Auto-Detection) Rejected Because:**
- Keyword matching is fragile ("when" could be non-temporal)
- Query rephrasing breaks detection
- Hard to debug when it doesn't trigger
- No official Graphiti support for this pattern
- Users don't understand why searches behave differently

**Option 3 (Threshold-Based) Rejected Because:**
- **Fundamentally broken:** Lower threshold ≠ temporal filtering
- No SearchFilters means no actual temporal constraints
- Returns irrelevant results with low scores
- Misleading method name creates false expectations
- No examples in Graphiti documentation supporting this pattern

#### Implementation Plan

**Phase 1: Fix search_temporal() (Immediate)**
1. Replace current implementation with explicit temporal parameters
2. Update method signature in `src/unified/graph_store.py`
3. Add comprehensive docstring with temporal logic explanation

**Phase 2: Update MCP Tool (Next)**
1. Modify `query_temporal_impl()` in `src/mcp/tools.py`
2. Accept `time_range_start`, `time_range_end` as ISO 8601 strings
3. Convert to datetime objects, call graph_store.search_temporal()
4. Update tool docstring with examples

**Phase 3: Add Tests (Validation)**
1. Unit tests for temporal filtering logic
2. Integration tests for MCP tool
3. Test edge cases (no dates, single date, range queries)

**Phase 4: Documentation (User-Facing)**
1. Update `.reference/KNOWLEDGE_GRAPH.md` with temporal examples
2. Add temporal query guide to MCP_QUICK_START.md
3. Create temporal search cookbook with common patterns

#### Success Metrics

- ✅ Temporal queries return results for relevant content with date filters
- ✅ Irrelevant temporal queries return empty (no false positives)
- ✅ Point-in-time queries work correctly
- ✅ Range queries span boundaries correctly
- ✅ All temporal test cases pass

---

### ADR-002: Search Method Selection (RRF vs CrossEncoder vs MMR)

**Status:** DECIDED
**Date:** 2025-10-23
**Decision Makers:** Development Team
**Tags:** search-config, reranker, performance

#### Context

Graphiti provides three reranking methods:
1. **RRF (Reciprocal Rank Fusion)** - Combines semantic + BM25 by rank position
2. **MMR (Maximal Marginal Relevance)** - Balances relevance + diversity
3. **CrossEncoder** - LLM-based binary classification (relevant/irrelevant)

Each has different performance characteristics and use cases.

#### Decision

**Use Case-Based Selection:**

| Search Type | Chosen Method | Threshold | Rationale |
|-------------|---------------|-----------|-----------|
| **Relational** (query_relationships) | CrossEncoder | 0.7 | High precision needed, willing to trade performance |
| **Temporal** (query_temporal) | RRF | Default (0.6 sim_min_score) | Broader recall for context, temporal questions need more results |
| **General** (if added) | RRF | Default | Balanced performance + quality |

#### Rationale

**For Relational Search (CrossEncoder):**
- Need high confidence in relevance (0.7 = "True/relevant")
- Relationship queries should be precise, not broad
- User expects "quality over quantity"
- Performance cost acceptable (~500-800ms vs ~100-200ms for RRF)

**For Temporal Search (RRF):**
- Temporal context requires broader results to show evolution
- Lower precision acceptable if we capture more timeline entries
- Better performance than cross-encoder (~100-200ms vs ~500-800ms)
- Temporal filtering already narrows results via SearchFilters

**Evidence from Graphiti Documentation:**

From official docs:
> "RRF (Default): Intelligently combines results from both semantic similarity and BM25 full-text search by merging rank positions from both approaches."

> "Use cross encoder when you need the highest accuracy in relevance scoring and are willing to trade some performance for better results."

> "Use MMR when you need diverse information for comprehensive context."

#### Consequences

**CrossEncoder for Relational:**
- ✅ High-quality relationship results
- ✅ Low false positive rate
- ❌ Slower queries (~500-800ms)
- ❌ More expensive (additional LLM call)

**RRF for Temporal:**
- ✅ Fast queries (~100-200ms)
- ✅ Better recall for temporal evolution
- ✅ Balanced semantic + keyword matching
- ❌ Some false positives possible (mitigated by temporal filters)

#### Threshold Tuning

**CrossEncoder Sigmoid Scores (0-1 range):**
- **0.7+** = "True/relevant" (high confidence) ← Used for relational
- **0.5-0.7** = "Maybe relevant" (medium confidence) ← Previously used incorrectly for temporal
- **< 0.5** = "False/irrelevant" (low confidence)

**Reasoning:**
Cross-encoder asks LLM: "Is this relevant?" and uses logprobs to generate 0-1 score. Scores follow sigmoid curve with sharp drop-off between relevant and irrelevant results.

**RRF Score Calculation:**
```python
# From graphiti_core/search/search_utils.py
score = 1 / (position + rank_const)
```
No explicit threshold needed - ranking naturally prioritizes better matches.

---

### ADR-003: Knowledge Graph Optionality Architecture

**Status:** DECIDED (Option B: All or Nothing)
**Date:** 2025-10-21
**Decision Makers:** Development Team
**Tags:** architecture, deployment, databases

#### Context

Knowledge Graph (Neo4j + Graphiti) was initially designed as "optional" - system should work with just PostgreSQL for RAG.

**Challenges Identified:**
1. MCP tools `query_relationships` and `query_temporal` useless without Neo4j
2. Unclear whether ingestion fails if graph unavailable
3. Complex conditional logic throughout codebase
4. Inconsistent error handling (silent vs loud failures)
5. Documentation ambiguity about what "optional" means

#### Decision

**CHOSEN: Option B - Mandatory Knowledge Graph (All or Nothing)**

Both PostgreSQL AND Neo4j MUST be operational. No RAG-only mode.

**Implementation:**
- Health checks validate both databases at startup
- Server refuses to start if either database unavailable
- All write operations require health checks on both databases
- Docker Compose configures both by default
- Documentation assumes both databases present

#### Alternatives Considered

**Option A: Truly Optional & Hidden**
- Don't expose graph tools if Neo4j unavailable
- Dynamically register tools based on connection test
- Silent about graph availability in ingestion
- **Rejected:** Too complex, confusing UX, hard to test

**Option C: Support Both with Clear Separation**
- Document two modes: "RAG-only" and "RAG+Graph"
- Explicit environment variables indicate mode
- Separate documentation for each mode
- **Rejected:** Doubles maintenance burden, increases test surface

#### Consequences

**Positive:**
- ✅ Simpler, cleaner architecture
- ✅ Predictable behavior (no conditional logic)
- ✅ Better user experience (clear setup requirements)
- ✅ Reduced testing surface area
- ✅ No ambiguity about system capabilities

**Negative:**
- ❌ Cannot run RAG-only if Neo4j unavailable
- ❌ Higher infrastructure requirements (2 databases)
- ❌ More complex local development setup (but Docker Compose solves this)
- ❌ Higher costs for cloud deployment (but Neo4j Aura free tier available)

**Mitigation:**
- Docker Compose sets up both databases automatically
- Clear setup documentation with Docker instructions
- Cloud deployment guide with Supabase + Neo4j Aura (both free tiers available)

#### Future Reconsideration

This decision can be revisited if:
1. Users demand RAG-only mode for specific use cases
2. Infrastructure costs become prohibitive
3. Neo4j availability becomes unreliable

For MVP/initial release, simplicity outweighs flexibility.

---

## Graphiti Integration Patterns

### 2.1 Search Method Mapping

#### Use Case: Entity Relationship Discovery

**Goal:** Find how entities are connected
**Tool:** `query_relationships()`
**Method:** CrossEncoder with 0.7 threshold

**Example:**
```python
# User asks: "Which services depend on authentication?"
results = await graph_store.search_relationships(
    "authentication service dependencies",
    num_results=5
)

# Returns: High-confidence edges only (score >= 0.7)
# [ServiceA] -[DEPENDS_ON]-> [AuthService]
# [ServiceB] -[CALLS]-> [AuthService]
# [ServiceC] -[USES]-> [AuthService]
```

**Configuration:**
```python
config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
    "limit": num_results,
    "reranker_min_score": 0.7
})
search_filter = SearchFilters()  # No temporal constraints
```

**Performance:** ~500-800ms per query (includes LLM cross-encoder call)

---

#### Use Case: Temporal Evolution Tracking

**Goal:** See how knowledge changed over time
**Tool:** `query_temporal()`
**Method:** RRF (after fix)

**Example:**
```python
# User asks: "How did CEO change in 2023?"
from datetime import datetime, timezone

start = datetime(2023, 1, 1, tzinfo=timezone.utc)
end = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

results = await graph_store.search_temporal(
    "CEO leadership",
    time_range_start=start,
    time_range_end=end,
    num_results=10
)

# Returns: All CEO-related facts valid during 2023
# Fact: "Alice was CEO" (valid_at: 2022-01-01, invalid_at: 2023-06-01)
# Fact: "Bob became CEO" (valid_at: 2023-06-01, invalid_at: None)
```

**Configuration:**
```python
config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})
search_filter = SearchFilters(
    valid_at=[[DateFilter(date=end, comparison_operator="<=")]],
    invalid_at=[
        [DateFilter(date=start, comparison_operator=">=")],
        [DateFilter(date=None, comparison_operator="IS NULL")]
    ]
)
```

**Performance:** ~100-200ms per query (no LLM call, just vector+BM25 fusion)

---

#### Use Case: Point-in-Time Query

**Goal:** "What was true at time T?"
**Tool:** `query_temporal()` with single reference time
**Method:** RRF

**Example:**
```python
# User asks: "Who was CEO on June 1, 2023?"
reference = datetime(2023, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

results = await graph_store.search_at_time(
    "CEO",
    reference_time=reference,
    num_results=5
)

# Returns: Facts valid at exactly that moment
# Logic: valid_at <= reference AND (invalid_at > reference OR invalid_at IS NULL)
```

**Configuration:**
```python
config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})
search_filter = SearchFilters(
    valid_at=[[DateFilter(date=reference, comparison_operator="<=")]],
    invalid_at=[
        [DateFilter(date=reference, comparison_operator=">")],
        [DateFilter(date=None, comparison_operator="IS NULL")]
    ]
)
```

---

### 2.2 Reranker Configuration Guide

#### When to Use RRF

**Best For:**
- General-purpose searches
- Temporal queries (need broader recall)
- When performance matters
- When you want balanced semantic + keyword matching

**Configuration:**
```python
from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF

config = EDGE_HYBRID_SEARCH_RRF.copy(update={
    "limit": 10,  # Number of results
    # sim_min_score defaults to 0.6 (built into recipe)
})
```

**Performance:** ~100-200ms
**Recall:** High (captures more results)
**Precision:** Medium (some false positives)

---

#### When to Use CrossEncoder

**Best For:**
- Relationship discovery (high precision needed)
- Critical searches where accuracy paramount
- When you can tolerate slower performance
- When false positives are expensive

**Configuration:**
```python
from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_CROSS_ENCODER

config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
    "limit": 10,
    "reranker_min_score": 0.7  # 0.7 = "True/relevant" threshold
})
```

**Performance:** ~500-800ms (includes LLM call)
**Recall:** Medium (filters aggressively)
**Precision:** Very High (low false positives)

**Threshold Guidelines:**
- **0.7+** = High confidence (recommended for production)
- **0.5-0.7** = Medium confidence (for exploratory queries)
- **< 0.5** = Low confidence (likely irrelevant)

---

#### When to Use MMR

**Best For:**
- Generating summaries (need diverse sources)
- Answering complex questions (need variety)
- Avoiding repetitive results
- When diversity matters more than precision

**Configuration:**
```python
from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_MMR

config = EDGE_HYBRID_SEARCH_MMR.copy(update={
    "limit": 10,
    "mmr_lambda": 0.5  # 0.0 = max diversity, 1.0 = max relevance
})
```

**Lambda Tuning:**
- **0.0** = Maximum diversity (results differ from each other)
- **0.5** = Balanced (default)
- **1.0** = Maximum relevance (most similar to query)

**Performance:** ~100-300ms
**Use Case:** Rare in RAG Memory (not currently used)

---

### 2.3 Threshold Tuning Recommendations

#### sim_min_score (Vector Similarity Threshold)

**Default:** 0.6 (from Graphiti constants)
**Range:** 0.0 - 1.0
**Applies to:** Cosine similarity searches (before reranking)

**Tuning Guide:**
- **0.8+** = Very strict (only near-identical embeddings)
- **0.6** = Balanced (recommended default)
- **0.4** = Loose (captures broader matches, more noise)
- **< 0.3** = Too loose (likely irrelevant results)

**Not typically changed** - presets use sensible defaults

---

#### reranker_min_score (Cross-Encoder Threshold)

**Default:** 0.0 (no filtering by default)
**Range:** 0.0 - 1.0
**Applies to:** Cross-encoder reranker outputs only

**Recommended Values:**
- **0.7** = "True/relevant" (high confidence) ← **Use for production**
- **0.5** = "Maybe relevant" (medium confidence) ← Use for exploration
- **0.3** = Too low (captures too much noise)

**Why 0.7?**
From Graphiti documentation and logprob analysis:
> "Cross-encoder uses logit_bias to favor 'True/False' tokens. Scores follow sigmoid curve where 0.7+ indicates LLM classified result as 'True/relevant'"

---

#### mmr_lambda (Diversity vs Relevance)

**Default:** 0.5
**Range:** 0.0 - 1.0
**Applies to:** MMR reranker only

**Tuning Guide:**
- **0.8-1.0** = Prioritize relevance (results similar to query)
- **0.4-0.6** = Balanced
- **0.0-0.2** = Prioritize diversity (results differ from each other)

**Rarely tuned** - 0.5 works well for most cases

---

### 2.4 Performance Characteristics

#### Query Latency Breakdown

| Component | Latency (Local) | Latency (Cloud) |
|-----------|-----------------|-----------------|
| **Embedding Generation** | 50-100ms | 100-200ms |
| **Vector Search (Neo4j)** | 10-30ms | 30-80ms |
| **BM25 Full-Text Search** | 5-15ms | 15-40ms |
| **BFS Traversal (3 hops)** | 20-50ms | 40-100ms |
| **RRF Reranking** | 5-10ms | 5-10ms |
| **CrossEncoder LLM Call** | 400-700ms | 500-900ms |
| **MMR Calculation** | 10-30ms | 10-30ms |

**Total Query Time:**
- **RRF Method:** 90-205ms (local), 160-430ms (cloud)
- **CrossEncoder Method:** 490-905ms (local), 660-1230ms (cloud)
- **MMR Method:** 95-225ms (local), 165-440ms (cloud)

**P95 Latency (from Zep paper):**
~300ms overall (includes all methods averaged)

---

#### Ingestion Performance

**Entity Extraction Cost:**
- **Time per document:** 30-60 seconds (GPT-4o call)
- **Cost per document:** ~$0.01 (OpenAI pricing)
- **vs RAG embedding:** ~$0.000001 (1000x cheaper, 30000x faster)

**Implications:**
- Graph ingestion is bottleneck (~30-60x slower than RAG)
- Large batch ingestion can take hours
- Not suitable for real-time ingestion
- Background job processing recommended

---

#### Storage Overhead

**Neo4j Storage:**
- **Typical:** 100-500 entities per document
- **Size per entity:** ~1-2 KB
- **1,000 documents:** ~500,000 entities = 0.5-1 GB

**vs PostgreSQL (RAG):**
- **Same 1,000 documents:** ~5-10 MB (embeddings only)
- **Graph adds:** ~50-100x storage overhead

**Trade-off:** Storage cost for relationship intelligence

---

## Known Limitations & Workarounds

### 3.1 Temporal Filtering Only Works on Edges

**Limitation:**
From Graphiti documentation:
> "Datetime filtering only applies to edge scope searches—when using scope='nodes' or scope='episodes', datetime filter values are ignored and have no effect on search results."

**Impact:**
- Cannot filter nodes by temporal validity
- Cannot filter episodes by temporal validity
- Can only filter relationships (edges) by time

**Workaround:**
- Always use edge-scope searches for temporal queries
- Current implementation already uses edge searches (correct)
- Future: If node/episode temporal filtering needed, must traverse from edges

---

### 3.2 No Automatic Temporal Detection

**Limitation:**
Graphiti does NOT detect temporal intent from query text like:
- "When was X first mentioned?"
- "How did Y change over time?"
- "What happened before Z?"

**Impact:**
- Cannot rely on query parsing for temporal logic
- Must explicitly construct SearchFilters with date constraints
- No "magic" temporal search detection

**Workaround:**
- Use explicit temporal parameters (implemented in ADR-001)
- MCP clients must provide ISO 8601 date strings
- Document temporal query patterns for users

---

### 3.3 No Official Temporal Search Examples

**Limitation:**
Despite extensive temporal documentation, Graphiti repository contains:
- ❌ No SearchFilters + temporal constraints examples
- ❌ No before/after date filtering examples
- ❌ No point-in-time query examples

**Impact:**
- Must infer correct implementation from source code
- No official validation of our approach
- Risk of misusing SearchFilters API

**Workaround:**
- Extensive testing with various temporal scenarios
- Source code analysis of SearchFilters class
- Community discussion and validation

**Evidence:**
- Quickstart shows temporal metadata display but NOT temporal filtering
- Blog posts discuss temporal model but not search implementation
- Official docs mention SearchFilters but provide minimal examples

---

### 3.4 Phase 4 Implementation Gaps

#### Document Update Gap

**Problem:**
```
Initial Ingest:  "PostgreSQL is powerful"
                 RAG ✅ stored, Graph ✅ entities extracted

Update:          "PostgreSQL 17 is powerful with pgvector"
                 RAG ✅ updated, Graph ❌ STALE

Result:          Graph still has old entities, missing new entities
```

**Status:** Known limitation, Phase 4 will fix
**Timeline:** Expected by end of 2025

**Workaround:**
1. Delete document completely
2. Re-ingest with updated content
3. Or manually clean Neo4j episodes

**Manual Cleanup:**
```cypher
# Find episode by name
MATCH (e:Episodic {name: 'doc_42'}) RETURN e

# Delete episode and relationships
MATCH (e:Episodic {name: 'doc_42'})
DETACH DELETE e

# Verify deletion
MATCH (e:Episodic {name: 'doc_42'}) RETURN e
# Should return no results
```

---

#### Document Deletion Gap

**Problem:**
```
Delete Document:  rag delete-document 42
                  RAG ✅ deleted, Graph ❌ orphaned episode remains

Result:           Episode 'doc_42' exists with no source document
```

**Status:** Known limitation, Phase 4 will fix

**Detection:**
```cypher
# Find orphaned episodes (no entities)
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
RETURN e

# Find all episodes (manual verification needed)
MATCH (e:Episode)
RETURN e.name
# Check if corresponding doc_id exists in RAG
```

**Workaround:**
```cypher
# Delete orphaned episodes
MATCH (e:Episode)
WHERE NOT (e)--(:Entity)
DETACH DELETE e
```

---

#### Recrawl Gap

**Problem:**
```
Initial Crawl:   Creates doc_290, doc_291, doc_292
                 RAG ✅ 3 docs, Graph ✅ 3 episodes

Recrawl:         Deletes old docs from RAG
                 Creates doc_295, doc_296, doc_297
                 RAG ✅ clean, Graph ❌ orphaned doc_290-292

Result:          Graph accumulates orphaned episodes over time
```

**Status:** Known limitation, Phase 4 will fix

**Workaround:**
```bash
# Before recrawl, note existing doc IDs
rag list-documents --collection my-collection

# After recrawl, manually delete old episodes
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password

MATCH (e:Episodic {name: 'doc_290'}) DETACH DELETE e
MATCH (e:Episodic {name: 'doc_291'}) DETACH DELETE e
MATCH (e:Episodic {name: 'doc_292'}) DETACH DELETE e
```

---

### 3.5 Wikipedia Ingestion Timeout

**Issue Observed:** 2025-10-17

**Symptom:**
```
Ingest: https://en.wikipedia.org/wiki/Quantum_computing
RAG:    ✅ 4 chunks indexed, searchable
Graph:  ⏱️ Timeout after 60 seconds
Result: 4 episodes created with 0 entities each
```

**Root Cause:**
- Graphiti LLM call (GPT-4o) exceeded 60-second timeout
- Wikipedia page too large/complex for single extraction
- OpenAI API latency or rate limiting

**Workarounds:**
1. **Retry with recrawl mode:**
   ```bash
   rag ingest url https://en.wikipedia.org/wiki/Quantum_computing \
       --collection tech --mode recrawl
   ```

2. **Chunk large documents before ingestion:**
   - Split long Wikipedia pages into sections
   - Ingest each section separately
   - Graph will create multiple episodes

3. **Monitor logs during ingestion:**
   ```bash
   tail -f /logs/mcp_server.log | grep -i graphiti
   ```

4. **Cleanup 0-entity episodes:**
   ```cypher
   MATCH (e:Episode)
   WHERE NOT (e)--()
   DETACH DELETE e
   ```

**Future Enhancement:**
- Implement automatic retry with exponential backoff
- Split large documents before graph ingestion
- Add configurable timeout for entity extraction

---

## Production Readiness Checklist

### 4.1 Configuration Validation

#### Environment Variables

**Required for PostgreSQL:**
```bash
DATABASE_URL="postgresql://user:pass@localhost:54320/ragmemory"
OPENAI_API_KEY="sk-..."
```

**Required for Neo4j:**
```bash
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="your-password"
```

**Validation:**
```bash
# Check PostgreSQL connection
uv run rag status

# Check Neo4j connection
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password
RETURN 1 as test
```

---

#### Docker Compose Validation

**Local Development:**
```bash
# Start both databases
docker-compose up -d

# Verify PostgreSQL
docker-compose ps | grep postgres

# Verify Neo4j
docker-compose ps | grep neo4j

# Check logs
docker-compose logs postgres | tail -20
docker-compose logs neo4j | tail -20
```

**Cloud Deployment:**
```bash
# Supabase (PostgreSQL)
curl -I https://your-project.supabase.co

# Neo4j Aura (Neo4j)
# Test via Neo4j Browser: https://workspace-xxx.neo4j.io
```

---

### 4.2 Error Handling

#### Health Check Implementation

**Startup Validation:**
```python
# src/unified/graph_store.py
async def health_check(self, timeout_ms: int = 2000) -> dict:
    """
    Lightweight Neo4j liveness check.

    Returns:
        {
            "status": "healthy" | "unhealthy" | "unavailable",
            "latency_ms": float or None,
            "error": str or None
        }
    """
    try:
        result = await self.graphiti.driver.execute_query("RETURN 1 AS num")
        if result.records[0]["num"] == 1:
            return {"status": "healthy", "latency_ms": latency, "error": None}
    except Exception as e:
        return {"status": "unhealthy", "latency_ms": latency, "error": str(e)}
```

**Write Operation Protection:**
```python
# src/mcp/tools.py
async def ensure_databases_healthy(db, graph_store):
    """
    Check both PostgreSQL and Neo4j before write operations.

    Returns None if healthy, error dict if unhealthy.
    """
    pg_health = await db.health_check(timeout_ms=2000)
    if pg_health["status"] != "healthy":
        return {
            "error": "Database unavailable",
            "status": "service_unavailable",
            "message": "PostgreSQL is temporarily unavailable. Try again in 30s.",
            "details": {"postgres": pg_health, "retry_after_seconds": 30}
        }

    graph_health = await graph_store.health_check(timeout_ms=2000)
    if graph_health["status"] == "unhealthy":
        return {
            "error": "Knowledge graph unavailable",
            "status": "service_unavailable",
            "message": "Neo4j is temporarily unavailable. Try again in 30s.",
            "details": {"neo4j": graph_health, "retry_after_seconds": 30}
        }

    return None  # All healthy
```

**Usage:**
```python
async def ingest_text_impl(...):
    health_error = await ensure_databases_healthy(db, graph_store)
    if health_error:
        return health_error

    # Proceed with ingestion
    ...
```

---

#### Graceful Degradation Strategy

**Current Implementation:** ALL OR NOTHING

**No Fallback Paths:**
- Server refuses to start if either database unavailable
- Write operations fail if health checks fail
- No automatic retries (user must retry manually)

**Rationale:**
- Simpler error handling (no partial states)
- Clearer user experience (either works or doesn't)
- No silent data loss (both stores always in sync)

**Future Consideration:**
If graceful degradation needed:
1. Add RAG-only mode flag
2. Conditionally register graph tools
3. Add rollback logic for partial failures
4. Implement two-phase commit

**Not planned for MVP** - complexity not justified

---

### 4.3 Monitoring Points

#### Key Metrics to Track

**Query Performance:**
- `query_relationships()` latency (target: < 1s)
- `query_temporal()` latency (target: < 500ms)
- `search_documents()` latency (RAG baseline: < 200ms)

**Ingestion Performance:**
- Graph entity extraction time (expected: 30-60s per doc)
- RAG chunking time (expected: < 1s per doc)
- End-to-end ingestion time (expected: ~60s per doc)

**Storage Growth:**
- Neo4j database size (expect ~50-100x RAG size)
- PostgreSQL database size (baseline)
- Episode count vs document count (should be 1:1)

**Error Rates:**
- Health check failures (PostgreSQL, Neo4j)
- Timeout errors during entity extraction
- Orphaned episode accumulation (Phase 4 gap)

---

#### Logging Configuration

**MCP Server Logs:**
```bash
# Location: /logs/mcp_server.log
tail -f /logs/mcp_server.log | grep -E "(ERROR|WARNING|Graph|temporal)"
```

**Key Log Patterns:**
```
✅ "GraphStore.add_knowledge() - Extracted N entities"
⏱️  "Calling Graphiti.add_episode() - This may take 30-60 seconds"
❌ "Neo4j service unavailable: Connection refused"
⚠️  "Episode cleanup attempted but may have issues"
```

**Neo4j Query Logs:**
```bash
docker-compose logs neo4j -f | grep -i "query"
```

---

#### Alerting Thresholds

**Critical Alerts:**
- PostgreSQL health check failure > 2 consecutive
- Neo4j health check failure > 2 consecutive
- Entity extraction timeout rate > 10%
- Orphaned episode count > 100 (suggests Phase 4 gap)

**Warning Alerts:**
- Query latency P95 > 2s (crossencoder) or > 1s (RRF)
- Ingestion time P95 > 120s
- Neo4j storage growth > 200x RAG size (unexpected)
- Episode-to-document ratio != 1.0 ± 0.1

---

### 4.4 Performance Benchmarks

#### Expected Query Times (Local Development)

| Operation | Method | Target | Actual (Observed) |
|-----------|--------|--------|-------------------|
| `search_documents()` | pgvector | < 200ms | ~100-150ms ✅ |
| `query_relationships()` | CrossEncoder | < 1s | ~500-800ms ✅ |
| `query_temporal()` | RRF (after fix) | < 500ms | ~100-200ms ✅ |
| `ingest_text()` (RAG only) | N/A | < 1s | ~500-800ms ✅ |
| `ingest_text()` (RAG+Graph) | GPT-4o | 30-60s | ~30-90s ✅ |

#### Expected Query Times (Cloud Deployment)

| Operation | Method | Target | Expected |
|-----------|--------|--------|----------|
| `search_documents()` | pgvector | < 500ms | ~200-400ms |
| `query_relationships()` | CrossEncoder | < 2s | ~800-1500ms |
| `query_temporal()` | RRF | < 1s | ~300-600ms |
| `ingest_text()` (RAG+Graph) | GPT-4o | 30-90s | ~40-120s |

**Factors Affecting Cloud Performance:**
- Network latency to OpenAI API
- Supabase connection pool saturation
- Neo4j Aura instance size (free tier vs paid)
- Geographic distance (US East vs Europe)

---

#### Regression Testing

**Baseline Test Suite:**
```bash
# Run integration tests
uv run pytest tests/integration/backend/test_graph_* -v

# Measure query performance
uv run pytest tests/performance/test_query_latency.py --benchmark

# Check for Phase 4 gaps
uv run pytest tests/integration/backend/test_document_lifecycle.py -k orphan
```

**Manual Validation:**
```bash
# Test temporal search fix
rag graph query-temporal "machine learning evolution" --limit 10

# Test relationship search
rag graph query-relationships "PostgreSQL dependencies" --limit 5

# Verify no orphaned episodes
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p graphiti-password
MATCH (e:Episode) WHERE NOT (e)--() RETURN count(e) as orphans
# Should return 0
```

---

## Future Enhancements

### 5.1 Advanced Temporal Queries

#### Before/After/During Operators

**Proposed API:**
```python
async def search_temporal_advanced(
    self,
    query: str,
    temporal_operator: str,  # "before", "after", "during", "between"
    reference_date: datetime | None = None,
    date_range: tuple[datetime, datetime] | None = None,
    num_results: int = 5
) -> list[Any]:
    """
    Advanced temporal queries with natural operators.

    Examples:
        # Before operator
        search_temporal_advanced("CEO", "before", datetime(2023, 1, 1))
        → Facts with invalid_at < 2023-01-01

        # After operator
        search_temporal_advanced("CEO", "after", datetime(2023, 1, 1))
        → Facts with valid_at > 2023-01-01

        # During operator
        search_temporal_advanced("CEO", "during", date_range=(start, end))
        → Facts valid during period (current implementation)

        # Between operator (synonym for during)
        search_temporal_advanced("CEO", "between", date_range=(start, end))
    """
```

**Implementation Complexity:** Medium
**Value:** High (more intuitive API)
**Timeline:** Post-MVP

---

#### Temporal Aggregations

**Proposed Feature:**
```python
async def get_timeline_summary(
    self,
    query: str,
    grouping: str = "month",  # "day", "week", "month", "year"
    time_range_start: datetime | None = None,
    time_range_end: datetime | None = None
) -> dict:
    """
    Aggregate temporal facts into timeline summary.

    Returns:
        {
            "timeline": [
                {
                    "period": "2023-01",
                    "fact_count": 5,
                    "top_entities": ["CEO", "CTO", "Engineering"],
                    "key_changes": ["Leadership transition", "Org restructure"]
                },
                ...
            ],
            "total_changes": 37,
            "most_active_period": "2023-06"
        }
    """
```

**Use Cases:**
- "Show me monthly changes to our architecture"
- "What were the key events each quarter?"
- "Summarize evolution by year"

**Implementation:** Requires custom Cypher queries, aggregation logic
**Timeline:** Phase 5+

---

### 5.2 Change Tracking Over Time

#### Diff Between Time Points

**Proposed Feature:**
```python
async def compare_time_periods(
    self,
    query: str,
    time_a: datetime,
    time_b: datetime
) -> dict:
    """
    Show what changed between two points in time.

    Example:
        compare_time_periods(
            "organization structure",
            datetime(2023, 1, 1),
            datetime(2023, 12, 31)
        )

    Returns:
        {
            "added": [
                {"fact": "Carol became CTO", "valid_at": "2023-06-01"},
                ...
            ],
            "removed": [
                {"fact": "Alice was CTO", "invalid_at": "2023-06-01"},
                ...
            ],
            "unchanged": [
                {"fact": "Bob is CEO", "valid_at": "2022-01-01"},
                ...
            ]
        }
    """
```

**Use Cases:**
- "What changed between Q1 and Q4?"
- "Show me architecture differences year-over-year"
- "Compare before and after migration"

**Implementation Complexity:** High
**Timeline:** Phase 6+

---

#### Fact Invalidation Tracking

**Proposed Feature:**
```python
async def get_invalidation_history(
    self,
    query: str,
    num_results: int = 10
) -> list:
    """
    Track why facts were invalidated (contradicted by new information).

    Returns:
        [
            {
                "old_fact": "Alice was CEO",
                "invalid_at": "2023-06-01",
                "invalidated_by": "Bob became CEO on 2023-06-01",
                "reason": "Leadership change",
                "source_document": "doc_42"
            },
            ...
        ]
    """
```

**Use Cases:**
- Audit trail of knowledge changes
- Understanding decision evolution
- Compliance and change management

**Implementation:** Requires tracking invalidation relationships in graph
**Timeline:** Phase 6+

---

### 5.3 Integration with Other Graph Systems

#### Neo4j Enterprise Features

**Potential Enhancements:**
- **Multi-tenancy:** Separate graphs per user/organization
- **Role-based access control:** Query filtering by permissions
- **Graph algorithms:** PageRank, community detection, centrality
- **Backup and restore:** Automated graph snapshots

**Requirement:** Neo4j Enterprise license (not free)
**Timeline:** If user demand exists

---

#### Alternative Graph Databases

**Considered but Not Planned:**
- **MemGraph:** In-memory graph (faster but limited storage)
- **ArangoDB:** Multi-model (graph + document)
- **TigerGraph:** Distributed graph (enterprise scale)

**Rationale for Neo4j:**
- Graphiti only supports Neo4j
- Best-in-class Cypher query language
- Strong ecosystem and tooling
- Free tier available (Aura)

**Not planning alternatives** unless Graphiti adds support

---

### 5.4 Performance Optimizations

#### Batch Entity Extraction

**Current:** Sequential entity extraction (30-60s per document)
**Proposed:** Batch multiple documents in single LLM call

**Potential Speedup:** 5-10x faster for large batches
**Implementation Complexity:** High (requires Graphiti changes)
**Timeline:** Depends on Graphiti roadmap

---

#### Local Entity Models

**Current:** GPT-4o via OpenAI API ($0.01/doc, 30-60s latency)
**Proposed:** Fine-tuned local model for entity extraction

**Benefits:**
- 100x cost reduction
- 10x latency reduction
- No API dependency
- Privacy (no external calls)

**Challenges:**
- Model training and maintenance
- Lower quality than GPT-4o
- Infrastructure requirements (GPU)

**Timeline:** Research phase only

---

#### Caching Extracted Entities

**Proposed:** Cache entity extraction results by content hash

**Benefit:**
- If same content ingested twice, skip extraction
- Useful for re-crawling unchanged pages
- Massive speedup for duplicate content

**Implementation:**
1. Hash document content
2. Check cache (Redis or PostgreSQL)
3. If hit, reuse entities; if miss, extract and cache

**Timeline:** Phase 5 (after Phase 4 complete)

---

## References

### Official Documentation

1. **Graphiti Overview**
   https://help.getzep.com/graphiti/graphiti/overview

2. **Searching the Graph (Zep v2)**
   https://help.getzep.com/v2/searching-the-graph

3. **Graphiti Getting Started**
   https://help.getzep.com/graphiti/getting-started/quick-start

### Research Papers

4. **Zep: A Temporal Knowledge Graph Architecture for Agent Memory**
   arXiv:2501.13956v1
   https://arxiv.org/html/2501.13956v1
   Authors: Preston Rasmussen, Daniel Chalef

### GitHub Repository

5. **Official Graphiti Repository**
   https://github.com/getzep/graphiti

6. **Source Code - search_filters.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_filters.py

7. **Source Code - search_config.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_config.py

8. **Source Code - search_config_recipes.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_config_recipes.py

### Blog Posts

9. **How do you search a Knowledge Graph?**
   https://blog.getzep.com/how-do-you-search-a-knowledge-graph/

10. **Graphiti: Temporal Knowledge Graphs for Agentic Apps**
    https://blog.getzep.com/graphiti-knowledge-graphs-for-agents/

### Internal Documentation

11. **RAG Memory - Graphiti Temporal Search Research**
    `/docs/GRAPHITI_TEMPORAL_SEARCH_RESEARCH.md`
    Comprehensive 20+ citation research report on temporal search

12. **RAG Memory - Graphiti Implementation Guide**
    `/docs/GRAPHITI_IMPLEMENTATION_GUIDE.md`
    Code examples, patterns, and implementation steps

13. **RAG Memory - Knowledge Graph Integration**
    `/.reference/KNOWLEDGE_GRAPH.md`
    User-facing documentation on graph features

14. **RAG Memory - Implementation Gaps and Roadmap**
    `/docs/IMPLEMENTATION_GAPS_AND_ROADMAP.md`
    Known issues, Phase 4 gaps, and future work

15. **RAG Memory - Startup Validation Implementation**
    `/docs/STARTUP_VALIDATION_IMPLEMENTATION.md`
    Health check specifications and validation logic

---

## Document History

**Version 1.0** - 2025-10-23
- Initial comprehensive analysis
- ADR-001: Temporal Search Design (explicit parameters chosen)
- ADR-002: Search Method Selection (RRF vs CrossEncoder vs MMR)
- ADR-003: Knowledge Graph Optionality (All or Nothing)
- Complete integration patterns documented
- Known limitations catalogued
- Production readiness checklist created
- Future enhancements outlined

**Next Review:** After Phase 4 completion (expected end of 2025)

---

## Summary

This document provides the definitive architectural analysis of Graphiti integration in RAG Memory. Key takeaways:

1. **Temporal search is broken** - requires explicit fix with SearchFilters (ADR-001)
2. **Architecture is All or Nothing** - both databases required (ADR-003)
3. **Search methods are use-case dependent** - CrossEncoder for precision, RRF for recall (ADR-002)
4. **Phase 4 gaps prevent production use** - document lifecycle issues remain
5. **Performance characteristics are well-understood** - query times, costs, storage overhead documented
6. **Future enhancements are mapped** - clear roadmap for temporal features, optimizations, integrations

**Status:** Ready for implementation of temporal search fix and Phase 4 completion.

**Last Updated:** 2025-10-23
