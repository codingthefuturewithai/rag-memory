# Web Crawling Feature - Planning Document

## Executive Summary

Based on research of Crawl4AI v0.7.4, RAG best practices, and the existing codebase, this document captures the finalized decisions for implementing web crawling functionality.

**Status**: ✅ All planning decisions finalized - ready to implement

**Decisions Made**:
1. ✅ Metadata Schema - Comprehensive schema with `crawl_root_url` for re-crawl tracking
2. ✅ Re-crawl Strategy - "Nuclear option" with `recrawl` command
3. ✅ Error Handling - Structured results (dataclasses), no CLI dependencies
4. ✅ Project Structure - Core/Ingestion/Retrieval domains with gradual migration

**Future Direction**: After core functionality is working, this will be exposed as either:
- FastAPI REST API, or
- MCP (Model Context Protocol) server with tools

This influences project structure and error handling design (need clean separation of business logic from CLI).

---

## ✅ FINALIZED DECISIONS

### 1. METADATA SCHEMA FOR WEB PAGES (DECIDED)

### Research Findings

From analyzing Firecrawl, Crawl4AI, and RAG best practices, the industry standard for web-scraped content includes:

**Essential Metadata (MUST HAVE)**:
- `source` - Full URL of the page (primary identifier)
- `title` - Page title (for display and relevance)
- `crawl_timestamp` - When the page was crawled (ISO 8601 format)
- `content_type` - Always "web_page" for scraped content
- `crawl_depth` - How many links deep from starting URL (0 = starting page)

**Highly Recommended**:
- `domain` - Extracted domain (e.g., "docs.python.org") for filtering
- `description` - Meta description tag content
- `content_length` - Character count of extracted markdown
- `crawler_version` - "crawl4ai-0.7.4" for troubleshooting
- `status_code` - HTTP status (200, 301, etc.)

**Optional but Useful**:
- `language` - Detected language code (en, es, etc.)
- `author` - If present in meta tags
- `keywords` - Meta keywords if present
- `canonical_url` - If different from source URL
- `crawl_session_id` - UUID to group pages from same crawl run

### ✅ FINAL DECISION: Comprehensive Metadata Schema

**Core metadata schema** (stored in `source_documents.metadata` JSONB field):

```python
{
    # PAGE IDENTITY
    "source": "https://docs.anthropic.com/en/api/agent-sdk/getting-started",  # Specific page URL
    "content_type": "web_page",

    # CRAWL CONTEXT (for re-crawl management - CRITICAL)
    "crawl_root_url": "https://docs.anthropic.com/en/api/agent-sdk/overview",  # Starting URL
    "crawl_timestamp": "2025-10-11T14:23:45Z",
    "crawl_session_id": "550e8400-e29b-41d4-a716-446655440000",
    "crawl_depth": 2,                    # Links deep from root

    # PAGE METADATA
    "title": "Getting Started with Agent SDK",
    "description": "Learn how to...",
    "domain": "docs.anthropic.com",

    # OPTIONAL BUT USEFUL
    "parent_url": "https://docs.anthropic.com/en/api/agent-sdk/overview",  # Page that linked here
    "language": "en",
    "status_code": 200,
    "content_length": 15234,
    "crawler_version": "crawl4ai-0.7.4",

    # USER-PROVIDED (merged from --metadata flag)
    "category": "tutorial",  # Example user metadata
    "version": "2.0"         # Example user metadata
}
```

**Rationale**:
- `source` - Specific page URL, critical for deduplication and citation
- `crawl_root_url` - **KEY FOR RE-CRAWL**: Used to identify all pages from same crawl for deletion
- `crawl_depth` - Enables filtering by distance from root
- `domain` - Allows fast domain-specific searches
- `crawl_timestamp` - Tracks content freshness
- `crawl_session_id` - Groups all pages from same crawl run
- `parent_url` - Tracks which page linked here (reconstructs crawl tree)
- User metadata merges with system metadata for custom organization

**Re-crawl Strategy**: Use `crawl_root_url` as the key to find and delete all pages from a previous crawl of the same site.

---

### 2. RE-CRAWL / UPDATE STRATEGY (DECIDED)

**✅ FINAL DECISION: "Nuclear Option" with `recrawl` Command**

**Approach**: Delete all pages matching `crawl_root_url`, then re-crawl from scratch.

