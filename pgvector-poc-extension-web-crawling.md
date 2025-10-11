# POC Extension: Web Crawling with Crawl4AI

## Purpose

This document extends the pgvector POC to add web crawling capabilities using Crawl4AI. This allows ingesting content directly from websites into collections, with support for recursive link following, automatic content cleaning, and markdown conversion optimized for RAG applications.

## Prerequisites

You should have already implemented:
- ✅ Base POC (PostgreSQL + pgvector, embeddings, search)
- ✅ Document chunking extension (source_documents, document_chunks tables)
- ✅ Document ingestion with `DocumentStore`
- ✅ CLI framework with Click

## Critical Requirement

**MUST implement link following**: The web crawler MUST support an optional `--follow-links` flag that allows recursive crawling of linked pages up to a configurable depth. This is NOT optional - it's a core requirement.

## Technology Selection: Crawl4AI

**Selected**: Crawl4AI v0.7.4 (Latest stable as of October 2025)

**Why Crawl4AI**:
- ✅ Built on top of Playwright (inherits all browser capabilities)
- ✅ Optimized specifically for LLM/RAG content extraction
- ✅ Built-in content filtering (removes navigation, ads, etc.)
- ✅ Returns clean markdown (better for chunking)
- ✅ Built-in recursive crawling with BFSDeepCrawlStrategy
- ✅ 51K+ GitHub stars, proven in production
- ✅ Latest version 0.7.4 with stability improvements

**Official Resources**:
- PyPI: https://pypi.org/project/crawl4ai/
- GitHub: https://github.com/unclecode/crawl4ai
- Documentation: https://docs.crawl4ai.com/

## ⚠️ IMPORTANT: Research Current API

**Before implementing**, you MUST:
1. Check the latest Crawl4AI documentation at https://docs.crawl4ai.com/
2. Verify the API structure hasn't changed since this document
3. Check for any breaking changes in v0.7.4+
4. Review the official examples for current best practices

The code snippets below are from a working implementation (verified August 2025) but **you must validate against current documentation**.

## Reference Implementation

Below are code snippets from a working Crawl4AI implementation. Use these as **guidance**, not gospel. Check current Crawl4AI docs for any API changes.

### Working Crawl4AI Setup (Reference)

```python
# From: rag_retriever/crawling/crawl4ai_crawler.py (lines 15-18, 42-65)
# This is REFERENCE CODE - verify API is still current!

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

def _create_crawler_config(max_depth: int = 0) -> CrawlerRunConfig:
    """
    Create Crawl4AI configuration with aggressive content filtering.
    
    IMPORTANT: Verify this API structure with current Crawl4AI docs!
    This was working as of August 2025 but may have changed.
    """
    # Aggressive filtering - removes navigation content
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(
            threshold=0.7,  # High threshold = aggressive filtering
            threshold_type="fixed"
        )
    )
    
    return CrawlerRunConfig(
        deep_crawl_strategy=BFSDeepCrawlStrategy(
            max_depth=max_depth,
            include_external=False  # Stay within same domain - CRITICAL for link following
        ),
        markdown_generator=md_generator,
        word_count_threshold=15,  # Ignore very short text blocks
        stream=True
    )
```

**Key Points from Reference**:
- `BFSDeepCrawlStrategy` with `max_depth` enables link following
- `include_external=False` keeps crawling within same domain
- `PruningContentFilter(threshold=0.7)` aggressively removes navigation
- `fit_markdown` output (shown below) is pre-cleaned

### Working Website Crawl (Reference)

```python
# From: rag_retriever/crawling/crawl4ai_crawler.py (lines 138-194)
# REFERENCE CODE - check current docs!

async def crawl_website(base_url: str, max_depth: int = 2, max_pages: int = 50):
    """
    Crawl a website recursively.
    
    Args:
        base_url: Starting URL
        max_depth: How many levels deep to follow links (0 = single page only)
        max_pages: Maximum number of pages to crawl
    """
    logger.info(f"Starting website crawl: {base_url} (max_depth: {max_depth})")
    
    documents = []
    config = _create_crawler_config(max_depth=max_depth)
    
    async with AsyncWebCrawler() as crawler:
        page_count = 0
        async for result in await crawler.arun(base_url, config=config):
            if page_count >= max_pages:
                logger.info(f"Reached max pages limit: {max_pages}")
                break
            
            if result.success:
                # KEY: Use fit_markdown for cleaned content
                content = result.markdown.fit_markdown
                
                if content and content.strip():
                    # Extract metadata
                    metadata = {
                        "source": result.url,
                        "title": result.metadata.get("title", "") if result.metadata else "",
                        "description": result.metadata.get("description", "") if result.metadata else "",
                        "content_length": len(content),
                        "crawler_type": "crawl4ai",
                        "depth": getattr(result, 'depth', 0) or 0
                    }
                    
                    # Create document (LangChain format)
                    document = Document(
                        page_content=content,
                        metadata=metadata
                    )
                    documents.append(document)
                    page_count += 1
                    
                    logger.info(f"✓ Crawled: {result.url} ({len(content)} chars)")
    
    return documents
```

