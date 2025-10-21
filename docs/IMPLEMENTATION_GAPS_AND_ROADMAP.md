# Implementation Gaps & Roadmap

**Status:** Planning Document (Captured 2025-10-20)
**Purpose:** Track identified gaps, design issues, and future improvements
**Owner:** Development Team

---

## Overview

This document captures critical gaps and design considerations identified during documentation review. These items represent work needed to make RAG Memory production-ready and user-friendly across different deployment scenarios.

**Note:** This is a living planning document. Items should be analyzed, prioritized, and tackled incrementally.

---

## SECTION 1: Missing MCP Tools

### Gap 1.1: Delete Collection Tool NOT Exposed

**Current State:**
- Backend logic exists: `collection_mgr.delete_collection(name)`
- CLI support exists: `rag collection delete <name>`
- MCP Tool: **MISSING** ❌

**User Expectation:**
- AI agents should be able to delete collections just like they create them
- Consistency: If we expose `create_collection` and `update_collection_description`, users expect `delete_collection`

**Implementation Requirements:**

1. **Create MCP Tool:** `delete_collection`
   - Parameters: `collection_name` (required)
   - Returns: Confirmation (name, deleted_at, documents_affected)
   - Pre-conditions: Get user confirmation (critical)

2. **Safety Requirements:**
   - **STRONG WARNING in docstring:**
     ```
     ⚠️ WARNING: This operation cannot be undone
     ⚠️ All documents in this collection will be permanently deleted
     ⚠️ This includes all chunks and embeddings for these documents
     ⚠️ Before executing, ensure you have explicit permission from the user
     ⚠️ Present this warning to the user and get confirmation
     ⚠️ Deletion is irreversible
     ```
   - Recommendation: Add confirmation parameter or require two-step process
     - Step 1: `delete_collection(name, confirm=False)` - returns warning + docs_affected count
     - Step 2: `delete_collection(name, confirm=True)` - actually deletes

3. **Impact Analysis:**
   - Affected documents: How many will be deleted?
   - Affected chunks: How many chunks will be removed?
   - Knowledge graph cleanup: Must also delete episodes for these documents
   - Storage recovery: How much space will be freed?

4. **Implementation Steps:**
   1. Add `delete_collection_impl()` to `src/mcp/tools.py`
   2. Register tool with proper docstring warnings
   3. Test with various scenarios (empty collection, large collection, mixed collections)
   4. Update documentation with warnings
   5. Update getting-started guide

**Priority:** HIGH (completes the collection management tool set)

**Related Issues:**
- Tool count is 15, not 16 (documentation error)
- Once added, documentation updates needed

---

### Gap 1.2: Tool Count Discrepancy

**Current Documentation:** Claims 16 tools
**Actual Count (without delete_collection):** 15 tools
**After delete_collection addition:** 16 tools ✓

**Action:**
- Confirm actual tool count by scanning `src/mcp/tools.py`
- Update documentation once delete_collection is implemented
- Update all references (OVERVIEW.md, MCP_QUICK_START.md, getting-started.md)

---

## SECTION 2: Knowledge Graph Optionality & Architectural Issues

### Gap 2.1: Knowledge Graph Optionality is "Kludgy"

**Current Problem:**
Knowledge Graph is supposed to be optional, but the architecture doesn't cleanly support this.

**Specific Issues:**

1. **MCP Tools Exposure Problem**
   - `query_relationships` and `query_temporal` tools are exposed in MCP
   - These tools are USELESS if Neo4j is not available
   - Currently return `status: "unavailable"` with no real help to user
   - Question: Should we expose these tools at all if graph is optional?

2. **Silent Failures vs Loud Failures**
   - When user tries to use graph tools without Neo4j running, they get error
   - But other tools (ingest, search) should work fine
   - Need to verify: Do ingest operations fail if graph is down? ❌ They shouldn't
   - Current behavior: Unified mediator tries both RAG + Graph, logs error if Graph fails, continues
   - **Missing verification:** Are there any error paths that bubble up and fail the entire operation?