**Why This Approach**:
- Simple and reliable (no edge cases with URL matching)
- Handles site redesigns, URL changes, deleted pages automatically
- No risk of stale content or duplicate pages
- Cost is acceptable for typical documentation sites (<200 pages)

**Implementation**:

**New CLI Command**:
```bash
uv run poc recrawl "https://docs.anthropic.com/en/api/agent-sdk/overview" \
    --collection anthropic-docs \
    --follow-links \
    --max-depth 3
```

**What it does**:
1. Query database: Find all source documents where `metadata.crawl_root_url` matches
2. Delete those source documents + all their chunks
3. Re-crawl from the root URL with same parameters
4. Ingest new pages into collection
5. Report: "Deleted X old pages, crawled Y new pages"

**Key Features**:
- ✅ Safe for mixed collections (only deletes pages from specific crawl root)
- ✅ User can have multiple crawl roots in one collection
- ✅ User can mix web pages + file ingestion in same collection
- ✅ Predictable behavior (always fresh data)
- ✅ No prompts or confirmations needed

**Alternative Usage** (explicit):
```bash
# Manual two-step approach (also supported)
uv run poc collection delete anthropic-docs
uv run poc collection create anthropic-docs
uv run poc crawl-url "https://docs.anthropic.com/..." --collection anthropic-docs
```

**Cost Estimate**: For 100-page site, re-embedding costs ~$0.02-0.10 with OpenAI (acceptable for weekly/monthly updates)

---

## 3. ERROR HANDLING STRATEGY (DECIDED)

**✅ FINAL DECISION: Structured Results with Error Lists**

**Approach**: Business logic returns structured dataclasses, not exceptions. CLI/API/MCP format the results.

**Why This Approach**:
- Enables FastAPI/MCP exposure later without refactoring
- Clean separation: business logic has zero CLI/API dependencies
- Errors are data, not control flow
- Continue-on-error behavior built into the design

### Implementation Pattern

**Core Business Logic** (returns structured results):

```python
from dataclasses import dataclass
from typing import List
from datetime import datetime

@dataclass
class CrawlError:
    """Structured error from a failed page crawl."""
    url: str
    error_type: str  # "timeout", "404", "parse_error", "network_error", etc.
    error_message: str
    timestamp: str

@dataclass
class CrawlResult:
    """Result from crawling one or more pages."""
    success: bool              # True if any pages succeeded
    pages_crawled: int         # Number of successful pages
    pages_failed: int          # Number of failed pages
    documents: List[Document]  # Successfully crawled documents
    errors: List[CrawlError]   # List of failures (empty if all succeeded)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

# Business logic - no CLI dependencies
def crawl_url(url: str, config: CrawlConfig) -> CrawlResult:
    """
    Crawl a URL and return structured result.
    Never prints to console, never calls sys.exit().
    """
    errors = []
    documents = []

    try:
        async for result in await crawler.arun(url, config):
            if result.success:
                documents.append(...)
            else:
                errors.append(CrawlError(
                    url=result.url,
                    error_type="crawl_failed",
                    error_message=getattr(result, 'error_message', 'Unknown'),
                    timestamp=datetime.utcnow().isoformat()
                ))
    except Exception as e:
        logger.exception(f"Unexpected error during crawl: {e}")
        errors.append(CrawlError(
            url=url,
            error_type="unexpected_error",
            error_message=str(e),
            timestamp=datetime.utcnow().isoformat()
        ))

    return CrawlResult(
        success=len(documents) > 0,
        pages_crawled=len(documents),
        pages_failed=len(errors),
        documents=documents,
        errors=errors
    )
```

**CLI Formatting** (thin wrapper):

```python
# cli.py - formats results for terminal display
@cli.command("crawl-url")
def crawl_url_cmd(url, collection, ...):
    """CLI command - just formats and displays results."""
    from src.ingestion.web_crawler import crawl_url, CrawlConfig

    config = CrawlConfig(...)
    result = crawl_url(url, config)  # Call business logic

    # Format for CLI
    if result.success:
        console.print(f"[green]✅ Crawled {result.pages_crawled} pages[/green]")
    else:
        console.print("[red]❌ Crawl failed - no pages retrieved[/red]")
        sys.exit(1)

    # Show errors prominently
    if result.has_errors:
        console.print(f"\n[yellow]⚠️  {result.pages_failed} pages failed:[/yellow]")
        for error in result.errors[:10]:
            console.print(f"  ✗ {error.url}: {error.error_message}")
        if result.pages_failed > 10:
            console.print(f"  ... and {result.pages_failed - 10} more")
```

