#!/usr/bin/env python3
"""
Test script to verify startup validations work correctly.

This tests the schema validation methods without requiring full server startup.
"""

import asyncio
import sys
import logging
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.database import Database
from src.unified.graph_store import GraphStore

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_postgresql_validation():
    """Test PostgreSQL schema validation."""
    logger.info("=" * 60)
    logger.info("Testing PostgreSQL Schema Validation")
    logger.info("=" * 60)

    try:
        db = Database()

        # Try health check first
        logger.info("\n1. Testing PostgreSQL health check...")
        health = await db.health_check()
        logger.info(f"   Status: {health['status']}")
        logger.info(f"   Latency: {health['latency_ms']}ms")
        if health['error']:
            logger.warning(f"   Error: {health['error']}")
            logger.info("   ⚠️ PostgreSQL not running - cannot test schema validation")
            return False

        # Try schema validation
        logger.info("\n2. Testing PostgreSQL schema validation...")
        validation = await db.validate_schema()

        logger.info(f"   Status: {validation['status']}")
        logger.info(f"   Latency: {validation['latency_ms']}ms")
        logger.info(f"   Tables found: {3 - len(validation['missing_tables'])}/3")

        if validation['missing_tables']:
            logger.warning(f"   Missing tables: {validation['missing_tables']}")

        logger.info(f"   pgvector loaded: {'✓' if validation['pgvector_loaded'] else '✗'}")
        logger.info(f"   HNSW indexes: {validation['hnsw_indexes']}/2")

        if validation['errors']:
            logger.warning("   Validation errors:")
            for error in validation['errors']:
                logger.warning(f"     - {error}")

        logger.info(f"\n   Result: {'✅ VALID' if validation['status'] == 'valid' else '❌ INVALID'}")
        return validation['status'] == 'valid'

    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.mark.asyncio
async def test_neo4j_validation():
    """Test Neo4j schema validation."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Neo4j Schema Validation")
    logger.info("=" * 60)

    try:
        from graphiti_core import Graphiti
        import os

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        logger.info(f"\nConnecting to Neo4j at {neo4j_uri}...")
        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        graph_store = GraphStore(graphiti)

        # Try health check first
        logger.info("\n1. Testing Neo4j health check...")
        health = await graph_store.health_check()
        logger.info(f"   Status: {health['status']}")
        logger.info(f"   Latency: {health['latency_ms']}ms")
        if health['error']:
            logger.warning(f"   Error: {health['error']}")
            logger.info("   ⚠️ Neo4j not running - cannot test schema validation")
            await graphiti.close()
            return False

        # Try schema validation
        logger.info("\n2. Testing Neo4j schema validation...")
        validation = await graph_store.validate_schema()

        logger.info(f"   Status: {validation['status']}")
        logger.info(f"   Latency: {validation['latency_ms']}ms")
        logger.info(f"   Indexes found: {validation['indexes_found']}")
        logger.info(f"   Graph queryable: {'✓' if validation['can_query_nodes'] else '✗'}")

        if validation['errors']:
            logger.warning("   Validation errors:")
            for error in validation['errors']:
                logger.warning(f"     - {error}")

        logger.info(f"\n   Result: {'✅ VALID' if validation['status'] == 'valid' else '❌ INVALID'}")

        await graphiti.close()
        return validation['status'] == 'valid'

    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all validation tests."""
    logger.info("\n" + "🚀 STARTUP VALIDATION TEST SUITE" + "\n")

    pg_result = await test_postgresql_validation()
    neo4j_result = await test_neo4j_validation()

    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    logger.info(f"PostgreSQL Validation: {'✅ PASS' if pg_result else '❌ FAIL'}")
    logger.info(f"Neo4j Validation: {'✅ PASS' if neo4j_result else '❌ FAIL'}")

    if pg_result and neo4j_result:
        logger.info("\n✅ All validations passed! Server startup checks are working correctly.")
        return 0
    else:
        logger.info("\n⚠️ Some validations failed. Check database connectivity and schema initialization.")
        logger.info("   Run 'docker-compose -f docker-compose.graphiti.yml up -d' to start databases")
        logger.info("   Run 'uv run rag init' to initialize PostgreSQL schema")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
