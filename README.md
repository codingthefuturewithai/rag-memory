# RAG Memory

A PostgreSQL pgvector-based RAG (Retrieval-Augmented Generation) memory system with MCP (Model Context Protocol) server for AI agents.

## Overview

This POC validates that pgvector with proper vector normalization and HNSW indexing provides significantly better similarity search accuracy compared to ChromaDB. The goal is to achieve similarity scores in the 0.7-0.95 range for semantically similar content, compared to the ~0.3 range currently experienced.

## Key Features

- **PostgreSQL 17** with pgvector extension
- **OpenAI text-embedding-3-small** (1536 dimensions, cost-effective)
- **Vector normalization** for accurate cosine similarity
- **HNSW indexing** for optimal search accuracy (95%+ recall)
- **Collection management** for organizing documents
- **Metadata support** for advanced filtering
- **CLI interface** for easy testing and validation

## Architecture

### Database Schema

- `documents` table with pgvector support
- `collections` table for organization
- `document_collections` junction table
- HNSW index on embeddings for fast similarity search
- GIN index on metadata for efficient filtering

### Python Application

```
src/
├── database.py      # PostgreSQL connection management
├── embeddings.py    # OpenAI embeddings with normalization
├── collections.py   # Collection CRUD operations
├── ingestion.py     # Document ingestion pipeline
├── search.py        # Similarity search with pgvector
└── cli.py          # Command-line interface
```

## Prerequisites

- **Docker & Docker Compose** - For PostgreSQL container
- **uv** - Fast Python package manager
- **Python 3.12** - Specified in .python-version
- **OpenAI API Key** - For embedding generation

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/timkitchens/projects/ai-projects/rag-memory

# Install dependencies with uv (super fast!)
uv sync
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-api-key-here
```

### 3. Start PostgreSQL

```bash
# Start PostgreSQL 17 with pgvector on port 5433
docker-compose up -d

# Check container is running
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Initialize Database

```bash
# Initialize and test connection
uv run rag init

# Check status
uv run rag status
```

### 5. Run Similarity Tests

```bash
# This is the key validation step!
# Tests high, medium, and low similarity scenarios
uv run rag test-similarity
```

Expected output:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Test                      ┃ Expected Range ┃ Actual Score ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━┩
│ High Similarity Test      │ 0.70 - 0.95    │ 0.8542       │ ✓ PASS │
│ Medium Similarity Test    │ 0.50 - 0.75    │ 0.6234       │ ✓ PASS │
│ Low Similarity Test       │ 0.10 - 0.40    │ 0.2145       │ ✓ PASS │
└───────────────────────────┴────────────────┴──────────────┴────────┘
```

## CLI Commands

### Collection Management

```bash
# Create a collection
uv run rag collection create my-docs --description "My document collection"

# List all collections
uv run rag collection list

# Delete a collection
uv run rag collection delete my-docs
```

### Document Ingestion

```bash
# Ingest a single text
uv run rag ingest text "PostgreSQL is a powerful database" --collection tech-docs

# Ingest a file
uv run rag ingest file document.txt --collection tech-docs

# Ingest a directory
uv run rag ingest directory ./docs --collection tech-docs --extensions .txt,.md

# With metadata
uv run rag ingest text "Python tutorial" --collection tutorials --metadata '{"author":"John","topic":"python"}'
```

### Search

```bash
# Basic search (searches document chunks)
uv run rag search "What is PostgreSQL?"

# Search within a collection
uv run rag search "database performance" --collection tech-docs

# Limit results
uv run rag search "machine learning" --limit 5

# Filter by similarity threshold
uv run rag search "RAG systems" --threshold 0.7

# Filter by metadata (JSONB containment)
uv run rag search "python tutorial" --metadata '{"language":"python","level":"beginner"}'

# Combine collection and metadata filters
uv run rag search "programming guide" --collection tutorials --metadata '{"language":"python"}'

# Verbose output (show full chunk content)
uv run rag search "vector embeddings" --verbose

# Include full source document content
uv run rag search "embeddings" --show-source
```

### Testing & Benchmarking

```bash
# Test similarity scores (validation)
uv run rag test-similarity

# Run performance benchmarks
uv run rag benchmark

# Check database status
uv run rag status
```

## Usage Examples

### Example 1: Build a Knowledge Base

```bash
# Create collection
uv run rag collection create knowledge-base

# Ingest documents
uv run rag ingest directory ./documentation --collection knowledge-base --extensions .md,.txt