3. **Ingestion Behavior Inconsistency**
   - If graph unavailable: Does ingest still succeed? (Should be YES)
   - If graph unavailable: Is there any error message? (Should be SILENT)
   - If graph unavailable: Does user see any indication it tried? (Should be TRANSPARENT)

**Design Decision Needed:**

**Option A: Make Knowledge Graph Truly Optional & Hidden**
- Don't expose `query_relationships` and `query_temporal` tools if Neo4j unavailable
- Dynamically register tools based on what's available
- Make ingestion completely silent about graph availability
- User experience: If they don't set up Neo4j, they never see graph tools
- Implementation: Tool registration conditional on connection test at startup

**Option B: Make Knowledge Graph Mandatory (Simpler)**
- Document everything assuming both Postgres + Neo4j required
- No optionality complexity
- Docker Compose sets up both by default
- Simpler code, no conditional logic
- User experience: Clear setup: "You need both. Here's Docker Compose."
- This is probably the right call for MVP
- Can always make optional later if demand exists

**Option C: Support Both But With Clear Separation**
- Make it clear to users: "Graph is optional, here's how to use without it"
- Create separate documentation for each mode
- Require explicit environment variables to indicate graph availability
- Tool registration based on env vars

**Recommendation:** Option B initially
- Simpler, cleaner architecture
- Better user experience (fewer failure modes)
- Can revisit if users demand optional mode
- Reduces testing surface area

**Action Items:**

1. **Decide:** Which option for initial release?
2. **Verify:** All ingestion paths work without graph (no exceptions)
3. **Audit:** Check every MCP tool implementation
   - Does it assume graph exists?
   - Does it fail gracefully if graph unavailable?
   - Does it have error handling that blocks RAV operations?

4. **Code Changes (if Option A):**
   - Conditional tool registration in `src/mcp/server.py`
   - Startup health check for Neo4j
   - Dynamic capability negotiation

5. **Code Changes (if Option B):**
   - Update documentation to require both
   - Remove all "optional" language
   - Ensure setup guides assume both

---

### Gap 2.2: Installation & Setup Complexity

**Current Situation:**
Users installing from PyPI get only Python package, but need:
- PostgreSQL + pgvector (not just Python)
- Neo4j (if using graph)
- Initialize both databases
- Set environment variables

**Problem:**
This is a significant barrier for non-technical users.

**Potential Solutions:**

**Solution A: Docker Compose Everything**
- Provide `docker-compose.yml` that spins up everything
- Users who aren't familiar with Docker still have to learn it
- But it's simpler than setting up Postgres + Neo4j manually
- Works great for local development
- For production: Need separate guidance

**Solution B: Leverage Vendor MCP Servers** ⭐ (Referenced in mcp_servers_workflow.md)
- Fly.io can run MCP server
- Supabase can host PostgreSQL + initialize schema
- Neo4j Aura can host Neo4j
- Users create accounts, configure MCP servers from vendors
- Minimal local setup needed
- **Major advantage:** Scales to cloud-hosted AI agents automatically
- **Needs analysis:** How would this actually work? What's the flow?

**Solution C: Hybrid Approach** (Recommended initially)
1. Local development: Docker Compose (everything local)
2. Cloud deployment: Vendor MCP servers (Fly.io, Supabase, Neo4j Aura)
3. Documentation for both paths
4. Examples for common scenarios

**Current Documentation Gap:**
- Getting-started assumes local + Docker
- Doesn't mention Fly.io approach
- Doesn't mention vendor MCP servers
- Doesn't provide step-by-step cloud setup

**Action Items:**

1. **Evaluate:** Review `mcp_servers_workflow.md` for vendor MCP approach
2. **Analyze:** What are the actual steps for vendor MCP server setup?
3. **Decide:** What's the primary recommended path for users?
4. **Document:** Provide setup guides for all approaches
   - Local with Docker Compose
   - Cloud with Fly.io + Supabase + Neo4j Aura
   - Mixed scenarios
