"""Metadata schema validation for documents during ingest."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MetadataValidator:
    """Validates custom metadata against a collection's declared schema."""

    def __init__(self, metadata_schema: dict):
        """
        Initialize validator with a collection's metadata schema.

        Args:
            metadata_schema: Schema dict from collections.metadata_schema
                Format: {"custom": {...}, "system": [...]}
        """
        self.schema = metadata_schema
        self.custom_schema = metadata_schema.get("custom", {})
        self.system_fields = metadata_schema.get("system", [])

    def validate(self, custom_metadata: dict | None) -> tuple[dict, list]:
        """
        Validate custom metadata against schema.

        Args:
            custom_metadata: Custom metadata dict from user.

        Returns:
            (validated_metadata, errors)
            - validated_metadata: Cleaned metadata (extra fields removed)
            - errors: List of validation error messages (empty if valid)

        Note:
            Does NOT raise exceptions. Returns errors as list for graceful handling.
            Extra fields not in schema are silently removed (don't store unknown fields).
        """
        if custom_metadata is None:
            custom_metadata = {}

        if not isinstance(custom_metadata, dict):
            return {}, [
                f"Custom metadata must be a dict, got {type(custom_metadata).__name__}"
            ]

        validated = {}
        errors = []

        # Check each declared field in the schema
        for field_name, field_def in self.custom_schema.items():
            if not isinstance(field_def, dict):
                field_def = {"type": str(field_def)}  # Allow shorthand

            field_type = field_def.get("type")
            is_required = field_def.get("required", False)
            enum_values = field_def.get("enum")

            if field_name not in custom_metadata:
                if is_required:
                    errors.append(f"Required field '{field_name}' is missing")
                continue

            value = custom_metadata[field_name]

            # Type validation
            if not self._validate_type(value, field_type):
                errors.append(
                    f"Field '{field_name}' has type {type(value).__name__}, "
                    f"expected {field_type}"
                )
                continue

            # Enum validation (if specified)
            if enum_values is not None:
                if value not in enum_values:
                    errors.append(
                        f"Field '{field_name}' value '{value}' not in allowed values: {enum_values}"
                    )
                    continue

            validated[field_name] = value

        # Warn about extra fields not in schema (but don't fail validation)
        extra_fields = set(custom_metadata.keys()) - set(self.custom_schema.keys())
        if extra_fields:
            logger.warning(
                f"Custom metadata contains unknown fields: {extra_fields}. "
                f"These will be discarded."
            )

        return validated, errors

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return False

        return isinstance(value, expected_python_type)
