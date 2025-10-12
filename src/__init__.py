"""RAG Memory - Core package for semantic document storage and retrieval."""

__version__ = "0.1.0"

# Backward compatibility layer - creates module aliases
# This allows old imports like "from src.database import X" to still work
# by redirecting to "from src.core.database import X"

import sys
from src.core import database, embeddings, chunking, collections
from src.ingestion import document_store
from src.retrieval import search

# Create module aliases in sys.modules for backward compatibility
sys.modules['src.database'] = database
sys.modules['src.embeddings'] = embeddings
sys.modules['src.chunking'] = chunking
sys.modules['src.collections'] = collections
sys.modules['src.document_store'] = document_store
sys.modules['src.search'] = search
