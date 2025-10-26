"""Unit tests for collection metadata schema functionality."""

import pytest
from unittest.mock import MagicMock
from src.mcp.tools import get_collection_metadata_schema_impl


class TestGetCollectionMetadataSchema:
    """Tests for get_collection_metadata_schema_impl function."""

    def test_get_schema_with_mandatory_and_custom_fields(self):
        """Test getting schema for collection with mandatory and custom fields."""
        coll_mgr = MagicMock()

        # Mock collection with mandatory and custom fields
        coll_mgr.get_collection.return_value = {
            "name": "test-docs",
            "description": "Test documentation",
            "metadata_schema": {
                "mandatory": {
                    "domain": "software-engineering",
                    "domain_scope": "Python programming and testing documentation"
                },
                "custom": {
                    "priority": {
                        "type": "string",
                        "enum": ["high", "low"],
                        "required": False,
                        "description": "Priority level"
                    },
                    "version": {
                        "type": "string",
                        "required": False,
                        "description": "Version number"
                    }
                },
                "system": []  # Not exposed in response
            },
            "document_count": 5
        }

        result = get_collection_metadata_schema_impl(coll_mgr, "test-docs")

        # Verify top-level structure
        assert result["collection_name"] == "test-docs"
        assert result["description"] == "Test documentation"
        assert result["document_count"] == 5

        # Verify metadata_schema structure
        assert "metadata_schema" in result
        assert "mandatory_fields" in result["metadata_schema"]
        assert "custom_fields" in result["metadata_schema"]

        # Verify mandatory fields
        mandatory = result["metadata_schema"]["mandatory_fields"]
        assert "domain" in mandatory
        assert mandatory["domain"]["value"] == "software-engineering"
        assert mandatory["domain"]["immutable"] is True

        assert "domain_scope" in mandatory
        assert mandatory["domain_scope"]["value"] == "Python programming and testing documentation"
        assert mandatory["domain_scope"]["immutable"] is True

        # Verify custom fields
        custom = result["metadata_schema"]["custom_fields"]
        assert "priority" in custom
        assert custom["priority"]["type"] == "string"
        assert custom["priority"]["required"] is False
        assert custom["priority"]["enum"] == ["high", "low"]

        assert "version" in custom
        assert custom["version"]["type"] == "string"
        assert custom["version"]["required"] is False

    def test_get_schema_with_no_custom_fields(self):
        """Test getting schema for collection with only mandatory fields."""
        coll_mgr = MagicMock()

        coll_mgr.get_collection.return_value = {
            "name": "minimal-collection",
            "description": "Minimal documentation",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Test documentation"
                },
                "custom": {},
                "system": []
            },
            "document_count": 0
        }

        result = get_collection_metadata_schema_impl(coll_mgr, "minimal-collection")

        # Verify mandatory fields exist
        mandatory = result["metadata_schema"]["mandatory_fields"]
        assert "domain" in mandatory
        assert "domain_scope" in mandatory

        # Verify custom fields are empty
        assert len(result["metadata_schema"]["custom_fields"]) == 0

    def test_get_schema_collection_not_found(self):
        """Test error when collection doesn't exist."""
        coll_mgr = MagicMock()
        coll_mgr.get_collection.return_value = None

        with pytest.raises(ValueError) as exc:
            get_collection_metadata_schema_impl(coll_mgr, "nonexistent")

        assert "not found" in str(exc.value).lower()

    def test_required_vs_optional_custom_fields(self):
        """Test that custom fields correctly show required flag."""
        coll_mgr = MagicMock()

        coll_mgr.get_collection.return_value = {
            "name": "test",
            "description": "Test",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Metadata testing"
                },
                "custom": {
                    "required_custom": {
                        "type": "string",
                        "required": True,
                        "description": "Required custom field"
                    },
                    "optional_custom": {
                        "type": "string",
                        "required": False,
                        "description": "Optional custom field"
                    }
                },
                "system": []
            },
            "document_count": 0
        }

        result = get_collection_metadata_schema_impl(coll_mgr, "test")

        # Check custom required field
        custom = result["metadata_schema"]["custom_fields"]
        assert custom["required_custom"]["required"] is True

        # Check custom optional field
        assert custom["optional_custom"]["required"] is False

    def test_field_descriptions_preserved(self):
        """Test that field descriptions are preserved in response."""
        coll_mgr = MagicMock()

        coll_mgr.get_collection.return_value = {
            "name": "test",
            "description": "Test",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Description testing"
                },
                "custom": {
                    "my_field": {
                        "type": "string",
                        "required": False,
                        "description": "This is my custom field"
                    }
                },
                "system": []
            },
            "document_count": 0
        }

        result = get_collection_metadata_schema_impl(coll_mgr, "test")

        # Check custom field description
        custom = result["metadata_schema"]["custom_fields"]
        assert custom["my_field"]["description"] == "This is my custom field"

        # Check mandatory field descriptions exist
        mandatory = result["metadata_schema"]["mandatory_fields"]
        assert "description" in mandatory["domain"]
        assert "description" in mandatory["domain_scope"]

    def test_custom_field_enum_preserved(self):
        """Test that custom fields with enum constraints preserve them."""
        coll_mgr = MagicMock()

        coll_mgr.get_collection.return_value = {
            "name": "test",
            "description": "Test",
            "metadata_schema": {
                "mandatory": {
                    "domain": "testing",
                    "domain_scope": "Enum testing"
                },
                "custom": {
                    "status": {
                        "type": "string",
                        "required": False,
                        "enum": ["draft", "published", "archived"],
                        "description": "Document status"
                    }
                },
                "system": []
            },
            "document_count": 0
        }

        result = get_collection_metadata_schema_impl(coll_mgr, "test")

        # Check custom field enum is preserved
        status = result["metadata_schema"]["custom_fields"]["status"]
        assert status["enum"] == ["draft", "published", "archived"]
