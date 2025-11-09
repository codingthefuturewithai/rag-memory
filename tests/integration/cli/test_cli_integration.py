"""Integration tests for CLI with real database."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.cli import main
from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.ingestion.document_store import get_document_store
from src.core.embeddings import get_embedding_generator


@pytest.fixture
def cli_runner():
    """Provide a Click CliRunner instance."""
    return CliRunner()


@pytest.fixture
def setup_test_db(setup_test_collection):
    """Fixture that provides a test database and ensures test collection exists."""
    # setup_test_collection comes from conftest.py and already sets up the db
    yield setup_test_collection


class TestCollectionLifecycle:
    """Test end-to-end collection lifecycle."""

    def test_collection_lifecycle(self, cli_runner, setup_test_db):
        """Test creating, listing, getting info, and deleting a collection."""
        test_collection_name = "cli-test-coll"

        # 1. Create a collection
        result = cli_runner.invoke(
            main,
            ["collection", "create", test_collection_name,
             "--description", "CLI test collection",
             "--domain", "testing",
             "--domain-scope", "Test collection for CLI integration testing"],
        )
        assert result.exit_code == 0, f"Failed to create collection: {result.output}"
        assert "Created collection" in result.output

        # 2. List collections (should include our new one)
        result = cli_runner.invoke(main, ["collection", "list"])
        assert result.exit_code == 0
        assert test_collection_name in result.output

        # 3. Get collection info
        result = cli_runner.invoke(main, ["collection", "info", test_collection_name])
        assert result.exit_code == 0
        assert test_collection_name in result.output

        # 4. Get collection schema
        result = cli_runner.invoke(main, ["collection", "schema", test_collection_name])
        assert result.exit_code == 0
        # Schema output is ok even if empty
        assert test_collection_name in result.output

        # 5. Delete the collection
        result = cli_runner.invoke(main, ["collection", "delete", test_collection_name, "--yes"])
        assert result.exit_code == 0
        assert "Deleted collection" in result.output

        # 6. Verify it's gone (list should not include it)
        result = cli_runner.invoke(main, ["collection", "list"])
        assert result.exit_code == 0
        assert test_collection_name not in result.output

    def test_collection_schema_display(self, cli_runner, setup_test_db):
        """Test displaying collection metadata schema."""
        # Use the existing test collection from fixture
        collection_name = setup_test_db

        result = cli_runner.invoke(main, ["collection", "schema", collection_name])

        assert result.exit_code == 0
        assert collection_name in result.output




class TestIngestURLWorkflow:
    """Test URL ingestion workflows including recrawl."""

    def test_ingest_url_modes(self, cli_runner, setup_test_db):
        """Test both crawl and recrawl modes for URL ingestion."""
        collection_name = setup_test_db

        # Note: These tests will attempt actual URL crawling which may fail
        # but the CLI should handle errors gracefully. We're testing that the
        # --mode parameter is properly recognized and processed.

        # Test 1: Crawl mode (default)
        result = cli_runner.invoke(
            main,
            [
                "ingest",
                "url",
                "https://example.com",
                "--collection",
                collection_name,
                "--mode",
                "crawl",
            ],
        )
        # Should either succeed or show error (not command line error)
        assert "Error: Invalid value for" not in result.output

        # Test 2: Recrawl mode
        result = cli_runner.invoke(
            main,
            [
                "ingest",
                "url",
                "https://example.com",
                "--collection",
                collection_name,
                "--mode",
                "recrawl",
            ],
        )
        # Should either succeed or show error (not command line error)
        assert "Error: Invalid value for" not in result.output


class TestStatusAndAnalyze:
    """Test status and analysis commands."""

    def test_status_command(self, cli_runner):
        """Test that status command works."""
        result = cli_runner.invoke(main, ["status"])

        # Status should always work
        assert result.exit_code == 0
        assert "status" in result.output.lower() or "database" in result.output.lower()

