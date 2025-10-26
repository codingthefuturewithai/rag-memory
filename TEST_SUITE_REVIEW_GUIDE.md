# Test Suite Review Guide - Collection Metadata & Graph Filtering Updates

## Overview

This guide documents recent major changes to the RAG Memory system and provides instructions for reviewing the test suite to ensure all tests reflect the new behavior.

## What We Just Implemented (2025-10-26)

### 1. Topics Removal from Mandatory Metadata

**What Changed:**
- Removed `topics` entirely from the mandatory metadata system
- `topics` is NO LONGER a required field on any ingestion calls
- System metadata now only includes: `file_type`, `ingested_at`

**Impact:**
- All MCP tools (ingest_text, ingest_file, ingest_directory, ingest_url) no longer accept `topics` parameter
- Collection metadata schemas cannot include `topics` in mandatory section
- Any test passing `topics=` parameter should be updated or verified removed

**Files Changed:**
- `src/core/collections.py` - Removed topics from mandatory metadata
- `src/mcp/server.py` - Removed topics from all MCP tool signatures
- `src/mcp/tools.py` - Removed topics handling from all ingestion implementations
- 9 test files already updated (see list below)

### 2. Auto-Apply Domain and Domain_Scope

**What Changed:**
- `domain` and `domain_scope` are now automatically copied from collection to ALL ingested documents
- MCP clients NO LONGER pass `domain` or `domain_scope` on ingest calls
- These fields are internally managed (like system metadata)

**How It Works:**
```python
# Collection has domain/domain_scope
collection = {"domain": "software-engineering", "domain_scope": "REST API documentation"}

# On ingest, these are automatically applied to document metadata
# Client only provides custom metadata (e.g., author, version, etc.)
document_metadata = {
    "domain": "software-engineering",        # AUTO-APPLIED from collection
    "domain_scope": "REST API documentation", # AUTO-APPLIED from collection
    "author": "John Doe",                     # Client-provided custom metadata
    "version": "1.0"                          # Client-provided custom metadata
}
```

