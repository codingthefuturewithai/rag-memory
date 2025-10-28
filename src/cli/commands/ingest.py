"""Document ingestion commands for RAG Memory."""

import click
from ..utils.console import console, print_success, print_error


@click.group(name='ingest')
def ingest_group():
    """Ingest documents into RAG Memory."""
    pass


# Placeholder for full ingest commands migration
# The actual implementation will be migrated from src/cli.py
# This is just the structure for now