# Installation

This guide covers setting up RAG Memory locally with Docker.

## Prerequisites

**Required Software**
- Docker Desktop (for Mac/Windows) or Docker Engine (for Linux)
- Git
- Python 3.11 or higher (for the setup script)

**Required Credentials**
- OpenAI API key (get from https://platform.openai.com/api-keys)

**System Requirements**
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space
- macOS, Linux, or Windows with WSL2

## Quick Start (5 Minutes)

```bash
# 1. Clone repository
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory

# 2. Activate virtual environment (REQUIRED)
source .venv/bin/activate

# 3. Run setup script
python scripts/setup.py
```

The setup script handles:
- Docker container startup (PostgreSQL + Neo4j)
- Database initialization
- System configuration
- CLI tool installation
- Health verification

## Detailed Setup Steps

### 1. Install Docker

**macOS**
```bash
# Download Docker Desktop from docker.com
# Or use Homebrew:
brew install --cask docker
```

**Linux**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

**Windows**
- Install Docker Desktop for Windows
- Enable WSL2 backend
- Restart system if prompted

### 2. Verify Docker

```bash
docker --version
docker ps
```

Should show Docker version and no errors.

### 3. Clone Repository

```bash
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
```

### 4. Activate Virtual Environment

```bash
# CRITICAL: This step is required for setup.py to work
source .venv/bin/activate

# Verify activation (prompt should show (.venv))
which python
```

### 5. Run Setup Script

```bash
python scripts/setup.py
```

**Setup Script Does:**
1. Checks Docker is running
2. Starts PostgreSQL container (port 54320)
3. Starts Neo4j container (ports 7474, 7687)
4. Waits for containers to be healthy
5. Initializes database schemas
6. Creates vector indices
7. Prompts for OpenAI API key
8. Writes configuration file
9. Installs CLI tool globally
10. Verifies installation

**Expected Output:**
```
✓ Docker daemon running
✓ Starting containers
✓ PostgreSQL ready (port 54320)
✓ Neo4j ready (port 7687)
✓ Database schemas initialized
✓ Vector indices created
Enter OpenAI API key: sk-...
✓ Configuration saved
✓ CLI tool installed
✓ Setup complete
```

## Verify Installation

### Check Services

```bash
# Check Docker containers
docker ps

# Should show:
# - rag-memory-postgres (port 54320)
# - rag-memory-neo4j (ports 7474, 7687)
```

### Check CLI Tool

```bash
# CLI should be available globally
rag status

# Expected output:
# ✓ PostgreSQL: healthy
# ✓ Neo4j: healthy
```

### Test Basic Functionality

```bash
# Create collection
rag collection create test-docs \
  --description "Test collection" \
  --domain "Testing" \
  --domain-scope "Setup verification"

# Ingest text
rag ingest text "PostgreSQL enables semantic search" \
  --collection test-docs

# Search
rag search "semantic search" --collection test-docs

# Should return the ingested text with similarity score
```

## Configuration Files

Setup creates configuration at:
- **macOS**: `~/Library/Application Support/rag-memory/config.yaml`
- **Linux**: `~/.config/rag-memory/config.yaml`
- **Windows**: `%APPDATA%\rag-memory\config.yaml`

Configuration contains:
- Database connection strings
- OpenAI API key
- Neo4j credentials
- Backup settings

See CONFIGURATION.md for details.

## Post-Installation

### Start Services

```bash
# Start containers (if stopped)
rag start

# Verify status
rag status
```

### Stop Services

```bash
# Stop containers (data persists)
rag stop
```

### View Logs

```bash
# View all service logs
rag logs

# View specific service
rag logs --service postgres
rag logs --service neo4j
```

## Database Access

**PostgreSQL**
```bash
# Connection string
postgresql://raguser:ragpassword@localhost:54320/rag_memory

# Connect via psql
psql postgresql://raguser:ragpassword@localhost:54320/rag_memory

# Or using docker exec
docker exec -it rag-memory-postgres-local psql -U raguser -d rag_memory
```

**Neo4j Browser**
- URL: http://localhost:7474
- Username: `neo4j`
- Password: `graphiti-password`

## Data Persistence

**Docker Volumes**
Data persists in Docker volumes even when containers are stopped:
- `postgres_data_local` - PostgreSQL data
- `neo4j_data_local` - Neo4j data
- `neo4j_logs_local` - Neo4j logs

**Backup**
```bash
# Manual backup
docker exec rag-memory-postgres-local pg_dump -U raguser rag_memory > backup.sql

# Restore
docker exec -i rag-memory-postgres-local psql -U raguser rag_memory < backup.sql
```

## Troubleshooting

See TROUBLESHOOTING.md for common issues and solutions.

**Quick Fixes:**

**Port Already in Use**
```bash
# Check what's using port 54320
lsof -i :54320

# Stop conflicting service or change RAG Memory port in config
```

**Docker Not Running**
```bash
# macOS: Start Docker Desktop app
# Linux: sudo systemctl start docker
# Windows: Start Docker Desktop
```

**Permission Denied**
```bash
# Linux: Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

## Next Steps

- **CLI Usage** - See CLI_GUIDE.md for commands
- **MCP Setup** - See MCP_GUIDE.md for AI agent integration
- **Configuration** - See CONFIGURATION.md for advanced settings
- **Cloud Deployment** - See CLOUD_SETUP.md for production deployment