5. **Automate:** Create setup scripts that handle initialization
   - Docker Compose initialization
   - Database schema setup
   - Environment configuration

---

## SECTION 3: Knowledge Graph Synchronization Issues

### Gap 3.1: Delete Document → Graph Episodes Not Cleaned

**Current State:** ⚠️ CRITICAL BUG

**What Happens:**
```
1. User ingests document → Creates source_document, chunks, episode
2. User calls delete_document(doc_id) → Deletes source_document + chunks
3. Graph: Episode still exists (orphaned) ❌
```

**Root Cause:**
`delete_document()` MCP tool only deletes from RAG store, doesn't clean graph.

**Analysis Needed:** ✓ User has researched this

**User's Assessment (Correct):**
1. Everything is wrapped in an episode
2. Nodes can be linked to multiple episodes
3. Episode metadata contains document_id (verify this)
4. When episode is deleted, Graphiti should:
   - Delete the episode
   - Clean up nodes only if they have no other episodes
   - Keep nodes if linked to other episodes

**Implementation Plan:**

1. **Verify Graphiti Behavior:**
   - Does Graphiti API have `delete_episode(episode_id)` method?
   - When episode is deleted, does Graphiti automatically clean orphaned nodes?
   - Test with multi-episode nodes to verify behavior

2. **Update delete_document() Tool:**
   ```python
   async def delete_document_impl(document_id: int):
       # 1. Get document from RAG
       doc = get_document(document_id)

       # 2. Delete from Graph (if available)
       if graph_store_available:
           episode_name = f"doc_{document_id}"
           await graph_store.delete_episode(episode_name)
           # Graphiti handles node cleanup automatically

       # 3. Delete from RAG
       delete_from_rag(document_id)
   ```

3. **Update update_document() Tool:**
   ```python
   async def update_document_impl(document_id: int, content: str, ...):
       # 1. Get old episode from graph (for cleanup)
       old_episode = f"doc_{document_id}"

       # 2. Delete old episode from graph
       if graph_store_available:
           await graph_store.delete_episode(old_episode)

       # 3. Update in RAG (re-chunks, re-embeds)
       updated_id = update_rag(document_id, content, ...)

       # 4. Create new episode in graph with updated content
       if graph_store_available:
           await graph_store.add_knowledge(
               content=content,
               source_document_id=updated_id,
               # ...
           )
   ```

4. **Update recrawl() Tool:**
   ```python
   async def recrawl_impl(url: str, collection_name: str, ...):
       # 1. Find all documents with crawl_root_url == url
       old_docs = search_by_crawl_root(url)

       # 2. Delete episodes from graph
       if graph_store_available:
           for doc in old_docs:
               await graph_store.delete_episode(f"doc_{doc.id}")

       # 3. Delete documents from RAG
       for doc in old_docs:
           delete_from_rag(doc.id)

       # 4. Re-crawl and ingest
       ingest_url(url, collection_name, ...)
   ```

**Testing Requirements:**
- Test delete_document with single-episode nodes
- Test delete_document with multi-episode nodes
- Test update_document with multi-episode nodes
- Test recrawl with orphans verification
- Verify Graphiti cleanup actually happens

**Priority:** CRITICAL (data consistency issue)

---

### Gap 3.2: Update Document → Graph Episodes Not Synced

**Current State:** ⚠️ CRITICAL BUG

**What Happens:**
```
1. User ingests document → Creates episode with entities
2. User calls update_document(doc_id, new_content)
3. RAG: Chunks re-generated, re-embedded ✓
4. Graph: Old episode with old entities still exists ❌
```

**Impact:**
- Graph searches return outdated information
- Agent gets inconsistent information (old from graph, new from RAG)
- No way to know which is current

**Solution:** See Gap 3.1 implementation plan - `update_document_impl()` needs graph sync

**Priority:** CRITICAL (data consistency issue)

---

### Gap 3.3: Recrawl → Graph Episodes Not Cleaned

**Current State:** ⚠️ CRITICAL BUG

