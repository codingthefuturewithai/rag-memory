#!/usr/bin/env python3
"""
RAG Memory - Automated Migration to Render

This script automates the migration of your local Docker-based RAG Memory
deployment to Render cloud services (PostgreSQL + Neo4j + MCP Server).

Features:
- Detects local Docker data automatically
- Asks user: migrate data or start fresh
- Fully automated PostgreSQL migration
- Fully automated Neo4j migration (Python driver-based)
- Interactive credential prompts
- Data integrity verification
- Keeps local data safe until confirmed

Usage:
    python scripts/migrate_to_render.py
    # OR
    uv run python scripts/migrate_to_render.py
"""

import os
import sys
import subprocess
import getpass
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, List
import json

try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
except ImportError:
    print("ERROR: 'rich' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich import print as rprint

try:
    from neo4j import GraphDatabase
except ImportError:
    print("ERROR: 'neo4j' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "neo4j"])
    from neo4j import GraphDatabase

try:
    import psycopg
except ImportError:
    print("ERROR: 'psycopg' library not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg[binary]"])
    import psycopg

console = Console()

# ============================================================================
# Configuration
# ============================================================================

LOCAL_POSTGRES_CONTAINER = "rag-memory-postgres-local"
LOCAL_NEO4J_CONTAINER = "rag-memory-neo4j-local"
LOCAL_POSTGRES_USER = "raguser"
LOCAL_POSTGRES_DB = "rag_memory"
LOCAL_NEO4J_USER = "neo4j"

# ============================================================================
# Phase 0: Detect Local Data
# ============================================================================

def check_docker_running() -> bool:
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_container_exists(container_name: str) -> bool:
    """Check if a specific Docker container exists and is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False
        )
        return container_name in result.stdout
    except Exception:
        return False


def get_local_postgres_counts() -> Optional[Dict[str, int]]:
    """Get document/chunk counts from local PostgreSQL."""
    try:
        result = subprocess.run(
            [
                "docker", "exec", LOCAL_POSTGRES_CONTAINER,
                "psql", "-U", LOCAL_POSTGRES_USER, "-d", LOCAL_POSTGRES_DB,
                "-t", "-c",
                "SELECT COUNT(*) FROM source_documents; SELECT COUNT(*) FROM document_chunks;"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        if len(lines) >= 2:
            return {
                "documents": int(lines[0]),
                "chunks": int(lines[1])
            }
    except Exception as e:
        console.print(f"[yellow]Warning: Could not get PostgreSQL counts: {e}[/yellow]")

    return None


def get_local_neo4j_counts() -> Optional[Dict[str, int]]:
    """Get node/relationship counts from local Neo4j."""
    try:
        # Get Neo4j password from environment or use default
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        result = subprocess.run(
            [
                "docker", "exec", LOCAL_NEO4J_CONTAINER,
                "cypher-shell", "-u", LOCAL_NEO4J_USER, "-p", neo4j_password,
                "MATCH (n) RETURN count(n) as nodes; MATCH ()-[r]->() RETURN count(r) as relationships;"
            ],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse output (cypher-shell returns formatted table)
        lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip() and not line.startswith("+") and not line.startswith("|")]

        # Extract numbers from lines
        nodes = 0
        relationships = 0
        for line in lines:
            if line.isdigit():
                if nodes == 0:
                    nodes = int(line)
                else:
                    relationships = int(line)
                    break

        return {
            "nodes": nodes,
            "relationships": relationships
        }
    except Exception as e:
        console.print(f"[yellow]Warning: Could not get Neo4j counts: {e}[/yellow]")

    return None


def detect_local_data() -> Tuple[bool, Optional[Dict], Optional[Dict]]:
    """
    Detect if local Docker containers have data.

    Returns:
        (has_data, postgres_counts, neo4j_counts)
    """
    console.print("\n[bold cyan]🔍 Detecting local Docker deployment...[/bold cyan]")

    if not check_docker_running():
        console.print("[yellow]⚠️  Docker is not running[/yellow]")
        return False, None, None

    postgres_exists = check_container_exists(LOCAL_POSTGRES_CONTAINER)
    neo4j_exists = check_container_exists(LOCAL_NEO4J_CONTAINER)

    if not postgres_exists and not neo4j_exists:
        console.print("[yellow]⚠️  No local RAG Memory containers found[/yellow]")
        return False, None, None

    console.print(f"[green]✓[/green] PostgreSQL container: {'Running' if postgres_exists else 'Not found'}")
    console.print(f"[green]✓[/green] Neo4j container: {'Running' if neo4j_exists else 'Not found'}")

    # Get data counts
    pg_counts = get_local_postgres_counts() if postgres_exists else None
    neo4j_counts = get_local_neo4j_counts() if neo4j_exists else None

    if pg_counts:
        console.print(f"[cyan]  → PostgreSQL: {pg_counts['documents']} documents, {pg_counts['chunks']} chunks[/cyan]")
    if neo4j_counts:
        console.print(f"[cyan]  → Neo4j: {neo4j_counts['nodes']} nodes, {neo4j_counts['relationships']} relationships[/cyan]")

    # Has data if either database has content
    has_data = (pg_counts and pg_counts['documents'] > 0) or (neo4j_counts and neo4j_counts['nodes'] > 0)

    return has_data, pg_counts, neo4j_counts


# ============================================================================
# Phase 1: Pre-flight Checks
# ============================================================================

def check_prerequisites() -> bool:
    """Check that required tools are installed."""
    console.print("\n[bold cyan]🔧 Checking prerequisites...[/bold cyan]")

    checks = {
        "docker": ["docker", "--version"],
        "psql": ["psql", "--version"],
    }

    all_good = True
    for tool, command in checks.items():
        try:
            subprocess.run(command, capture_output=True, check=True)
            console.print(f"[green]✓[/green] {tool} installed")
        except (FileNotFoundError, subprocess.CalledProcessError):
            console.print(f"[red]✗[/red] {tool} not found")
            all_good = False

    # Check Python libraries (already imported, so just verify)
    console.print(f"[green]✓[/green] neo4j Python driver installed")
    console.print(f"[green]✓[/green] psycopg Python library installed")
    console.print(f"[green]✓[/green] rich Python library installed")

    return all_good


# ============================================================================
# Phase 2: Gather Render Credentials
# ============================================================================

def gather_credentials() -> Dict[str, str]:
    """Interactively gather Render service credentials."""
    console.print("\n[bold cyan]🔐 Enter your Render service credentials[/bold cyan]")
    console.print("[dim]These can be found in your Render dashboard for each service[/dim]\n")

    credentials = {}

    # PostgreSQL
    console.print("[bold]PostgreSQL (Render managed database):[/bold]")
    credentials["pg_url"] = Prompt.ask(
        "  External Database URL",
        default=os.getenv("RENDER_DATABASE_URL", "")
    )

    # Neo4j
    console.print("\n[bold]Neo4j (Render Docker service):[/bold]")
    credentials["neo4j_uri"] = Prompt.ask(
        "  Connection URI",
        default=os.getenv("RENDER_NEO4J_URI", "neo4j://...onrender.com:7687")
    )
    credentials["neo4j_user"] = Prompt.ask(
        "  Username",
        default="neo4j"
    )
    credentials["neo4j_password"] = getpass.getpass("  Password: ")

    return credentials


# ============================================================================
# Phase 3: Test Render Connectivity
# ============================================================================

def test_postgres_connection(database_url: str) -> bool:
    """Test connection to Render PostgreSQL."""
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception as e:
        console.print(f"[red]✗ PostgreSQL connection failed: {e}[/red]")
        return False


def test_neo4j_connection(uri: str, user: str, password: str) -> bool:
    """Test connection to Render Neo4j."""
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        driver.close()
        return True
    except Exception as e:
        console.print(f"[red]✗ Neo4j connection failed: {e}[/red]")
        return False


def test_render_connectivity(credentials: Dict[str, str]) -> bool:
    """Test connectivity to all Render services."""
    console.print("\n[bold cyan]🌐 Testing Render connectivity...[/bold cyan]")

    pg_ok = test_postgres_connection(credentials["pg_url"])
    console.print(f"[{'green' if pg_ok else 'red'}]{'✓' if pg_ok else '✗'}[/] PostgreSQL")

    neo4j_ok = test_neo4j_connection(
        credentials["neo4j_uri"],
        credentials["neo4j_user"],
        credentials["neo4j_password"]
    )
    console.print(f"[{'green' if neo4j_ok else 'red'}]{'✓' if neo4j_ok else '✗'}[/] Neo4j")

    return pg_ok and neo4j_ok


# ============================================================================
# Phase 4: Dry Run Preview
# ============================================================================

def show_migration_preview(pg_counts: Dict, neo4j_counts: Dict):
    """Show what will be migrated."""
    console.print("\n[bold cyan]📋 Migration Preview[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Database", style="dim")
    table.add_column("What will be migrated")
    table.add_column("Count", justify="right")

    table.add_row(
        "PostgreSQL",
        "Documents",
        str(pg_counts.get("documents", 0))
    )
    table.add_row(
        "",
        "Chunks",
        str(pg_counts.get("chunks", 0))
    )
    table.add_row(
        "Neo4j",
        "Nodes",
        str(neo4j_counts.get("nodes", 0))
    )
    table.add_row(
        "",
        "Relationships",
        str(neo4j_counts.get("relationships", 0))
    )

    console.print(table)
    console.print("\n[dim]Your local data will remain intact until you confirm success.[/dim]")


# ============================================================================
# Phase 5: Export from Local
# ============================================================================

def create_backup_directory() -> Path:
    """Create timestamped backup directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("backups") / f"migration_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def export_postgres(backup_dir: Path) -> Path:
    """Export PostgreSQL database using pg_dump."""
    console.print("\n[bold cyan]📦 Exporting PostgreSQL...[/bold cyan]")

    backup_file = backup_dir / "postgres_backup.sql"

    try:
        cmd = [
            "docker", "exec", LOCAL_POSTGRES_CONTAINER,
            "pg_dump",
            "-U", LOCAL_POSTGRES_USER,
            "-d", LOCAL_POSTGRES_DB,
            "--clean",
            "--if-exists"
        ]

        with open(backup_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True, text=True)

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] PostgreSQL exported ({size_mb:.2f} MB)")
        return backup_file
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
        raise


