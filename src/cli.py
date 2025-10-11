"""Command-line interface for the pgvector RAG POC."""

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.ingestion.document_store import get_document_store
from src.core.embeddings import get_embedding_generator
from src.retrieval.search import get_similarity_search
from src.ingestion.web_crawler import crawl_single_page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

console = Console()


@click.group()
def main():
    """PostgreSQL pgvector RAG POC - Command-line interface."""
    pass


@main.command()
def init():
    """Initialize database schema."""
    try:
        db = get_database()
        console.print("[bold blue]Initializing database...[/bold blue]")

        if db.test_connection():
            console.print("[bold green]✓ Database connection successful[/bold green]")

            if db.initialize_schema():
                console.print(
                    "[bold green]✓ Database schema initialized[/bold green]"
                )
            else:
                console.print(
                    "[yellow]⚠ Schema tables not found - they should be created by init.sql[/yellow]"
                )
                console.print(
                    "[yellow]Make sure Docker container initialized properly[/yellow]"
                )
        else:
            console.print("[bold red]✗ Database connection failed[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.command()
def status():
    """Check database connection and show statistics."""
    try:
        db = get_database()
        console.print("[bold blue]Checking database status...[/bold blue]")

        if db.test_connection():
            console.print("[bold green]✓ Database connection: OK[/bold green]")

            stats = db.get_stats()
            table = Table(title="Database Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Documents", str(stats["source_documents"]))
            table.add_row("Chunks", str(stats["chunks"]))
            table.add_row("Collections", str(stats["collections"]))
            table.add_row("Database Size", stats["database_size"])

            console.print(table)
        else:
            console.print("[bold red]✗ Database connection failed[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.group()
def collection():
    """Manage collections."""
    pass


@collection.command("create")
@click.argument("name")
@click.option("--description", help="Collection description")
def collection_create(name, description):
    """Create a new collection."""
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        collection_id = mgr.create_collection(name, description)
        console.print(
            f"[bold green]✓ Created collection '{name}' (ID: {collection_id})[/bold green]"
        )

    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@collection.command("list")
def collection_list():
    """List all collections."""
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        collections = mgr.list_collections()

        if not collections:
            console.print("[yellow]No collections found[/yellow]")
            return

        table = Table(title="Collections")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Documents", style="green")
        table.add_column("Created", style="blue")

        for coll in collections:
            table.add_row(
                coll["name"],
                coll["description"] or "",
                str(coll["document_count"]),
                str(coll["created_at"]),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@collection.command("delete")
@click.argument("name")
def collection_delete(name):
    """Delete a collection."""
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        if mgr.delete_collection(name):
            console.print(f"[bold green]✓ Deleted collection '{name}'[/bold green]")
        else:
            console.print(f"[yellow]Collection '{name}' not found[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.group()
def ingest():
    """Ingest documents."""
    pass


@ingest.command("file")
@click.argument("path", type=click.Path(exists=True))
@click.option("--collection", required=True, help="Collection name")
@click.option("--metadata", help="Additional metadata as JSON string")
def ingest_file(path, collection, metadata):
    """Ingest a document from a file with automatic chunking."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        metadata_dict = json.loads(metadata) if metadata else None

        console.print(f"[bold blue]Ingesting file: {path}[/bold blue]")

        source_id, chunk_ids = doc_store.ingest_file(path, collection, metadata_dict)
        console.print(
            f"[bold green]✓ Ingested file (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@ingest.command("directory")
@click.argument("path", type=click.Path(exists=True))
@click.option("--collection", required=True, help="Collection name")
@click.option(
    "--extensions", default=".txt,.md", help="Comma-separated file extensions"
)
@click.option("--recursive", is_flag=True, help="Search subdirectories")
def ingest_directory(path, collection, extensions, recursive):
    """Ingest all files from a directory with automatic chunking."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        ext_list = [ext.strip() for ext in extensions.split(",")]
        path_obj = Path(path)

        console.print(
            f"[bold blue]Ingesting files from: {path} (extensions: {ext_list})[/bold blue]"
        )

        # Find all matching files
        files = []
        if recursive:
            for ext in ext_list:
                files.extend(path_obj.rglob(f"*{ext}"))
        else:
            for ext in ext_list:
                files.extend(path_obj.glob(f"*{ext}"))

        files = sorted(set(files))  # Remove duplicates and sort

        # Ingest each file
        source_ids = []
        total_chunks = 0
        for file_path in files:
            try:
                source_id, chunk_ids = doc_store.ingest_file(str(file_path), collection)
                source_ids.append(source_id)
                total_chunks += len(chunk_ids)
                console.print(f"  ✓ {file_path.name}: {len(chunk_ids)} chunks")
            except Exception as e:
                console.print(f"  ✗ {file_path.name}: {e}")

        console.print(
            f"[bold green]✓ Ingested {len(source_ids)} documents with {total_chunks} total chunks to collection '{collection}'[/bold green]"
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@ingest.command("url")
@click.argument("url")
@click.option("--collection", required=True, help="Collection name")
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
@click.option("--verbose", is_flag=True, help="Enable verbose crawling output")
def ingest_url(url, collection, headless, verbose):
    """Crawl and ingest a web page with automatic chunking."""
    try:
        console.print(f"[bold blue]Crawling URL: {url}[/bold blue]")

        # Crawl the page
        result = asyncio.run(crawl_single_page(url, headless=headless, verbose=verbose))

        if not result.success:
            console.print(f"[bold red]✗ Failed to crawl {url}[/bold red]")
            if result.error:
                console.print(f"[bold red]Error: {result.error.error_message}[/bold red]")
            sys.exit(1)

        console.print(f"[green]✓ Successfully crawled page ({len(result.content)} chars)[/green]")

        # Ingest the content
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        source_id, chunk_ids = doc_store.ingest_document(
            content=result.content,
            filename=result.metadata.get("title", url),
            collection_name=collection,
            metadata=result.metadata,
            file_type="web_page",
        )

        console.print(
            f"[bold green]✓ Ingested web page (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
        )
        console.print(f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]")
        console.print(f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@main.command()
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


@main.group()
def document():
    """Manage source documents."""
    pass


@document.command("list")
@click.option("--collection", help="Filter by collection")
def document_list(collection):
    """List all source documents."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        console.print("[bold blue]Listing source documents...[/bold blue]\n")

        documents = doc_store.list_source_documents(collection)

        if not documents:
            console.print("[yellow]No documents found[/yellow]")
            return

        table = Table(title=f"Source Documents{f' in {collection}' if collection else ''}")
        table.add_column("ID", style="cyan")
        table.add_column("Filename", style="white")
        table.add_column("Type", style="blue")
        table.add_column("Size", style="green")
        table.add_column("Chunks", style="magenta")
        table.add_column("Created", style="dim")

        for doc in documents:
            size_kb = doc["file_size"] / 1024 if doc["file_size"] else 0
            table.add_row(
                str(doc["id"]),
                doc["filename"],
                doc["file_type"] or "text",
                f"{size_kb:.1f} KB",
                str(doc["chunk_count"]),
                str(doc["created_at"]),
            )

        console.print(table)
        console.print(f"\n[bold]Total: {len(documents)} documents[/bold]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@document.command("view")
@click.argument("doc_id", type=int)
@click.option("--show-chunks", is_flag=True, help="Show all chunks")
@click.option("--show-content", is_flag=True, help="Show full document content")
def document_view(doc_id, show_chunks, show_content):
    """View a source document and its chunks."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        console.print(f"[bold blue]Viewing document {doc_id}...[/bold blue]\n")

        # Get source document
        doc = doc_store.get_source_document(doc_id)
        if not doc:
            console.print(f"[bold red]Document {doc_id} not found[/bold red]")
            sys.exit(1)

        # Display document info
        console.print("[bold cyan]Document Info:[/bold cyan]")
        console.print(f"  ID: {doc['id']}")
        console.print(f"  Filename: {doc['filename']}")
        console.print(f"  Type: {doc['file_type']}")
        console.print(f"  Size: {doc['file_size']} bytes ({doc['file_size']/1024:.1f} KB)")
        console.print(f"  Created: {doc['created_at']}")
        console.print(f"  Updated: {doc['updated_at']}")
        if doc["metadata"]:
            console.print(f"  Metadata: {json.dumps(doc['metadata'], indent=2)}")

        if show_content:
            console.print(f"\n[bold cyan]Content:[/bold cyan]")
            console.print(f"{doc['content'][:1000]}..." if len(doc['content']) > 1000 else doc['content'])

        # Get chunks
        chunks = doc_store.get_document_chunks(doc_id)
        console.print(f"\n[bold cyan]Chunks: {len(chunks)}[/bold cyan]")

        if show_chunks and chunks:
            for chunk in chunks:
                console.print(f"\n  [bold]Chunk {chunk['chunk_index']}:[/bold] (ID: {chunk['id']})")
                console.print(f"    Position: chars {chunk['char_start']}-{chunk['char_end']}")
                console.print(f"    Length: {len(chunk['content'])} chars")
                console.print(f"    Preview: {chunk['content'][:100]}...")
        elif chunks:
            console.print(f"  Use --show-chunks to view all {len(chunks)} chunks")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