**What Happens:**
```
1. Initial crawl: Creates doc_290, doc_291, doc_292 (episodes + entities)
2. Recrawl: Deletes docs from RAG, re-crawls, creates doc_295, doc_296, doc_297
3. Graph: Has BOTH old (doc_290-292) AND new (doc_295-297) ❌
4. Result: Orphaned episodes accumulate with each recrawl
```

**Solution:** See Gap 3.1 implementation plan - `recrawl_impl()` needs graph cleanup

**Priority:** CRITICAL (data consistency issue, production blocker for web crawling)

---

## SECTION 4: Knowledge Graph Configuration

### Gap 4.1: GPT-5 Nano Model Support

**Current Situation:**
- Graphiti currently configured to use GPT-4o for entity extraction
- GPT-5 Nano is cheaper and potentially as good
- Need to verify: Does Graphiti support model configuration?

**Investigation Needed:**

1. **Graphiti Capabilities:**
   - Can we configure which LLM Graphiti uses?
   - What models does Graphiti support?
   - Has Graphiti been tested with GPT-5 Nano?
   - How much cheaper is Nano? (cost comparison)

2. **Performance Comparison:**
   - Entity extraction quality: GPT-4o vs Nano
   - Speed: GPT-4o vs Nano
   - Cost per document: GPT-4o vs Nano
   - Overall latency impact

3. **Configuration Options:**
   - Environment variable for model selection?
   - Configuration file setting?
   - Runtime parameter?

**Action Items:**

1. Research Graphiti documentation for model configuration
2. Test Nano model with sample documents
3. Compare quality/speed/cost with GPT-4o
4. If viable, add model configuration option
5. Update documentation with cost comparisons

**Potential Implementation:**
```python
# In GraphStore initialization
graphiti = Graphiti(
    uri=NEO4J_URI,
    user=NEO4J_USER,
    password=NEO4J_PASSWORD,
    llm_model=os.getenv("GRAPHITI_LLM_MODEL", "gpt-4o-turbo"),
    # or detect from env: gpt-5-nano, gpt-4o, etc.
)
```

**Priority:** MEDIUM (nice-to-have optimization, affects costs)

---

## SECTION 5: Documentation Gaps

### Gap 5.1: Episode Metadata Not Fully Documented

**Current Documentation:** Incomplete metadata documentation

**What's Missing:**
- What metadata is stored ON the episode node itself?
- How is it structured?
- What's searchable?
- What's indexed?

**Required Documentation:**

In KNOWLEDGE_GRAPH.md, add section: "Episode Metadata"

```markdown
### Episode Metadata

When a document is ingested, an episode is created with the following metadata:

**Episode Node Properties:**
- `name` (required) - Format: `doc_{source_document_id}`
- `description` (auto-generated) - Contains:
  - Collection name
  - Document title
  - Key concepts
  - Custom metadata
- `created_at` - Timestamp of ingestion
- `source_document_id` - Link to RAG document
- `metadata` (JSON) - Custom metadata from ingestion

**Searchable Fields:**
- Episode name, description, and metadata are searchable
- Entities linked to episode are searchable
- Relationships between entities are searchable

**Example:**
```json
{
  "name": "doc_42",
  "description": "Collection: tech-docs. Title: PostgreSQL Basics. Topics: database, search, indexing",
  "source_document_id": 42,
  "created_at": "2025-10-20T12:00:00Z",
  "metadata": {
    "collection": "tech-docs",
    "topic": "databases",
    "source": "crawl",
    "crawl_root_url": "https://docs.example.com"
  }
}
```

**Used For:**
- Linking to source document (for cleanup/updates)
- Associating metadata with entities
- Temporal tracking (when episode created/updated)
- Filtering searches by metadata
```

**Action:** Add to KNOWLEDGE_GRAPH.md, update MCP_QUICK_START.md

**Priority:** HIGH (needed for understanding graph operations)

---

### Gap 5.2: RAV Metadata Documentation Incomplete

**Current Documentation:** Partial, in OVERVIEW.md

