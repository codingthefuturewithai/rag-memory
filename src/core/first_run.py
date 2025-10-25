"""Configuration validation for RAG Memory.

This module validates that required configuration exists at startup.
For CLI usage, provides helpful error messages pointing to setup scripts.
Does NOT create configuration - that's the setup script's responsibility.
"""

import os
import sys
from pathlib import Path

from rich.console import Console

from .config_loader import (
    get_config_path,
    ensure_config_exists,
    get_missing_config_keys,
    load_environment_variables,
)

console = Console()


def validate_config_exists() -> bool:
    """
    Validate that configuration file exists and is complete.

    For CLI usage: Exits with helpful error message if config is missing or incomplete.
    For MCP usage: Can be checked before server startup.

    Returns:
        True if config is valid, False if invalid (CLI will have exited)
    """
    config_path = get_config_path()

    # Check if config file exists
    if not config_path.exists():
        console.print("\n[bold red]✗ Configuration not found[/bold red]")
        console.print(f"[yellow]Expected location: {config_path}[/yellow]\n")
        console.print("[cyan]To set up RAG Memory, run:[/cyan]")
        console.print("[bold]  python scripts/setup.py[/bold]\n")
        console.print("[dim]This will:[/dim]")
        console.print("[dim]  - Create Docker containers (PostgreSQL + Neo4j)[/dim]")
        console.print("[dim]  - Generate configuration file[/dim]")
        console.print("[dim]  - Optionally install CLI tool system-wide[/dim]\n")
        return False

    # Check if all required configuration is present
    missing = get_missing_config_keys()
    if missing:
        console.print("\n[bold red]✗ Configuration is incomplete[/bold red]")
        console.print(f"[yellow]Missing settings: {', '.join(missing)}[/yellow]")
        console.print(f"[dim]Configuration file: {config_path}[/dim]\n")
        console.print("[cyan]To update configuration, run:[/cyan]")
        console.print("[bold]  python scripts/update-config.py[/bold]\n")
        console.print("[dim]Then rebuild Docker containers:[/dim]")
        console.print("[dim]  docker-compose up -d --build[/dim]\n")
        return False

    return True


def ensure_config_or_exit():
    """
    Ensure configuration exists and is valid, or exit with helpful message.

    This is called by CLI and MCP server at startup.
    Loads environment variables into os.environ for use by the application.

    Exits the program if configuration is missing or incomplete.
    """
    # Load environment variables from config file
    load_environment_variables()

    # Validate configuration is complete
    if not validate_config_exists():
        sys.exit(1)
