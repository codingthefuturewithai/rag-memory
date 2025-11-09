"""Command-line interface for RAG Memory - Thin Orchestrator."""

import logging
import click

# Suppress harmless Neo4j server notifications (they query properties before they exist)
# These are cosmetic warnings, not errors. Real Neo4j errors will still be shown.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

# Suppress verbose httpx HTTP request logs (OpenAI API calls)
# These clutter console output during graph queries. Errors still visible.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Suppress python-dotenv parsing warnings from third-party libraries
# Libraries like crawl4ai and graphiti-core auto-load .env files during import.
# These warnings are cosmetic - the variables still load correctly.
logging.getLogger("dotenv.main").setLevel(logging.ERROR)

# Import all command groups and commands
from src.cli_commands.service import service_group, start, stop, restart, status
from src.cli_commands.collection import collection
from src.cli_commands.ingest import ingest
from src.cli_commands.search import search
from src.cli_commands.document import document
from src.cli_commands.graph import graph
from src.cli_commands.analyze import analyze
from src.cli_commands.config import config
from src.cli_commands.logs import logs


def get_version():
    """Get package version from installed metadata."""
    try:
        from importlib.metadata import version
        return version("rag-memory")
    except Exception:
        return "unknown"


@click.group()
@click.version_option(version=get_version(), prog_name="rag")
def main():
    """RAG Memory - AI knowledge base management system.

    Service Management:
      rag start/stop/restart  # Manage services
      rag status              # Check system status
      rag logs                # View service logs
      rag config show         # View configuration

    Document Management:
      rag collection create/list/info/delete
      rag ingest text/file/directory/url
      rag search "query"
      rag document list/view/update/delete

    Knowledge Graph:
      rag graph query-relationships
      rag graph query-temporal

    Analysis:
      rag analyze website <url>

    Use 'rag COMMAND --help' for more information on a specific command.
    """
    # Load and validate configuration before any commands execute
    # This respects RAG_CONFIG_PATH/RAG_CONFIG_FILE for dev/test scenarios
    # and falls back to system-level config for production CLI usage
    from src.core.first_run import ensure_config_or_exit
    ensure_config_or_exit()


# Register command groups
main.add_command(service_group)  # rag service start/stop/restart/status
main.add_command(collection)     # rag collection create/list/info/delete
main.add_command(ingest)         # rag ingest text/file/directory/url
main.add_command(document)       # rag document list/view/update/delete
main.add_command(graph)          # rag graph query-relationships/query-temporal
main.add_command(analyze)        # rag analyze website
main.add_command(config)         # rag config show/edit/set

# Register standalone commands
main.add_command(search)         # rag search
main.add_command(logs)           # rag logs

# Register service shortcuts as top-level commands
main.add_command(start, name='start')      # rag start
main.add_command(stop, name='stop')        # rag stop
main.add_command(restart, name='restart')  # rag restart
main.add_command(status, name='status')    # rag status


if __name__ == "__main__":
    main()