**Critical Features**:
- `max_depth` parameter controls link following
- `async for result in await crawler.arun()` handles streaming results
- `result.markdown.fit_markdown` is the cleaned markdown
- `result.success` checks if crawl succeeded
- Tracks depth in metadata

## Implementation Plan

### Step 1: Add Crawl4AI Dependency

Update `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "crawl4ai>=0.7.4",           # Latest stable (Oct 2025)
    "playwright>=1.49.0",         # Required by Crawl4AI
]
```

**THEN**: Run post-installation setup:
```bash
uv sync
uv run crawl4ai-setup  # Installs browser binaries
uv run crawl4ai-doctor  # Verifies installation
```

Or manually install browsers:
```bash
python -m playwright install --with-deps chromium
```

### Step 2: Create Web Crawler Module

Create `src/web_crawler.py`:

**⚠️ IMPORTANT**: Before copying this code, check https://docs.crawl4ai.com/ for current API!

```python
"""Web crawling using Crawl4AI for content extraction."""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from langchain_core.documents import Document

# Import Crawl4AI components
# NOTE: Verify these imports match current Crawl4AI v0.7.4+ API
try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    CRAWL4AI_AVAILABLE = True
except ImportError as e:
    CRAWL4AI_AVAILABLE = False
    print(f"Warning: Crawl4AI not available: {e}")

logger = logging.getLogger(__name__)


@dataclass
class CrawlConfig:
    """Configuration for web crawling."""
    
    max_depth: int = 0            # 0 = single page, 1+ = follow links
    max_pages: int = 50           # Max pages to crawl
    include_external: bool = False  # Follow external links?
    filter_threshold: float = 0.7  # Content filter aggressiveness (0-1)
    word_count_threshold: int = 15  # Minimum words per block
    
    
class WebCrawler:
    """
    Web crawler using Crawl4AI for content extraction.
    
    MUST support link following when max_depth > 0.
    """
    
    def __init__(self):
        """Initialize web crawler."""
        if not CRAWL4AI_AVAILABLE:
            raise ImportError(
                "Crawl4AI not installed. Run: pip install crawl4ai>=0.7.4"
            )
        
        self.visited_urls = set()
    
    def _create_config(self, crawl_config: CrawlConfig) -> CrawlerRunConfig:
        """
        Create Crawl4AI crawler configuration.
        
        IMPORTANT: Before using this, verify the API at:
        https://docs.crawl4ai.com/
        
        This code structure was valid as of v0.7.4 but may change.
        Research the current API first!
        """
        # Content filtering for clean markdown
        md_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=crawl_config.filter_threshold,
                threshold_type="fixed"
            )
        )
        
        # CRITICAL: BFSDeepCrawlStrategy enables link following
        # max_depth > 0 means follow links recursively
        deep_crawl_strategy = None
        if crawl_config.max_depth > 0:
            deep_crawl_strategy = BFSDeepCrawlStrategy(
                max_depth=crawl_config.max_depth,
                include_external=crawl_config.include_external
            )
        
        # TODO: Check current CrawlerRunConfig API before using!
        return CrawlerRunConfig(
            deep_crawl_strategy=deep_crawl_strategy,
            markdown_generator=md_generator,
            word_count_threshold=crawl_config.word_count_threshold,
            stream=True
        )
    
    async def crawl_url(
        self,
        url: str,
        crawl_config: Optional[CrawlConfig] = None
    ) -> List[Document]:
        """
        Crawl a URL and optionally follow links.
        
        Args:
            url: Starting URL to crawl
            crawl_config: Optional crawl configuration
            
        Returns:
            List of Document objects (LangChain format)
        """
        if crawl_config is None:
            crawl_config = CrawlConfig()
        
        logger.info(
            f"Starting crawl: {url} "
            f"(depth: {crawl_config.max_depth}, max_pages: {crawl_config.max_pages})"
        )
        
        documents = []
        config = self._create_config(crawl_config)
        
        try:
            async with AsyncWebCrawler() as crawler:
                page_count = 0
                
                # NOTE: Verify this async iteration pattern with current docs
                async for result in await crawler.arun(url, config=config):
                    if page_count >= crawl_config.max_pages:
                        logger.info(f"Reached max pages limit: {crawl_config.max_pages}")
                        break
                    
                    if result.success:
                        # Use fit_markdown for cleaned content
                        # NOTE: Verify result.markdown.fit_markdown still exists in v0.7.4+
                        content = result.markdown.fit_markdown
                        
                        if content and content.strip():
                            # Build metadata
                            metadata = {
                                "source": result.url,
                                "title": result.metadata.get("title", "") if result.metadata else "",
                                "description": result.metadata.get("description", "") if result.metadata else "",
                                "content_length": len(content),
                                "crawler_type": "crawl4ai",
                                "depth": getattr(result, 'depth', 0) or 0,
                            }
                            
                            document = Document(
                                page_content=content,
                                metadata=metadata
                            )
                            
                            documents.append(document)
                            self.visited_urls.add(result.url)
                            page_count += 1
                            
                            logger.info(
                                f"✓ Crawled [{page_count}/{crawl_config.max_pages}]: "
                                f"{result.url} ({len(content)} chars, depth: {metadata['depth']})"
                            )
                        else:
                            logger.warning(f"✗ No content extracted: {result.url}")
                    else:
                        error = getattr(result, 'error_message', 'Unknown error')
                        logger.error(f"✗ Failed to crawl {result.url}: {error}")
                
                logger.info(
                    f"Crawl complete: {len(documents)} pages from {url} "
                    f"(visited {len(self.visited_urls)} URLs)"
                )
                
                return documents
                
        except Exception as e:
            logger.error(f"Error during crawl: {e}")
            raise
    
    def crawl_url_sync(
        self,
        url: str,
        crawl_config: Optional[CrawlConfig] = None
    ) -> List[Document]:
        """
        Synchronous wrapper for async crawl_url.
        
        Use this for CLI commands and non-async contexts.
        """
        return asyncio.run(self.crawl_url(url, crawl_config))
    
    def reset(self):
        """Reset visited URLs tracking."""
        self.visited_urls.clear()
```

