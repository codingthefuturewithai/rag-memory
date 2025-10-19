# Architecture Audit: MCP Tools vs CLI Commands

**Date**: 2025-10-19
**Issue**: Violations of "thin facade" principle - business logic duplicated in interface layers

## Principle

Both CLI and MCP tools should be **thin facades** over the business logic layer:

### ✅ CORRECT Pattern:
```python
def command_impl(dependencies):
    result = business_logic_layer.do_work(args)
    return format_for_interface(result)
```

### ❌ WRONG Pattern:
```python
def command_impl(dependencies):
    conn = db.connect()
    cur.execute("SELECT ... custom SQL ...")  # VIOLATION
    return custom_processing(rows)
```

---

## Audit Results

### Summary

- **Total Tools Audited**: 17
- **✅ CORRECT**: 12 tools (70.6%)
- **❌ VIOLATIONS**: 5 tools (29.4%)

---

## ✅ CORRECT Implementations (12)

1. **search_documents_impl** - Both call `searcher.search_chunks()`
2. **list_collections_impl** - Both call `coll_mgr.list_collections()`
3. **create_collection_impl** - Both call `coll_mgr.create_collection()`
4. **ingest_text_impl** - Both call `unified_mediator` or `doc_store.ingest_document()`
5. **get_document_by_id_impl** - Both call `doc_store.get_source_document()` + `get_document_chunks()`
6. **analyze_website_impl** - Both call `analyze_website()`
7. **ingest_file_impl** - Both call `unified_mediator` or `doc_store.ingest_file()`
8. **ingest_directory_impl** - Both call `unified_mediator` or `doc_store.ingest_file()`
9. **update_document_impl** - Both call `doc_store.update_document()`
10. **delete_document_impl** - Both call `doc_store.delete_document()`
11. **query_relationships_impl** - Calls `graph_store.search_relationships()`
12. **query_temporal_impl** - Calls `graph_store.search_relationships()`

---

## ❌ VIOLATIONS (5)

### 1. update_collection_description_impl (src/mcp/tools.py:121)

**Problem**: Both MCP and CLI execute direct SQL:
```python
cur.execute("UPDATE collections SET description = %s WHERE name = %s", ...)
```

**Fix Required**:
- Create `CollectionManager.update_description(name, description)` method
- Both MCP and CLI call this method

**Impact**: Medium - Both interfaces violate architecture

---

### 2. get_collection_info_impl (src/mcp/tools.py:267)

**Problem**: Both MCP and CLI execute custom SQL queries:
- Chunk count query
- Sample documents query
- Crawl history query

**Example violation** (lines 103-157):
```python
conn = db.connect()
with conn.cursor() as cur:
    cur.execute("""SELECT COUNT(DISTINCT dc.id) FROM document_chunks...""")
    chunk_count = cur.fetchone()[0]
    # More custom queries...
```

**Fix Required**:
- Create `CollectionManager.get_collection_info(name)` method with all statistics
- Both MCP and CLI call this method

**Impact**: High - Complex business logic duplicated in interface layer

---

### 3. check_existing_crawl (src/mcp/tools.py:371)

**Problem**: Helper function executes custom SQL:
```python
def check_existing_crawl(db: Database, url: str, collection_name: str):
    conn = db.connect()
    cur.execute("""SELECT ... FROM source_documents sd JOIN ...""")
```

**Fix Required**:
- Move to `DocumentStore.check_existing_crawl(url, collection_name)` method
- MCP calls this method

**Impact**: Medium - Business logic in wrong layer

---

### 4. ingest_url_impl - Recrawl Logic (src/mcp/tools.py:295-332)

**Problem**: Both MCP and CLI duplicate recrawl deletion logic with direct SQL:

**MCP** (lines 295-332):
```python
if mode == "recrawl":
    conn = db.connect()
    cur.execute("SELECT id, filename FROM source_documents WHERE metadata->>'crawl_root_url' = %s")
    # Delete Graph episodes
    # Delete chunks
    # Delete source documents
```

**CLI** (src/cli.py:183-230):
```python
# Identical SQL queries and deletion logic
cur.execute("SELECT id, filename FROM source_documents WHERE metadata->>'crawl_root_url' = %s")
# Delete chunks
# Delete source documents
```

**Fix Required**:
- Create `DocumentStore.delete_by_crawl_url(url, graph_store=None)` method
- Both MCP and CLI call this method
- Method handles both RAG and Graph cleanup

**Impact**: HIGH - Complex business logic duplicated in TWO interface layers

---

### 5. list_documents_impl (src/mcp/tools.py:855) 🔴 CRITICAL

**Problem**: MCP uses custom SQL, CLI uses business logic layer

**MCP** (lines 693-739):
```python
conn = db.connect()
if collection_name:
    # Custom SQL with pagination
    cur.execute("""
        SELECT sd.id, sd.filename, ... COUNT(dc.id) as chunk_count
        FROM source_documents sd
        JOIN document_chunks dc ...
        WHERE cc.collection_id = %s
        GROUP BY sd.id, ...
        LIMIT %s OFFSET %s
    """)
```

**CLI** (line 792):
```python
documents = doc_store.list_source_documents(collection)  # ✅ CORRECT
```

**Fix Required**:
- Enhance `DocumentStore.list_source_documents()` to support:
  - `limit` and `offset` parameters (pagination)
  - `include_details` flag (extended metadata)
  - Return total count for pagination
- MCP calls the enhanced method
- CLI may need updates if it needs pagination

**Impact**: CRITICAL - This is the bug we just fixed, and it's a symptom of the architectural violation

---

## Remediation Plan

### Priority 1 (CRITICAL - Fix Immediately)
1. **list_documents_impl** - Refactor to use DocumentStore

### Priority 2 (HIGH - Fix This Sprint)
2. **ingest_url_impl recrawl logic** - Create DocumentStore method
3. **get_collection_info_impl** - Create CollectionManager method

### Priority 3 (MEDIUM - Fix Next Sprint)
4. **update_collection_description_impl** - Create CollectionManager method
5. **check_existing_crawl** - Move to DocumentStore

---

## Root Cause Analysis

**Why did this happen?**

The MCP tools were likely implemented by:
1. Looking at what the CLI does
2. Seeing the CLI uses SQL queries in some places
3. Copying that pattern instead of recognizing it as a violation

**The real issue**: Some CLI commands also violate the architecture (especially `collection info`). When MCP tools were created, these violations were replicated instead of fixed.

---

## Lessons Learned

1. ✅ **DO**: Interface layers call business logic methods
2. ❌ **DON'T**: Interface layers execute SQL directly
3. ✅ **DO**: Put business logic in `DocumentStore`, `CollectionManager`, or service classes
4. ❌ **DON'T**: Duplicate business logic across interface layers
5. ✅ **DO**: If business logic is missing, add it to the appropriate layer FIRST

---

## Next Steps

1. Fix Priority 1 violation (list_documents)
2. Create architectural review checklist for future PRs
3. Add linting/testing to catch violations
4. Fix remaining violations in priority order
