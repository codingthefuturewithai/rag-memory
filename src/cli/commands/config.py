"""Configuration management commands for RAG Memory."""

import click
from ..utils.config_manager import ConfigManager
from ..utils.console import print_error


@click.group(name='config')
def config_group():
    """Manage RAG Memory configuration."""
    pass


@config_group.command(name='show')
def show_config():
    """Display current configuration."""
    ConfigManager.show_config()


@config_group.command(name='edit')
def edit_config():
    """Interactive configuration editor."""
    ConfigManager.interactive_edit()


@config_group.command(name='set')
@click.argument('key')
@click.argument('value')
def set_config_value(key: str, value: str):
    """Set a specific configuration value.

    \b
    Examples:
      rag config set api_key sk-1234...
      rag config set backup_schedule "0 3 * * *"
      rag config set postgres_port 54320
    """
    ConfigManager.set_value(key, value)


# Register shortcuts at module level for backward compatibility
show = show_config
edit = edit_config
set_value = set_config_value