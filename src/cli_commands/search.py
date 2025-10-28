"""Search commands."""

import click


@click.command(name='search')
@click.argument("query")
@click.option("--collection", help="Collection name to search in")
@click.option("--limit", type=int, default=5, help="Number of results")
@click.option("--threshold", type=float, default=0.7, help="Similarity threshold")
@click.option("--metadata", help="JSON metadata filter")
@click.option("--verbose", is_flag=True, help="Show detailed results")
@click.option("--show-source", is_flag=True, help="Display source document content")
def search(query, collection, limit, threshold, metadata, verbose, show_source):
    """Search for similar document chunks."""
    click.echo(f"Search - COPYING FULL IMPLEMENTATION IN PHASE 4")
