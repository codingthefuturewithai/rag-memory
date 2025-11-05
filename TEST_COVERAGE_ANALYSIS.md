# Test Coverage Analysis - Ingest Tools & Reingest Mode

**Date:** 2025-11-05
**Context:** Comprehensive testing completed manually for centralized deletion logic (`delete_document_for_reingest`). This report analyzes existing automated test coverage and identifies gaps.

---

## Executive Summary

**Current State:**
- ✅ All 4 ingest tools have **basic ingestion tests**
- ✅ Duplicate detection is **partially tested** (URLs only)
- ❌ **NO automated tests** for `mode="reingest"` parameter across ANY ingest tool
- ❌ **NO tests** for centralized deletion function (`delete_document_for_reingest`)
- ❌ **CRITICAL GAP:** The bug we just fixed (missing `await` on deletion) would NOT have been caught by existing tests

**Risk Assessment:** 🔴 **HIGH RISK**
- Manual testing validated the fix, but future regressions are likely without automated coverage
- The centralized deletion logic is a critical component that affects data integrity across all 4 ingest tools

---

## Current Test Coverage by Tool

### 1. `ingest_text` (tests/integration/mcp/test_ingestion.py)

**Existing Tests:**
- ✅ Basic ingestion creates searchable documents
- ✅ Metadata preservation
- ✅ Non-existent collection error handling

**Coverage Gaps:**
- ❌ Duplicate detection (no test for ingesting same title twice with `mode="ingest"`)
- ❌ Reingest mode (no test for `mode="reingest"` updating existing documents)
- ❌ Verification that old document is completely removed after reingest
- ❌ Graph cleanup during reingest

**Lines of Code Tested:** ~45 / ~150 (30%)

---

### 2. `ingest_file` (tests/integration/mcp/test_ingest_file.py)

**Existing Tests:**
- ✅ Basic file ingestion (text and markdown)
- ✅ Metadata preservation
- ✅ Invalid collection error handling
- ✅ Non-existent file error handling
- ✅ Response structure validation

**Coverage Gaps:**
- ❌ Duplicate detection (no test for ingesting same file_path twice with `mode="ingest"`)
- ❌ Reingest mode (no test for `mode="reingest"` updating existing files)
- ❌ Verification that old document is completely removed after reingest
- ❌ Graph cleanup during reingest

**Lines of Code Tested:** ~50 / ~150 (33%)

---

### 3. `ingest_directory` (tests/integration/mcp/test_ingest_directory.py)

**Existing Tests:**
- ✅ Basic directory ingestion (multiple files)
- ✅ File extension filtering
- ✅ Empty directory handling
- ✅ Invalid collection error handling
- ✅ Non-existent directory error handling
- ✅ Response structure validation

**Coverage Gaps:**
- ❌ Duplicate detection (no test for ingesting same directory twice with `mode="ingest"`)
- ❌ Reingest mode (no test for `mode="reingest"` updating existing batch)
- ❌ Verification that all old documents are removed after reingest
- ❌ Mixed scenario: Some files exist, some are new
- ❌ Graph cleanup during reingest (for all files in batch)

**Lines of Code Tested:** ~45 / ~200 (22%)

---

### 4. `ingest_url` (tests/integration/mcp/test_ingest_url.py)

**Existing Tests:**
- ✅ Single page crawling
- ✅ Document IDs inclusion
- ✅ Invalid collection error handling
- ✅ **Duplicate detection (crawl mode)** ✨ *Only tool with this coverage*
- ✅ **Recrawl mode basic functionality** ✨ *Only tool with this coverage*
- ✅ Response structure validation
- ✅ Multi-page crawling with follow_links

**Coverage Gaps:**
- ⚠️ Recrawl test exists but **DOES NOT verify complete deletion** of old documents
- ⚠️ Recrawl test **DOES NOT verify graph cleanup**
- ❌ No verification that old pages are completely removed (only checks new data exists)
- ❌ No test for error handling if deletion fails during recrawl

**Lines of Code Tested:** ~60 / ~180 (33%)