def export_neo4j(backup_dir: Path, neo4j_password: str) -> Path:
    """Export Neo4j database using Python driver."""
    console.print("\n[bold cyan]📦 Exporting Neo4j...[/bold cyan]")

    backup_file = backup_dir / "neo4j_backup.json"

    try:
        # Connect to local Neo4j
        driver = GraphDatabase.driver(
            f"bolt://localhost:{os.getenv('PROD_NEO4J_BOLT_PORT', '7687')}",
            auth=(LOCAL_NEO4J_USER, neo4j_password)
        )

        nodes = []
        relationships = []

        with driver.session() as session:
            # Export all nodes
            console.print("  → Exporting nodes...")
            result = session.run("MATCH (n) RETURN n")
            for record in result:
                node = record["n"]
                nodes.append({
                    "id": node.id,
                    "labels": list(node.labels),
                    "properties": dict(node)
                })

            # Export all relationships
            console.print("  → Exporting relationships...")
            result = session.run("MATCH ()-[r]->() RETURN r, startNode(r) as start, endNode(r) as end")
            for record in result:
                rel = record["r"]
                start = record["start"]
                end = record["end"]
                relationships.append({
                    "id": rel.id,
                    "type": rel.type,
                    "properties": dict(rel),
                    "start_id": start.id,
                    "end_id": end.id
                })

        driver.close()

        # Save to JSON
        data = {
            "nodes": nodes,
            "relationships": relationships
        }

        with open(backup_file, "w") as f:
            json.dump(data, f, indent=2)

        size_mb = backup_file.stat().st_size / (1024 * 1024)
        console.print(f"[green]✓[/green] Neo4j exported: {len(nodes)} nodes, {len(relationships)} relationships ({size_mb:.2f} MB)")
        return backup_file
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")
        raise


