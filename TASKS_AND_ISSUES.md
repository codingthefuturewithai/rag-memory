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

**Context:** Forked Crawl4AI repo to fix bugs that were blocking RAG Memory development

**Current state:** Maintaining our own fork with patches for known bugs

**Known issues:** Crawl4AI team aware of these bugs for months but hasn't fixed them

**Required action:**
- Submit our patches upstream to Crawl4AI project for their consideration/incorporation
- Goal: Get fixes merged into official repo so we can eliminate the fork dependency

**Benefit:** Reduce maintenance burden of maintaining our own fork long-term

---

## Issue 9: CRITICAL - Knowledge Graph Extraction Only Returns Document-to-Document Links

**Severity:** CRITICAL - Knowledge graph queries are completely useless as currently implemented

**Problem:** Graphiti entity extraction is only capturing document-level relationships, not semantic entities within documents

**Current behavior:**
- Relationship queries return: "Document A links to Document B"
- Temporal queries return: "Document X was updated at time Y"
- No extraction of actual semantic entities (Python, setup, API, library, etc.)
- No extraction of actual relationships between concepts (Python USES standard_library, REQUIRES setup, etc.)

**What should happen:**
- Extract semantic entities from document content (nouns, concepts, topics)
- Build relationships between those entities across all documents in collection
- Support queries like: "What does Python require?" or "What libraries are part of Python?"
- Timeline should track entity evolution, not document updates

**Test evidence:** (2025-11-02 13:21:19)
- Crawled 5 pages about Python documentation
- Ingested 3 documents with 23 chunks
- Relationship query for "How does Python documentation relate to Python programming?" returned only document link relationships
- Temporal query returned document timestamps, not entity evolution

**Root cause:** Graphiti's extraction logic (in UnifiedIngestionMediator) is not properly configured to extract semantic entities from ingested documents

**Investigation needed:**
- How is Graphiti configured for entity extraction?
- What prompt/instructions are given to LLM for entity identification?
- Are entities being extracted but then filtered out?
- Is the issue in extraction or in query execution?

**Impact:** Knowledge graph feature is non-functional for actual use cases - clients cannot query relationships between entities/concepts, only between documents

**Fix priority:** HIGH - This is a core feature that's broken

---

## Issue 10: Web Page Content Filtering to Reduce Navigation Noise in Knowledge Graph

**Severity:** HIGH - Knowledge graph quality degradation for web crawls

**Problem:** Web pages ingested via crawlers produce excessive document-to-document relationships instead of semantic entity relationships. Navigation bars, sidebars, headers, and footers appear on every page, creating artificial link graphs where every page connects to the same navigation targets.

**Evidence:**
- Tested: 5 Python documentation pages
- Result: Relationship queries returned only "Document A links to Document B" patterns
- Compared: Same knowledge graph extraction on local project documentation files works correctly, returns semantic entities and relationships

**Root Cause:** Crawl4AI converts web pages to markdown that includes navigation elements (links, breadcrumbs, sidebars). When passed to Graphiti's LLM extraction, these structural elements bias the LLM toward extracting document relationships instead of semantic content.

**Tested Solutions:**

### Available in Crawl4AI (Our Fork)

1. **PruningContentFilter**
   - Algorithm: Text density + link density scoring with tag importance weights
   - Cost: FREE (no API calls)
   - Quality: High (~80-85% noise reduction)
   - Robustness: Production-proven, works across 95%+ of websites
   - Implementation: `from crawl4ai.content_filter_strategy import PruningContentFilter`

2. **BM25ContentFilter**
   - Algorithm: BM25 ranking (used by Elasticsearch) with stemming and priority tag weights
   - Cost: FREE (no API calls)
   - Quality: High (slightly better than pruning, semantic ranking)
   - Robustness: Production-proven, works across 95%+ of websites
   - Implementation: `from crawl4ai.content_filter_strategy import BM25ContentFilter`

3. **LLMContentFilter**
   - Algorithm: LLM passes each HTML chunk through instruction to generate clean markdown
   - Cost: PAID (~$0.01-0.05 per page with gpt-4o-mini)
   - Quality: Very High (~95%+ noise reduction, semantic understanding)
   - Robustness: Most robust across diverse website structures
   - Implementation: `from crawl4ai.content_filter_strategy import LLMContentFilter`
   - Caching: Uses `~/.cache/llm_cache/content_filter/` to avoid re-processing
   - **IMPORTANT:** User-configurable only (optional flag)

