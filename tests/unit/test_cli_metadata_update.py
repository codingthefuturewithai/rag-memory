"""Unit tests for CLI collection update-metadata command."""

import pytest
import json
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from src.cli import collection_update_metadata


class TestCLIUpdateMetadata:
    """Tests for the CLI collection update-metadata command."""

    def test_cli_update_metadata_success(self):
        """Test successful metadata update via CLI."""
        runner = CliRunner()

        with patch('src.cli.get_database') as mock_db, \
             patch('src.cli.get_collection_manager') as mock_get_mgr:

            # Setup mocks
            db = MagicMock()
            mock_db.return_value = db

            mgr = MagicMock()
            mock_get_mgr.return_value = mgr

            # Mock successful update
            mgr.update_collection_metadata_schema.return_value = {
                "name": "test-collection",
                "metadata_schema": {
                    "custom": {
                        "priority": {"type": "string", "enum": ["high", "low"]},
                        "reviewed": {"type": "boolean"}
                    }
                }
            }

            # Run command
            new_fields = {"priority": {"type": "string", "enum": ["high", "low"]}}
            result = runner.invoke(
                collection_update_metadata,
                ["test-collection", "--add-fields", json.dumps(new_fields)]
            )

            # Verify
            assert result.exit_code == 0
            assert "Updated collection 'test-collection' metadata schema" in result.output
            assert "Fields added:" in result.output
            assert "Total custom fields:" in result.output

    def test_cli_update_metadata_invalid_json(self):
        """Test error handling for invalid JSON input."""
        runner = CliRunner()

        with patch('src.cli.get_database') as mock_db, \
             patch('src.cli.get_collection_manager') as mock_get_mgr:

            db = MagicMock()
            mock_db.return_value = db
            mgr = MagicMock()
            mock_get_mgr.return_value = mgr

            # Run with invalid JSON
            result = runner.invoke(
                collection_update_metadata,
                ["test-collection", "--add-fields", "not-valid-json{"]
            )

            # Verify error
            assert result.exit_code == 1
            assert "Invalid JSON" in result.output

    def test_cli_update_metadata_validation_error(self):
        """Test that validation errors are displayed properly."""
        runner = CliRunner()

        with patch('src.cli.get_database') as mock_db, \
             patch('src.cli.get_collection_manager') as mock_get_mgr:

            db = MagicMock()
            mock_db.return_value = db

            mgr = MagicMock()
            mock_get_mgr.return_value = mgr

            # Mock validation error
            mgr.update_collection_metadata_schema.side_effect = ValueError(
                "Cannot remove existing field 'important_field'"
            )

            # Run command
            result = runner.invoke(
                collection_update_metadata,
                ["test-collection", "--add-fields", '{"new": "string"}']
            )

            # Verify error message
            assert result.exit_code == 1
            assert "Validation error" in result.output
            assert "Cannot remove existing field" in result.output

    def test_cli_update_metadata_collection_not_found(self):
        """Test error when collection doesn't exist."""
        runner = CliRunner()

        with patch('src.cli.get_database') as mock_db, \
             patch('src.cli.get_collection_manager') as mock_get_mgr:

            db = MagicMock()
            mock_db.return_value = db

            mgr = MagicMock()
            mock_get_mgr.return_value = mgr

            # Mock collection not found
            mgr.update_collection_metadata_schema.side_effect = ValueError(
                "Collection 'non-existent' not found"
            )

            # Run command
            result = runner.invoke(
                collection_update_metadata,
                ["non-existent", "--add-fields", '{"field": "string"}']
            )

            # Verify error
            assert result.exit_code == 1
            assert "Collection 'non-existent' not found" in result.output

    def test_cli_update_metadata_shorthand_syntax(self):
        """Test that shorthand JSON syntax works."""
        runner = CliRunner()

        with patch('src.cli.get_database') as mock_db, \
             patch('src.cli.get_collection_manager') as mock_get_mgr:

            db = MagicMock()
            mock_db.return_value = db

            mgr = MagicMock()
            mock_get_mgr.return_value = mgr

            # Mock successful update
            mgr.update_collection_metadata_schema.return_value = {
                "name": "test",
                "metadata_schema": {
                    "custom": {
                        "field1": {"type": "string"},
                        "field2": {"type": "boolean"}
                    }
                }
            }

            # Use shorthand syntax
            result = runner.invoke(
                collection_update_metadata,
                ["test", "--add-fields", '{"field1": "string", "field2": "boolean"}']
            )

            # Verify success
            assert result.exit_code == 0
            assert "Updated collection 'test' metadata schema" in result.output