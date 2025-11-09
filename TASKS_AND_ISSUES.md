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

**Status:** READY TO START

**Problem:** Recent changes (Issues 1-4) mean documentation may be out of sync with current codebase

**Objective:** Verify and update all documentation to reflect current implementation

**Scope of Work:**

**Phase 1: Audit .reference/ Documentation**
Review each file for accuracy against current codebase:

1. **`.reference/OVERVIEW.md`**
   - Verify CLI commands match `src/cli/commands.py`
   - Check installation steps are current
   - Verify database setup instructions

2. **`.reference/MCP_QUICK_START.md`**
   - Verify all 17 MCP tools are documented
   - Check tool parameters match `src/mcp/server.py` docstrings
   - Verify examples still work

3. **`.reference/KNOWLEDGE_GRAPH.md`**
   - Verify graph query examples
   - Check Neo4j integration details

4. **`.reference/CLOUD_DEPLOYMENT.md`**
   - Verify Fly.io deployment steps
   - Check environment variable requirements

5. **`.reference/SEARCH_OPTIMIZATION.md`**
   - Verify similarity scores mentioned are accurate
   - Check optimization recommendations

6. **`.reference/PRICING.md`**
   - Verify cost estimates are current

**Phase 2: Test /getting-started Custom Command**
1. **Run the command:**
   ```bash
   # In Claude Code, execute:
   /getting-started
   ```

2. **Verify it covers:**
   - ✅ Installation: `uv tool install rag-memory` or local setup
   - ✅ Configuration: `.env` file setup, `config.yaml`
   - ✅ Docker setup: `docker-compose up -d` (auto-initializes databases)
   - ✅ Verification: `rag status`
   - ✅ First ingest: Example command

3. **Check for Issues:**
   - Missing steps?
   - Outdated commands?
   - Incorrect file paths?
   - Confusing explanations?

**Phase 3: Update as Needed**
1. Create branch: `docs/update-reference-docs`
2. Fix any inaccuracies found
3. Update `.claude/commands/getting-started.md` if needed
4. Test changes by running through setup process
5. Commit with clear descriptions of what was updated

**Deliverables:**
- All `.reference/` files verified accurate
- `/getting-started` command tested and updated if needed
- Any corrections committed to branch
- Issue marked ✅ COMPLETE

**Tools to Help:**
```bash
# Search for specific terms across .reference/
grep -r "term" .reference/

# Check if file paths mentioned actually exist
ls -la path/mentioned/in/docs

# Verify CLI commands work
rag --help
rag status
```

**Estimated Time:** 30-120 minutes (depends on how many issues found)

**Risk Level:** Low (documentation only, no code changes)

**Branch:** `docs/update-reference-docs`

**Documentation to Update When Complete:**
- Mark this issue as ✅ COMPLETE in TASKS_AND_ISSUES.md
- Document what was updated in commit messages

---

## Issue 6: Spin down cloud deployment to reduce costs

**Status:** READY TO START

**Context:** MCP server, PostgreSQL, and Neo4j are currently deployed to Fly.io

**Objective:** Temporarily spin down cloud resources to reduce costs while not in active use

**Prerequisites:**
- Fly.io CLI installed (`flyctl`)
- Authenticated to Fly.io account
- Access to cloud deployment configuration

**Actions:**

1. **Verify Current Deployment Status:**
   ```bash
   flyctl apps list
   flyctl status -a rag-memory-mcp
   ```

2. **Spin Down MCP Server:**
   ```bash
   flyctl scale count 0 -a rag-memory-mcp
   ```

3. **Verify Scale Down:**
   ```bash
   flyctl status -a rag-memory-mcp
   # Should show 0 instances running
   ```

4. **Document Current State:**
   - Update TASKS_AND_ISSUES.md to mark as ✅ COMPLETE
   - Note: "Cloud deployment scaled to 0. To restart: `flyctl scale count 1 -a rag-memory-mcp`"

