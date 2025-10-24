# RAG Memory Scripts

Quick reference for utility scripts available in this project.

## Database Data Checker

Quick verification script to check if data exists in PostgreSQL and Neo4j across different environments.

### Usage

```bash
# Check test database (default)
uv run scripts/check_database_data.py

# Check specific environment
uv run scripts/check_database_data.py --env test
uv run scripts/check_database_data.py --env dev

# Check all configured environments
uv run scripts/check_database_data.py --env all

# Show verbose output
uv run scripts/check_database_data.py --env test --verbose
```

### What It Checks

**PostgreSQL:**
- Document count (source_documents table)
- Chunk count (document_chunks table)
- Crawl history count (if table exists)
- Total rows across all tables

**Neo4j:**
- Total nodes in graph
- Entity node count
- Connection status

### Output Example

```
================================================================================
DATABASE STATUS: Test (54323/7689)
================================================================================

📊 PostgreSQL
  Documents:          0
  Chunks:             0
  Total rows:         0
  Status:        ✅ CLEAN

🔗 Neo4j
  Total nodes:        0
  Entities:           0
  Status:        ✅ CLEAN
```

### Supported Environments

- **test** - Test databases (PostgreSQL: localhost:54323, Neo4j: localhost:7689)
- **dev** - Development databases (PostgreSQL: localhost:54320, Neo4j: localhost:7688)
- **all** - Check all environments and show summary

### Quick Commands

**Add to your shell alias (optional):**

```bash
# In ~/.zshrc or ~/.bashrc
alias rag-check='uv run scripts/check_database_data.py'

# Then use as:
rag-check --env test
rag-check --env all
```

## Adding New Environments

To add a new environment, edit `scripts/check_database_data.py` and add to the `configs` dictionary:

```python
"production": {
    "pg_url": "postgresql://user:pass@host:port/dbname",
    "neo4j_uri": "bolt://host:port",
    "neo4j_user": "neo4j",
    "neo4j_password": "password",
    "label": "Production (port/port)"
}
```

Then use:

```bash
uv run scripts/check_database_data.py --env production
```
