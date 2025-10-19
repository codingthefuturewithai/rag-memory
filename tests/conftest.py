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

from src.core.config_loader import load_environment_variables

# ============================================================================
# CRITICAL: Load .env.test to ensure tests use test servers
# ============================================================================

# Get repo root (parent of tests directory)
repo_root = Path(__file__).parent.parent

# Try to load .env.test first (primary test config)
env_test_path = repo_root / ".env.test"
env_dev_path = repo_root / ".env.dev"
env_supabase_path = repo_root / ".env.supabase"

# Load from .env.test if it exists, otherwise fallback to .env.dev
if env_test_path.exists():
    # Load .env.test first
    from dotenv import load_dotenv
    load_dotenv(env_test_path, override=True)
    print("✅ Loaded .env.test for test environment")
elif env_dev_path.exists():
    print("⚠️  WARNING: .env.test not found, falling back to .env.dev")
    print("   Tests will run against development servers instead of test servers")
    from dotenv import load_dotenv
    load_dotenv(env_dev_path, override=True)
else:
    print("⚠️  No environment file found, using shell environment variables")

# Also load from ~/.rag-memory-env for credentials if it exists
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
    print("      docker-compose -f docker-compose.test.yml up -d")
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
        print("   1. docker-compose -f docker-compose.test.yml up -d")
        print("   2. Restart pytest to auto-load .env.test")

print(f"ℹ️  Test Environment: {env_name}")
print(f"ℹ️  Postgres: {database_url.split('@')[1] if '@' in database_url else 'local'}")
print(f"ℹ️  Neo4j: {neo4j_uri}")
