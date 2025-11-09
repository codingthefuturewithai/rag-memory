# Configuration

RAG Memory configuration includes environment variables, config files, and database connection strings.

## Configuration File Location

Setup creates configuration at OS-specific location:

**macOS:**
```
~/Library/Application Support/rag-memory/config.yaml
```

**Linux:**
```
~/.config/rag-memory/config.yaml
```

**Windows:**
```
%APPDATA%\rag-memory\config.yaml
```

## Configuration Format

Configuration uses YAML format:

```yaml
# Database connections
database:
  url: postgresql://raguser:ragpassword@localhost:54320/rag_memory

neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: graphiti-password

# OpenAI API
openai:
  api_key: sk-your-api-key-here
  embedding_model: text-embedding-3-small

# Graphiti models
server:
  graphiti_model: gpt-4o
  graphiti_small_model: gpt-4o-mini
  max_reflexion_iterations: 0

# Backup settings
backup:
  enabled: true
  schedule: "5 2 * * *"  # Daily at 2:05 AM
  archive_path: /path/to/backups

# Directory mounts (for MCP server file access)
mounts:
  documents: /Users/you/Documents
  projects: /Users/you/Projects
```

## Environment Variables

Configuration can be set via environment or config file:

### Required Variables

**OPENAI_API_KEY**
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```
Your OpenAI API key for embeddings and Graphiti.

**DATABASE_URL**
```bash
export DATABASE_URL="postgresql://raguser:ragpassword@localhost:54320/rag_memory"
```
PostgreSQL connection string. Default uses port 54320 (not 5432) to avoid conflicts.

### Neo4j Variables

**NEO4J_URI**
```bash
export NEO4J_URI="bolt://localhost:7687"
```
Neo4j connection URI. Default: bolt://localhost:7687

**NEO4J_USER**
```bash
export NEO4J_USER="neo4j"
```
Neo4j username. Default: neo4j

**NEO4J_PASSWORD**
```bash
export NEO4J_PASSWORD="graphiti-password"
```
Neo4j password. Default: graphiti-password (local Docker only)

### Graphiti Model Variables

**GRAPHITI_MODEL**
```bash
export GRAPHITI_MODEL="gpt-4o"
```
Main model for entity extraction. See Graphiti docs for options: https://docs.graphiti.ai/

**GRAPHITI_SMALL_MODEL**
```bash
export GRAPHITI_SMALL_MODEL="gpt-4o-mini"
```
Smaller model for less complex extraction tasks.

**MAX_REFLEXION_ITERATIONS**
```bash
export MAX_REFLEXION_ITERATIONS="0"
```
Number of reflexion iterations for entity extraction (0-3). Default: 0

### Optional Variables

**RAG_CONFIG_PATH**
```bash
export RAG_CONFIG_PATH="/custom/path/to/config.yaml"
```
Override config file location. Default uses OS-specific location.

## Database Connection Strings

### PostgreSQL

**Format:**
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

**Local Docker (default):**
```
postgresql://raguser:ragpassword@localhost:54320/rag_memory
```

**Cloud (Supabase):**
```
postgresql://postgres:[password]@db.xxxxx.supabase.co:5432/postgres
```

**Connection Components:**
- User: raguser (local) or postgres (Supabase)
- Password: Set during setup
- Host: localhost (local) or Supabase domain (cloud)
- Port: 54320 (local) or 5432 (cloud)
- Database: rag_memory (local) or postgres (cloud)

### Neo4j

**Format:**
```
bolt://[host]:[port]
```

**Local Docker:**
```
bolt://localhost:7687
```

**Cloud (Neo4j Aura):**
```
bolt://xxxxx.databases.neo4j.io:7687
```

**Credentials:**
- Username: neo4j
- Password: Set during setup (local) or Aura (cloud)

## Configuration Commands

### View Configuration

```bash
rag config show
```

Shows:
- Database connections (credentials redacted)
- OpenAI API key status
- Neo4j configuration
- Backup settings
- Directory mounts

### Edit Configuration

```bash
rag config edit
```

Opens config.yaml in system editor ($EDITOR or default).

### Set Specific Value

```bash
rag config set <key> <value>
```

Examples:
```bash
# Update API key
rag config set openai.api_key "sk-new-key"

# Change backup schedule
rag config set backup.schedule "0 3 * * *"

