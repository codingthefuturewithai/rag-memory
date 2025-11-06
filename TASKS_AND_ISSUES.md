# RAG Memory - Tasks and Issues

## Issue 1: Re-examine ingest MCP tool deduplication approach

**Status:** ✅ COMPLETE (merged 2025-11-06)

**Solution Implemented:**
- Automatic duplicate detection with clear error messages across all 4 ingest tools
- mode='ingest' (default): Error if duplicate exists, suggests mode='reingest'
- mode='reingest': Deletes old content completely, re-ingests fresh
- Centralized deletion logic with complete cleanup (graph + RAG)
- 24 comprehensive integration tests covering all duplicate/reingest scenarios
- 100% accurate documentation (server instructions + tool docstrings synchronized)

**Key Achievement:** Clients get helpful errors guiding them to the right solution, rather than silent failures or confusing behavior

---

## Issue 2: Standardize document handling across all ingest tools

**Status:** ✅ COMPLETE (merged 2025-11-06)

**Solution Implemented:**
- Centralized validate_mode() - single source of truth for mode validation (used by 4 tools)
- Centralized validate_collection_exists() - single source of truth for collection checks (used by 4 tools)
- Centralized read_file_with_metadata() - single source of truth for file reading (used by 2 tools)
- All 4 tools route through unified_mediator.ingest_text() for document processing
- Centralized delete_document_for_reingest() for complete cleanup
- Fixed absolute path handling for consistent duplicate detection

**Key Achievement:** Single source of truth for validation patterns - when we add features (mode='update', collection quotas, file encoding detection), we change ONE function instead of 4 separate implementations, eliminating risk of inconsistent updates

**Maintenance Benefit:** Reduced from 4 duplicate implementations to 1 centralized function per pattern

---

## Issue 3: Improve test coverage for critical ingest and search logic

**Status:** ✅ SIGNIFICANTLY IMPROVED for ingest tools (2025-11-06)

**Coverage Added:**
- 16 new comprehensive reingest tests (test_reingest_modes.py)
  - 4 tests per tool × 4 tools (ingest_text, ingest_file, ingest_directory, ingest_url)
  - Each tool tested for: duplicate detection, complete deletion, isolation, tool-specific scenarios
- 8 enhanced URL tests with complete deletion verification
- Total: 24 integration tests covering critical ingest/reingest flows

**Key Achievement:** Critical ingest patterns now have solid regression protection - duplicate detection bugs and centralization changes caught by automated tests before deployment

**Remaining Work:** Search logic, graph queries, and other complex features still need similar comprehensive coverage

---

## Issue 4: Clean up codebase artifacts and .gitignore

**Status:** ✅ COMPLETE (merged 2025-11-06)

**Solution Implemented:**
- Deleted crawl4ai-local/ directory (no longer needed)
- Project now uses crawl4ai-ctf>=0.7.6.post3 from PyPI
- Removed crawl4ai-local/ entry from .gitignore
- Repository is now clean and minimal

**Key Achievement:** Clean codebase without temporary experimental artifacts. All crawl4ai dependencies now managed through PyPI package.

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