# Search
uv run rag search "How do I configure authentication?" --collection knowledge-base --limit 5
```

### Example 2: Compare Similarity Scores

```bash
# Ingest related documents
uv run rag ingest text "PostgreSQL is a relational database" --collection db-test
uv run rag ingest text "MySQL is also a relational database" --collection db-test
uv run rag ingest text "The weather is sunny today" --collection db-test

# Search and compare
uv run rag search "Tell me about databases" --collection db-test --verbose
```

You should see:
- PostgreSQL document: ~0.85 similarity
- MySQL document: ~0.75 similarity
- Weather document: ~0.15 similarity

## Critical Implementation Details

### Vector Normalization

**This is the #1 most important aspect for accurate similarity scores.**

All embeddings are normalized to unit length before storage and during queries:

```python
def normalize_embedding(embedding):
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    return (arr / norm).tolist() if norm > 0 else arr.tolist()
```

Without normalization, you'll see artificially low scores (0.3 range) like ChromaDB.

### Distance to Similarity Conversion

pgvector's `<=>` operator returns **cosine distance** (0-2), not similarity:

```python
similarity = 1.0 - distance
```

This converts to a 0-1 scale where 1.0 = identical, 0.0 = orthogonal.

### HNSW Index Configuration

```sql
CREATE INDEX documents_embedding_idx ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Parameters:
- `m = 16`: Number of connections per node (good default)
- `ef_construction = 64`: Construction-time search depth
- Higher values = better recall but slower indexing

## Expected Results

### Similarity Score Improvements

| Content Type | Expected Range | ChromaDB (Current) | pgvector (POC) |
|-------------|---------------|-------------------|----------------|
| Near-identical | 0.90-0.99 | ~0.3 | 0.90-0.99 |
| Semantically similar | 0.70-0.90 | ~0.3 | 0.70-0.90 |
| Related topics | 0.50-0.70 | ~0.2 | 0.50-0.70 |
| Unrelated | 0.00-0.30 | ~0.1 | 0.00-0.30 |

### Performance Targets

- **Search latency**: < 50ms for 100K documents
- **Recall**: 95%+ with HNSW index
- **Ingestion**: ~2-5 docs/second (OpenAI API limited)

## Troubleshooting

### Database Connection Errors

```bash
# Check if container is running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart container
docker-compose restart

# Reset everything
docker-compose down -v
docker-compose up -d
```

### Low Similarity Scores

If you're seeing low scores (< 0.5 for similar content):

1. **Check normalization**: Run `uv run rag test-similarity`
2. **Verify embeddings**: Check that embeddings have unit length
3. **Check HNSW index**: Ensure index was created properly

```sql
# Connect to database
docker exec -it rag-memory psql -U raguser -d rag_poc

# Check index
\d documents
```

### OpenAI API Errors

```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Check .env file
cat .env

# Test with a simple command
uv run rag ingest text "test" --collection test-col
```

### Import Errors

```bash
# Reinstall dependencies
uv sync

# Check Python version
python --version  # Should be 3.12

# Verify uv installation
uv --version
```

## MCP Server Usage

This RAG system can be accessed by AI agents via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). The MCP server exposes **11 tools** for complete document lifecycle management.

### What is MCP?

MCP is Anthropic's open standard for connecting AI agents to external systems (adopted by Claude Desktop, OpenAI, and Google DeepMind). Think "USB-C for AI" - provides standardized way for agents to discover and use capabilities.

### Quick Start

**Start the server (stdio mode for Claude Desktop):**
```bash
uv run python -m src.mcp.server
```

**Test with MCP Inspector:**
```bash
uv run mcp dev src/mcp/server.py
```

**Multiple transport modes available:**
```bash
# stdio (default - for Claude Desktop)
uv run python -m src.mcp.server --transport stdio

# SSE (for browser clients)
uv run python -m src.mcp.server --transport sse --port 3001

# Streamable HTTP (for web integrations)
uv run python -m src.mcp.server --transport streamable-http --port 3001
```

### Available Tools (11 Total)

#### Core RAG (3 tools)
1. **`search_documents`** - Semantic search with vector similarity
2. **`list_collections`** - Discover available knowledge bases
3. **`ingest_text`** - Add text content with auto-chunking

#### Document Management (4 tools)
4. **`list_documents`** - Browse documents with pagination
5. **`get_document_by_id`** - Retrieve full source document
6. **`update_document`** ⭐ - Edit existing documents
7. **`delete_document`** ⭐ - Remove outdated content

#### Advanced Ingestion (4 tools)
8. **`get_collection_info`** - Collection stats + crawl history
9. **`analyze_website`** ⭐ **NEW** - Sitemap analysis for planning crawls
10. **`ingest_url`** - Crawl web pages with duplicate prevention
11. **`ingest_file`** - Ingest text files from filesystem
12. **`ingest_directory`** - Batch ingest from directory

