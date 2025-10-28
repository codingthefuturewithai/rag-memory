"""Service management commands for RAG Memory."""

import click
from rich.table import Table
from ..core.docker import DockerManager
from ..utils.console import console, print_success, print_error, print_info


@click.group(name='service')
def service_group():
    """Manage RAG Memory services."""
    pass


@service_group.command(name='start')
def start_services():
    """Start all RAG Memory services."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    DockerManager.start()


@service_group.command(name='stop')
def stop_services():
    """Stop all RAG Memory services."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    DockerManager.stop()


@service_group.command(name='restart')
def restart_services():
    """Restart all RAG Memory services."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    DockerManager.restart()


@service_group.command(name='status')
def service_status():
    """Check status of RAG Memory services."""
    if not DockerManager.is_initialized():
        print_error("RAG Memory not initialized. Please run 'rag init' first.")
        return

    print_info("Checking RAG Memory service status...")
    status = DockerManager.status()

    if status:
        console.print("\n" + status)

        # Parse the status output to show a nicer table
        lines = status.strip().split('\n')
        if len(lines) > 1:
            # Skip header and create table
            table = Table(title="RAG Memory Services", show_header=True, header_style="bold cyan")

            # Parse header to get column names
            headers = lines[0].split()
            for header in headers:
                table.add_column(header)

            # Add service rows
            for line in lines[1:]:
                if line.strip():
                    # Split by multiple spaces to handle column alignment
                    parts = line.split()
                    if len(parts) >= len(headers):
                        table.add_row(*parts[:len(headers)])

            console.print(table)
    else:
        print_error("Could not get service status.")


# Register shortcuts at module level for backward compatibility
start = start_services
stop = stop_services
restart = restart_services
status = service_status