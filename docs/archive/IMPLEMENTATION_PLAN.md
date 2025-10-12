# Incremental RAG Optimization Implementation Plan

## Project Context
- **Goal**: Transform POC into production RAG system with measurable search improvements
- **Approach**: One optimization at a time, with before/after testing
- **Test Collection**: `claude-agent-sdk` (391 documents, locked - no updates during implementation)
- **Method**: Controlled variables - only change the optimization method being tested

---

## Phase 0: Foundation & Baseline (Prep Work)

### 0.1: Create Feature Branch
```bash
git checkout -b feature/rag-search-optimizations
```

### 0.2: Lock Test Collection
- Document current state of `claude-agent-sdk` collection
- Create snapshot metadata file: `test-data/collection-snapshot.json`
- **No modifications** to this collection during implementation

### 0.3: Create Test Query Suite
Design 15-20 test queries covering different scenarios:

**Well-Formed Queries** (baseline performance):
1. "Claude Code configuration options"
2. "Model Context Protocol setup"
3. "GitHub Actions integration guide"
4. "troubleshooting connection errors"

**Abbreviation Queries** (will benefit from hybrid search):
5. "MCP server setup"
6. "SDK migration"
7. "CI/CD integration"
8. "API auth"

**Poorly Worded Queries** (will benefit from multi-query):
9. "how make agent work"
10. "setup tool thing"
11. "fix code not working"
12. "connect stuff together"

**Technical/Specific Queries** (will benefit from re-ranking):
13. "configuring IAM roles for Bedrock access"
14. "differences between Claude Code and Claude Agent SDK"
15. "implementing custom hooks for git operations"

**Save as**: `test-data/test-queries.yaml`

### 0.4: Create Baseline Test Runner
Build automated test harness:
- `tests/benchmark/test_runner.py` - Executes all test queries
- Captures: query, top 5 results (ID, similarity, content preview), latency
- Outputs: `test-results/baseline-YYYYMMDD-HHMMSS.json`

### 0.5: Run Baseline Tests
Execute baseline with current vector-only search:
```bash
uv run pytest tests/benchmark/test_runner.py --baseline
```
- Captures current performance metrics
- This is your "control group" for all comparisons

**Deliverable**: Baseline results JSON file for comparison

---

## Phase 1: Hybrid Search Implementation (Highest ROI)

### 1.1: Database Schema Update
**File**: `migrations/001_add_fulltext_search.sql`

```sql
-- Add tsvector column for full-text search
ALTER TABLE document_chunks
ADD COLUMN content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Create GIN index for fast text search
CREATE INDEX document_chunks_content_tsv_idx
ON document_chunks USING gin(content_tsv);
```

**Verify**:
```bash
docker exec -it pgvector-rag-poc psql -U raguser -d rag_poc -f migrations/001_add_fulltext_search.sql
```

### 1.2: Implement Hybrid Search Module
**File**: `src/retrieval/hybrid_search.py`

Components:
- `keyword_search()` - PostgreSQL full-text search
- `vector_search()` - Current vector similarity search
- `reciprocal_rank_fusion()` - RRF merging algorithm
- `hybrid_search()` - Main entry point

### 1.3: Update CLI with Hybrid Flag
**File**: `src/cli.py`

Add `--hybrid` flag to search command:
```bash
uv run poc search "query" --hybrid
```

### 1.4: Create Phase 1 Tests
**File**: `tests/benchmark/test_phase1_hybrid.py`

Test cases:
- Abbreviations: "MCP" should find "Model Context Protocol"
- Exact matches: "GitHub Actions" with exact keyword
- RRF algorithm correctness
- Performance: hybrid vs vector-only latency

### 1.5: Run Phase 1 Benchmark
```bash
uv run pytest tests/benchmark/test_runner.py --phase1
```

Generates: `test-results/phase1-hybrid-YYYYMMDD-HHMMSS.json`

### 1.6: Compare Results
**Tool**: `tests/benchmark/compare_results.py`

```bash
uv run python tests/benchmark/compare_results.py \
  --baseline test-results/baseline-*.json \
  --phase1 test-results/phase1-hybrid-*.json
```

**Outputs**:
- Recall improvement % (expected: +30-40%)
- Query-by-query comparison
- Latency impact
- Rich formatted report

### 1.7: Phase 1 Decision Point
**If successful** (>20% improvement):
- Merge to main: `git merge feature/rag-search-optimizations`
- Tag: `v0.2.0-hybrid-search`
- Proceed to Phase 2

**If unsuccessful**:
- Debug and iterate
- Do NOT proceed until Phase 1 works

---

## Phase 2: Multi-Query Retrieval Implementation

### 2.1: Add Dependencies
Update `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "langchain>=0.3.0",  # Already have this
]
```

### 2.2: Implement Multi-Query Module
**File**: `src/retrieval/multi_query.py`

Components:
- `generate_query_variations()` - LLM-based query expansion
- `multi_query_search()` - Search with all variations + RRF merge
- Uses gpt-4o-mini for cost efficiency

### 2.3: Update CLI with Multi-Query Flag
```bash
uv run poc search "query" --hybrid --multi-query
uv run poc search "query" --hybrid --multi-query --show-variations
```

### 2.4: Create Phase 2 Tests
**File**: `tests/benchmark/test_phase2_multiquery.py`

Test cases:
- Query variation quality (3 meaningful variations)
- Poorly worded queries improvement
- Recall vs Phase 1
- Cost tracking (OpenAI API calls)

### 2.5: Run Phase 2 Benchmark
```bash
uv run pytest tests/benchmark/test_runner.py --phase2
```

Generates: `test-results/phase2-multiquery-YYYYMMDD-HHMMSS.json`

