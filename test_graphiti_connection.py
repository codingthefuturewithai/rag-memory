#!/usr/bin/env python3
"""Quick test to verify Graphiti can connect to Neo4j"""

import asyncio
from graphiti_core import Graphiti

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


async def test_connection():
    print("Testing Graphiti connection to Neo4j...")

    try:
        graphiti = Graphiti(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="graphiti-password"
        )

        print("✅ Successfully connected to Neo4j!")
        print("   Building indices and constraints...")

        await graphiti.build_indices_and_constraints()

        print("✅ Indices and constraints built successfully!")
        print("\nGraphiti is ready to use!")
        print("\nNext step: Set OPENAI_API_KEY and run graphiti_demo.py")

        await graphiti.close()

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Is Neo4j running? Check with: docker-compose -f docker-compose.graphiti.yml ps")
        print("2. Is it healthy? Status should show '(healthy)'")
        print("3. Wait 30 seconds for Neo4j to fully start if just started")


if __name__ == "__main__":
    asyncio.run(test_connection())
