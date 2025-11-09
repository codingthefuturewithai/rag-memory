# What is RAG Memory?

RAG Memory is a PostgreSQL-based semantic search system for AI agents and knowledge management. It combines vector search with knowledge graph capabilities to provide both content retrieval and relationship tracking.

## Core Concept

RAG stands for Retrieval-Augmented Generation:
- **Retrieval** - Find relevant documents from your knowledge base
- **Augmented** - Add those documents to your AI prompt
- **Generation** - Let the AI generate responses with full context

RAG Memory handles the retrieval part, storing your documents in a searchable format and providing them when needed.

## What It Provides

**Vector Database**
- PostgreSQL with pgvector extension for semantic search
- Stores document embeddings (1536-dimensional vectors)
- Enables finding documents by meaning, not just keywords

**Document Storage**
- Full source documents preserved
- Automatic chunking into searchable pieces
- Metadata tracking for flexible organization

**Knowledge Graph**
- Neo4j database with Graphiti for entity extraction
- Tracks relationships between concepts
- Enables temporal reasoning about how knowledge evolves

**Two Interfaces**
- MCP Server - 18 tools for AI agents (Claude Desktop, Claude Code, Cursor)
- CLI Tool - Direct command-line access for management and automation

## How It Works

```
1. INGEST
   Your Content → Auto-Chunking → Vector Embeddings → PostgreSQL + Neo4j

2. STORE
   Source Document (full text)
   Chunks (searchable pieces with embeddings)
   Collections (organized by topic)
   Entities and Relationships (knowledge graph)

3. SEARCH
   User Query → Generate Embedding → Vector Search → Rank Results

4. RETRIEVE
   Return matching chunks with source documents
```

## Key Capabilities

**Semantic Search**
- Find documents by meaning, not keywords
- Query: "How do I authenticate users?" matches content about OAuth, tokens, and login flows
- Returns similarity scores (0.0-1.0) indicating relevance

**Document Chunking**
- Large documents split into 1000-character chunks
- 200-character overlap preserves context
- Each chunk embedded and searchable independently

**Collection Management**
- Organize documents by topic or source
- Multiple collections for different domains
- Documents can belong to multiple collections

**Web Crawling**
- Ingest documentation websites
- Follow links automatically
- Re-crawl to update content

**Knowledge Graph**
- Extract entities and relationships from text
- Track how knowledge changes over time
- Query connections between concepts

## Why RAG Memory?

**For AI Agents**
Give your AI persistent memory of documents and knowledge. The agent can search for relevant information during conversations without you having to paste content repeatedly.

**For Knowledge Management**
Build searchable documentation repositories. Ingest manuals, wikis, and documentation sites, then search them semantically.

**For Research**
Understand how concepts relate and evolve. The knowledge graph tracks entities, relationships, and temporal changes.

## Architecture

**Dual Storage System**
- PostgreSQL (pgvector) - Vector search and document storage
- Neo4j (Graphiti) - Entity graph and relationships
- Both databases are required and kept in sync automatically

**Vector Normalization**
Embeddings are normalized to unit length before storage. This is critical for accurate similarity scores.

**No Keyword Search**
RAG Memory uses semantic similarity search only. Queries should be natural language questions, not keyword lists.

## Use Cases

1. **Agent Memory** - Give Claude/Cursor/other AI agents persistent knowledge
2. **Documentation Search** - Make documentation semantically searchable
3. **Research Analysis** - Explore relationships between concepts
4. **Knowledge Evolution** - Track how information changes over time

## What It's Not

**Not a Keyword Search Engine**
Use full questions like "How do I configure authentication?" instead of keywords like "auth config".

**Not a Database**
RAG Memory stores embeddings for semantic search, not structured data for queries.

**Not a Chatbot**
It's a retrieval system that provides context to AI agents. The agent does the generation.

**Not Cloud-Only**
Runs locally with Docker or deploys to cloud (Fly.io + Supabase).

## Next Steps

- **Installation** - See INSTALLATION.md for Docker setup
- **MCP Setup** - See MCP_GUIDE.md for AI agent configuration
- **CLI Usage** - See CLI_GUIDE.md for command reference
- **Search Details** - See VECTOR_SEARCH.md for semantic search
- **Graph Features** - See KNOWLEDGE_GRAPH.md for entity extraction
