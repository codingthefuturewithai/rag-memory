# Vector Search

This guide explains how semantic search works in RAG Memory.

## What is Semantic Search?

Semantic search finds documents by meaning, not keywords. It understands that "authenticate users" and "login validation with OAuth" are related concepts even though they share no words.

**Traditional Keyword Search:**
- Matches exact words
- Misses synonyms and related concepts
- Returns documents containing search terms

**Semantic Search:**
- Matches meaning and intent
- Finds related concepts
- Returns conceptually similar content

## How It Works

### 1. Embedding Generation

Text is converted to vectors (lists of numbers) that represent meaning:

```
Input: "PostgreSQL is a powerful database"
Output: [0.023, -0.145, 0.891, ..., 0.234]  # 1536 numbers
```

Each number captures a dimension of meaning. Similar concepts have similar vectors.

### 2. Vector Normalization

Vectors are normalized to unit length (magnitude = 1). This is critical for accurate similarity scoring.

```python
# Without normalization
vector = [0.5, 0.5, 0.5]
magnitude = sqrt(0.5² + 0.5² + 0.5²) = 0.866

# After normalization
normalized = [0.577, 0.577, 0.577]
magnitude = 1.0
```

Normalization ensures similarity scores are accurate and comparable.

### 3. Storage

Embeddings are stored in PostgreSQL with pgvector extension:

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536),  -- pgvector type
    ...
);

CREATE INDEX ON document_chunks
USING hnsw (embedding vector_cosine_ops);
```

HNSW (Hierarchical Navigable Small World) index enables fast similarity search.

### 4. Query Processing

When you search:

1. Query text is embedded (same process as documents)
2. Query embedding is normalized
3. pgvector finds nearest neighbors using HNSW index
4. Results ranked by cosine similarity

```sql
SELECT content, 1 - (embedding <=> query_embedding) as similarity
FROM document_chunks
WHERE collection_id = ?
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

The `<=>` operator computes cosine distance. Similarity = 1 - distance.

## Embeddings Model

**Model:** text-embedding-3-small (OpenAI)
**Dimensions:** 1536
**Context window:** 8191 tokens

This model balances quality and cost. See OpenAI pricing documentation for current rates.

## Document Chunking

Large documents are split into chunks before embedding. This improves search precision.

### Why Chunk?

**Problem without chunking:**
- Long documents have low overall similarity to queries
- Relevant section buried in irrelevant context
- Hard to pinpoint exact information

**Solution with chunking:**
- Each section embedded independently
- Search finds specific relevant chunk
- Higher similarity scores for matches

### Chunking Strategy

**Default settings:**
- Chunk size: 1000 characters
- Overlap: 200 characters
- Separators: Headers → Paragraphs → Sentences → Words

**How it works:**
```
Original document (5000 characters):
"Introduction... [0-1200]
Setup instructions... [1000-2200]
Configuration... [2000-3200]
Advanced topics... [3000-4200]
Conclusion... [4000-5000]"

Chunks created:
Chunk 1: chars 0-1000 (Introduction + start of Setup)
Chunk 2: chars 800-1800 (end of Intro + Setup + start of Config)
Chunk 3: chars 1600-2600 (end of Setup + Config + start of Advanced)
Chunk 4: chars 2400-3400 (end of Config + Advanced)
Chunk 5: chars 3200-4200 (Advanced + start of Conclusion)
Chunk 6: chars 4000-5000 (end of Advanced + Conclusion)
```

Overlap prevents concepts from being split across boundaries.

### Configurable Chunking

Adjust for different content types:

**Code files:**
```bash
rag ingest file code.py \
  --collection code \
  --chunk-size 800 \
  --chunk-overlap 100
```

**Web pages:**
```bash
rag ingest url https://docs.example.com \
  --collection docs \
  --chunk-size 2500 \
  --chunk-overlap 300
```

**Long documents:**
```bash
rag ingest file manual.pdf \
  --collection manuals \
  --chunk-size 1500 \
  --chunk-overlap 250
```

## Similarity Scores

Similarity scores range from 0.0 (unrelated) to 1.0 (identical).

### Score Interpretation

**0.90-1.00: Near-identical**
- Exact match or close rephrasing
- Example: "PostgreSQL database" vs "PostgreSQL DB"

**0.70-0.89: Highly relevant**
- What you're looking for
- Example: "user authentication" vs "OAuth login flow"

**0.50-0.69: Related**
- Relevant but less direct
- Example: "error handling" vs "exception logging"

