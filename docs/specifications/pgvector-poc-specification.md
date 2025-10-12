# PostgreSQL pgvector RAG POC - Complete Specification

## Project Overview

This is a proof-of-concept to test PostgreSQL with pgvector extension as a replacement for ChromaDB in a RAG (Retrieval-Augmented Generation) system. The goal is to validate that pgvector provides better similarity search accuracy and addresses the low cosine similarity scores (0.3 range) currently experienced with ChromaDB.

## Current Problem

The existing RAG Retriever using ChromaDB shows unexpectedly low cosine similarity scores (~0.3) even when querying content that should match well with indexed documents. This POC aims to demonstrate that pgvector with proper vector normalization and HNSW indexing provides significantly better similarity scores (0.7-0.95 range for good matches).

## Technical Requirements

### Core Stack
- **Database**: PostgreSQL 17 (latest stable as of Oct 2025) with pgvector extension
- **Language**: Python 3.12+ (Python 3.13 is latest but 3.12 recommended for stability)
- **Embedding Model**: OpenAI text-embedding-3-small (1536 dimensions, $0.02/1M tokens)
  - Alternative: text-embedding-3-large (3072 dimensions, $0.13/1M tokens) for maximum accuracy
  - Rationale: Small model is 6.5x cheaper with near-equivalent performance for RAG
- **Deployment**: Docker Compose
- **Framework**: LangChain 0.3.x with langchain-postgres integration

### Must-Have Features
1. ✅ Docker Compose setup with PostgreSQL + pgvector
2. ✅ Document ingestion with metadata support
3. ✅ Vector embedding generation and storage
4. ✅ Similarity search functionality
5. ✅ Full document retrieval from search results
6. ✅ Collection management (create, list, delete)
7. ✅ CLI interface for testing
8. ✅ Proper vector normalization
9. ✅ HNSW indexing for optimal accuracy

### Nice-to-Have Features
- Simple web UI for visualization (optional)
- Performance benchmarking script
- Comparison with expected similarity scores

## Architecture Design

### Docker Setup
- Single PostgreSQL 17 container with pgvector pre-installed
- Port: 5433 (to avoid conflicts with existing PostgreSQL)
- Persistent volume for data
- Health checks enabled
- Initialization script to set up database schema

### Database Schema

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimensions (3072 for large)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Collection management table
CREATE TABLE collections (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document-collection relationship
CREATE TABLE document_collections (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, collection_id)
);

-- HNSW index for optimal similarity search accuracy
-- m=16 and ef_construction=64 provide good balance of speed and recall
CREATE INDEX documents_embedding_idx ON documents 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Index for metadata queries
CREATE INDEX documents_metadata_idx ON documents USING gin (metadata);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at 
    BEFORE UPDATE ON documents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### Python Application Structure

```
pgvector-rag-poc/
├── docker-compose.yml
├── init.sql
├── pyproject.toml           # Modern Python project configuration with uv
├── uv.lock                  # Lock file for reproducible builds
├── .env.example
├── .env
├── .python-version          # Specify Python version for uv
├── README.md
├── src/
│   ├── __init__.py
│   ├── database.py          # Database connection and setup
│   ├── embeddings.py        # OpenAI embedding generation with normalization
│   ├── ingestion.py         # Document ingestion logic
│   ├── search.py            # Similarity search functionality
│   ├── collections.py       # Collection management
│   └── cli.py              # Command-line interface
├── tests/
│   ├── __init__.py
│   ├── test_embeddings.py
│   ├── test_search.py
│   └── sample_documents.py
└── notebooks/
    └── poc_demo.ipynb      # Jupyter notebook for interactive testing
```

## Implementation Details

### 1. Docker Compose Configuration

**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg17
    container_name: pgvector-rag-poc
    environment:
      POSTGRES_USER: raguser
      POSTGRES_PASSWORD: ragpassword
      POSTGRES_DB: rag_poc
    ports:
      - "5433:5432"
    volumes:
      - pgvector_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U raguser -d rag_poc"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  pgvector_data:
    driver: local
