"""Component initialization for RAG Memory CLI."""

import asyncio
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Global variables to hold RAG components
db = None
embedder = None
coll_mgr = None
doc_store = None

# Global variables for Knowledge Graph components
graph_store = None
unified_mediator = None


def initialize_components():
    """
    Initialize RAG components only.

    Knowledge Graph components (graph_store, unified_mediator) are initialized
    lazily within async context to avoid event loop conflicts.
    """
    global db, embedder, coll_mgr, doc_store

    # Import here to avoid circular imports
    from src.core.database import get_database
    from src.core.embeddings import get_embedding_generator
    from src.core.collections import get_collection_manager
    from src.ingestion.document_store import get_document_store

    # Initialize RAG components
    logger.info("Initializing RAG components...")
    db = get_database()
    embedder = get_embedding_generator()
    coll_mgr = get_collection_manager(db)
    doc_store = get_document_store(db, embedder, coll_mgr)
    logger.info("RAG components initialized")


async def initialize_graph_components() -> Tuple[Optional[object], Optional[object]]:
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
        from graphiti_core.llm_client.openai_client import OpenAIClient
        from graphiti_core.llm_client.config import LLMConfig

        # Read Neo4j connection details from environment
        # Note: These environment variables are set by ensure_config_or_exit() in main(),
        # which loads credentials from config/config.yaml. The fallback defaults are only
        # used if the config file is missing or incomplete (which shouldn't happen in normal use).
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "graphiti-password")
        openai_api_key = os.getenv("OPENAI_API_KEY", "")

        if not openai_api_key:
            logger.warning("OPENAI_API_KEY not set - graph operations will fail")
            return None, None

        # Create Graphiti client with OpenAI
        llm_config = LLMConfig(api_key=openai_api_key)
        llm_client = OpenAIClient(llm_config)

        graphiti_client = Graphiti(
            uri=neo4j_uri,
            username=neo4j_user,
            password=neo4j_password,
            llm_client=llm_client,
        )

        # Initialize GraphStore wrapper
        from src.unified import GraphStore, UnifiedIngestionMediator

        local_graph_store = GraphStore()
        local_graph_store.graphiti = graphiti_client
        await local_graph_store.init()

        # Initialize unified mediator
        if db and doc_store and coll_mgr:
            local_unified_mediator = UnifiedIngestionMediator(
                doc_store=doc_store,
                graph_store=local_graph_store,
                collection_manager=coll_mgr
            )
            logger.info("Knowledge Graph components initialized")
            return local_graph_store, local_unified_mediator
        else:
            logger.warning("RAG components not available for unified mediator")
            return local_graph_store, None

    except ImportError as e:
        logger.error(f"Failed to import Graphiti dependencies: {e}")
        logger.error("Please install graphiti-core: pip install graphiti-core")
        return None, None
    except Exception as e:
        logger.error(f"Failed to initialize Knowledge Graph components: {e}")
        return None, None


def get_components():
    """Get initialized RAG components.

    Returns:
        tuple: (db, embedder, coll_mgr, doc_store)
    """
    if db is None:
        initialize_components()
    return db, embedder, coll_mgr, doc_store


async def get_graph_components():
    """Get initialized Knowledge Graph components.

    Returns:
        tuple: (graph_store, unified_mediator)
    """
    global graph_store, unified_mediator

    if graph_store is None:
        graph_store, unified_mediator = await initialize_graph_components()

    return graph_store, unified_mediator