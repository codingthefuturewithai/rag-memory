"""Configuration management utilities."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from rich.table import Table
from rich.prompt import Prompt
from dotenv import dotenv_values, set_key

from ..core.paths import Paths
from .console import console, create_table, print_success, print_error, print_warning


class ConfigManager:
    """Manage configuration files for RAG Memory."""

    @staticmethod
    def load_config() -> Dict[str, Any]:
        """Load configuration from config.yaml.

        Returns:
            Dictionary containing configuration
        """
        config_file = Paths.config_yaml()
        if not config_file.exists():
            return {}

        with open(config_file, 'r') as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def save_config(config: Dict[str, Any]):
        """Save configuration to config.yaml.

        Args:
            config: Configuration dictionary to save
        """
        config_file = Paths.config_yaml()
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    @staticmethod
    def load_env() -> Dict[str, str]:
        """Load environment variables from .env file.

        Returns:
            Dictionary of environment variables
        """
        env_file = Paths.env_file()
        if not env_file.exists():
            return {}
        return dotenv_values(env_file)

    @staticmethod
    def update_env(key: str, value: str):
        """Update a value in the .env file.

        Args:
            key: Environment variable name
            value: New value
        """
        env_file = Paths.env_file()
        set_key(str(env_file), key, value)

    @staticmethod
    def show_config():
        """Display current configuration in a formatted table."""
        config_file = Paths.config_yaml()
        env_file = Paths.env_file()

        if not config_file.exists():
            print_error("Configuration not found. Please run setup first.")
            return

        console.print(f"\n[bold]Configuration Location:[/bold] {Paths.config_dir()}")

        # Load configs
        config = ConfigManager.load_config()
        env_vars = ConfigManager.load_env()

        # Create table
        table = create_table("Current Configuration")
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")

        # Server configuration
        server_config = config.get('server', {})

        # API Key (masked)
        api_key = server_config.get('openai_api_key', '')
        if api_key:
            masked = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 20 else api_key
            table.add_row("OpenAI API Key", masked, "config.yaml")

        # Database settings
        table.add_row("Database URL", server_config.get('database_url', ''), "config.yaml")
        table.add_row("Neo4j URI", server_config.get('neo4j_uri', ''), "config.yaml")
        table.add_row("Neo4j User", server_config.get('neo4j_user', ''), "config.yaml")

        # Port settings from .env
        table.add_row("PostgreSQL Port", env_vars.get('PROD_POSTGRES_PORT', '54320'), ".env")
        table.add_row("Neo4j HTTP Port", env_vars.get('PROD_NEO4J_HTTP_PORT', '7475'), ".env")
        table.add_row("Neo4j Bolt Port", env_vars.get('PROD_NEO4J_BOLT_PORT', '7688'), ".env")
        table.add_row("MCP Server Port", env_vars.get('MCP_SSE_PORT', '8001'), ".env")

        # Backup settings
        table.add_row("Backup Schedule", env_vars.get('BACKUP_CRON_SCHEDULE', ''), ".env")
        table.add_row("Backup Directory", env_vars.get('BACKUP_DIR', ''), ".env")

        # Credentials
        table.add_row("PostgreSQL User", env_vars.get('POSTGRES_USER', 'raguser'), ".env")
        table.add_row("Neo4j Password", "********" if env_vars.get('NEO4J_PASSWORD') else "not set", ".env")

        console.print(table)

    @staticmethod
    def interactive_edit():
        """Interactive configuration editor."""
        console.print("\n[bold]RAG Memory Configuration Editor[/bold]")
        console.print("Press Enter to keep current value, or type new value.\n")

        # Load current config
        config = ConfigManager.load_config()
        env_vars = ConfigManager.load_env()
        server_config = config.get('server', {})

        updates_config = {}
        updates_env = {}

        # OpenAI API Key
        current_key = server_config.get('openai_api_key', '')
        if current_key:
            masked = current_key[:10] + '...' + current_key[-4:]
            new_key = Prompt.ask(f"OpenAI API Key [{masked}]", password=True, default="")
        else:
            new_key = Prompt.ask("OpenAI API Key", password=True)

        if new_key:
            updates_config['openai_api_key'] = new_key

        # Neo4j Password
        current_neo4j_pass = server_config.get('neo4j_password', '')
        if current_neo4j_pass:
            new_pass = Prompt.ask("Neo4j Password [********]", password=True, default="")
        else:
            new_pass = Prompt.ask("Neo4j Password", password=True, default="graphiti-password")

        if new_pass:
            updates_config['neo4j_password'] = new_pass
            updates_env['NEO4J_PASSWORD'] = new_pass

        # PostgreSQL Password
        current_pg_pass = env_vars.get('POSTGRES_PASSWORD', 'ragpassword')
        new_pg_pass = Prompt.ask(f"PostgreSQL Password [{'*' * 8}]", password=True, default="")
        if new_pg_pass:
            updates_env['POSTGRES_PASSWORD'] = new_pg_pass

        # Backup Schedule
        current_cron = env_vars.get('BACKUP_CRON_SCHEDULE', '5 2 * * *')
        console.print(f"\nCurrent backup schedule: [cyan]{current_cron}[/cyan]")
        console.print("Format: MIN HOUR * * * (e.g., '0 3 * * *' for 3:00 AM)")
        new_cron = Prompt.ask("Backup Schedule", default=current_cron)
        if new_cron != current_cron:
            updates_env['BACKUP_CRON_SCHEDULE'] = new_cron

        # Backup Directory
        current_backup = env_vars.get('BACKUP_DIR', str(Paths.backup_dir()))
        new_backup = Prompt.ask("Backup Directory", default=current_backup)
        if new_backup != current_backup:
            updates_env['BACKUP_DIR'] = new_backup

        # Apply updates
        if updates_config:
            for key, value in updates_config.items():
                server_config[key] = value
            config['server'] = server_config
            ConfigManager.save_config(config)
            print_success("Configuration updated")

        if updates_env:
            for key, value in updates_env.items():
                ConfigManager.update_env(key, value)
            print_success("Environment settings updated")

        if updates_config or updates_env:
            print_warning("Restart services for changes to take effect: rag restart")

    @staticmethod
    def set_value(key: str, value: str):
        """Set a specific configuration value.

        Args:
            key: Configuration key
            value: New value
        """
        # Map friendly names to actual keys
        config_keys = {
            'openai_api_key': ('config', 'openai_api_key'),
            'api_key': ('config', 'openai_api_key'),
            'neo4j_password': ('config', 'neo4j_password'),
            'neo4j_user': ('config', 'neo4j_user'),
        }

        env_keys = {
            'backup_schedule': 'BACKUP_CRON_SCHEDULE',
            'backup_dir': 'BACKUP_DIR',
            'postgres_port': 'PROD_POSTGRES_PORT',
            'neo4j_http_port': 'PROD_NEO4J_HTTP_PORT',
            'neo4j_bolt_port': 'PROD_NEO4J_BOLT_PORT',
            'mcp_port': 'MCP_SSE_PORT',
            'postgres_user': 'POSTGRES_USER',
            'postgres_password': 'POSTGRES_PASSWORD',
        }

        if key in config_keys:
            # Update config.yaml
            config = ConfigManager.load_config()
            _, config_key = config_keys[key]
            if 'server' not in config:
                config['server'] = {}
            config['server'][config_key] = value
            ConfigManager.save_config(config)
            print_success(f"Updated {key} in configuration")

        elif key in env_keys:
            # Update .env
            env_key = env_keys[key]
            ConfigManager.update_env(env_key, value)
            print_success(f"Updated {key} in environment")

        else:
            print_error(f"Unknown configuration key: {key}")
            console.print("\nValid configuration keys:")
            console.print("  Config file: openai_api_key, neo4j_password, neo4j_user")
            console.print("  Environment: backup_schedule, backup_dir, postgres_port, neo4j_http_port")
            return

        print_warning("Restart services for changes to take effect: rag restart")