### NOT Recommended

- **Excluding "Document" entity type from Graphiti:** Unreliable - webpages legitimately discuss documents (PDFs, specs, etc.), would lose real semantic content. Parameter exists but extraction behavior not verified.

---

## RECOMMENDED IMPLEMENTATION (Rank-Ordered)

### Phase 1 (Immediate - Breaking Change OK, No Users Yet)

1. **Enable PruningContentFilter by default in web_crawler.py**
   ```python
   from crawl4ai.content_filter_strategy import PruningContentFilter

   # In WebCrawler.__init__:
   self.content_filter = PruningContentFilter(
       threshold_type="dynamic",
       threshold=0.48
   )

   # In crawl_page():
   result = await crawler.arun(
       url=url,
       config=self.crawler_config,
       content_filter=self.content_filter  # NEW
   )
   ```

2. **Change markdown source from raw_markdown to cleaned markdown**
   - Current: `content = result.markdown.raw_markdown`
   - Proposed: `content = result.markdown.markdown_with_citations` (filtered output)

3. **Add aggressive excluded_tags**
   ```python
   excluded_tags=[
       "nav", "footer", "header", "aside",
       "form", "iframe", "script", "style",
       "noscript", "meta", "link"
   ]
   ```

4. **Mark web crawl episodes with metadata**
   - Add `"filtered": True` to metadata sent to Graphiti
   - Add `"content_type": "article_body"` to distinguish from document structure

**Expected result:** ~80-85% reduction in spurious document-to-document relationships

### Phase 2 (Optional Enhancement - User-Configurable)

1. **Add LLMContentFilter as optional feature**
   ```python
   crawl_config = CrawlerRunConfig(
       use_llm_content_filter=False,  # Default: off to avoid API costs
       llm_provider="openai",
       llm_model="gpt-4o-mini"
   )
   ```

2. **Document API cost implications**
   - Estimate: ~$0.01-0.05 per page
   - Users must opt-in explicitly

3. **Implement with caching**
   - Graphiti's LLMContentFilter already has caching built-in
   - Repeated crawls of same URL use cached result

---

## Implementation Files to Modify

1. `/src/ingestion/web_crawler.py`
   - Import PruningContentFilter
   - Initialize in __init__()
   - Pass to crawler.arun()
   - Change markdown source

2. `/src/unified/mediator.py`
   - Add metadata marking for web crawls (filtered=True)

3. Documentation/README
   - Explain content filtering behavior
   - Document API cost implications if LLMContentFilter enabled

---

## Testing Plan

After implementation:

1. **Re-run crawl test with Python documentation**
   - Verify relationship queries return semantic entities, not document links
   - Expected: "User Service USES_DATABASE PostgreSQL" pattern (like project docs)
   - Not: "Document A LINKS_TO Document B" pattern

2. **Verify no breaking changes**
   - Ensure document-level chunks still stored correctly
   - Verify similarity search still works
   - Confirm RAG retrieval unaffected

3. **Quality metrics**
   - Entity-to-entity relationship ratio vs document-to-document
   - Count average relationships per extracted entity (should increase)
   - Knowledge graph clustering coefficient (should improve)

---

## Timeline & Risk

**Risk Level:** MEDIUM
- Breaking change but no users affected
- PruningContentFilter is production-proven
- Can roll back by removing filter if needed

**Timeline:**
- Phase 1 implementation: 1-2 hours
- Testing and validation: 1 hour
- Phase 2 (optional): 1-2 hours (much later)

---

## References

- Crawl4AI fork location: `/crawl4ai-fork/crawl4ai/content_filter_strategy.py` (775 lines)
- Research findings: Web scraping content filtering is well-solved problem
- Production examples: Elasticsearch (BM25), Readability.js (Arc90 algorithm)
- Graphiti: Production-ready, supports all filtering approaches
- Cost estimate: gpt-4o-mini = $0.15 per 1M input tokens (~$0.01-0.05 per page)