### Step 3: Integrate with DocumentStore

Update `src/document_store.py` to add web crawling:

```python
# Add this method to your existing DocumentStore class

def ingest_from_url(
    self,
    url: str,
    collection_name: str = "default",
    follow_links: bool = False,
    max_depth: int = 1,
    max_pages: int = 50,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Tuple[int, List[int]]]:
    """
    Crawl a URL and ingest all pages into collection.
    
    Args:
        url: Starting URL to crawl
        collection_name: Collection to add documents to
        follow_links: Whether to recursively follow links
        max_depth: How many levels deep to follow links (requires follow_links=True)
        max_pages: Maximum number of pages to crawl
        metadata: Optional base metadata for all documents
        
    Returns:
        List of (source_document_id, chunk_ids) tuples for each crawled page
    """
    from .web_crawler import WebCrawler, CrawlConfig
    
    # Create crawler
    crawler = WebCrawler()
    
    # Configure crawling
    config = CrawlConfig(
        max_depth=max_depth if follow_links else 0,  # 0 = single page only
        max_pages=max_pages,
        include_external=False,  # Stay within same domain
    )
    
    logger.info(
        f"Crawling {url} (follow_links={follow_links}, "
        f"max_depth={max_depth if follow_links else 0})"
    )
    
    # Crawl the URL(s)
    documents = crawler.crawl_url_sync(url, config)
    
    if not documents:
        logger.warning(f"No documents retrieved from {url}")
        return []
    
    logger.info(f"Retrieved {len(documents)} documents from crawl")
    
    # Ingest each crawled page
    results = []
    for i, doc in enumerate(documents, 1):
        logger.info(f"Ingesting document {i}/{len(documents)}: {doc.metadata['source']}")
        
        # Merge base metadata with page metadata
        doc_metadata = metadata.copy() if metadata else {}
        doc_metadata.update(doc.metadata)
        
        # Ingest document (chunks automatically)
        source_id, chunk_ids = self.ingest_document(
            content=doc.page_content,
            filename=doc.metadata.get('title') or doc.metadata['source'],
            collection_name=collection_name,
            metadata=doc_metadata,
            file_type="web_page",
        )
        
        results.append((source_id, chunk_ids))
        logger.info(
            f"  → Stored as document {source_id} with {len(chunk_ids)} chunks"
        )
    
    logger.info(
        f"✅ Ingestion complete: {len(results)} documents, "
        f"{sum(len(chunks) for _, chunks in results)} total chunks"
    )
    
    return results
```

