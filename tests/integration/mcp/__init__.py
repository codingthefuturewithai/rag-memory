"""MCP Integration Tests

Tests for MCP tool functionality using real client-server interaction.
Uses STDIO transport with actual MCP SDK components.

Each test calls real MCP tools through a ClientSession and validates
that the tool implementations actually work (not just the protocol).
"""