### Key Features

- **Context window optimization**: Minimal responses by default, optional extended data
- **Duplicate prevention**: `ingest_url` prevents accidental re-crawling
- **Website analysis**: `analyze_website` helps agents discover site structure before crawling
- **Crawl tracking**: `get_collection_info` shows crawl history to avoid duplicates
- **Memory management**: `update_document` and `delete_document` keep knowledge current

### Complete Documentation

📚 **See [docs/MCP_SERVER_GUIDE.md](./docs/MCP_SERVER_GUIDE.md) for:**
- Detailed transport mode setup
- MCP Inspector testing instructions
- Claude Desktop configuration
- Tool reference with examples
- Common workflows
- Troubleshooting guide

### Quick Claude Desktop Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/FULL/PATH/TO/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-your-key-here"
      }
    }
  }
}
```

**Replace `/FULL/PATH/TO/rag-memory` with your actual path** (run `pwd` in project directory).

---

## Development

### Running Tests

```bash
# Run all tests (requires database and API key)
uv run pytest

# Run specific test file
uv run pytest tests/test_embeddings.py -v

# Run without API calls
uv run pytest tests/test_embeddings.py::TestEmbeddingNormalization -v
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run ruff check src/ tests/
```

## Project Structure

```
rag-memory/
├── .env                    # Environment variables (create from .env.example)
├── .env.example           # Environment template
├── .gitignore             # Git ignore patterns
├── .python-version        # Python version for uv
├── docker-compose.yml     # PostgreSQL with pgvector
├── init.sql              # Database schema initialization
├── pyproject.toml        # Project configuration and dependencies
├── README.md             # This file
├── src/
│   ├── __init__.py
│   ├── cli.py           # Command-line interface
│   ├── collections.py   # Collection management
│   ├── database.py      # Database connection
│   ├── embeddings.py    # Embedding generation with normalization
│   ├── ingestion.py     # Document ingestion
│   └── search.py        # Similarity search
└── tests/
    ├── __init__.py
    ├── sample_documents.py  # Test data
    ├── test_embeddings.py   # Embedding tests
    └── test_search.py       # Search tests
```

## Technology Stack

- **Database**: PostgreSQL 17 with pgvector extension
- **Language**: Python 3.12
- **Package Manager**: uv (Astral)
- **Embedding Model**: OpenAI text-embedding-3-small (1536 dims)
- **CLI Framework**: Click + Rich
- **Testing**: pytest
- **Deployment**: Docker Compose

## Cost Analysis

### OpenAI Embedding Costs

**text-embedding-3-small**: $0.02 per 1M tokens

Example usage:
- 10,000 documents × 750 tokens avg = 7.5M tokens
- Cost: **$0.15** for entire corpus
- Per-query: ~$0.00003 (negligible)

**Alternative models**:
- text-embedding-3-large: $0.13/1M tokens (6.5x more expensive)
- Cohere Embed v3: $0.10/1M tokens
- Self-hosted SBERT: Free (infrastructure costs only)

## Migration Path to RAG Retriever

Once POC validates pgvector superiority:

1. **Create adapter layer** matching existing VectorStore interface
2. **Parallel run** both ChromaDB and pgvector for comparison
3. **Data migration script** to transfer embeddings
4. **A/B testing** to validate improvements
5. **Gradual rollout** starting with new collections
6. **Deprecate ChromaDB** after full validation

## Success Criteria

- ✅ Similarity scores in 0.7-0.95 range for good matches
- ✅ Significantly better than ChromaDB's ~0.3 scores
- ✅ Query latency < 100ms for reasonable dataset sizes
- ✅ Easy to integrate into existing RAG Retriever
- ✅ Clear migration path documented

## References

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [LangChain pgvector Integration](https://python.langchain.com/docs/integrations/vectorstores/pgvector)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [HNSW Algorithm](https://arxiv.org/abs/1603.09320)

## License

This is a proof-of-concept project for internal evaluation.

## Support

For issues or questions:
- Check the Troubleshooting section above
- Review Docker logs: `docker-compose logs -f`
- Verify environment setup: `uv run rag status`
- Run validation tests: `uv run rag test-similarity`

---

**Key Takeaway**: The critical difference between ChromaDB (0.3 scores) and pgvector (0.7-0.95 scores) is **vector normalization**. This POC demonstrates that proper normalization combined with HNSW indexing provides the accuracy needed for production RAG systems.