**Future API/MCP** (same business logic, different formatting):

```python
# api/crawl.py - FastAPI endpoint (future)
@app.post("/crawl")
def api_crawl(request: CrawlRequest):
    result = crawl_url(request.url, ...)
    return {
        "success": result.success,
        "pages_crawled": result.pages_crawled,
        "pages_failed": result.pages_failed,
        "errors": [{"url": e.url, "error": e.error_message} for e in result.errors]
    }

# mcp/tools.py - MCP tool (future)
def mcp_crawl_tool(url: str, ...):
    result = crawl_url(url, ...)
    return {
        "content": [{"type": "text", "text": f"Crawled {result.pages_crawled} pages"}],
        "isError": not result.success
    }
```

### Logging Strategy

- `logger.info()` - Successful operations (page crawled, document ingested)
- `logger.warning()` - Skipped items (filtered out, already visited)
- `logger.error()` - Failed operations (network error, parse error)
- `logger.exception()` - Unexpected exceptions with stack trace

**Key Point**: Logging is separate from return values. Business logic logs AND returns structured results.

### Exit Codes (CLI Only)

- `0` - Any pages succeeded (even if some failed)
- `1` - Zero pages succeeded (total failure)

### Current Pattern Analysis

Looking at your existing code in `src/cli.py:247-248` and `src/document_store.py`:

```python
# cli.py - directory ingestion (lines 242-248)
for file_path in files:
    try:
        source_id, chunk_ids = doc_store.ingest_file(str(file_path), collection)
        source_ids.append(source_id)
        total_chunks += len(chunk_ids)
        console.print(f"  ✓ {file_path.name}: {len(chunk_ids)} chunks")
    except Exception as e:
        console.print(f"  ✗ {file_path.name}: {e}")
```

**Current behavior**: Continue on error, log failure, proceed with remaining files.

### Options for Web Crawling

**Option A: Fail Fast (Stop on First Error)**
- Pros: Immediately alerts to problems, forces fixing issues
- Cons: Can't complete partial crawls, brittle for flaky websites

**Option B: Continue on Error (Current Pattern)**
- Pros: Maximizes data collection, resilient to partial failures
- Cons: Silent failures if logs missed

**Option C: Fail Fast with Flag Override**
- Pros: Safe by default, flexible when needed
- Cons: Extra flag to remember

### My Recommendation

**Use Option B (Continue on Error) with Enhanced Reporting**

**Rationale**:
1. **Consistency**: Matches your existing `ingest directory` pattern
2. **Resilience**: Web scraping is inherently flaky (timeouts, 404s, rate limits)
3. **Practicality**: A crawl with 45/50 pages successful is valuable, not a failure

**Implementation Strategy**:

```python
# During crawl - collect failures
failed_pages = []  # List of (url, error_message) tuples

async for result in await crawler.arun(url, config=config):
    if result.success:
        # Process successful page
        documents.append(...)
    else:
        # Log failure at ERROR level
        error_msg = getattr(result, 'error_message', 'Unknown error')
        logger.error(f"Failed to crawl {result.url}: {error_msg}")
        failed_pages.append((result.url, error_msg))

# After crawl - report summary
logger.info(f"Crawl complete: {len(documents)} succeeded, {len(failed_pages)} failed")

# In CLI - display failures prominently
if failed_pages:
    console.print(f"\n[yellow]⚠️  {len(failed_pages)} pages failed:[/yellow]")
    for url, error in failed_pages[:10]:  # Show first 10
        console.print(f"  ✗ {url}: {error}")
    if len(failed_pages) > 10:
        console.print(f"  ... and {len(failed_pages) - 10} more")
```

**Logging Strategy**:
- `logger.info()` - Successful page crawls
- `logger.warning()` - Skipped pages (e.g., already visited, filtered out)
- `logger.error()` - Failed crawls (network errors, timeouts, parse failures)
- `logger.exception()` - Unexpected exceptions with full stack trace

**Exit Codes**:
- `0` - All pages succeeded
- `0` - Some pages failed but at least one succeeded (with warning message)
- `1` - Zero pages succeeded (total failure)

---

## 4. PROJECT STRUCTURE & MODULARITY (DECIDED)