**Branch Needed:** No - operational task, no code changes

**Notes:**
- Databases (PostgreSQL/Neo4j) are on Supabase/Neo4j Aura - handle separately if needed
- Fly.io scales to zero = no compute costs, minimal storage costs
- Can scale back up anytime with: `flyctl scale count 1 -a rag-memory-mcp`

**Estimated Time:** 5 minutes

**Risk Level:** Very low (can easily restart)

---

## Issue 7: Search for and clean up dead/unused code

**Status:** READY TO START

**Objective:** Identify and remove dead code, unused functions, unused imports, unused variables to keep codebase clean

**Prerequisites:**
- Install `vulture` (dead code detector): `uv pip install vulture`
- Install `autoflake` (unused imports remover): `uv pip install autoflake`

**Strategy:**

**Phase 1: Automated Detection**
1. **Run vulture to find dead code:**
   ```bash
   vulture src/ --min-confidence 80
   ```
   This will report:
   - Unused functions
   - Unused classes
   - Unused variables
   - Unused properties
   - Unused imports

2. **Run autoflake to find unused imports:**
   ```bash
   autoflake --check --remove-all-unused-imports --recursive src/
   ```

**Phase 2: Manual Review**
1. Review vulture output - **DO NOT blindly delete everything**
2. Common false positives to ignore:
   - MCP tool functions (may appear unused but are called by framework)
   - Functions decorated with `@mcp.tool()` - these ARE used
   - CLI command functions - these ARE used
   - Model fields (Pydantic) - these ARE used
   - `__init__` methods - these ARE used
3. Create list of genuinely unused code to remove

**Phase 3: Safe Removal**
1. Create branch: `cleanup/remove-dead-code`
2. Remove confirmed dead code in small, logical commits
3. After each removal:
   ```bash
   # Verify syntax
   python -m py_compile src/mcp/tools.py src/mcp/server.py

   # Run tests
   pytest tests/integration/mcp/test_reingest_modes.py tests/integration/mcp/test_ingest_url.py -v
   ```
4. If tests fail after removal, code wasn't actually dead - restore it

**Phase 4: Automated Import Cleanup**
```bash
# Remove unused imports automatically (safe)
autoflake --in-place --remove-all-unused-imports --recursive src/
```

**Important Warnings:**
- ⚠️ Do NOT remove functions decorated with `@mcp.tool()` even if vulture says unused
- ⚠️ Do NOT remove CLI command functions even if vulture says unused
- ⚠️ Do NOT remove Pydantic model fields even if vulture says unused
- ⚠️ Always run tests after each batch of deletions
- ⚠️ Commit frequently so you can rollback if needed

**Estimated Time:** 30-60 minutes

**Risk Level:** Medium (potential to break things if not careful)

**Documentation to Update When Complete:**
- Mark this issue as ✅ COMPLETE in TASKS_AND_ISSUES.md
- Document what was removed in commit messages

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

**Status:** READY TO START - Verification Testing

**Original Problem:** Graphiti entity extraction was only capturing document-level relationships, not semantic entities within documents

**Suspected Fix:** Content filtering (Issue 10) likely resolved this by removing navigation noise that biased LLM extraction

**Objective:** Verify knowledge graph now extracts semantic entities correctly

**Prerequisites:**
- Docker containers running (`docker-compose up -d`)
- Clean test collection (or create new one)

**Test Plan:**

**Phase 1: Ingest Test Content**
```bash
# Create test collection
# (Use MCP tool or CLI)

# Ingest small documentation site with clear semantic entities
# Example: Python standard library docs (clear concepts like "modules", "functions", "classes")
rag ingest https://docs.python.org/3/library/functools.html --collection test-kg --max-pages 5
```

**Phase 2: Verify Entity Extraction**
1. **Query for semantic entities:**
   - Expected: Entities like "functools", "decorator", "cache", "lru_cache", "partial"
   - NOT expected: Entities like "navigation", "menu", "header"

