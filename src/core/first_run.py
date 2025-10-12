"""First-run configuration wizard for RAG Memory."""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt, Confirm

from .config_loader import (
    get_global_config_path,
    ensure_config_exists,
    save_env_var,
    create_default_config,
)

console = Console()


def check_and_setup_config() -> bool:
    """
    Check if configuration exists, and if not, guide user through setup.

    Returns:
        True if config is ready to use (exists or was created), False if user declined setup.
    """
    # Check if config already exists with required variables
    if ensure_config_exists():
        return True  # Config is good, proceed

    config_path = get_global_config_path()

    # First-run setup needed
    console.print("\n[bold yellow]🔧 First-Time Setup Required[/bold yellow]\n")
    console.print(
        f"RAG Memory needs to create a configuration file: [cyan]{config_path}[/cyan]\n"
    )
    console.print("[dim]This will store your database connection and API key settings.[/dim]")
    console.print("[dim]The file will be created with user-only permissions (chmod 0o600).[/dim]\n")

    # Ask if they want to proceed
    proceed = Confirm.ask("Would you like to set this up now?", default=True)

    if not proceed:
        console.print("\n[yellow]Setup cancelled. You can configure manually by creating:[/yellow]")
        console.print(f"[cyan]{config_path}[/cyan]\n")
        console.print("[dim]With the following content:[/dim]")
        console.print("[dim]DATABASE_URL=postgresql://raguser:ragpassword@localhost:54320/rag_memory[/dim]")
        console.print("[dim]OPENAI_API_KEY=your-api-key-here[/dim]\n")
        return False

    console.print()

    # Get DATABASE_URL
    console.print("[bold cyan]1. Database Configuration[/bold cyan]")
    console.print(
        "[dim]If you're using the default Docker setup, press Enter to accept the default.[/dim]"
    )

    default_db_url = "postgresql://raguser:ragpassword@localhost:54320/rag_memory"
    database_url = Prompt.ask(
        "Database URL",
        default=default_db_url,
    )

    # Get OPENAI_API_KEY
    console.print("\n[bold cyan]2. OpenAI API Key[/bold cyan]")
    console.print(
        "[dim]Your API key will be stored securely with user-only file permissions.[/dim]"
    )
    console.print(
        "[dim]Get your key from: https://platform.openai.com/api-keys[/dim]"
    )

    api_key = Prompt.ask(
        "OpenAI API Key",
        password=True,  # Hide input
    )

    if not api_key or api_key.strip() == "":
        console.print("[bold red]✗ API key cannot be empty[/bold red]")
        return False

    # Save configuration
    console.print("\n[bold blue]Saving configuration...[/bold blue]")

    success = True
    success = success and save_env_var("DATABASE_URL", database_url)
    success = success and save_env_var("OPENAI_API_KEY", api_key.strip())

    if success:
        console.print(f"[bold green]✓ Configuration saved to {config_path}[/bold green]\n")
        console.print("[dim]You can edit this file anytime to update your settings.[/dim]\n")

        # Reload environment variables
        from .config_loader import load_environment_variables
        load_environment_variables()

        return True
    else:
        console.print(f"[bold red]✗ Failed to save configuration to {config_path}[/bold red]")
        console.print("[yellow]Make sure the directory is writable[/yellow]\n")
        return False


def ensure_config_or_exit():
    """
    Ensure configuration exists, or run first-time setup.
    Exits the program if setup fails or user declines.

    Also loads environment variables using the three-tier system.
    """
    # First, load environment variables (three-tier: env vars → .env → ~/.rag-memory-env)
    from .config_loader import load_environment_variables
    load_environment_variables()

    # Then check if config exists (or run setup wizard)
    if not check_and_setup_config():
        console.print("[yellow]⚠ Configuration is required to use RAG Memory[/yellow]")
        console.print("[dim]Run any command again to restart the setup wizard.[/dim]\n")
        sys.exit(1)
