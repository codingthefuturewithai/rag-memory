"""Log viewing commands."""

import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

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


def get_rag_version() -> str:
    """Get RAG Memory version."""
    try:
        from importlib.metadata import version
        return version("rag-memory")
    except Exception:
        return "unknown"


def export_logs_to_file(containers, tail, export_path):
    """Export logs from specified containers to a single file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version = get_rag_version()

    with open(export_path, 'w') as f:
        f.write(f"RAG Memory Log Export\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"Version: {version}\n")
        f.write(f"{'='*80}\n\n")

        for service_name, container_name in containers:
            # Get logs for this container
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_name],
                capture_output=True,
                text=True,
                check=False
            )

            f.write(f"\n{'='*80}\n")
            f.write(f"{service_name.upper()} ({container_name})\n")
            f.write(f"{'='*80}\n\n")

            if result.returncode == 0:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(result.stderr)
            else:
                f.write(f"Error: Failed to get logs (exit code {result.returncode})\n")
                f.write(result.stderr)

            f.write("\n")


def export_all_to_archive(containers, tail, archive_path):
    """Export all logs + system info to tar.gz archive."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    version = get_rag_version()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create system info file
        with open(tmppath / "system_info.txt", 'w') as f:
            f.write(f"RAG Memory System Report\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Version: {version}\n")
            f.write(f"{'='*80}\n\n")

            # Docker version
            result = subprocess.run(["docker", "version"], capture_output=True, text=True, check=False)
            f.write("DOCKER VERSION\n")
            f.write("-"*80 + "\n")
            f.write(result.stdout)
            f.write("\n\n")

            # Docker ps
            result = subprocess.run(["docker", "ps", "-a"], capture_output=True, text=True, check=False)
            f.write("DOCKER CONTAINERS\n")
            f.write("-"*80 + "\n")
            f.write(result.stdout)
            f.write("\n\n")

        # Export logs for each container
        for service_name, container_name in containers:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail), container_name],
                capture_output=True,
                text=True,
                check=False
            )

            log_file = tmppath / f"{service_name}_logs.txt"
            with open(log_file, 'w') as f:
                f.write(f"{service_name.upper()} Logs\n")
                f.write(f"Container: {container_name}\n")
                f.write(f"{'='*80}\n\n")

                if result.returncode == 0:
                    f.write(result.stdout)
                    if result.stderr:
                        f.write("\n--- STDERR ---\n")
                        f.write(result.stderr)
                else:
                    f.write(f"Error: Failed to get logs (exit code {result.returncode})\n")
                    f.write(result.stderr)

        # Create tar.gz archive
        with tarfile.open(archive_path, "w:gz") as tar:
            for file in tmppath.glob("*"):
                tar.add(file, arcname=file.name)


@click.command(name='logs')
@click.option('--service', help='Specific service (mcp, postgres, neo4j, backup)')
@click.option('--tail', type=int, default=50, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--export', type=click.Path(), help='Export logs to file')
@click.option('--export-all', type=click.Path(), help='Export all logs + system info to archive')
def logs(service, tail, follow, export, export_all):
    """View Docker container logs.

    Shows logs from RAG Memory Docker containers. By default, shows logs
    from all containers. Use --service to filter by specific container.
    Use --follow to stream logs in real-time (requires --service).

    Examples:
        rag logs                              # Show all logs (last 50 lines each)
        rag logs --service mcp                # Show MCP server logs
        rag logs --service postgres           # Show PostgreSQL logs
        rag logs --tail 100                   # Show last 100 lines
        rag logs --service mcp -f             # Follow MCP logs only
        rag logs --export bug-report.txt      # Export all logs to file
        rag logs --service mcp --export mcp.txt  # Export MCP logs only
        rag logs --export-all report.tar.gz   # Export logs + system info
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

        # Handle export options
        if export_all:
            console.print(f"[cyan]Exporting all logs + system info to {export_all}...[/cyan]")
            export_all_to_archive(containers, tail, export_all)
            console.print(f"[green]✓ Export complete: {export_all}[/green]")
            return

        if export:
            console.print(f"[cyan]Exporting logs to {export}...[/cyan]")
            export_logs_to_file(containers, tail, export)
            console.print(f"[green]✓ Export complete: {export}[/green]")
            return

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