**✅ FINAL DECISION: Clean Domain Separation with Gradual Migration**

**Approach**: Reorganize into core/ingestion/retrieval domains, migrate gradually.

**Migration Strategy**:
1. First, restructure existing code (no new features yet)
2. Add compatibility layer so imports don't break
3. Then add web crawling to new structure
4. This ensures existing functionality keeps working throughout

### Target Structure

```
src/
├── __init__.py              # Compatibility layer (re-exports for backward compat)
├── cli.py                   # CLI commands (stays at root for now)
│
├── core/                    # Core infrastructure (database, embeddings, etc.)
│   ├── __init__.py
│   ├── database.py          # MOVED from src/
│   ├── embeddings.py        # MOVED from src/
│   ├── chunking.py          # MOVED from src/
│   └── collections.py       # MOVED from src/
│
├── ingestion/               # Document ingestion domain
│   ├── __init__.py
│   ├── models.py            # NEW - CrawlResult, IngestionResult, CrawlError
│   ├── document_store.py    # MOVED from src/
│   └── web_crawler.py       # NEW - web crawling (added after restructure)
│
└── retrieval/               # Search/retrieval domain
    ├── __init__.py
    ├── models.py            # NEW - SearchResult, etc.
    └── search.py            # MOVED from src/
```

**Why This Structure**:
- ✅ Clean separation: core infrastructure vs domain logic
- ✅ API/MCP-ready: business logic independent of interface
- ✅ Minimal disruption: backward compatibility via `src/__init__.py`
- ✅ Future-proof: Easy to add `src/api/` or `src/mcp/` later

### Compatibility Layer

`src/__init__.py` will re-export everything:
```python
# Backward compatibility - old imports still work
from src.core.database import *
from src.core.embeddings import *
from src.core.chunking import *
from src.core.collections import *
from src.ingestion.document_store import *
from src.retrieval.search import *
```

This means existing code like `from src.database import get_database` continues to work.

### Current Structure Analysis

```
src/
├── __init__.py
├── cli.py              # 430 lines - CLI commands
├── database.py         # Database connection
├── embeddings.py       # OpenAI embedding generation
├── chunking.py         # Text chunking logic
├── document_store.py   # Document ingestion
├── search.py           # Similarity search
└── collections.py      # Collection management
```

**Issue**: Flat structure, all files in one directory. As the project grows, this becomes hard to navigate.

### Proposed Modular Structure

```
src/
├── __init__.py
├── cli/                    # CLI module
│   ├── __init__.py
│   ├── main.py            # Entry point, Click group
│   ├── collection_commands.py
│   ├── ingest_commands.py
│   ├── search_commands.py
│   ├── document_commands.py
│   └── crawl_commands.py  # NEW - web crawling commands
│
├── core/                   # Core business logic
│   ├── __init__.py
│   ├── database.py
│   ├── embeddings.py
│   ├── chunking.py
│   └── collections.py
│
├── ingestion/              # Data ingestion module
│   ├── __init__.py
│   ├── document_store.py  # Moved from root
│   └── web_crawler.py     # NEW - web crawling logic
│
└── retrieval/              # Search/retrieval module
    ├── __init__.py
    └── search.py           # Moved from root
```

### Alternative: Minimal Reorganization (My Recommendation for POC)

Since this is a POC, I recommend a **lighter reorganization**:

```
src/
├── __init__.py
├── cli.py              # Keep as-is for now
│
├── core/               # NEW - Move existing core files here
│   ├── __init__.py
│   ├── database.py
│   ├── embeddings.py
│   ├── chunking.py
│   └── collections.py
│
├── ingestion/          # NEW - Ingestion logic
│   ├── __init__.py
│   ├── document_store.py
│   └── web_crawler.py      # NEW
│
└── retrieval/          # NEW - Search logic
    ├── __init__.py
    └── search.py
```

**Why this approach?**:
1. **Gradual migration**: Doesn't break existing code immediately
2. **Clear domains**: Core, Ingestion, Retrieval are logical groupings
3. **Easy imports**: `from src.ingestion.web_crawler import WebCrawler`
4. **Future-proof**: Easy to add `src/cli/` module later if CLI grows
5. **Minimal disruption**: Existing imports can be updated incrementally

**Import Strategy**:
```python
# Old imports (still work during transition)
from src.database import get_database
from src.embeddings import get_embedding_generator

# New imports (update over time)
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.web_crawler import WebCrawler
```

