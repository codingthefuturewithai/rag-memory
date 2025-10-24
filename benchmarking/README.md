# Knowledge Graph Relationship Search Benchmarking

This directory contains tools and data for benchmarking the Knowledge Graph relationship search functionality with various threshold configurations.

## Setup

### Configure OpenAI API Key

1. Copy the example environment file:
   ```bash
   cp benchmarking/.env.example benchmarking/.env
   ```

2. Add your OpenAI API key to `benchmarking/.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

The script will load the API key from:
1. `benchmarking/.env` (if it exists), or
2. Project root `.env` (fallback)

## Directory Structure

```
benchmarking/
├── README.md                    # This file
├── .env.example                 # Template for environment variables
├── .gitignore                   # Git ignore for .env and reports
├── data/
│   ├── test_documents/          # Test data files
│   │   ├── ai_ml_comprehensive.txt
│   │   ├── cloud_computing_comprehensive.txt
│   │   └── ancient_history_comprehensive.txt
│   └── test_queries.json        # Test query suite with expected results
├── scripts/
│   └── run_benchmark.py         # Main benchmarking script (with LLM judging)
└── reports/                     # Generated benchmark reports (created on first run)
    └── report_threshold_X.XX_TIMESTAMP.json
```

## Quick Start

### Select Environment (dev/test/prod)

By default, the benchmark uses the `dev` environment and loads configuration from:
- `config/config.dev.yaml` - Database URLs and credentials
- `.env.dev` - Secret environment variables (OpenAI API key, passwords)

To use a different environment:

```bash
uv run python benchmarking/scripts/run_benchmark.py --env test
uv run python benchmarking/scripts/run_benchmark.py --env prod
```

The script will automatically load the correct configuration files for that environment.

### Run Benchmark with Default Threshold (0.35)

```bash
uv run python benchmarking/scripts/run_benchmark.py
```

### Run Benchmark with Custom Threshold

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.5
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.6
```

### Quick Test with First 5 Queries (Fast Feedback)

Use `--sample-size` to run and judge only the first N queries:

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --sample-size 5
```

This runs 5 queries with full LLM judging in about 30-60 seconds, perfect for quick iteration and validating your setup.

### Full Benchmark with All 30 Queries

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35
```

Runs all 30 queries with LLM judging (takes a few minutes).

### Database Cleanup (Default Behavior)

By default, the benchmark **cleans all data** from both PostgreSQL and Neo4j before running, ensuring noise-free results:

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35
```

You will be prompted to confirm (showing the actual databases from your config):
```
⚠️  WARNING: Database Cleanup
============================================================
The benchmark will delete ALL existing data from (dev environment):
  1. PostgreSQL: postgresql://raguser:ragpassword@localhost:54320/rag_memory_dev
  2. Neo4j:      bolt://localhost:7687

This ensures clean, noise-free benchmark results.
Database schemas and indexes will be preserved.
============================================================

Continue with data deletion? (yes/no):
```

**Note:**
- Schemas are preserved, only data is deleted. You can safely run multiple benchmarks.
- The warning shows the **actual database connections** from your config file, so you can verify you're cleaning the right databases.
- Different environments (test, prod) will show different database URLs from their respective config files.

### Skip Database Cleanup (Reuse Existing Data)

To skip cleanup and use existing data in the databases:

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --skip-clean
```

Combined with `--skip-ingest` to skip both cleanup AND re-ingestion:

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --skip-clean --skip-ingest
```

### Skip Data Re-ingestion (Reuse Existing Data)

To clean the databases but reuse the test data already in them:

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --skip-ingest
```

### Save Report to Custom Location

```bash
uv run python benchmarking/scripts/run_benchmark.py --threshold 0.5 --output my_custom_report.json
```

## Test Data

Three comprehensive test datasets cover different domains:

### 1. AI & Machine Learning
- **File:** `ai_ml_comprehensive.txt`
- **Topics:** Machine learning, neural networks, deep learning, transformers, attention mechanisms, large language models, embeddings, training algorithms
- **Expected relationships:** ~20-30 extracted entities and relationships