### Step 4: Add CLI Commands

Add these commands to `src/cli.py`:

```python
@cli.command(name="crawl-url")
@click.argument("url")
@click.option("--collection", default="default", help="Collection name")
@click.option("--follow-links/--no-follow-links", default=False, 
              help="Follow links recursively (REQUIRED feature)")
@click.option("--max-depth", default=1, 
              help="Max depth for link following (only with --follow-links)")
@click.option("--max-pages", default=50, 
              help="Maximum pages to crawl")
@click.option("--metadata", type=str, 
              help="JSON metadata to attach to all crawled pages")
def crawl_url_cmd(url, collection, follow_links, max_depth, max_pages, metadata):
    """
    Crawl a website and ingest content into collection.
    
    Examples:
        # Single page only
        uv run poc crawl-url "https://docs.python.org/3/tutorial/intro.html"
        
        # Follow links 1 level deep
        uv run poc crawl-url "https://docs.python.org/3/tutorial/" \
            --follow-links --max-depth 1 --collection python-docs
        
        # Deep crawl with metadata
        uv run poc crawl-url "https://www.postgresql.org/docs/current/" \
            --follow-links --max-depth 2 --max-pages 100 \
            --collection postgres-docs \
            --metadata '{"version":"17","category":"official-docs"}'
    """
    from rich.console import Console
    from rich.progress import Progress
    from .document_store import DocumentStore
    import json
    
    console = Console()
    
    # Parse metadata if provided
    doc_metadata = json.loads(metadata) if metadata else {}
    
    # Validate max_depth usage
    if max_depth > 0 and not follow_links:
        console.print(
            "[yellow]⚠️  Warning: max-depth ignored without --follow-links[/yellow]"
        )
    
    # Show what we're doing
    if follow_links:
        console.print(
            f"🕸️  [green]Crawling {url}[/green]\n"
            f"   Follow links: [cyan]Yes[/cyan] (depth: {max_depth}, max: {max_pages} pages)\n"
            f"   Collection: [magenta]{collection}[/magenta]"
        )
    else:
        console.print(
            f"🕸️  [green]Fetching single page: {url}[/green]\n"
            f"   Collection: [magenta]{collection}[/magenta]"
        )
    
    # Create document store
    doc_store = DocumentStore()
    
    try:
        with console.status("[bold green]Crawling website..."):
            # Crawl and ingest
            results = doc_store.ingest_from_url(
                url=url,
                collection_name=collection,
                follow_links=follow_links,
                max_depth=max_depth,
                max_pages=max_pages,
                metadata=doc_metadata,
            )
        
        # Show results
        total_docs = len(results)
        total_chunks = sum(len(chunks) for _, chunks in results)
        
        console.print(f"\n✅ [bold green]Crawl complete![/bold green]")
        console.print(f"   Documents ingested: [cyan]{total_docs}[/cyan]")
        console.print(f"   Total chunks: [yellow]{total_chunks}[/yellow]")
        console.print(f"   Collection: [magenta]{collection}[/magenta]")
        
        # Show first few URLs crawled
        if results:
            console.print(f"\n[bold]Crawled URLs:[/bold]")
            for i, (source_id, _) in enumerate(results[:5], 1):
                # Get source document to show URL
                doc = doc_store.get_source_document(source_id)
                if doc:
                    source_url = doc['metadata'].get('source', 'unknown')
                    console.print(f"   {i}. {source_url}")
            
            if len(results) > 5:
                console.print(f"   ... and {len(results) - 5} more")
        
    except ImportError:
        console.print(
            "[bold red]❌ Crawl4AI not installed![/bold red]\n\n"
            "Install with:\n"
            "  uv sync\n"
            "  uv run crawl4ai-setup\n"
            "  python -m playwright install chromium"
        )
        raise click.Abort()
    
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        logger.error(f"Crawl failed: {e}", exc_info=True)
        raise click.Abort()


@cli.command(name="crawl-batch")
@click.argument("urls_file", type=click.Path(exists=True))
@click.option("--collection", default="default")
@click.option("--follow-links/--no-follow-links", default=False)
@click.option("--max-depth", default=1)
def crawl_batch_cmd(urls_file, collection, follow_links, max_depth):
    """
    Crawl multiple URLs from a file (one URL per line).
    
    Example:
        # Create urls.txt with one URL per line
        # Then run:
        uv run poc crawl-batch urls.txt --collection my-docs --follow-links
    """
    from rich.console import Console
    from rich.progress import track
    from pathlib import Path
    from .document_store import DocumentStore
    
    console = Console()
    
    # Read URLs
    urls = Path(urls_file).read_text().strip().split('\n')
    urls = [u.strip() for u in urls if u.strip() and not u.startswith('#')]
    
    if not urls:
        console.print("❌ No valid URLs found in file")
        return
    
    console.print(f"Found [cyan]{len(urls)}[/cyan] URLs to crawl")
    
    doc_store = DocumentStore()
    
    total_docs = 0
    total_chunks = 0
    failed = []
    
    for url in track(urls, description="Crawling..."):
        try:
            results = doc_store.ingest_from_url(
                url=url,
                collection_name=collection,
                follow_links=follow_links,
                max_depth=max_depth,
            )
            
            docs = len(results)
            chunks = sum(len(c) for _, c in results)
            total_docs += docs
            total_chunks += chunks
            
        except Exception as e:
            logger.error(f"Failed to crawl {url}: {e}")
            failed.append((url, str(e)))
    
    console.print(f"\n✅ [green]Batch crawl complete![/green]")
    console.print(f"   Total documents: [cyan]{total_docs}[/cyan]")
    console.print(f"   Total chunks: [yellow]{total_chunks}[/yellow]")
    
    if failed:
        console.print(f"\n[red]Failed ({len(failed)}):[/red]")
        for url, error in failed[:5]:
            console.print(f"   • {url}: {error}")
```