```

### 2. Python Dependencies

**File**: `pyproject.toml`

```toml
[project]
name = "pgvector-rag-poc"
version = "0.1.0"
description = "POC for PostgreSQL pgvector RAG system"
requires-python = ">=3.12"
dependencies = [
    # Core Database
    "psycopg[binary]>=3.2.0",
    "pgvector>=0.3.0",
    "numpy>=2.0.0",
    
    # LangChain (October 2025 stable versions)
    "langchain>=0.3.0,<0.4.0",
    "langchain-postgres>=0.0.12",
    "langchain-openai>=0.2.0",
    "langchain-community>=0.3.0",
    "langchain-core>=0.3.0",
    
    # OpenAI
    "openai>=1.50.0",
    
    # CLI
    "click>=8.1.0",
    "rich>=13.9.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "black>=24.0.0",
    "ruff>=0.6.0",
]
jupyter = [
    "jupyter>=1.1.0",
    "ipykernel>=6.29.0",
]

[project.scripts]
poc = "src.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.black]
line-length = 100
target-version = ["py312"]
```

**File**: `.python-version`

```
3.12
```

### 3. Environment Configuration

**File**: `.env.example`

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=raguser
POSTGRES_PASSWORD=ragpassword
POSTGRES_DB=rag_poc

# Database URL (constructed from above)
DATABASE_URL=postgresql://raguser:ragpassword@localhost:5433/rag_poc
```

### 4. Key Implementation Requirements

#### Vector Normalization
**Critical**: All embeddings MUST be normalized to unit length before storage and during queries.

```python
import numpy as np

def normalize_embedding(embedding: list[float]) -> list[float]:
    """
    Normalize vector to unit length for accurate cosine similarity.
    
    This is CRITICAL for getting proper similarity scores (0.7-0.95 range).
    Without normalization, scores can be artificially low (0.3 range).
    """
    arr = np.array(embedding)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return arr.tolist()
    return (arr / norm).tolist()
```

#### Similarity Score Conversion
The pgvector `<=>` operator returns **cosine distance** (0 to 2), not similarity.
Must convert to similarity score (0 to 1):

```python
# In SQL
similarity_score = 1 - cosine_distance

# In Python
similarity_score = 1 - distance
```

#### HNSW Index Parameters
- `m = 16`: Number of bi-directional links per node (16 is good default)
- `ef_construction = 64`: Size of dynamic candidate list during construction
- Higher values = better recall but slower index build

For production, consider:
- `m = 32` and `ef_construction = 128` for higher accuracy
- `m = 8` and `ef_construction = 32` for faster indexing with lower accuracy

### 5. CLI Commands Required

```bash
# Setup and initialization
poc init              # Initialize database schema
poc status            # Check database connection and stats

# Collection management
poc collection create <name> [--description TEXT]
poc collection list
poc collection delete <name>

# Document ingestion
poc ingest file <path> --collection <name> [--metadata JSON]
poc ingest text "<text>" --collection <name> [--metadata JSON]
poc ingest directory <path> --collection <name> [--extensions .txt,.md]

# Search
poc search "<query>" [--collection NAME] [--limit N] [--threshold FLOAT]
poc search "<query>" --verbose  # Show full documents and metadata

# Testing and validation
poc test-similarity  # Test with known good/bad matches
poc benchmark       # Run performance tests
```

### 6. Test Data

Create sample documents that test various similarity ranges:

**High Similarity (expect 0.85-0.95)**:
- Document: "PostgreSQL is a powerful relational database system"
- Query: "What is PostgreSQL and what type of database is it?"

**Medium Similarity (expect 0.60-0.75)**:
- Document: "Python is a popular programming language for data science"
- Query: "Tell me about machine learning tools"

**Low Similarity (expect 0.20-0.40)**:
- Document: "The weather today is sunny and warm"
- Query: "How do I configure a database?"

### 7. Expected Results