**Compatibility Layer** (`src/__init__.py`):
```python
# Maintain backward compatibility during transition
from src.core.database import *
from src.core.embeddings import *
from src.core.chunking import *
from src.core.collections import *
from src.ingestion.document_store import *
from src.retrieval.search import *
```

---

## 4. TESTING STRATEGY

### Philosophy: Test as You Build

Following your preference for "implement a little, test a little":

### Phase 1: Installation & Setup
**Implement**:
- Add crawl4ai to pyproject.toml
- Run `uv sync`
- Run `uv run crawl4ai-setup` or `python -m playwright install chromium`

**Test**:
```bash
# Verify installation
python -c "import crawl4ai; print(crawl4ai.__version__)"

# Should print: 0.7.4 or higher
```

**Test File**: `tests/test_crawler_installation.py`
```python
def test_crawl4ai_installed():
    """Verify Crawl4AI is available."""
    import crawl4ai
    assert crawl4ai.__version__

def test_playwright_installed():
    """Verify Playwright browsers are available."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
```

### Phase 2: Basic Web Crawler (Single Page)
**Implement**:
- Create `src/ingestion/web_crawler.py`
- Implement `WebCrawler` class
- Implement `crawl_url()` method with `max_depth=0` (single page only)
- Add basic error handling

**Test**:
```bash
# Manual test
python -c "
from src.ingestion.web_crawler import WebCrawler, CrawlConfig
crawler = WebCrawler()
config = CrawlConfig(max_depth=0, max_pages=1)
docs = crawler.crawl_url_sync('https://example.com', config)
print(f'Crawled {len(docs)} pages')
print(f'First page: {docs[0].metadata}')
"
```

**Test File**: `tests/test_web_crawler_basic.py`
```python
def test_crawl_single_page():
    """Test crawling a single page (no link following)."""
    crawler = WebCrawler()
    config = CrawlConfig(max_depth=0, max_pages=1)
    docs = crawler.crawl_url_sync("https://example.com", config)

    assert len(docs) == 1
    assert docs[0].page_content
    assert docs[0].metadata["source"] == "https://example.com"
    assert docs[0].metadata["crawl_depth"] == 0
```

### Phase 3: Link Following
**Implement**:
- Add `BFSDeepCrawlStrategy` with `max_depth > 0`
- Test with depth=1 (starting page + direct links)

**Test**:
```bash
# Manual test with real site
python -c "
from src.ingestion.web_crawler import WebCrawler, CrawlConfig
crawler = WebCrawler()
config = CrawlConfig(max_depth=1, max_pages=10)
docs = crawler.crawl_url_sync('https://example.com', config)
print(f'Crawled {len(docs)} pages')
for doc in docs:
    print(f'  - {doc.metadata[\"source\"]} (depth: {doc.metadata[\"crawl_depth\"]})')
"
```

**Test File**: `tests/test_web_crawler_depth.py`
```python
def test_link_following():
    """Test that link following works with max_depth > 0."""
    crawler = WebCrawler()
    config = CrawlConfig(max_depth=1, max_pages=10)
    docs = crawler.crawl_url_sync("https://example.com", config)

    # Should get at least the starting page
    assert len(docs) >= 1

    # Check depth tracking
    depths = {doc.metadata["crawl_depth"] for doc in docs}
    assert 0 in depths  # Starting page
```

### Phase 4: DocumentStore Integration
**Implement**:
- Add `ingest_from_url()` method to `DocumentStore`
- Integrate crawler with existing chunking/embedding pipeline

**Test**:
```bash
# End-to-end test
uv run poc collection create test-crawl
uv run poc crawl-url "https://example.com" --collection test-crawl
uv run poc document list --collection test-crawl
# Should show 1 document with chunks
```

**Test File**: `tests/test_crawler_integration.py`
```python
def test_crawl_to_database(test_db, test_collection):
    """Test full crawl → chunk → embed → store pipeline."""
    doc_store = get_document_store(...)

    results = doc_store.ingest_from_url(
        url="https://example.com",
        collection_name=test_collection,
        follow_links=False
    )

    assert len(results) == 1
    source_id, chunk_ids = results[0]
    assert source_id > 0
    assert len(chunk_ids) > 0

    # Verify document is searchable
    searcher = get_similarity_search(...)
    search_results = searcher.search_chunks("example", collection_name=test_collection)
    assert len(search_results) > 0
```

