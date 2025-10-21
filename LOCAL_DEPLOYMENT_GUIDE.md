# RAG Memory - Local Deployment Guide

**For non-technical users who want to run RAG Memory on their own machine.**

---

## What You're Getting

- PostgreSQL database (stores documents and vectors)
- Neo4j graph database (stores entity relationships)
- MCP Server (connects to Claude and other AI agents)
- All running on YOUR machine, completely local
- Automatic daily backups

---

## Prerequisites

### Step 1: Install Docker Desktop

**What it is:** Docker Desktop runs containers (isolated environments for applications)

**Where to get it:**
- **Mac:** https://www.docker.com/products/docker-desktop (Universal or Intel, choose based on your Mac)
- **Windows:** https://www.docker.com/products/docker-desktop (Windows 10/11 Pro, Home, or Enterprise)
- **Linux:** Follow your distribution's instructions: https://docs.docker.com/engine/install/

**Installation:**
1. Download Docker Desktop for your OS
2. Run the installer
3. Follow the prompts (default settings are fine)
4. Restart your computer

**Verify it worked:**
- Open Terminal (Mac/Linux) or PowerShell (Windows)
- Run: `docker --version`
- Should show: `Docker version X.X.X`

**Reference:** https://docs.docker.com/get-started/get-docker/

### Step 2: Install UV (Python Package Manager)

**What it is:** UV installs Python dependencies your MCP server needs

**Where to get it:**
- All OS: https://docs.astral.sh/uv/getting-started/installation/

**Installation:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Verify it worked:**
```bash
uv --version
```

**Reference:** https://docs.astral.sh/uv/

### Step 3: Get Your OpenAI API Key

**What it is:** Your access to OpenAI's embedding model (creates searchable vectors from text)

**Where to get it:**
1. Go to https://platform.openai.com/account/api-keys
2. Log in or sign up
3. Click "Create new secret key"
4. Copy the key (you'll need it later)

**Reference:** https://platform.openai.com/docs/quickstart

---

## Installation (5 minutes)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/rag-memory.git
cd rag-memory
```

### Step 2: Create .env File

In the `rag-memory` directory, create a file named `.env`:

```bash
# Mac/Linux
echo 'OPENAI_API_KEY=sk-YOUR-KEY-HERE' > .env

# Windows PowerShell
"OPENAI_API_KEY=sk-YOUR-KEY-HERE" | Out-File -FilePath .env -Encoding utf8
```

Replace `sk-YOUR-KEY-HERE` with your actual OpenAI API key.

### Step 3: Start Everything

```bash
docker-compose up -d
```

This command:
- Downloads PostgreSQL, Neo4j, and sets up the MCP server
- Starts all 3 services
- Returns immediately (runs in background)

**Takes:** 2-5 minutes on first run (downloading images)

### Step 4: Verify Everything Started

```bash
docker-compose ps
```

You should see:
```
NAME              STATUS
postgres          Up 2 minutes
neo4j             Up 2 minutes
rag-mcp           Up 1 minute
```

All should say `Up` (not `Exited` or `restarting`)

**Reference:** https://docs.docker.com/compose/

---

## Using RAG Memory

### Initialize Database Schema

First time only:

```bash
uv run rag init
```

This creates the PostgreSQL tables and indexes. Takes ~10 seconds.

### Use with Claude Desktop

1. **Edit Claude Desktop config:**
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Add this section:**

```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "uv",
      "args": ["--directory", "/path/to/rag-memory", "run", "python", "-m", "src.mcp.server"],
      "env": {
        "OPENAI_API_KEY": "sk-YOUR-KEY-HERE"
      }
    }
  }
}
```

Replace `/path/to/rag-memory` with your actual directory path.

3. **Restart Claude Desktop**

4. **Verify in Claude:**
   - Open a new conversation
   - Look for "rag-memory" in the available tools
   - You should see 17 tools listed

---

## Common Commands

**Start everything:**
```bash
docker-compose up -d
```

**Stop everything:**
```bash
docker-compose down
```

**View logs (see what's happening):**
```bash
docker-compose logs -f
```

**Access PostgreSQL:**
```bash
psql postgresql://raguser:ragpassword@localhost:5432/rag_memory
```

**Access Neo4j Browser:**
- Go to: http://localhost:7474
- Username: `neo4j`
- Password: `graphiti-password`

**Reset everything (delete all data):**
```bash
docker-compose down -v
docker-compose up -d
uv run rag init
```

**Reference:** https://docs.docker.com/compose/reference/

---

## Backups

Backups happen automatically every day at 2 AM local time.

**Where backups are stored:**
```
./backups/rag-memory-backup-YYYYMMDD-HHMMSS.tar.gz
```

**To restore from backup:**

```bash
# Stop everything
docker-compose down

