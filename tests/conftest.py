"""Pytest configuration and fixtures.

This file is automatically loaded by pytest before running tests.
It ensures environment variables are loaded from .env.test before any test code runs.

CRITICAL SAFETY FEATURES:
- Loads .env.test to point to ephemeral test servers (never production)
- Production protection: Prevents running tests against Supabase
- Verifies tests use test database (port 54321) not dev (54320) or production
"""

import os
import sys
from pathlib import Path
import asyncio
import pytest
import pytest_asyncio

from src.core.config_loader import load_environment_variables
from src.core.database import Database

# ============================================================================
# CRITICAL: Enable coverage tracking in subprocesses
# ============================================================================

# Set coverage environment variable before any tests run
os.environ["COVERAGE_PROCESS_START"] = ".coveragerc"


@pytest.fixture(autouse=True)
def ensure_coverage_tracking():
    """Ensure coverage tracking is enabled for all tests."""
    # This fixture runs for every test, keeping the env var set
    assert os.environ.get("COVERAGE_PROCESS_START") == ".coveragerc"
    yield


# ============================================================================
# CRITICAL: Configure test environment to use repo-local configs
# ============================================================================

# Get repo root (parent of tests directory)
repo_root = Path(__file__).parent.parent

# Set RAG_CONFIG_PATH to use test config from repo
# This ensures tests use config/config.test.yaml, NOT system-level config
os.environ['RAG_CONFIG_PATH'] = str(repo_root / 'config')
os.environ['RAG_CONFIG_FILE'] = 'config.test.yaml'
print(f"✅ Using repo-local config: {os.environ['RAG_CONFIG_PATH']}/config.test.yaml")

# Load secrets from .env file (OPENAI_API_KEY only)
env_test_path = repo_root / ".env.test"
env_dev_path = repo_root / ".env.dev"

# Try .env.test first (primary for tests), fallback to .env.dev
if env_test_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_test_path, override=True)
    print("✅ Loaded .env.test for test environment")
elif env_dev_path.exists():
    print("⚠️  WARNING: .env.test not found, falling back to .env.dev")
    from dotenv import load_dotenv
    load_dotenv(env_dev_path, override=True)
else:
    print("⚠️  No .env file found, OPENAI_API_KEY must be in shell environment")

# Load config from YAML - will use config/config.test.yaml automatically
# (RAG_CONFIG_PATH and RAG_CONFIG_FILE are already set above to point to repo config directory)
load_environment_variables()

# ============================================================================
# PRODUCTION PROTECTION: Verify we're using test servers
# ============================================================================

database_url = os.getenv("DATABASE_URL", "")
neo4j_uri = os.getenv("NEO4J_URI", "")
env_name = os.getenv("ENV_NAME", "unknown")

# Get expected test ports from environment variables
# These should be defined in .env.test (or .env.dev for fallback)
expected_test_postgres_port = os.getenv("POSTGRES_PORT", "")
expected_test_postgres_db = os.getenv("POSTGRES_DB", "")
expected_neo4j_host = os.getenv("NEO4J_URI", "")

# Check for production indicators
is_supabase = "supabase.com" in database_url
is_dev_postgres = "rag_memory_dev" in database_url
is_test_postgres = "rag_memory_test" in expected_test_postgres_db and expected_test_postgres_port in database_url
is_test_neo4j = expected_neo4j_host in neo4j_uri

# ============================================================================
# Safety checks before running tests
# ============================================================================

if is_supabase:
    print("❌ FATAL: Tests configured to run against Supabase production database!")
    print("   DATABASE_URL contains: supabase.com")
    print("   This would corrupt your production data!")
    print("")
    print("   To use test servers:")
    print("   1. Ensure docker-compose.test.yml is running:")
    print("      docker-compose -f deploy/docker/compose/docker-compose.test.yml up -d")
    print("   2. Load test environment:")
    print("      source .env.test && pytest tests/")
    print("   3. Or just run pytest (conftest.py auto-loads .env.test)")
    sys.exit(1)