After implementation, we should observe:

**Similarity Score Improvements**:
- Near-identical text: 0.95-0.99 (currently seeing 0.3 with ChromaDB)
- Semantically similar: 0.70-0.90
- Related but different: 0.50-0.70
- Unrelated: 0.00-0.30

**Query Performance**:
- < 50ms for searches under 100K documents
- < 200ms for searches under 1M documents
- Scales well with HNSW indexing

**Recall**:
- 95%+ recall with HNSW index
- Consistent results across queries

## Success Criteria

### Phase 1: Basic Functionality ✅
- [ ] Docker container running PostgreSQL 17 with pgvector
- [ ] Database schema created successfully
- [ ] Python can connect and query database
- [ ] Can generate and store embeddings
- [ ] Can perform basic similarity searches

### Phase 2: Core Features ✅
- [ ] CLI commands all working
- [ ] Document ingestion with metadata
- [ ] Collection management (create, list, delete)
- [ ] Full document retrieval from search results
- [ ] Proper error handling

### Phase 3: Validation ✅
- [ ] Similarity scores in expected range (0.7-0.95 for good matches)
- [ ] Significantly better than current ChromaDB scores (0.3)
- [ ] Search results are relevant and properly ranked
- [ ] Vector normalization confirmed working
- [ ] HNSW index providing good recall

### Phase 4: Documentation ✅
- [ ] README with setup instructions
- [ ] Code comments explaining key concepts
- [ ] Example usage documented
- [ ] Troubleshooting guide
- [ ] Migration notes for RAG Retriever integration

## Known Considerations

### Normalization is Critical
Without vector normalization, you'll see the same low scores as ChromaDB. Every embedding must be normalized before storage and when generating query embeddings.

### Index Build Time
HNSW index builds in background on first query. For large datasets, consider building index explicitly after bulk inserts.

### Connection Pooling
For production, use connection pooling (e.g., pgBouncer or asyncpg). POC can use simple connections.

### Memory Usage
Each 3072-dimension vector uses ~12KB of memory. Plan accordingly:
- 100K docs ≈ 1.2GB
- 1M docs ≈ 12GB
- 10M docs ≈ 120GB

### Query Performance
- HNSW provides approximate nearest neighbor (ANN) search
- 95%+ recall means you might miss 5% of true nearest neighbors
- Trade-off between speed and accuracy is configurable

## Security Notes

For POC:
- Using simple passwords (fine for local testing)
- No SSL/TLS (fine for localhost)
- No authentication beyond database password

For production:
- Use strong passwords or certificate authentication
- Enable SSL/TLS
- Use environment variables or secrets management
- Restrict network access

## Migration Path to RAG Retriever

Once POC validates pgvector:

1. **Create adapter layer** in RAG Retriever that matches existing VectorStore interface
2. **Parallel run** both ChromaDB and pgvector temporarily
3. **Data migration script** to move existing embeddings
4. **A/B testing** to compare results
5. **Gradual rollout** starting with new collections
6. **Deprecate ChromaDB** once fully validated

The POC code should serve as reference implementation for the migration.

## Reference Information

### pgvector Documentation
- GitHub: https://github.com/pgvector/pgvector
- Distance operators: `<->` (L2), `<#>` (inner product), `<=>` (cosine)
- Indexing: IVFFlat vs HNSW comparison

### LangChain Integration
- Package: `langchain-postgres`
- Docs: https://python.langchain.com/docs/integrations/vectorstores/pgvector

### Embedding Model Selection (Researched October 2025)

#### **Recommended: OpenAI text-embedding-3-small**
- **Dimensions**: 1536
- **Cost**: $0.02 per 1M tokens
- **Performance**: Excellent for RAG applications
- **Benchmark**: Strong performance on MTEB leaderboard
- **Why**: Best cost/performance ratio for POC and production

#### **Alternative Options Evaluated:**