**What's Missing:**
- Complete list of auto-generated metadata
- What's on source_documents vs document_chunks
- Web crawl metadata (crawl_root_url, session_id, depth, parent_url)
- How metadata is preserved through chunking
- How to filter by metadata

**Required Documentation:**

In OVERVIEW.md or separate doc, add: "Metadata Reference"

```markdown
### Metadata Storage & Structure

**Source Document Metadata** (source_documents table)
- `id` - Primary key
- `filename` - Original filename
- `file_type` - Extension (.txt, .md, .pdf, etc.)
- `file_size` - Size in bytes
- `metadata` (JSONB) - User-provided + auto-generated
  - User-provided: Any JSON passed at ingestion
  - Auto-generated:
    - `ingestion_date` - ISO 8601 timestamp
    - `source_type` - "text", "file", "url", "directory"
    - `title` - Document title (if provided)
    - For URLs: `crawl_root_url`, `crawl_session_id`, `crawl_timestamp`

**Document Chunk Metadata** (document_chunks table)
- `metadata` (JSONB) - Inherits from source + chunk-specific
  - Inherited from source document
  - Chunk-specific:
    - `chunk_index` - Position in document (0-based)
    - `char_start` - Character position in source
    - `char_end` - Character position in source
    - `chunk_size` - Size in characters

**Web Crawl Metadata** (special fields)
- `crawl_root_url` - Starting URL of crawl (used for recrawl targeting)
- `crawl_session_id` - UUID, unique per crawl session (tracks related pages)
- `crawl_timestamp` - ISO 8601, when page was crawled
- `crawl_depth` - Distance from root (0 = root, 1 = links from root, etc.)
- `parent_url` - URL of page that linked to this page (for depth > 0)

**Metadata Filtering:**
```bash
# Search with metadata filter
rag search "query" --metadata '{"topic":"databases"}'

# MCP tool with metadata filter
search_documents(
    query="PostgreSQL",
    metadata_filter={"topic": "databases"}
)
```

**Preserved Metadata:**
- When document is chunked, chunk inherits all source metadata
- Can filter searches by chunk metadata
- Can retrieve source metadata from chunk results
```

**Action:** Add metadata reference section to documentation

**Priority:** HIGH (needed for advanced users filtering)

---

## SECTION 6: Outstanding Architecture Questions

### Gap 6.1: Docker Compose Configuration Clarity

**Current State:** Confusion about how Neo4j Docker Compose fits into overall setup

**Issue:**
- Documentation mentions `docker-compose.graphiti.yml`
- But unclear how this relates to main `docker-compose.yml`
- Are there multiple YAML files? Which one to use?
- Is this a relic from earlier versions?

**Investigation Needed:**

1. **What YAML files exist?**
   - `docker-compose.yml` - Main stack?
   - `docker-compose.graphiti.yml` - Neo4j only?
   - `docker-compose.test.yml` - Test environment?
   - Others?

2. **What should we recommend?**
   - Single unified YAML with everything?
   - Separate YAMLs for different scenarios?
   - Compose profiles to enable/disable services?

3. **Recommended Structure:**
   ```yaml
   # docker-compose.yml (unified)
   services:
     postgres:
       image: pgvector/pgvector
       # ...
     neo4j:
       image: neo4j
       # ...
     # Optional: adminer for quick DB access
     adminer:
       image: adminer
       ports:
         - "8080:8080"

   # Usage:
   docker-compose up -d              # Start all services
   docker-compose down               # Stop all services
   docker-compose logs postgres      # View specific logs
   ```

4. **Or: Compose Profiles**
   ```yaml
   services:
     postgres:
       image: pgvector/pgvector
       profiles: ["core", "all"]
     neo4j:
       image: neo4j
       profiles: ["graph", "all"]

   # Usage:
   docker-compose --profile core up  # Just Postgres
   docker-compose --profile all up   # Everything
   ```

**Action Items:**

1. Audit existing Docker Compose files
2. Decide on unified vs modular approach
3. Create documented, clear setup
4. Update documentation accordingly

