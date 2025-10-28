"""Console utilities for rich output."""

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

# Shared console instance for consistent output
console = Console()


def create_table(title: str = None) -> Table:
    """Create a styled table.

    Args:
        title: Optional title for the table

    Returns:
        Configured Table instance
    """
    table = Table(show_header=True, header_style="bold cyan", title=title)
    return table


def print_success(message: str):
    """Print a success message with checkmark."""
    console.print(f"[green]✅ {message}[/green]")


def print_error(message: str):
    """Print an error message with X mark."""
    console.print(f"[red]❌ {message}[/red]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[cyan]ℹ️  {message}[/cyan]")