"""Ingestion commands."""

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console

from src.core.chunking import ChunkingConfig, get_document_chunker
from src.core.collections import get_collection_manager
from src.core.database import get_database
from src.core.embeddings import get_embedding_generator
from src.ingestion.document_store import get_document_store
from src.ingestion.web_crawler import WebCrawler, crawl_single_page

logger = logging.getLogger(__name__)
console = Console()


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
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient

        from src.unified import GraphStore, UnifiedIngestionMediator

        # Read Neo4j connection details from environment
        import os

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            logger.warning("OPENAI_API_KEY not found - Knowledge Graph will not be available")
            return None, None

        # Read optional Graphiti LLM model configuration from environment
        # If not specified, Graphiti will use its own defaults
        graphiti_model = os.getenv("GRAPHITI_MODEL")
        graphiti_small_model = os.getenv("GRAPHITI_SMALL_MODEL")

        # Create LLM client with optional model overrides
        llm_config_kwargs = {
            'api_key': openai_api_key
        }
        if graphiti_model:
            llm_config_kwargs['model'] = graphiti_model
            logger.info(f"Using configured Graphiti model: {graphiti_model}")
        if graphiti_small_model:
            llm_config_kwargs['small_model'] = graphiti_small_model
            logger.info(f"Using configured Graphiti small model: {graphiti_small_model}")

        llm_config = LLMConfig(**llm_config_kwargs)
        llm_client = OpenAIClient(llm_config)

        graphiti = Graphiti(neo4j_uri, neo4j_user, neo4j_password, llm_client)

        # Initialize GraphStore wrapper
        graph_store = GraphStore(graphiti)

        # Initialize RAG components for unified mediator
        db = get_database()
        embedder = get_embedding_generator()
        coll_mgr = get_collection_manager(db)

        # Initialize unified mediator (creates rag_store internally)
        unified_mediator = UnifiedIngestionMediator(
            db=db,
            embedder=embedder,
            collection_mgr=coll_mgr,
            graph_store=graph_store
        )

        logger.info("Knowledge Graph components initialized successfully")
        return graph_store, unified_mediator

    except Exception as e:
        logger.warning(f"Failed to initialize Knowledge Graph: {e}")
        return None, None


@click.group()
def ingest():
    """Ingest documents."""
    pass


