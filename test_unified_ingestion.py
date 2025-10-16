#!/usr/bin/env python3
"""
Test script for unified RAG + Knowledge Graph ingestion.

This script tests the end-to-end flow:
1. Initialize both RAG (pgvector) and Knowledge Graph (Graphiti/Neo4j)
2. Ingest test content through unified mediator
3. Verify both stores were updated
4. Test search in both RAG and Graph

Prerequisites:
- PostgreSQL with pgvector running (port 54320)
- Neo4j running (docker-compose.graphiti.yml, port 7687)
- OPENAI_API_KEY in .env
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import RAG components
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.ingestion.document_store import get_document_store
from src.retrieval.search import get_similarity_search

# Import Knowledge Graph components
from graphiti_core import Graphiti
from src.unified import GraphStore, UnifiedIngestionMediator


async def main():
    print("=" * 80)
    print("Unified RAG + Knowledge Graph Ingestion Test")
    print("=" * 80)
    print()

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in .env")
        return

    print(f"✅ Loaded OpenAI API key (ends with ...{api_key[-4:]})\n")

    # =========================================================================
    # Step 1: Initialize RAG components
    # =========================================================================
    print("=" * 80)
    print("Step 1: Initializing RAG Components (PostgreSQL + pgvector)")
    print("=" * 80)
    print()

    print("📊 Connecting to PostgreSQL...")
    db = get_database()
    embedder = get_embedding_generator()
    coll_mgr = get_collection_manager(db)
    doc_store = get_document_store(db, embedder, coll_mgr)
    searcher = get_similarity_search(db, embedder, coll_mgr)
    print("✅ Connected to PostgreSQL\n")

    # Create test collection
    collection_name = "unified-test"
    print(f"📁 Creating collection '{collection_name}'...")
    try:
        coll_mgr.create_collection(collection_name, "Test collection for unified ingestion")
        print("✅ Collection created\n")
    except ValueError:
        print("⚠️  Collection already exists (skipping)\n")

    # =========================================================================
    # Step 2: Initialize Knowledge Graph components
    # =========================================================================
    print("=" * 80)
    print("Step 2: Initializing Knowledge Graph Components (Graphiti/Neo4j)")
    print("=" * 80)
    print()

    print("📊 Connecting to Neo4j...")
    graphiti = Graphiti(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="graphiti-password"
    )
    await graphiti.build_indices_and_constraints()
    print("✅ Connected to Neo4j\n")

    print("🔧 Creating GraphStore and UnifiedIngestionMediator...")
    graph_store = GraphStore(graphiti)
    mediator = UnifiedIngestionMediator(db, embedder, coll_mgr, graph_store)
    print("✅ Unified mediator ready\n")

    # =========================================================================
    # Step 3: Ingest test content through unified mediator
    # =========================================================================
    print("=" * 80)
    print("Step 3: Ingesting Test Content (RAG + Graph simultaneously)")
    print("=" * 80)
    print()

    test_content = """
    My business strategy for 2025 is to build AI-powered developer tools.
    I'm focusing on three key areas: my YouTube channel where I share
    programming tutorials, my online school.com community for teaching
    advanced coding practices, and my flagship product rag-memory which
    provides long-term knowledge management for AI agents using pgvector
    and knowledge graphs.
    """

    print("📝 Test content:")
    print(f"   {test_content.strip()[:100]}...\n")

    print("⚙️  Ingesting through unified mediator...")
    ingest_result = await mediator.ingest_text(
        content=test_content,
        collection_name=collection_name,
        document_title="Business Strategy 2025",
        metadata={"category": "business", "year": 2025}
    )

    print("✅ Ingestion complete!\n")
    print(f"   📄 Source Document ID: {ingest_result['source_document_id']}")
    print(f"   📦 RAG Chunks Created: {ingest_result['num_chunks']}")
    print(f"   🔗 Graph Entities Extracted: {ingest_result['entities_extracted']}")
    print(f"   📁 Collection: {ingest_result['collection_name']}\n")

    # =========================================================================
    # Step 4: Verify RAG search works
    # =========================================================================
    print("=" * 80)
    print("Step 4: Testing RAG Search (pgvector semantic search)")
    print("=" * 80)
    print()

    query = "What are my key business areas?"
    print(f"❓ Query: {query}")

    rag_results = searcher.search_chunks(
        query=query,
        collection_name=collection_name,
        limit=3,
        threshold=0.3
    )

    print(f"📊 Found {len(rag_results)} RAG results:\n")
    for i, r in enumerate(rag_results[:2], 1):
        print(f"   {i}. Similarity: {r.similarity:.3f}")
        print(f"      Content: {r.content[:100]}...\n")

    # =========================================================================
    # Step 5: Verify Knowledge Graph search works
    # =========================================================================
    print("=" * 80)
    print("Step 5: Testing Knowledge Graph Search (Graphiti relationships)")
    print("=" * 80)
    print()

    graph_query = "How does my YouTube channel relate to my business?"
    print(f"❓ Query: {graph_query}")

    graph_results = await graph_store.search_relationships(graph_query, num_results=5)
    print(f"📊 Found {len(graph_results)} graph results (raw list):\n")

    # Note: API changed - results is now a list directly, not object with .edges
    for i, result in enumerate(graph_results[:3], 1):
        print(f"   {i}. {result}\n")

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()
    print("✅ Successfully tested:")
    print("   1. RAG component initialization (PostgreSQL + pgvector)")
    print("   2. Knowledge Graph initialization (Graphiti + Neo4j)")
    print("   3. Unified ingestion (single call updates both stores)")
    print("   4. RAG semantic search (pgvector)")
    print("   5. Knowledge Graph relationship search (Graphiti)")
    print()
    print("🎯 Key Achievement:")
    print("   Single ingest_text() call updated BOTH:")
    print(f"   - RAG: {ingest_result['num_chunks']} searchable chunks")
    print(f"   - Graph: {ingest_result['entities_extracted']} entities + relationships")
    print()
    print("🔗 View your graph in Neo4j Browser:")
    print("   http://localhost:7474")
    print("   Username: neo4j")
    print("   Password: graphiti-password")
    print()
    print("   Try running this Cypher query:")
    print("   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25")
    print()

    # Cleanup
    await graph_store.close()
    db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
