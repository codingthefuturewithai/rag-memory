"""Service management commands for RAG Memory."""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


def get_compose_file() -> Path:
    """
    Get the path to docker-compose.yml file.

    Tries two locations:
    1. System config directory (created by setup.py) - for global CLI usage
    2. Repository location - for development

    Returns:
        Path to docker-compose.yml

    Raises:
        FileNotFoundError if docker-compose.yml not found in either location
    """
    import platformdirs

    # Try system config directory first (for users who ran setup.py)
    config_dir = Path(platformdirs.user_config_dir('rag-memory', appauthor=False))
    system_compose = config_dir / 'docker-compose.yml'

    if system_compose.exists():
        return system_compose

    # Fall back to repository location (for development)
    # Assume we're running from installed package, find the repo
    repo_compose = Path(__file__).parent.parent.parent / 'deploy' / 'docker' / 'compose' / 'docker-compose.yml'

    if repo_compose.exists():
        return repo_compose

    raise FileNotFoundError(
        "docker-compose.yml not found. Please run setup.py first.\n"
        f"  Expected locations:\n"
        f"    System: {system_compose}\n"
        f"    Repo: {repo_compose}"
    )


def run_docker_command(args: list, check: bool = True) -> tuple:
    """
    Run a docker or docker-compose command.

    Args:
        args: Command arguments (e.g., ["docker", "ps"])
        check: Whether to raise on non-zero exit

    Returns:
        tuple: (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def check_docker_installed() -> bool:
    """Check if Docker is installed"""
    code, _, _ = run_docker_command(["docker", "--version"])
    return code == 0


def check_docker_running() -> bool:
    """Check if Docker daemon is running"""
    code, _, _ = run_docker_command(["docker", "ps"])
    return code == 0


@click.group(name='service')
def service_group():
    """Manage RAG Memory services."""
    pass


@service_group.command(name='start')
def start_command():
    """Start all RAG Memory services (PostgreSQL, Neo4j, MCP server, backup)."""
    try:
        # Check Docker
        if not check_docker_installed():
            console.print("[bold red]✗ Docker is not installed[/bold red]")
            console.print("[yellow]Install Docker Desktop from: https://www.docker.com/products/docker-desktop[/yellow]")
            sys.exit(1)

        if not check_docker_running():
            console.print("[bold red]✗ Docker daemon is not running[/bold red]")
            console.print("[yellow]Start Docker Desktop and try again[/yellow]")
            sys.exit(1)

        # Get compose file
        try:
            compose_file = get_compose_file()
        except FileNotFoundError as e:
            console.print(f"[bold red]✗ {e}[/bold red]")
            sys.exit(1)

        console.print("[bold blue]Starting RAG Memory services...[/bold blue]\n")

        # Start containers
        code, stdout, stderr = run_docker_command([
            "docker-compose", "-f", str(compose_file), "up", "-d"
        ])

        if code != 0:
            console.print(f"[bold red]✗ Failed to start services[/bold red]")
            console.print(f"[red]{stderr}[/red]")
            sys.exit(1)

        console.print("[bold green]✓ Services started successfully[/bold green]")
        console.print("\n[dim]Containers are starting in the background...[/dim]")
        console.print("[dim]Run 'rag status' to check when services are ready[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@service_group.command(name='stop')
def stop_command():
    """Stop all RAG Memory services."""
    try:
        # Get compose file
        try:
            compose_file = get_compose_file()
        except FileNotFoundError as e:
            console.print(f"[bold red]✗ {e}[/bold red]")
            sys.exit(1)

        console.print("[bold blue]Stopping RAG Memory services...[/bold blue]\n")

        # Stop containers
        code, stdout, stderr = run_docker_command([
            "docker-compose", "-f", str(compose_file), "down"
        ])

        if code != 0:
            console.print(f"[bold red]✗ Failed to stop services[/bold red]")
            console.print(f"[red]{stderr}[/red]")
            sys.exit(1)

        console.print("[bold green]✓ Services stopped successfully[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@service_group.command(name='restart')
def restart_command():
    """Restart all RAG Memory services."""
    try:
        # Get compose file
        try:
            compose_file = get_compose_file()
        except FileNotFoundError as e:
            console.print(f"[bold red]✗ {e}[/bold red]")
            sys.exit(1)

        console.print("[bold blue]Restarting RAG Memory services...[/bold blue]\n")

        # Restart = stop + start
        console.print("[dim]Stopping services...[/dim]")
        code, _, stderr = run_docker_command([
            "docker-compose", "-f", str(compose_file), "down"
        ])

        if code != 0:
            console.print(f"[bold red]✗ Failed to stop services[/bold red]")
            console.print(f"[red]{stderr}[/red]")
            sys.exit(1)

        console.print("[dim]Starting services...[/dim]")
        code, _, stderr = run_docker_command([
            "docker-compose", "-f", str(compose_file), "up", "-d"
        ])

        if code != 0:
            console.print(f"[bold red]✗ Failed to start services[/bold red]")
            console.print(f"[red]{stderr}[/red]")
            sys.exit(1)

        console.print("[bold green]✓ Services restarted successfully[/bold green]")
        console.print("\n[dim]Run 'rag status' to check when services are ready[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@service_group.command(name='status')
def status_command():
    """Check status of all RAG Memory services."""
    try:
        # Check Docker
        if not check_docker_installed():
            console.print("[bold red]✗ Docker is not installed[/bold red]")
            sys.exit(1)

        if not check_docker_running():
            console.print("[bold red]✗ Docker daemon is not running[/bold red]")
            sys.exit(1)

        console.print("[bold blue]RAG Memory Service Status[/bold blue]\n")

        # Define services to check
        services = [
            ("PostgreSQL", "rag-memory-postgres-local"),
            ("Neo4j", "rag-memory-neo4j-local"),
            ("MCP Server", "rag-memory-mcp-local"),
            ("Backup", "rag-memory-backup-local"),
        ]

        # Create status table
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Container", style="white")
        table.add_column("Status", style="bold")

        all_running = True

        for service_name, container_name in services:
            # Check container status
            code, stdout, _ = run_docker_command([
                "docker", "ps", "--filter", f"name={container_name}",
                "--format", "{{.Status}}"
            ])

            if code == 0 and stdout.strip():
                status = stdout.strip()

                # Determine status color
                if "Up" in status:
                    if "healthy" in status.lower():
                        status_display = f"[green]✓ {status}[/green]"
                    elif "unhealthy" in status.lower():
                        status_display = f"[red]✗ {status}[/red]"
                        all_running = False
                    else:
                        status_display = f"[yellow]⚠ {status}[/yellow]"
                else:
                    status_display = f"[yellow]{status}[/yellow]"
            else:
                status_display = "[red]✗ Not running[/red]"
                all_running = False

            table.add_row(service_name, container_name, status_display)

        console.print(table)
        console.print()

        if all_running:
            console.print("[bold green]✓ All services are running[/bold green]")
        else:
            console.print("[bold yellow]⚠ Some services are not running[/bold yellow]")
            console.print("[dim]Run 'rag start' to start services[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


# Shortcuts for top-level commands
start = start_command
stop = stop_command
restart = restart_command
status = status_command
