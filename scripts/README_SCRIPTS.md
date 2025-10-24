# RAG Memory Scripts

Quick reference for utility scripts available in this project.

## Database Data Checker

Quick verification script to check if data exists in PostgreSQL and Neo4j across different environments.

**Key Feature:** Automatically discovers available environments by scanning `config/config.*.yaml` files. No hardcoded database connections!

### Usage

```bash
# Check test database (default)
uv run scripts/check_database_data.py

# Check specific environment (loaded from config/)
uv run scripts/check_database_data.py --env test
uv run scripts/check_database_data.py --env dev

# Check all configured environments
uv run scripts/check_database_data.py --env all

# Show verbose output (includes config file loading status)
uv run scripts/check_database_data.py --env test --verbose
```

### How It Works

The script automatically discovers available environments by:
1. Scanning the `config/` directory for `config.*.yaml` files
2. Extracting database connection details from the `server:` section
3. Dynamically populating the `--env` argument choices
4. Loading credentials directly from YAML files (no hardcoding needed)

### What It Checks

**PostgreSQL:**
- Document count (source_documents table)
- Chunk count (document_chunks table)
- Crawl history count (if table exists)
- Total rows across all tables

**Neo4j:**
- Total node count
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

Environments are automatically discovered from:
- `config/config.test.yaml` → Available as `--env test`
- `config/config.dev.yaml` → Available as `--env dev`
- Any other `config/config.*.yaml` files → Available as `--env <name>`
- `--env all` → Check all available environments

List available environments anytime:
```bash
uv run scripts/check_database_data.py --help
```

### Quick Commands

**Add to your shell alias (optional):**

```bash
# In ~/.zshrc or ~/.bashrc
alias rag-check='uv run scripts/check_database_data.py'

# Then use as:
rag-check --env test
rag-check --env all
rag-check --env dev --verbose
```

## Adding New Environments

To add a new environment:

1. **Create a config file:** `config/config.production.yaml`
2. **Add database details:**
   ```yaml
   server:
     database_url: postgresql://user:pass@host:5432/dbname
     neo4j_uri: bolt://host:7687
     neo4j_user: neo4j
     neo4j_password: your-password
   ```
3. **Use it immediately:**
   ```bash
   uv run scripts/check_database_data.py --env production
   ```

The script will automatically discover and load your new environment from the YAML file!
