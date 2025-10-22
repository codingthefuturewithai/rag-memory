# Production Setup Guide - Using docker-compose.prod.yml

This guide shows how to use the production Docker Compose setup locally to emulate a new user deploying RAG Memory.

## Quick Start

### 1. Create Your Configuration File

Copy the template and customize for your environment:

```bash
cp .env.example .env.prod
```

Then edit `.env.prod` and set your actual OpenAI API key:

```bash
# .env.prod
OPENAI_API_KEY=sk-proj-your-actual-api-key-here

# You can also customize port numbers if you have conflicts:
PROD_POSTGRES_PORT=54320      # Change if port 54320 is in use
PROD_NEO4J_BOLT_PORT=7687     # Change if port 7687 is in use
PROD_NEO4J_HTTP_PORT=7474     # Change if port 7474 is in use
PROD_MCP_PORT=8000            # Change if port 8000 is in use
```

### 2. Start the Production Stack

**Option A: Using --env-file flag (Recommended)**

```bash
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

**Option B: Source the file and start**

```bash
source .env.prod
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Verify Services Are Running

```bash
docker-compose -f docker-compose.prod.yml ps
```

You should see:
```
rag-memory-postgres   ✓ Up (healthy)
rag-memory-neo4j      ✓ Up (healthy)
rag-memory-mcp        ✓ Up
rag-memory-backup     ✓ Up
```

### 4. Test the CLI

The CLI needs the same environment variables. Use the same `.env.prod` file:

```bash
# Source the environment and run a command
source .env.prod
uv run rag status

# Or pass environment variables explicitly
OPENAI_API_KEY=$(grep OPENAI_API_KEY .env.prod | cut -d= -f2) \
DATABASE_URL=$(grep DATABASE_URL .env.prod | cut -d= -f2) \
NEO4J_URI=$(grep NEO4J_URI .env.prod | cut -d= -f2) \
NEO4J_USER=$(grep NEO4J_USER .env.prod | cut -d= -f2) \
NEO4J_PASSWORD=$(grep NEO4J_PASSWORD .env.prod | cut -d= -f2) \
uv run rag status
```

### 5. Test the MCP Server

The MCP server runs inside the Docker container on port 8000 (configurable via `PROD_MCP_PORT`).

From Claude Code:

```bash
claude mcp add-json --scope user rag-memory '{"type":"sse","url":"http://localhost:8000/sse"}'
```

Then ask your AI agent:
> "List my RAG Memory collections"

## Configuration File Explained

### Environment-Specific Files

RAG Memory uses separate `.env` files for different deployment scenarios:

```
.env.dev      → Development (docker-compose.dev.yml)
.env.test     → Testing (docker-compose.test.yml)
.env.prod     → Production (docker-compose.prod.yml)
.env.supabase → Cloud deployment (your custom setup)
```

### Why Multiple Files?

Each environment has:
- **Different default ports** to avoid conflicts when running multiple stacks
- **Different databases** (rag_memory_dev vs rag_memory_test vs rag_memory)
- **Different credentials** (dev-password vs test-password vs graphiti-password)
- **Different backup schedules** (optional)

## Port Configuration

All services use environment variables for host ports:

| Service | Dev Port | Test Port | Prod Port | Env Variable |
|---------|----------|-----------|-----------|--------------|
| PostgreSQL | 54320 | 54323 | 54320* | `PROD_POSTGRES_PORT` |
| Neo4j Bolt | 7687 | 7689 | 7687* | `PROD_NEO4J_BOLT_PORT` |
| Neo4j HTTP | 7474 | 7476 | 7474* | `PROD_NEO4J_HTTP_PORT` |
| MCP Server | - | - | 8000* | `PROD_MCP_PORT` |

*Default values. Override in `.env.prod` if you have port conflicts.

### Example: Using Different Ports for Dev and Prod