**0.30-0.49: Somewhat related**
- Might be useful
- Example: "Python tutorial" vs "programming concepts"

**0.00-0.29: Loosely related**
- Usually noise
- Example: "database query" vs "weather forecast"

### Threshold Filtering

Control results with thresholds:

**Strict (0.7+):**
```bash
rag search "authentication" --threshold 0.7
# Only high-confidence matches
```

**Balanced (0.5+):**
```bash
rag search "authentication" --threshold 0.5
# Good mix of precision and recall
```

**Exploratory (0.3+):**
```bash
rag search "authentication" --threshold 0.3
# Cast wide net for discovery
```

**No threshold:**
```bash
rag search "authentication" --limit 10
# Top 10 results regardless of score
```

## Search Features

### Collection Scoping

Search within specific collections:

```bash
# Search all collections
rag search "deployment process"

# Search specific collection
rag search "deployment process" --collection devops-docs
```

### Metadata Filtering

Filter by document metadata:

```bash
# Filter by document type
rag search "API endpoints" \
  --metadata '{"doc_type": "api-reference"}'

# Filter by version
rag search "configuration" \
  --metadata '{"version": "2.0"}'

# Multiple filters
rag search "authentication" \
  --metadata '{"doc_type": "guide", "status": "approved"}'
```

### Result Limits

Control number of results:

```bash
# Default (10 results)
rag search "error handling"

# More results
rag search "error handling" --limit 50

# Fewer results
rag search "error handling" --limit 3
```

## Query Best Practices

### Use Natural Language

**Good queries (natural language):**
- "How do I authenticate users in the API?"
- "What are the configuration options for backups?"
- "Show me examples of error handling"

**Poor queries (keywords):**
- "auth API users"
- "config backup options"
- "error handling examples"

Semantic search works best with complete questions and sentences.

### Be Specific

**Vague:**
- "database"

**Specific:**
- "How do I optimize PostgreSQL query performance?"

**Vague:**
- "errors"

**Specific:**
- "What causes connection timeout errors in production?"

### Tune Thresholds

Start with default, adjust based on results:

1. **Too many irrelevant results?** Increase threshold (0.6, 0.7)
2. **Too few results?** Decrease threshold (0.4, 0.3)
3. **Need everything?** Remove threshold, use --limit

## Performance

### Search Speed

**Typical search time:** 100-500ms
- Includes: query embedding + vector search + ranking
- HNSW index provides sub-linear search time

**Factors affecting speed:**
- Collection size (more documents = slightly slower)
- Chunk count (index size)
- Concurrent queries

### Optimizations

**HNSW Index:**
- Created automatically during setup
- Provides fast approximate nearest neighbor search
- Accuracy vs speed tradeoff controlled by index parameters

**Vector Normalization:**
- Critical for accuracy
- All vectors stored and queried at unit length
- Enables accurate cosine similarity

## Advanced Topics

### Collections

Organize documents by domain:

```bash
# Separate collections for different topics
rag collection create api-docs --description "API documentation"
rag collection create guides --description "User guides"
rag collection create internal --description "Internal docs"

# Search scoped to relevant collection
rag search "authentication" --collection api-docs
```

Collections partition the search space and improve relevance.

### Re-ingestion

Update content when documents change:

```bash
# Update single document
rag document update 42 --content "Updated content here"

# Re-crawl web documentation
rag ingest url https://docs.example.com \
  --collection docs \
  --mode recrawl \
  --follow-links
```

Updates trigger re-chunking and re-embedding.

## Troubleshooting

### Low Similarity Scores

**Causes:**
- Query too vague
- Missing relevant documents
- Wrong collection

**Solutions:**
- Make query more specific
- Ingest more content
- Check collection scoping

### No Results

**Causes:**
- Threshold too high
- Collection empty
- Database issues

**Solutions:**
```bash
# Check collection has documents
rag collection info your-collection

# Remove threshold
rag search "query" --collection your-collection

# Check database
rag status
```

### Unexpected Results

**Causes:**
- Query ambiguous
- Document metadata incorrect
- Need threshold tuning

**Solutions:**
- Rephrase query more specifically
- Check document content and metadata
- Adjust threshold up or down

See TROUBLESHOOTING.md for more issues and solutions.

## Next Steps

- **CLI Guide** - See CLI_GUIDE.md for search commands
- **MCP Guide** - See MCP_GUIDE.md for agent integration
- **Knowledge Graph** - See KNOWLEDGE_GRAPH.md for relationship queries