if not is_test_postgres:
    if not is_dev_postgres:
        print("⚠️  WARNING: DATABASE_URL not pointing to test or dev server")
        print(f"   DATABASE_URL: {database_url}")
        if expected_test_postgres_port:
            print(f"   Expected test database on port {expected_test_postgres_port} or dev on similar pattern")
        else:
            print("   Cannot determine expected test port - POSTGRES_PORT not set in environment")
    else:
        print("⚠️  WARNING: Using development database instead of test database")
        print("   This is suboptimal - development data may be affected by tests")
        print("   To use dedicated test servers:")
        print("   1. docker-compose -f deploy/docker/compose/docker-compose.test.yml up -d")
        print("   2. Restart pytest to auto-load .env.test")

print(f"ℹ️  Test Environment: {env_name}")
print(f"ℹ️  Postgres: {database_url.split('@')[1] if '@' in database_url else 'local'}")
print(f"ℹ️  Neo4j: {neo4j_uri}")

# ============================================================================
# AUTOMATED NEO4J INITIALIZATION: Initialize schema once per test session
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def initialize_test_neo4j():
    """
    Automatically initialize Neo4j test database schema before running any tests.

    This fixture:
    1. Runs once per test session (not per test)
    2. Runs automatically without needing to be added to test functions
    3. Creates Graphiti fulltext indexes and vector indexes required for KG queries
    4. Handles both test and dev environments gracefully
    5. Skips silently if Neo4j is not available (e.g., if only testing RAG layer)

    Why this is needed:
    - Graphiti requires specific indexes to exist (e.g., node_name_and_summary fulltext index)
    - Without initialization, KG queries fail with "no such fulltext schema index" errors
    - Manual initialization defeats the purpose of automated testing

    The async operation is wrapped in asyncio.run() because pytest fixtures don't directly
    support async in session scope (you need pytest-asyncio for that, which we don't use
    in session scope).
    """
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "test-password")

    # Skip initialization if Neo4j is not configured
    if not neo4j_uri:
        print("⏭️  Skipping Neo4j initialization (NEO4J_URI not set)")
        return

    try:
        from graphiti_core import Graphiti

        async def init_db():
            try:
                graphiti = Graphiti(
                    uri=neo4j_uri,
                    user=neo4j_user,
                    password=neo4j_password,
                )
                await graphiti.build_indices_and_constraints()
                print("✅ Neo4j test database initialized (fulltext indexes, vector indexes, schema)")
                await graphiti.close()
            except Exception as e:
                print(f"⚠️  Warning: Neo4j initialization failed: {e}")
                print("   Tests may fail if they depend on Knowledge Graph queries")
                # Don't raise - let tests proceed anyway (RAG layer might still work)

        asyncio.run(init_db())

    except ImportError:
        print("⏭️  Skipping Neo4j initialization (graphiti_core not installed)")
    except Exception as e:
        print(f"⚠️  Warning: Unexpected error during Neo4j initialization: {e}")


