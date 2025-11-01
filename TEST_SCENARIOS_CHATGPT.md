# RAG Memory - ChatGPT Test Scenarios

**Purpose:** Systematically test ingest_url duplicate checking and recrawl behavior with clean environment.

**Prerequisites:**
- Fresh rebuild of rag-memory-mcp-local container (includes latest code fixes)
- Fresh PostgreSQL and Neo4j volumes (completely empty databases)
- All containers healthy and running

---

## Test Scenario 1: Basic Single Collection Crawl

**Goal:** Verify normal crawl works without errors.

**Steps:**
1. Create collection "test-scenario-1" with description "Basic single collection test"
2. Analyze website: `https://python.org/about`
3. Ingest URL with `follow_links=True`, `max_pages=3`, provide analysis_token
4. Verify ingestion completes successfully

**Expected Result:**
- 1-3 documents created
- NO duplicate errors
- Graph extraction completes

**ChatGPT Prompt:**
```
Test Scenario 1: Basic single collection crawl

1. Create collection "test-scenario-1" with description "Basic single collection test"
2. Analyze https://python.org/about
3. Ingest that URL into the collection with follow_links=True, max_pages=3, using the analysis token
4. Report: How many documents were created? Any errors?
```

---

## Test Scenario 2: Same URL, Different Collections

**Goal:** Verify same URL can be crawled into multiple different collections.

**Steps:**
1. Create collection "test-scenario-2a" with description "First collection for same URL test"
2. Create collection "test-scenario-2b" with description "Second collection for same URL test"
3. Analyze website: `https://python.org/about` (reuse token if still valid)
4. Ingest URL into "test-scenario-2a" with `follow_links=True`, `max_pages=2`
5. Ingest SAME URL into "test-scenario-2b" with `follow_links=True`, `max_pages=2`

**Expected Result:**
- Both ingestions succeed
- NO duplicate errors (different collections should allow same URL)
- Each collection has its own documents

**ChatGPT Prompt:**
```
Test Scenario 2: Same URL in different collections

1. Create collection "test-scenario-2a" with description "First collection for same URL test"
2. Create collection "test-scenario-2b" with description "Second collection for same URL test"
3. Analyze https://python.org/about (or reuse token from Scenario 1 if still valid)
4. Ingest https://python.org/about into "test-scenario-2a" with follow_links=True, max_pages=2
5. Ingest https://python.org/about into "test-scenario-2b" with follow_links=True, max_pages=2
6. Report: Did both succeed? Any duplicate errors? How many docs in each collection?
```

---

## Test Scenario 3: Duplicate Crawl in Same Collection (Should Fail)

**Goal:** Verify duplicate prevention works within same collection.

**Steps:**
1. Use existing collection "test-scenario-2a" from previous test
2. Attempt to ingest `https://python.org/about` again into same collection (mode='crawl')

**Expected Result:**
- Should raise error: "URL already crawled into collection"
- Error should suggest using mode='recrawl'

**ChatGPT Prompt:**
```
Test Scenario 3: Duplicate crawl prevention

1. Attempt to ingest https://python.org/about into "test-scenario-2a" again (mode='crawl', follow_links=True, max_pages=2)
2. Report: Did it fail with duplicate error? What was the error message?
```

---

## Test Scenario 4: Recrawl Updates Existing Content

**Goal:** Verify recrawl mode properly replaces content in same collection.

**Steps:**
1. Use existing collection "test-scenario-2a"
2. Query how many documents currently exist
3. Ingest `https://python.org/about` with `mode='recrawl'`, `follow_links=True`, `max_pages=3`
4. Query how many documents exist after recrawl

**Expected Result:**
- Old documents deleted
- New documents created
- Final count may be different (3 pages instead of 2)
- NO documents leaked into "test-scenario-2b"

**ChatGPT Prompt:**
```
Test Scenario 4: Recrawl updates content

1. Check how many documents are in "test-scenario-2a" before recrawl
2. Check how many documents are in "test-scenario-2b" before recrawl (should be unchanged)
3. Ingest https://python.org/about into "test-scenario-2a" with mode='recrawl', follow_links=True, max_pages=3
4. Check document counts again for BOTH collections
5. Report: Did old docs get replaced? Are both collections still independent?
```

---

## Test Scenario 5: Retry After Interruption

**Goal:** Verify behavior if operation gets interrupted (simulating server restart).

**Steps:**
1. Create collection "test-scenario-5" with description "Interruption test"
2. Ingest `https://python.org/about` with `follow_links=True`, `max_pages=1`
3. Wait for completion
4. Immediately attempt same crawl again (mode='crawl')

**Expected Result:**
- First crawl succeeds
- Second attempt raises duplicate error
- Using mode='recrawl' on second attempt should work

**ChatGPT Prompt:**
```
Test Scenario 5: Retry after completion

1. Create collection "test-scenario-5" with description "Interruption test"
2. Ingest https://python.org/about with follow_links=True, max_pages=1
3. Wait for it to complete successfully
4. Immediately try the same crawl again (mode='crawl')
5. If it fails, try again with mode='recrawl'
6. Report: What happened on each attempt?
```

---

## Summary Questions for ChatGPT After All Tests

```
After completing all 5 test scenarios:

1. Did any scenario produce unexpected errors?
2. Did Scenario 2 succeed (same URL in different collections)?
3. Did Scenario 4 properly isolate collections during recrawl?
4. Were there any orphaned documents or duplicate issues?
5. What were the final document counts for each collection?
```

---

## Notes for Analysis

After ChatGPT completes these tests:

1. Check server logs for any errors or warnings
2. Verify database state matches expected document counts
3. Confirm no cross-collection contamination during recrawls
4. Check if graph extraction completed for all documents
5. Look for any orphaned documents in database

**Key metric:** All tests should pass cleanly with fresh environment. Any failures indicate real bugs vs environment corruption.
