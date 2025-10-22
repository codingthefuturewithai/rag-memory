"""MCP Integration Test Configuration - STDIO Transport Only

Provides pytest fixtures for testing MCP tools via real client-server interaction.
Uses STDIO transport with actual MCP SDK components.

Key design:
- Starts real MCP server subprocess (src.mcp.server)
- Creates ClientSession with actual MCP protocol
- Tests invoke tools via session.call_tool() (real client-server flow)
- Validates that tool implementations work, not just protocol
- Uses shared database fixtures from tests/conftest.py for data setup/teardown
"""

import asyncio
import os
import sys
import subprocess
import time
import signal
import atexit
from pathlib import Path
from typing import AsyncGenerator, Tuple, Optional
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment


# Mark all tests in this module as async
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Configure anyio to use asyncio backend only.

    Without this, pytest-anyio tries to run tests with both asyncio and trio,
    but trio is not installed, causing test failures.
    """
    return "asyncio"


@pytest.fixture(params=["stdio"])
async def mcp_session(request) -> AsyncGenerator[Tuple[ClientSession, str], None]:
    """Provide an MCP client session for testing with STDIO transport.

    This fixture:
    1. Starts a real MCP server subprocess (src.mcp.server)
    2. Connects via STDIO transport with actual MCP protocol
    3. Initializes ClientSession and protocol
    4. Yields (session, transport_name) to tests
    5. Guarantees complete cleanup even on test failure

    The session uses the same database fixtures from tests/conftest.py,
    so data setup/teardown is automatic per test.

    Args:
        request: pytest request object containing the transport parameter

    Yields:
        Tuple of (ClientSession, transport_name)
    """
    session = None
    cleanup_funcs = []
    stdio_proc = None

    # Register pytest finalizer for guaranteed cleanup
    def emergency_cleanup():
        """Emergency cleanup that runs no matter what."""
        nonlocal stdio_proc
        if stdio_proc:
            try:
                stdio_proc.terminate()
                stdio_proc.wait(timeout=2)
            except Exception:
                try:
                    stdio_proc.kill()
                except Exception:
                    pass

    request.addfinalizer(emergency_cleanup)

    try:
        # Setup STDIO transport
        project_root = Path(__file__).parent.parent.parent
        server_module = "src.mcp.server"

        # Build environment
        env = get_default_environment()

        # Add database environment variables (critical for MCP server to connect)
        db_vars = [
            "DATABASE_URL",
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "OPENAI_API_KEY",
            "ENV_NAME",
            "POSTGRES_PORT",
            "POSTGRES_DB",
        ]

        for var in db_vars:
            if var in os.environ:
                env[var] = os.environ[var]

        # Add coverage environment variables if present
        coverage_vars = [
            "COVERAGE_PROCESS_START",
            "COVERAGE_FILE",
            "COVERAGE_CORE",
        ]

        for var in coverage_vars:
            if var in os.environ:
                env[var] = os.environ[var]

        # Add PYTHONPATH
        if "PYTHONPATH" in os.environ:
            env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        else:
            env["PYTHONPATH"] = str(project_root)

        # Create server parameters
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", server_module],
            env=env
        )

        # Start stdio client
        import inspect
        sig = inspect.signature(stdio_client)
        if 'errlog' in sig.parameters:
            stdio_context = stdio_client(server_params, errlog=sys.stderr)
        else:
            stdio_context = stdio_client(server_params)

        read, write = await stdio_context.__aenter__()

        # Create and initialize session
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        # Add cleanup for stdio
        async def cleanup_stdio():
            if session:
                await session.__aexit__(None, None, None)
            await stdio_context.__aexit__(None, None, None)

        cleanup_funcs.append(cleanup_stdio)

        # Yield the session and transport name
        yield session, "stdio"

    finally:
        # Run all cleanup functions
        for cleanup_func in cleanup_funcs:
            try:
                await cleanup_func()
            except RuntimeError as e:
                # Ignore "Event loop is closed" errors during cleanup
                # These happen when pytest-anyio tears down the loop before cleanup completes
                if "Event loop is closed" not in str(e):
                    print(f"Cleanup error: {e}", file=sys.stderr)
            except BaseException as e:
                # Catch ExceptionGroup from httpx background task cleanup
                # These are harmless "Event loop is closed" errors from connection cleanup
                error_str = str(e)
                if "Event loop is closed" not in error_str:
                    print(f"Cleanup error: {e}", file=sys.stderr)


# Helper functions for extracting MCP response content


def extract_text_content(result) -> Optional[str]:
    """Extract text content from MCP tool result.

    Args:
        result: MCP CallToolResult

    Returns:
        Text content if found, None otherwise
    """
    from mcp import types

    for content in result.content:
        if isinstance(content, types.TextContent):
            return content.text
    return None


def extract_result_data(result):
    """Extract data from MCP tool result, using structuredContent when available.

    MCP protocol optimization: When tools return lists, structuredContent contains
    the full list, while content contains separate TextContent objects per item.

    Args:
        result: MCP CallToolResult

    Returns:
        Python object (list, dict, etc.) extracted from structuredContent or parsed JSON
    """
    import json

    # Use structuredContent if available (MCP protocol optimization for lists)
    if hasattr(result, 'structuredContent') and result.structuredContent:
        return result.structuredContent.get('result')

    # Fallback to text parsing
    text = extract_text_content(result)
    if text:
        return json.loads(text)

    return None


def extract_error_text(result) -> Optional[str]:
    """Extract error text from MCP error result.

    Args:
        result: MCP CallToolResult

    Returns:
        Error text if result is an error, None otherwise
    """
    if result.isError and result.content:
        return extract_text_content(result)
    return None