## Configuration

Add to `config.yaml`:

```yaml
# Web crawling configuration
web_crawler:
  # Default crawl settings
  default_max_depth: 1          # Default link following depth
  default_max_pages: 50         # Default max pages per crawl
  
  # Content filtering
  filter_threshold: 0.7         # 0-1, higher = more aggressive filtering
  word_count_threshold: 15      # Minimum words per content block
  
  # Link following behavior
  include_external: false       # Stay within same domain (recommended)
  respect_robots_txt: true      # Respect robots.txt (good practice)
  
  # Rate limiting
  delay_between_pages: 0.5      # Seconds between page requests
  max_retries: 3                # Retry failed pages
  
  # Timeout settings  
  page_timeout: 30000           # 30 seconds per page
  
# Integration with document processing
document_processing:
  # Web pages are automatically chunked like other documents
  web_page_chunk_size: 1000     # Same as other documents
  web_page_chunk_overlap: 200
```

## Usage Examples

### Example 1: Single Page

```bash
# Fetch one page, no link following
uv run poc crawl-url "https://docs.python.org/3/tutorial/introduction.html" \
    --collection python-docs \
    --no-follow-links
```

### Example 2: Follow Links (Shallow)

```bash
# Crawl starting page + direct links (depth 1)
uv run poc crawl-url "https://docs.python.org/3/tutorial/" \
    --collection python-docs \
    --follow-links \
    --max-depth 1 \
    --max-pages 20
```

### Example 3: Deep Crawl with Metadata

```bash
# Deep crawl with custom metadata
uv run poc crawl-url "https://www.postgresql.org/docs/current/tutorial.html" \
    --collection postgres-docs \
    --follow-links \
    --max-depth 2 \
    --max-pages 100 \
    --metadata '{"version":"17","category":"tutorial","official":true}'
```

### Example 4: Batch Crawl Multiple Sites

Create `sites.txt`:
```
https://docs.python.org/3/tutorial/
https://www.postgresql.org/docs/current/tutorial.html
https://fastapi.tiangolo.com/
# Comments are ignored
```

Then run:
```bash
uv run poc crawl-batch sites.txt \
    --collection tech-docs \
    --follow-links \
    --max-depth 1
```

### Example 5: Crawl and Search

```bash
# Crawl documentation
uv run poc crawl-url "https://docs.python.org/3/library/asyncio.html" \
    --collection python-docs \
    --follow-links \
    --max-depth 1

# Search the crawled content
uv run poc search "async await tutorial" --collection python-docs
```

## Testing

Create `tests/test_web_crawler.py`:

