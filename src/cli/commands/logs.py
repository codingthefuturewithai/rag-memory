"""Log viewing commands for RAG Memory."""

import click
from ..core.docker import DockerManager
from ..utils.console import print_error, print_info


@click.command(name='logs')
@click.option('--service', default=None, help='Specific service to show logs for (mcp, postgres, neo4j, backup)')
@click.option('--tail', default=50, help='Number of lines to show (default: 50)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs_command(service: str, tail: int, follow: bool):
    """View Docker container logs.

    \b
    Examples:
      rag logs                      # Show all logs
      rag logs --service mcp        # Show MCP server logs
      rag logs --service postgres   # Show PostgreSQL logs
      rag logs --service neo4j      # Show Neo4j logs
      rag logs --service backup     # Show backup logs
      rag logs --follow             # Follow all logs
      rag logs --tail 100           # Show last 100 lines
      rag logs --service mcp -f     # Follow MCP logs
    """
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run setup first.")
        return

    if service:
        # Map friendly names to actual service names
        service_map = {
            'mcp': 'mcp-server',
            'postgres': 'postgres-local',
            'postgresql': 'postgres-local',
            'neo4j': 'neo4j-local',
            'backup': 'backup-local'
        }
        service = service_map.get(service, service)
        print_info(f"Showing last {tail} lines from {service}...")
    else:
        print_info(f"Showing last {tail} lines from all services...")

    DockerManager.logs(service=service, tail=tail, follow=follow)
