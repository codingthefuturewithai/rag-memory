"""Main entry point for RAG Memory CLI."""

import logging
import os
import sys
from pathlib import Path

import click

# Import command groups
from .commands.service import service_group, start_services, stop_services, restart_services, service_status
from .commands.config import config_group
from .commands.logs import logs_group, logs_command
from .commands.admin import admin_group
from .commands.collection import collection_group
from .commands.ingest import ingest_group
from .commands.search import search_command
from .commands.document import document_group
from .commands.graph import graph_group

# Import utilities
from .utils.console import console, print_error
from .core.paths import Paths

# Configure logging
log_dir = Paths.log_dir()
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "cli.log"),
        logging.StreamHandler()  # Also log to stderr
    ]
)

# Suppress dotenv parsing warnings
logging.getLogger("dotenv.main").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


def get_version():
    """Get package version from installed metadata."""
    try:
        from importlib.metadata import version
        return version("rag-memory")
    except Exception:
        return "unknown"


def ensure_config_or_exit():
    """Check that configuration exists or exit gracefully."""
    from src.core.config_loader import load_config

    try:
        config = load_config()

        # Set environment variables for components that read them directly
        # This ensures consistency between CLI and containerized services
        if 'server' in config:
            server_config = config['server']

            # Set OpenAI API key
            if 'openai_api_key' in server_config:
                os.environ['OPENAI_API_KEY'] = server_config['openai_api_key']

            # Set database URLs
            if 'database_url' in server_config:
                os.environ['DATABASE_URL'] = server_config['database_url']

            # Set Neo4j connection details
            if 'neo4j_uri' in server_config:
                os.environ['NEO4J_URI'] = server_config['neo4j_uri']
            if 'neo4j_user' in server_config:
                os.environ['NEO4J_USER'] = server_config['neo4j_user']
            if 'neo4j_password' in server_config:
                os.environ['NEO4J_PASSWORD'] = server_config['neo4j_password']

        return config

    except FileNotFoundError:
        print_error("Configuration file not found. Please run setup first.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)


@click.group()
@click.version_option(version=get_version(), prog_name="rag")
@click.pass_context
def cli(ctx):
    """RAG Memory - AI knowledge base management system.

    \b
    Quick Start:
      rag init              # Initialize database
      rag start             # Start services
      rag status            # Check system status
      rag collection create my-docs "My documentation"  # Create collection

    \b
    Service Management:
      rag start/stop/restart  # Manage services
      rag logs                # View service logs
      rag config show         # View configuration

    Use 'rag COMMAND --help' for more information on a specific command.
    """
    # Ensure configuration exists for all commands except setup
    if ctx.invoked_subcommand not in ['setup', 'version']:
        config = ensure_config_or_exit()
        ctx.obj = config


# Register command groups
cli.add_command(service_group)
cli.add_command(config_group)
cli.add_command(logs_group)
cli.add_command(admin_group)
cli.add_command(collection_group)
cli.add_command(ingest_group)
cli.add_command(document_group)
cli.add_command(graph_group)

# Register standalone commands
cli.add_command(search_command)
cli.add_command(logs_command)

# Register service shortcuts as top-level commands
cli.add_command(start_services, name='start')
cli.add_command(stop_services, name='stop')
cli.add_command(restart_services, name='restart')
cli.add_command(service_status, name='status')

# Register admin shortcuts
from .commands.admin import init_database, check_status, migrate_database
cli.add_command(init_database, name='init')
cli.add_command(migrate_database, name='migrate')


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.exception("Unexpected error in CLI")
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()