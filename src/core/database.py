"""Database connection and management for PostgreSQL with pgvector."""

import logging
import os
import time
from typing import Optional

import psycopg
from psycopg import OperationalError, DatabaseError

# Note: Environment variables are loaded by CLI (via first_run.py) or provided by MCP client.
# No automatic config loading at module import to avoid issues with MCP server usage.

logger = logging.getLogger(__name__)


class Database:
    """Manages PostgreSQL database connections with pgvector support."""

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            connection_string: PostgreSQL connection string. If None, uses DATABASE_URL from env.
        """
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError(
                "DATABASE_URL not found. Set it in environment variables, ~/.rag-memory-env, "
                "or pass connection_string parameter."
            )
        self._connection: Optional[psycopg.Connection] = None
        logger.info("Database initialized with connection string")

    def connect(self) -> psycopg.Connection:
        """
        Create and return a database connection.

        Returns:
            Active PostgreSQL connection with autocommit enabled.
        """
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(self.connection_string, autocommit=True)
            logger.info("Database connection established")
        return self._connection

    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
            logger.info("Database connection closed")

    def test_connection(self) -> bool:
        """
        Test if database connection is working and pgvector is available.

        Returns:
            True if connection and pgvector extension are working.
        """
        try:
            conn = self.connect()
            with conn.cursor() as cur:
                # Check PostgreSQL version
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                logger.info(f"PostgreSQL version: {version}")

                # Check pgvector extension
                cur.execute(
                    "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
                )
                result = cur.fetchone()
                if result:
                    logger.info(f"pgvector extension: {result[0]} v{result[1]}")
                else:
                    logger.error("pgvector extension not found!")
                    return False

                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    async def health_check(self, timeout_ms: int = 2000) -> dict:
        """
        Lightweight PostgreSQL liveness check for use before write operations.

        Performs two checks:
        1. Property check (instant) - verifies connection object state
        2. Network validation (1-10ms) - executes SELECT 1 query

        Returns:
            Dictionary with health status:
                {
                    "status": "healthy" | "unhealthy",
                    "latency_ms": float,
                    "error": str or None
                }

        Note:
            - This is a best-effort check, not a guarantee of operation success
            - Latency: ~0-5ms local, ~5-20ms cloud, ~20-50ms Fly.io
            - Designed to fail-fast on unreachable databases before expensive operations
        """
        start = time.perf_counter()

        # Step 1: Property check (instant, no network)
        if self._connection and (self._connection.closed or self._connection.broken):
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": "Connection closed or broken",
            }

        # Step 2: SELECT 1 network validation
        try:
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "error": None,
            }
        except (OperationalError, DatabaseError) as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": str(e),
            }
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return {
                "status": "unhealthy",
                "latency_ms": round(latency, 2),
                "error": f"Unexpected error: {str(e)}",
            }

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with document counts, collection count, and database size.
        """
        conn = self.connect()
        with conn.cursor() as cur:
            # Count source documents
            cur.execute("SELECT COUNT(*) FROM source_documents;")
            source_doc_count = cur.fetchone()[0]

            # Count document chunks
            cur.execute("SELECT COUNT(*) FROM document_chunks;")
            chunk_count = cur.fetchone()[0]

            # Count collections
            cur.execute("SELECT COUNT(*) FROM collections;")
            collection_count = cur.fetchone()[0]

            # Get database size
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()));")
            db_size = cur.fetchone()[0]

            return {
                "source_documents": source_doc_count,
                "chunks": chunk_count,
                "collections": collection_count,
                "database_size": db_size,
            }

    async def validate_schema(self) -> dict:
        """
        Validate PostgreSQL schema is properly initialized (startup only).

        Performs lightweight checks:
        1. Required tables exist (source_documents, document_chunks, collections)
        2. pgvector extension is loaded
        3. HNSW indexes exist (performance critical)

        Returns:
            Dictionary with validation status:
                {
                    "status": "valid" | "invalid",
                    "latency_ms": float,
                    "missing_tables": list[str],
                    "pgvector_loaded": bool,
                    "hnsw_indexes": int,
                    "errors": list[str]
                }

        Note:
            - Only called at server startup
            - Latency: ~4-6ms local, ~10-20ms cloud
            - Provides early failure if schema not initialized
        """
        start = time.perf_counter()
        errors = []
        missing_tables = []
        pgvector_loaded = False
        hnsw_indexes = 0

        try:
            conn = self.connect()
            with conn.cursor() as cur:
                # Check 1: Required tables exist
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('source_documents', 'document_chunks', 'collections');
                    """
                )
                existing_tables = {row[0] for row in cur.fetchall()}
                required_tables = {"source_documents", "document_chunks", "collections"}
                missing_tables = list(required_tables - existing_tables)

                if missing_tables:
                    errors.append(
                        f"Missing required tables: {', '.join(missing_tables)}. "
                        "Run 'uv run rag init' to initialize the database."
                    )

                # Check 2: pgvector extension loaded
                cur.execute(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
                )
                pgvector_result = cur.fetchone()
                pgvector_loaded = pgvector_result is not None

                if not pgvector_loaded:
                    errors.append(
                        "pgvector extension not found. "
                        "Ensure PostgreSQL has pgvector installed and initialized."
                    )

                # Check 3: HNSW indexes exist (if tables exist)
                if not missing_tables:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM pg_indexes
                        WHERE schemaname = 'public'
                        AND indexname LIKE '%embedding%'
                        AND indexdef LIKE '%hnsw%';
                        """
                    )
                    hnsw_indexes = cur.fetchone()[0]

                    if hnsw_indexes < 1:
                        errors.append(
                            f"HNSW embedding index not found. "
                            "Run 'uv run rag init' to create indexes."
                        )

        except Exception as e:
            errors.append(f"Schema validation error: {str(e)}")

        latency = (time.perf_counter() - start) * 1000

        return {
            "status": "valid" if not errors else "invalid",
            "latency_ms": round(latency, 2),
            "missing_tables": missing_tables,
            "pgvector_loaded": pgvector_loaded,
            "hnsw_indexes": hnsw_indexes,
            "errors": errors,
        }

    def initialize_schema(self) -> bool:
        """
        Initialize database schema if not already created.

        Note: This is typically done by init.sql in Docker, but can be called manually.

        Returns:
            True if schema initialization succeeds.
        """
        try:
            conn = self.connect()
            with conn.cursor() as cur:
                # Check if tables exist
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('source_documents', 'document_chunks', 'collections');
                """
                )
                existing_tables = [row[0] for row in cur.fetchall()]

                required_tables = {"source_documents", "document_chunks", "collections"}
                if required_tables.issubset(set(existing_tables)):
                    logger.info("Database schema already initialized")
                    return True

                logger.info("Database schema not found - may need to run init.sql")
                return False
        except Exception as e:
            logger.error(f"Schema initialization check failed: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_database() -> Database:
    """
    Factory function to get a Database instance.

    Returns:
        Configured Database instance.
    """
    return Database()
