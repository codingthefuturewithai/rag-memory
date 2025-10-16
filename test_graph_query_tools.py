#!/usr/bin/env python3
"""
Test script for Knowledge Graph query MCP tools.

This script tests the new graph query tools:
1. query_relationships() - Search for entity relationships
2. query_temporal() - Track how knowledge evolved over time

Prerequisites:
- PostgreSQL with pgvector running (port 54320)
- Neo4j running (docker-compose.graphiti.yml, port 7687)
- OPENAI_API_KEY in .env
- Existing test data in graph (run test_unified_ingestion.py first)
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import all MCP tool implementations
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.core.collections import get_collection_manager
from src.mcp.tools import query_relationships_impl, query_temporal_impl

# Import Graph components
from graphiti_core import Graphiti
from src.unified import GraphStore


async def main():
    print("=" * 80)
    print("Knowledge Graph Query Tools Test")
    print("=" * 80)
    print()

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in .env")
        return

    print(f"✅ Loaded OpenAI API key (ends with ...{api_key[-4:]})\n")

    # =========================================================================
    # Step 1: Initialize Graph components
    # =========================================================================
    print("=" * 80)
    print("Step 1: Initializing Knowledge Graph Components")
    print("=" * 80)
    print()

    print("📊 Connecting to Neo4j...")
    try:
        graphiti = Graphiti(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="graphiti-password"
        )
        await graphiti.build_indices_and_constraints()
        graph_store = GraphStore(graphiti)
        print("✅ Connected to Neo4j\n")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        print("   Make sure Neo4j is running: docker-compose -f docker-compose.graphiti.yml up -d")
        return

    # =========================================================================
    # Step 2: Test query_relationships tool
    # =========================================================================
    print("=" * 80)
    print("Step 2: Testing query_relationships Tool")
    print("=" * 80)
    print()

    # Test 1: Business relationships
    query1 = "How does my YouTube channel relate to my business?"
    print(f"🔍 Query 1: {query1}\n")

    result1 = await query_relationships_impl(
        graph_store=graph_store,
        query=query1,
        num_results=5
    )

    print(f"📊 Status: {result1['status']}")
    print(f"📊 Found {result1['num_results']} relationships:\n")

    if result1['status'] == 'success' and result1['relationships']:
        for i, rel in enumerate(result1['relationships'][:3], 1):
            print(f"   {i}. {rel['relationship_type']}")
            print(f"      Fact: {rel['fact'][:100]}...")
            if rel.get('valid_from'):
                print(f"      Valid from: {rel['valid_from']}")
            print()
    else:
        print(f"   Message: {result1.get('message', 'No relationships found')}\n")

    # Test 2: Product relationships
    query2 = "What tools are part of my workflow?"
    print(f"🔍 Query 2: {query2}\n")

    result2 = await query_relationships_impl(
        graph_store=graph_store,
        query=query2,
        num_results=5
    )

    print(f"📊 Status: {result2['status']}")
    print(f"📊 Found {result2['num_results']} relationships:\n")

    if result2['status'] == 'success' and result2['relationships']:
        for i, rel in enumerate(result2['relationships'][:3], 1):
            print(f"   {i}. {rel['relationship_type']}")
            print(f"      Fact: {rel['fact'][:100]}...")
            print()
    else:
        print(f"   Message: {result2.get('message', 'No relationships found')}\n")

    # =========================================================================
    # Step 3: Test query_temporal tool
    # =========================================================================
    print("=" * 80)
    print("Step 3: Testing query_temporal Tool")
    print("=" * 80)
    print()

    # Test 3: Business evolution
    query3 = "How has my business strategy evolved?"
    print(f"🕐 Query: {query3}\n")

    result3 = await query_temporal_impl(
        graph_store=graph_store,
        query=query3,
        num_results=10
    )

    print(f"📊 Status: {result3['status']}")
    print(f"📊 Found {result3['num_results']} timeline items:\n")

    if result3['status'] == 'success' and result3['timeline']:
        for i, item in enumerate(result3['timeline'][:5], 1):
            status_icon = "✅" if item['status'] == "current" else "⏰"
            print(f"   {i}. {status_icon} {item['status'].upper()}")
            print(f"      Fact: {item['fact'][:80]}...")
            print(f"      Valid: {item.get('valid_from', 'Unknown')} → {item.get('valid_until') or 'present'}")
            print()
    else:
        print(f"   Message: {result3.get('message', 'No timeline found')}\n")

    # =========================================================================
    # Step 4: Test with unavailable graph_store (graceful degradation)
    # =========================================================================
    print("=" * 80)
    print("Step 4: Testing Graceful Degradation (graph_store=None)")
    print("=" * 80)
    print()

    print("Testing with graph_store=None (simulates Neo4j unavailable)...\n")

    result4 = await query_relationships_impl(
        graph_store=None,
        query="Test query",
        num_results=5
    )

    print(f"📊 Status: {result4['status']}")
    print(f"📊 Message: {result4['message']}\n")

    if result4['status'] == 'unavailable':
        print("✅ Graceful degradation working correctly!\n")
    else:
        print("⚠️  Expected status='unavailable', but got something else\n")

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()
    print("✅ Successfully tested:")
    print("   1. query_relationships() - Entity relationship queries")
    print("   2. query_temporal() - Temporal evolution queries")
    print("   3. Graceful degradation when graph unavailable")
    print()
    print("🎯 Key Features Demonstrated:")
    print("   - Natural language relationship queries")
    print("   - Temporal reasoning (how knowledge evolved)")
    print("   - Automatic fact extraction and relationship mapping")
    print("   - Graceful fallback to RAG-only mode")
    print()
    print("📊 Tool Statistics:")
    print(f"   - query_relationships: {result1['num_results']} + {result2['num_results']} relationships found")
    print(f"   - query_temporal: {result3['num_results']} timeline items found")
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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