@ingest.command("text")
@click.argument("content")
@click.option("--collection", required=True, help="Collection name")
@click.option("--title", help="Document title")
@click.option("--metadata", help="Additional metadata as JSON string")
def ingest_text_cmd(content, collection, title, metadata):
    """Ingest text content directly with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.
    """

    async def run_ingest():
        try:
            metadata_dict = json.loads(metadata) if metadata else None

            console.print(f"[bold blue]Ingesting text content[/bold blue]")

            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = (
                await initialize_graph_components()
            )

            # Use unified mediator if available (match MCP server logic)
            if local_unified_mediator:
                logger.info("Using unified mediator for text ingestion")

                result = await local_unified_mediator.ingest_text(
                    content=content,
                    collection_name=collection,
                    document_title=title or "text_input",
                    metadata=metadata_dict or {},
                )

                console.print(
                    f"[bold green]✓ Ingested text (ID: {result['source_document_id']}) "
                    f"with {result['num_chunks']} chunks to collection '{collection}'[/bold green]"
                )
                console.print(
                    f"[dim]Entities extracted: {result.get('entities_extracted', 0)}[/dim]"
                )

            # Fallback: RAG-only mode
            else:
                logger.info("Using RAG-only mode for text ingestion")
                db = get_database()
                embedder = get_embedding_generator()
                coll_mgr = get_collection_manager(db)
                doc_store = get_document_store(db, embedder, coll_mgr)

                source_id, chunk_ids = doc_store.ingest_text(
                    content, collection, title or "text_input", metadata_dict
                )
                console.print(
                    f"[bold green]✓ Ingested text (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
                )
                console.print(
                    "[dim]Knowledge Graph not available - RAG-only mode[/dim]"
                )

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())


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
            local_graph_store, local_unified_mediator = (
                await initialize_graph_components()
            )

            # Use unified mediator if available (match MCP server logic)
            if local_unified_mediator:
                logger.info(f"Using unified mediator for file: {Path(path).name}")

                # Read file content
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()

                # Merge file metadata
                file_metadata = metadata_dict.copy() if metadata_dict else {}
                file_path_obj = Path(path)
                file_metadata.update(
                    {
                        "file_type": file_path_obj.suffix.lstrip(".").lower() or "text",
                        "file_size": file_path_obj.stat().st_size,
                    }
                )

                result = await local_unified_mediator.ingest_text(
                    content=file_content,
                    collection_name=collection,
                    document_title=file_path_obj.name,
                    metadata=file_metadata,
                )

                console.print(
                    f"[bold green]✓ Ingested file (ID: {result['source_document_id']}) "
                    f"with {result['num_chunks']} chunks to collection '{collection}'[/bold green]"
                )
                console.print(
                    f"[dim]Entities extracted: {result.get('entities_extracted', 0)}[/dim]"
                )

            # Fallback: RAG-only mode
            else:
                logger.info(f"Using RAG-only mode for file: {Path(path).name}")
                db = get_database()
                embedder = get_embedding_generator()
                coll_mgr = get_collection_manager(db)
                doc_store = get_document_store(db, embedder, coll_mgr)

                source_id, chunk_ids = doc_store.ingest_file(
                    path, collection, metadata_dict
                )
                console.print(
                    f"[bold green]✓ Ingested file (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
                )
                console.print(
                    "[dim]Knowledge Graph not available - RAG-only mode[/dim]"
                )

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
@click.option(
    "--metadata", help="Additional metadata as JSON string to apply to all files"
)
def ingest_directory(path, collection, extensions, recursive, metadata):
    """Ingest all files from a directory with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.
    """

    async def run_ingest():
        try:
            # Parse metadata if provided
            metadata_dict = json.loads(metadata) if metadata else None

            ext_list = [ext.strip() for ext in extensions.split(",")]
            path_obj = Path(path)

            console.print(
                f"[bold blue]Ingesting files from: {path} (extensions: {ext_list})[/bold blue]"
            )
            if metadata_dict:
                console.print(f"[dim]Applying metadata: {metadata}[/dim]")

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
            local_graph_store, local_unified_mediator = (
                await initialize_graph_components()
            )

            # Ingest each file
            source_ids = []
            total_chunks = 0
            total_entities = 0

            for file_path in files:
                try:
                    # Use unified mediator if available
                    if local_unified_mediator:
                        # Read file content
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            file_content = f.read()

                        # Build file metadata: merge user metadata with file metadata
                        file_metadata = metadata_dict.copy() if metadata_dict else {}
                        file_metadata.update(
                            {
                                "file_type": file_path.suffix.lstrip(".").lower()
                                or "text",
                                "file_size": file_path.stat().st_size,
                            }
                        )

                        result = await local_unified_mediator.ingest_text(
                            content=file_content,
                            collection_name=collection,
                            document_title=file_path.name,
                            metadata=file_metadata,
                        )

                        source_ids.append(result["source_document_id"])
                        total_chunks += result["num_chunks"]
                        total_entities += result.get("entities_extracted", 0)
                        console.print(
                            f"  ✓ {file_path.name}: {result['num_chunks']} chunks, {result.get('entities_extracted', 0)} entities"
                        )

                    # Fallback: RAG-only mode
                    else:
                        db = get_database()
                        embedder = get_embedding_generator()
                        coll_mgr = get_collection_manager(db)
                        doc_store = get_document_store(db, embedder, coll_mgr)

                        source_id, chunk_ids = doc_store.ingest_file(
                            str(file_path), collection
                        )
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
                console.print(
                    "[dim]Knowledge Graph not available - RAG-only mode[/dim]"
                )

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())


