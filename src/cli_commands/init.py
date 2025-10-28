"""Database initialization command."""

import asyncio
import sys
import click
from rich.console import Console

console = Console()


@click.command(name='init')
def init_command():
    """Initialize database schemas for PostgreSQL and Neo4j.

    This command is idempotent and safe to run multiple times.

    What it does:
    - Verifies PostgreSQL schema exists (usually auto-created by Docker)
    - Initializes Neo4j indices and constraints via Graphiti
    - Safe to re-run after Graphiti version upgrades

    Examples:
        rag init                    # Initialize both databases
        python scripts/setup.py     # Calls this automatically
    """
    asyncio.run(init_databases())


async def init_databases():
    """Initialize both PostgreSQL and Neo4j schemas."""
    console.print("[bold blue]RAG Memory - Database Initialization[/bold blue]\n")

    # Step 1: Initialize PostgreSQL
    console.print("[bold]1. Checking PostgreSQL schema...[/bold]")
    if not await init_postgresql():
        console.print("[bold red]✗ PostgreSQL initialization failed[/bold red]")
        sys.exit(1)

    # Step 2: Initialize Neo4j
    console.print("\n[bold]2. Initializing Neo4j indices and constraints...[/bold]")
    if not await init_neo4j():
        console.print("[bold red]✗ Neo4j initialization failed[/bold red]")
        sys.exit(1)

    console.print("\n[bold green]✓ Database initialization complete![/bold green]")
    console.print("[dim]Both PostgreSQL and Neo4j are ready to use.[/dim]")


async def init_postgresql():
    """Verify PostgreSQL schema exists (idempotent check)."""
    try:
        from src.core.database import get_database

        db = get_database()

        # Test connection
        if not db.test_connection():
            console.print("[bold red]  ✗ PostgreSQL connection failed[/bold red]")
            console.print("[yellow]  Make sure PostgreSQL is running (docker-compose up -d)[/yellow]")
            return False

        console.print("[green]  ✓ PostgreSQL connection successful[/green]")

        # Check if schema exists (idempotent - safe if already initialized)
        if db.initialize_schema():
            console.print("[green]  ✓ PostgreSQL schema verified[/green]")
        else:
            console.print("[yellow]  ⚠ Schema verification returned False[/yellow]")
            console.print("[yellow]    This is expected if Docker auto-initialized the schema[/yellow]")

        return True

    except Exception as e:
        console.print(f"[bold red]  ✗ PostgreSQL error: {e}[/bold red]")
        return False


async def init_neo4j():
    """Initialize Neo4j indices and constraints via Graphiti (idempotent)."""
    try:
        import os
        from graphiti_core import Graphiti
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient

        # Read Neo4j connection details from environment
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            console.print("[bold red]  ✗ OPENAI_API_KEY not found in environment[/bold red]")
            console.print("[yellow]    Neo4j initialization requires OpenAI API key[/yellow]")
            return False

        # Read optional Graphiti LLM model configuration from environment
        graphiti_model = os.getenv("GRAPHITI_MODEL")
        graphiti_small_model = os.getenv("GRAPHITI_SMALL_MODEL")

        # Create LLM client with optional model overrides
        llm_config_kwargs = {
            'api_key': openai_api_key
        }
        if graphiti_model:
            llm_config_kwargs['model'] = graphiti_model
        if graphiti_small_model:
            llm_config_kwargs['small_model'] = graphiti_small_model

        llm_config = LLMConfig(**llm_config_kwargs)
        llm_client = OpenAIClient(llm_config)

        # Initialize Graphiti
        graphiti = Graphiti(neo4j_uri, neo4j_user, neo4j_password, llm_client)

        console.print(f"[dim]  Connecting to Neo4j at {neo4j_uri}...[/dim]")

        # Build indices and constraints (idempotent - safe to run multiple times)
        # This creates:
        # - Vector indices for name_embedding (entity similarity search)
        # - Fulltext indices for entity search
        # - Range indices for temporal queries
        # - Constraints for data integrity
        await graphiti.build_indices_and_constraints(delete_existing=False)

        console.print("[green]  ✓ Neo4j indices and constraints initialized[/green]")
        console.print("[dim]    Schema includes: entity embeddings, temporal indices, constraints[/dim]")

        return True

    except ImportError:
        console.print("[bold red]  ✗ Graphiti not installed (pip install graphiti-core)[/bold red]")
        return False
    except Exception as e:
        console.print(f"[bold red]  ✗ Neo4j initialization error: {e}[/bold red]")
        console.print("[yellow]    Make sure Neo4j is running and credentials are correct[/yellow]")
        return False
