# RAG Memory - Tasks and Issues

## Issue 1: Re-examine ingest MCP tool deduplication approach

**Current assumption:** Deduplication checks are necessary to prevent duplicate documents

**Question to reflect on:** Is deduplication the right approach at all?

**Key insight:** Re-ingesting a document with the same title/URL but different content is actually a different document, not a duplicate

**Available safeguards already in place:**
- Tools exist for clients to discover documents in a collection (list_documents, search_documents)
- Documentation and guidance available to clients
- Warnings about long ingest times and retry behavior

**Proposed direction:** Instead of trying to prevent duplicates for clients, provide clear guidance and let them manage it:
- Document the ingest behavior clearly in MCP server instructions and tool docstrings
- Warn clients: "Ingests take a long time - don't retry the same call for several minutes"
- Trust clients to use available tools and guidance to check for existing documents before ingesting
- Accept that if they re-ingest with same metadata but different content, it's actually a new version of the document

---

## Issue 2: Standardize document handling across all ingest tools

**Problem:** Ingest tool flows are inconsistent - different tools have different logic paths and handling

**Example:** One ingest tool has deduplication logic while others don't (or they do it differently)

**Current state:** Document handling varies depending on the source (URL, text, file)

**Required approach:**
- Centralize all source-specific logic (URL fetching, file reading, text parsing)
- Once a document is obtained (regardless of source), it enters a single, unified code path
- All documents follow identical logic: same rules, same validation, same processing
- Philosophy: "A document is a document is a document" - source doesn't matter once content is available
- Any shared logic (deduplication, chunking, embedding, storage) must be identical across all sources

**Goal:** Single source of truth for document processing logic, no exceptions

**Testing benefit:** Centralizing logic also simplifies and strengthens testing - can test/isolate ingest logic in one place with confidence instead of running the same logic tests across multiple ingest tool permutations

**Documentation update:** After implementation, carefully update MCP server instructions and docstrings for all affected ingest tools to reflect new unified behavior

---

## Issue 3: Improve test coverage for critical ingest and search logic

**Problem:** Despite having hundreds of tests, coverage of critical ingest/search logic is extremely poor

**Discovery:** Many bugs and inconsistencies found only after implementation, not caught by existing tests
- Example: One ingest tool had deduplication logic while others didn't (discovered during implementation, not testing)

**Root cause:** Tests don't cover critical flows, rules, and behavior - they exist but don't validate what matters

**Required approach:**
- Tool-by-tool analysis: Carefully examine each ingest tool's critical flows, critical rules, critical behaviors
- For each tool, identify: What must work correctly? What are the edge cases? What are the invariants?
- Build solid automated test coverage: Ensure all critical paths are tested, not just happy paths
- Same rigor for: Ingest tools, search logic, and other complex features

**Goal:** Catch bugs and inconsistencies during testing, not during implementation

---

## Issue 4: Clean up codebase artifacts and .gitignore

**Problem:** Temporary artifacts left in repository (crawl4ai-fork, dashlocal, etc.) are being ignored via .gitignore instead of being removed

**Current state:** .gitignore contains entries for temporary/experimental artifacts that shouldn't be there

**Required approach:**
- Identify and remove all unnecessary artifacts (crawl4ai-fork, dashlocal, etc.)
- Clean up .gitignore to remove entries for deleted artifacts
- Keep .gitignore focused on actual project needs (dependencies, configs, secrets, etc.)

**Goal:** Clean, minimal repository without temporary experiments cluttering the codebase

---

## Issue 5: Update .reference directory and /getting-started command for current state

**Problem:** Recent changes mean documentation and getting-started guide may be out of sync with current codebase

**Current state:** .reference directory and /getting-started custom command need verification and updates

**Required approach:**
- Carefully analyze all .reference documentation files
- Verify accuracy against current codebase implementation
- Ensure /getting-started command (custom Claude Code command) reflects current setup process
- Validate that getting-started guide correctly educates users through entire flow:
  - Installation process
  - Configuration process
  - Initial setup

**Goal:** Documentation and guides are accurate, complete, and lead users through proper setup without gaps or outdated information

---

## Issue 6: Spin down cloud deployment to reduce costs

**Status:** MCP server, PostgreSQL, and Neo4j are currently deployed to cloud

**Action needed:** Temporarily spin down cloud resources (not in active use)

**Reason:** Reduce unnecessary cloud costs while not actively developing/testing in cloud environment

---

## Issue 7: Search for and clean up dead/unused code

**Task:** Identify and remove dead code, unused functions, unused imports, unused variables, etc.

**Goal:** Keep codebase clean and maintainable by removing code that serves no purpose

---

## Issue 8: Submit Crawl4AI bug fixes upstream

**Status:** OUTSTANDING - Not urgent (hygiene issue)

**Context:** Forked Crawl4AI repo to fix bugs that were blocking RAG Memory development

**Current state:** Maintaining our own fork with patches for known bugs

**Known issues:** Crawl4AI team aware of these bugs for months but hasn't fixed them

**Required action:**
- Submit our patches upstream to Crawl4AI project for their consideration/incorporation
- Goal: Get fixes merged into official repo so we can eliminate the fork dependency

**Benefit:** Reduce maintenance burden of maintaining our own fork long-term

---

## Issue 9: Knowledge Graph Extraction - Needs Testing to Confirm Fix

**Status:** LIKELY FIXED - Needs verification testing

**Original Problem:** Graphiti entity extraction was only capturing document-level relationships, not semantic entities within documents

**Suspected Fix:** Content filtering implemented in Issue 10 likely resolved this by removing navigation noise that was biasing LLM extraction

**Required Action:**
- Test with multiple documentation sites to verify semantic entity extraction is working correctly
- Verify relationship queries return entity-to-entity relationships (e.g., "Python USES standard_library")
- Verify temporal queries track entity evolution, not just document timestamps
- Compare results before/after content filtering to confirm improvement

**Success Criteria:**
- Relationship queries return semantic entities and their relationships
- Temporal queries show entity evolution over time
- Document-to-document relationships should be minimal or relevant only

---

## Issue 10: Web Page Content Filtering to Reduce Navigation Noise in Knowledge Graph

**Status:** ✅ COMPLETE - Tested and working to satisfaction

**Implementation Summary:**
- PruningContentFilter enabled by default in `web_crawler.py` (threshold=0.40, fixed mode)
- Aggressive excluded_tags configured (nav, footer, header, aside, etc.)
- Using `fit_markdown` for filtered content with fallback to `markdown_with_citations`
- All MCP tool documentation finalized and working as expected

**Note:** The `analyze_website` MCP tool is complete and working to satisfaction. MCP tool implementation, documentation, and client guidance are all finalized. No further changes needed.

**Remaining Task:** Test CLI command for `analyze_website` to verify output format

---

## Issue 11: Test analyze_website CLI Command

**Status:** NEW - Low priority

**Task:** Verify the CLI command `rag analyze <url>` returns proper output format

**Reason:** MCP tool has been tested and works. CLI wrapper hasn't been tested yet.

**Action:** Run a quick test with sample URL to verify CLI output is user-friendly
