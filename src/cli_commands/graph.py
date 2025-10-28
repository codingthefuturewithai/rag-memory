"""Knowledge graph query commands."""

import asyncio
import logging
import os
import sys
import time

import click
from rich.console import Console

from src.unified import GraphStore

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def graph():
    """Query the Knowledge Graph."""
    pass


@graph.command("query-relationships")
@click.argument("query")
@click.option("--limit", default=5, help="Maximum number of relationships to return")
@click.option("--threshold", type=float, default=0.35, help="Relationship confidence threshold (0.0-1.0, default 0.35)")
@click.option("--verbose", is_flag=True, help="Show detailed metadata (id, source/target nodes, established date)")
def graph_query_relationships(query, limit, threshold, verbose):
    """
    Search for entity relationships using natural language.

    Example:
        rag graph query-relationships "How does quantum computing relate to cryptography?" --limit 5
        rag graph query-relationships "How does quantum computing relate to cryptography?" --threshold 0.5
        rag graph query-relationships "How does quantum computing relate to cryptography?" --verbose
    """
    try:
        from graphiti_core import Graphiti
        from src.mcp.tools import query_relationships_impl

        # Initialize Graphiti
        # Note: These environment variables are set by ensure_config_or_exit() in main(),
        # which loads credentials from config/config.yaml. The fallback defaults are only
        # used if configuration hasn't been loaded (should not happen in normal operation).
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        graph_store = GraphStore(graphiti)

        console.print(f"[bold blue]Searching Knowledge Graph...[/bold blue]\n")
        console.print(f"Query: {query}")
        console.print(f"Threshold: {threshold}\n")

        # Call business logic layer (same as MCP tool)
        result = asyncio.run(query_relationships_impl(
            graph_store,
            query,
            num_results=limit,
            threshold=threshold
        ))

        if result["status"] == "unavailable":
            console.print("[yellow]Knowledge Graph is not available. Only RAG search is enabled.[/yellow]")
            sys.exit(1)

        if not result["relationships"]:
            console.print("[yellow]No relationships found.[/yellow]")
            return

        console.print(f"[bold green]Found {result['num_results']} relationship(s):[/bold green]\n")

        for i, rel in enumerate(result["relationships"], 1):
            console.print(f"[bold cyan]{i}. {rel['relationship_type']}[/bold cyan]")
            console.print(f"   {rel['fact']}")

            if verbose:
                if rel.get("id"):
                    console.print(f"   [dim]ID: {rel['id']}[/dim]")
                if rel.get("source_node_id"):
                    console.print(f"   [dim]Source node: {rel['source_node_id']}[/dim]")
                if rel.get("target_node_id"):
                    console.print(f"   [dim]Target node: {rel['target_node_id']}[/dim]")
                if rel.get("valid_from"):
                    console.print(f"   [dim]Established: {rel['valid_from']}[/dim]")

            console.print()

    except ImportError:
        console.print("[bold red]Error: Graphiti not installed. Knowledge Graph features unavailable.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@graph.command("query-temporal")
@click.argument("query")
@click.option("--limit", default=10, help="Maximum number of timeline items to return")
@click.option("--valid-from", default=None, help="ISO 8601 date - only facts valid after this date (e.g., 2025-12-01T00:00:00)")
@click.option("--valid-until", default=None, help="ISO 8601 date - only facts valid before this date (e.g., 2025-12-31T23:59:59)")
def graph_query_temporal(query, limit, valid_from, valid_until):
    """
    Query how knowledge evolved over time using temporal reasoning.

    Supports temporal filtering to find decisions or facts from specific time windows.

    Examples:
        rag graph query-temporal "How has quantum computing understanding evolved?" --limit 10

        rag graph query-temporal "What decisions did I make?" \\
          --valid-from "2025-12-01T00:00:00" \\
          --valid-until "2025-12-31T23:59:59"
    """
    try:
        from graphiti_core import Graphiti
        from src.mcp.tools import query_temporal_impl

        # Initialize Graphiti
        # Note: These environment variables are set by ensure_config_or_exit() in main(),
        # which loads credentials from config/config.yaml. The fallback defaults are only
        # used if configuration hasn't been loaded (should not happen in normal operation).
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

        graphiti = Graphiti(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password
        )

        graph_store = GraphStore(graphiti)

        console.print(f"[bold blue]Searching Knowledge Graph Timeline...[/bold blue]\n")
        console.print(f"Query: {query}\n")
        if valid_from or valid_until:
            console.print(f"[cyan]Temporal filters: from={valid_from}, until={valid_until}[/cyan]\n")

        # Call business logic layer (same as MCP tool)
        result = asyncio.run(query_temporal_impl(
            graph_store,
            query,
            num_results=limit,
            valid_from=valid_from,
            valid_until=valid_until
        ))

        if result["status"] == "unavailable":
            console.print("[yellow]Knowledge Graph is not available. Only RAG search is enabled.[/yellow]")
            sys.exit(1)

        if not result["timeline"]:
            console.print("[yellow]No temporal data found.[/yellow]")
            return

        console.print(f"[bold green]Found {result['num_results']} timeline item(s):[/bold green]\n")

        for i, item in enumerate(result["timeline"], 1):
            status_icon = "✅" if item["status"] == "current" else "⏰"
            console.print(f"[bold cyan]{status_icon} {i}. {item['relationship_type']}[/bold cyan]")
            console.print(f"   {item['fact']}")
            console.print(f"   Valid from: {item.get('valid_from', 'N/A')}")
            if item.get("valid_until"):
                console.print(f"   Valid until: {item['valid_until']}")
            console.print(f"   Status: {item['status']}")
            console.print()

    except ImportError:
        console.print("[bold red]Error: Graphiti not installed. Knowledge Graph features unavailable.[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@graph.command("rebuild-communities")
@click.option("--collection", help="Rebuild communities for specific collection only")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def graph_rebuild_communities(collection, yes):
    """
    Rebuild community detection for the Knowledge Graph (admin operation).

    Community detection groups related entities together based on their relationships.
    This is a computationally expensive operation that should be run periodically
    (e.g., nightly or after major ingestions).

    WARNING: This will clear all existing communities and rebuild from scratch.

    Examples:
        # Rebuild all communities (requires confirmation)
        rag graph rebuild-communities

        # Rebuild for specific collection only
        rag graph rebuild-communities --collection project-docs

        # Skip confirmation prompt
        rag graph rebuild-communities --yes
    """
    async def run_rebuild():
        try:
            from graphiti_core import Graphiti
            from graphiti_core.llm_client.openai_client import OpenAIClient
            from graphiti_core.llm_client.config import LLMConfig

            # Show warning and confirm
            if not yes:
                if collection:
                    console.print(f"\n[bold yellow]⚠️  WARNING: This will rebuild communities for collection '{collection}'[/bold yellow]")
                else:
                    console.print(f"\n[bold yellow]⚠️  WARNING: This will rebuild ALL communities in the Knowledge Graph[/bold yellow]")
                console.print("[yellow]This is a computationally expensive operation that may take several minutes.[/yellow]")
                console.print("[yellow]Existing communities will be cleared and rebuilt from scratch.[/yellow]\n")

                confirm = click.confirm("Are you sure you want to proceed?", default=False)
                if not confirm:
                    console.print("[dim]Rebuild cancelled[/dim]")
                    return

            console.print(f"[bold blue]Initializing Knowledge Graph...[/bold blue]")

            # Initialize Graphiti (similar to initialize_graph_components but simpler)
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")

            # Read optional Graphiti LLM model configuration
            graphiti_model = os.getenv("GRAPHITI_MODEL")
            graphiti_small_model = os.getenv("GRAPHITI_SMALL_MODEL")

            # Create LLM client with optional model overrides
            llm_config_kwargs = {
                'api_key': os.getenv("OPENAI_API_KEY")
            }
            if graphiti_model:
                llm_config_kwargs['model'] = graphiti_model
                logger.info(f"Using configured Graphiti model: {graphiti_model}")
            if graphiti_small_model:
                llm_config_kwargs['small_model'] = graphiti_small_model
                logger.info(f"Using configured Graphiti small model: {graphiti_small_model}")

            llm_config = LLMConfig(**llm_config_kwargs)
            llm_client = OpenAIClient(config=llm_config)

            graphiti = Graphiti(
                uri=neo4j_uri,
                user=neo4j_user,
                password=neo4j_password,
                llm_client=llm_client
            )

            # Prepare group_ids if collection specified
            group_ids = [collection] if collection else None

            if collection:
                console.print(f"[bold blue]Rebuilding communities for collection: {collection}[/bold blue]")
            else:
                console.print(f"[bold blue]Rebuilding ALL communities in the Knowledge Graph...[/bold blue]")

            console.print("[dim]This may take several minutes depending on graph size...[/dim]\n")

            # Start timer
            start_time = time.time()

            # Call Graphiti's build_communities method
            communities, community_edges = await graphiti.build_communities(group_ids=group_ids)

            # Calculate duration
            duration = time.time() - start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)

            # Display results
            console.print(f"\n[bold green]✅ Community rebuild complete![/bold green]")
            console.print(f"  Communities created: {len(communities)}")
            console.print(f"  Community edges: {len(community_edges)}")
            console.print(f"  Duration: {minutes}m {seconds}s")

            if collection:
                console.print(f"  Collection: {collection}")

            # Show sample communities if any were created
            if communities and len(communities) > 0:
                console.print(f"\n[bold cyan]Sample communities (first 3):[/bold cyan]")
                for i, community in enumerate(communities[:3], 1):
                    # Communities have name and summary attributes
                    console.print(f"  {i}. {getattr(community, 'name', 'Unnamed')}")
                    if hasattr(community, 'summary'):
                        # Truncate summary if too long
                        summary = getattr(community, 'summary', '')
                        if len(summary) > 100:
                            summary = summary[:100] + "..."
                        console.print(f"     [dim]{summary}[/dim]")

        except ImportError:
            console.print("[bold red]Error: Graphiti not installed. Knowledge Graph features unavailable.[/bold red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]Error during community rebuild: {e}[/bold red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # Run the async function
    asyncio.run(run_rebuild())
