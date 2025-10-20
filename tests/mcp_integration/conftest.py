"""MCP Integration Test Configuration - STDIO Transport Only

Provides pytest fixtures for testing MCP tools via real client-server interaction.
Uses STDIO transport with actual MCP SDK components.
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path
from typing import AsyncGenerator
import pytest
from pytest_asyncio import fixture
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment
import atexit
import signal


@fixture
async def mcp_stdio_session() -> AsyncGenerator[ClientSession, None]:
    """Provide an MCP client session via STDIO transport.

    Creates a real MCP server subprocess and connects via STDIO.
    Guarantees complete cleanup even on test failure.

    Yields:
        ClientSession: Connected MCP client session
    """
    session = None
    stdio_context = None
    stdio_proc = None

    def emergency_cleanup():
        """Emergency cleanup if test crashes."""
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

    # Register emergency cleanup to run at exit
    atexit.register(emergency_cleanup)

    try:
        # Setup STDIO transport
        project_root = Path(__file__).parent.parent.parent
        server_module = "src.mcp.server"

        # Build environment
        env = get_default_environment()

        # Add database environment variables (critical for test setup)
        db_vars = [
            "DATABASE_URL",
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "OPENAI_API_KEY",
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

        yield session

    finally:
        # Cleanup
        if session:
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                print(f"Session cleanup error: {e}", file=sys.stderr)

        if stdio_context:
            try:
                await stdio_context.__aexit__(None, None, None)
            except Exception as e:
                print(f"STDIO context cleanup error: {e}", file=sys.stderr)


# Helper functions for extracting MCP response content

def extract_text_content(result) -> str | None:
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


def extract_error_text(result) -> str | None:
    """Extract error text from MCP error result.

    Args:
        result: MCP CallToolResult

    Returns:
        Error text if result is an error, None otherwise
    """
    if result.isError and result.content:
        return extract_text_content(result)
    return None
