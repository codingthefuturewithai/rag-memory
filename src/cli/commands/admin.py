"""Administrative commands for RAG Memory."""

import asyncio
import logging
import click
from pathlib import Path
from rich.table import Table

from ..utils.console import console, print_success, print_error, print_warning, print_info
from ..core.paths import Paths

logger = logging.getLogger(__name__)


@click.group(name='admin')
def admin_group():
    """Administrative commands."""
    pass


@admin_group.command(name='init')
def init_database():
    """Initialize the database schema.

    Creates all required tables and indexes for RAG Memory.
    """
    # Import here to avoid circular imports
    from src.core.database import get_database

    print_info("Initializing RAG Memory database...")
    try:
        db = get_database()
        db.init_schema()
        print_success("Database schema initialized successfully")

        print_info("\nNext steps:")
        console.print("1. Start services: [cyan]rag start[/cyan]")
        console.print("2. Check status: [cyan]rag status[/cyan]")
        console.print("3. Create a collection: [cyan]rag collection create <name> '<description>'[/cyan]")
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        raise click.Abort()


@admin_group.command(name='status')
def check_status():
    """Check RAG Memory system status."""
    # Import here to avoid circular imports
    from src.core.database import get_database
    from src.core.collections import get_collection_manager
    from src.unified import GraphStore

    console.print("[bold]RAG Memory Status[/bold]\n")

    # Create status table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan", width=20)
    table.add_column("Status", width=15)
    table.add_column("Details")

    # Check PostgreSQL
    try:
        db = get_database()
        result = db.execute_query("SELECT version()")
        version = result[0][0].split(',')[0] if result else "Unknown"
        table.add_row("PostgreSQL", "[green]✓ Connected[/green]", version)

        # Check pgvector extension
        result = db.execute_query(
            "SELECT default_version FROM pg_available_extensions WHERE name = 'vector'"
        )
        if result:
            table.add_row("pgvector", "[green]✓ Available[/green]", f"Version {result[0][0]}")
        else:
            table.add_row("pgvector", "[yellow]⚠ Not found[/yellow]", "Extension may need installation")
    except Exception as e:
        table.add_row("PostgreSQL", "[red]✗ Failed[/red]", str(e))

    # Check Neo4j
    try:
        async def check_neo4j():
            graph_store = GraphStore()
            await graph_store.init()
            result = await graph_store.health_check()
            await graph_store.close()
            return result

        neo4j_healthy = asyncio.run(check_neo4j())
        if neo4j_healthy:
            table.add_row("Neo4j", "[green]✓ Connected[/green]", "Graph database ready")
        else:
            table.add_row("Neo4j", "[yellow]⚠ Unhealthy[/yellow]", "Connection established but unhealthy")
    except Exception as e:
        table.add_row("Neo4j", "[red]✗ Failed[/red]", str(e))

    # Check collections
    try:
        coll_mgr = get_collection_manager(db)
        collections = coll_mgr.list_collections()
        count = len(collections)
        details = f"{count} collection{'s' if count != 1 else ''}"
        if collections:
            names = ", ".join([c['name'] for c in collections[:3]])
            if count > 3:
                names += f", ... ({count-3} more)"
            details += f": {names}"
        table.add_row("Collections", "[green]✓ Ready[/green]", details)
    except Exception as e:
        table.add_row("Collections", "[red]✗ Error[/red]", str(e))

    # Check configuration
    config_file = Paths.config_yaml()
    if config_file.exists():
        table.add_row("Configuration", "[green]✓ Found[/green]", str(config_file))
    else:
        table.add_row("Configuration", "[yellow]⚠ Missing[/yellow]", "Run setup to create")

    console.print(table)


@admin_group.command(name='migrate')
@click.option('--show-sql', is_flag=True, help='Show SQL statements without executing')
def migrate_database(show_sql):
    """Run database migrations.

    Applies any pending schema updates to the database.
    """
    # Import here to avoid circular imports
    from src.core.database import get_database

    if show_sql:
        print_info("Migration SQL statements:")
        console.print("[dim]-- Note: These statements would be executed[/dim]")

        # Show the migration SQL
        migration_sql = """
        -- Ensure pgvector extension is enabled
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Add any new columns or indexes here
        -- Example:
        -- ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB;
        -- CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin(metadata);
        """
        console.print(migration_sql)
    else:
        print_info("Running database migrations...")
        try:
            db = get_database()

            # Run any pending migrations
            # For now, just ensure the schema is up to date
            db.init_schema()

            print_success("Database migrations completed successfully")
        except Exception as e:
            print_error(f"Migration failed: {e}")
            raise click.Abort()


@admin_group.command(name='uninstall')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def uninstall(yes):
    """Remove RAG Memory system configuration.

    This removes configuration files but preserves data.
    """
    if not yes:
        confirm = click.confirm(
            "This will remove RAG Memory configuration files.\n"
            "Data will be preserved. Continue?",
            default=False
        )
        if not confirm:
            print_info("Uninstall cancelled")
            return

    print_info("Removing RAG Memory configuration...")

    removed_files = []
    preserved_files = []

    # Remove configuration files
    for path in [Paths.config_yaml(), Paths.env_file(), Paths.docker_compose_file(), Paths.init_sql()]:
        if path.exists():
            try:
                path.unlink()
                removed_files.append(str(path))
            except Exception as e:
                print_warning(f"Could not remove {path}: {e}")
                preserved_files.append(str(path))

    # Note: We preserve data and log directories
    for path in [Paths.data_dir(), Paths.log_dir(), Paths.backup_dir()]:
        if path.exists():
            preserved_files.append(str(path))

    if removed_files:
        print_success("Removed configuration files:")
        for file in removed_files:
            console.print(f"  - {file}")

    if preserved_files:
        print_info("Preserved data and logs:")
        for file in preserved_files:
            console.print(f"  - {file}")

    print_info("\nTo completely remove RAG Memory, also run:")
    console.print("  docker-compose down -v  # Remove Docker volumes")
    console.print("  uv tool uninstall rag-memory  # Uninstall CLI tool")