**Priority:** MEDIUM (setup quality, not blocking functionality)

---

### Gap 6.2: Phase Four Clarification Needed

**User's Question:** Where does "Phase 4" come from in documentation?

**Issue:**
- Documentation references "Phase 4" for knowledge graph cleanup
- Not clear if this is established project terminology
- Could be confusing to readers

**Action Items:**

1. **Clarify terminology:**
   - Is "Phase N" standard project terminology?
   - If so, document all phases clearly
   - If not, replace with "Planned Future Work" or similar

2. **Document explicitly:**
   - Phase 1: Core RAG (✓ Complete)
   - Phase 2: Graph queries (✓ Complete)
   - Phase 3: Extended ingestion (✓ Complete)
   - Phase 4: Graph sync cleanup (⏳ Planned)
   - Phase 5: [etc if any]

3. **Or: Remove Phase terminology**
   - Replace with: "Known Gaps" → "Planned Fixes"
   - Clearer for newcomers

**Priority:** LOW (documentation clarity, not blocking)

---

## SECTION 7: MCP Tool Audit Checklist

**Action:** Need to audit every MCP tool for knowledge graph assumptions

### Audit Requirements:

For each MCP tool, verify:

```
Tool: [name]
Location: src/mcp/tools.py line [X]

1. Does it assume Knowledge Graph exists? YES/NO
   If YES: How gracefully does it fail?

2. If graph unavailable, does it fail silently? YES/NO
   If NO: What's the error? Should it be silent?

3. Does it have graph sync logic? YES/NO
   If YES: Is it correct? Is it complete?
   If NO: Does it need it? (See Gap 3.1 - critical operations)

4. Does it use unified mediator? YES/NO
   If YES: Is mediator correctly handling failures?

5. Testing coverage? YES/NO
   - Test with graph available
   - Test with graph unavailable
   - Test with graph partially available (timeout, etc.)
```

### Tools to Audit:

- [ ] search_documents
- [ ] list_collections
- [ ] get_collection_info
- [ ] analyze_website
- [ ] list_documents
- [ ] get_document_by_id
- [ ] ingest_text ⚠️ CRITICAL (uses mediator)
- [ ] update_document ⚠️ CRITICAL (missing sync)
- [ ] delete_document ⚠️ CRITICAL (missing sync)
- [ ] create_collection
- [ ] update_collection_description
- [ ] delete_collection ❌ NOT YET IMPLEMENTED
- [ ] ingest_url ⚠️ CRITICAL (uses mediator)
- [ ] ingest_file ⚠️ CRITICAL (uses mediator)
- [ ] ingest_directory ⚠️ CRITICAL (uses mediator)
- [ ] recrawl_url ⚠️ CRITICAL (missing sync)
- [ ] query_relationships (graph-only)
- [ ] query_temporal (graph-only)

**Priority:** CRITICAL (ensure data consistency)

---

## SECTION 8: Related Planning Documents

### Gap 8.1: mcp_servers_workflow.md

**Referenced:** User mentioned this document
**Status:** Created by user with AI assistance
**Purpose:** Explore using vendor MCP servers for setup

**Action:** Review and evaluate this document
- Does it align with our architecture?
- Is the vendor MCP approach viable?
- What would be required to implement?
- Should this be part of recommended setup path?

**When:** After Gap 2.2 decisions are made

---

## SUMMARY TABLE

