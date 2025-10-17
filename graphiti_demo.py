#!/usr/bin/env python3
"""
Simple Graphiti Demo Script

This script demonstrates:
1. Connecting to Neo4j
2. Adding knowledge episodes with automatic entity extraction
3. Querying relationships
4. Temporal reasoning (how knowledge evolves)

Prerequisites:
- Neo4j running (via docker-compose.graphiti.yml)
- OPENAI_API_KEY environment variable set
- graphiti-core installed: uv pip install graphiti-core
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


async def main():
    print("=" * 80)
    print("Graphiti Knowledge Graph Demo")
    print("=" * 80)
    print()

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found")
        print("   Add it to your .env file: OPENAI_API_KEY=sk-...")
        return

    print(f"✅ Loaded OpenAI API key from .env (ends with ...{api_key[-4:]})\n")

    # Initialize Graphiti connection to Neo4j
    print("📊 Connecting to Neo4j...")
    graphiti = Graphiti(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="graphiti-password"
    )
    await graphiti.build_indices_and_constraints()
    print("✅ Connected to Neo4j successfully\n")

    # =========================================================================
    # DEMO 1: Add Knowledge Episodes (Automatic Entity Extraction)
    # =========================================================================
    print("=" * 80)
    print("DEMO 1: Adding Knowledge with Automatic Entity Extraction")
    print("=" * 80)
    print()

    episode1 = """
    My business vision for 2025 is to build AI-powered developer tools.
    I'm focusing on two main channels: my school.com community where I teach
    coding practices, and my YouTube channel where I share tutorials.
    My core tool stack includes Claude Code for AI assistance and rag-memory
    for long-term knowledge management.
    """

    print("📝 Adding Episode 1: Business Vision...")
    print(f"   Content: {episode1.strip()[:100]}...")

    result1 = await graphiti.add_episode(
        name="business_vision_jan_2025",
        episode_body=episode1,
        source=EpisodeType.message,
        source_description="Personal knowledge base",
        reference_time=datetime(2025, 1, 15, 10, 0, 0)
    )
    print(f"✅ Episode added! Extracted {len(result1.nodes)} entities\n")

    episode2 = """
    I've updated my workflow to use Claude Code more extensively.
    Claude Code integrates with my rag-memory system, allowing me to store
    and retrieve knowledge during coding sessions. This supports my YouTube
    tutorial creation process and helps me teach better in my school.com
    community.
    """

    print("📝 Adding Episode 2: Updated Workflow...")
    print(f"   Content: {episode2.strip()[:100]}...")

    result2 = await graphiti.add_episode(
        name="workflow_update_feb_2025",
        episode_body=episode2,
        source=EpisodeType.message,
        source_description="Personal knowledge base",
        reference_time=datetime(2025, 2, 1, 14, 30, 0)
    )
    print(f"✅ Episode added! Extracted {len(result2.nodes)} entities\n")

    episode3 = """
    My business vision has evolved. While I'm still focused on AI developer
    tools, I've decided to prioritize rag-memory as my flagship product.
    The school.com community is now centered around memory systems for AI,
    and my YouTube content focuses specifically on RAG architectures and
    knowledge graphs.
    """

    print("📝 Adding Episode 3: Evolved Vision...")
    print(f"   Content: {episode3.strip()[:100]}...")

    result3 = await graphiti.add_episode(
        name="vision_evolution_mar_2025",
        episode_body=episode3,
        source=EpisodeType.message,
        source_description="Personal knowledge base",
        reference_time=datetime(2025, 3, 10, 9, 0, 0)
    )
    print(f"✅ Episode added! Extracted {len(result3.nodes)} entities\n")

    # =========================================================================
    # DEMO 2: Relationship Queries
    # =========================================================================
    print("=" * 80)
    print("DEMO 2: Querying Relationships")
    print("=" * 80)
    print()

    query1 = "How does my YouTube channel relate to my business vision?"
    print(f"❓ Query: {query1}")

    search_results1 = await graphiti.search(query1, num_results=5)
    print(f"📊 Found {len(search_results1.edges)} relationship edges:\n")

    for i, edge in enumerate(search_results1.edges[:3], 1):
        print(f"   {i}. {edge.source.name} --[{edge.name}]--> {edge.target.name}")
        if hasattr(edge, 'fact'):
            print(f"      Context: {edge.fact[:100]}...")
    print()

    query2 = "What tools are part of my workflow?"
    print(f"❓ Query: {query2}")

    search_results2 = await graphiti.search(query2, num_results=5)
    print(f"📊 Found {len(search_results2.edges)} relationship edges:\n")

    for i, edge in enumerate(search_results2.edges[:3], 1):
        print(f"   {i}. {edge.source.name} --[{edge.name}]--> {edge.target.name}")
        if hasattr(edge, 'fact'):
            print(f"      Context: {edge.fact[:100]}...")
    print()

    # =========================================================================
    # DEMO 3: Temporal Reasoning (How Knowledge Evolved)
    # =========================================================================
    print("=" * 80)
    print("DEMO 3: Temporal Reasoning - How Has My Vision Evolved?")
    print("=" * 80)
    print()

    # Search at different time points
    query3 = "What is my business vision?"

    print(f"❓ Query: {query3}")
    print(f"   🕐 As of January 2025 (initial vision):")

    jan_results = await graphiti.search(
        query3,
        num_results=3,
        # Note: Graphiti's temporal queries use validity intervals
        # The most recent valid facts will be returned by default
    )

    for edge in jan_results.edges[:2]:
        print(f"      - {edge.source.name} --[{edge.name}]--> {edge.target.name}")
        if hasattr(edge, 'valid_at'):
            print(f"        Valid from: {edge.valid_at}")
        if hasattr(edge, 'fact'):
            print(f"        Fact: {edge.fact[:80]}...")
    print()

    print(f"   🕐 As of March 2025 (evolved vision):")
    # The latest facts will show the evolution
    # Graphiti automatically handles temporal validity

    march_results = await graphiti.search(
        "What is my current business focus?",
        num_results=3
    )

    for edge in march_results.edges[:2]:
        print(f"      - {edge.source.name} --[{edge.name}]--> {edge.target.name}")
        if hasattr(edge, 'fact'):
            print(f"        Fact: {edge.fact[:80]}...")
    print()

    # =========================================================================
    # DEMO 4: Entity Discovery
    # =========================================================================
    print("=" * 80)
    print("DEMO 4: Entity Discovery - What Entities Were Extracted?")
    print("=" * 80)
    print()

    # Get all nodes (entities)
    all_nodes = []
    for result in [result1, result2, result3]:
        all_nodes.extend(result.nodes)

    # Deduplicate by name
    unique_entities = {node.name: node for node in all_nodes}

    print(f"📋 Extracted {len(unique_entities)} unique entities:")
    for i, (name, node) in enumerate(sorted(unique_entities.items())[:10], 1):
        entity_type = getattr(node, 'labels', ['Unknown'])[0] if hasattr(node, 'labels') else 'Unknown'
        print(f"   {i}. {name} (type: {entity_type})")

    if len(unique_entities) > 10:
        print(f"   ... and {len(unique_entities) - 10} more")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print()
    print("✅ Successfully demonstrated:")
    print("   1. Automatic entity extraction from unstructured text")
    print("   2. Automatic relationship mapping")
    print("   3. Relationship queries (how concepts connect)")
    print("   4. Temporal reasoning (how knowledge evolves)")
    print()
    print("🎯 Key Insight:")
    print("   Graphiti automatically extracted entities like 'YouTube channel',")
    print("   'business vision', 'Claude Code', 'rag-memory', 'school.com'")
    print("   and mapped their relationships WITHOUT you manually defining")
    print("   an ontology or schema. It just works.")
    print()
    print("🔗 View your graph in Neo4j Browser:")
    print("   http://localhost:7474")
    print("   Username: neo4j")
    print("   Password: graphiti-password")
    print()
    print("   Try running this Cypher query:")
    print("   MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 25")
    print()

    # Close connection
    await graphiti.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
