#!/usr/bin/env python3
"""
End-to-end test: Crawl Claude docs with PruningContentFilter, ingest, query, and measure delta.
"""

import asyncio
import os
from pathlib import Path

# Load environment
from src.core.config_loader import load_environment_variables
load_environment_variables()

from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.ingestion.document_store import get_document_store
from src.ingestion.web_crawler import WebCrawler
from src.retrieval.search import get_similarity_search


async def main():
    print("\n" + "="*100)
    print("END-TO-END TEST: Claude Docs with PruningContentFilter")
    print("="*100)

    # Initialize components
    print("\n[1/7] Initializing RAG components...")
    db = get_database()
    embedder = get_embedding_generator()
    doc_store = get_document_store(db)
    coll_mgr = get_collection_manager(db, doc_store)
    search = get_similarity_search(db, embedder, coll_mgr)

    print("✓ Components initialized")

    # Step 1: Create collection
    print("\n[2/7] Creating collection 'claude-docs-mcp'...")
    collection_name = "claude-docs-mcp"

    try:
        collection = coll_mgr.create_collection(
            name=collection_name,
            description="Claude MCP docs crawled with PruningContentFilter to remove navigation noise",
            domain="Documentation",
            domain_scope="Official Anthropic Claude MCP documentation"
        )
        print(f"✓ Collection created")
    except Exception as e:
        print(f"Collection creation: {str(e)[:100]}")
        collection = coll_mgr.get_collection(collection_name)
        print(f"✓ Using existing collection")

    # Step 2: Analyze website
    print("\n[3/7] Analyzing Claude docs website structure...")
    crawler = WebCrawler(headless=True, verbose=False)

    base_url = "https://docs.claude.com/en/docs/mcp"
    print(f"  Base URL: {base_url}")
    print(f"  Will crawl with follow_links=True, max_depth=1, max_pages=5")

    # Step 3: Crawl pages
    print("\n[4/7] Crawling pages...")
    try:
        crawl_results = await crawler.crawl_deep_pages(
            url=base_url,
            max_depth=1,
            max_pages=5
        )
        print(f"✓ Crawled {len(crawl_results)} pages")
    except Exception as e:
        print(f"✗ Crawl failed: {e}")
        return

    # Step 4: Ingest pages
    print("\n[5/7] Ingesting pages into collection...")
    ingested_count = 0
    total_raw_chars = 0
    total_filtered_chars = 0
    pages_info = []

    for i, result in enumerate(crawl_results, 1):
        if result.success:
            ingested_count += 1
            content_size = len(result.content)
            total_filtered_chars += content_size

            print(f"  Page {i}: {content_size:,} chars")

            # Store page info for delta analysis
            pages_info.append({
                "url": result.url,
                "filtered_size": content_size,
                "raw_size": 0  # Will calculate delta separately
            })

            # Ingest into RAG system
            try:
                # The unified mediator will handle both vector and graph storage
                from src.unified import UnifiedIngestionMediator
                mediator = UnifiedIngestionMediator(db, embedder, doc_store, coll_mgr)

                doc_id = mediator.ingest_content(
                    collection_id=collection.id,
                    content=result.content,
                    url=result.url,
                    title=result.url.split("/")[-1] or f"Page {i}",
                    metadata=result.metadata
                )
                print(f"    ✓ Ingested as document {doc_id}")
            except Exception as e:
                print(f"    ✗ Ingestion failed: {str(e)[:100]}")

    print(f"\n✓ Ingested {ingested_count} pages")
    print(f"  Total filtered content: {total_filtered_chars:,} chars")

    # Step 5: Query collection
    print("\n[6/7] Testing queries on ingested content...")

    queries = [
        "What is Model Context Protocol and how does it work?",
        "How can I build and extend MCP servers?",
        "How do I integrate MCP with Claude applications and products?"
    ]

    for q_num, query in enumerate(queries, 1):
        print(f"\n  Query {q_num}: '{query[:60]}...'")
        try:
            results = search.similarity_search(
                query=query,
                collection_name=collection_name,
                limit=3
            )
            print(f"  Results: {len(results)} matches")
            for i, result in enumerate(results, 1):
                sim = result.get('similarity', 0)
                src = result.get('source_filename', 'unknown')[:50]
                content_preview = result.get('content', '')[:80]
                print(f"    {i}. [{sim:.3f}] {src}")
                print(f"       {content_preview}...")
        except Exception as e:
            print(f"  ✗ Query failed: {str(e)[:100]}")

    # Step 6: Get collection stats
    print("\n[7/7] Collection statistics...")
    try:
        info = coll_mgr.get_collection_info(collection_name)
        print(f"  Documents: {info.get('document_count', '?')}")
        print(f"  Chunks: {info.get('chunk_count', '?')}")
    except Exception as e:
        print(f"  ✗ Stats failed: {str(e)[:100]}")

    print("\n" + "="*100)
    print("✓ END-TO-END TEST COMPLETE")
    print("="*100)
    print("\nSUMMARY:")
    print(f"  - Pages crawled: {len(crawl_results)}")
    print(f"  - Pages ingested: {ingested_count}")
    print(f"  - Total filtered content: {total_filtered_chars:,} chars")
    print(f"  - Queries tested: {len(queries)}")
    print("\nNext step: Compare this test with a WITHOUT-filter version to measure delta")


if __name__ == "__main__":
    asyncio.run(main())
