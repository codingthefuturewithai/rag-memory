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
    get_missing_variables,
    REQUIRED_VARIABLES,
)

console = Console()


def prompt_for_missing_variables() -> bool:
    """
    Detect and prompt for any missing required environment variables.

    This is called on every startup to handle:
    - Fresh installations (all variables missing)
    - Upgrades (new variables added but not in config)
    - User edits (if user deletes a variable)

    Returns:
        True if all variables are now configured, False if user declined
    """
    missing = get_missing_variables()

    if not missing:
        return True  # All variables present, nothing to do

    # User is missing some variables - need to prompt
    config_path = get_global_config_path()

    console.print("\n[bold yellow]⚠️  Missing Configuration[/bold yellow]\n")

    if config_path.exists():
        # This is an upgrade or partial config
        console.print(
            f"[yellow]Your configuration file is missing {len(missing)} required variables.[/yellow]\n"
        )
        console.print("[dim]This typically happens when RAG Memory is upgraded with new features.[/dim]\n")
    else:
        # First-time setup
        console.print(f"[yellow]Configuration file not found at {config_path}[/yellow]\n")
        console.print("[dim]RAG Memory needs the following information:[/dim]\n")

    console.print(f"[dim]Missing variables: {', '.join(missing)}[/dim]\n")

    # Ask if they want to provide them
    proceed = Confirm.ask("Would you like to configure these now?", default=True)

    if not proceed:
        console.print("\n[yellow]Configuration incomplete. You can configure manually by editing:[/yellow]")
        console.print(f"[cyan]{config_path}[/cyan]\n")
        return False

    console.print()

    # Prompt for each missing variable
    for var_name in missing:
        prompt_text = _get_prompt_text(var_name)
        default_value = _get_default_value(var_name)

        if var_name in ['OPENAI_API_KEY', 'NEO4J_PASSWORD']:
            # Password fields - hide input
            value = Prompt.ask(prompt_text, password=True)
        else:
            # Regular input, possibly with default
            if default_value:
                value = Prompt.ask(prompt_text, default=default_value)
            else:
                value = Prompt.ask(prompt_text)

        # Validate that value is not empty
        if not value or value.strip() == "":
            console.print(f"[red]✗ {var_name} cannot be empty[/red]")
            return False

        save_env_var(var_name, value.strip())

    console.print(f"\n[bold green]✓ Configuration saved to {config_path}[/bold green]\n")

    # Reload environment variables
    from .config_loader import load_environment_variables
    load_environment_variables()

    return True


def _get_prompt_text(var_name: str) -> str:
    """Get user-friendly prompt text for a variable."""
    prompts = {
        'DATABASE_URL': 'PostgreSQL/Supabase Database URL',
        'OPENAI_API_KEY': 'OpenAI API Key',
        'NEO4J_URI': 'Neo4j Aura Connection URI',
        'NEO4J_USER': 'Neo4j Username',
        'NEO4J_PASSWORD': 'Neo4j Password',
    }
    return prompts.get(var_name, var_name)


def _get_default_value(var_name: str) -> str:
    """Get default value suggestion for a variable."""
    defaults = {
        'DATABASE_URL': 'postgresql://raguser:ragpassword@localhost:54320/rag_memory',
        'NEO4J_USER': 'neo4j',
    }
    return defaults.get(var_name, '')


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
    Ensure all required configuration exists, or prompt user to provide it.
    Exits the program if setup fails or user declines.

    Also loads environment variables using the priority system.

    This function handles:
    - Fresh installations (no config file)
    - Upgrades (new variables added)
    - Partial configurations (user deleted variables)
    """
    # First, load environment variables (priority: shell env vars → ~/.rag-memory-env)
    from .config_loader import load_environment_variables
    load_environment_variables()

    # Check for missing variables and prompt if needed
    if not prompt_for_missing_variables():
        console.print("[yellow]⚠ Configuration is required to use RAG Memory[/yellow]")
        console.print("[dim]Run any command again to restart the configuration wizard.[/dim]\n")
        sys.exit(1)
