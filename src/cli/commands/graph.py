"""Knowledge graph commands for RAG Memory."""

import click
from ..utils.console import console, print_success, print_error


@click.group(name='graph')
def graph_group():
    """Query and manage the knowledge graph."""
    pass


# Placeholder for full graph commands migration
# The actual implementation will be migrated from src/cli.py
# This is just the structure for now