# ============================================================================
# Phase 6: Import to Render
# ============================================================================

def import_postgres(backup_file: Path, database_url: str):
    """Import PostgreSQL backup to Render."""
    console.print("\n[bold cyan]📤 Importing PostgreSQL to Render...[/bold cyan]")

    try:
        # First, enable pgvector extension
        console.print("  → Enabling pgvector extension...")
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
        console.print("[green]  ✓ pgvector enabled[/green]")

        # Import SQL dump
        console.print("  → Importing data (this may take a few minutes)...")
        cmd = ["psql", database_url, "--single-transaction"]

        with open(backup_file, "r") as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                check=False
            )

        if result.returncode != 0:
            # Check if errors are just warnings about existing objects
            if "already exists" in result.stderr:
                console.print("[yellow]  ⚠ Some objects already existed (expected)[/yellow]")
            else:
                console.print(f"[red]✗ Import failed:\n{result.stderr}[/red]")
                raise Exception("PostgreSQL import failed")

        console.print("[green]✓[/green] PostgreSQL imported successfully")
    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        raise


def import_neo4j(backup_file: Path, uri: str, user: str, password: str):
    """Import Neo4j backup to Render using Python driver."""
    console.print("\n[bold cyan]📤 Importing Neo4j to Render...[/bold cyan]")

    try:
        # Load backup data
        with open(backup_file, "r") as f:
            data = json.load(f)

        nodes = data["nodes"]
        relationships = data["relationships"]

        driver = GraphDatabase.driver(uri, auth=(user, password))

        # Create id mapping (old id -> new id)
        id_mapping = {}

        with console.status("[bold green]Importing nodes...") as status:
            with driver.session() as session:
                # Import nodes in batches
                batch_size = 100
                for i in range(0, len(nodes), batch_size):
                    batch = nodes[i:i+batch_size]

                    for node in batch:
                        labels_str = ":".join(node["labels"]) if node["labels"] else ""

                        # Create node
                        cypher = f"CREATE (n:{labels_str}) SET n = $properties RETURN id(n) as new_id"
                        result = session.run(cypher, properties=node["properties"])
                        new_id = result.single()["new_id"]
                        id_mapping[node["id"]] = new_id

                    progress = min(i + batch_size, len(nodes))
                    status.update(f"[bold green]Importing nodes... {progress}/{len(nodes)}")

        console.print(f"[green]✓[/green] Imported {len(nodes)} nodes")

        with console.status("[bold green]Importing relationships...") as status:
            with driver.session() as session:
                # Import relationships in batches
                for i in range(0, len(relationships), batch_size):
                    batch = relationships[i:i+batch_size]

                    for rel in batch:
                        start_new_id = id_mapping.get(rel["start_id"])
                        end_new_id = id_mapping.get(rel["end_id"])

                        if start_new_id is None or end_new_id is None:
                            console.print(f"[yellow]⚠ Skipping relationship {rel['id']} (missing node)[/yellow]")
                            continue

                        # Create relationship
                        cypher = f"""
                        MATCH (start) WHERE id(start) = $start_id
                        MATCH (end) WHERE id(end) = $end_id
                        CREATE (start)-[r:{rel['type']}]->(end)
                        SET r = $properties
                        """
                        session.run(
                            cypher,
                            start_id=start_new_id,
                            end_id=end_new_id,
                            properties=rel["properties"]
                        )

                    progress = min(i + batch_size, len(relationships))
                    status.update(f"[bold green]Importing relationships... {progress}/{len(relationships)}")

        driver.close()
        console.print(f"[green]✓[/green] Imported {len(relationships)} relationships")
    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        raise