@ingest.command("url")
@click.argument("url")
@click.option("--collection", required=True, help="Collection name")
@click.option(
    "--mode",
    type=click.Choice(["crawl", "recrawl"], case_sensitive=False),
    default="crawl",
    help="Crawl mode: fresh crawl or recrawl (delete old + crawl new)",
)
@click.option(
    "--headless/--no-headless", default=True, help="Run browser in headless mode"
)
@click.option("--verbose", is_flag=True, help="Enable verbose crawling output")
@click.option(
    "--chunk-size",
    type=int,
    default=2500,
    help="Chunk size for web pages (default: 2500)",
)
@click.option(
    "--chunk-overlap", type=int, default=300, help="Chunk overlap (default: 300)"
)
@click.option("--follow-links", is_flag=True, help="Follow internal links (multi-page crawl)")
@click.option(
    "--max-depth",
    type=int,
    default=1,
    help="Maximum crawl depth when following links (default: 1)",
)
@click.option(
    "--metadata", help="Additional metadata as JSON string to apply to all pages"
)
def ingest_url(
    url,
    collection,
    mode,
    headless,
    verbose,
    chunk_size,
    chunk_overlap,
    follow_links,
    max_depth,
    metadata,
):
    """Crawl and ingest a web page with automatic chunking.

    Routes through unified mediator to update both RAG store and Knowledge Graph.
    Falls back to RAG-only mode if Knowledge Graph unavailable.

    By default, only the specified page is crawled. Use --follow-links to crawl
    linked pages up to --max-depth levels deep.

    Use --mode recrawl to find and delete existing documents from previous crawls
    of the same URL before re-crawling.

    Examples:
        # Single page only
        rag ingest url https://example.com --collection docs

        # Re-crawl (delete old, then crawl)
        rag ingest url https://example.com --collection docs --mode recrawl

        # Follow direct links (depth=1)
        rag ingest url https://example.com --collection docs --follow-links

        # Follow links 2 levels deep
        rag ingest url https://example.com --collection docs --follow-links --max-depth 2
    """

    async def run_ingest():
        try:
            # Parse metadata if provided
            metadata_dict = json.loads(metadata) if metadata else None
            if metadata_dict:
                console.print(f"[dim]Applying metadata: {metadata}[/dim]")

            # Handle recrawl mode: delete old documents first
            if mode.lower() == "recrawl":
                console.print(f"[bold blue]Re-crawling: {url}[/bold blue]")
                console.print(
                    f"[dim]Finding existing documents with crawl_root_url = {url}...[/dim]"
                )

                # Step 1: Find all source documents with matching crawl_root_url
                db = get_database()
                conn = db.connect()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, filename, metadata
                        FROM source_documents
                        WHERE metadata->>'crawl_root_url' = %s
                        """,
                        (url,),
                    )
                    existing_docs = cur.fetchall()

                if not existing_docs:
                    console.print(
                        f"[yellow]No existing documents found with crawl_root_url = {url}[/yellow]"
                    )
                    console.print("[dim]Proceeding with fresh crawl...[/dim]")
                    old_doc_count = 0
                else:
                    old_doc_count = len(existing_docs)
                    console.print(
                        f"[yellow]Found {old_doc_count} existing documents to delete[/yellow]"
                    )

                    # Step 2: Delete the old documents and their chunks
                    embedder = get_embedding_generator()
                    coll_mgr = get_collection_manager(db)
                    web_chunking_config = ChunkingConfig(
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap
                    )
                    web_chunker = get_document_chunker(web_chunking_config)
                    web_doc_store = get_document_store(
                        db, embedder, coll_mgr, chunker=web_chunker
                    )

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
                                    (doc_id,),
                                )
                                # Delete source document
                                cur.execute(
                                    "DELETE FROM source_documents WHERE id = %s",
                                    (doc_id,),
                                )

                            console.print(
                                f"  [dim]✓ Deleted document {doc_id}: {filename} ({chunk_count} chunks)[/dim]"
                            )
                        except Exception as e:
                            console.print(
                                f"  [red]✗ Failed to delete document {doc_id}: {e}[/red]"
                            )

                console.print(f"\n[bold blue]Starting crawl...[/bold blue]")
            else:
                old_doc_count = 0
                console.print(f"[bold blue]Crawling URL: {url}[/bold blue]")

            # Initialize Knowledge Graph components (lazy initialization within async context)
            local_graph_store, local_unified_mediator = (
                await initialize_graph_components()
            )

            if follow_links:
                # Multi-page crawl with link following
                if mode.lower() != "recrawl":
                    console.print(
                        f"[bold blue]Crawling URL with link following: {url} (max_depth={max_depth})[/bold blue]"
                    )

                crawler = WebCrawler(headless=headless, verbose=verbose)
                results = await crawler.crawl_with_depth(url, max_depth=max_depth)

                if not results:
                    console.print(
                        f"[bold red]✗ No pages crawled from {url}[/bold red]"
                    )
                    sys.exit(1)

                console.print(f"[green]✓ Crawled {len(results)} pages[/green]")

                # Ingest each page
                total_chunks = 0
                total_entities = 0
                successful_ingests = 0

                for i, result in enumerate(results, 1):
                    if not result.success:
                        console.print(
                            f"  [yellow]⚠ Skipped failed page {i}: {result.url}[/yellow]"
                        )
                        continue

                    try:
                        # Merge user metadata with page metadata
                        page_metadata = metadata_dict.copy() if metadata_dict else {}
                        page_metadata.update(result.metadata)

                        # Use unified mediator if available
                        if local_unified_mediator:
                            ingest_result = await local_unified_mediator.ingest_text(
                                content=result.content,
                                collection_name=collection,
                                document_title=result.metadata.get("title", result.url),
                                metadata=page_metadata,
                            )
                            total_chunks += ingest_result["num_chunks"]
                            total_entities += ingest_result.get("entities_extracted", 0)
                            successful_ingests += 1
                            console.print(
                                f"  ✓ Page {i}/{len(results)}: {result.metadata.get('title', result.url)[:50]}... "
                                f"({ingest_result['num_chunks']} chunks, {ingest_result.get('entities_extracted', 0)} entities, "
                                f"depth={result.metadata.get('crawl_depth', 0)})"
                            )

                        # Fallback: RAG-only mode
                        else:
                            db = get_database()
                            embedder = get_embedding_generator()
                            coll_mgr = get_collection_manager(db)
                            web_chunking_config = ChunkingConfig(
                                chunk_size=chunk_size, chunk_overlap=chunk_overlap
                            )
                            web_chunker = get_document_chunker(web_chunking_config)
                            web_doc_store = get_document_store(
                                db, embedder, coll_mgr, chunker=web_chunker
                            )

                            source_id, chunk_ids = web_doc_store.ingest_document(
                                content=result.content,
                                filename=result.metadata.get("title", result.url),
                                collection_name=collection,
                                metadata=page_metadata,
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

                if mode.lower() == "recrawl":
                    console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                    console.print(
                        f"[bold]Deleted {old_doc_count} old pages, crawled {successful_ingests} new pages with {total_chunks} total chunks[/bold]"
                    )
                    console.print(f"[dim]Collection: '{collection}'[/dim]")
                else:
                    console.print(
                        f"\n[bold green]✓ Ingested {successful_ingests} pages with {total_chunks} total chunks "
                        f"to collection '{collection}'[/bold green]"
                    )
                if local_unified_mediator and total_entities > 0:
                    console.print(
                        f"[dim]Total entities extracted: {total_entities}[/dim]"
                    )
                elif not local_unified_mediator:
                    console.print(
                        "[dim]Knowledge Graph not available - RAG-only mode[/dim]"
                    )
                console.print(
                    f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]"
                )

            else:
                # Single-page crawl
                if mode.lower() != "recrawl":
                    console.print(f"[bold blue]Crawling URL: {url}[/bold blue]")

                # Crawl the page
                result = await crawl_single_page(url, headless=headless, verbose=verbose)

                if not result.success:
                    console.print(f"[bold red]✗ Failed to crawl {url}[/bold red]")
                    if result.error:
                        console.print(
                            f"[bold red]Error: {result.error.error_message}[/bold red]"
                        )
                    sys.exit(1)

                console.print(
                    f"[green]✓ Successfully crawled page ({len(result.content)} chars)[/green]"
                )

                # Merge user metadata with page metadata
                page_metadata = metadata_dict.copy() if metadata_dict else {}
                page_metadata.update(result.metadata)

                # Use unified mediator if available
                if local_unified_mediator:
                    ingest_result = await local_unified_mediator.ingest_text(
                        content=result.content,
                        collection_name=collection,
                        document_title=result.metadata.get("title", url),
                        metadata=page_metadata,
                    )

                    if mode.lower() == "recrawl":
                        console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                        console.print(
                            f"[bold]Deleted {old_doc_count} old pages, crawled 1 new page with {ingest_result['num_chunks']} chunks[/bold]"
                        )
                        console.print(f"[dim]Collection: '{collection}'[/dim]")
                        console.print(
                            f"[dim]Entities extracted: {ingest_result.get('entities_extracted', 0)}[/dim]"
                        )
                    else:
                        console.print(
                            f"[bold green]✓ Ingested web page (ID: {ingest_result['source_document_id']}) "
                            f"with {ingest_result['num_chunks']} chunks to collection '{collection}'[/bold green]"
                        )
                        console.print(
                            f"[dim]Entities extracted: {ingest_result.get('entities_extracted', 0)}[/dim]"
                        )
                    console.print(
                        f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]"
                    )
                    console.print(
                        f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]"
                    )

                # Fallback: RAG-only mode
                else:
                    db = get_database()
                    embedder = get_embedding_generator()
                    coll_mgr = get_collection_manager(db)
                    web_chunking_config = ChunkingConfig(
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap
                    )
                    web_chunker = get_document_chunker(web_chunking_config)
                    web_doc_store = get_document_store(
                        db, embedder, coll_mgr, chunker=web_chunker
                    )

                    source_id, chunk_ids = web_doc_store.ingest_document(
                        content=result.content,
                        filename=result.metadata.get("title", url),
                        collection_name=collection,
                        metadata=page_metadata,
                        file_type="web_page",
                    )

                    if mode.lower() == "recrawl":
                        console.print(f"\n[bold green]✓ Re-crawl complete![/bold green]")
                        console.print(
                            f"[bold]Deleted {old_doc_count} old pages, crawled 1 new page with {len(chunk_ids)} chunks[/bold]"
                        )
                        console.print(f"[dim]Collection: '{collection}'[/dim]")
                    else:
                        console.print(
                            f"[bold green]✓ Ingested web page (ID: {source_id}) with {len(chunk_ids)} chunks to collection '{collection}'[/bold green]"
                        )
                    console.print(
                        "[dim]Knowledge Graph not available - RAG-only mode[/dim]"
                    )
                    console.print(
                        f"[dim]Title: {result.metadata.get('title', 'N/A')}[/dim]"
                    )
                    console.print(
                        f"[dim]Domain: {result.metadata.get('domain', 'N/A')}[/dim]"
                    )
                    console.print(
                        f"[dim]Chunk size: {chunk_size} chars, Overlap: {chunk_overlap} chars[/dim]"
                    )

        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_ingest())