# Extract backup (replace filename with your backup)
tar -xzf ./backups/rag-memory-backup-YYYYMMDD-HHMMSS.tar.gz -C ./

# Start everything
docker-compose up -d
uv run rag init
```

**Reference:** https://github.com/offen/docker-volume-backup (backup sidecar documentation)

---

## Troubleshooting

**"docker: command not found"**
- Docker Desktop not installed or not in PATH
- Restart Terminal/PowerShell after installation
- Reinstall Docker Desktop

**"containers exiting/restarting"**
```bash
docker-compose logs
```
Check what error messages appear

**"Cannot connect to localhost:5432"**
- PostgreSQL not running: `docker-compose ps`
- Check if port 5432 is already in use on your machine

**"Neo4j won't start"**
- Check logs: `docker-compose logs neo4j`
- Usually means insufficient disk space or memory

**"MCP server not connecting to Claude"**
- Verify config is correct
- Check Claude Desktop logs
- Restart Claude Desktop

---

## Storage Requirements

- **PostgreSQL:** ~1 GB initial, grows with documents
- **Neo4j:** ~500 MB initial, grows with entities
- **MCP Server:** ~500 MB
- **Total:** ~2-3 GB minimum

---

## Performance Expectations

- **Search:** <1 second per query
- **Ingest document:** 2-5 seconds per document
- **Neo4j entity extraction:** 30-60 seconds per document (uses LLM)

---

## What Happens When You Run docker-compose up

1. **Docker checks** if PostgreSQL, Neo4j images exist locally
2. **If not found:** Downloads from Docker Hub (~1-2 GB)
3. **Starts PostgreSQL** on `localhost:5432`
4. **Starts Neo4j** on `localhost:7474` (browser) and `localhost:7687` (bolt)
5. **Starts MCP Server** on `localhost:8000`
6. **All run in background** (you get control back immediately)

**Reference:** https://docs.docker.com/compose/compose-file/

---

## FAQ

**Q: Is my data safe?**
A: Yes. All data stays on your machine. Daily automatic backups to `./backups/`

**Q: Can I access the databases directly?**
A: Yes. PostgreSQL via `psql`, Neo4j via Browser at http://localhost:7474

**Q: What if I restart my computer?**
A: Data persists. Just run `docker-compose up -d` again.

**Q: Can I run this on multiple machines?**
A: Yes. Each machine needs Docker Desktop, but each gets its own local RAG Memory instance.

**Q: Do I need internet for normal use?**
A: Only for:
- Initial setup (downloading Docker images)
- OpenAI API calls (embedding generation)
- Ingesting web content via URL

Local search and document management work offline.

---

## Support

**Getting help:**
1. Check troubleshooting section above
2. Check logs: `docker-compose logs`
3. Verify prerequisites are installed: `docker --version`, `uv --version`
4. Read Docker Compose documentation: https://docs.docker.com/compose/

---

## Removing Everything

To completely remove RAG Memory:

```bash
# Stop and remove containers
docker-compose down -v

# Optional: Remove the directory
rm -rf rag-memory
```

**Reference:** https://docs.docker.com/compose/reference/compose_down/

---

**This is it. No cloud complexity. No $200/month bills. Just Docker, local databases, and automatic backups.**
