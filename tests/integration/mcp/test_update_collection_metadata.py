"""MCP update_collection_metadata tool integration tests.

Tests the update_collection_metadata tool covering:
- Adding new custom fields
- Attempting to remove fields (should fail)
- Attempting to change field types (should fail)
- Automatic marking of new fields as optional
- Error scenarios
"""

import json
import pytest
from .conftest import extract_text_content, extract_error_text, extract_result_data

pytestmark = pytest.mark.anyio


class TestUpdateCollectionMetadata:
    """Test update_collection_metadata tool functionality via MCP."""

    async def test_add_new_custom_fields(self, mcp_session):
        """Test successfully adding new custom fields to a collection."""
        session, transport = mcp_session

        collection_name = f"test_update_add_fields_{id(session)}"

        # Create collection with initial schema
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Collection for testing metadata updates",
            "domain": "testing",
            "domain_scope": "Test collection for metadata update testing",
            "metadata_schema": {
                "custom": {
                    "status": {
                        "type": "string",
                        "required": False,
                        "enum": ["draft", "published"]
                    }
                }
            }
        })

        # Add new custom fields (must include existing fields too - additive only)
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "status": {  # Keep existing field
                        "type": "string",
                        "required": False,
                        "enum": ["draft", "published"]
                    },
                    "priority": {  # New field
                        "type": "string",
                        "description": "Task priority level",
                        "enum": ["high", "medium", "low"]
                    },
                    "reviewed": {  # New field
                        "type": "boolean",
                        "description": "Whether content has been reviewed"
                    }
                }
            }
        })

        assert not result.isError, f"update_collection_metadata failed: {result}"
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify response structure
        assert data.get("name") == collection_name
        assert "metadata_schema" in data
        assert data.get("fields_added") == 2
        assert data.get("total_custom_fields") == 3  # original 1 + new 2

        # Verify schema includes new fields
        schema = data["metadata_schema"]
        assert "priority" in schema.get("custom", {})
        assert "reviewed" in schema.get("custom", {})
        assert "status" in schema.get("custom", {})  # Original field still there

    async def test_new_fields_automatically_optional(self, mcp_session):
        """Test that new fields are automatically marked as optional (required=false)."""
        session, transport = mcp_session

        collection_name = f"test_update_auto_optional_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test auto-optional fields",
            "domain": "testing",
            "domain_scope": "Test collection for auto-optional field testing"
        })

        # Add new field (don't specify required)
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "new_field": {
                        "type": "string",
                        "description": "A new field"
                    }
                }
            }
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify field was marked as optional
        new_field_spec = data["metadata_schema"]["custom"]["new_field"]
        assert new_field_spec.get("required") is False, "New fields must be optional"

    async def test_cannot_remove_existing_fields(self, mcp_session):
        """Test that attempting to remove existing fields fails."""
        session, transport = mcp_session

        collection_name = f"test_update_no_remove_{id(session)}"

        # Create collection with fields
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test field removal prevention",
            "domain": "testing",
            "domain_scope": "Test collection for field removal testing",
            "metadata_schema": {
                "custom": {
                    "field1": {"type": "string"},
                    "field2": {"type": "number"}
                }
            }
        })

        # Try to update with only field1 (implicitly removing field2)
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "field1": {"type": "string"}
                    # field2 missing - this should fail
                }
            }
        })

        # Should error because we're trying to remove field2
        assert result.isError, "Should not allow removing existing fields"
        error_text = extract_error_text(result)
        assert "cannot remove" in error_text.lower() or "field2" in error_text.lower()

    async def test_cannot_change_field_types(self, mcp_session):
        """Test that attempting to change field types fails."""
        session, transport = mcp_session

        collection_name = f"test_update_no_type_change_{id(session)}"

        # Create collection with string field
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test type change prevention",
            "domain": "testing",
            "domain_scope": "Test collection for type change testing",
            "metadata_schema": {
                "custom": {
                    "score": {"type": "string"}
                }
            }
        })

        # Try to change score from string to number
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "score": {"type": "number"}  # Changed type
                }
            }
        })

        # Should error because type changed
        assert result.isError, "Should not allow changing field types"
        error_text = extract_error_text(result)
        assert "cannot change type" in error_text.lower() or "type" in error_text.lower()

    async def test_update_nonexistent_collection(self, mcp_session):
        """Test that updating nonexistent collection fails gracefully."""
        session, transport = mcp_session

        collection_name = f"nonexistent_collection_{id(session)}"

        # Try to update collection that doesn't exist
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "some_field": {"type": "string"}
                }
            }
        })

        # Should error
        assert result.isError, "Should error when collection doesn't exist"
        error_text = extract_error_text(result)
        assert "not found" in error_text.lower() or collection_name in error_text.lower()

    async def test_cannot_modify_immutable_mandatory_fields(self, mcp_session):
        """Test that mandatory fields (domain, domain_scope) cannot be changed."""
        session, transport = mcp_session

        collection_name = f"test_update_immutable_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test immutable field protection",
            "domain": "original_domain",
            "domain_scope": "Original scope description"
        })

        # Try to change domain (immutable field)
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "mandatory": {
                    "domain": "new_domain"  # Trying to change immutable field
                }
            }
        })

        # Should error because domain is immutable
        assert result.isError, "Should not allow changing immutable mandatory fields"
        error_text = extract_error_text(result)
        assert "immutable" in error_text.lower() or "domain" in error_text.lower()

    async def test_shorthand_field_syntax(self, mcp_session):
        """Test that shorthand syntax {"field": "type"} works."""
        session, transport = mcp_session

        collection_name = f"test_update_shorthand_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test shorthand syntax",
            "domain": "testing",
            "domain_scope": "Test collection for shorthand syntax testing"
        })

        # Add field using shorthand syntax
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "simple_field": "string"  # Shorthand: just the type
                }
            }
        })

        assert not result.isError, f"Shorthand syntax should work: {result}"
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify field was added
        assert "simple_field" in data["metadata_schema"]["custom"]
        field_spec = data["metadata_schema"]["custom"]["simple_field"]
        assert field_spec["type"] == "string"

    async def test_add_multiple_fields_at_once(self, mcp_session):
        """Test adding multiple new fields in a single update."""
        session, transport = mcp_session

        collection_name = f"test_update_multiple_{id(session)}"

        # Create collection with one field
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test multiple field additions",
            "domain": "testing",
            "domain_scope": "Test collection for multiple field testing",
            "metadata_schema": {
                "custom": {
                    "existing": {"type": "string"}
                }
            }
        })

        # Add multiple new fields
        result = await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "existing": {"type": "string"},  # Keep existing
                    "field1": {"type": "string"},
                    "field2": {"type": "number"},
                    "field3": {"type": "boolean"},
                    "field4": {"type": "array"}
                }
            }
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify all fields added
        assert data.get("fields_added") == 4  # 4 new fields
        assert data.get("total_custom_fields") == 5  # 1 existing + 4 new
        schema = data["metadata_schema"]["custom"]
        assert "existing" in schema
        assert "field1" in schema
        assert "field2" in schema
        assert "field3" in schema
        assert "field4" in schema

    async def test_get_schema_after_update(self, mcp_session):
        """Test that get_collection_metadata_schema reflects updates."""
        session, transport = mcp_session

        collection_name = f"test_update_get_schema_{id(session)}"

        # Create collection
        await session.call_tool("create_collection", {
            "name": collection_name,
            "description": "Test schema retrieval after update",
            "domain": "testing",
            "domain_scope": "Test collection for schema retrieval testing",
            "metadata_schema": {
                "custom": {
                    "original": {"type": "string"}
                }
            }
        })

        # Update schema
        await session.call_tool("update_collection_metadata", {
            "collection_name": collection_name,
            "new_fields": {
                "custom": {
                    "original": {"type": "string"},
                    "new_field": {"type": "number"}
                }
            }
        })

        # Get schema and verify it includes the update
        result = await session.call_tool("get_collection_metadata_schema", {
            "collection_name": collection_name
        })

        assert not result.isError
        text = extract_text_content(result)
        data = json.loads(text)

        # Verify both fields are in schema
        custom_fields = data["metadata_schema"]["custom_fields"]
        assert "original" in custom_fields
        assert "new_field" in custom_fields