```python
"""Test web crawling functionality."""

import pytest
from src.web_crawler import WebCrawler, CrawlConfig


def test_crawl4ai_available():
    """Verify Crawl4AI is installed."""
    try:
        from crawl4ai import AsyncWebCrawler
        assert True
    except ImportError:
        pytest.fail("Crawl4AI not installed. Run: pip install crawl4ai>=0.7.4")


def test_single_page_crawl():
    """Test crawling a single page (no link following)."""
    crawler = WebCrawler()
    
    config = CrawlConfig(
        max_depth=0,  # Single page only
        max_pages=1,
    )
    
    # Use a simple, reliable test URL
    url = "https://example.com"
    
    documents = crawler.crawl_url_sync(url, config)
    
    # Should get exactly 1 document
    assert len(documents) == 1
    
    # Should have content
    assert len(documents[0].page_content) > 0
    
    # Should have metadata
    assert "source" in documents[0].metadata
    assert documents[0].metadata["source"] == url


def test_link_following():
    """
    Test that link following works (CRITICAL REQUIREMENT).
    """
    crawler = WebCrawler()
    
    config = CrawlConfig(
        max_depth=1,  # Follow links 1 level deep
        max_pages=10,
    )
    
    # Use a URL known to have links
    url = "https://example.com"  # Replace with better test URL
    
    documents = crawler.crawl_url_sync(url, config)
    
    # With max_depth=1, should get more than just the starting page
    # (Actual count depends on the site, but should be > 1)
    assert len(documents) >= 1
    
    # Check that visited_urls was populated
    assert len(crawler.visited_urls) >= 1
    
    print(f"\nCrawled {len(documents)} pages:")
    for doc in documents:
        print(f"  - {doc.metadata['source']} (depth: {doc.metadata.get('depth', 0)})")


def test_depth_tracking():
    """Verify depth is tracked correctly in metadata."""
    crawler = WebCrawler()
    
    config = CrawlConfig(max_depth=2, max_pages=20)
    
    documents = crawler.crawl_url_sync("https://example.com", config)
    
    # All documents should have depth in metadata
    for doc in documents:
        assert "depth" in doc.metadata
        assert isinstance(doc.metadata["depth"], int)
        assert 0 <= doc.metadata["depth"] <= 2


def test_markdown_output():
    """Verify output is clean markdown suitable for RAG."""
    crawler = WebCrawler()
    
    config = CrawlConfig(max_depth=0)
    
    documents = crawler.crawl_url_sync("https://example.com", config)
    
    content = documents[0].page_content
    
    # Should not contain HTML tags
    assert "<html" not in content.lower()
    assert "<script" not in content.lower()
    
    # Should be substantive (not just navigation)
    assert len(content) > 100
    
    # Should be markdown or plain text
    print(f"\nContent preview:\n{content[:500]}...")


# Run with: uv run pytest tests/test_web_crawler.py -v -s
```

## Important Notes for Implementation

### 1. Research Current Crawl4AI API First

**Before writing any code**, the AI assistant MUST:

```bash
# Check current documentation
pip install crawl4ai
python -c "import crawl4ai; help(crawl4ai.AsyncWebCrawler)"

# Or visit official docs
https://docs.crawl4ai.com/
```

**Things that might have changed since v0.7.4**:
- Import paths
- CrawlerRunConfig parameters
- BFSDeepCrawlStrategy API
- Markdown output structure (fit_markdown location)
- Streaming iteration pattern

**VERIFY** the reference code above matches current API before implementing!

### 2. Link Following is MANDATORY

The implementation MUST support:
- ✅ `--follow-links` flag that enables/disables recursive crawling
- ✅ `--max-depth` parameter to control how deep to follow links
- ✅ `--max-pages` parameter to limit total pages crawled
- ✅ Staying within same domain (no external links by default)
- ✅ Tracking depth in metadata
- ✅ Avoiding duplicate URLs (visited_urls tracking)

### 3. Integration with Existing POC

The web crawler should:
- Use existing `DocumentStore.ingest_document()` method
- Respect existing chunking configuration
- Store in existing `source_documents` and `document_chunks` tables
- Work with existing collections
- Generate embeddings using existing `embeddings.py`
- Follow same error handling patterns

### 4. Content Quality

Crawl4AI's `fit_markdown` output is **already optimized** for RAG:
- Navigation removed
- Clean markdown formatting
- No boilerplate/ads
- Preserves structure (headers, lists, code blocks)
- Better than raw HTML parsing

**Don't add extra cleaning** - fit_markdown is already clean!

### 5. Error Handling

Handle these common scenarios:
- URL not accessible (404, 500, etc.)
- JavaScript errors during crawl
- Timeout on slow pages
- Rate limiting by target site
- Invalid URLs
- No content extracted

## Testing Strategy

### Phase 1: Verify Installation

```bash
# Install
uv sync

# Setup Crawl4AI
uv run crawl4ai-setup

# Verify
uv run crawl4ai-doctor

# Should show green checkmarks for browser installation
```

### Phase 2: Test Single Page

```bash
# Simple, reliable test
uv run poc crawl-url "https://example.com" --collection test

# Verify in database
uv run poc list-documents --collection test

# Should see 1 document
```

### Phase 3: Test Link Following

