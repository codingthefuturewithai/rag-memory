"""
MCP (Model Context Protocol) server module.

Exposes RAG functionality to AI agents via standardized MCP protocol.
"""

from src.mcp.server import mcp, main

__all__ = ["mcp", "main"]
