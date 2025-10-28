"""Collection management commands."""

import json
import sys
import click
from rich.console import Console
from rich.table import Table

from src.core.database import get_database
from src.core.collections import get_collection_manager

console = Console()


@click.group()
def collection():
    """Manage collections."""
    pass


@collection.command("create")
@click.argument("name")
@click.option("--description", required=True, help="Collection description")
@click.option("--domain", required=True, help="Domain category (immutable)")
@click.option("--domain-scope", required=True, help="Domain scope description (immutable)")
def collection_create(name, description, domain, domain_scope):
    """Create a new collection."""
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        collection_id = mgr.create_collection(name, description, domain, domain_scope)
        console.print(
            f"[bold green]✓ Created collection '{name}' (ID: {collection_id})[/bold green]"
        )

    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@collection.command("update-metadata")
@click.argument("name")
@click.option("--add-fields", required=True, help="JSON dict of new fields to add")
def collection_update_metadata(name, add_fields):
    """Update collection metadata schema (additive only).

    Add new optional metadata fields to an existing collection.
    Cannot remove existing fields or change their types.

    Examples:
        rag collection update-metadata my-docs \\
            --add-fields '{"priority": "string", "reviewed": "boolean"}'

        rag collection update-metadata my-docs \\
            --add-fields '{"status": {"type": "string", "enum": ["draft", "published"]}}'
    """
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        # Parse JSON fields
        try:
            new_fields = json.loads(add_fields)
        except json.JSONDecodeError as e:
            console.print(f"[bold red]Invalid JSON: {e}[/bold red]")
            sys.exit(1)

        # Update the collection
        result = mgr.update_collection_metadata_schema(name, new_fields)

        console.print(f"[bold green]✓ Updated collection '{name}' metadata schema[/bold green]")
        console.print(f"  Fields added: {len(new_fields) if isinstance(new_fields, dict) else 0}")
        console.print(f"  Total custom fields: {len(result['metadata_schema'].get('custom', {}))}")

        # Show the updated schema
        console.print("\n[bold]Updated schema:[/bold]")
        console.print_json(data=result['metadata_schema'])

    except ValueError as e:
        console.print(f"[bold red]Validation error: {e}[/bold red]")
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