# ============================================================================
# Phase 7: Verification
# ============================================================================

def verify_postgres(database_url: str, expected_counts: Dict) -> bool:
    """Verify PostgreSQL data was imported correctly."""
    console.print("\n[bold cyan]🔍 Verifying PostgreSQL...[/bold cyan]")

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM source_documents")
                doc_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM document_chunks")
                chunk_count = cur.fetchone()[0]

        docs_match = doc_count == expected_counts.get("documents", 0)
        chunks_match = chunk_count == expected_counts.get("chunks", 0)

        console.print(f"  Documents: {doc_count} (expected {expected_counts.get('documents', 0)}) [{'green' if docs_match else 'red'}]{'✓' if docs_match else '✗'}[/]")
        console.print(f"  Chunks: {chunk_count} (expected {expected_counts.get('chunks', 0)}) [{'green' if chunks_match else 'red'}]{'✓' if chunks_match else '✗'}[/]")

        return docs_match and chunks_match
    except Exception as e:
        console.print(f"[red]✗ Verification failed: {e}[/red]")
        return False


def verify_neo4j(uri: str, user: str, password: str, expected_counts: Dict) -> bool:
    """Verify Neo4j data was imported correctly."""
    console.print("\n[bold cyan]🔍 Verifying Neo4j...[/bold cyan]")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]

            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]

        driver.close()

        nodes_match = node_count == expected_counts.get("nodes", 0)
        rels_match = rel_count == expected_counts.get("relationships", 0)

        console.print(f"  Nodes: {node_count} (expected {expected_counts.get('nodes', 0)}) [{'green' if nodes_match else 'red'}]{'✓' if nodes_match else '✗'}[/]")
        console.print(f"  Relationships: {rel_count} (expected {expected_counts.get('relationships', 0)}) [{'green' if rels_match else 'red'}]{'✓' if rels_match else '✗'}[/]")

        return nodes_match and rels_match
    except Exception as e:
        console.print(f"[red]✗ Verification failed: {e}[/red]")
        return False