| Gap # | Category | Issue | Priority | Status |
|-------|----------|-------|----------|--------|
| 1.1 | Tools | delete_collection missing | HIGH | Not Started |
| 1.2 | Tools | Tool count discrepancy (15 vs 16) | HIGH | Documentation Error |
| 2.1 | Architecture | Graph optionality is complex | CRITICAL | Decision Needed |
| 2.2 | Installation | Setup too complex for non-technical users | HIGH | Decision Needed |
| 3.1 | Sync | delete_document → graph not cleaned | CRITICAL | Research ✓, Impl Needed |
| 3.2 | Sync | update_document → graph not synced | CRITICAL | Impl Needed |
| 3.3 | Sync | recrawl → graph orphans accumulate | CRITICAL | Impl Needed |
| 4.1 | Config | GPT-5 Nano model support | MEDIUM | Investigation Needed |
| 5.1 | Docs | Episode metadata not documented | HIGH | Doc Update Needed |
| 5.2 | Docs | RAG metadata incomplete | HIGH | Doc Update Needed |
| 6.1 | Architecture | Docker Compose clarity | MEDIUM | Audit Needed |
| 6.2 | Docs | Phase 4 terminology unclear | LOW | Clarification Needed |
| 7.0 | Audit | MCP tool graph assumptions | CRITICAL | Audit Needed |
| 8.1 | Planning | mcp_servers_workflow.md evaluation | HIGH | Review Needed |

---

## RECOMMENDED PRIORITY ORDER

### Phase A: Critical Blockers (Do First)

1. **Gap 3.1-3.3:** Fix delete/update/recrawl graph sync
   - Without this: Data inconsistency issues
   - Blocking: Production use of crawling
   - Effort: Medium (need Graphiti API validation)

2. **Gap 7.0:** Audit MCP tools for graph assumptions
   - Without this: Unknown failure modes
   - Blocking: Confident release
   - Effort: High (many tools to check)

3. **Gap 1.1:** Implement delete_collection tool
   - Without this: Incomplete API
   - Blocking: Parity with create/update
   - Effort: Low (straightforward implementation)

4. **Gap 2.1:** Decide Knowledge Graph optionality
   - Without this: Architecture unclear
   - Blocking: Setup documentation
   - Effort: Medium (decision + code changes if needed)

### Phase B: Important (Do Second)

5. **Gap 2.2:** Solve setup complexity
   - Choose path: Docker Compose vs Vendor MCP
   - Create setup automation
   - Effort: High (infrastructure + docs)

6. **Gap 5.1-5.2:** Complete metadata documentation
   - Without this: Users can't use filters
   - Effort: Low (documentation only)

7. **Gap 6.1:** Clarify Docker Compose files
   - Without this: Confusing setup
   - Effort: Medium (audit + refactor)

### Phase C: Nice-to-Have (Do Later)

8. **Gap 4.1:** GPT-5 Nano support
   - Cost optimization
   - Effort: Medium (investigation + implementation)

9. **Gap 6.2:** Phase terminology clarification
   - Documentation clarity
   - Effort: Low (terminology update)

10. **Gap 8.1:** Evaluate vendor MCP servers
    - Future architecture
    - Effort: High (new paradigm)

---

## NEXT STEPS

### Immediate (This Week)

1. ✅ Capture this document (DONE)
2. Create task list in GitHub or project management tool
3. Review and prioritize with team
4. Start with Phase A items

### Short Term (Next 2 Weeks)

1. Implement Gap 1.1 (delete_collection)
2. Audit MCP tools (Gap 7.0)
3. Fix graph sync issues (Gap 3.1-3.3)
4. Update documentation for fixes

### Medium Term (Next Month)

1. Solve Knowledge Graph optionality (Gap 2.1)
2. Improve setup process (Gap 2.2)
3. Complete metadata documentation (Gap 5.1-5.2)
4. Evaluate vendor MCP servers (Gap 8.1)

### Long Term (Next Quarter)

1. GPT-5 Nano support (Gap 4.1)
2. Docker Compose refactoring (Gap 6.1)
3. Additional architectural improvements

---

## Questions for User Feedback

1. **Gap 1.1:** Should delete_collection require confirmation? How to implement safely?
2. **Gap 2.1:** Should we commit to mandatory graph for now, or support optionality?
3. **Gap 2.2:** Which setup path should be primary recommendation?
4. **Gap 4.1:** Worth investigating GPT-5 Nano now or later?
5. **Gap 8.1:** Should we evaluate vendor MCP approach before finalizing architecture?

---

**Document Created:** 2025-10-20
**Status:** Planning (Ready for team review)
**Next Review:** After priority decisions made