**1. OpenAI text-embedding-3-large** (Premium Option)
- Dimensions: 3072
- Cost: $0.13 per 1M tokens (6.5x more expensive)
- Performance: 10-15% better on complex semantic tasks
- Use when: Maximum accuracy is critical, cost is secondary

**2. Cohere Embed v3** (Strong Competitor)
- Dimensions: 1024
- Cost: $0.10 per million tokens (5x more than small)
- Performance: Excellent for noisy real-world data, 100+ languages
- Use when: Multilingual support or noisy data handling needed

**3. Mistral E5-Mistral-7B-Instruct**
- Dimensions: Variable
- Cost: $0.10 per million tokens
- Performance: Best for instruction-following tasks
- Use when: Complex query understanding required

**4. Open Source Options** (Self-Hosted)
- **SBERT**: Free, good performance, 384-768 dimensions
- **Universal Sentence Encoder**: Free, TensorFlow-based
- Use when: Want to avoid API costs, have infrastructure

#### **Cost Analysis for 10K Documents (~7.5M tokens)**
- **text-embedding-3-small**: $0.15 (⭐ Recommended)
- **Cohere Embed v3**: $0.75
- **text-embedding-3-large**: $0.975
- **SBERT/USE**: $0 (infrastructure costs only)

#### **Why text-embedding-3-small for POC?**
1. **Cost-effective**: 6.5x cheaper than large
2. **Proven performance**: Used in production by many RAG systems
3. **Easy upgrade path**: Can switch to large if needed
4. **The 0.3 score issue is normalization**: Not model quality
5. **Fast validation**: Lower costs = test more iterations

#### **When to Consider Upgrading:**
- POC shows good results but need 10-15% accuracy boost
- Working with highly technical/specialized content
- Budget allows for premium embedding quality
- After confirming normalization and pgvector are working correctly

## Deliverables

1. ✅ Working Docker Compose setup
2. ✅ Complete database schema with indexes
3. ✅ Python CLI application with all core features
4. ✅ Test suite with sample documents
5. ✅ README with setup and usage instructions
6. ✅ Jupyter notebook demonstrating functionality
7. ✅ Documentation of results and lessons learned
8. ✅ Recommendations for RAG Retriever integration

## Setup Instructions

### Prerequisites
- Docker and Docker Compose installed
- `uv` package manager installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- OpenAI API key

### Quick Start
```bash
# 1. Clone/create the repository
git init pgvector-rag-poc && cd pgvector-rag-poc

# 2. Set Python version
echo "3.12" > .python-version

# 3. Initialize uv project (creates pyproject.toml)
uv init --python 3.12

# 4. Install dependencies with uv (super fast!)
uv sync

# 5. Set up environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 6. Start PostgreSQL with pgvector
docker-compose up -d

# 7. Initialize database
uv run poc init

# 8. Test the system
uv run poc test-similarity
```

## Timeline Estimate

- **Day 1**: Docker setup, database schema, basic connection
- **Day 2**: Embedding generation, ingestion, normalization
- **Day 3**: Search functionality, CLI commands
- **Day 4**: Testing, validation, documentation
- **Total**: 4 days for complete POC

## Questions to Answer

1. Do similarity scores improve from 0.3 range to 0.7-0.95 range?
2. Is search accuracy better than ChromaDB?
3. Is query performance acceptable?
4. How easy is collection management?
5. Does metadata filtering work well?
6. Can we store and retrieve full documents efficiently?
7. Is the integration path to RAG Retriever clear?

## Success Metrics

- **Primary**: Similarity scores in 0.7-0.95 range for good matches ✅
- **Secondary**: < 100ms query latency for 100K documents ✅
- **Tertiary**: 95%+ recall with HNSW index ✅
- **Bonus**: Simpler code than ChromaDB implementation ✅

---

## Notes for Implementation

- Start with smallest working version first
- Add features incrementally
- Test similarity scores early and often
- Document any surprises or gotchas
- Keep it simple - this is a POC, not production code
- Focus on validating the core hypothesis: pgvector > ChromaDB for similarity accuracy

