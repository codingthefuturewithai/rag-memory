"""Unit tests for database health checks and connection management."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import time

from src.core.database import Database


class TestDatabaseConnectionManagement:
    """Test database connection initialization and management."""

    def test_database_init_with_explicit_connection_string(self):
        """Test initializing database with explicit connection string."""
        conn_string = "postgresql://user:pass@localhost:5432/rag"
        db = Database(connection_string=conn_string)

        assert db.connection_string == conn_string

    def test_database_init_from_environment_variable(self):
        """Test initializing database from DATABASE_URL environment variable."""
        with patch.dict('os.environ', {'DATABASE_URL': 'postgresql://env-db:5432/rag'}):
            db = Database()

            assert db.connection_string == 'postgresql://env-db:5432/rag'

    def test_database_init_raises_without_connection_string(self):
        """Test that ValueError is raised when no connection string available."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Database()

            assert "DATABASE_URL not found" in str(exc_info.value)

    def test_database_init_prefers_explicit_over_environment(self):
        """Test that explicit connection string takes priority over environment variable."""
        explicit_conn = "postgresql://explicit:pass@localhost:5432/rag"
        env_conn = "postgresql://env:pass@localhost:5432/rag"

        with patch.dict('os.environ', {'DATABASE_URL': env_conn}):
            db = Database(connection_string=explicit_conn)

            assert db.connection_string == explicit_conn


class TestDatabaseConnectionStateManagement:
    """Test managing database connection state."""

    @patch('psycopg.connect')
    def test_connect_creates_new_connection(self, mock_psycopg_connect):
        """Test that connect() creates a new connection."""
        mock_conn = MagicMock()
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.connect()

        assert result is mock_conn
        mock_psycopg_connect.assert_called_once()

    @patch('psycopg.connect')
    def test_connect_reuses_existing_connection(self, mock_psycopg_connect):
        """Test that connect() reuses existing open connection."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        db.connect()
        result2 = db.connect()

        # Should only call psycopg.connect once, reusing the connection
        assert mock_psycopg_connect.call_count == 1
        assert result2 is mock_conn

    @patch('psycopg.connect')
    def test_connect_reconnects_when_closed(self, mock_psycopg_connect):
        """Test that connect() creates new connection if previous was closed."""
        mock_conn1 = MagicMock()
        mock_conn1.closed = True
        mock_conn2 = MagicMock()
        mock_conn2.closed = False

        mock_psycopg_connect.return_value = mock_conn2

        db = Database(connection_string="postgresql://localhost/test")
        db._connection = mock_conn1  # Simulate having a closed connection

        result = db.connect()

        # Should create a new connection
        assert result is mock_conn2
        assert mock_psycopg_connect.call_count == 1

    @patch('psycopg.connect')
    def test_close_closes_open_connection(self, mock_psycopg_connect):
        """Test that close() closes an open connection."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        db.connect()
        db.close()

        mock_conn.close.assert_called_once()

    @patch('psycopg.connect')
    def test_close_ignores_already_closed_connection(self, mock_psycopg_connect):
        """Test that close() handles already-closed connections gracefully."""
        mock_conn = MagicMock()
        mock_conn.closed = True
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        db.connect()
        db.close()

        # Should not attempt to close an already-closed connection
        mock_conn.close.assert_not_called()

    @patch('psycopg.connect')
    def test_close_without_connection(self, mock_psycopg_connect):
        """Test that close() handles case where no connection exists."""
        db = Database(connection_string="postgresql://localhost/test")

        # Should not raise an error
        db.close()


