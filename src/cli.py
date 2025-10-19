"""Command-line interface for RAG Memory."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Configure cross-platform file logging (match MCP server)
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "cli.log"),
        logging.StreamHandler()  # Also log to stderr
    ]
)
# Suppress dotenv parsing warnings from dependencies (e.g., Crawl4AI)
logging.getLogger("dotenv.main").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

import click
from rich.console import Console
from rich.table import Table

from src.core.chunking import ChunkingConfig, get_document_chunker
from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.ingestion.document_store import get_document_store
from src.core.embeddings import get_embedding_generator
from src.retrieval.search import get_similarity_search
from src.retrieval.hybrid_search import get_hybrid_search
from src.retrieval.multi_query import get_multi_query_search
from src.ingestion.web_crawler import crawl_single_page, WebCrawler
from src.ingestion.website_analyzer import analyze_website
from src.unified import GraphStore, UnifiedIngestionMediator

console = Console()

# Global variables to hold RAG components (initialized by startup)
db = None
embedder = None
coll_mgr = None
doc_store = None

# Global variables for Knowledge Graph components (match MCP server)
graph_store = None
unified_mediator = None


def get_version():
    """Get package version from installed metadata."""
    try:
        from importlib.metadata import version
        return version("rag-memory")
    except Exception:
        return "unknown"


def initialize_components():
    """
    Initialize RAG components only.

    Knowledge Graph components (graph_store, unified_mediator) are initialized
    lazily within async context to avoid event loop conflicts.
    """
    global db, embedder, coll_mgr, doc_store

    # Initialize RAG components
    logger.info("Initializing RAG components...")
    db = get_database()
    embedder = get_embedding_generator()
    coll_mgr = get_collection_manager(db)
    doc_store = get_document_store(db, embedder, coll_mgr)
    logger.info("RAG components initialized")


async def initialize_graph_components():
    """
    Initialize Knowledge Graph components within async context.

    This MUST be called from within an async function to avoid
    "Future attached to a different loop" errors.

    Returns:
        tuple: (graph_store, unified_mediator) if successful, (None, None) if failed
    """
    logger.info("Initializing Knowledge Graph components...")
    try:
        from graphiti_core import Graphiti

        # Read Neo4j connection details from environment
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )
        await graphiti.build_indices_and_constraints()

        graph_store = GraphStore(graphiti)
        unified_mediator = UnifiedIngestionMediator(db, embedder, coll_mgr, graph_store)
        logger.info("Knowledge Graph components initialized")
        return graph_store, unified_mediator

    except Exception as e:
        logger.warning(f"Failed to initialize Knowledge Graph: {e}")
        logger.warning("Knowledge Graph features will be disabled. RAG-only mode.")
        return None, None


@click.group()
@click.version_option(version=get_version(), prog_name="rag")
def main():
    """RAG Memory - Command-line interface for semantic document storage and retrieval."""
    # Check for first-run setup before executing any command
    from src.core.first_run import ensure_config_or_exit
    ensure_config_or_exit()

    # Initialize components if not already initialized
    global db
    if db is None:
        initialize_components()


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


@main.command()
@click.option("--show-sql", is_flag=True, help="Print SQL statements being executed")
def migrate(show_sql):
    """Run database migrations using Alembic.

    Applies all pending migrations to bring the database schema up to date.

    Examples:
        # Run all pending migrations
        uv run rag migrate

        # Run migrations with SQL output
        uv run rag migrate --show-sql
    """
    try:
        import subprocess

        console.print("[bold blue]Running database migrations...[/bold blue]\n")

        # Build alembic command
        cmd = ["uv", "run", "alembic", "upgrade", "head"]

        if show_sql:
            cmd.append("--sql")

        # Run alembic upgrade
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        # Display output
        if result.stdout:
            console.print(result.stdout)

        if result.stderr:
            console.print(result.stderr)

        if result.returncode == 0:
            console.print("[bold green]✓ Migrations completed successfully[/bold green]")
        else:
            console.print("[bold red]✗ Migration failed[/bold red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@main.command()
@click.argument("url")
@click.option("--include-urls", is_flag=True, help="Include full URL lists per pattern")
@click.option("--max-urls", type=int, default=10, help="Max URLs per pattern when --include-urls (default: 10)")
@click.option("--timeout", type=int, default=10, help="Request timeout in seconds (default: 10)")
def analyze(url, include_urls, max_urls, timeout):
    """Analyze a website's structure by parsing its sitemap.
    
    This command fetches and parses the sitemap.xml from a website, then groups
    URLs by pattern (e.g., /api/*, /docs/*, /blog/*) to help you understand
    the site structure and plan comprehensive crawls.
    
    Examples:
        # Quick analysis (pattern statistics only)
        uv run rag analyze https://docs.python.org
        
        # Include sample URLs for each pattern
        uv run rag analyze https://docs.python.org --include-urls
        
        # Show more URLs per pattern
        uv run rag analyze https://docs.python.org --include-urls --max-urls 20
    """
    try:
        console.print(f"[bold blue]Analyzing website: {url}[/bold blue]\n")
        
        # Perform analysis
        result = analyze_website(url, timeout, include_urls, max_urls)
        
        # Show results
        if result["total_urls"] == 0:
            console.print(f"[yellow]⚠ {result['notes']}[/yellow]")
            return
        
        console.print(f"[green]✓ Found sitemap with {result['total_urls']:,} URLs[/green]")
        console.print(f"[dim]Method: {result['analysis_method']}[/dim]")
        
        # Show domains if multiple
        if "domains" in result and len(result["domains"]) > 1:
            console.print(f"[yellow]⚠ Sitemap contains URLs from {len(result['domains'])} domains:[/yellow]")
            for domain in result["domains"]:
                console.print(f"  • {domain}")
        elif "domains" in result and len(result["domains"]) == 1:
            console.print(f"[dim]Domain: {result['domains'][0]}[/dim]")
        
        console.print()
        
        # Display pattern statistics table
        if result["pattern_stats"]:
            table = Table(title="URL Pattern Statistics")
            table.add_column("Pattern", style="cyan", no_wrap=True)
            table.add_column("Count", style="green", justify="right")
            table.add_column("Avg Depth", style="blue", justify="right")
            table.add_column("Example URLs", style="white")
            
            for pattern, stats in result["pattern_stats"].items():
                # Format example URLs (show just paths, truncate if needed)
                examples = stats["example_urls"][:3]
                example_text = "\n".join([
                    urlparse(url).path[:50] + ("..." if len(urlparse(url).path) > 50 else "")
                    for url in examples
                ])
                
                table.add_row(
                    pattern,
                    str(stats["count"]),
                    str(stats["avg_depth"]),
                    example_text
                )
            
            console.print(table)
        
        # Show full URL lists if requested
        if include_urls and "url_groups" in result:
            console.print(f"\n[bold cyan]URL Lists (max {max_urls} per pattern):[/bold cyan]\n")
            for pattern, urls in result["url_groups"].items():
                console.print(f"[bold]{pattern}[/bold] ({len(urls)} URLs):")
                for url in urls:
                    console.print(f"  • {url}")
                console.print()
        
        console.print(f"\n[dim]{result['notes']}[/dim]")
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        import traceback
        traceback.print_exc()
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


@collection.command("info")
@click.argument("name")
def collection_info(name):
    """Show detailed information about a collection including crawl history.
    
    Displays collection statistics, sample documents, and a history of all
    web pages that have been crawled into this collection. Useful for
    understanding what content is already stored and avoiding duplicate crawls.
    
    Examples:
        uv run rag collection info python-docs
        uv run rag collection info my-knowledge-base
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


@collection.command("update")
@click.argument("name")
@click.option("--description", required=True, help="New collection description")
def collection_update(name, description):
    """Update a collection's description.

    Examples:
        uv run rag collection update my-docs --description "Updated documentation collection"
    """
    try:
        db = get_database()
        mgr = get_collection_manager(db)

        # Get collection to verify it exists
        collection = mgr.get_collection(name)
        if not collection:
            console.print(f"[yellow]Collection '{name}' not found[/yellow]")
            sys.exit(1)

        # Update the description
        conn = db.connect()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE collections SET description = %s WHERE name = %s",
                (description, name)
            )
            conn.commit()

        console.print(f"[bold green]✓ Updated collection '{name}'[/bold green]")
        console.print(f"  New description: {description}")

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


@main.group()
def ingest():
    """Ingest documents."""
    pass


@ingest.command("file")
@click.argument("path", type=click.Path(exists=True))
@click.option("--collection", required=True, help="Collection name")
@click.option("--metadata", help="Additional metadata as JSON string")
def ingest_file_cmd(path, collection, metadata):
    """Ingest a document from a file with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.
    """
    async def run_ingest():
        try:
            metadata_dict = json.loads(metadata) if metadata else None

            console.print(f"[bold blue]Ingesting file: {path}[/bold blue]")

            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = await initialize_graph_components()

            # Use unified mediator if available (match MCP server logic)
            if local_unified_mediator:
                logger.info(f"Using unified mediator for file: {Path(path).name}")

                # Read file content
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()

                # Merge file metadata
                file_metadata = metadata_dict.copy() if metadata_dict else {}
                file_path_obj = Path(path)
                file_metadata.update({
                    "file_type": file_path_obj.suffix.lstrip(".").lower() or "text",
                    "file_size": file_path_obj.stat().st_size,
                })

                result = await local_unified_mediator.ingest_text(
                    content=file_content,
                    collection_name=collection,
                    document_title=file_path_obj.name,
                    metadata=file_metadata
                )

                console.print(
                    f"[bold green]✓ Ingested file (ID: {result['source_document_id']}) "
                    f"with {result['num_chunks']} chunks to collection '{collection}'[/bold green]"
                )
                console.print(f"[dim]Entities extracted: {result.get('entities_extracted', 0)}[/dim]")

            # Fallback: RAG-only mode
            else:
                logger.info(f"Using RAG-only mode for file: {Path(path).name}")
                source_id, chunk_ids = doc_store.ingest_file(path, collection, metadata_dict)
                console.print(
                    f"[bold green]✓ Ingested file (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
                )
                console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())


@ingest.command("directory")
@click.argument("path", type=click.Path(exists=True))
@click.option("--collection", required=True, help="Collection name")
@click.option(
    "--extensions", default=".txt,.md", help="Comma-separated file extensions"
)
@click.option("--recursive", is_flag=True, help="Search subdirectories")
def ingest_directory(path, collection, extensions, recursive):
    """Ingest all files from a directory with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.
    """
    async def run_ingest():
        try:
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

            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = await initialize_graph_components()

            # Ingest each file
            source_ids = []
            total_chunks = 0
            total_entities = 0

            for file_path in files:
                try:
                    # Use unified mediator if available
                    if local_unified_mediator:
                        # Read file content
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            file_content = f.read()

                        # Build file metadata
                        file_metadata = {
                            "file_type": file_path.suffix.lstrip(".").lower() or "text",
                            "file_size": file_path.stat().st_size,
                        }

                        result = await local_unified_mediator.ingest_text(
                            content=file_content,
                            collection_name=collection,
                            document_title=file_path.name,
                            metadata=file_metadata
                        )

                        source_ids.append(result['source_document_id'])
                        total_chunks += result['num_chunks']
                        total_entities += result.get('entities_extracted', 0)
                        console.print(f"  ✓ {file_path.name}: {result['num_chunks']} chunks, {result.get('entities_extracted', 0)} entities")

                    # Fallback: RAG-only mode
                    else:
                        source_id, chunk_ids = doc_store.ingest_file(str(file_path), collection)
                        source_ids.append(source_id)
                        total_chunks += len(chunk_ids)
                        console.print(f"  ✓ {file_path.name}: {len(chunk_ids)} chunks")

                except Exception as e:
                    console.print(f"  ✗ {file_path.name}: {e}")

            console.print(
                f"[bold green]✓ Ingested {len(source_ids)} documents with {total_chunks} total chunks to collection '{collection}'[/bold green]"
            )
            if local_unified_mediator and total_entities > 0:
                console.print(f"[dim]Total entities extracted: {total_entities}[/dim]")
            elif not local_unified_mediator:
                console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())


@ingest.command("url")
@click.argument("url")
@click.option("--collection", required=True, help="Collection name")
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
@click.option("--verbose", is_flag=True, help="Enable verbose crawling output")
@click.option("--chunk-size", type=int, default=2500, help="Chunk size for web pages (default: 2500)")
@click.option("--chunk-overlap", type=int, default=300, help="Chunk overlap (default: 300)")
@click.option("--follow-links", is_flag=True, help="Follow internal links (multi-page crawl)")
@click.option("--max-depth", type=int, default=1, help="Maximum crawl depth when following links (default: 1)")
def ingest_url(url, collection, headless, verbose, chunk_size, chunk_overlap, follow_links, max_depth):
    """Crawl and ingest a web page with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.

    By default, only the specified page is crawled. Use --follow-links to crawl
    linked pages up to --max-depth levels deep.

    Examples:
        # Single page only
        rag ingest url https://example.com --collection docs

        # Follow direct links (depth=1)
        rag ingest url https://example.com --collection docs --follow-links

        # Follow links 2 levels deep
        rag ingest url https://example.com --collection docs --follow-links --max-depth 2
    """
    async def run_ingest():
        try:
            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = await initialize_graph_components()

            if follow_links:
                # Multi-page crawl with link following
                console.print(f"[bold blue]Crawling URL with link following: {url} (max_depth={max_depth})[/bold blue]")

                crawler = WebCrawler(headless=headless, verbose=verbose)
                results = await crawler.crawl_with_depth(url, max_depth=max_depth)

                if not results:
                    console.print(f"[bold red]✗ No pages crawled from {url}[/bold red]")
                    sys.exit(1)

                console.print(f"[green]✓ Crawled {len(results)} pages[/green]")

                # Ingest each page
                total_chunks = 0
                total_entities = 0
                successful_ingests = 0

                for i, result in enumerate(results, 1):
                    if not result.success:
                        console.print(f"  [yellow]⚠ Skipped failed page {i}: {result.url}[/yellow]")
                        continue

                    try:
                        # Use unified mediator if available
                        if local_unified_mediator:
                            ingest_result = await local_unified_mediator.ingest_text(
                                content=result.content,
                                collection_name=collection,
                                document_title=result.metadata.get("title", result.url),
                                metadata=result.metadata
                            )
                            total_chunks += ingest_result['num_chunks']
                            total_entities += ingest_result.get('entities_extracted', 0)
                            successful_ingests += 1
                            console.print(
                                f"  ✓ Page {i}/{len(results)}: {result.metadata.get('title', result.url)[:50]}... "
                                f"({ingest_result['num_chunks']} chunks, {ingest_result.get('entities_extracted', 0)} entities, "
                                f"depth={result.metadata.get('crawl_depth', 0)})"
                            )

                        # Fallback: RAG-only mode
                        else:
                            web_chunking_config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                            web_chunker = get_document_chunker(web_chunking_config)
                            web_doc_store = get_document_store(db, embedder, coll_mgr, chunker=web_chunker)

                            source_id, chunk_ids = web_doc_store.ingest_document(
                                content=result.content,
                                filename=result.metadata.get("title", result.url),
                                collection_name=collection,
                                metadata=result.metadata,
                                file_type="web_page",
                            )
                            total_chunks += len(chunk_ids)
                            successful_ingests += 1
                            console.print(
                                f"  ✓ Page {i}/{len(results)}: {result.metadata.get('title', result.url)[:50]}... "
                                f"({len(chunk_ids)} chunks, depth={result.metadata.get('crawl_depth', 0)})"
                            )

                    except Exception as e:
                        console.print(f"  [red]✗ Failed to ingest page {i}: {e}[/red]")

                console.print(
                    f"\n[bold green]✓ Ingested {successful_ingests} pages with {total_chunks} total chunks "
                    f"to collection '{collection}'[/bold green]"
                )
                if local_unified_mediator and total_entities > 0:
                    console.print(f"[dim]Total entities extracted: {total_entities}[/dim]")
                elif not local_unified_mediator:
                    console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")
                console.print(f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]")

            else:
                # Single-page crawl
                console.print(f"[bold blue]Crawling URL: {url}[/bold blue]")

                # Crawl the page
                result = await crawl_single_page(url, headless=headless, verbose=verbose)

                if not result.success:
                    console.print(f"[bold red]✗ Failed to crawl {url}[/bold red]")
                    if result.error:
                        console.print(f"[bold red]Error: {result.error.error_message}[/bold red]")
                    sys.exit(1)

                console.print(f"[green]✓ Successfully crawled page ({len(result.content)} chars)[/green]")

                # Use unified mediator if available
                if local_unified_mediator:
                    ingest_result = await local_unified_mediator.ingest_text(
                        content=result.content,
                        collection_name=collection,
                        document_title=result.metadata.get("title", url),
                        metadata=result.metadata
                    )

                    console.print(
                        f"[bold green]✓ Ingested web page (ID: {ingest_result['source_document_id']}) "
                        f"with {ingest_result['num_chunks']} chunks to collection '{collection}'[/bold green]"
                    )
                    console.print(f"[dim]Entities extracted: {ingest_result.get('entities_extracted', 0)}[/dim]")
                    console.print(f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]")
                    console.print(f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]")

                # Fallback: RAG-only mode
                else:
                    web_chunking_config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                    web_chunker = get_document_chunker(web_chunking_config)
                    web_doc_store = get_document_store(db, embedder, coll_mgr, chunker=web_chunker)

                    source_id, chunk_ids = web_doc_store.ingest_document(
                        content=result.content,
                        filename=result.metadata.get("title", url),
                        collection_name=collection,
                        metadata=result.metadata,
                        file_type="web_page",
                    )

                    console.print(
                        f"[bold green]✓ Ingested web page (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
                    )
                    console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")
                    console.print(f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]")
                    console.print(f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]")
                    console.print(f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]")

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())


@main.command()
@click.argument("url")
@click.option("--collection", required=True, help="Collection name")
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
@click.option("--verbose", is_flag=True, help="Enable verbose crawling output")
@click.option("--chunk-size", type=int, default=2500, help="Chunk size for web pages (default: 2500)")
@click.option("--chunk-overlap", type=int, default=300, help="Chunk overlap (default: 300)")
@click.option("--follow-links", is_flag=True, help="Follow internal links (multi-page crawl)")
@click.option("--max-depth", type=int, default=1, help="Maximum crawl depth when following links (default: 1)")
def recrawl(url, collection, headless, verbose, chunk_size, chunk_overlap, follow_links, max_depth):
    """Re-crawl a URL by deleting old pages and re-ingesting.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.

    This command finds all source documents where metadata.crawl_root_url matches
    the specified URL, deletes those documents and their chunks, then re-crawls
    and re-ingests the content. Other documents in the collection are unaffected.

    Examples:
        # Re-crawl single page
        rag recrawl https://example.com --collection docs

        # Re-crawl with link following
        rag recrawl https://example.com --collection docs --follow-links --max-depth 2
    """
    async def run_recrawl():
        try:
            console.print(f"[bold blue]Re-crawling: {url}[/bold blue]")
            console.print(f"[dim]Finding existing documents with crawl_root_url = {url}...[/dim]")

            # Step 1: Find all source documents with matching crawl_root_url
            conn = db.connect()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename, metadata
                    FROM source_documents
                    WHERE metadata->>'crawl_root_url' = %s
                    """,
                    (url,)
                )
                existing_docs = cur.fetchall()

            if not existing_docs:
                console.print(f"[yellow]No existing documents found with crawl_root_url = {url}[/yellow]")
                console.print("[dim]Proceeding with fresh crawl...[/dim]")
                old_doc_count = 0
            else:
                old_doc_count = len(existing_docs)
                console.print(f"[yellow]Found {old_doc_count} existing documents to delete[/yellow]")

                # Step 2: Delete the old documents and their chunks
                # Note: Using direct database access here for RAG cleanup
                # TODO (Phase 4): Also delete corresponding Graph episodes
                web_chunking_config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                web_chunker = get_document_chunker(web_chunking_config)
                web_doc_store = get_document_store(db, embedder, coll_mgr, chunker=web_chunker)

                for doc_id, filename, metadata in existing_docs:
                    try:
                        # Get chunk count before deletion
                        chunks = web_doc_store.get_document_chunks(doc_id)
                        chunk_count = len(chunks)

                        # Delete the document (cascades to chunks and chunk_collections)
                        with conn.cursor() as cur:
                            # Delete chunks first
                            cur.execute(
                                "DELETE FROM document_chunks WHERE source_document_id = %s",
                                (doc_id,)
                            )
                            # Delete source document
                            cur.execute(
                                "DELETE FROM source_documents WHERE id = %s",
                                (doc_id,)
                            )

                        console.print(f"  [dim]✓ Deleted document {doc_id}: {filename} ({chunk_count} chunks)[/dim]")
                    except Exception as e:
                        console.print(f"  [red]✗ Failed to delete document {doc_id}: {e}[/red]")

            console.print(f"\n[bold blue]Starting crawl...[/bold blue]")

            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = await initialize_graph_components()

            # Step 3: Perform the crawl
            if follow_links:
                # Multi-page crawl with link following
                console.print(f"[dim]Crawling with link following (max_depth={max_depth})...[/dim]")

                crawler = WebCrawler(headless=headless, verbose=verbose)
                results = await crawler.crawl_with_depth(url, max_depth=max_depth)

                if not results:
                    console.print(f"[bold red]✗ No pages crawled from {url}[/bold red]")
                    sys.exit(1)

                console.print(f"[green]✓ Crawled {len(results)} pages[/green]")

                # Ingest each page
                total_chunks = 0
                total_entities = 0
                successful_ingests = 0

                for i, result in enumerate(results, 1):
                    if not result.success:
                        console.print(f"  [yellow]⚠ Skipped failed page {i}: {result.url}[/yellow]")
                        continue

                    try:
                        # Use unified mediator if available
                        if local_unified_mediator:
                            ingest_result = await local_unified_mediator.ingest_text(
                                content=result.content,
                                collection_name=collection,
                                document_title=result.metadata.get("title", result.url),
                                metadata=result.metadata
                            )
                            total_chunks += ingest_result['num_chunks']
                            total_entities += ingest_result.get('entities_extracted', 0)
                            successful_ingests += 1
                            console.print(
                                f"  ✓ Page {i}/{len(results)}: {result.metadata.get('title', result.url)[:50]}... "
                                f"({ingest_result['num_chunks']} chunks, {ingest_result.get('entities_extracted', 0)} entities, "
                                f"depth={result.metadata.get('crawl_depth', 0)})"
                            )

                        # Fallback: RAG-only mode
                        else:
                            web_chunking_config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                            web_chunker = get_document_chunker(web_chunking_config)
                            web_doc_store = get_document_store(db, embedder, coll_mgr, chunker=web_chunker)

                            source_id, chunk_ids = web_doc_store.ingest_document(
                                content=result.content,
                                filename=result.metadata.get("title", result.url),
                                collection_name=collection,
                                metadata=result.metadata,
                                file_type="web_page",
                            )
                            total_chunks += len(chunk_ids)
                            successful_ingests += 1
                            console.print(
                                f"  ✓ Page {i}/{len(results)}: {result.metadata.get('title', result.url)[:50]}... "
                                f"({len(chunk_ids)} chunks, depth={result.metadata.get('crawl_depth', 0)})"
                            )

                    except Exception as e:
                        console.print(f"  [red]✗ Failed to ingest page {i}: {e}[/red]")

                console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                console.print(f"[bold]Deleted {old_doc_count} old pages, crawled {successful_ingests} new pages with {total_chunks} total chunks[/bold]")
                console.print(f"[dim]Collection: '{collection}'[/dim]")
                if local_unified_mediator and total_entities > 0:
                    console.print(f"[dim]Total entities extracted: {total_entities}[/dim]")
                elif not local_unified_mediator:
                    console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")
                console.print(f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]")

            else:
                # Single-page crawl
                console.print(f"[dim]Crawling single page...[/dim]")

                result = await crawl_single_page(url, headless=headless, verbose=verbose)

                if not result.success:
                    console.print(f"[bold red]✗ Failed to crawl {url}[/bold red]")
                    if result.error:
                        console.print(f"[bold red]Error: {result.error.error_message}[/bold red]")
                    sys.exit(1)

                console.print(f"[green]✓ Successfully crawled page ({len(result.content)} chars)[/green]")

                # Use unified mediator if available
                if local_unified_mediator:
                    ingest_result = await local_unified_mediator.ingest_text(
                        content=result.content,
                        collection_name=collection,
                        document_title=result.metadata.get("title", url),
                        metadata=result.metadata
                    )

                    console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                    console.print(f"[bold]Deleted {old_doc_count} old pages, crawled 1 new page with {ingest_result['num_chunks']} chunks[/bold]")
                    console.print(f"[dim]Collection: '{collection}'[/dim]")
                    console.print(f"[dim]Entities extracted: {ingest_result.get('entities_extracted', 0)}[/dim]")
                    console.print(f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]")
                    console.print(f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]")

                # Fallback: RAG-only mode
                else:
                    web_chunking_config = ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                    web_chunker = get_document_chunker(web_chunking_config)
                    web_doc_store = get_document_store(db, embedder, coll_mgr, chunker=web_chunker)

                    source_id, chunk_ids = web_doc_store.ingest_document(
                        content=result.content,
                        filename=result.metadata.get("title", url),
                        collection_name=collection,
                        metadata=result.metadata,
                        file_type="web_page",
                    )

                    console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                    console.print(f"[bold]Deleted {old_doc_count} old pages, crawled 1 new page with {len(chunk_ids)} chunks[/bold]")
                    console.print(f"[dim]Collection: '{collection}'[/dim]")
                    console.print("[dim]Knowledge Graph not available - RAG-only mode[/dim]")
                    console.print(f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]")
                    console.print(f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]")
                    console.print(f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]")

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_recrawl())


@main.command()
@click.argument("query")
@click.option("--collection", help="Search within specific collection")
@click.option("--limit", default=10, help="Maximum number of results")
@click.option("--threshold", type=float, help="Minimum similarity score (0-1)")
@click.option("--metadata", help="Filter by metadata (JSON string)")
@click.option("--verbose", is_flag=True, help="Show full chunk content")
@click.option("--show-source", is_flag=True, help="Include full source document content")
@click.option("--hybrid", is_flag=True, help="Use hybrid search (vector + keyword with RRF)")
@click.option("--multi-query", is_flag=True, help="Use multi-query retrieval (query expansion + RRF)")
def search(query, collection, limit, threshold, metadata, verbose, show_source, hybrid, multi_query):
    """Search for similar document chunks."""
    try:
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)

        # Check for conflicting flags
        if hybrid and multi_query:
            console.print("[bold red]Error: Cannot use both --hybrid and --multi-query flags[/bold red]")
            sys.exit(1)

        # Choose search method
        if multi_query:
            searcher = get_multi_query_search(db, embedder, coll_mgr)
            search_method = "multi-query (query expansion + RRF)"
        elif hybrid:
            searcher = get_hybrid_search(db, embedder, coll_mgr)
            search_method = "hybrid (vector + keyword with RRF)"
        else:
            searcher = get_similarity_search(db, embedder, coll_mgr)
            search_method = "vector-only"

        # Parse metadata filter if provided
        metadata_filter = None
        if metadata:
            try:
                metadata_filter = json.loads(metadata)
            except json.JSONDecodeError as e:
                console.print(f"[bold red]Invalid JSON in metadata filter: {e}[/bold red]")
                sys.exit(1)

        console.print(f"[bold blue]Searching for: {query}[/bold blue]")
        console.print(f"[dim]Method: {search_method}[/dim]")
        if metadata_filter:
            console.print(f"[dim]Metadata filter: {metadata_filter}[/dim]")

        # Execute search based on method
        if multi_query:
            results = searcher.multi_query_search(
                query=query,
                limit=limit,
                collection_name=collection,
                metadata_filter=metadata_filter,
                include_source=show_source
            )
        elif hybrid:
            results = searcher.hybrid_search(
                query=query,
                limit=limit,
                collection_name=collection,
                metadata_filter=metadata_filter,
                include_source=show_source
            )
        else:
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


if __name__ == "__main__":
    main()
