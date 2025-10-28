"""Collection management commands for RAG Memory."""

import click
from ..utils.console import console, print_success, print_error


@click.group(name='collection')
def collection_group():
    """Manage RAG Memory collections."""
    pass


# Placeholder for full collection commands migration
# The actual implementation will be migrated from src/cli.py
# This is just the structure for now