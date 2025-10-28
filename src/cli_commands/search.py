"""Search commands."""

import json
import sys

import click
from rich.console import Console

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.retrieval.search import get_similarity_search

console = Console()


@click.command(name='search')
@click.argument("query")
@click.option("--collection", help="Search within specific collection")
@click.option("--limit", default=10, help="Maximum number of results")
@click.option("--threshold", type=float, help="Minimum similarity score (0-1)")
@click.option("--metadata", help="Filter by metadata (JSON string)")
@click.option("--verbose", is_flag=True, help="Show full chunk content")
@click.option("--show-source", is_flag=True, help="Include full source document content")
def search(query, collection, limit, threshold, metadata, verbose, show_source):
    """Search for similar document chunks."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)

        # Create searcher using baseline vector-only search
        searcher = get_similarity_search(db, embedder, coll_mgr)

        # Parse metadata filter if provided
        metadata_filter = None
        if metadata:
            try:
                metadata_filter = json.loads(metadata)
            except json.JSONDecodeError as e:
                console.print(f"[bold red]Invalid JSON in metadata filter: {e}[/bold red]")
                sys.exit(1)

        console.print(f"[bold blue]Searching for: {query}[/bold blue]")
        if metadata_filter:
            console.print(f"[dim]Metadata filter: {metadata_filter}[/dim]")

        # Execute vector-only search
        results = searcher.search_chunks(
            query, limit, threshold, collection, include_source=show_source, metadata_filter=metadata_filter
        )

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"\n[bold green]Found {len(results)} results:[/bold green]\n")

        for i, result in enumerate(results, 1):
            console.print(f"[bold cyan]Result {i}:[/bold cyan]")
            console.print(f"  Chunk ID: {result.chunk_id}")
            console.print(f"  Source: {result.source_filename} (Doc ID: {result.source_document_id})")
            console.print(f"  Chunk: {result.chunk_index + 1}")
            console.print(
                f"  Similarity: [bold green]{result.similarity:.4f}[/bold green]"
            )
            console.print(f"  Position: chars {result.char_start}-{result.char_end}")

            if verbose:
                console.print(f"  Content:\n{result.content}")
                if result.metadata:
                    console.print(f"  Metadata: {json.dumps(result.metadata, indent=2)}")
                if show_source and result.source_content:
                    console.print(f"  [dim]Full Source ({len(result.source_content)} chars)[/dim]")
            else:
                preview_len = 150 if show_source else 100
                console.print(f"  Preview: {result.content[:preview_len]}...")

            console.print()

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