class TestDatabaseContextManager:
    """Test database as context manager."""

    @patch('psycopg.connect')
    def test_context_manager_connect_on_enter(self, mock_psycopg_connect):
        """Test that context manager calls connect() on __enter__."""
        mock_conn = MagicMock()
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")

        with db:
            pass

        mock_psycopg_connect.assert_called_once()

    @patch('psycopg.connect')
    def test_context_manager_close_on_exit(self, mock_psycopg_connect):
        """Test that context manager calls close() on __exit__."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")

        with db:
            pass

        mock_conn.close.assert_called_once()

    @patch('psycopg.connect')
    def test_context_manager_returns_database_instance(self, mock_psycopg_connect):
        """Test that context manager returns the database instance."""
        mock_conn = MagicMock()
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")

        with db as context_db:
            assert context_db is db


class TestDatabaseHealthCheckAsync:
    """Test async health check functionality."""

    @patch('psycopg.connect')
    def test_health_check_returns_healthy_status(self, mock_psycopg_connect):
        """Test that health_check returns healthy status for working connection."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.health_check())

        assert result["status"] == "healthy"
        assert "latency_ms" in result
        assert result["error"] is None
        assert result["latency_ms"] > 0

    @patch('psycopg.connect')
    def test_health_check_detects_closed_connection(self, mock_psycopg_connect):
        """Test that health_check detects closed connection."""
        mock_conn = MagicMock()
        mock_conn.closed = True

        db = Database(connection_string="postgresql://localhost/test")
        db._connection = mock_conn

        result = asyncio.run(db.health_check())

        assert result["status"] == "unhealthy"
        assert "closed or broken" in result["error"]

    @patch('psycopg.connect')
    def test_health_check_detects_broken_connection(self, mock_psycopg_connect):
        """Test that health_check detects broken connection."""
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = True

        db = Database(connection_string="postgresql://localhost/test")
        db._connection = mock_conn

        result = asyncio.run(db.health_check())

        assert result["status"] == "unhealthy"
        assert "closed or broken" in result["error"]

    @patch('psycopg.connect')
    def test_health_check_handles_operational_error(self, mock_psycopg_connect):
        """Test that health_check handles OperationalError from psycopg."""
        from psycopg import OperationalError

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = OperationalError("Connection refused")
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.health_check())

        assert result["status"] == "unhealthy"
        assert "Connection refused" in result["error"]

    @patch('psycopg.connect')
    def test_health_check_handles_database_error(self, mock_psycopg_connect):
        """Test that health_check handles DatabaseError from psycopg."""
        from psycopg import DatabaseError

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = DatabaseError("Database error")
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.health_check())

        assert result["status"] == "unhealthy"
        assert "Database error" in result["error"]

    @patch('psycopg.connect')
    def test_health_check_handles_unexpected_error(self, mock_psycopg_connect):
        """Test that health_check handles unexpected errors gracefully."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = RuntimeError("Unexpected error")
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.health_check())

        assert result["status"] == "unhealthy"
        assert "Unexpected error" in result["error"]

    @patch('psycopg.connect')
    def test_health_check_measures_latency(self, mock_psycopg_connect):
        """Test that health_check measures and returns latency."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.broken = False
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.health_check())

        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0


