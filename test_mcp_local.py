"""
Test MCP server ingest_url in local venv using the same getters as the server.
"""
import asyncio
import logging
from src.core.database import get_database
from src.ingestion.document_store import get_document_store
from src.unified import GraphStore, UnifiedIngestionMediator
from src.core.config_loader import load_environment_variables
from src.mcp.tools import ingest_url_impl, analyze_website_impl, create_collection_impl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test ingest_url_impl with follow_links=True."""
    logger.info("="*80)
    logger.info("Testing MCP ingest_url with follow_links=True (max_pages=5)")
    logger.info("="*80)
    
    # Load config first
    load_environment_variables()
    
    # Initialize components using the same getters as MCP server
    db = get_database()
    db.connect()
    
    doc_store = get_document_store()
    
    # GraphStore and UnifiedIngestionMediator need manual init
    from src.core.config_loader import load_config
    config = load_config()
    
    graph_store = GraphStore(
        uri=config['server']['neo4j_uri'],
        user=config['server']['neo4j_user'],
        password=config['server']['neo4j_password']
    )
    
    unified_mediator = UnifiedIngestionMediator(
        graph_store=graph_store,
        doc_store=doc_store,
        config=config
    )
    
    try:
        # Step 1: Analyze website
        logger.info("Step 1: Analyzing website...")
        analysis = analyze_website_impl("https://python.org/about")
        logger.info(f"Analysis complete: {analysis['total_urls']} URLs found")
        
        # Step 2: Create collection
        logger.info("\nStep 2: Creating test collection...")
        try:
            create_collection_impl(
                db, 
                name="test_mcp_crawl",
                description="Test collection for MCP crawl debugging",
                domain="Testing",
                domain_scope="Debug test"
            )
            logger.info("Collection created")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("Collection already exists, continuing...")
            else:
                raise
        
        # Step 3: Ingest with follow_links
        logger.info("\nStep 3: Calling ingest_url_impl with follow_links=True...")
        result = await ingest_url_impl(
            db=db,
            doc_store=doc_store,
            unified_mediator=unified_mediator,
            graph_store=graph_store,
            url="https://python.org/about",
            collection_name="test_mcp_crawl",
            follow_links=True,
            max_pages=5,
            analysis_token=analysis['analysis_token'],
            mode="recrawl",  # Use recrawl to avoid duplicate errors
            metadata=None,
            include_document_ids=False,
            progress_callback=None
        )
        
        logger.info("="*80)
        logger.info(f"✅ SUCCESS: Crawled {result['pages_crawled']} pages")
        logger.info(f"Ingested: {result['pages_ingested']} pages")
        logger.info(f"Total chunks: {result['total_chunks']}")
        logger.info("="*80)
        
    finally:
        await db.close()
        graph_store.close()


if __name__ == "__main__":
    asyncio.run(main())
