# RAG Search Optimization Results

**Date:** 2025-10-11
**Collection:** claude-agent-sdk (391 documents, 2,093 chunks)
**Embedding Model:** text-embedding-3-small (1536 dimensions)
**Test Queries:** 20 queries across 4 categories (7 with ground truth labels)

## Executive Summary

**Baseline vector-only search is the optimal approach for this dataset.**

Two advanced retrieval optimizations were tested:
- **Phase 1: Hybrid Search** (vector + keyword + RRF)
- **Phase 2: Multi-Query Retrieval** (query expansion + RRF)

**Both optimizations decreased performance** compared to baseline:
- Lower recall, precision, and MRR
- Significantly higher latency (65% - 138% slower)
- Added complexity without quality improvement

**Recommendation:** Continue using baseline vector search with text-embedding-3-small.

---

## Benchmark Results

### Metrics Comparison

| Metric | Baseline | Phase 1 (Hybrid) | Phase 2 (Multi-Query) | Winner |
|--------|----------|------------------|----------------------|--------|
| **Recall@5 (any relevant)** | **81.0%** | 76.2% ↓ | 76.2% ↓ | Baseline |
| **Recall@5 (highly relevant)** | **78.6%** | 78.6% = | 71.4% ↓ | Baseline |
| **Precision@5 (any relevant)** | **57.1%** | 45.7% ↓ | 51.4% ↓ | Baseline |
| **Precision@5 (highly relevant)** | **54.3%** | 45.7% ↓ | 48.6% ↓ | Baseline |
| **MRR (any relevant)** | **0.679** | 0.583 ↓ | 0.560 ↓ | Baseline |
| **MRR (highly relevant)** | **0.679** | 0.583 ↓ | 0.512 ↓ | Baseline |
| **nDCG@10** | **1.471** | 1.159 ↓ | 1.315 ↓ | Baseline |
| **Avg Latency** | **413.6ms** | 684.3ms ↑65% | 982.5ms ↑138% | Baseline |

**Legend:** ↑ = increase, ↓ = decrease, = = no change

### Per-Query Analysis

**Queries where all methods performed equally:**
- `wf-03` (GitHub Actions): 100% recall across all methods
- `abbr-01` (MCP server setup): 100% recall across all methods
- `abbr-02` (SDK migration): 100% recall across all methods
- `poor-01` (how make agent work): 100% recall, but MRR varies
- `tech-03` (custom hooks): 100% recall across all methods

**Queries where baseline outperformed:**
- `wf-01` (Claude Code configuration): Baseline 67% recall vs 33% for both optimizations
- `tech-02` (differences Claude Code vs SDK): All methods failed (0% recall)

**Key Insight:** The optimizations don't improve difficult queries and hurt performance on easier ones.

---

## Phase 1: Hybrid Search

**Approach:** Combine vector similarity search with PostgreSQL full-text search using Reciprocal Rank Fusion (RRF).

**Implementation:**
- Database migration: Added `content_tsv tsvector` column with GIN index
- Keyword search: PostgreSQL `plainto_tsquery` with `ts_rank`
- Vector search: Standard cosine similarity with HNSW index
- Fusion: RRF algorithm (k=60) to merge both rankings

**Why it failed:**
- Keyword search adds noise for this documentation dataset
- Technical terms and abbreviations don't benefit from full-text matching
- Well-structured documents already have clear semantic meaning captured by embeddings
- The additional retrieval (keyword + vector) increases latency without improving quality

**Code preserved:** Hybrid search is still available via `--hybrid` flag for experimentation.

---

## Phase 2: Multi-Query Retrieval

**Approach:** Generate multiple variations of the user query and merge results using RRF.

**Implementation:**
- Query expansion: Rule-based generation of 3 query variations
  - Add "documentation guide" context
  - Rephrase as question/statement
  - Add "setup configuration" specificity
- Retrieval: Run vector search for each variation (3x API calls)
- Fusion: RRF algorithm (k=60) to merge rankings

**Why it failed:**
- Simple rule-based query expansion is too naive
- Variations don't capture semantic nuances ("SDK migration" → "guide for SDK migration" doesn't help)
- 3x embedding API calls = 3x latency
- The original query is already well-formed enough for embeddings to work

**Potential improvements (not pursued):**
- Use LLM to generate more sophisticated query variations
- Use HyDE (Hypothetical Document Embeddings) instead of query variations
- However, this would add even more latency and cost

**Code preserved:** Multi-query search is available via `--multi-query` flag.

---

## Why Baseline Works So Well

**High-quality dataset:**
- Well-structured documentation with clear sections
- Consistent terminology and formatting
- Proper markdown hierarchy

**Strong embedding model:**
- text-embedding-3-small captures semantic meaning effectively
- 1536 dimensions provide good representation
- Normalized vectors + HNSW indexing = fast, accurate retrieval

**Appropriate chunking:**
- ~1000 char chunks with 200 char overlap
- Hierarchical splitting (headers → paragraphs → sentences)
- Each chunk has sufficient context

**Result:** 81% recall means 4 out of 5 relevant documents appear in top 5 results. This is already excellent performance.

---

## Recommendations

### For Production Use

**Use baseline vector search:**
```bash
uv run poc search "your query" --collection name --limit 10
```