**Impact:**
- Tests should verify domain/domain_scope are present in document metadata after ingestion
- Tests should NOT pass domain/domain_scope in metadata on ingest calls
- Search tests can filter by domain/domain_scope (it's in the document metadata)

**Files Changed:**
- `src/core/ingestion.py` - Auto-apply logic in `_apply_metadata_to_document()`
- All ingestion tools in `src/mcp/tools.py`

### 3. Collection Filtering via group_ids

**What Changed:**
- Added `collection_name` parameter to `query_relationships` MCP tool
- Added `collection_name` parameter to `query_temporal` MCP tool
- Both tools now convert `collection_name` to `group_ids` and filter graph results

**How It Works:**
```python
# MCP client calls with collection_name
query_relationships(
    query="How do I authenticate users?",
    collection_name="user-management-docs",  # NEW parameter
    threshold=0.35
)

# Implementation converts to group_ids
group_ids = ["user-management-docs"]

# Graphiti filters results to only that collection
results = await graphiti.search_(query, group_ids=group_ids)
```

**Impact:**
- Graph search tests should verify collection filtering works
- Tests should verify results only come from specified collection
- Tests should verify omitting collection_name returns results from all collections

**Files Changed:**
- `src/unified/graph_store.py` - Added `group_ids` parameter to `search_relationships()`
- `src/mcp/server.py` - Added `collection_name` to both graph query tools
- `src/mcp/tools.py` - Updated implementations to convert and pass `group_ids`

### 4. Temporal Filtering Using Graphiti SearchFilters API

**What Changed:**
- Replaced buggy client-side temporal filtering with Graphiti's built-in SearchFilters API
- Properly handles null `invalid_at` (current facts) using OR logic
- Added `threshold` parameter to `query_temporal` for consistency with `query_relationships`

**How It Works:**
```python
# MCP client queries for facts valid at a specific time
query_temporal(
    query="What are the current authentication best practices?",
    collection_name="user-management-docs",
    valid_from="2025-10-26T12:00:00+00:00",  # Only facts valid at/after this time
    threshold=0.35
)

# Implementation builds SearchFilters with OR logic
SearchFilters(
    invalid_at=[
        [DateFilter(date=valid_from, comparison_operator='>=')],  # OR
        [DateFilter(date=None, comparison_operator='IS NULL')]    # Still valid (current)
    ]
)
```

**Temporal Logic:**
- `valid_until`: Facts must have started on or before this time (`valid_at <= valid_until`)
- `valid_from`: Facts must not have ended before this time (`invalid_at >= valid_from OR invalid_at IS NULL`)
- No filters: Returns all results

**Impact:**
- Temporal tests should verify time-based filtering works correctly
- Tests should verify null `invalid_at` facts are included when appropriate
- Tests should verify both `valid_from` and `valid_until` filters work

**Files Changed:**
- `src/mcp/tools.py` - Complete rewrite of `query_temporal_impl()` to use SearchFilters
- Removed 56 lines of buggy client-side filtering logic

### 5. Pydantic Type Hint Fixes

**What Changed:**
- Fixed optional string parameters in MCP tools to use `str | None = None` instead of `str = None`
- Prevents Pydantic validation errors when clients omit optional parameters

**Example:**
```python
# BEFORE (broken)
async def query_temporal(
    valid_from: str = None,  # Pydantic validates as type `str`, rejects None
    valid_until: str = None,
)

# AFTER (fixed)
async def query_temporal(
    valid_from: str | None = None,  # Pydantic accepts both str and None
    valid_until: str | None = None,
)
```

**Impact:**
- Tests calling tools with omitted optional parameters should work without validation errors
- Verify tools accept None for optional parameters

**Files Changed:**
- `src/mcp/server.py` - Fixed type hints in `query_temporal` tool signature

### 6. Semantic Search Warning in CLAUDE.md

**What Changed:**
- Added prominent warning at top of CLAUDE.md about semantic search vs keyword search
- All search queries must be full questions/statements, NOT keywords

**Example:**
```
✓ CORRECT: "How do I authenticate users in the system?"
✗ WRONG: "user authentication"
```

**Impact:**
- Any test documentation or examples should use semantic queries
- Test query strings should be full questions, not keywords

## Test Files Already Updated (Topics Removal)

The following 9 test files were already updated to remove `topics=` parameter:

1. `tests/integration/backend/test_document_chunking.py`
2. `tests/integration/backend/test_rag_graph.py` (2 locations)
3. `tests/integration/web/test_recrawl.py`
4. `tests/integration/web/test_web_ingestion.py`
5. `tests/integration/web/test_web_link_following.py`
6. `tests/integration/test_delete_collection_graph_cleanup.py`
7. `tests/integration/cli/test_cli_integration.py`
8. `tests/unit/test_collection_metadata_schema.py`
9. `tests/unit/cli/test_cli_commands.py`

## Test Suite Review Instructions

### Step 1: Identify All Test Files Touching Changed Areas

**Search for tests involving:**
```bash
# Collection creation/metadata
grep -r "create_collection" tests/
grep -r "metadata_schema" tests/

# Document ingestion
grep -r "ingest_text" tests/
grep -r "ingest_file" tests/
grep -r "ingest_directory" tests/
grep -r "ingest_url" tests/

# Graph queries
grep -r "query_relationships" tests/
grep -r "query_temporal" tests/
grep -r "search_relationships" tests/

# Metadata searches
grep -r "metadata_filter" tests/
grep -r "search_documents" tests/
```

### Step 2: Review Each Test Category

#### A. Collection Creation Tests

**What to Check:**
- ✓ Tests can still create collections with custom metadata schemas
- ✓ Tests verify `domain` and `domain_scope` are in collection metadata
- ✗ Tests should NOT include `topics` in metadata schemas
- ✓ Tests verify `system` metadata section is always empty `[]`

**Example Test Pattern:**
```python
# CORRECT
metadata_schema = {
    "mandatory": {
        "domain": "value",
        "domain_scope": "value"
    },
    "optional": {
        "author": "string",
        "version": "string"
    },
    "system": []  # Always empty, internally managed
}

# WRONG - topics should not appear
metadata_schema = {
    "mandatory": {
        "topics": ["list"],  # ❌ REMOVED
    }
}
```

#### B. Ingestion Tests (Text, File, Directory, URL)

**What to Check:**
- ✗ Tests should NOT pass `topics=` parameter (already removed from 9 files)
- ✗ Tests should NOT pass `domain` or `domain_scope` in metadata (auto-applied)
- ✓ Tests CAN pass custom metadata (author, version, etc.)
- ✓ After ingestion, verify document has `domain` and `domain_scope` from collection
- ✓ Verify `file_type` and `ingested_at` system metadata are present

**Example Test Pattern:**
```python
# CORRECT - Only pass custom metadata
await ingest_text(
    content="...",
    collection_name="my-collection",
    document_title="My Doc",
    metadata={
        "author": "John Doe",
        "version": "1.0"
    }
)

# Verify auto-applied fields
doc = await get_document(doc_id)
assert doc["metadata"]["domain"] == "software-engineering"  # From collection
assert doc["metadata"]["domain_scope"] == "REST API"         # From collection
assert doc["metadata"]["author"] == "John Doe"               # Custom
assert "file_type" in doc["metadata"]                        # System
assert "ingested_at" in doc["metadata"]                      # System

# WRONG - Don't pass domain/domain_scope/topics
await ingest_text(
    content="...",
    metadata={
        "topics": ["auth"],           # ❌ REMOVED
        "domain": "software",          # ❌ AUTO-APPLIED
        "domain_scope": "API docs"     # ❌ AUTO-APPLIED
    }
)
```

#### C. Search Tests (VectorStore)

**What to Check:**
- ✓ Tests can filter by `domain` and `domain_scope` (it's in document metadata)
- ✓ Tests can filter by custom metadata (author, version, etc.)
- ✗ Tests should NOT filter by `topics` (removed)
- ✓ Search queries should be semantic (full questions), NOT keywords

**Example Test Pattern:**
```python
# CORRECT - Filter by domain (it's in document metadata)
results = await search_documents(
    query="How do I authenticate users in the system?",  # Semantic query
    collection_name="my-collection",
    metadata_filter={
        "domain": "software-engineering",   # Can filter (in metadata)
        "author": "John Doe"                 # Can filter (custom field)
    }
)

# WRONG - Keyword query
results = await search_documents(
    query="user authentication",  # ❌ Use semantic query
)

# WRONG - Filter by topics (removed)
results = await search_documents(
    metadata_filter={
        "topics": ["auth"]  # ❌ REMOVED
    }
)
```

#### D. Graph Query Tests (Relationships & Temporal)

**What to Check:**
- ✓ Tests can pass `collection_name` to filter results by collection
- ✓ Tests verify collection filtering works (only returns results from that collection)
- ✓ Tests verify omitting `collection_name` returns results from all collections
- ✓ Temporal tests verify `valid_from` and `valid_until` filters work
- ✓ Temporal tests verify null `invalid_at` (current facts) are handled correctly
- ✓ Both tools accept `threshold` parameter (default 0.35)
- ✓ Search queries should be semantic (full questions), NOT keywords

**Example Test Pattern:**
```python
# CORRECT - Test collection filtering
results = await query_relationships(
    query="How do users authenticate in the system?",  # Semantic
    collection_name="user-management-docs",             # Filter by collection
    threshold=0.35
)
assert all(r.collection == "user-management-docs" for r in results)

# CORRECT - Test temporal filtering
results = await query_temporal(
    query="What were the authentication best practices before OAuth?",
    collection_name="user-management-docs",
    valid_until="2025-10-25T00:00:00+00:00",  # Facts valid before this date
    threshold=0.35
)

# CORRECT - Test current facts
results = await query_temporal(
    query="What are the current authentication best practices?",
    valid_from="2025-10-26T12:00:00+00:00",  # Includes facts with null invalid_at
)

# WRONG - Keyword query
results = await query_relationships(
    query="authentication methods",  # ❌ Use semantic query
)
```

#### E. MCP Integration Tests

**What to Check:**
- ✓ Tests call MCP tools with correct parameter signatures
- ✓ Tests verify optional parameters can be omitted without validation errors
- ✓ Tests verify `str | None` parameters accept both string and None
- ✓ Tests verify collection filtering works across all graph query tools

**Example Test Pattern:**
```python
# CORRECT - Test optional parameters
result = await query_temporal(
    query="How do I authenticate users?",
    # collection_name omitted (should work)
    # valid_from omitted (should work)
    # valid_until omitted (should work)
)

# CORRECT - Test with all parameters
result = await query_temporal(
    query="How do I authenticate users?",
    collection_name="user-management-docs",
    valid_from="2025-10-26T00:00:00+00:00",
    valid_until="2025-10-27T00:00:00+00:00",
    threshold=0.5
)
```

### Step 3: Run Test Suite and Verify

```bash
# Run all tests
uv run pytest -xvs

# Run specific test categories
uv run pytest tests/integration/backend/ -xvs       # Backend integration
uv run pytest tests/integration/mcp/ -xvs           # MCP tools
uv run pytest tests/unit/test_collection_metadata_schema.py -xvs  # Metadata schema

# Run tests with specific patterns
uv run pytest -k "ingest" -xvs                      # All ingestion tests
uv run pytest -k "graph" -xvs                       # All graph tests
uv run pytest -k "search" -xvs                      # All search tests
uv run pytest -k "temporal" -xvs                    # Temporal tests
```

### Step 4: Common Issues to Look For

1. **Topics still referenced:**
   - Search for `topics=` in test files
   - Search for `"topics"` in metadata schemas
   - Search for topics in metadata filters

2. **Domain/domain_scope passed on ingest:**
   - Tests should NOT pass these in metadata (auto-applied)
   - Tests SHOULD verify these exist after ingestion

3. **Keyword searches instead of semantic:**
   - Search queries should be full questions/statements
   - Not single words or short phrases

4. **Missing collection_name parameter:**
   - Graph query tests should test WITH and WITHOUT collection filtering
   - Verify filtering works correctly

5. **Temporal filtering edge cases:**
   - Test with `valid_from` only (should include current facts)
   - Test with `valid_until` only (should include facts before that time)
   - Test with both (should include facts in time window)
   - Test with neither (should return all results)

6. **Pydantic validation errors:**
   - Optional parameters should accept None without errors
   - Check for `str = None` vs `str | None = None` issues

## Expected Test Results

**All 397 tests should pass.**

If tests fail, likely causes:
1. Test still references `topics` parameter
2. Test expects domain/domain_scope in ingest call instead of auto-apply
3. Test uses keyword query instead of semantic query
4. Test expects temporal filtering to exclude current facts (null `invalid_at`)
5. Test doesn't account for collection filtering via `group_ids`

## Summary of Key Behavioral Changes

| Feature | Before | After |
|---------|--------|-------|
| Topics | Required on all ingests | Completely removed |
| Domain/Domain_Scope | Clients pass on each ingest | Auto-applied from collection |
| Collection Filtering | Not available in graph queries | Available via `collection_name` parameter |
| Temporal Filtering | Client-side logic (buggy) | Graphiti SearchFilters API (correct) |
| Current Facts | Excluded by temporal filters | Included via OR logic (null `invalid_at`) |
| Query Style | Mixed keyword/semantic | Semantic only (full questions) |
| Optional Parameters | `str = None` (broken) | `str | None = None` (correct) |

## Files to Review for Test Changes

**Core Implementation:**
- `src/core/collections.py` - Collection metadata handling
- `src/core/ingestion.py` - Auto-apply logic
- `src/unified/graph_store.py` - Graph operations with group_ids
- `src/mcp/server.py` - MCP tool signatures
- `src/mcp/tools.py` - MCP tool implementations

**Test Files (Priority Order):**
1. `tests/unit/test_collection_metadata_schema.py` - Collection metadata schema tests
2. `tests/integration/mcp/test_*.py` - All MCP integration tests
3. `tests/integration/backend/test_rag_graph.py` - Graph integration tests
4. `tests/integration/backend/test_document_chunking.py` - Ingestion tests
5. `tests/integration/web/test_web_ingestion.py` - Web ingestion tests
6. `tests/integration/cli/test_cli_integration.py` - CLI integration tests
7. Any test with "search", "query", "ingest", or "collection" in the name

## Next Steps

1. Read this guide thoroughly
2. Search for test files touching changed areas (Step 1)
3. Review each test category systematically (Step 2)
4. Run tests and verify all pass (Step 3)
5. Fix any failures using common issues guide (Step 4)
6. Report findings and any needed updates

---

**Document Created:** 2025-10-26
**Commit Reference:** cb879a9
**Test Status:** All 397 tests passing at time of writing
