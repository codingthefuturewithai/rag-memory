#!/usr/bin/env python3
"""Test PruningContentFilter implementation."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from graphiti_core import Graphiti
from src.database import Database
from src.unified.graph_store import GraphStore
from src.core.collections import CollectionManager
from src.core.config_loader import load_environment_variables
from src.ingestion.web_crawler import WebCrawler


async def main():
    # Load environment variables from config
    load_environment_variables()
    print("=" * 80)
    print("Testing PruningContentFilter Implementation")
    print("=" * 80)

    # Initialize components
    print("\n1. Initializing components...")
    db = Database()

    # Initialize Graphiti
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

    graphiti = Graphiti(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password
    )

    graph = GraphStore(graphiti)
    cm = CollectionManager(db, graph)

    # Create collection
    print("\n2. Creating test collection...")
    collection_name = "python_docs_test_filtered"
    try:
        result = cm.create_collection(
            name=collection_name,
            description="Testing PruningContentFilter with Python documentation crawl",
            domain="Documentation",
            domain_scope="Python official documentation for testing content filtering"
        )
        print(f"   Collection created: {result}")
    except Exception as e:
        print(f"   Collection may already exist: {e}")

    # Initialize WebCrawler
    print("\n3. Initializing WebCrawler...")
    print("   Looking for PruningContentFilter initialization...")
    crawler = WebCrawler(db, graph)
    print(f"   WebCrawler initialized successfully")

    # Test single page crawl
    print("\n4. Testing single page crawl...")
    test_url = "https://docs.python.org/3/tutorial/index.html"
    print(f"   Crawling: {test_url}")

    try:
        pages = await crawler.crawl_website(
            base_url=test_url,
            follow_links=False,
            max_pages=1
        )

        print(f"\n5. Crawl Results:")
        print(f"   Pages crawled: {len(pages)}")

        if pages:
            page = pages[0]
            print(f"\n   Page Details:")
            print(f"   - URL: {page['url']}")
            print(f"   - Title: {page['title']}")
            print(f"   - Content length: {len(page['content'])} chars")
            print(f"   - Metadata: {page['metadata']}")

            # Show first 500 chars of content
            print(f"\n   Content Preview (first 500 chars):")
            print(f"   {page['content'][:500]}")
            print("   ...")

            # Check for filtering metadata
            if 'filtered' in page['metadata']:
                print(f"\n   ✓ PruningContentFilter was applied!")
                print(f"     - filtered: {page['metadata']['filtered']}")
                print(f"     - content_type: {page['metadata'].get('content_type', 'N/A')}")
            else:
                print(f"\n   ✗ No filtering metadata found")

        # Ingest the page
        print("\n6. Ingesting page into collection...")
        if pages:
            page = pages[0]
            result = await crawler.ingest_crawled_pages(
                pages=pages,
                collection_name=collection_name,
                base_metadata={"test": "pruning_filter"}
            )
            print(f"   Ingestion result: {result}")

            # Query documents
            print("\n7. Verifying ingestion...")
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, filename, metadata
                        FROM source_documents
                        WHERE filename LIKE %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (f"%{test_url}%",))
                    doc = cur.fetchone()

                    if doc:
                        print(f"   Document found in database:")
                        print(f"   - ID: {doc[0]}")
                        print(f"   - Filename: {doc[1]}")
                        print(f"   - Metadata: {doc[2]}")
                    else:
                        print(f"   ✗ Document not found in database")

        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error during crawl: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