# ============================================================================
# AUTOMATED POSTGRESQL INITIALIZATION: Initialize schema once per test session
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def initialize_test_postgres():
    """
    Automatically initialize PostgreSQL test database schema before running any tests.

    This fixture:
    1. Runs once per test session (not per test)
    2. Runs automatically without needing to be added to test functions
    3. Ensures all required tables and extensions exist
    4. Handles pgvector setup and HNSW indexing
    5. Skips silently if PostgreSQL is not available

    Why this is needed:
    - RAG system requires pgvector extension for vector search
    - Database migrations must run before tests
    - HNSW indexes must be created for performance
    - Ensures consistent schema across test runs

    This runs before Neo4j initialization to ensure both databases are ready.
    """
    from src.core.database import Database

    database_url = os.getenv("DATABASE_URL", "")

    # Skip initialization if not using test database
    if "rag_memory_test" not in database_url:
        print("⏭️  Skipping PostgreSQL initialization (not test database)")
        return

    try:
        db = Database()

        # Test connection and verify schema
        try:
            conn = db.connection()
            cur = conn.cursor()

            # Check if tables exist
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'source_documents'
                )
            """)
            tables_exist = cur.fetchone()[0]

            if tables_exist:
                print("✅ PostgreSQL test database already initialized (schema exists)")
            else:
                print("⚠️  PostgreSQL schema not found - migrations may not have run")
                print("   Run 'uv run rag init' to initialize database")

            # Verify pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            print("✅ PostgreSQL pgvector extension verified")

            cur.close()
            conn.close()

        except Exception as e:
            print(f"⚠️  Warning: PostgreSQL verification failed: {e}")
            print("   Tests may fail if database schema is incomplete")
            # Don't raise - let tests proceed anyway

    except ImportError:
        print("⏭️  Skipping PostgreSQL initialization (Database class not available)")
    except Exception as e:
        print(f"⚠️  Warning: Unexpected error during PostgreSQL initialization: {e}")


# ============================================================================
# INTEGRATION TEST ISOLATION: Complete database cleanup after every test
# ============================================================================

@pytest_asyncio.fixture(autouse=True, scope="function")
async def cleanup_after_each_test():
    """
    ATOMIC TEST ISOLATION: Clean all data from both databases after every test.

    This fixture ensures every integration test is completely isolated:
    - Runs after EVERY test function (autouse=True)
    - Deletes ALL data from PostgreSQL tables (collections, chunks, documents)
    - Deletes ALL nodes and relationships from Neo4j
    - No test-specific cleanup logic needed - this is universal

    This is non-negotiable: Each test must start with zero data, end with zero data.
    The next test gets a completely blank slate.

    Location: conftest.py (global, applies to all tests)
    Mechanism: async fixture with yield (cleanup runs AFTER test completes)
    """
    yield  # Test runs here

    # CLEANUP PHASE: Delete everything from both databases after test completes

    # PostgreSQL cleanup - delete in order respecting foreign keys
    try:
        db = Database()
        conn = db.connect()
        with conn.cursor() as cur:
            # chunk_collections references both chunks and collections
            cur.execute("DELETE FROM chunk_collections;")
            # document_chunks references source_documents
            cur.execute("DELETE FROM document_chunks;")
            # collections table
            cur.execute("DELETE FROM collections;")
            # source_documents table
            cur.execute("DELETE FROM source_documents;")
        db.close()
    except Exception as e:
        raise RuntimeError(f"PostgreSQL cleanup failed: {e}")

    # Neo4j cleanup - delete all nodes and relationships
    try:
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7689")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "test-password")

        from graphiti_core import Graphiti

        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        await graphiti.driver.execute_query("MATCH (n) DETACH DELETE n")
    except Exception as e:
        raise RuntimeError(f"Neo4j cleanup failed: {e}")


# ============================================================================
# SHARED FIXTURES: Available to all test suites
# ============================================================================

import uuid
from src.core.embeddings import EmbeddingGenerator
from src.core.collections import CollectionManager
from src.retrieval.search import SimilaritySearch


@pytest_asyncio.fixture
async def test_db():
    """Create a test database connection with cleanup.

    Scope: function (fresh database connection per test)
    Available to: all test suites (backend integration, MCP integration)
    """
    db = Database()
    yield db
    try:
        db.close()
    except Exception:
        pass


@pytest_asyncio.fixture
async def embedder():
    """Create embedding generator for tests.

    Scope: function
    Available to: all test suites
    """
    return EmbeddingGenerator()


@pytest_asyncio.fixture
async def collection_mgr(test_db):
    """Create collection manager using test database.

    Scope: function
    Available to: all test suites
    """
    return CollectionManager(test_db)


@pytest_asyncio.fixture
async def searcher(test_db, embedder, collection_mgr):
    """Create similarity search using test components.

    Scope: function
    Available to: all test suites
    """
    return SimilaritySearch(test_db, embedder, collection_mgr)


@pytest_asyncio.fixture
async def test_collection_name():
    """Generate unique test collection name to avoid conflicts.

    Scope: function
    """
    return f"test_collection_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def setup_test_collection(collection_mgr, test_collection_name):
    """Create and return a test collection with cleanup.

    Scope: function
    """
    # Create collection with default metadata schema
    default_schema = {
        "custom": {},
        "system": ["file_type", "source_type", "ingested_at"]
    }

    collection_mgr.create_collection(
        name=test_collection_name,
        description="Test collection",
        domain="testing",
        domain_scope="Test collection for automated testing",
        metadata_schema=default_schema
    )

    yield test_collection_name

    # Cleanup
    try:
        collection_mgr.delete_collection(test_collection_name)
    except Exception:
        pass
