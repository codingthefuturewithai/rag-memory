"""Document management commands for RAG Memory."""

import click
from ..utils.console import console, print_success, print_error


@click.group(name='document')
def document_group():
    """Manage documents in RAG Memory."""
    pass


# Placeholder for full document commands migration
# The actual implementation will be migrated from src/cli.py
# This is just the structure for now