"""Command-line interface for the pgvector RAG POC."""

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.collections import get_collection_manager
from src.database import get_database
from src.embeddings import get_embedding_generator
from src.ingestion import get_document_ingestion
from src.search import get_similarity_search

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

            table.add_row("Documents", str(stats["documents"]))
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


@ingest.command("text")
@click.argument("text")
@click.option("--collection", required=True, help="Collection name")
@click.option("--metadata", help="Metadata as JSON string")
def ingest_text(text, collection, metadata):
    """Ingest a text document."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)

        metadata_dict = json.loads(metadata) if metadata else None

        console.print("[bold blue]Ingesting document...[/bold blue]")
        doc_id = ingestion.ingest_text(text, collection, metadata_dict)

        console.print(
            f"[bold green]✓ Ingested document (ID: {doc_id}) to collection '{collection}'[/bold green]"
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@ingest.command("file")
@click.argument("path", type=click.Path(exists=True))
@click.option("--collection", required=True, help="Collection name")
@click.option("--metadata", help="Additional metadata as JSON string")
def ingest_file(path, collection, metadata):
    """Ingest a document from a file."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)

        metadata_dict = json.loads(metadata) if metadata else None

        console.print(f"[bold blue]Ingesting file: {path}[/bold blue]")
        doc_id = ingestion.ingest_file(path, collection, metadata_dict)

        console.print(
            f"[bold green]✓ Ingested file (ID: {doc_id}) to collection '{collection}'[/bold green]"
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
    """Ingest all files from a directory."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)

        ext_list = [ext.strip() for ext in extensions.split(",")]

        console.print(
            f"[bold blue]Ingesting files from: {path} (extensions: {ext_list})[/bold blue]"
        )
        doc_ids = ingestion.ingest_directory(path, collection, ext_list, recursive)

        console.print(
            f"[bold green]✓ Ingested {len(doc_ids)} documents to collection '{collection}'[/bold green]"
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--collection", help="Search within specific collection")
@click.option("--limit", default=10, help="Maximum number of results")
@click.option("--threshold", type=float, help="Minimum similarity score (0-1)")
@click.option("--verbose", is_flag=True, help="Show full document content")
def search(query, collection, limit, threshold, verbose):
    """Search for similar documents."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        console.print(f"[bold blue]Searching for: {query}[/bold blue]")

        results = searcher.search(query, limit, threshold, collection)

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        console.print(f"\n[bold green]Found {len(results)} results:[/bold green]\n")

        for i, result in enumerate(results, 1):
            console.print(f"[bold cyan]Result {i}:[/bold cyan]")
            console.print(f"  Document ID: {result.document_id}")
            console.print(
                f"  Similarity: [bold green]{result.similarity:.4f}[/bold green]"
            )
            console.print(f"  Distance: {result.distance:.4f}")

            if verbose:
                console.print(f"  Content: {result.content[:200]}...")
                if result.metadata:
                    console.print(f"  Metadata: {json.dumps(result.metadata, indent=2)}")
            else:
                console.print(f"  Preview: {result.content[:100]}...")

            console.print()

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.command("test-similarity")
def test_similarity():
    """Test similarity search with known documents."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        console.print("[bold blue]Running similarity tests...[/bold blue]\n")

        # Create test collection
        collection_name = "similarity_test"
        try:
            coll_mgr.create_collection(
                collection_name, "Test collection for similarity validation"
            )
            console.print(f"[green]Created test collection '{collection_name}'[/green]")
        except ValueError:
            console.print(
                f"[yellow]Test collection '{collection_name}' already exists[/yellow]"
            )

        # Test documents with expected similarity ranges
        test_cases = [
            {
                "name": "High Similarity Test",
                "document": "PostgreSQL is a powerful relational database system with advanced features for storing and querying data efficiently.",
                "query": "What is PostgreSQL and what type of database is it?",
                "expected_range": (0.70, 0.95),
            },
            {
                "name": "Medium Similarity Test",
                "document": "Python is a popular programming language widely used for data science, machine learning, and web development.",
                "query": "Tell me about machine learning tools and frameworks",
                "expected_range": (0.50, 0.75),
            },
            {
                "name": "Low Similarity Test",
                "document": "The weather today is sunny and warm with clear blue skies.",
                "query": "How do I configure a database server?",
                "expected_range": (0.10, 0.40),
            },
        ]

        results_table = Table(title="Similarity Test Results")
        results_table.add_column("Test", style="cyan")
        results_table.add_column("Expected Range", style="blue")
        results_table.add_column("Actual Score", style="green")
        results_table.add_column("Status", style="white")

        for test_case in test_cases:
            # Ingest document
            doc_id = ingestion.ingest_text(
                test_case["document"],
                collection_name,
                {"test_name": test_case["name"]},
            )

            # Search for it
            search_results = searcher.search(
                test_case["query"], limit=1, collection_name=collection_name
            )

            if search_results:
                similarity = search_results[0].similarity
                expected_min, expected_max = test_case["expected_range"]

                if expected_min <= similarity <= expected_max:
                    status = "✓ PASS"
                    style = "green"
                else:
                    status = "✗ FAIL"
                    style = "red"

                results_table.add_row(
                    test_case["name"],
                    f"{expected_min:.2f} - {expected_max:.2f}",
                    f"[{style}]{similarity:.4f}[/{style}]",
                    f"[{style}]{status}[/{style}]",
                )
            else:
                results_table.add_row(
                    test_case["name"],
                    f"{test_case['expected_range'][0]:.2f} - {test_case['expected_range'][1]:.2f}",
                    "[red]N/A[/red]",
                    "[red]✗ NO RESULTS[/red]",
                )

        console.print()
        console.print(results_table)
        console.print()
        console.print(
            "[bold]Note:[/bold] High similarity scores (0.70-0.95) indicate proper "
            "vector normalization is working!"
        )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.command()
def benchmark():
    """Run performance benchmarks."""
    import time

    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        ingestion = get_document_ingestion(db, embedder, coll_mgr)
        searcher = get_similarity_search(db, embedder, coll_mgr)

        console.print("[bold blue]Running performance benchmarks...[/bold blue]\n")

        # Create benchmark collection
        collection_name = "benchmark"
        try:
            coll_mgr.create_collection(collection_name, "Benchmark collection")
        except ValueError:
            pass

        # Test documents
        test_docs = [
            "PostgreSQL is a powerful open-source relational database system.",
            "Python is a versatile programming language for many applications.",
            "Machine learning models require large amounts of training data.",
            "Cloud computing provides scalable infrastructure for applications.",
            "Data science involves analyzing and interpreting complex data sets.",
        ]

        # Benchmark ingestion
        console.print("[cyan]Benchmarking document ingestion...[/cyan]")
        start_time = time.time()
        doc_ids = ingestion.ingest_batch(test_docs, collection_name)
        ingestion_time = time.time() - start_time

        console.print(
            f"  Ingested {len(doc_ids)} documents in {ingestion_time:.3f}s "
            f"({len(doc_ids)/ingestion_time:.2f} docs/s)"
        )

        # Benchmark search
        console.print("\n[cyan]Benchmarking similarity search...[/cyan]")
        query = "Tell me about databases and data storage"

        search_times = []
        for i in range(5):
            start_time = time.time()
            results = searcher.search(query, limit=10, collection_name=collection_name)
            search_time = time.time() - start_time
            search_times.append(search_time)

        avg_search_time = sum(search_times) / len(search_times)
        console.print(
            f"  Average search time: {avg_search_time*1000:.2f}ms (over {len(search_times)} runs)"
        )
        console.print(f"  Found {len(results)} results per query")

        if results:
            console.print(
                f"  Top result similarity: {results[0].similarity:.4f}"
            )

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