**Note:** This is the ONLY tool with any reingest/recrawl testing, but even here the coverage is incomplete (doesn't verify deletion completeness).

---

## Critical Function: `delete_document_for_reingest`

**Location:** `src/mcp/tools.py:1074-1140`
**Used By:** All 4 ingest tools (4 call sites)

**Current Test Coverage:** ❌ **0% - NOT TESTED AT ALL**

**What This Function Does:**
1. Deletes Knowledge Graph episode (all entities, relationships, edges)
2. Deletes RAG document (all chunks, embeddings, metadata, collection links)
3. Verifies deletion succeeded
4. Raises exception if ANY step fails (abort reingest to prevent corruption)

**Why This is Critical:**
- **Data Integrity:** Prevents duplicate documents with stale data
- **Graph Consistency:** Ensures graph and RAG stay synchronized
- **Error Handling:** Aborts reingest if deletion fails (prevents partial corruption)
- **Used by ALL 4 ingest tools:** Single point of failure

**Missing `await` Bug:**
The bug we just fixed (missing `await` on `doc_store.delete_document()`) would have been caught if this function had test coverage. The bug allowed:
- Coroutine warnings in logs
- Potential race conditions
- Incomplete deletions before reingest

---

## Test Suite Gaps Summary

| Test Scenario | ingest_text | ingest_file | ingest_directory | ingest_url |
|--------------|-------------|-------------|------------------|------------|
| **Basic Ingestion** | ✅ | ✅ | ✅ | ✅ |
| **Duplicate Detection** | ❌ | ❌ | ❌ | ✅ |
| **Reingest Mode** | ❌ | ❌ | ❌ | ⚠️ (incomplete) |
| **Complete Deletion Verification** | ❌ | ❌ | ❌ | ❌ |
| **Graph Cleanup Verification** | ❌ | ❌ | ❌ | ❌ |
| **Error Handling (deletion fails)** | ❌ | ❌ | ❌ | ❌ |
| **Centralized Deletion Function** | ❌ | ❌ | ❌ | ❌ |

**Overall Coverage Estimate:** ~25-30% (basic ingestion only)
**Target Coverage:** 80-90% (including all critical paths)

---

## Recommended Test Additions

### Priority 1: CRITICAL (Must Have)

#### A. Add Comprehensive Reingest Tests for All 4 Tools

**New Test File:** `tests/integration/mcp/test_reingest_modes.py`

**Test Cases (per tool):**

1. **`test_<tool>_duplicate_detection_mode_ingest`**
   - Ingest content with `mode="ingest"`
   - Attempt to ingest identical content with `mode="ingest"` again
   - **Verify:** Error raised with suggestion to use `mode="reingest"`
   - **Verify:** Error message includes correct identification of duplicate

2. **`test_<tool>_reingest_mode_deletes_old_document`**
   - Ingest content with `mode="ingest"` → Get doc_id_1
   - Ingest identical content with `mode="reingest"` → Get doc_id_2
   - **Verify:** doc_id_1 completely removed from database
   - **Verify:** doc_id_2 exists with new content
   - **Verify:** Only ONE document exists (not both)
   - **Verify:** Chunk count matches new ingestion

3. **`test_<tool>_reingest_mode_cleans_graph`**
   - Ingest content with `mode="ingest"` → Creates graph episode `doc_X`
   - Query graph to verify episode exists
   - Ingest same content with `mode="reingest"`
   - **Verify:** Old graph episode `doc_X` is deleted
   - **Verify:** New graph episode created
   - **Verify:** Graph nodes/edges from old document are gone

4. **`test_<tool>_reingest_mode_preserves_other_documents`**
   - Ingest document A with `mode="ingest"`
   - Ingest document B with `mode="ingest"`
   - Reingest document A with `mode="reingest"`
   - **Verify:** Document B is completely untouched
   - **Verify:** Only document A was affected

**Estimated Work:** 4 tools × 4 tests = 16 new test cases (~4-6 hours)

---

#### B. Add Direct Tests for `delete_document_for_reingest`

**New Test File:** `tests/unit/test_delete_document_for_reingest.py`

**Test Cases:**

1. **`test_delete_document_for_reingest_success`**
   - Create test document and graph episode
   - Call `delete_document_for_reingest()`
   - **Verify:** Document completely removed from PostgreSQL
   - **Verify:** Graph episode completely removed from Neo4j
   - **Verify:** Verification step passes (document doesn't exist)

2. **`test_delete_document_for_reingest_graph_deletion_fails`**
   - Mock graph_store to raise exception
   - Call `delete_document_for_reingest()`
   - **Verify:** Exception is raised and propagated
   - **Verify:** Error message indicates graph deletion failed
   - **Verify:** Function aborts cleanly

3. **`test_delete_document_for_reingest_rag_deletion_fails`**
   - Mock doc_store.delete_document() to raise exception
   - Call `delete_document_for_reingest()`
   - **Verify:** Exception is raised and propagated
   - **Verify:** Error message indicates RAG deletion failed

4. **`test_delete_document_for_reingest_verification_fails`**
   - Mock doc_store.get_source_document() to return non-None after deletion
   - Call `delete_document_for_reingest()`
   - **Verify:** Exception raised with "CRITICAL" message
   - **Verify:** Error prevents reingest from continuing

5. **`test_delete_document_for_reingest_no_graph_store`**
   - Call with graph_store=None
   - **Verify:** Function completes without error
   - **Verify:** Only RAG deletion is performed
   - **Verify:** Warning logged about skipping graph deletion

**Estimated Work:** 5 test cases (~2-3 hours)

---

### Priority 2: IMPORTANT (Should Have)

#### C. Enhance Existing `ingest_url` Recrawl Tests

**File:** `tests/integration/mcp/test_ingest_url.py:151-195`

**Current Test:** `test_ingest_url_recrawl_mode` (line 151)
- ✅ Tests that recrawl succeeds
- ✅ Verifies new chunks are created
- ❌ **Does NOT verify old documents are deleted**
- ❌ **Does NOT verify complete cleanup**

**Enhancement:**
```python
async def test_ingest_url_recrawl_mode(self, mcp_session, setup_test_collection):
    # ... existing code ...

    response1 = json.loads(extract_text_content(result1))
    first_chunk_count = response1.get("total_chunks", 0)
    first_doc_ids = response1.get("document_ids", [])  # NEW: Capture old doc IDs

    # ... recrawl code ...

    response2 = json.loads(extract_text_content(result2))
    second_doc_ids = response2.get("document_ids", [])  # NEW: Capture new doc IDs

    # NEW: Verify old documents are completely deleted
    for old_doc_id in first_doc_ids:
        verify_result = await session.call_tool("get_document_by_id", {
            "document_id": old_doc_id
        })
        assert verify_result.isError, f"Old document {old_doc_id} should be deleted"

    # NEW: Verify new documents exist
    for new_doc_id in second_doc_ids:
        verify_result = await session.call_tool("get_document_by_id", {
            "document_id": new_doc_id
        })
        assert not verify_result.isError, f"New document {new_doc_id} should exist"
```

**Estimated Work:** ~1 hour

---

### Priority 3: NICE TO HAVE (Future Enhancement)

#### D. Add Performance/Scale Tests

**New Test File:** `tests/integration/mcp/test_reingest_performance.py`

**Test Cases:**

1. **`test_reingest_large_document`**
   - Ingest 10MB document
   - Reingest same document
   - **Verify:** Deletion completes within reasonable time (<30s)
   - **Verify:** No memory leaks

2. **`test_reingest_many_chunks`**
   - Ingest document creating 100+ chunks
   - Reingest same document
   - **Verify:** All chunks deleted correctly
   - **Verify:** Performance is acceptable

3. **`test_concurrent_reingest_different_documents`**
   - Trigger 3 simultaneous reingests of different documents
   - **Verify:** All complete successfully
   - **Verify:** No race conditions
   - **Verify:** No cross-contamination

**Estimated Work:** 3 test cases (~3-4 hours)

---

## Implementation Plan

### Phase 1: Critical Coverage (Week 1)

**Goal:** Prevent regressions of the bug we just fixed

1. ✅ Manual testing completed (documented in this session)
2. 📋 Create `test_reingest_modes.py` with all 16 test cases (Priority 1.A)
3. 📋 Create `test_delete_document_for_reingest.py` with 5 test cases (Priority 1.B)
4. 📋 Run full test suite and verify all tests pass
5. 📋 Add to CI/CD pipeline

**Success Criteria:**
- All 21 new tests passing
- Code coverage for `delete_document_for_reingest()` reaches 100%
- Coverage for reingest mode in all 4 tools reaches 80%+

**Estimated Time:** 8-10 hours

---

### Phase 2: Enhancement (Week 2)

**Goal:** Strengthen existing weak coverage

1. 📋 Enhance `test_ingest_url_recrawl_mode` (Priority 2.C)
2. 📋 Add missing duplicate detection tests for text/file/directory (Priority 1.A items 1-2)
3. 📋 Review and update existing tests for consistency
4. 📋 Add test documentation to README

**Success Criteria:**
- All ingest tools have equivalent test coverage
- No tool has <50% coverage for critical paths
- Test suite documentation is complete

**Estimated Time:** 4-6 hours

---

### Phase 3: Advanced Testing (Optional - Future)

**Goal:** Ensure robustness under edge cases

1. 📋 Implement performance/scale tests (Priority 3.D)
2. 📋 Add chaos engineering tests (network failures, database timeouts)
3. 📋 Add integration tests with real Neo4j graph complexity
4. 📋 Property-based testing with Hypothesis

**Success Criteria:**
- System handles edge cases gracefully
- Performance benchmarks are established
- Chaos scenarios documented

**Estimated Time:** 8-12 hours

---

## Risk Assessment Without Tests

**What Could Break Without Coverage:**

1. **Missing `await` Regression** (High Risk)
   - Symptom: Coroutine warnings in logs
   - Impact: Incomplete deletions, duplicate documents
   - Likelihood: HIGH (already happened once)

2. **Partial Deletion** (Critical Risk)
   - Symptom: Old documents remain after reingest
   - Impact: Stale data in search results, graph corruption
   - Likelihood: MEDIUM (would manifest if deletion logic changes)

3. **Graph Desynchronization** (High Risk)
   - Symptom: Graph has nodes for deleted documents
   - Impact: Incorrect relationships, query errors
   - Likelihood: MEDIUM (if graph deletion order changes)

4. **Collection Contamination** (Medium Risk)
   - Symptom: Reingest of doc A affects doc B
   - Impact: Data integrity issues, user confusion
   - Likelihood: LOW (but high impact)

**Current Protection:** ⚠️ **Manual testing only** (not sustainable)

---

## Recommendations Summary

### Immediate Action Items (This Sprint)

1. **Create `test_reingest_modes.py`** - Comprehensive reingest testing for all 4 tools
2. **Create `test_delete_document_for_reingest.py`** - Direct unit tests for centralized deletion
3. **Update CI/CD** - Ensure new tests run on every commit

### Success Metrics

- **Code Coverage:** Increase from 30% → 80% for ingest tools
- **Regression Protection:** 100% coverage for `delete_document_for_reingest()`
- **Confidence Level:** Can deploy reingest changes without manual testing

### Long-Term

- Add performance benchmarks
- Document testing strategy in `.reference/TESTING_STRATEGY.md`
- Create test data generator for reproducible scenarios

---

## Appendix: Test Execution Results

**Manual Testing Session (2025-11-05):**

All 4 ingest tools tested manually with comprehensive scenarios:
- ✅ Duplicate detection working correctly
- ✅ Reingest mode deletes old documents completely
- ✅ Graph cleanup verified in logs
- ✅ No coroutine warnings
- ✅ Only new documents exist after reingest

**Test Files Created During Session:**
- Collection: `test-ingest` (ID 13)
- Documents ingested: 48 total
- Test files: `test-article.txt`, `test-data/project-docs/*.md`
- Test URLs: `example.com`, `docs.python.org/3/library/asyncio.html`

**Docker Logs Verified:**
- All deletion sequences logged correctly
- Verification steps confirmed in logs
- PostgreSQL CASCADE working as expected
- Neo4j episode deletion confirmed

---

**Report Generated:** 2025-11-05
**Next Review:** After Phase 1 implementation (1 week)