### 2.6: Three-Way Comparison
```bash
uv run python tests/benchmark/compare_results.py \
  --baseline test-results/baseline-*.json \
  --phase1 test-results/phase1-hybrid-*.json \
  --phase2 test-results/phase2-multiquery-*.json
```

**Expected**: Phase 2 > Phase 1 > Baseline for recall

### 2.7: Phase 2 Decision Point
**If successful** (>15% improvement over Phase 1):
- Merge to main
- Tag: `v0.3.0-multi-query`
- Proceed to Phase 3

---

## Phase 3: Re-Ranking Implementation (Optional)

### 3.1: Add Dependencies
```toml
dependencies = [
    # ... existing ...
    "cohere>=5.0.0",  # For Cohere API
    "sentence-transformers>=2.0.0",  # For local cross-encoder
]
```

### 3.2: Implement Re-Ranking Module
**File**: `src/retrieval/reranking.py`

Support both:
- Cohere API (fast, costs $1/1000 queries)
- Local cross-encoder (free, slower)

### 3.3: Update CLI with Rerank Flag
```bash
uv run poc search "query" --hybrid --multi-query --rerank cohere
uv run poc search "query" --hybrid --multi-query --rerank cross-encoder
```

### 3.4: Create Phase 3 Tests
Test both reranking methods separately:
- `test_phase3_rerank_cohere.py`
- `test_phase3_rerank_crossencoder.py`

### 3.5: Run Phase 3 Benchmarks
```bash
# Test Cohere
uv run pytest tests/benchmark/test_runner.py --phase3-cohere

# Test Cross-Encoder
uv run pytest tests/benchmark/test_runner.py --phase3-crossencoder
```

### 3.6: Four-Way Comparison
Compare all methods including both reranking approaches.

### 3.7: Phase 3 Decision Point
Choose best reranking method (or decide not to use re-ranking).

---

## Phase 4: Configuration & Production Readiness

### 4.1: Create Configuration System
**File**: `config.yaml`

```yaml
search:
  default_method: "hybrid+multiquery"  # or "vector", "hybrid", etc.

  hybrid_search:
    enabled: true
    vector_weight: 0.5
    keyword_weight: 0.5
    rrf_k: 60

  multi_query:
    enabled: true
    num_variations: 3
    model: "gpt-4o-mini"

  reranking:
    enabled: false
    method: "cross_encoder"  # or "cohere"
```

### 4.2: Environment-Based Config
Support `.env` overrides for production:
```bash
SEARCH_METHOD=hybrid+multiquery
ENABLE_RERANKING=true
RERANK_METHOD=cohere
```

### 4.3: API Endpoint Design (Future)
Prepare for REST API:
```python
POST /api/search
{
  "query": "...",
  "collection": "...",
  "method": "auto",  # uses config default
  "limit": 5
}
```

### 4.4: Documentation
- Update CLAUDE.md with new search methods
- Create BENCHMARKS.md with test results
- Migration guide for existing users

---

## File Structure

```
rag-pgvector-poc/
├── migrations/
│   └── 001_add_fulltext_search.sql
├── src/
│   └── retrieval/
│       ├── hybrid_search.py       # Phase 1
│       ├── multi_query.py         # Phase 2
│       └── reranking.py           # Phase 3
├── tests/
│   └── benchmark/
│       ├── test_runner.py         # Main test harness
│       ├── compare_results.py     # Comparison tool
│       ├── test_phase1_hybrid.py
│       ├── test_phase2_multiquery.py
│       └── test_phase3_rerank*.py
├── test-data/
│   ├── collection-snapshot.json   # Locked collection state
│   └── test-queries.yaml          # Test query suite
├── test-results/                  # Git-ignored
│   ├── baseline-*.json
│   ├── phase1-*.json
│   ├── phase2-*.json
│   └── phase3-*.json
└── config.yaml                     # Phase 4
```

---

## Success Metrics

### Phase 1 Success:
- ✅ +25-40% recall improvement on abbreviation queries
- ✅ No regression on well-formed queries
- ✅ <50ms additional latency

### Phase 2 Success:
- ✅ +15-30% recall improvement over Phase 1
- ✅ Better handling of poorly worded queries
- ✅ <500ms additional latency (includes LLM call)

### Phase 3 Success:
- ✅ +10-20% precision improvement
- ✅ Better ordering of results
- ✅ Cost/performance trade-off acceptable

---

## Timeline Estimate

- **Phase 0**: 4-6 hours (foundation, test suite, baseline)
- **Phase 1**: 6-8 hours (implementation + testing)
- **Phase 2**: 4-6 hours (builds on Phase 1 patterns)
- **Phase 3**: 6-8 hours (two implementations to compare)
- **Phase 4**: 3-4 hours (config system, docs)

**Total**: 23-32 hours over ~1-2 weeks

---

## Risk Mitigation

1. **Feature branch** - Easy to discard if things go wrong
2. **Incremental merges** - Each phase is independently valuable
3. **Locked test data** - No moving targets
4. **Automated comparisons** - Objective measurements
5. **Rollback plan** - Each phase can be disabled via config

---

## Key Decision Points

1. After Phase 0: "Is our test suite comprehensive enough?"
2. After Phase 1: "Is hybrid search worth keeping?"
3. After Phase 2: "Is multi-query worth the cost?"
4. After Phase 3: "Which reranking method (if any) should we use?"

---

## Implementation Status

- [ ] Phase 0: Foundation & Baseline
- [ ] Phase 1: Hybrid Search
- [ ] Phase 2: Multi-Query Retrieval
- [ ] Phase 3: Re-Ranking
- [ ] Phase 4: Production Readiness