2. **Run relationship query (via MCP tool):**
   ```python
   # Use mcp__rag-memory__query_relationships
   query_relationships(
       query="What is functools and how does it relate to decorators?",
       collection_name="test-kg",
       num_results=10
   )
   ```

3. **Check results for:**
   - ✅ Entity-to-entity relationships (e.g., "functools CONTAINS lru_cache")
   - ✅ Concept relationships (e.g., "lru_cache IS_A decorator")
   - ❌ Document-to-document relationships should be minimal

**Phase 3: Verify Temporal Tracking**
1. **Ingest updated version of same content (simulate content change)**
2. **Run temporal query (via MCP tool):**
   ```python
   # Use mcp__rag-memory__query_temporal
   query_temporal(
       query="How has the functools module evolved?",
       collection_name="test-kg",
       num_results=10
   )
   ```

3. **Check results show:**
   - ✅ Entity evolution over time (not just document timestamps)
   - ✅ Superseded vs current facts

**Success Criteria:**
- ✅ Relationship queries return semantic entities (concepts, not just documents)
- ✅ Entity relationships make logical sense
- ✅ Temporal queries track concept evolution
- ✅ Minimal navigation/UI noise in extracted entities

**If Issues Found:**
- Document specific problems
- Create branch: `fix/knowledge-graph-extraction`
- Investigate Graphiti configuration in `src/graph/graph_store.py`
- May need to adjust entity extraction prompts or filtering

**If Everything Works:**
- Document confirmation with example queries
- Mark issue ✅ COMPLETE
- No code changes needed

**Estimated Time:** 20-30 minutes

**Risk Level:** Very low (read-only verification)

**Branch:** Only if fixes needed: `fix/knowledge-graph-extraction`

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

**Status:** READY TO START

**Objective:** Verify the CLI command `rag analyze <url>` works properly and produces user-friendly output

**Context:**
- The MCP tool `analyze_website()` has been tested and works correctly
- The CLI wrapper in `src/cli/commands.py` needs verification
- This is purely a verification test - NO code changes expected unless bugs are found

**Test Plan:**

1. **Prerequisites Check:**
   - Verify Docker containers are running: `docker-compose ps`
   - If not running: `docker-compose up -d`
   - Verify `rag` CLI is available: `which rag` or `rag --help`

2. **Run Test Command:**
   ```bash
   rag analyze https://docs.python.org/3/library/
   ```

3. **Acceptance Criteria - Verify Output Contains:**
   - ✅ Total URLs discovered (should be a number)
   - ✅ URL pattern statistics (grouped by path patterns)
   - ✅ Elapsed time in seconds
   - ✅ Clear, readable formatting (not raw JSON dumps)
   - ✅ Helpful summary/notes about the analysis
   - ✅ No Python tracebacks or error messages

4. **Expected Behavior:**
   - Command should complete in ~10-50 seconds (50 second timeout)
   - Should display progress or indication it's working
   - Output should be suitable for end users (not just developers)

5. **If Issues Found:**
   - Document specific problems (error messages, poor formatting, missing data)
   - Create branch: `fix/analyze-website-cli-output`
   - Fix issues in `src/cli/commands.py`
   - Test again
   - Follow standard git workflow (branch → commit → merge → delete branch)

6. **If Everything Works:**
   - Update this issue status to ✅ COMPLETE
   - Document confirmation: "Tested with [URL], output verified user-friendly"
   - No branch needed - just update TASKS_AND_ISSUES.md on main

**Estimated Time:** 5-10 minutes (assuming no bugs found)

**Risk Level:** Very low (read-only verification test)

**Documentation to Update When Complete:**
- Mark this issue as ✅ COMPLETE in TASKS_AND_ISSUES.md
- Optionally capture sample output in issue notes if you want reference
