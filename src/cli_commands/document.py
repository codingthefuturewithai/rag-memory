"""Document management commands."""

import click


@click.group()
def document():
    """Manage source documents."""
    pass


@document.command("list")
@click.option("--collection", help="Filter by collection name")
@click.option("--limit", type=int, default=20, help="Number of documents to show")
def document_list(collection, limit):
    """List documents."""
    click.echo(f"Document list - COPYING FULL IMPLEMENTATION IN PHASE 4")


@document.command("view")
@click.argument("document_id", type=int)
@click.option("--show-chunks", is_flag=True, help="Show document chunks")
@click.option("--show-content", is_flag=True, help="Show full content")
def document_view(document_id, show_chunks, show_content):
    """View document details."""
    click.echo(f"Document view - COPYING FULL IMPLEMENTATION IN PHASE 4")


@document.command("update")
@click.argument("document_id", type=int)
@click.option("--content", help="New content")
@click.option("--title", help="New title")
@click.option("--metadata", help="JSON metadata")
def document_update(document_id, content, title, metadata):
    """Update a document (re-chunks and re-embeds)."""
    click.echo(f"Document update - COPYING FULL IMPLEMENTATION IN PHASE 4")


@document.command("delete")
@click.argument("document_id", type=int)
@click.option("--confirm", is_flag=True, help="Skip confirmation")
def document_delete(document_id, confirm):
    """Delete a document."""
    click.echo(f"Document delete - COPYING FULL IMPLEMENTATION IN PHASE 4")