**Do NOT use:**
- `--hybrid` flag (worse performance, higher latency)
- `--multi-query` flag (worse performance, much higher latency)

### For Future Optimization

**If you must improve recall beyond 81%:**

1. **Re-Ranking (Phase 3 - not implemented):**
   - Keep baseline retrieval (fast, accurate)
   - Add cross-encoder re-ranker for top-K results
   - Only re-rank top 20-50 results (minimal latency impact)
   - Models: `cross-encoder/ms-marco-MiniLM-L-6-v2`

2. **LLM-based Query Expansion:**
   - Use LLM to generate sophisticated query variations
   - Focus on capturing user intent, not just rewording
   - But: adds significant latency and cost

3. **Improve Ground Truth:**
   - Current ground truth only covers 7/20 queries
   - More labeled queries = better evaluation
   - Consider using LLM to assist with labeling

### What NOT to Do

❌ Don't add keyword search (proved to add noise)
❌ Don't use rule-based query expansion (too naive)
❌ Don't optimize latency at the cost of quality
❌ Don't add complexity without measuring improvement

---

## Technical Details

### Ground Truth Methodology

**Document-level matching:**
- Ground truth uses `source_document_id` not exact `chunk_id`
- For queries like "SDK migration", ANY chunk from Migration Guide doc is relevant
- More robust than chunk-level matching across different search methods

**Relevance levels:**
- `highly_relevant`: Directly answers the query, primary source
- `relevant`: Contains useful related information, secondary source
- `not_relevant`: Off-topic or tangentially related

**Metrics:**
- **Recall@K**: What fraction of relevant docs appear in top K?
- **Precision@K**: What fraction of top K results are relevant?
- **MRR**: Mean Reciprocal Rank - 1 / rank of first relevant document
- **nDCG@K**: Normalized Discounted Cumulative Gain - considers ranking quality

### Database Schema

**Chunking tables:**
- `source_documents`: Full original documents
- `document_chunks`: Searchable chunks with embeddings
- `chunk_collections`: Many-to-many relationship

**Indexes:**
- HNSW on `document_chunks.embedding` (m=16, ef_construction=64)
- GIN on `document_chunks.content_tsv` (for hybrid search)
- B-tree on `document_chunks.source_document_id`

### File Structure

```
src/retrieval/
├── search.py                    # Baseline vector search
├── hybrid_search.py             # Phase 1: Hybrid search
└── multi_query.py               # Phase 2: Multi-query retrieval

tests/benchmark/
├── test_runner.py               # Baseline benchmark
├── run_phase1.py                # Phase 1 benchmark
├── run_phase2.py                # Phase 2 benchmark
└── metrics.py                   # Evaluation metrics

test-data/
├── test-queries.yaml            # 20 test queries
├── ground-truth-simple.yaml     # Ground truth labels (7 queries)
└── collection-snapshot.json     # Locked test collection state

migrations/
└── 001_add_fulltext_search.sql  # PostgreSQL full-text search setup
```

---

## Lessons Learned

1. **Measure, don't assume:** Both optimizations seemed promising in theory but failed in practice.

2. **Baseline matters:** Starting with a good embedding model + proper chunking gives 81% recall. Hard to beat.

3. **Dataset characteristics drive optimization:** Well-structured documentation doesn't benefit from keyword search or query expansion.

4. **Latency is a quality metric:** 138% slower retrieval is not acceptable for marginal quality changes.

5. **Scientific method works:** Ground truth labels + standardized metrics enabled objective comparison.

6. **Keep it simple:** The simplest solution (vector-only search) won.

---

## Cost Analysis

**Per-query cost (OpenAI API):**
- Baseline: 1 embedding call = $0.00003
- Phase 1 (Hybrid): 1 embedding call = $0.00003 (same cost, worse quality)
- Phase 2 (Multi-Query): 3 embedding calls = $0.00009 (3x cost, worse quality)

**Database overhead:**
- Baseline: 1 vector search query
- Phase 1: 1 vector + 1 full-text search query
- Phase 2: 3 vector search queries

**Winner:** Baseline (lowest cost, best quality, fastest)

---

## Conclusion

**The baseline vector search is the optimal approach for this RAG application.**

Advanced retrieval optimizations (hybrid search, multi-query retrieval) added complexity, latency, and cost without improving quality. The combination of:
- High-quality documentation dataset
- Strong embedding model (text-embedding-3-small)
- Proper chunking strategy
- HNSW indexing

...already provides excellent retrieval performance (81% recall, 0.679 MRR, 414ms latency).

**Recommendation:** Deploy baseline vector search to production. Monitor real-world user queries. Only revisit optimization if user feedback indicates poor retrieval quality.

---

## Appendix: Running Benchmarks

**Baseline:**
```bash
uv run python tests/benchmark/test_runner.py --baseline
```

**Phase 1 (Hybrid):**
```bash
uv run python tests/benchmark/run_phase1.py
```

**Phase 2 (Multi-Query):**
```bash
uv run python tests/benchmark/run_phase2.py
```

**Results saved to:** `test-results/` directory with timestamp

**Ground truth:** `test-data/ground-truth-simple.yaml`

---

**Generated:** 2025-10-11
**Collection:** claude-agent-sdk
**Test Queries:** 20 (7 with ground truth)
**Conclusion:** Baseline vector search wins 🏆