# ============================================================================
# Phase 8: Next Steps
# ============================================================================

def show_next_steps():
    """Show user what to do next."""
    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold green]✅ Migration Complete![/bold green]\n\n"
        "[bold]Next Steps:[/bold]\n"
        "1. Test your Render deployment (run some searches, list collections)\n"
        "2. Verify data looks correct in Render dashboard\n"
        "3. Once confirmed, you can stop local Docker:\n"
        "   [cyan]docker stop rag-memory-postgres-local rag-memory-neo4j-local[/cyan]\n\n"
        "[yellow]⚠️  Your local data is kept safe until you manually stop Docker containers.[/yellow]",
        title="🎉 Success",
        border_style="green"
    ))


# ============================================================================
# Main Script
# ============================================================================

def main():
    """Main migration workflow."""
    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold cyan]RAG Memory - Cloud Migration Tool[/bold cyan]\n\n"
        "This tool will migrate your local Docker deployment to Render.\n"
        "Your local data will remain intact throughout the process.",
        border_style="cyan"
    ))

    # Phase 0: Detect local data
    has_data, pg_counts, neo4j_counts = detect_local_data()

    # Ask user: migrate or fresh start?
    migrate_data = False
    if has_data:
        console.print("\n[bold yellow]📊 Local data detected![/bold yellow]")
        migrate_data = Confirm.ask(
            "\nDo you want to migrate your local data to Render?",
            default=True
        )

        if not migrate_data:
            console.print("[yellow]Skipping migration. Proceeding with fresh deployment.[/yellow]")
    else:
        console.print("\n[dim]No local data found. Proceeding with fresh deployment.[/dim]")

    # Phase 1: Pre-flight checks (if migrating)
    if migrate_data and not check_prerequisites():
        console.print("\n[red]✗ Prerequisites check failed. Please install missing tools.[/red]")
        sys.exit(1)

    # Phase 2: Gather credentials
    credentials = gather_credentials()

    # Phase 3: Test connectivity
    if not test_render_connectivity(credentials):
        console.print("\n[red]✗ Cannot connect to Render services. Please check your credentials.[/red]")
        sys.exit(1)

    if migrate_data:
        # Phase 4: Preview
        show_migration_preview(pg_counts or {}, neo4j_counts or {})

        if not Confirm.ask("\nProceed with migration?", default=True):
            console.print("[yellow]Migration cancelled.[/yellow]")
            sys.exit(0)

        # Phase 5: Export
        backup_dir = create_backup_directory()
        console.print(f"\n[dim]Backup directory: {backup_dir}[/dim]")

        pg_backup = export_postgres(backup_dir)
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")
        neo4j_backup = export_neo4j(backup_dir, neo4j_password)

        # Phase 6: Import
        import_postgres(pg_backup, credentials["pg_url"])
        import_neo4j(
            neo4j_backup,
            credentials["neo4j_uri"],
            credentials["neo4j_user"],
            credentials["neo4j_password"]
        )

        # Phase 7: Verify
        pg_ok = verify_postgres(credentials["pg_url"], pg_counts or {})
        neo4j_ok = verify_neo4j(
            credentials["neo4j_uri"],
            credentials["neo4j_user"],
            credentials["neo4j_password"],
            neo4j_counts or {}
        )

        if not (pg_ok and neo4j_ok):
            console.print("\n[red]⚠️  Verification failed! Please check the errors above.[/red]")
            console.print("[yellow]Your local data is still intact. You can retry the migration.[/yellow]")
            sys.exit(1)
    else:
        # Fresh deployment - just verify connectivity
        console.print("\n[green]✓[/green] Render services are ready for fresh deployment")
        console.print("\n[bold]Next:[/bold] Deploy your MCP server and start using Render!")

    # Phase 8: Success
    if migrate_data:
        show_next_steps()
    else:
        console.print("\n[green]✓[/green] Ready to deploy! Your Render services are connected and waiting.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Migration cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
