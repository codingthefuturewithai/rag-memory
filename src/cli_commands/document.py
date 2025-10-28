"""Document management commands."""

import json
import sys

import click
from rich.console import Console
from rich.table import Table

from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.document_store import get_document_store

console = Console()


@click.group()
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

        # Call business logic layer (now returns dict with documents + metadata)
        result = doc_store.list_source_documents(collection_name=collection, include_details=True)
        documents = result["documents"]

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
        console.print(f"\n[bold]Total: {result['total_count']} documents[/bold]")

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


@document.command("update")
@click.argument("doc_id", type=int)
@click.option("--content", help="New content (triggers re-chunking and re-embedding)")
@click.option("--title", help="New document title/filename")
@click.option("--metadata", help="New metadata as JSON string (merged with existing)")
def document_update(doc_id, content, title, metadata):
    """Update a source document's content, title, or metadata.

    Examples:
        # Update content (re-chunks and re-embeds automatically)
        rag document update 42 --content "New company vision: ..."

        # Update title only
        rag document update 42 --title "Updated Title"

        # Update metadata (merged with existing)
        rag document update 42 --metadata '{"status": "reviewed"}'

        # Update multiple fields
        rag document update 42 --content "..." --title "New Title"
    """
    try:
        if not content and not title and not metadata:
            console.print("[bold red]Error: Must provide at least one of --content, --title, or --metadata[/bold red]")
            sys.exit(1)

        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        console.print(f"[bold blue]Updating document {doc_id}...[/bold blue]\n")

        # Parse metadata if provided
        metadata_dict = None
        if metadata:
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError as e:
                console.print(f"[bold red]Invalid JSON in metadata: {e}[/bold red]")
                sys.exit(1)

        # Update document
        result = doc_store.update_document(
            document_id=doc_id,
            content=content,
            filename=title,
            metadata=metadata_dict
        )

        console.print(f"[bold green]✓ Updated document {doc_id}[/bold green]")
        console.print(f"  Updated fields: {', '.join(result['updated_fields'])}")

        if "content" in result['updated_fields']:
            console.print(f"  Replaced {result['old_chunk_count']} chunks with {result['new_chunk_count']} new chunks")

    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@document.command("delete")
@click.argument("doc_id", type=int)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def document_delete(doc_id, confirm):
    """Delete a source document and all its chunks.

    This permanently deletes the document and cannot be undone.

    Examples:
        # Delete with confirmation prompt
        rag document delete 42

        # Delete without confirmation
        rag document delete 42 --confirm
    """
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)
        doc_store = get_document_store(db, embedder, coll_mgr)

        # Get document info
        doc = doc_store.get_source_document(doc_id)
        if not doc:
            console.print(f"[bold red]Document {doc_id} not found[/bold red]")
            sys.exit(1)

        # Confirmation prompt unless --confirm flag is used
        if not confirm:
            console.print(f"[yellow]About to delete document {doc_id}: '{doc['filename']}'[/yellow]")
            console.print(f"[yellow]This will also delete all associated chunks.[/yellow]")
            response = input("\nAre you sure? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                console.print("[dim]Deletion cancelled[/dim]")
                return

        console.print(f"[bold blue]Deleting document {doc_id}...[/bold blue]\n")

        # Delete document
        result = doc_store.delete_document(doc_id)

        console.print(f"[bold green]✓ Deleted document {doc_id}[/bold green]")
        console.print(f"  Title: {result['document_title']}")
        console.print(f"  Chunks deleted: {result['chunks_deleted']}")
        if result['collections_affected']:
            console.print(f"  Collections affected: {', '.join(result['collections_affected'])}")

    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)
