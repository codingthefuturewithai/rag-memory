# Debugging Session - Ingest URL & Duplicate Check Issues

**Session Date:** 2025-11-01
**Primary Issue:** Docker crawling hanging + duplicate check bugs discovered during testing

---

## Timeline of Events (Chronological Order)

### Initial Problem
- `ingest_url` with `follow_links=True` was hanging in Docker container after 2nd page
- Code worked perfectly in local Python environment
- Root cause: Crawl4AI v0.6.0 has known Chrome browser process cleanup bug in Docker (GitHub issue #943)

### Fix Applied
1. Upgraded Crawl4AI v0.6.0 → v0.7.6
2. Added Chrome flags: `--single-process`, `--no-zygote`, `--no-sandbox`, `--disable-dev-shm-usage`
3. Added `stream=True` and `session_id` to CrawlerRunConfig
4. Result: Test script successfully crawled 5 pages in Docker without hanging

### ChatGPT Testing Revealed New Issues
1. User had ChatGPT test the Docker container
2. ChatGPT got duplicate check error when trying to ingest
3. Investigation found orphaned document 107 from interrupted graph extraction
4. User deleted collection "test_docker_crawl" to clean up

### Critical Discovery - Document Count Discrepancy

**BEFORE Collection Delete:**
- PostgreSQL database had **12 total source_documents** (IDs: 93-102, 112, 113)
- CLI command `rag list-documents --collection test_docker_crawl` showed **13 documents**
- Documents 112 and 113 were from python.org/about crawl
- **PROBLEM: This is mathematically impossible - collection can't have more documents than exist in entire database**

**AFTER Collection Delete:**
- PostgreSQL database has **10 source_documents** (IDs: 93-102)
- Documents 112 and 113 were successfully deleted
- Collection "test_docker_crawl" no longer exists
- System now in clean state

---

## Problems Identified

### PROBLEM 1: IMPOSSIBLE DOCUMENT COUNT
- **What:** CLI claimed 13 documents in collection, database only had 12 total documents
- **Impact:** Indicates bug in counting logic or corrupted state
- **Possible Causes:**
  - Bug in `list_documents` counting logic
  - Bug in chunk_collections tracking
  - Phantom/corrupted database state
- **Status:** UNRESOLVED - need to investigate counting logic

### PROBLEM 2: FAULTY DUPLICATE CHECK IN ingest_url
- **What:** `check_existing_crawl()` prevents re-ingesting same URL even into DIFFERENT collections
- **Location:** `src/mcp/tools.py` lines 924-973
- **User Quote:** "You can't prevent me from deciding that I want to crawl the same website for a different collection"
- **Impact:** Legitimate use case blocked
- **Status:** IDENTIFIED - needs fix

### PROBLEM 3: INCONSISTENT DUPLICATE CHECKING
- **What:** Only `ingest_url` has duplicate checking, other ingest methods don't
- **Affected Methods:**
  - `ingest_text` - NO duplicate checking
  - `ingest_file` - NO duplicate checking
  - `ingest_directory` - NO duplicate checking
  - `ingest_url` - HAS duplicate checking (but faulty)
- **User Quote:** "Ingests are ingests. They should have identical behavior. Identical behavior."
- **Status:** IDENTIFIED - needs unified approach

### PROBLEM 4: LACK OF CENTRALIZED CRUD LOGIC
- **What:** Each ingest method has different implementation instead of unified path
- **User Quote:** "From the point you get content to ingest, every single CRUD operation should be identical logic"
- **Impact:** Inconsistent behavior, harder to maintain, more bugs
- **Status:** IDENTIFIED - need to centralize

### PROBLEM 5: ORPHANED DOCUMENT 107
- **What:** Document created during interrupted graph extraction, blocked re-ingestion
- **Timeline:**
  - 12:51:40 - Ingest started, created doc 107
  - 12:51:48 - Doc 107 ingested into RAG (8 chunks)
  - 12:52:39 - Server restarted (graph extraction interrupted, doc 107 orphaned)
  - 12:52:40 - ChatGPT tried to ingest, duplicate check found doc 107, ERROR
- **Impact:** Interrupted ingestions leave orphaned documents that block re-ingestion
- **Status:** CLEANED UP (via collection delete) - but underlying issue remains

### PROBLEM 6: MCP SERVER LIFECYCLE INTERRUPTS LONG-RUNNING OPERATIONS
- **What:** MCP server restarts/shuts down for every tool call, interrupting operations > ~60 seconds
- **Pattern:**
  - Server starts up on tool call
  - Tool executes
  - Server shuts down when tool completes
  - If tool takes > ~60 seconds, server restarts mid-operation
- **Evidence:**
  - Doc 114: Graph extraction started 13:40:24, server restarted 13:41:17 (53 seconds later)
  - Graph extraction completed in 62.5 seconds total (interrupted halfway)
  - Left orphaned document (RAG complete, graph incomplete)
- **Impact:**
  - Graph extraction operations routinely take 30-60+ seconds
  - Server lifecycle can't handle this duration
  - Creates orphaned documents
  - Triggers duplicate check errors on retry
- **Root Cause:** Unknown - could be:
  - FastMCP framework behavior
  - Docker/uvicorn timeout settings
  - MCP client timeout
  - Something in our lifespan implementation
- **Status:** IDENTIFIED - needs investigation of MCP server/FastMCP lifecycle

---

## Current Status

**Time:** ~1:45 PM
**State:** ChatGPT test completed, discovered CRITICAL MCP server behavior issue

## CRITICAL DISCOVERY: MCP Server Lifecycle Pattern

**Pattern Observed:** MCP server **restarts for EVERY tool call**

### Evidence from Logs:

**Every tool call follows this pattern:**

1. **Tool call arrives:**
   ```
   INFO: "POST /messages/?session_id=... HTTP/1.1" 202 Accepted
   ```

2. **Server INITIALIZES (fresh start):**
   ```
   2025-11-01 13:34:17,460 - __main__ - INFO - Initializing RAG components...
   2025-11-01 13:34:17,463 - src.core.database - INFO - Database initialized with connection string
   2025-11-01 13:34:17,538 - src.core.embeddings - INFO - EmbeddingGenerator initialized...
   2025-11-01 13:34:17,593 - src.core.database - INFO - Database connection established
   ...
   2025-11-01 13:34:31,438 - __main__ - INFO - All startup validations passed - server ready ✓
   ```

3. **Tool executes:**
   ```
   2025-11-01 13:34:31,805 - mcp.server.lowlevel.server - INFO - Processing request of type CallToolRequest
   ```

4. **Server SHUTS DOWN (after tool completes):**
   ```
   2025-11-01 13:34:34,535 - __main__ - INFO - Shutting down MCP server...
   2025-11-01 13:34:34,535 - src.core.database - INFO - Database connection closed
   ```

**This happens for EVERY SINGLE TOOL CALL.**

### Impact on ChatGPT Test

**Timeline with Server Lifecycle Context:**

1. **13:34:18** - ChatGPT calls `create_collection`
   - Server starts up
   - Collection created (ID 11)
   - **Server shuts down**

2. **13:34:31** - ChatGPT calls `analyze_website`
   - Server starts up (NEW process)
   - Analysis completes
   - **Server shuts down**

3. **13:40:17** - ChatGPT calls `ingest_url` (first attempt)
   - Server starts up (NEW process)
   - Crawl completes (1 page successful, 4 failed with "memory pressure")
   - RAG ingestion completes: doc 114 created
   - Graph extraction starts at 13:40:24
   - **Server NEVER COMPLETES SHUTDOWN - graph extraction still running**

4. **13:41:17** - Server RESTARTS (60 seconds later)
   - **Graph extraction was INTERRUPTED mid-process**
   - Doc 114 left orphaned (RAG complete, graph incomplete)

5. **13:41:19** - ChatGPT retries `ingest_url` (mode='crawl')
   - Server starts up (NEW process)
   - Duplicate check FINDS orphaned doc 114
   - ERROR: "URL already crawled"
   - **Server shuts down**

6. **13:41:23** - ChatGPT retries with `mode='recrawl'`
   - Server starts up (NEW process)
   - Deletes old docs 114
   - Re-crawls (3 pages successful this time)
   - Completes successfully

### Root Cause Analysis

**PROBLEM: Long-running graph extraction causes server lifecycle issue**

- Graph extraction took **62.5 seconds** (normal is 30-60 seconds)
- Server restart/shutdown mechanism can't handle operations > ~60 seconds
- This is NOT about container memory or Docker
- This is about **MCP server lifecycle management**

**Why this never happened in local testing:**
- Integration tests complete quickly (< 60 seconds total)
- Never hit the lifecycle timeout/restart threshold

**Why it happens in Docker:**
- Same lifecycle issue exists
- Just more visible because we're monitoring logs continuously

---

## DEEP ANALYSIS: ingest_url Duplicate Check Logic (2025-11-01)

### Current State of Database (Verified)

**Total Documents:** 14 documents in source_documents table
- 10 from test-project-docs (IDs 93-102, no crawl metadata)
- 4 from test_docker_crawl (IDs 117-120, crawl_root_url = https://python.org/about)

**Collections:**
- test_docker_crawl: 4 documents, 21 chunks
- test-project-docs: 10 documents, 36 chunks
- anthropic-mcp-docs: 0 documents, 0 chunks
- mcp-docs-test: 0 documents, 0 chunks

**Critical Observation:** Documents 117-120 have TWO DIFFERENT crawl_session_ids:
- Doc 117: a8a21957-17a2-4b26-83c6-048288ae5b16
- Doc 118: f7080a54-f061-45a3-aaa8-1b5a06c11b84
- Docs 119-120: a8a21957-17a2-4b26-83c6-048288ae5b16

This proves multiple crawl sessions happened for the same crawl_root_url.

### The Duplicate Check Logic (src/mcp/tools.py:924-973)

**Function:** `check_existing_crawl(db, url, collection_name)`

**Query:**
```sql
SELECT
    sd.metadata->>'crawl_session_id' as session_id,
    sd.metadata->>'crawl_timestamp' as timestamp,
    COUNT(DISTINCT sd.id) as page_count,
    COUNT(DISTINCT dc.id) as chunk_count
FROM source_documents sd
JOIN document_chunks dc ON dc.source_document_id = sd.id
JOIN chunk_collections cc ON cc.chunk_id = dc.id
JOIN collections c ON c.id = cc.collection_id
WHERE sd.metadata->>'crawl_root_url' = %s
  AND c.name = %s
GROUP BY sd.metadata->>'crawl_session_id', sd.metadata->>'crawl_timestamp'
ORDER BY sd.metadata->>'crawl_timestamp' DESC
LIMIT 1
```

**What This Does:**
1. Finds documents where `metadata->>'crawl_root_url'` matches the URL parameter
2. Filters by collection name
3. Groups by crawl session and timestamp
4. Returns the MOST RECENT crawl session for that URL + collection combo
5. Returns session_id, timestamp, page_count, chunk_count

**Return Value:**
- Returns dict with crawl info if found
- Returns None if not found

### How ingest_url Uses This Check (src/mcp/tools.py:1065-1074)

```python
# Check for existing crawl
existing_crawl = check_existing_crawl(db, url, collection_name)

if mode == "crawl" and existing_crawl:
    raise ValueError(
        f"URL '{url}' has already been crawled into collection '{collection_name}'.\n"
        f"Existing crawl: {existing_crawl['page_count']} pages, "
        f"{existing_crawl['chunk_count']} chunks, "
        f"timestamp: {existing_crawl['crawl_timestamp']}\n"
        f"To update existing content, use mode='recrawl'."
    )
```

**Behavior:**
- `mode="crawl"` + existing_crawl found = ERROR (prevents duplicate)
- `mode="recrawl"` + existing_crawl found = DELETE old docs, then proceed
- `mode="crawl"` + NO existing_crawl = Proceed normally

### The Recrawl Deletion Logic (src/mcp/tools.py:1076-1117)

**When:** `mode == "recrawl" and existing_crawl`

**Steps:**
1. Find ALL documents with matching `crawl_root_url` (NOT filtered by collection!)
   ```python
   cur.execute(
       """
       SELECT id, filename
       FROM source_documents
       WHERE metadata->>'crawl_root_url' = %s
       """,
       (url,),  # NOTE: NO collection filter here!
   )
   ```

2. Delete Graph episodes for each document
3. Delete document_chunks for each document
4. Delete source_documents for each document

**CRITICAL BUG #1: Recrawl Deletes Across ALL Collections**

The deletion query does NOT filter by collection_name. It deletes ALL documents with that crawl_root_url from the ENTIRE database, regardless of which collection they're in.

**Example Scenario:**
1. User crawls `https://python.org/about` into collection "python-docs-v1"
2. User crawls `https://python.org/about` into collection "python-docs-v2" (different collection!)
3. User runs recrawl on "python-docs-v1"
4. **BUG:** Deletes docs from BOTH collections because deletion doesn't filter by collection

### User Complaint: "You can't prevent me from deciding I want to crawl the same website for a different collection"

**User's Point:** The duplicate check should allow same URL in DIFFERENT collections.

**Current Behavior:**
- Duplicate check DOES scope by collection (line 953: `AND c.name = %s`)
- So duplicate check CORRECTLY allows same URL in different collections ✓

**BUT:** Recrawl deletion is BROKEN - it deletes across all collections ✗

### CRITICAL BUG #2: Inconsistent Duplicate Checking Across Ingest Methods

**ingest_url:** HAS duplicate checking via `check_existing_crawl()`
**ingest_text:** NO duplicate checking at all
**ingest_file:** NO duplicate checking at all
**ingest_directory:** NO duplicate checking at all

**User Quote:** "Ingests are ingests. They should have identical behavior. Identical behavior."

**Problem:** Only `ingest_url` prevents duplicates. Other methods freely create duplicates.

### Why This Matters for ChatGPT Test

**Timeline Analysis:**

1. **13:40:17 - First ingest_url call (mode='crawl')**
   - Database was EMPTY (verified by user)
   - `check_existing_crawl()` returned None (no existing crawl)
   - Proceeded to crawl and ingest
   - Created doc 114 in RAG
   - Started graph extraction

2. **13:41:17 - Server restarted (interrupted graph extraction)**
   - Doc 114 exists in RAG, but graph incomplete
   - Doc 114 is now "orphaned" (RAG complete, graph incomplete)

3. **13:41:19 - Second ingest_url call (mode='crawl', retry)**
   - `check_existing_crawl()` finds doc 114 (created 1 minute ago)
   - Returns existing_crawl info
   - Raises ValueError: "URL already crawled"
   - ERROR blocks retry

4. **13:41:23 - Third ingest_url call (mode='recrawl')**
   - `check_existing_crawl()` finds doc 114
   - Deletion logic runs
   - Deletes doc 114 from database
   - Re-crawls successfully

**Why duplicate check triggered:** Doc 114 was created during the FIRST call, so the SECOND call found it via `check_existing_crawl()`.

### Root Cause Summary

**Problem 1: Recrawl deletion is not collection-scoped**
- Deletes ALL docs with matching crawl_root_url across entire database
- Should delete ONLY docs in the specified collection
- Breaks legitimate use case: same URL in different collections

**Problem 2: Duplicate check is inconsistent**
- Only `ingest_url` has duplicate prevention
- `ingest_text`, `ingest_file`, `ingest_directory` don't check for duplicates
- No centralized CRUD logic

**Problem 3: Server lifecycle interrupts long operations**
- Graph extraction takes 30-60+ seconds
- Server restarts after ~60 seconds
- Creates orphaned documents (RAG complete, graph incomplete)
- Orphaned docs trigger duplicate check on retry

### Proposed Fixes (For Discussion)

**Fix 1: Add collection filter to recrawl deletion**
```python
# Current (WRONG - deletes across all collections):
cur.execute(
    """
    SELECT id, filename
    FROM source_documents
    WHERE metadata->>'crawl_root_url' = %s
    """,
    (url,),
)

# Fixed (deletes only in specified collection):
cur.execute(
    """
    SELECT DISTINCT sd.id, sd.filename
    FROM source_documents sd
    JOIN document_chunks dc ON dc.source_document_id = sd.id
    JOIN chunk_collections cc ON cc.chunk_id = dc.id
    JOIN collections c ON c.id = cc.collection_id
    WHERE sd.metadata->>'crawl_root_url' = %s
      AND c.name = %s
    """,
    (url, collection_name),
)
```

**Fix 2: Implement consistent duplicate checking (Future Work)**
- Create centralized function to check for duplicate content
- Apply to all ingest methods (text, file, directory, url)
- Use content hash or title+metadata for detection
- For URLs: use crawl_root_url + collection_name (current behavior)

**Fix 3: Address server lifecycle issue (Separate Investigation)**
- Investigate why server restarts after ~60 seconds
- Possible causes: FastMCP, Docker, uvicorn timeout, MCP client timeout
- May need async job queue for long-running operations

---

## Pending Tasks

1. ~~Monitor MCP server logs during ChatGPT test~~ (COMPLETED)
2. Fix recrawl deletion to be collection-scoped (ANALYSIS COMPLETE - awaiting approval)
3. Implement consistent duplicate checking across all ingest methods (FUTURE WORK)
4. Centralize CRUD logic for all ingest operations (FUTURE WORK)
5. ~~Investigate collection document count discrepancy bug~~ (FIXED - was counting chunks)
6. Handle orphaned documents from interrupted ingestions (Requires server lifecycle fix)
7. Investigate MCP server lifecycle timeout issue (NEW - CRITICAL)

---

## Key User Feedback

- "Stop moving so fucking fast" - override prime directive to slow down
- "Process of deduction. What does it mean?"
- "One variable at a time"
- "Until you run a successful ingest URL with follow links... You are not done"
- "Ingests are ingests. They should have identical behavior."
- "From the point you get content to ingest, every single CRUD operation should be identical logic"
- "As we go, you need to note and keep tabs and keep track of the problems you see"
- "Facts matter a lot. You get one of those facts wrong and you'll go down a rabbit hole all day long"
