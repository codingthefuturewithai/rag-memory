"""Unit tests for MCP update_collection_metadata tool."""

import pytest
from unittest.mock import MagicMock, patch
from src.mcp.tools import update_collection_metadata_impl


class TestMCPUpdateCollectionMetadata:
    """Tests for the MCP update_collection_metadata tool implementation."""

    def test_update_metadata_impl_success(self):
        """Test successful metadata update through MCP tool."""
        # Setup
        coll_mgr = MagicMock()

        # Mock existing collection
        existing_collection = {
            "name": "test-collection",
            "description": "Test collection",
            "metadata_schema": {
                "custom": {
                    "existing": {"type": "string"}
                }
            }
        }

        # Mock updated collection
        updated_collection = {
            "name": "test-collection",
            "description": "Test collection",
            "metadata_schema": {
                "custom": {
                    "existing": {"type": "string"},
                    "new_field": {"type": "boolean", "required": False}
                }
            }
        }

        coll_mgr.get_collection.side_effect = [existing_collection, None]
        coll_mgr.update_collection_metadata_schema.return_value = updated_collection

        # Call the implementation
        new_fields = {"new_field": {"type": "boolean"}}
        result = update_collection_metadata_impl(coll_mgr, "test-collection", new_fields)

        # Verify
        assert result["name"] == "test-collection"
        assert result["fields_added"] == 1
        assert result["total_fields"] == 2
        assert result["metadata_schema"]["custom"]["new_field"]["type"] == "boolean"

    def test_update_metadata_impl_wraps_custom(self):
        """Test that new_fields gets wrapped in 'custom' if needed."""
        # Setup
        coll_mgr = MagicMock()

        existing = {
            "name": "test",
            "description": "Test collection",
            "metadata_schema": {"custom": {}}
        }
        updated = {
            "name": "test",
            "description": "Test collection",
            "metadata_schema": {"custom": {"field1": {"type": "string"}}}
        }

        coll_mgr.get_collection.return_value = existing
        coll_mgr.update_collection_metadata_schema.return_value = updated

        # Call with unwrapped fields
        new_fields = {"field1": {"type": "string"}}
        result = update_collection_metadata_impl(coll_mgr, "test", new_fields)

        # Verify it was wrapped properly
        call_args = coll_mgr.update_collection_metadata_schema.call_args[0]
        assert "custom" in call_args[1]
        assert call_args[1]["custom"]["field1"]["type"] == "string"

    def test_update_metadata_impl_collection_not_found(self):
        """Test error when collection doesn't exist."""
        # Setup
        coll_mgr = MagicMock()
        coll_mgr.get_collection.return_value = None

        # Should raise ValueError
        with pytest.raises(ValueError) as exc:
            update_collection_metadata_impl(coll_mgr, "non-existent", {"field": "string"})

        assert "Collection 'non-existent' not found" in str(exc.value)

    def test_update_metadata_impl_validation_error(self):
        """Test that validation errors are propagated."""
        # Setup
        coll_mgr = MagicMock()

        existing = {"name": "test", "metadata_schema": {"custom": {"field1": {"type": "string"}}}}
        coll_mgr.get_collection.return_value = existing

        # Mock validation error
        coll_mgr.update_collection_metadata_schema.side_effect = ValueError(
            "Cannot change type of field 'field1'"
        )

        # Should propagate the ValueError
        with pytest.raises(ValueError) as exc:
            update_collection_metadata_impl(
                coll_mgr, "test", {"field1": {"type": "number"}}
            )

        assert "Cannot change type of field 'field1'" in str(exc.value)