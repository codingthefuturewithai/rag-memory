"""Configuration management commands."""

import os
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from src.core.config_loader import (
    get_config_path,
    load_config,
    save_config,
    REQUIRED_SERVER_KEYS,
    OPTIONAL_SERVER_KEYS,
)

console = Console()


@click.group()
def config():
    """Manage RAG Memory configuration."""
    pass


@config.command("show")
@click.option("--path", is_flag=True, help="Show config file path only")
def config_show(path):
    """Display current configuration.

    Shows the configuration from the active config.yaml file, including
    server settings and mounted directories. Sensitive values like API
    keys are masked for security.

    Examples:
        # Show full configuration
        rag config show

        # Show config file path
        rag config show --path
    """
    try:
        config_path = get_config_path()

        if path:
            console.print(f"[cyan]{config_path}[/cyan]")
            return

        if not config_path.exists():
            console.print(f"[yellow]⚠ Config file not found[/yellow]")
            console.print(f"Expected location: {config_path}")
            console.print("\n[dim]Run 'python scripts/setup.py' to create configuration[/dim]")
            sys.exit(1)

        # Load and display config
        config_data = load_config(config_path)

        if not config_data:
            console.print(f"[yellow]⚠ Config file is empty or invalid[/yellow]")
            console.print(f"Location: {config_path}")
            sys.exit(1)

        console.print(f"[bold blue]Configuration File:[/bold blue] {config_path}\n")

        # Display server settings
        server_config = config_data.get('server', {})
        if server_config:
            console.print("[bold cyan]Server Settings:[/bold cyan]")
            for key, value in server_config.items():
                # Mask sensitive values
                if 'key' in key.lower() or 'password' in key.lower():
                    masked_value = value[:8] + '...' if len(str(value)) > 8 else '***'
                    console.print(f"  {key}: [dim]{masked_value}[/dim]")
                else:
                    console.print(f"  {key}: {value}")
            console.print()

        # Display mounts
        mounts = config_data.get('mounts', [])
        if mounts:
            console.print("[bold cyan]Mounted Directories:[/bold cyan]")
            for mount in mounts:
                mount_path = mount.get('path', 'N/A')
                read_only = mount.get('read_only', True)
                ro_label = "[dim](read-only)[/dim]" if read_only else "[yellow](read-write)[/yellow]"
                console.print(f"  • {mount_path} {ro_label}")
            console.print()

        # Show missing required keys if any
        missing_keys = []
        for key in REQUIRED_SERVER_KEYS:
            if key not in server_config:
                # Check if it's in environment variables
                env_var = key.upper()
                if env_var not in os.environ:
                    missing_keys.append(key)

        if missing_keys:
            console.print("[bold yellow]⚠ Missing Required Configuration:[/bold yellow]")
            for key in missing_keys:
                console.print(f"  • {key}")
            console.print("\n[dim]Run 'rag config set <key> <value>' to add missing values[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@config.command("edit")
def config_edit():
    """Open configuration file in system editor.

    Opens the config.yaml file in your default text editor. The editor
    is determined by the $EDITOR environment variable (defaults to 'nano'
    on Unix systems, 'notepad' on Windows).

    Examples:
        # Edit with default editor
        rag config edit

        # Use specific editor (bash)
        EDITOR=vim rag config edit
    """
    try:
        config_path = get_config_path()

        if not config_path.exists():
            console.print(f"[yellow]⚠ Config file not found[/yellow]")
            console.print(f"Expected location: {config_path}")
            console.print("\n[dim]Run 'python scripts/setup.py' to create configuration[/dim]")
            sys.exit(1)

        # Determine editor to use
        if os.name == 'nt':
            # Windows
            editor = os.getenv('EDITOR', 'notepad')
        else:
            # Unix-like systems
            editor = os.getenv('EDITOR', 'nano')

        console.print(f"[dim]Opening {config_path} with {editor}...[/dim]\n")

        # Open editor
        try:
            subprocess.run([editor, str(config_path)], check=True)
            console.print("\n[bold green]✓ Editor closed[/bold green]")
        except subprocess.CalledProcessError:
            console.print(f"[bold red]✗ Editor exited with error[/bold red]")
            sys.exit(1)
        except FileNotFoundError:
            console.print(f"[bold red]✗ Editor '{editor}' not found[/bold red]")
            console.print("[yellow]Set the $EDITOR environment variable to your preferred editor[/yellow]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--section", default="server", help="Config section (default: server)")
def config_set(key, value, section):
    """Set a specific configuration value.

    Updates a configuration key in the config.yaml file. By default,
    updates are made in the 'server' section. Keys are stored in
    lowercase with underscores (e.g., 'api_key' becomes 'api_key').

    Examples:
        # Set database URL
        rag config set database_url postgresql://user:pass@localhost:5432/db

        # Set Neo4j credentials
        rag config set neo4j_user admin
        rag config set neo4j_password mypassword

        # Set optional Graphiti model
        rag config set graphiti_model gpt-4
    """
    try:
        config_path = get_config_path()

        # Load existing config or create empty
        if config_path.exists():
            config_data = load_config(config_path)
        else:
            config_data = {}
            console.print(f"[dim]Creating new config file at {config_path}[/dim]")

        # Ensure section exists
        if section not in config_data:
            config_data[section] = {}

        # Normalize key to lowercase with underscores
        normalized_key = key.lower().replace('-', '_')

        # Update value
        old_value = config_data[section].get(normalized_key)
        config_data[section][normalized_key] = value

        # Save config
        if save_config(config_data, config_path):
            if old_value:
                console.print(f"[bold green]✓ Updated {section}.{normalized_key}[/bold green]")
                # Don't show old/new values for sensitive keys
                if 'key' not in normalized_key and 'password' not in normalized_key:
                    console.print(f"  Old: {old_value}")
                    console.print(f"  New: {value}")
            else:
                console.print(f"[bold green]✓ Set {section}.{normalized_key} = {value}[/bold green]")

            console.print(f"\n[dim]Config saved to {config_path}[/dim]")
        else:
            console.print(f"[bold red]✗ Failed to save configuration[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