### 2. Cloud Computing & DevOps
- **File:** `cloud_computing_comprehensive.txt`
- **Topics:** Cloud providers (AWS, Google Cloud, Azure), containers, Kubernetes, DevOps practices, CI/CD, infrastructure as code, microservices, monitoring
- **Expected relationships:** ~20-30 extracted entities and relationships

### 3. Ancient History & Archaeology
- **File:** `ancient_history_comprehensive.txt`
- **Topics:** Ancient civilizations, archaeology, empires, warfare, trade, religious systems
- **Expected relationships:** ~20-30 extracted entities and relationships

## Test Query Suite

**30 total queries** organized by category:

- **AI/ML Queries (10):** Direct relationship queries about machine learning, neural networks, transformers, LLMs, etc.
- **Cloud/DevOps Queries (10):** Direct relationship queries about cloud platforms, containers, Kubernetes, CI/CD, etc.
- **History Queries (6):** Direct relationship queries about ancient civilizations, archaeology, trade, etc.
- **Cross-Domain Negative Tests (4):** Intentional mismatches (medieval history vs cloud computing) that should return 0 results

Each query specifies:
- Expected minimum results
- Expected maximum results
- Keywords that should appear
- Description of the relationship being tested

## LLM Judging System

The benchmark includes **GPT-5 Nano LLM judging** to evaluate whether results are semantically useful for answering questions, not just checking result counts.

### How It Works

1. **For each query**, the LLM evaluates the returned relationships on a 1-5 scale:
   - **5:** Definitely helpful (directly answers the question)
   - **4:** Very likely helpful (strong relevance with minor gaps)
   - **3:** Possibly helpful (could work with inference)
   - **2:** Unlikely helpful (tangentially related or significant gaps)
   - **1:** Not helpful (irrelevant or misleading)

2. **Sample-based judging** (recommended for iteration):
   ```bash
   # Judge only first 5 queries (faster feedback)
   uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35 --sample-size 5
   ```

3. **Full judging** (comprehensive evaluation):
   ```bash
   # Judge all 30 queries
   uv run python benchmarking/scripts/run_benchmark.py --threshold 0.35
   ```

### Why LLM Judging?

- **Mirrors real usage:** AI agents will be your actual consumers
- **Semantic evaluation:** Captures relevance better than simple result counts
- **Non-deterministic OK:** Variance is expected; we're evaluating overall trends, not exact scores

### Judge Output

**Console Output (during execution):**
```
      📤 LLM Judge Request:
         Query: How does machine learning relate to neural networks?
         Results: 4 relationships
      📥 LLM Judge Response:
         {"score": 5, "reasoning": "These relationships directly address..."}
```

**Report Includes:**
- Individual judge scores for each query (1-5 scale)
- Judge reasoning explaining the score
- **Raw LLM response** (even if malformed) for debugging
- Average judge score across the test set
- Score distribution (how many 5s, 4s, 3s, etc.)
- Judge error details if the LLM fails to follow format

Example report summary:
```
LLM Judge Results (1-5 scale):
  Total judged: 30
  Average score: 3.7
  Distribution:
    5/5: 8 ████████
    4/5: 12 ████████████
    3/5: 7 ███████
    2/5: 2 ██
    1/5: 1 █
```

**Full Visibility:**
- See exact LLM request (query + relationships formatted for judge)
- See exact LLM response (raw text, before parsing)
- See parsed score and reasoning
- See error messages if judge response is malformed
- Identify when LLM "goes rogue" and responds in unexpected format

## Report Format

Generated reports are JSON files containing:

```json
{
  "metadata": {
    "timestamp": "ISO 8601 timestamp",
    "threshold": 0.35,
    "test_data_ingested": true,
    "query_count": 30
  },
  "summary": {
    "total_queries": 30,
    "passed": 26,
    "failed": 4,
    "pass_rate_percent": 86.67
  },
  "by_category": {
    "ai_ml_direct": {"passed": 9, "failed": 1},
    "cloud_devops_direct": {"passed": 10, "failed": 0},
    "history_direct": {"passed": 6, "failed": 0},
    "cross_domain_negative": {"passed": 1, "failed": 3}
  },
  "query_results": [
    {
      "query_id": 1,
      "query_text": "How does machine learning relate to neural networks?",
      "category": "ai_ml_direct",
      "expected_min": 1,
      "expected_max": 5,
      "actual_results": 3,
      "passed": true,
      "results": [
        {
          "id": "uuid-string",
          "relationship_type": "USES",
          "fact": "Machine learning involves neural networks"
        }
      ]
    },
    ...
  ]
}
```

## Workflow for Threshold Tuning

1. **Run initial benchmark at default threshold:**
   ```bash
   python benchmarking/scripts/run_benchmark.py --threshold 0.35
   ```

2. **Review results** and identify patterns:
   - Which categories have highest false positive/negative rates?
   - Are cross-domain mismatches being correctly filtered?

3. **Test alternative thresholds:**
   ```bash
   python benchmarking/scripts/run_benchmark.py --threshold 0.30
   python benchmarking/scripts/run_benchmark.py --threshold 0.40
   ```

4. **Compare reports:**
   - Look at `pass_rate_percent` in summary
   - Check `by_category` breakdown
   - Review specific query failures

5. **Select optimal threshold** based on metrics:
   - Prioritize avoiding false positives (cross-domain mismatches)
   - Maintain reasonable recall for in-domain queries
   - Balance precision and coverage

## Database Preparation

The benchmark script handles database cleanup and preparation automatically. It loads the correct database configuration from your YAML config files based on the environment (dev/test/prod).

### Ensure Docker Containers Are Running

Make sure your Docker containers are running for the target environment:

```bash
# For dev environment (default)
docker-compose -f docker-compose.dev.yml up -d

# Or for test/prod environments (if using different compose files)
docker-compose -f docker-compose.test.yml up -d
```

### Configuration-Driven Database Selection

The benchmark script automatically:
1. **Loads configuration** from `config/config.{env}.yaml` based on `--env` flag
2. **Reads database credentials** from the loaded YAML (PostgreSQL URL, Neo4j URI, etc.)
3. **Displays actual databases** in the cleanup confirmation prompt
4. **Cleans the correct databases** based on your configuration

This ensures you're always operating on the intended databases. Different environments (dev/test/prod) can point to completely different database instances.

### Automatic Setup Flow

The `run_benchmark.py` script will automatically:
1. **Prompt and clean** both PostgreSQL and Neo4j (unless `--skip-clean` is specified)
   - Deletes all data while preserving schemas and indexes
   - Shows the actual database connections being cleaned
2. Create collections if they don't exist
3. Ingest test documents into PostgreSQL
4. Extract entities and relationships into Neo4j
5. Run test queries

**No manual database cleanup required** - the script handles it with user confirmation.

## Interpreting Results

### Pass Rate
- **90-100%:** Threshold is well-tuned
- **80-90%:** Acceptable but may need tuning
- **<80%:** Threshold is too aggressive or too permissive

### By Category Breakdown
- **Cross-domain negatives:** Should have high pass rate (0 results when expected)
- **In-domain queries:** Should have high pass rate (correct number of results)
- **Mismatches indicate:** Threshold filtering too permissive (false positives) or too strict (false negatives)

## Limitations

- Test datasets are relatively small (3 documents, ~8000 words each)
- Graphiti's entity extraction quality affects benchmark validity (excellent model performance required)
- Cross-domain tests assume topics are truly unrelated (may not match by chance)
- Single-threaded execution (all queries run sequentially)

## Future Enhancements

- Add more test documents and queries for statistical significance
- Parallel query execution for faster benchmarking
- Threshold optimization algorithm to find optimal value
- Comparison across multiple thresholds in single report
- Per-entity accuracy metrics (not just query-level)
