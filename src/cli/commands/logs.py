"""Log viewing commands for RAG Memory."""

import click
from ..core.docker import DockerManager
from ..utils.console import print_error, print_info


@click.group(name='logs')
def logs_group():
    """View RAG Memory service logs."""
    pass


@logs_group.command(name='all')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def show_all_logs(tail: int, follow: bool):
    """View logs from all services."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    print_info(f"Showing last {tail} lines from all services...")
    DockerManager.logs(service=None, tail=tail, follow=follow)


@logs_group.command(name='mcp')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def show_mcp_logs(tail: int, follow: bool):
    """View MCP server logs."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    print_info(f"Showing last {tail} lines from MCP server...")
    DockerManager.logs(service='mcp-server', tail=tail, follow=follow)


@logs_group.command(name='postgres')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def show_postgres_logs(tail: int, follow: bool):
    """View PostgreSQL logs."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    print_info(f"Showing last {tail} lines from PostgreSQL...")
    DockerManager.logs(service='postgres-local', tail=tail, follow=follow)


@logs_group.command(name='neo4j')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def show_neo4j_logs(tail: int, follow: bool):
    """View Neo4j logs."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    print_info(f"Showing last {tail} lines from Neo4j...")
    DockerManager.logs(service='neo4j-local', tail=tail, follow=follow)


# Direct command for backward compatibility
@click.command(name='logs')
@click.option('--service', default=None, help='Specific service to show logs for')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs_command(service: str, tail: int, follow: bool):
    """View Docker container logs.

    \b
    Examples:
      rag logs                  # Show all logs
      rag logs --service mcp    # Show MCP server logs
      rag logs --follow         # Follow all logs
      rag logs --tail 100       # Show last 100 lines
    """
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    if service:
        # Map friendly names to actual service names
        service_map = {
            'mcp': 'mcp-server',
            'postgres': 'postgres-local',
            'postgresql': 'postgres-local',
            'neo4j': 'neo4j-local'
        }
        service = service_map.get(service, service)
        print_info(f"Showing last {tail} lines from {service}...")
    else:
        print_info(f"Showing last {tail} lines from all services...")

    DockerManager.logs(service=service, tail=tail, follow=follow)