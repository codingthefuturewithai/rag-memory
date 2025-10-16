"""
Unified RAG + Knowledge Graph integration.

This module provides a unified interface for ingesting content into both
the vector-based RAG store (pgvector) and the knowledge graph store (Graphiti/Neo4j).

Key components:
- GraphStore: Wraps Graphiti operations, abstracts Neo4j complexity
- UnifiedIngestionMediator: Orchestrates ingestion to both RAG and Graph stores
"""

from .graph_store import GraphStore
from .mediator import UnifiedIngestionMediator

__all__ = ["GraphStore", "UnifiedIngestionMediator"]