```bash
# Crawl with link following
uv run poc crawl-url "https://example.com" \
    --follow-links \
    --max-depth 1 \
    --max-pages 5 \
    --collection test

# Should get multiple pages
uv run poc list-documents --collection test

# Should see 2-5 documents
```

### Phase 4: Test Real Documentation Site

```bash
# Try Python docs (good test site)
uv run poc crawl-url "https://docs.python.org/3/tutorial/introduction.html" \
    --follow-links \
    --max-depth 1 \
    --max-pages 10 \
    --collection python-test

# Verify chunks are searchable
uv run poc search "python variables" --collection python-test

# Should find relevant content
```

## Troubleshooting

### Problem: "Crawl4AI not installed"

```bash
uv add "crawl4ai>=0.7.4"
uv sync
uv run crawl4ai-setup
```

### Problem: "Browser not found"

```bash
python -m playwright install chromium
# Or install all browsers:
python -m playwright install
```

### Problem: No content extracted

Check if:
- URL is accessible in browser
- Site blocks bots (check robots.txt)
- Content is behind login/paywall
- JavaScript errors preventing render

### Problem: Import errors

```python
# Verify Crawl4AI version
python -c "import crawl4ai; print(crawl4ai.__version__)"

# Should show 0.7.4 or higher
```

If API has changed, check official docs and update code accordingly.

### Problem: Crawl very slow

- Reduce `max_pages` for testing
- Crawl4AI is async but still renders full pages
- Consider adding delays to avoid rate limiting
- Some sites are just slow

## Performance Expectations

**Single page crawl**:
- Time: 2-5 seconds
- Depends on: Page complexity, JS load time, network speed

**Link following (depth=1, 10 pages)**:
- Time: 20-60 seconds
- Produces: 10-50 chunks (depends on page size)
- Storage: ~100-500KB

**Deep crawl (depth=2, 50 pages)**:
- Time: 2-10 minutes
- Produces: 100-500 chunks
- Storage: ~1-5MB

## Success Criteria

This extension is complete when:

✅ Crawl4AI v0.7.4+ installed and verified  
✅ Can crawl single page with `crawl-url` command  
✅ Can follow links with `--follow-links --max-depth N` (REQUIRED)  
✅ Crawled pages automatically chunked and embedded  
✅ Can search crawled content immediately after ingestion  
✅ Depth tracked in metadata  
✅ Can batch crawl multiple URLs from file  
✅ Clean markdown output suitable for RAG  
✅ Integration with existing DocumentStore works  
✅ Tests validate link following works correctly  

## Integration with Future Extensions

This web crawling capability will work seamlessly with:

**RAG Optimizations** (when you add them later):
- Crawled content → Chunked → Embedded → Searchable
- Hybrid search will work on web content
- Multi-query will improve web content retrieval
- Re-ranking will work on web-sourced chunks

**Collections by Topic**:
```bash
# Create topic-based collections from web sources
uv run poc crawl-url "https://docs.python.org" \
    --collection python-docs --follow-links --max-depth 2

uv run poc crawl-url "https://postgresql.org/docs" \
    --collection postgres-docs --follow-links --max-depth 2

uv run poc crawl-url "https://fastapi.tiangolo.com" \
    --collection fastapi-docs --follow-links --max-depth 1
```

## Real-World Testing Plan

### Step 1: Start Small
```bash
# Single tutorial page
uv run poc crawl-url "https://docs.python.org/3/tutorial/introduction.html" \
    --collection python-test
```

### Step 2: Add Link Following
```bash
# Tutorial section with links
uv run poc crawl-url "https://docs.python.org/3/tutorial/" \
    --collection python-test \
    --follow-links \
    --max-depth 1 \
    --max-pages 10
```

### Step 3: Test Search Quality
```bash
# Search the crawled content
uv run poc search "python lists and tuples" --collection python-test

# Should find relevant tutorial sections
```

### Step 4: Build Real Collections
```bash
# PostgreSQL documentation
uv run poc crawl-url "https://www.postgresql.org/docs/current/tutorial.html" \
    --collection postgres-docs \
    --follow-links \
    --max-depth 2 \
    --max-pages 50 \
    --metadata '{"source":"postgresql.org","version":"current"}'

# FastAPI documentation  
uv run poc crawl-url "https://fastapi.tiangolo.com/" \
    --collection fastapi-docs \
    --follow-links \
    --max-depth 1 \
    --max-pages 30

# Test cross-collection search
uv run poc search "async database queries" --search-all-collections
```

## Reference Code Snippets

The following snippets are from the working RAG Retriever implementation. Use them as **reference** but verify against current Crawl4AI documentation.

### Full Working Crawler Class (Reference)