# Add directory mount
rag config set mounts.docs "/path/to/docs"
```

After changing configuration, restart services:
```bash
rag restart
```

## Port Configuration

**PostgreSQL: 54320**
- Why not 5432: Avoids conflicts with existing PostgreSQL installations
- Change if needed in docker-compose.yml

**Neo4j: 7474 (HTTP), 7687 (Bolt)**
- 7474: Neo4j Browser interface
- 7687: Bolt protocol for queries

**MCP Server: 3001 (SSE/HTTP transports)**
- Only used for SSE and HTTP transports
- Stdio transport doesn't need a port

## Security

### Protecting API Keys

**Never commit API keys to git:**
```bash
# Config file is in OS-specific location (outside repo)
# .env files are gitignored
# config.yaml has secure permissions (0600)
```

**File Permissions:**
```bash
# Config file should be readable only by owner
chmod 600 ~/Library/Application\ Support/rag-memory/config.yaml
```

**Environment Variables:**
```bash
# Set in shell profile, not in code
# Example: ~/.zshrc or ~/.bashrc
export OPENAI_API_KEY="sk-your-key"
```

### Database Credentials

**Local Development:**
- Default credentials in Docker are for development only
- Not secure for production use

**Production:**
- Use strong passwords
- Restrict network access
- Enable SSL/TLS connections
- Consider managed databases (Supabase, Neo4j Aura)

## MCP Server Configuration

MCP server gets configuration from two sources:

### 1. Client Environment (Claude Desktop/Code)

Configuration in client config file:

**Claude Desktop:**
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "env": {
        "OPENAI_API_KEY": "sk-your-key",
        "DATABASE_URL": "postgresql://..."
      }
    }
  }
}
```

**Claude Code:**
```bash
claude mcp add-json --scope user rag-memory '{
  "type": "stdio",
  "command": "rag-mcp-stdio",
  "env": {
    "OPENAI_API_KEY": "sk-your-key",
    "DATABASE_URL": "postgresql://..."
  }
}'
```

### 2. System Configuration

CLI commands use system config file at OS-specific location.

## Configuration Priority

When multiple configuration sources exist:

1. **Environment variables** (highest priority)
2. **Command-line arguments**
3. **Config file** (lowest priority)

Example:
```bash
# Config file has: embedding_model: text-embedding-3-small
# Environment sets: export EMBEDDING_MODEL="text-embedding-3-large"
# Result: Uses text-embedding-3-large (environment wins)
```

## Backup Configuration

**Schedule Format:**
Cron expression: `minute hour day month weekday`

Examples:
```yaml
backup:
  schedule: "5 2 * * *"    # Daily at 2:05 AM
  schedule: "0 */6 * * *"  # Every 6 hours
  schedule: "0 0 * * 0"    # Weekly on Sunday
```

**Archive Path:**
```yaml
backup:
  archive_path: /path/to/backups
```

Backup files stored as:
```
/path/to/backups/rag-memory-2025-10-20-020500.tar.gz
```

## Directory Mounts

For MCP server file access (ingest_file, ingest_directory):

```yaml
mounts:
  documents: /Users/you/Documents
  projects: /Users/you/Projects
  data: /mnt/data
```

MCP server can access files in mounted directories:
```bash
# Via MCP tool
ingest_file("/Users/you/Documents/guide.md", "tech-docs")

# Mounted path available to MCP server
```

## Troubleshooting Configuration

### Config File Not Found

```bash
# Check file exists
ls ~/Library/Application\ Support/rag-memory/config.yaml

# Re-run setup if missing
python scripts/setup.py
```

### Invalid Configuration

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Check for common issues:
# - Indentation (use spaces, not tabs)
# - Quotes around strings with special characters
# - No trailing commas
```

### Connection Errors

```bash
# Test PostgreSQL
psql $DATABASE_URL -c "SELECT 1"

# Test Neo4j
docker exec -it rag-memory-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD

# Check environment
env | grep -E "DATABASE_URL|NEO4J|OPENAI"
```

### Permission Errors

```bash
# Fix config file permissions
chmod 600 ~/Library/Application\ Support/rag-memory/config.yaml

# Fix directory permissions
chmod 700 ~/Library/Application\ Support/rag-memory
```

## Next Steps

- **Installation** - See INSTALLATION.md for initial setup
- **MCP Setup** - See MCP_GUIDE.md for AI agent configuration
- **Troubleshooting** - See TROUBLESHOOTING.md for common issues
