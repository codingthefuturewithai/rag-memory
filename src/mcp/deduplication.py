"""
Request deduplication for MCP tools.

Prevents duplicate concurrent requests to non-idempotent operations like ingestion.
Uses function signature introspection to automatically capture all parameters without
hard-coding them, making it resilient to signature changes.
"""

import hashlib
import json
import inspect
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)


class RequestDeduplicator:
    """
    Tracks active requests to prevent duplicate concurrent operations.

    Uses function signature introspection to automatically capture all parameters
    and create deterministic hashes. Ignores client-preference fields that don't
    affect the logical request (like include_document_ids).
    """

    def __init__(self):
        self._active_requests: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        # Client-preference fields that don't affect the logical request
        # These are typically "include_*" flags that control response format
        self._ignored_fields = {
            'include_document_ids',
            'include_chunk_ids',
            'include_metadata',
            'include_source',
            'include_details',
            'include_chunks',
            'include_url_lists'
        }

        # Cache function signatures to avoid repeated introspection
        # Populated once per function at decoration time
        self._signature_cache: Dict[Callable, inspect.Signature] = {}

    def _get_signature(self, func: Callable) -> inspect.Signature:
        """Get function signature (cached after first call)."""
        if func not in self._signature_cache:
            self._signature_cache[func] = inspect.signature(func)
        return self._signature_cache[func]

    def _hash_request(
        self,
        tool_name: str,
        func: Callable,
        bound_args: inspect.BoundArguments
    ) -> str:
        """
        Create deterministic hash from bound arguments.

        Args:
            tool_name: Name of the tool (for namespacing)
            func: The function being called (for signature cache)
            bound_args: Bound arguments from sig.bind()

        Returns:
            16-character hex hash uniquely identifying this request
        """
        normalized_params = {}

        for param_name, value in bound_args.arguments.items():
            # Skip client-preference fields (don't affect logical request)
            if param_name in self._ignored_fields:
                continue

            # Normalize value for deterministic hashing
            if isinstance(value, dict):
                # Sort dict keys for deterministic JSON
                value = json.dumps(value, sort_keys=True)
            elif isinstance(value, list):
                # Convert list to tuple for hashability
                value = tuple(value)

            normalized_params[param_name] = value

        # Create deterministic payload
        payload = json.dumps({
            'tool': tool_name,
            'params': normalized_params
        }, sort_keys=True, default=str)  # default=str handles non-JSON types

        # Return first 16 chars of SHA256 (sufficient for collision resistance)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    async def check_and_register(
        self,
        tool_name: str,
        func: Callable,
        bound_args: inspect.BoundArguments
    ) -> Optional[str]:
        """
        Check if this exact request is already processing.

        If not a duplicate, registers it as active.

        Args:
            tool_name: Name of the tool
            func: The function being called
            bound_args: Bound arguments

        Returns:
            Error message if duplicate, None if okay to proceed
        """
        request_hash = self._hash_request(tool_name, func, bound_args)

        async with self._lock:
            if request_hash in self._active_requests:
                info = self._active_requests[request_hash]
                elapsed = (datetime.now() - info['timestamp']).total_seconds()

                logger.warning(
                    f"Duplicate request detected for {tool_name} "
                    f"(hash: {request_hash}, elapsed: {elapsed:.0f}s)"
                )

                return (
                    f"This exact request is already processing (started {elapsed:.0f}s ago). "
                    f"Please wait for the current operation to complete."
                )

            # Register as active
            self._active_requests[request_hash] = {
                'timestamp': datetime.now(),
                'tool': tool_name
            }

            logger.debug(f"Registered request {tool_name} (hash: {request_hash})")
            return None

    async def unregister(
        self,
        tool_name: str,
        func: Callable,
        bound_args: inspect.BoundArguments
    ):
        """
        Remove request from tracking.

        Should be called in a finally block to ensure cleanup even on errors.
        """
        request_hash = self._hash_request(tool_name, func, bound_args)

        async with self._lock:
            if request_hash in self._active_requests:
                del self._active_requests[request_hash]
                logger.debug(f"Unregistered request {tool_name} (hash: {request_hash})")


# Global instance (shared across all tools)
_deduplicator = RequestDeduplicator()


def deduplicate_request(tool_name: Optional[str] = None):
    """
    Decorator to prevent duplicate concurrent requests.

    Automatically captures all function parameters using signature introspection.
    Parameters are hashed to create a unique request ID, which is tracked during
    execution to prevent duplicate concurrent calls.

    Client-preference fields (like include_document_ids) are ignored since they
    don't affect the logical request, only the response format.

    Usage:
        @deduplicate_request()
        async def ingest_url_impl(url, collection_name, ...):
            # ... implementation ...
            pass

    Or with custom tool name:
        @deduplicate_request('custom_name')
        async def my_tool(...):
            pass

    Args:
        tool_name: Optional custom name (defaults to function name)

    Returns:
        Decorated function that includes deduplication logic
    """
    def decorator(func: Callable):
        # Use function name if tool_name not provided
        name = tool_name or func.__name__

        # Cache signature at decoration time (happens once at server startup)
        sig = _deduplicator._get_signature(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Bind arguments to signature (fast - just parameter matching)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()  # Fill in default values

            # Check for duplicate
            error = await _deduplicator.check_and_register(name, func, bound_args)
            if error:
                logger.info(f"Rejected duplicate request for {name}")
                return {'error': error, 'status': 'duplicate_request'}

            try:
                # Call original function
                result = await func(*args, **kwargs)
                return result
            finally:
                # Always cleanup, even if function raises exception
                await _deduplicator.unregister(name, func, bound_args)

        return wrapper
    return decorator
