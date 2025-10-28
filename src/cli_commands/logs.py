"""Log viewing commands."""

import subprocess
import sys

import click
from rich.console import Console

console = Console()

# Map of service short names to container names
SERVICE_CONTAINERS = {
    'postgres': 'rag-memory-postgres-local',
    'neo4j': 'rag-memory-neo4j-local',
    'mcp': 'rag-memory-mcp-local',
    'backup': 'rag-memory-backup-local',
}


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def check_container_exists(container_name: str) -> bool:
    """Check if a container exists (running or stopped)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0 and container_name in result.stdout
    except Exception:
        return False


@click.command(name='logs')
@click.option('--service', help='Specific service (mcp, postgres, neo4j, backup)')
@click.option('--tail', type=int, default=50, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(service, tail, follow):
    """View Docker container logs.

    Shows logs from RAG Memory Docker containers. By default, shows logs
    from all containers. Use --service to filter by specific container.
    Use --follow to stream logs in real-time.

    Examples:
        rag logs                      # Show all logs (last 50 lines each)
        rag logs --service mcp        # Show MCP server logs
        rag logs --service postgres   # Show PostgreSQL logs
        rag logs --tail 100           # Show last 100 lines
        rag logs --follow             # Follow all logs
        rag logs --service mcp -f     # Follow MCP logs only
    """
    try:
        # Check Docker is running
        if not check_docker_running():
            console.print("[bold red]✗ Docker daemon is not running[/bold red]")
            console.print("[yellow]Start Docker Desktop and try again[/yellow]")
            sys.exit(1)

        # Determine which containers to show logs for
        if service:
            # Specific service requested
            if service not in SERVICE_CONTAINERS:
                console.print(f"[bold red]✗ Unknown service: {service}[/bold red]")
                console.print(f"[yellow]Valid services: {', '.join(SERVICE_CONTAINERS.keys())}[/yellow]")
                sys.exit(1)

            containers = [(service, SERVICE_CONTAINERS[service])]
        else:
            # Show all containers
            containers = list(SERVICE_CONTAINERS.items())

        # If following logs, only one container is allowed for clean output
        if follow and len(containers) > 1:
            console.print("[bold red]✗ Cannot follow logs from multiple containers[/bold red]")
            console.print("[yellow]Use --service to specify which container to follow[/yellow]")
            console.print(f"[yellow]Valid services: {', '.join(SERVICE_CONTAINERS.keys())}[/yellow]")
            sys.exit(1)

        # Show logs for each container
        for service_name, container_name in containers:
            # Check if container exists
            if not check_container_exists(container_name):
                if len(containers) == 1:
                    console.print(f"[bold red]✗ Container '{container_name}' not found[/bold red]")
                    console.print("[yellow]Run 'rag start' to start services[/yellow]")
                    sys.exit(1)
                else:
                    # Skip missing containers when showing all logs
                    console.print(f"[dim]Skipping {service_name} (container not found)[/dim]")
                    continue

            # Build docker logs command
            cmd = ["docker", "logs"]

            if follow:
                cmd.append("--follow")

            cmd.extend(["--tail", str(tail)])
            cmd.append(container_name)

            # Print header for this container (unless following)
            if not follow and len(containers) > 1:
                console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
                console.print(f"[bold cyan]{service_name.upper()} ({container_name})[/bold cyan]")
                console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")

            # Execute docker logs command
            # For follow mode, pass through to terminal (don't capture output)
            # For normal mode, capture and print through Rich for formatting
            try:
                if follow:
                    # Follow mode - stream directly to terminal
                    console.print(f"[dim]Following logs for {service_name} (Ctrl+C to stop)...[/dim]\n")
                    subprocess.run(cmd, check=True)
                else:
                    # Normal mode - capture and display
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )

                    if result.returncode != 0:
                        console.print(f"[bold red]✗ Failed to get logs for {service_name}[/bold red]")
                        console.print(f"[red]{result.stderr}[/red]")
                        if len(containers) == 1:
                            sys.exit(1)
                        continue

                    # Print logs
                    if result.stdout:
                        console.print(result.stdout, end='')
                    else:
                        console.print(f"[dim]No logs available for {service_name}[/dim]")

            except subprocess.CalledProcessError as e:
                console.print(f"[bold red]✗ Error getting logs for {service_name}[/bold red]")
                console.print(f"[red]{e}[/red]")
                if len(containers) == 1:
                    sys.exit(1)
            except KeyboardInterrupt:
                # User pressed Ctrl+C while following
                console.print("\n[dim]Stopped following logs[/dim]")
                break

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
