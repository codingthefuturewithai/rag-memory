"""Unit tests for collection metadata schema updates."""

import pytest
from unittest.mock import MagicMock, patch
from psycopg.types.json import Jsonb
from src.core.collections import CollectionManager


class TestUpdateCollectionMetadata:
    """Tests for updating collection metadata schemas."""

    def test_update_metadata_add_new_fields(self):
        """Test adding new fields to an existing collection."""
        # Setup
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        db.connect.return_value = conn
        conn.cursor.return_value.__enter__ = lambda self: cursor
        conn.cursor.return_value.__exit__ = lambda self, *args: None

        mgr = CollectionManager(db)

        # Mock existing collection
        existing_collection = {
            "id": 1,
            "name": "test-collection",
            "description": "Test collection",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test collection for unit testing"
                },
                "custom": {
                    "existing_field": {"type": "string", "required": False}
                },
                "system": []
            },
            "created_at": "2025-10-25",
            "document_count": 10
        }

        # Mock get_collection to return existing
        with patch.object(mgr, 'get_collection', return_value=existing_collection):
            # Mock the UPDATE query
            cursor.fetchone.return_value = [1]
            cursor.rowcount = 1

            # Add new fields (must include existing fields too)
            new_fields = {
                "custom": {
                    "existing_field": {"type": "string", "required": False},  # Keep existing
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},  # Add new
                    "reviewed": {"type": "boolean"}  # Add new
                }
            }

            # Mock the updated collection (after update)
            updated_collection = existing_collection.copy()
            updated_collection["metadata_schema"]["custom"].update(new_fields["custom"])

            with patch.object(mgr, 'get_collection', side_effect=[existing_collection, updated_collection]):
                result = mgr.update_collection_metadata_schema("test-collection", new_fields)

                # Verify the UPDATE was called with merged schema
                cursor.execute.assert_called_once()
                call_args = cursor.execute.call_args[0]
                assert "UPDATE collections" in call_args[0]
                assert "metadata_schema" in call_args[0]

                # Check the result
                assert result["name"] == "test-collection"
                assert "priority" in result["metadata_schema"]["custom"]
                assert "reviewed" in result["metadata_schema"]["custom"]
                assert "existing_field" in result["metadata_schema"]["custom"]

    def test_update_metadata_cannot_remove_fields(self):
        """Test that removing existing fields raises an error."""
        # Setup
        db = MagicMock()
        mgr = CollectionManager(db)

        # Mock existing collection
        existing_collection = {
            "id": 1,
            "name": "test-collection",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test collection for field removal testing"
                },
                "custom": {
                    "field1": {"type": "string"},
                    "field2": {"type": "number"}
                },
                "system": []
            }
        }

        with patch.object(mgr, 'get_collection', return_value=existing_collection):
            # Try to update with only field1 (removing field2)
            new_fields = {
                "custom": {
                    "field1": {"type": "string"}
                }
            }

            with pytest.raises(ValueError) as exc:
                mgr.update_collection_metadata_schema("test-collection", new_fields)

            assert "Cannot remove existing field 'field2'" in str(exc.value)

    def test_update_metadata_cannot_change_field_types(self):
        """Test that changing field types raises an error."""
        # Setup
        db = MagicMock()
        mgr = CollectionManager(db)

        # Mock existing collection
        existing_collection = {
            "id": 1,
            "name": "test-collection",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test collection for type change testing"
                },
                "custom": {
                    "field1": {"type": "string"}
                },
                "system": []
            }
        }

        with patch.object(mgr, 'get_collection', return_value=existing_collection):
            # Try to change field1 from string to number
            new_fields = {
                "custom": {
                    "field1": {"type": "number"}
                }
            }

            with pytest.raises(ValueError) as exc:
                mgr.update_collection_metadata_schema("test-collection", new_fields)

            assert "Cannot change type of field 'field1'" in str(exc.value)
            assert "from 'string' to 'number'" in str(exc.value)

    def test_update_metadata_forces_new_fields_optional(self):
        """Test that new fields are forced to be optional."""
        # Setup
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        db.connect.return_value = conn
        conn.cursor.return_value.__enter__ = lambda self: cursor
        conn.cursor.return_value.__exit__ = lambda self, *args: None

        mgr = CollectionManager(db)

        # Mock existing collection
        existing_collection = {
            "id": 1,
            "name": "test-collection",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test collection for optional fields testing"
                },
                "custom": {},
                "system": []
            },
            "document_count": 0
        }

        # Try to add a field with required=True
        new_fields = {
            "custom": {
                "new_field": {"type": "string", "required": True}
            }
        }

        # Capture what gets passed to the database UPDATE
        cursor.fetchone.return_value = [1]
        cursor.rowcount = 1

        with patch.object(mgr, 'get_collection') as mock_get:
            # First call returns existing, second call returns updated
            mock_get.side_effect = [
                existing_collection,
                {
                    "id": 1,
                    "name": "test-collection",
                    "metadata_schema": {
                        "custom": {
                            "new_field": {"type": "string", "required": False}
                        },
                        "system": []
                    },
                    "document_count": 0
                }
            ]

            result = mgr.update_collection_metadata_schema("test-collection", new_fields)

            # Check what was passed to the UPDATE statement
            update_call = cursor.execute.call_args[0]
            schema_passed = update_call[1][0]  # First parameter to UPDATE (the Jsonb)

            # The schema passed to the database should have required=False
            assert schema_passed.obj["custom"]["new_field"]["required"] is False

    def test_update_metadata_collection_not_found(self):
        """Test updating metadata for non-existent collection."""
        # Setup
        db = MagicMock()
        mgr = CollectionManager(db)

        with patch.object(mgr, 'get_collection', return_value=None):
            with pytest.raises(ValueError) as exc:
                mgr.update_collection_metadata_schema("non-existent", {"custom": {}})

            assert "Collection 'non-existent' not found" in str(exc.value)

    def test_update_metadata_shorthand_syntax(self):
        """Test that shorthand syntax gets expanded properly."""
        # Setup
        db = MagicMock()
        conn = MagicMock()
        cursor = MagicMock()
        db.connect.return_value = conn
        conn.cursor.return_value.__enter__ = lambda self: cursor
        conn.cursor.return_value.__exit__ = lambda self, *args: None

        mgr = CollectionManager(db)

        # Mock existing collection
        existing_collection = {
            "id": 1,
            "name": "test-collection",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test collection for shorthand syntax testing"
                },
                "custom": {},
                "system": []
            },
            "document_count": 0
        }

        with patch.object(mgr, 'get_collection', return_value=existing_collection):
            cursor.fetchone.return_value = [1]
            cursor.rowcount = 1

            # Use shorthand syntax (just field names)
            new_fields = {
                "priority": "string",
                "count": "number"
            }

            updated = existing_collection.copy()
            updated["metadata_schema"]["custom"] = {
                "priority": {"type": "string", "required": False},
                "count": {"type": "number", "required": False}
            }

            with patch.object(mgr, 'get_collection', side_effect=[existing_collection, updated]):
                result = mgr.update_collection_metadata_schema("test-collection", new_fields)

                # Verify fields were added with proper structure
                assert "priority" in result["metadata_schema"]["custom"]
                assert "count" in result["metadata_schema"]["custom"]