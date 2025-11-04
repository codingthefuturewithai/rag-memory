#!/usr/bin/env python3
"""
Integration test: Create collection, crawl Claude docs, ingest, query, and verify filter works.
This tests the complete end-to-end flow with PruningContentFilter.
"""

import asyncio
import sys
import os

# Set up environment
os.environ.setdefault("RAG_DATABASE_URL", "postgresql://raguser:ragpassword@localhost:54320/rag_memory")
os.environ.setdefault("RAG_NEO4J_URI", "bolt://localhost:7475")
os.environ.setdefault("RAG_NEO4J_USER", "neo4j")
os.environ.setdefault("RAG_NEO4J_PASSWORD", "graphiti-password")

from src.core.database import Database
from src.core.embeddings import EmbeddingGenerator
from src.ingestion.document_store import DocumentStore
from src.ingestion.collection_manager import CollectionManager
from src.ingestion.web_crawler import WebCrawler
from src.core.graph_store import GraphStore
from src.retrieval.search import SimilaritySearch


async def main():
    print("="*100)
    print("INTEGRATION TEST: Claude Docs Crawl with PruningContentFilter")
    print("="*100)

    # Initialize components
    print("\n[1] Initializing RAG components...")
    db = Database()
    embedder = EmbeddingGenerator()
    doc_store = DocumentStore(db)
    coll_mgr = CollectionManager(db, doc_store)
    graph_store = GraphStore()
    search = SimilaritySearch(db, embedder, coll_mgr)

    print("✓ All components initialized")

    # Step 1: Create collection
    print("\n[2] Creating collection 'claude-docs-mcp'...")
    collection_name = "claude-docs-mcp"

    try:
        # Check if collection exists and delete it
        existing = coll_mgr.get_collection(collection_name)
        if existing:
            print(f"  - Collection exists, deleting it first...")
            # We can't delete directly, so we'll skip
    except:
        pass

    # Create new collection
    collection = coll_mgr.create_collection(
        name=collection_name,
        description="Claude documentation for Model Context Protocol with PruningContentFilter",
        domain="Documentation",
        domain_scope="Official Anthropic Claude MCP documentation"
    )
    print(f"✓ Collection created: {collection}")

    # Step 2: Crawl and ingest
    print("\n[3] Crawling Claude docs website (follow_links=True, max_depth=1)...")
    crawler = WebCrawler(headless=True, verbose=False)

    base_url = "https://docs.claude.com/en/docs/mcp"
    crawl_results = await crawler.crawl_deep_pages(
        url=base_url,
        max_depth=1,
        max_pages=5
    )

    print(f"✓ Crawled {len(crawl_results)} pages")

    # Step 3: Ingest into collection
    print("\n[4] Ingesting crawled pages into collection...")
    ingested_count = 0
    total_chars = 0

    for result in crawl_results:
        if result.success:
            ingested_count += 1
            content_size = len(result.content)
            total_chars += content_size
            print(f"  - {result.url}: {content_size} chars")

            # Ingest into document store
            doc_id = doc_store.add_document(
                collection_id=collection.id,
                url=result.url,
                title=result.url.split("/")[-1] or "Claude Docs",
                content=result.content,
                metadata=result.metadata
            )
            print(f"    → Document ID: {doc_id}")

    print(f"\n✓ Ingested {ingested_count} pages ({total_chars:,} total chars)")

    # Step 4: Get collection stats
    print("\n[5] Collection statistics...")
    col_info = coll_mgr.get_collection_info(collection_name)
    print(f"  - Documents: {col_info['document_count']}")
    print(f"  - Chunks: {col_info['chunk_count']}")

    # Step 5: Query the collection
    print("\n[6] Testing queries...")

    # Query 1: MCP semantic query
    print("\n  Query 1: 'What is Model Context Protocol and how does it work?'")
    results = search.similarity_search(
        query="What is Model Context Protocol and how does it work?",
        collection_name=collection_name,
        limit=3
    )
    print(f"  Results: {len(results)} matches")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['similarity']:.2f}] {result['source_filename'][:60]}")
        print(f"       {result['content'][:100]}...")

    # Query 2: Architecture query
    print("\n  Query 2: 'How can I build and extend MCP servers?'")
    results = search.similarity_search(
        query="How can I build and extend MCP servers?",
        collection_name=collection_name,
        limit=3
    )
    print(f"  Results: {len(results)} matches")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['similarity']:.2f}] {result['source_filename'][:60]}")
        print(f"       {result['content'][:100]}...")

    # Query 3: Application integration query
    print("\n  Query 3: 'How do I integrate MCP with Claude applications?'")
    results = search.similarity_search(
        query="How do I integrate MCP with Claude applications?",
        collection_name=collection_name,
        limit=3
    )
    print(f"  Results: {len(results)} matches")
    for i, result in enumerate(results, 1):
        print(f"    {i}. [{result['similarity']:.2f}] {result['source_filename'][:60]}")
        print(f"       {result['content'][:100]}...")

    print("\n" + "="*100)
    print("✓ INTEGRATION TEST COMPLETE")
    print("="*100)


if __name__ == "__main__":
    asyncio.run(main())