### Phase 5: CLI Commands
**Implement**:
- Add `crawl-url` command
- Add `crawl-batch` command
- Rich output formatting

**Test**:
```bash
# CLI tests
uv run poc crawl-url "https://example.com" --collection test
uv run poc crawl-url "https://example.com" --follow-links --max-depth 1 --collection test
uv run poc search "example" --collection test
```

### Test Coverage Strategy

**Unit Tests** (fast, no network):
- Metadata schema validation
- URL parsing and normalization
- Error handling logic
- Configuration validation

**Integration Tests** (requires network):
- Single page crawl
- Link following
- Database storage
- Search functionality

**End-to-End Tests** (full pipeline):
- CLI command execution
- Crawl → chunk → embed → search

**Test Fixtures**:
- Use `example.com` for simple tests (reliable, fast)
- Mock Crawl4AI responses for unit tests
- Use local HTML files for offline testing

---

## 5. IMPLEMENTATION PLAN

### Phase 1: Setup & Dependencies (30 minutes)
1. Update `pyproject.toml` with crawl4ai + playwright
2. Run `uv sync`
3. Install Playwright browsers
4. Create test to verify installation

**Deliverable**: Working Crawl4AI installation

### Phase 2: Core Web Crawler Module (2 hours)
1. Create `src/ingestion/` directory
2. Move `src/document_store.py` → `src/ingestion/document_store.py`
3. Create `src/ingestion/web_crawler.py`
4. Implement `WebCrawler` class with single-page crawling (max_depth=0)
5. Implement metadata extraction
6. Write basic tests

**Deliverable**: Working `WebCrawler` class that can fetch single pages

### Phase 3: Link Following (1.5 hours)
1. Add `BFSDeepCrawlStrategy` configuration
2. Implement depth tracking
3. Add visited URL tracking
4. Test with depth=1, then depth=2

**Deliverable**: Working link following with configurable depth

### Phase 4: DocumentStore Integration (1 hour)
1. Add `ingest_from_url()` method to `DocumentStore`
2. Integrate crawler with existing chunking pipeline
3. Add error collection and reporting
4. Test full pipeline

**Deliverable**: URLs can be ingested into database

### Phase 5: CLI Commands (1.5 hours)
1. Add `crawl-url` command to `src/cli.py`
2. Add Rich formatting for crawl progress
3. Add failure reporting
4. Add `crawl-batch` command (optional)

**Deliverable**: Working CLI for web crawling

### Phase 6: Testing & Documentation (1 hour)
1. Write comprehensive tests
2. Update CLAUDE.md with examples
3. Test with real documentation sites
4. Performance tuning if needed

**Deliverable**: Production-ready feature

**Total Estimated Time**: 7-8 hours

---

## 6. MIGRATION STRATEGY (Structural Changes)

### Option A: Big Bang (Not Recommended)
- Move all files to new structure immediately
- Update all imports at once
- High risk of breaking changes

### Option B: Gradual Migration (Recommended)
1. **Week 1**: Create new directories, add new code
   - Create `src/core/`, `src/ingestion/`, `src/retrieval/`
   - Add compatibility imports in `src/__init__.py`
   - All existing code still works

2. **Week 2**: Move files gradually
   - Move `database.py` → `src/core/database.py`
   - Update imports in new code only
   - Old imports still work via `__init__.py`

3. **Week 3**: Update imports
   - Update all imports to new structure
   - Remove compatibility layer
   - Verify all tests pass

### For This Feature: Hybrid Approach
1. **Immediately**: Create `src/ingestion/` for new crawler code
2. **Keep**: `src/*.py` files in current location
3. **Future**: Migrate gradually as time permits

**This approach**:
- ✅ Adds modularity where we need it (new crawler)
- ✅ Doesn't break existing code
- ✅ Demonstrates better structure for future work
- ✅ Keeps this PR focused on web crawling feature

---

## RECOMMENDATIONS SUMMARY

1. **Metadata**: Use comprehensive schema with required + optional fields
2. **Error Handling**: Continue on error (match existing pattern), log failures prominently
3. **Structure**: Create `src/ingestion/` for crawler, migrate gradually
4. **Testing**: Implement-test-implement-test in small phases
5. **Timeline**: 7-8 hours of focused work

**Next Steps**: Review each section, provide feedback, then begin Phase 1 implementation.