```bash
# .env.prod - use different ports than dev
PROD_POSTGRES_PORT=54321
PROD_NEO4J_BOLT_PORT=7688
PROD_NEO4J_HTTP_PORT=7475
PROD_MCP_PORT=8001

# Now you can run both dev and prod simultaneously:
docker-compose -f docker-compose.dev.yml up -d    # Uses 54320, 7687, 7474
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d   # Uses 54321, 7688, 7475
```

## Automated Backups

The production stack includes automatic daily backups using `offen/docker-volume-backup`.

### Backup Configuration

Edit `.env.prod` to customize backup behavior:

```bash
# Backup schedule (cron format: minute hour * * *)
# Default: 5 2 * * * (2:05 AM daily)
BACKUP_CRON_SCHEDULE=5 2 * * *

# Enable/disable compression
BACKUP_COMPRESSION=true

# Retention (days to keep backups, 0 = infinite)
BACKUP_RETENTION_DAYS=30
```

### Backup Location

Backups are stored in: `./backups/` (relative to project root)

After backups run, you'll see:
```
./backups/
├── backup-2025-10-21T020500.tar.gz
├── backup-2025-10-20T020500.tar.gz
├── backup-2025-10-19T020500.tar.gz
└── ... (older backups)
```

### Restore from Backup

To restore from a backup:

```bash
# Stop the stack
docker-compose -f docker-compose.prod.yml down

# Extract backup into volumes
# (This is a manual process - consult backup documentation)

# Restart
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

## Multiple Environment Management

### Running Dev, Test, and Prod Simultaneously

With different ports configured:

```bash
# Terminal 1: Development
source .env.dev
docker-compose -f docker-compose.dev.yml up -d

# Terminal 2: Test
source .env.test
docker-compose -f docker-compose.test.yml up -d

# Terminal 3: Production
source .env.prod
docker-compose -f docker-compose.prod.yml up -d

# Check all are running
docker ps | grep rag-memory
```

### Switch Between Environments

```bash
# Clean up old environment
docker-compose -f docker-compose.dev.yml down -v

# Start new environment
source .env.prod
docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Connection Refused

Make sure services are healthy:

```bash
docker-compose -f docker-compose.prod.yml logs postgres
docker-compose -f docker-compose.prod.yml logs neo4j
```

### Port Already in Use

If you get "port already in use" error:

1. Check what's using the port:
   ```bash
   lsof -i :54320  # Check what's on port 54320
   ```

2. Edit `.env.prod` and change the port:
   ```bash
   PROD_POSTGRES_PORT=54321  # Use different port
   ```

3. Restart:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   docker-compose --env-file .env.prod -f docker-compose.prod.yml up -d
   ```

### Backups Not Running

Check the backup container logs:

```bash
docker-compose -f docker-compose.prod.yml logs backup
```

The backup service should show something like:
```
Starting backup service on schedule: 5 2 * * * (2:05 AM daily)
```

## Comparison with Development Setup

### Why This Different From Dev?

| Aspect | Dev (`docker-compose.dev.yml`) | Prod (`docker-compose.prod.yml`) |
|--------|--------|----------|
| Data Persistence | ✓ Data kept across restarts | ✓ Data kept across restarts |
| Backups | Manual (via `docker volume`) | Automated daily |
| Cleanup | Manual delete | Requires explicit `down -v` |
| Use Case | Manual testing, exploration | Emulating production deployment |
| Port Conflicts | Isolated dev ports | Configurable for any port |

## Next Steps

1. **Add Documents**
   ```bash
   source .env.prod
   uv run rag ingest text "Your document content here" --collection my-docs
   ```

2. **Search**
   ```bash
   uv run rag search "query" --collection my-docs
   ```

3. **Connect MCP Server**
   ```bash
   claude mcp add-json --scope user rag-memory '{"type":"sse","url":"http://localhost:8000/sse"}'
   ```

4. **Monitor Backups**
   ```bash
   ls -lah ./backups/  # See backup files
   docker-compose -f docker-compose.prod.yml logs backup  # Check backup logs
   ```
