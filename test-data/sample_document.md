# Sample Test Document

This is a sample markdown document used for testing file and directory ingestion in automated tests.

## Section 1: Overview

RAG Memory is a knowledge management system that combines PostgreSQL pgvector for semantic search with Neo4j for knowledge graph storage.

## Section 2: Key Features

- **Vector Search**: Uses pgvector for efficient similarity search
- **Knowledge Graphs**: Stores relationships and entities in Neo4j
- **Dual Storage**: Maintains both RAG index and graph database
- **File Ingestion**: Supports uploading and indexing documents

## Section 3: Architecture

The system consists of three main components:

1. PostgreSQL with pgvector extension
2. Neo4j graph database
3. MCP server for tool access

## Section 4: Usage Example

To search for information:

```python
from src.retrieval.search import SimilaritySearch

searcher = SimilaritySearch(db, embedder, collection_mgr)
results = searcher.search("your query here", collection_name="docs")
```

This is test data used by automated tests to validate file and directory ingestion functionality.