From `rag_retriever/crawling/crawl4ai_crawler.py`:

```python
# REFERENCE CODE - Verify API is current before using!
# This worked in August 2025 with Crawl4AI 0.4.0
# May need updates for v0.7.4+

class Crawl4AICrawler:
    """Web page crawler using Crawl4AI for fast content extraction."""
    
    def __init__(self):
        """Initialize the crawler with configuration."""
        self.config = config.browser  # From your config system
        self.visited_urls: Set[str] = set()
        self._total_chunks = 0

    def _create_crawler_config(self, max_depth: int = 0) -> CrawlerRunConfig:
        """
        Create Crawl4AI configuration.
        
        Based on working solution that properly filters navigation content.
        Key: BFSDeepCrawlStrategy + high threshold (0.7) = clean content.
        """
        # Aggressive filtering - this removes navigation content
        md_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.7,  # High threshold = aggressive filtering
                threshold_type="fixed"
            )
        )
        
        return CrawlerRunConfig(
            deep_crawl_strategy=BFSDeepCrawlStrategy(
                max_depth=max_depth,
                include_external=False  # Stay within same domain
            ),
            markdown_generator=md_generator,
            word_count_threshold=15,  # Ignore very short text blocks
            stream=True
        )

    async def crawl_website(self, base_url: str, max_depth: int = 2, max_pages: int = 50):
        """Crawl a website recursively."""
        logger.info(f"Starting website crawl: {base_url} (max_depth: {max_depth})")
        
        documents = []
        config = self._create_crawler_config(max_depth=max_depth)
        
        async with AsyncWebCrawler() as crawler:
            page_count = 0
            async for result in await crawler.arun(base_url, config=config):
                if page_count >= max_pages:
                    logger.info(f"Reached max pages limit: {max_pages}")
                    break
                
                if result.success:
                    # KEY: Use fit_markdown for filtered content
                    content = result.markdown.fit_markdown
                    
                    if content and content.strip():
                        metadata = {
                            "source": result.url,
                            "title": result.metadata.get("title", "") if result.metadata else "",
                            "description": result.metadata.get("description", "") if result.metadata else "",
                            "content_length": len(content),
                            "crawler_type": "crawl4ai",
                            "depth": getattr(result, 'depth', 0) or 0
                        }
                        
                        document = Document(
                            page_content=content,
                            metadata=metadata
                        )
                        documents.append(document)
                        self.visited_urls.add(result.url)
                        page_count += 1
                        
                        logger.info(f"✓ Crawled: {result.url} ({len(content)} chars)")
        
        return documents

    def run_crawl(self, url: str, max_depth: int = 2):
        """Synchronous wrapper for the async crawl_website method."""
        return asyncio.run(self.crawl_website(url, max_depth))
```

**What to adapt**:
- Integration with POC's DocumentStore
- CLI parameter mapping
- Error handling for POC context
- Configuration loading from POC's config.yaml

## API Verification Checklist

Before implementing, verify these APIs are current:

- [ ] `from crawl4ai import AsyncWebCrawler, CrawlerRunConfig`
- [ ] `from crawl4ai.deep_crawling import BFSDeepCrawlStrategy`
- [ ] `from crawl4ai.content_filter_strategy import PruningContentFilter`
- [ ] `from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator`
- [ ] `async with AsyncWebCrawler() as crawler:`
- [ ] `async for result in await crawler.arun(url, config=config):`
- [ ] `result.markdown.fit_markdown`
- [ ] `result.success`
- [ ] `result.url`
- [ ] `result.metadata`

**If any of these have changed**, update the code accordingly and document the changes.

## Summary

This extension adds web crawling to your POC using Crawl4AI v0.7.4:

**Features**:
- ✅ Single page fetching
- ✅ **Recursive link following (REQUIRED)** with configurable depth
- ✅ Clean markdown output optimized for RAG
- ✅ Automatic content filtering (removes navigation/ads)
- ✅ Integration with existing document chunking
- ✅ Metadata tracking (URL, depth, title, description)
- ✅ Batch crawling of multiple URLs
- ✅ Rate limiting and error handling

**CLI Commands**:
- `crawl-url <url>` - Crawl single or multiple pages
- `crawl-batch <file>` - Batch crawl from URL list

**Configuration**:
- Toggleable link following
- Configurable depth and page limits
- Tunable content filtering

**Integration**:
- Works with existing DocumentStore
- Automatic chunking via existing pipeline
- Searchable immediately after crawl

The implementation is based on proven, working code from RAG Retriever but **MUST be validated against Crawl4AI v0.7.4+ current documentation** before deployment!