@collection.command("info")
@click.argument("name")
def collection_info(name):
    """Show detailed information about a collection including crawl history.

    Displays collection statistics, sample documents, and a history of all
    web pages that have been crawled into this collection. Useful for
    understanding what content is already stored and avoiding duplicate crawls.

    Examples:
        rag collection info python-docs
        rag collection info my-knowledge-base
    """
    try:
        db = get_database()
        coll_mgr = get_collection_manager(db)

        console.print(f"[bold blue]Collection: {name}[/bold blue]\n")

        # Get collection basic info
        collection = coll_mgr.get_collection(name)
        if not collection:
            console.print(f"[yellow]Collection '{name}' not found[/yellow]")
            sys.exit(1)

        # Display basic info
        console.print(f"[cyan]Description:[/cyan] {collection['description'] or '(none)'}")
        console.print(f"[cyan]Created:[/cyan] {collection['created_at']}\n")

        # Get detailed statistics
        conn = db.connect()
        with conn.cursor() as cur:
            # Get chunk count
            cur.execute(
                """
                SELECT COUNT(DISTINCT dc.id)
                FROM document_chunks dc
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                """,
                (collection["id"],),
            )
            chunk_count = cur.fetchone()[0]

            # Display statistics table
            stats_table = Table(title="Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green", justify="right")

            stats_table.add_row("Documents", str(collection.get("document_count", 0)))
            stats_table.add_row("Chunks", str(chunk_count))

            console.print(stats_table)
            console.print()

            # Get sample documents
            cur.execute(
                """
                SELECT DISTINCT sd.id, sd.filename, sd.file_type, sd.created_at
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                ORDER BY sd.created_at DESC
                LIMIT 5
                """,
                (collection["id"],),
            )
            sample_docs = cur.fetchall()

            if sample_docs:
                console.print("[bold cyan]Sample Documents:[/bold cyan]")
                for doc_id, filename, file_type, _ in sample_docs:
                    type_badge = f"[dim]({file_type})[/dim]" if file_type else ""
                    console.print(f"  • {filename} {type_badge} [dim](ID: {doc_id})[/dim]")
                console.print()

            # Get crawl history (web pages with crawl_root_url metadata)
            cur.execute(
                """
                SELECT DISTINCT
                    sd.metadata->>'crawl_root_url' as crawl_url,
                    sd.metadata->>'crawl_timestamp' as crawl_time,
                    COUNT(DISTINCT sd.id) as page_count,
                    COUNT(DISTINCT dc.id) as chunk_count
                FROM source_documents sd
                JOIN document_chunks dc ON dc.source_document_id = sd.id
                JOIN chunk_collections cc ON cc.chunk_id = dc.id
                WHERE cc.collection_id = %s
                  AND sd.metadata->>'crawl_root_url' IS NOT NULL
                GROUP BY sd.metadata->>'crawl_root_url', sd.metadata->>'crawl_timestamp'
                ORDER BY sd.metadata->>'crawl_timestamp' DESC
                LIMIT 20
                """,
                (collection["id"],),
            )
            crawl_history = cur.fetchall()

            if crawl_history:
                console.print("[bold cyan]Crawl History:[/bold cyan]")
                crawl_table = Table()
                crawl_table.add_column("Root URL", style="white", no_wrap=False)
                crawl_table.add_column("Pages", style="green", justify="right")
                crawl_table.add_column("Chunks", style="blue", justify="right")
                crawl_table.add_column("Timestamp", style="dim")

                for crawl_url, crawl_time, page_count, chunk_count in crawl_history:
                    # Format timestamp (remove microseconds if present)
                    timestamp = crawl_time.split('.')[0] if crawl_time else "N/A"

                    crawl_table.add_row(
                        crawl_url,
                        str(page_count),
                        str(chunk_count),
                        timestamp
                    )

                console.print(crawl_table)
                console.print(f"\n[dim]Total crawl sessions: {len(crawl_history)}[/dim]")
            else:
                console.print("[dim]No web crawls found in this collection[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@collection.command("schema")
@click.argument("name")
def collection_schema(name):
    """Display the metadata schema for a collection.

    Shows the structure of metadata fields configured for the collection,
    which defines what metadata can be associated with documents.

    Examples:
        rag collection schema my-docs
    """
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        collection = mgr.get_collection(name)
        if not collection:
            console.print(f"[yellow]Collection '{name}' not found[/yellow]")
            sys.exit(1)

        metadata_schema = collection.get("metadata_schema", {})

        if not metadata_schema:
            console.print(f"[dim]Collection '{name}' has no metadata schema configured[/dim]")
            return

        console.print(f"[bold cyan]Metadata Schema for '{name}':[/bold cyan]")
        console.print()

        # Display schema as formatted JSON
        schema_json = json.dumps(metadata_schema, indent=2)
        console.print(schema_json)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@collection.command("delete")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def collection_delete(name, yes):
    """Delete a collection (admin function - requires confirmation)."""
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        # Get collection info for confirmation
        collection = mgr.get_collection(name)
        if not collection:
            console.print(f"[yellow]Collection '{name}' not found[/yellow]")
            sys.exit(1)

        # Get document count
        doc_count = collection.get("document_count", 0)

        # Show warning and prompt for confirmation
        if not yes:
            console.print(f"\n[bold red]⚠️  WARNING: This will permanently delete collection '{name}'[/bold red]")
            console.print(f"  • {doc_count} documents will be removed")
            console.print(f"  • This action cannot be undone\n")

            confirm = click.confirm("Are you sure you want to proceed?", default=False)
            if not confirm:
                console.print("[yellow]Deletion cancelled[/yellow]")
                return

        if mgr.delete_collection(name):
            console.print(f"[bold green]✓ Deleted collection '{name}' ({doc_count} documents)[/bold green]")
        else:
            console.print(f"[yellow]Failed to delete collection '{name}'[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