class TestDatabaseSchemaValidation:
    """Test database schema validation."""

    @patch('psycopg.connect')
    def test_validate_schema_returns_expected_structure(self, mock_psycopg_connect):
        """Test schema validation returns all expected fields in response."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.validate_schema())

        # Check that all required response fields are present
        assert "status" in result
        assert "latency_ms" in result
        assert "missing_tables" in result
        assert "pgvector_loaded" in result
        assert "hnsw_indexes" in result
        assert "errors" in result
        assert isinstance(result["missing_tables"], list)
        assert isinstance(result["pgvector_loaded"], bool)
        assert isinstance(result["hnsw_indexes"], int)
        assert isinstance(result["errors"], list)

    @patch('psycopg.connect')
    def test_validate_schema_missing_table(self, mock_psycopg_connect):
        """Test schema validation when a required table is missing."""
        mock_cursor = MagicMock()
        # Missing document_chunks table
        mock_cursor.fetchall.return_value = [
            ("source_documents",),
            ("collections",)
        ]
        mock_cursor.fetchone.return_value = [("vector", "0.5.0")]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.validate_schema())

        assert result["status"] == "invalid"
        assert "document_chunks" in result["missing_tables"]
        assert any("Missing required tables" in error for error in result["errors"])

    @patch('psycopg.connect')
    def test_validate_schema_pgvector_not_loaded(self, mock_psycopg_connect):
        """Test schema validation when pgvector extension is not loaded."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("source_documents",),
            ("document_chunks",),
            ("collections",)
        ]
        mock_cursor.fetchone.return_value = None  # pgvector not found

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.validate_schema())

        assert result["status"] == "invalid"
        assert result["pgvector_loaded"] is False
        assert any("pgvector extension not found" in error for error in result["errors"])

    @patch('psycopg.connect')
    def test_validate_schema_measures_latency(self, mock_psycopg_connect):
        """Test schema validation measures execution latency."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.validate_schema())

        # Verify latency measurement is present and reasonable
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], float)
        assert result["latency_ms"] >= 0

    @patch('psycopg.connect')
    def test_validate_schema_handles_exception(self, mock_psycopg_connect):
        """Test schema validation handles unexpected exceptions."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database connection error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = asyncio.run(db.validate_schema())

        assert result["status"] == "invalid"
        assert any("Schema validation error" in error for error in result["errors"])


class TestDatabaseTestConnection:
    """Test the test_connection() method."""

    @patch('psycopg.connect')
    def test_test_connection_success(self, mock_psycopg_connect):
        """Test successful connection test."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ["PostgreSQL 14.2"],
            ["vector", "0.5.0"]
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.test_connection()

        assert result is True

    @patch('psycopg.connect')
    def test_test_connection_pgvector_missing(self, mock_psycopg_connect):
        """Test connection test when pgvector is missing."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            ["PostgreSQL 14.2"],
            None  # pgvector not found
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.test_connection()

        assert result is False

    @patch('psycopg.connect')
    def test_test_connection_exception(self, mock_psycopg_connect):
        """Test connection test handles exceptions."""
        mock_psycopg_connect.side_effect = Exception("Connection failed")

        db = Database(connection_string="postgresql://localhost/test")
        result = db.test_connection()

        assert result is False


class TestDatabaseGetStats:
    """Test database statistics retrieval."""

    @patch('psycopg.connect')
    def test_get_stats_returns_all_metrics(self, mock_psycopg_connect):
        """Test that get_stats returns all required metrics."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            [100],  # source_documents count
            [500],  # chunks count
            [5],    # collections count
            ["25 MB"]  # database size
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        stats = db.get_stats()

        assert stats["source_documents"] == 100
        assert stats["chunks"] == 500
        assert stats["collections"] == 5
        assert stats["database_size"] == "25 MB"

    @patch('psycopg.connect')
    def test_get_stats_with_zero_counts(self, mock_psycopg_connect):
        """Test get_stats when database is empty."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            [0],  # source_documents
            [0],  # chunks
            [0],  # collections
            ["8 kB"]  # size
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        stats = db.get_stats()

        assert stats["source_documents"] == 0
        assert stats["chunks"] == 0
        assert stats["collections"] == 0


class TestDatabaseInitializeSchema:
    """Test schema initialization."""

    @patch('psycopg.connect')
    def test_initialize_schema_already_exists(self, mock_psycopg_connect):
        """Test initialize_schema when tables already exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("source_documents",),
            ("document_chunks",),
            ("collections",)
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.initialize_schema()

        assert result is True

    @patch('psycopg.connect')
    def test_initialize_schema_missing_tables(self, mock_psycopg_connect):
        """Test initialize_schema when tables don't exist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No tables found

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.initialize_schema()

        assert result is False

    @patch('psycopg.connect')
    def test_initialize_schema_exception(self, mock_psycopg_connect):
        """Test initialize_schema handles exceptions."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
        mock_psycopg_connect.return_value = mock_conn

        db = Database(connection_string="postgresql://localhost/test")
        result = db.initialize_schema()

        assert result is False
