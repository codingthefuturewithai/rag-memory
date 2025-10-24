"""Comprehensive unit tests for metadata schema validation."""

import pytest
from src.ingestion.metadata_validator import MetadataValidator


class TestMetadataValidatorBasic:
    """Test basic validation with simple schemas."""

    def test_validate_empty_metadata_with_empty_schema(self):
        """Test validating empty metadata against empty schema."""
        schema = {"custom": {}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({})

        assert validated == {}
        assert errors == []

    def test_validate_none_metadata_returns_empty(self):
        """Test that None metadata is converted to empty dict."""
        schema = {"custom": {}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate(None)

        assert validated == {}
        assert errors == []

    def test_validate_non_dict_metadata_returns_error(self):
        """Test that non-dict metadata returns type error."""
        schema = {"custom": {}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate("not a dict")

        assert validated == {}
        assert len(errors) == 1
        assert "must be a dict" in errors[0]

    def test_validate_non_dict_metadata_with_list(self):
        """Test that list metadata returns type error."""
        schema = {"custom": {}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate(["item1", "item2"])

        assert validated == {}
        assert len(errors) == 1
        assert "must be a dict" in errors[0]


class TestMetadataValidatorStringType:
    """Test validation of string type fields."""

    def test_validate_string_field_success(self):
        """Test validating correct string field."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"title": "My Document"})

        assert validated == {"title": "My Document"}
        assert errors == []

    def test_validate_string_field_with_wrong_type(self):
        """Test that non-string value fails for string field."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"title": 123})

        assert validated == {}
        assert len(errors) == 1
        assert "Field 'title'" in errors[0]
        assert "expected string" in errors[0]

    def test_validate_optional_string_field_missing(self):
        """Test that optional string field can be missing."""
        schema = {"custom": {"title": {"type": "string", "required": False}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({})

        assert validated == {}
        assert errors == []

    def test_validate_required_string_field_missing(self):
        """Test that required string field raises error when missing."""
        schema = {"custom": {"title": {"type": "string", "required": True}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({})

        assert validated == {}
        assert len(errors) == 1
        assert "Required field 'title'" in errors[0]


class TestMetadataValidatorNumberType:
    """Test validation of number type fields."""

    def test_validate_number_field_with_int(self):
        """Test validating number field with integer."""
        schema = {"custom": {"count": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": 42})

        assert validated == {"count": 42}
        assert errors == []

    def test_validate_number_field_with_float(self):
        """Test validating number field with float."""
        schema = {"custom": {"score": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"score": 3.14})

        assert validated == {"score": 3.14}
        assert errors == []

    def test_validate_number_field_with_string_fails(self):
        """Test that string fails for number field."""
        schema = {"custom": {"count": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": "42"})

        assert validated == {}
        assert len(errors) == 1
        assert "expected number" in errors[0]


class TestMetadataValidatorBooleanType:
    """Test validation of boolean type fields."""

    def test_validate_boolean_field_true(self):
        """Test validating boolean field with True."""
        schema = {"custom": {"published": {"type": "boolean"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"published": True})

        assert validated == {"published": True}
        assert errors == []

    def test_validate_boolean_field_false(self):
        """Test validating boolean field with False."""
        schema = {"custom": {"published": {"type": "boolean"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"published": False})

        assert validated == {"published": False}
        assert errors == []

    def test_validate_boolean_field_with_string_fails(self):
        """Test that string fails for boolean field."""
        schema = {"custom": {"published": {"type": "boolean"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"published": "true"})

        assert validated == {}
        assert len(errors) == 1
        assert "expected boolean" in errors[0]


class TestMetadataValidatorArrayType:
    """Test validation of array type fields."""

    def test_validate_array_field_with_list(self):
        """Test validating array field with list."""
        schema = {"custom": {"tags": {"type": "array"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"tags": ["tag1", "tag2"]})

        assert validated == {"tags": ["tag1", "tag2"]}
        assert errors == []

    def test_validate_array_field_empty_list(self):
        """Test validating array field with empty list."""
        schema = {"custom": {"tags": {"type": "array"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"tags": []})

        assert validated == {"tags": []}
        assert errors == []

    def test_validate_array_field_with_string_fails(self):
        """Test that string fails for array field."""
        schema = {"custom": {"tags": {"type": "array"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"tags": "tag1,tag2"})

        assert validated == {}
        assert len(errors) == 1
        assert "expected array" in errors[0]


class TestMetadataValidatorObjectType:
    """Test validation of object type fields."""

    def test_validate_object_field_with_dict(self):
        """Test validating object field with dict."""
        schema = {"custom": {"metadata": {"type": "object"}}, "system": []}
        validator = MetadataValidator(schema)

        metadata_value = {"nested_key": "nested_value"}
        validated, errors = validator.validate({"metadata": metadata_value})

        assert validated == {"metadata": metadata_value}
        assert errors == []

    def test_validate_object_field_empty_dict(self):
        """Test validating object field with empty dict."""
        schema = {"custom": {"metadata": {"type": "object"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"metadata": {}})

        assert validated == {"metadata": {}}
        assert errors == []

    def test_validate_object_field_with_string_fails(self):
        """Test that string fails for object field."""
        schema = {"custom": {"metadata": {"type": "object"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"metadata": "not an object"})

        assert validated == {}
        assert len(errors) == 1
        assert "expected object" in errors[0]


class TestMetadataValidatorEnumConstraint:
    """Test validation with enum constraints."""

    def test_validate_enum_field_valid_value(self):
        """Test that value in enum list passes validation."""
        schema = {
            "custom": {"status": {"type": "string", "enum": ["draft", "published", "archived"]}},
            "system": []
        }
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"status": "published"})

        assert validated == {"status": "published"}
        assert errors == []

    def test_validate_enum_field_invalid_value(self):
        """Test that value not in enum list fails validation."""
        schema = {
            "custom": {"status": {"type": "string", "enum": ["draft", "published", "archived"]}},
            "system": []
        }
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"status": "invalid"})

        assert validated == {}
        assert len(errors) == 1
        assert "not in allowed values" in errors[0]
        assert "['draft', 'published', 'archived']" in errors[0]

    def test_validate_enum_with_numbers(self):
        """Test enum constraint with numeric values."""
        schema = {
            "custom": {"priority": {"type": "number", "enum": [1, 2, 3]}},
            "system": []
        }
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"priority": 2})

        assert validated == {"priority": 2}
        assert errors == []

    def test_validate_enum_with_number_fails(self):
        """Test that number not in enum fails."""
        schema = {
            "custom": {"priority": {"type": "number", "enum": [1, 2, 3]}},
            "system": []
        }
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"priority": 5})

        assert validated == {}
        assert len(errors) == 1
        assert "not in allowed values" in errors[0]


class TestMetadataValidatorMultipleFields:
    """Test validation with multiple fields."""

    def test_validate_multiple_fields_all_valid(self):
        """Test validating multiple valid fields."""
        schema = {
            "custom": {
                "title": {"type": "string"},
                "count": {"type": "number"},
                "published": {"type": "boolean"}
            },
            "system": []
        }
        validator = MetadataValidator(schema)

        metadata = {"title": "Test", "count": 42, "published": True}
        validated, errors = validator.validate(metadata)

        assert validated == metadata
        assert errors == []

    def test_validate_multiple_fields_some_invalid(self):
        """Test validating multiple fields with some invalid."""
        schema = {
            "custom": {
                "title": {"type": "string"},
                "count": {"type": "number"},
                "published": {"type": "boolean"}
            },
            "system": []
        }
        validator = MetadataValidator(schema)

        metadata = {"title": "Test", "count": "not a number", "published": True}
        validated, errors = validator.validate(metadata)

        # Validator continues with valid fields even when some are invalid
        assert "title" in validated
        assert "count" not in validated
        assert "published" in validated
        assert len(errors) == 1
        assert "count" in errors[0]

    def test_validate_multiple_required_fields_missing(self):
        """Test validating when multiple required fields are missing."""
        schema = {
            "custom": {
                "title": {"type": "string", "required": True},
                "count": {"type": "number", "required": True},
                "published": {"type": "boolean"}
            },
            "system": []
        }
        validator = MetadataValidator(schema)

        metadata = {"published": True}
        validated, errors = validator.validate(metadata)

        # Valid optional field is included, required fields are missing
        assert "published" in validated
        assert "title" not in validated
        assert "count" not in validated
        assert len(errors) == 2
        assert any("title" in error for error in errors)
        assert any("count" in error for error in errors)

    def test_validate_partial_field_submission(self):
        """Test validating when some optional fields are not provided."""
        schema = {
            "custom": {
                "title": {"type": "string", "required": True},
                "count": {"type": "number", "required": False},
                "published": {"type": "boolean", "required": False}
            },
            "system": []
        }
        validator = MetadataValidator(schema)

        metadata = {"title": "Test"}
        validated, errors = validator.validate(metadata)

        assert validated == {"title": "Test"}
        assert errors == []


class TestMetadataValidatorExtraFields:
    """Test handling of fields not in schema."""

    def test_validate_extra_fields_removed_silently(self):
        """Test that extra fields not in schema are removed."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        metadata = {"title": "Test", "extra_field": "extra_value"}
        validated, errors = validator.validate(metadata)

        assert "title" in validated
        assert "extra_field" not in validated
        assert errors == []

    def test_validate_multiple_extra_fields_removed(self):
        """Test that multiple extra fields are all removed."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        metadata = {"title": "Test", "extra1": "val1", "extra2": "val2"}
        validated, errors = validator.validate(metadata)

        assert validated == {"title": "Test"}
        assert errors == []


class TestMetadataValidatorShorthandSchema:
    """Test shorthand schema format (type as string instead of dict)."""

    def test_validate_shorthand_string_type(self):
        """Test that shorthand schema format works for types."""
        # Shorthand: {"custom": {"title": "string"}} instead of {"custom": {"title": {"type": "string"}}}
        schema = {"custom": {"title": "string"}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"title": "Test"})

        assert validated == {"title": "Test"}
        assert errors == []

    def test_validate_shorthand_number_type(self):
        """Test shorthand schema with number type."""
        schema = {"custom": {"count": "number"}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": 42})

        assert validated == {"count": 42}
        assert errors == []

    def test_validate_shorthand_fails_with_wrong_type(self):
        """Test that shorthand schema still validates types correctly."""
        schema = {"custom": {"count": "number"}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": "not a number"})

        assert validated == {}
        assert len(errors) == 1


class TestMetadataValidatorInvalidType:
    """Test handling of invalid type definitions in schema."""

    def test_validate_invalid_type_in_schema(self):
        """Test that invalid type in schema returns False for validation."""
        schema = {"custom": {"field": {"type": "unknown_type"}}, "system": []}
        validator = MetadataValidator(schema)

        # When schema has invalid type, field validation should fail
        validated, errors = validator.validate({"field": "any_value"})

        assert validated == {}
        assert len(errors) == 1


class TestMetadataValidatorSystemFields:
    """Test handling of system fields."""

    def test_system_fields_defined_but_not_enforced(self):
        """Test that system fields are stored in schema but not actively validated."""
        schema = {"custom": {"title": {"type": "string"}}, "system": ["created_at", "updated_at"]}
        validator = MetadataValidator(schema)

        # System fields aren't validated or enforced by this validator
        validated, errors = validator.validate({"title": "Test"})

        assert validated == {"title": "Test"}
        assert errors == []


class TestMetadataValidatorEdgeCases:
    """Test edge cases and special scenarios."""

    def test_validate_empty_schema_with_data(self):
        """Test validation when schema has no fields but data is provided."""
        schema = {"custom": {}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"any_field": "any_value"})

        # Extra fields should be removed
        assert validated == {}
        assert errors == []

    def test_validate_boolean_zero_vs_false(self):
        """Test that 0 (falsy but not boolean) is rejected for boolean field."""
        schema = {"custom": {"flag": {"type": "boolean"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"flag": 0})

        assert validated == {}
        assert len(errors) == 1

    def test_validate_empty_string_for_string_field(self):
        """Test that empty string is valid for string field."""
        schema = {"custom": {"description": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"description": ""})

        assert validated == {"description": ""}
        assert errors == []

    def test_validate_unicode_strings(self):
        """Test validation with unicode characters."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"title": "Тест 测试 تجربة"})

        assert validated == {"title": "Тест 测试 تجربة"}
        assert errors == []

    def test_validate_very_large_number(self):
        """Test validation with very large numbers."""
        schema = {"custom": {"value": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        large_num = 9999999999999999999
        validated, errors = validator.validate({"value": large_num})

        assert validated == {"value": large_num}
        assert errors == []

    def test_validate_deeply_nested_object(self):
        """Test validation with deeply nested object."""
        schema = {"custom": {"metadata": {"type": "object"}}, "system": []}
        validator = MetadataValidator(schema)

        nested = {"level1": {"level2": {"level3": {"key": "value"}}}}
        validated, errors = validator.validate({"metadata": nested})

        assert validated == {"metadata": nested}
        assert errors == []


class TestMetadataValidatorErrorMessages:
    """Test that error messages are clear and helpful."""

    def test_error_message_contains_field_name(self):
        """Test that error messages include the field name."""
        schema = {"custom": {"title": {"type": "string"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"title": 123})

        assert len(errors) == 1
        assert "title" in errors[0]

    def test_error_message_contains_expected_type(self):
        """Test that error messages include the expected type."""
        schema = {"custom": {"count": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": "not a number"})

        assert len(errors) == 1
        assert "number" in errors[0]

    def test_error_message_contains_actual_type(self):
        """Test that error messages include the actual type received."""
        schema = {"custom": {"count": {"type": "number"}}, "system": []}
        validator = MetadataValidator(schema)

        validated, errors = validator.validate({"count": "not a number"})

        assert len(errors) == 1
        assert "str" in errors[0]


class TestMetadataValidatorIntegration:
    """Integration tests simulating real-world usage."""

    def test_validate_document_metadata_complete_schema(self):
        """Test validation with a complete realistic document schema."""
        schema = {
            "custom": {
                "document_type": {"type": "string", "enum": ["article", "guide", "tutorial"]},
                "author": {"type": "string", "required": True},
                "publication_date": {"type": "string"},
                "tags": {"type": "array"},
                "version": {"type": "number"},
                "is_published": {"type": "boolean", "required": True},
                "metadata": {"type": "object"}
            },
            "system": ["created_at", "updated_at"]
        }
        validator = MetadataValidator(schema)

        document = {
            "document_type": "article",
            "author": "John Doe",
            "publication_date": "2024-01-01",
            "tags": ["python", "database"],
            "version": 1,
            "is_published": True,
            "metadata": {"source": "github", "license": "MIT"},
            "extra_field": "should_be_ignored"
        }

        validated, errors = validator.validate(document)

        assert errors == []
        assert "extra_field" not in validated
        assert validated["author"] == "John Doe"
        assert validated["version"] == 1

    def test_validate_incomplete_required_fields(self):
        """Test that incomplete required fields are caught."""
        schema = {
            "custom": {
                "author": {"type": "string", "required": True},
                "is_published": {"type": "boolean", "required": True}
            },
            "system": []
        }
        validator = MetadataValidator(schema)

        document = {"author": "John Doe"}  # Missing is_published

        validated, errors = validator.validate(document)

        assert len(errors) == 1
        assert "is_published" in errors[0]

    def test_validate_enum_type_mismatch(self):
        """Test that enum validation fails on type mismatch."""
        schema = {
            "custom": {"status": {"type": "string", "enum": ["active", "inactive"]}},
            "system": []
        }
        validator = MetadataValidator(schema)

        document = {"status": 1}  # Wrong type (number instead of string)

        validated, errors = validator.validate(document)

        assert len(errors) == 1
        assert "expected string" in errors[0]
