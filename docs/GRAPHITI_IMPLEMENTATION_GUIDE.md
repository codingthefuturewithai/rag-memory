# Graphiti Temporal Search Implementation Guide

**Created:** 2025-10-23 (During autonomous research session)
**Purpose:** Comprehensive implementation guide for proper temporal search in RAG Memory
**Based on:** Official Graphiti documentation, source code analysis, and 20+ authoritative citations

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Implementation Patterns](#implementation-patterns)
4. [Code Examples](#code-examples)
5. [MCP Tool Integration](#mcp-tool-integration)
6. [Testing Strategy](#testing-strategy)
7. [API Design Recommendations](#api-design-recommendations)
8. [Migration Path](#migration-path)

---

## Executive Summary

### The Problem

Our current `search_temporal()` method in `src/unified/graph_store.py` (lines 386-416) does **NOT** perform temporal search. It only uses a lower threshold (0.5 vs 0.7), making it a looser relational search, not a true temporal search.

**Result:** Queries like "When was machine learning first mentioned?" return 0 results even though the content is in the graph.

### The Root Cause

Graphiti does **NOT** automatically detect temporal intent from query text. Temporal search requires **explicit `SearchFilters` with `valid_at`/`invalid_at` date constraints**.

### The Solution

Implement proper temporal search by:
1. Accepting explicit temporal parameters (date ranges or point-in-time reference)
2. Constructing `SearchFilters` with `DateFilter` objects
3. Using appropriate `ComparisonOperator` values for the temporal logic
4. Selecting RRF reranker for broader recall (vs. cross-encoder's precision)

---

## Current State Analysis

### search_relationships() - CORRECT ✅

```python
async def search_relationships(
    self,
    query: str,
    num_results: int = 5
) -> list[Any]:
    config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
        "limit": num_results,
        "reranker_min_score": 0.7
    })
    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=SearchFilters()
    )
    return search_results.edges if search_results.edges else []
```

**Status:** ✅ **WORKING** - Properly filters relational queries with 0.7 threshold

**Test Results:**
- Query: "What are relationships between ML, neural networks, training models?"
- Result: 3 relevant edges returned ✅

### search_temporal() - BROKEN ❌

```python
async def search_temporal(
    self,
    query: str,
    num_results: int = 5
) -> list[Any]:
    config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
        "limit": num_results,
        "reranker_min_score": 0.5  # ⚠️ Lower threshold
    })
    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=SearchFilters()  # ❌ No temporal filtering!
    )
    return search_results.edges if search_results.edges else []
```

**Status:** ❌ **NOT WORKING** - Empty SearchFilters() means no temporal constraints

**Test Results:**
- Query: "When was machine learning first mentioned?"
- Result: 0 timeline items (should have 5-10) ❌

**Why It Failed:**
1. No temporal constraints in SearchFilters
2. Lower threshold (0.5) doesn't make a search "temporal"
3. Cross-encoder with 0.5 threshold returns zero results for temporal phrasing
4. Fundamental misunderstanding: Can't fix temporal search by just lowering a score

---

## Implementation Patterns

### Pattern 1: Explicit Temporal Parameters (Recommended) ⭐

**Best for:** Precise temporal queries, API clarity, testability

```python
from datetime import datetime, timezone
from graphiti_core.search.search_filters import SearchFilters, DateFilter, ComparisonOperator

async def search_temporal(
    self,
    query: str,
    time_range_start: datetime | None = None,
    time_range_end: datetime | None = None,
    include_current_facts: bool = True,
    num_results: int = 5
) -> list[Any]:
    """
    Search knowledge graph with explicit temporal filtering.

    Args:
        query: Natural language query (e.g., "partnerships", "leadership changes")
        time_range_start: Find facts valid on/after this date (UTC required)
        time_range_end: Find facts valid on/before this date (UTC required)
        include_current_facts: Include facts with null invalid_at (still valid)
        num_results: Number of results to return

    Returns:
        List of EntityEdge objects with temporal validity metadata

    Example:
        # Find partnerships that were active in 2023
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 12, 31, tzinfo=timezone.utc)

        results = await search_temporal(
            "company partnerships",
            time_range_start=start,
            time_range_end=end,
            num_results=10
        )

    Temporal Logic:
        For a fact to be "valid during [start, end]":
        - valid_at <= end (fact started before/at range end)
        - invalid_at >= start OR invalid_at is null (fact ended after/at range start or ongoing)
    """
    filters = SearchFilters()

    # Build temporal constraints only if dates provided
    if time_range_start or time_range_end:
        # Constraint 1: valid_at (when fact became true)
        # A fact is relevant if it became valid before the range ends
        if time_range_end:
            filters.valid_at = [
                [DateFilter(
                    date=time_range_end,
                    comparison_operator=ComparisonOperator.less_than_equal
                )]
            ]
        elif time_range_start:
            # If only start provided, facts must have started
            filters.valid_at = [
                [DateFilter(
                    date=datetime.now(timezone.utc),
                    comparison_operator=ComparisonOperator.less_than_equal
                )]
            ]

        # Constraint 2: invalid_at (when fact stopped being true)
        # A fact is relevant if it became invalid after range starts, OR is still valid
        if time_range_start:
            invalid_at_conditions = [
                [DateFilter(
                    date=time_range_start,
                    comparison_operator=ComparisonOperator.greater_than_equal
                )]
            ]

            # Add condition for ongoing facts (no end date)
            if include_current_facts:
                invalid_at_conditions.append([
                    DateFilter(
                        date=None,
                        comparison_operator=ComparisonOperator.is_null
                    )
                ])

            filters.invalid_at = invalid_at_conditions

    # Use RRF for temporal searches (broader recall)
    # Temporal questions need context, not strict precision filtering
    config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})

    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=filters
    )

    return search_results.edges if search_results.edges else []
```

### Pattern 2: Point-in-Time Query

**Best for:** "What was true at time T?" questions

```python
async def search_at_time(
    self,
    query: str,
    reference_time: datetime,
    num_results: int = 5
) -> list[Any]:
    """
    Find facts that were valid at a specific point in time.

    Args:
        query: Natural language query
        reference_time: The specific point in time (must have timezone, UTC recommended)
        num_results: Number of results to return

    Returns:
        Facts that were valid at the specified moment

    Example:
        # What was the company leadership on Jan 1, 2023?
        results = await search_at_time(
            "company leadership",
            reference_time=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )

    Logic:
        A fact is valid at time T if:
        - valid_at <= T (fact had started by time T)
        - invalid_at > T OR invalid_at is null (fact was still valid at time T)
    """
    filters = SearchFilters(
        # Fact must have started by reference_time
        valid_at=[
            [DateFilter(
                date=reference_time,
                comparison_operator=ComparisonOperator.less_than_equal
            )]
        ],
        # Fact must still be valid at reference_time (ended after or not ended)
        invalid_at=[
            [DateFilter(
                date=reference_time,
                comparison_operator=ComparisonOperator.greater_than
            )],
            [DateFilter(
                date=None,
                comparison_operator=ComparisonOperator.is_null
            )]
        ]
    )

    config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})

    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=filters
    )

    return search_results.edges if search_results.edges else []
```

### Pattern 3: Query-Based Auto-Detection (User-Friendly)

**Best for:** LLM-friendly interfaces where temporal intent is implicit

```python
async def search_with_temporal_detection(
    self,
    query: str,
    reference_time: datetime | None = None,
    num_results: int = 5
) -> list[Any]:
    """
    Smart search that detects temporal queries and applies temporal filtering.

    If query contains temporal keywords AND reference_time provided,
    applies temporal filtering. Otherwise, performs standard relational search.

    Args:
        query: Natural language query
        reference_time: Reference point for temporal detection (UTC recommended)
        num_results: Number of results

    Returns:
        Search results (relational or temporal depending on query)

    Example:
        # This will auto-detect temporal intent and apply filtering
        results = await search_with_temporal_detection(
            "When was the CEO changed?",
            reference_time=datetime.now(timezone.utc)
        )
    """
    temporal_keywords = [
        'when', 'before', 'after', 'during', 'since', 'until',
        'first', 'last', 'previously', 'formerly', 'changed', 'evolution',
        'history', 'timeline', 'period', 'year', 'month', 'date'
    ]

    query_lower = query.lower()
    is_temporal = any(kw in query_lower for kw in temporal_keywords)

    if is_temporal and reference_time:
        # Perform temporal search
        return await self.search_at_time(query, reference_time, num_results)
    else:
        # Perform standard relational search
        return await self.search_relationships(query, num_results)
```

---

## Code Examples

### Example 1: Range Query (2023 Partnerships)

```python
from datetime import datetime, timezone

# Search for partnerships active in 2023
start = datetime(2023, 1, 1, tzinfo=timezone.utc)
end = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

results = await graph_store.search_temporal(
    "company partnerships",
    time_range_start=start,
    time_range_end=end,
    num_results=10
)

# Process results
for edge in results:
    print(f"Partnership: {edge.fact}")
    if edge.valid_at:
        print(f"  Started: {edge.valid_at}")
    if edge.invalid_at:
        print(f"  Ended: {edge.invalid_at}")
    else:
        print(f"  Status: Ongoing")
```

### Example 2: Point-in-Time Query

```python
# What was the org chart on June 1, 2023?
reference_date = datetime(2023, 6, 1, 9, 0, 0, tzinfo=timezone.utc)

results = await graph_store.search_at_time(
    "organization structure leadership roles",
    reference_time=reference_date,
    num_results=15
)

print(f"Org structure as of {reference_date.isoformat()}:")
for edge in results:
    print(f"  {edge.fact}")
```

### Example 3: Current Facts Only

```python
from datetime import datetime, timezone, timedelta

# Find partnerships that started in last 90 days and are still active
start_date = datetime.now(timezone.utc) - timedelta(days=90)
now = datetime.now(timezone.utc)

results = await graph_store.search_temporal(
    "recent partnerships collaborations",
    time_range_start=start_date,
    time_range_end=now,
    include_current_facts=True,
    num_results=5
)

print("Active partnerships from last 90 days:")
for edge in results:
    if edge.invalid_at is None:
        print(f"  {edge.fact} (Still active)")
    else:
        print(f"  {edge.fact} (Ended {edge.invalid_at})")
```

---

## MCP Tool Integration

### Option A: Extend query_temporal with Optional Parameters (Recommended)

**Advantages:**
- Non-breaking change
- Backward compatible
- Clear parameter documentation
- Flexible for LLM callers

**Implementation:**

```python
@mcp.tool()
async def query_temporal(
    query: str,
    time_range_start: str = None,
    time_range_end: str = None,
    num_results: int = 10,
) -> Dict[str, Any]:
    """
    Query how knowledge evolved over time, with optional temporal filtering.

    Args:
        query: Natural language query (e.g., "CEO changes", "partnership timeline")
        time_range_start: ISO 8601 datetime (e.g., "2023-01-01T00:00:00Z")
                         Optional - if provided, filter facts valid from this date
        time_range_end: ISO 8601 datetime (e.g., "2023-12-31T23:59:59Z")
                       Optional - if provided, filter facts valid until this date
        num_results: Maximum number of results (default 10)

    Returns:
        Dictionary with:
        - status: "success" or "error"
        - timeline: List of temporal facts with validity windows
        - query: The original query
        - num_results: Count of returned results

    Examples:
        1. Basic temporal query (returns all related facts):
           query: "When did the CEO change?"
           time_range_start: null
           time_range_end: null
           → Returns all CEO-related facts with their temporal validity

        2. Range query (facts valid during period):
           query: "CEO during 2023"
           time_range_start: "2023-01-01T00:00:00Z"
           time_range_end: "2023-12-31T23:59:59Z"
           → Returns only facts that were valid at some point in 2023

        3. Point-in-time (set start and end to same time):
           query: "CEO on Jan 1 2023"
           time_range_start: "2023-01-01T00:00:00Z"
           time_range_end: "2023-01-01T00:00:00Z"
           → Returns facts valid at exactly that moment

    Notes:
        - All timestamps must be ISO 8601 format with timezone
        - UTC recommended (Z suffix or +00:00)
        - Temporal filtering only applies to edge (relationship) searches
        - Returns empty results if no facts match the temporal constraints
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph not available",
                "timeline": []
            }

        # Parse ISO 8601 timestamps if provided
        start_dt = None
        end_dt = None

        if time_range_start:
            try:
                # Handle both "2023-01-01T00:00:00Z" and "2023-01-01T00:00:00+00:00"
                start_dt = datetime.fromisoformat(
                    time_range_start.replace('Z', '+00:00')
                )
            except ValueError as e:
                return {
                    "status": "error",
                    "message": f"Invalid time_range_start format: {str(e)}",
                    "timeline": []
                }

        if time_range_end:
            try:
                end_dt = datetime.fromisoformat(
                    time_range_end.replace('Z', '+00:00')
                )
            except ValueError as e:
                return {
                    "status": "error",
                    "message": f"Invalid time_range_end format: {str(e)}",
                    "timeline": []
                }

        # Perform temporal search
        results = await graph_store.search_temporal(
            query,
            time_range_start=start_dt,
            time_range_end=end_dt,
            num_results=num_results
        )

        # Format as timeline
        timeline_items = []
        for edge in results:
            item = {
                "fact": getattr(edge, 'fact', ''),
                "relationship_type": getattr(edge, 'name', 'RELATED_TO'),
            }

            # Add temporal validity
            if hasattr(edge, 'valid_at') and edge.valid_at:
                item["valid_from"] = edge.valid_at.isoformat()
            else:
                item["valid_from"] = None

            if hasattr(edge, 'invalid_at') and edge.invalid_at:
                item["valid_until"] = edge.invalid_at.isoformat()
                item["status"] = "expired"
            else:
                item["valid_until"] = None
                item["status"] = "current"

            # Add metadata
            if hasattr(edge, 'created_at') and edge.created_at:
                item["created_at"] = edge.created_at.isoformat()
            if hasattr(edge, 'expired_at') and edge.expired_at:
                item["expired_at"] = edge.expired_at.isoformat()

            timeline_items.append(item)

        return {
            "status": "success",
            "query": query,
            "num_results": len(timeline_items),
            "time_range_start": time_range_start,
            "time_range_end": time_range_end,
            "timeline": timeline_items
        }

    except Exception as e:
        logger.error(f"query_temporal failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "timeline": []
        }
```

### Option B: Create New Point-in-Time Tool

**Advantages:**
- Dedicated tool for time queries
- Clear separation of concerns
- Explicit about time-based searching

**Implementation:**

```python
@mcp.tool()
async def query_at_time(
    query: str,
    reference_time: str,  # ISO 8601 required
    num_results: int = 10,
) -> Dict[str, Any]:
    """
    Find facts that were valid at a specific point in time.

    Use this when you want to know what was true at a particular moment
    (e.g., "Who was CEO on Jan 1, 2023?").

    Args:
        query: Natural language query about the topic
        reference_time: ISO 8601 datetime (e.g., "2023-01-01T00:00:00Z")
        num_results: Maximum number of results

    Returns:
        Facts valid at that specific time with validity windows

    Examples:
        1. "Who was the CEO on Jan 1, 2023?"
           query: "CEO"
           reference_time: "2023-01-01T00:00:00Z"

        2. "What was the company structure on Q2 2023?"
           query: "organization structure roles"
           reference_time: "2023-06-30T23:59:59Z"
    """
    try:
        if not graph_store:
            return {
                "status": "unavailable",
                "message": "Knowledge Graph not available",
                "results": []
            }

        # Parse reference time
        try:
            ref_dt = datetime.fromisoformat(
                reference_time.replace('Z', '+00:00')
            )
        except ValueError as e:
            return {
                "status": "error",
                "message": f"Invalid reference_time format: {str(e)}",
                "results": []
            }

        # Perform point-in-time search
        results = await graph_store.search_at_time(
            query,
            reference_time=ref_dt,
            num_results=num_results
        )

        # Format results
        formatted_results = []
        for edge in results:
            formatted_results.append({
                "fact": getattr(edge, 'fact', ''),
                "relationship_type": getattr(edge, 'name', 'RELATED_TO'),
                "valid_from": edge.valid_at.isoformat() if hasattr(edge, 'valid_at') and edge.valid_at else None,
                "valid_until": edge.invalid_at.isoformat() if hasattr(edge, 'invalid_at') and edge.invalid_at else None,
                "status": "expired" if (hasattr(edge, 'invalid_at') and edge.invalid_at) else "current",
            })

        return {
            "status": "success",
            "query": query,
            "reference_time": reference_time,
            "num_results": len(formatted_results),
            "results": formatted_results
        }

    except Exception as e:
        logger.error(f"query_at_time failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "results": []
        }
```

---

## Testing Strategy

### Unit Tests for Graph Store

```python
import pytest
from datetime import datetime, timezone, timedelta

class TestTemporalSearch:
    """Test temporal search functionality."""

    @pytest.fixture
    async def sample_temporal_data(self, graph_store):
        """Create sample data with temporal metadata."""
        # CEO A: Jan 2022 - Dec 2022
        await graph_store.add_knowledge(
            content="Alice was CEO starting in January 2022.",
            source_document_id=1,
            ingestion_timestamp=datetime(2022, 1, 1, tzinfo=timezone.utc)
        )

        # CEO B: Jan 2023 - Dec 2023
        await graph_store.add_knowledge(
            content="Bob became CEO in January 2023.",
            source_document_id=2,
            ingestion_timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc)
        )

        # CEO C: Jan 2024 - Present
        await graph_store.add_knowledge(
            content="Carol is the current CEO as of January 2024.",
            source_document_id=3,
            ingestion_timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )

    async def test_point_in_time_2022(self, sample_temporal_data, graph_store):
        """Test finding CEO at specific time in 2022."""
        results = await graph_store.search_at_time(
            "CEO",
            reference_time=datetime(2022, 6, 1, tzinfo=timezone.utc)
        )

        assert len(results) > 0
        facts = [edge.fact for edge in results]
        assert any("Alice" in fact for fact in facts)
        assert not any("Bob" in fact for fact in facts)
        assert not any("Carol" in fact for fact in facts)

    async def test_point_in_time_2023(self, sample_temporal_data, graph_store):
        """Test finding CEO at specific time in 2023."""
        results = await graph_store.search_at_time(
            "CEO",
            reference_time=datetime(2023, 6, 1, tzinfo=timezone.utc)
        )

        assert len(results) > 0
        facts = [edge.fact for edge in results]
        assert not any("Alice" in fact for fact in facts)
        assert any("Bob" in fact for fact in facts)
        assert not any("Carol" in fact for fact in facts)

    async def test_range_query_2023(self, sample_temporal_data, graph_store):
        """Test finding facts valid during 2023."""
        results = await graph_store.search_temporal(
            "CEO leadership",
            time_range_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2023, 12, 31, tzinfo=timezone.utc)
        )

        assert len(results) > 0
        # Should include Bob (CEO in 2023)
        facts = [edge.fact for edge in results]
        assert any("Bob" in fact for fact in facts)

    async def test_range_query_spanning_years(self, sample_temporal_data, graph_store):
        """Test finding facts across multiple year boundaries."""
        results = await graph_store.search_temporal(
            "CEO",
            time_range_start=datetime(2022, 11, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2023, 2, 1, tzinfo=timezone.utc)
        )

        # Should include both Alice and Bob (overlapping period)
        assert len(results) > 0

    async def test_temporal_query_no_match(self, graph_store):
        """Test temporal query with no matching facts."""
        results = await graph_store.search_temporal(
            "CEO in 1990",
            time_range_start=datetime(1990, 1, 1, tzinfo=timezone.utc),
            time_range_end=datetime(1990, 12, 31, tzinfo=timezone.utc)
        )

        # Should return empty (data is from 2022+)
        assert len(results) == 0

    async def test_temporal_query_irrelevant(self, graph_store):
        """Test irrelevant temporal query returns empty."""
        results = await graph_store.search_temporal(
            "ancient Rome",
            time_range_start=datetime(100, 1, 1, tzinfo=timezone.utc),
            time_range_end=datetime(500, 12, 31, tzinfo=timezone.utc)
        )

        assert len(results) == 0
```

### Integration Tests for MCP Tools

```python
import pytest
from datetime import datetime

class TestTemporalMCPTools:
    """Test temporal search through MCP tool interface."""

    async def test_query_temporal_with_date_range(self, mcp_server):
        """Test query_temporal tool with date range parameters."""
        response = await mcp_server.call_tool(
            "query_temporal",
            {
                "query": "CEO leadership",
                "time_range_start": "2023-01-01T00:00:00Z",
                "time_range_end": "2023-12-31T23:59:59Z",
                "num_results": 10
            }
        )

        assert response["status"] == "success"
        assert response["num_results"] > 0
        assert "timeline" in response

    async def test_query_temporal_no_date_range(self, mcp_server):
        """Test query_temporal without date range (returns all related facts)."""
        response = await mcp_server.call_tool(
            "query_temporal",
            {
                "query": "CEO",
                "num_results": 10
            }
        )

        assert response["status"] == "success"
        # Should return multiple CEOs across all time periods

    async def test_query_temporal_invalid_date_format(self, mcp_server):
        """Test query_temporal with invalid date format."""
        response = await mcp_server.call_tool(
            "query_temporal",
            {
                "query": "CEO",
                "time_range_start": "invalid-date",
                "num_results": 10
            }
        )

        assert response["status"] == "error"
        assert "Invalid" in response["message"]

    async def test_query_at_time(self, mcp_server):
        """Test point-in-time query tool."""
        response = await mcp_server.call_tool(
            "query_at_time",
            {
                "query": "CEO",
                "reference_time": "2023-06-01T00:00:00Z",
                "num_results": 5
            }
        )

        assert response["status"] == "success"
        assert response["num_results"] >= 0
        assert response["reference_time"] == "2023-06-01T00:00:00Z"
```

---

## API Design Recommendations

### Principle 1: Explicit Over Implicit

**DON'T:** Rely on query text like "when was" to trigger temporal logic
```python
# ❌ WRONG - Too implicit
results = await search("When was machine learning mentioned?")
```

**DO:** Accept explicit temporal parameters
```python
# ✅ CORRECT - Clear what's happening
results = await search_temporal(
    "machine learning",
    reference_time=datetime.now(timezone.utc)
)
```

### Principle 2: ISO 8601 for API Boundaries

**Rationale:** Language-independent, unambiguous, timezone-aware

```python
# MCP tool parameter
"time_range_start": "2023-01-01T00:00:00Z"

# Internally, convert to Python datetime
from datetime import datetime
dt = datetime.fromisoformat("2023-01-01T00:00:00Z".replace('Z', '+00:00'))
```

### Principle 3: Always Use Timezone-Aware Datetimes

**DON'T:**
```python
# ❌ WRONG - No timezone
dt = datetime(2023, 1, 1, 0, 0, 0)
```

**DO:**
```python
# ✅ CORRECT - UTC timezone
dt = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
```

### Principle 4: Document the Temporal Logic

Every temporal method should include:

1. **Clear docstring** explaining what "valid during" means
2. **Example usage** showing actual date values
3. **Logic description** explaining valid_at/invalid_at constraints
4. **Return format** showing temporal fields in results

---

## Migration Path

### Phase 1: Update search_temporal() (Immediate)

Replace current implementation with Pattern 1 (explicit temporal parameters):

```bash
# In src/unified/graph_store.py
# Replace lines 386-416 (search_temporal method)
# With the implementation from "Pattern 1: Explicit Temporal Parameters"
```

### Phase 2: Update query_temporal_impl() (In tools.py)

```bash
# In src/mcp/tools.py
# Update query_temporal_impl() to:
# 1. Accept time_range_start, time_range_end as ISO 8601 strings
# 2. Convert to datetime objects
# 3. Call graph_store.search_temporal() with temporal parameters
# 4. Format timeline results with validity windows
```

### Phase 3: Add Tests

```bash
# In tests/
# 1. Create test_temporal_search.py with unit tests
# 2. Create test_temporal_mcp_tools.py with integration tests
# 3. Add temporal test data fixtures
```

### Phase 4: Documentation

```bash
# In .reference/
# 1. Create TEMPORAL_SEARCH_GUIDE.md for users
# 2. Update MCP_QUICK_START.md with temporal examples
# 3. Add temporal query examples to README
```

### Phase 5: Verification

1. Manual testing with MCP Inspector
2. Test all 4 original queries (2 relevant, 2 irrelevant)
3. Verify compound queries work correctly
4. Test with date ranges and point-in-time queries

---

## Success Criteria

✅ **Temporal query returns results for relevant content:**
```
Query: "When was machine learning first mentioned?"
Expected: Multiple timeline items with temporal validity
Result: ✅ Should work with new implementation
```

✅ **Irrelevant temporal queries return empty:**
```
Query: "When was ancient Roman plumbing discussed?"
Expected: 0 results (not in content)
Result: ✅ Should return empty
```

✅ **Relationship queries still work with 0.7 threshold:**
```
Query: "What are relationships between ML, neural networks, training models?"
Expected: 3-5 relevant edges
Result: ✅ Already working, should continue
```

✅ **Compound queries handled correctly:**
```
Query: "How do neural networks relate to blockchain?"
Expected: Return neural network relationships, exclude blockchain
Result: ✅ Should work (blockchain not in content, neural networks are)
```

---

## References

This implementation guide is based on:

1. **Official Graphiti Documentation:**
   - https://help.getzep.com/graphiti/
   - https://help.getzep.com/v2/searching-the-graph

2. **Graphiti Research Report:**
   - `/docs/GRAPHITI_TEMPORAL_SEARCH_RESEARCH.md`

3. **Source Code Analysis:**
   - `graphiti_core/search/search_filters.py`
   - `graphiti_core/search/search_config.py`
   - `graphiti_core/graphiti.py`

4. **Zep Architecture Paper:**
   - arXiv:2501.13956v1

---

**Status:** Ready for implementation
**Last Updated:** 2025-10-23
**Next Step:** Implement Pattern 1 in `src/unified/graph_store.py`
