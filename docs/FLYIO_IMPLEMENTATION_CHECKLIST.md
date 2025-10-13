# Fly.io Deployment - Implementation Checklist

**Branch:** `feature/flyio-deployment`
**Plan:** See `FLYIO_DEPLOYMENT_PLAN.md`
**Date:** 2025-10-13

---

## Phase 1: Docker Setup (Days 1-2)

### File: `Dockerfile`

**Location:** `/Users/timkitchens/projects/ai-projects/rag-memory/Dockerfile`

**Contents:**
```dockerfile
# Multi-stage build for RAG Memory MCP Server
# Base: Microsoft Playwright image (includes Chromium for Crawl4AI)

# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy AS builder

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv package manager and sync dependencies
RUN pip install --no-cache-dir -U uv && \
    uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Runtime image
# ============================================================================
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src /app/src
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY init.sql /app/init.sql
COPY pyproject.toml /app/pyproject.toml

# Environment variables
ENV PORT=8000
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run MCP server with SSE transport on port 8000
CMD ["python", "-m", "src.mcp.server", "--transport", "sse", "--port", "8000"]
```

**Checklist:**
- [ ] File created at project root
- [ ] Multi-stage build configured
- [ ] Playwright base image specified (v1.44.0-jammy)
- [ ] uv dependency installation
- [ ] Virtual environment copied from builder stage
- [ ] Application code copied (src, alembic, configs)
- [ ] Environment variables set (PORT, PLAYWRIGHT_*, PATH)
- [ ] Port 8000 exposed
- [ ] Health check configured
- [ ] CMD runs MCP server with SSE transport

---

### File: `.dockerignore`

**Location:** `/Users/timkitchens/projects/ai-projects/rag-memory/.dockerignore`

**Contents:**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
test-results/
*.coverage

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Git
.git/
.gitignore

# Documentation (not needed at runtime)
docs/
.reference/
*.md

# Build artifacts
dist/
build/
*.egg-info/

# Environment files (secrets should come from Fly.io)
.env
.env.example
.env.local
~/.rag-memory-env

# Test data
test-data/
backups/

# Mac
.DS_Store

# Docker
docker-compose.yml
Dockerfile
.dockerignore

# Migration archives (not needed in production)
migrations/archive/

# Scripts (development only)
scripts/
build.sh
```

**Checklist:**
- [ ] File created at project root
- [ ] Python artifacts excluded
- [ ] Virtual environment excluded (built in container)
- [ ] Test files excluded
- [ ] Documentation excluded
- [ ] Environment files excluded (secrets via Fly.io)
- [ ] Git directory excluded
- [ ] Development scripts excluded

---

### File: `.dockerignore` Validation

**Test locally:**
```bash
# Build the image
docker build -t rag-memory-mcp .

# Check image size (should be <2GB)
docker images rag-memory-mcp

# Run locally with environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://raguser:ragpassword@host.docker.internal:54320/rag_memory" \
  -e OPENAI_API_KEY="sk-test-key" \
  rag-memory-mcp

# In another terminal, test health check
curl http://localhost:8000/health

# Test SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8000/sse
```

**Checklist:**
- [ ] Image builds without errors (<10 minutes)
- [ ] Image size reasonable (<2GB)
- [ ] Container starts and listens on port 8000
- [ ] Health check endpoint responds
- [ ] SSE endpoint accepts connections
- [ ] Database connection works (to local Docker)
- [ ] No errors in container logs

---

## Phase 2: Fly.io Configuration (Day 3)

### File: `fly.toml`

**Location:** `/Users/timkitchens/projects/ai-projects/rag-memory/fly.toml`

**Contents:**
```toml
# Fly.io configuration for RAG Memory MCP Server
# Region: iad (Ashburn, VA) - closest to Supabase us-east-1

app = "rag-memory-mcp"
primary_region = "iad"
kill_signal = "SIGINT"
kill_timeout = "5s"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"

# HTTP service configuration
[[services]]
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

  # HTTP port (redirects to HTTPS)
  [[services.ports]]
    handlers = ["http"]
    port = 80
    force_https = true

  # HTTPS port (TLS termination)
  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  # Concurrency limits
  [services.concurrency]
    type = "connections"
    hard_limit = 25
    soft_limit = 20

  # Health check
  [[services.http_checks]]
    grace_period = "10s"
    interval = "30s"
    method = "GET"
    path = "/health"
    timeout = "5s"

  # TCP checks (backup)
  [[services.tcp_checks]]
    grace_period = "10s"
    interval = "30s"
    timeout = "5s"

# Machine configuration
[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

**Checklist:**
- [ ] File created at project root
- [ ] App name: `rag-memory-mcp`
- [ ] Region: `iad`
- [ ] Dockerfile specified
- [ ] PORT environment variable set
- [ ] Internal port 8000 configured
- [ ] External ports 80 (HTTP) and 443 (HTTPS)
- [ ] force_https enabled
- [ ] Concurrency limits set (soft=20, hard=25)
- [ ] Health check configured (/health endpoint)
- [ ] TCP check as backup
- [ ] VM size: shared-cpu-1x, 256MB RAM
- [ ] Auto-start/stop enabled
- [ ] Min machines = 0 (scale to zero)

---

### Fly.io CLI Setup

**Commands:**
```bash
# Install Fly CLI (if not already installed)
curl -L https://fly.io/install.sh | sh

# Add to PATH (if needed)
echo 'export PATH="$HOME/.fly/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Authenticate
flyctl auth login

# Verify authentication
flyctl auth whoami
```

**Checklist:**
- [ ] Fly CLI installed
- [ ] PATH configured
- [ ] Authenticated with Fly.io account
- [ ] Account verified

---

### Create Fly.io App (Don't Deploy Yet)

**Commands:**
```bash
cd /Users/timkitchens/projects/ai-projects/rag-memory

# Launch app (do NOT deploy)
flyctl launch --region iad --name rag-memory-mcp --no-deploy

# This will:
# - Create the app on Fly.io
# - Generate fly.toml (already created manually above)
# - NOT deploy yet (we need to set secrets first)
```

**Checklist:**
- [ ] App created on Fly.io
- [ ] App name: `rag-memory-mcp`
- [ ] Region: `iad`
- [ ] fly.toml reviewed and correct
- [ ] NOT deployed yet

---

### Set Fly.io Secrets

**Get Supabase connection string:**
1. Go to Supabase Dashboard → Settings → Database → Connection Strings
2. Copy **Session Pooler** URL (NOT Direct Connection)
3. Format: `postgresql://postgres.[REF]:[PASS]@aws-0-[REGION].pooler.supabase.com:5432/postgres`

**Commands:**
```bash
# Set DATABASE_URL (replace with your Supabase URL)
flyctl secrets set DATABASE_URL='postgresql://postgres.[REF]:[PASS]@aws-0-us-east-1.pooler.supabase.com:5432/postgres'

# Set OPENAI_API_KEY (replace with your key)
flyctl secrets set OPENAI_API_KEY='sk-...'

# Set PORT (matches fly.toml)
flyctl secrets set PORT=8000

# Verify secrets set (values will be masked)
flyctl secrets list

# Expected output:
# NAME            DIGEST                           CREATED AT
# DATABASE_URL    <masked>                         1m ago
# OPENAI_API_KEY  <masked>                         1m ago
# PORT            <masked>                         1m ago
```

**Checklist:**
- [ ] DATABASE_URL set (Supabase Session Pooler)
- [ ] OPENAI_API_KEY set
- [ ] PORT set (8000)
- [ ] Secrets verified in `flyctl secrets list`
- [ ] Values are masked (not visible in plain text)

---

## Phase 3: Code Changes for Production (Day 3-4)

### Add Health Check Endpoint to MCP Server

**File:** `src/mcp/server.py`

**Add after line 77 (after `mcp = FastMCP(...)`):**

```python
# Health check endpoint for Fly.io
@mcp.route("/health", methods=["GET"])
async def health_check(request):
    """
    Health check endpoint for container orchestration.

    Returns:
        200: Server is healthy and database is accessible
        503: Server is unhealthy or database is unreachable
    """
    try:
        # Check database connection
        if db:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "server": "rag-memory-mcp",
            "version": "0.6.0",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, 503
```

**Add imports at top of file:**
```python
from datetime import datetime, timezone
```

**Checklist:**
- [ ] Health check endpoint added to server.py
- [ ] Endpoint path: `/health`
- [ ] Method: GET
- [ ] Returns 200 when healthy
- [ ] Returns 503 when unhealthy
- [ ] Checks database connection
- [ ] Returns JSON with status, database, version, timestamp
- [ ] Error handling for database connection failures
- [ ] Logging for health check failures

---

### Enhance Logging for Production

**File:** `src/mcp/server.py`

**Update logging configuration (replace lines 35-36):**

```python
# Configure logging for production
import os
import sys

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Fly.io captures stdout
    ]
)
logger = logging.getLogger(__name__)
```

**Checklist:**
- [ ] Logging level configurable via LOG_LEVEL env var
- [ ] Default log level: INFO
- [ ] Logs to stdout (Fly.io captures this)
- [ ] Log format includes timestamp, logger name, level, message
- [ ] No file logging (Fly.io handles log aggregation)

---

### Update server.py main() for Production

**File:** `src/mcp/server.py`

**Update the main() function (around line 956) to support environment-based transport:**

```python
def main():
    """Run the MCP server with specified transport."""
    import sys
    import asyncio
    import click
    import os

    @click.command()
    @click.option(
        "--port",
        default=lambda: int(os.getenv("PORT", "3001")),
        help="Port to listen on for SSE or Streamable HTTP transport"
    )
    @click.option(
        "--transport",
        type=click.Choice(["stdio", "sse", "streamable-http"]),
        default=lambda: os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport type (stdio, sse, or streamable-http)"
    )
    def run_cli(port: int, transport: str):
        """Run the RAG memory MCP server with specified transport."""
        logger.info(f"Starting MCP server (transport={transport}, port={port})")

        async def run_server():
            """Inner async function to run the server and manage the event loop."""
            try:
                if transport == "stdio":
                    logger.info("Starting server with STDIO transport")
                    await mcp.run_stdio_async()
                elif transport == "sse":
                    logger.info(f"Starting server with SSE transport on port {port}")
                    mcp.settings.port = port
                    await mcp.run_sse_async()
                elif transport == "streamable-http":
                    logger.info(f"Starting server with Streamable HTTP transport on port {port}")
                    mcp.settings.port = port
                    mcp.settings.streamable_http_path = "/mcp"
                    await mcp.run_streamable_http_async()
                else:
                    raise ValueError(f"Unknown transport: {transport}")
            except KeyboardInterrupt:
                logger.info("Server stopped by user")
            except Exception as e:
                logger.error(f"Failed to start server: {e}", exc_info=True)
                raise

        try:
            asyncio.run(run_server())
        except KeyboardInterrupt:
            logger.info("Server interrupted")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    run_cli()
```

**Checklist:**
- [ ] PORT defaults to environment variable (Fly.io sets this)
- [ ] MCP_TRANSPORT environment variable supported
- [ ] Logs include transport and port information
- [ ] Graceful error handling for startup failures
- [ ] Keyboard interrupt handled gracefully

---

## Phase 4: Initial Deployment (Day 4)

### Deploy to Fly.io

**Commands:**
```bash
cd /Users/timkitchens/projects/ai-projects/rag-memory

# Deploy (first deployment will be slow - building image)
flyctl deploy

# Expected output:
# - Building Docker image
# - Pushing to Fly.io registry
# - Creating VM
# - Starting application
# - Health checks passing
# - Deployment successful

# Check deployment status
flyctl status

# View logs
flyctl logs

# Check specific machine
flyctl machine list
flyctl machine status <machine-id>
```

**Checklist:**
- [ ] Deployment command executed
- [ ] Docker image built successfully
- [ ] Image pushed to Fly.io registry
- [ ] VM created in iad region
- [ ] Application started
- [ ] Health checks passing
- [ ] Status shows "running"
- [ ] Logs show no errors

---

### Verify Deployment

**Test health endpoint:**
```bash
# Test HTTP (should redirect to HTTPS)
curl -I http://rag-memory-mcp.fly.dev/health

# Test HTTPS
curl https://rag-memory-mcp.fly.dev/health

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "server": "rag-memory-mcp",
#   "version": "0.6.0",
#   "timestamp": "2025-10-13T..."
# }
```

**Test SSE endpoint:**
```bash
# Test SSE connection (should hang waiting for events)
curl -N -H "Accept: text/event-stream" https://rag-memory-mcp.fly.dev/sse

# Should see: Connection established (may timeout after 60s if idle)
```

**Test MCP tools:**
```bash
# Test listing tools via HTTP
curl -X POST https://rag-memory-mcp.fly.dev/mcp \
  -H "Content-Type: application/json" \
  -d '{"method":"tools/list","params":{}}'

# Expected: JSON response with list of 14 tools
```

**Checklist:**
- [ ] Health endpoint returns 200
- [ ] Health response shows "healthy" and "connected"
- [ ] SSE endpoint accepts connections
- [ ] MCP tools endpoint works
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] SSL certificate valid (Fly.io automatic cert)

---

### Test Database Connection

**Via CLI (test from Fly.io VM):**
```bash
# SSH into the Fly.io machine
flyctl ssh console

# Inside the container, test database connection
python3 -c "
import os
from src.core.database import get_database
db = get_database()
conn = db.get_connection()
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM collections')
count = cur.fetchone()[0]
print(f'Collections count: {count}')
"

# Exit SSH
exit
```

**Checklist:**
- [ ] SSH console accessible
- [ ] Python environment available
- [ ] Database connection successful
- [ ] Query returns results from Supabase
- [ ] No connection errors in logs

---

## Phase 5: AI Agent Integration Testing (Day 5)

### Test with ChatGPT (Custom Action)

**ChatGPT Configuration:**
1. Go to ChatGPT → Settings → Custom Actions
2. Add new action:

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "RAG Memory API",
    "description": "Semantic search and document management for AI agents",
    "version": "0.6.0"
  },
  "servers": [
    {
      "url": "https://rag-memory-mcp.fly.dev"
    }
  ],
  "paths": {
    "/mcp": {
      "post": {
        "operationId": "mcpCall",
        "summary": "Call MCP server methods",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "method": {"type": "string"},
                  "params": {"type": "object"}
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object"
                }
              }
            }
          }
        }
      }
    }
  }
}
```

3. Test in ChatGPT:
   - "List available RAG collections"
   - "Search for 'Python async programming' in my documents"
   - "Create a new collection called 'test-docs'"

**Checklist:**
- [ ] ChatGPT custom action configured
- [ ] ChatGPT can connect to MCP server
- [ ] List collections works
- [ ] Search documents works
- [ ] Create collection works
- [ ] Responses are formatted correctly

---

### Test with Claude Desktop (Local - Ensure Unchanged)

**Claude Desktop Config:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "rag-memory-local": {
      "command": "rag-mcp-stdio",
      "args": [],
      "env": {
        "DATABASE_URL": "postgresql://raguser:ragpassword@localhost:54320/rag_memory",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

**Test:**
1. Restart Claude Desktop
2. Ask: "List my RAG collections"
3. Ask: "Search for 'test' in my documents"

**Checklist:**
- [ ] Claude Desktop still works with local stdio
- [ ] Local Docker database still accessible
- [ ] No interference with production deployment
- [ ] Both environments work independently

---

## Phase 6: Scale-to-Zero Configuration (Day 5)

### Enable Auto-Stop/Start

**Commands:**
```bash
# Get machine ID
flyctl machine list

# Configure auto-stop and auto-start
flyctl machine update <machine-id> \
  --auto-start \
  --auto-stop \
  --min-machines-running 0

# Verify configuration
flyctl machine status <machine-id>
```

**Test auto-stop:**
```bash
# Wait 5 minutes with no requests
sleep 300

# Check status (should show "stopped")
flyctl status

# Make request (should wake up)
curl https://rag-memory-mcp.fly.dev/health

# Check status again (should show "started")
flyctl status
```

**Measure cold start time:**
```bash
# After machine is stopped, time the first request
time curl https://rag-memory-mcp.fly.dev/health

# Document the time (should be <5 seconds)
```

**Checklist:**
- [ ] Auto-start enabled
- [ ] Auto-stop enabled
- [ ] Min machines = 0
- [ ] Machine stops after 5 minutes idle
- [ ] Machine wakes on request
- [ ] Cold start time <5 seconds
- [ ] Warm requests <500ms

---

## Phase 7: Documentation (Day 6-7)

### Create Deployment Guide

**File:** `docs/FLYIO_DEPLOYMENT_GUIDE.md`

**Contents:** (User-facing step-by-step guide)
- Prerequisites
- Supabase setup
- Fly.io account creation
- Docker local testing
- Deployment steps
- Verification checklist
- Troubleshooting common issues
- Cost analysis
- Monitoring and maintenance

**Checklist:**
- [ ] Deployment guide created
- [ ] All steps documented
- [ ] Commands tested and verified
- [ ] Screenshots added (optional)
- [ ] Troubleshooting section complete

---

### Update README.md

**File:** `README.md`

**Add section after "## MCP Server for AI Agents":**

```markdown
## Deployment to Fly.io (Production)

RAG Memory can be deployed to Fly.io for production use with AI agents that require remote access.

**Quick Deploy:**
```bash
# Prerequisites: Fly CLI installed and authenticated
cd rag-memory
flyctl deploy

# Set secrets
flyctl secrets set DATABASE_URL='<supabase-url>'
flyctl secrets set OPENAI_API_KEY='<your-key>'
```

**Result:** Your MCP server will be available at `https://rag-memory-mcp.fly.dev`

**Features:**
- HTTPS with automatic SSL certificates
- SSE and Streamable HTTP transports
- Scale-to-zero (cost: ~$5/month)
- Connects to Supabase (cloud database)
- Compatible with ChatGPT, Make.com, Zapier

**See:** [Fly.io Deployment Guide](./docs/FLYIO_DEPLOYMENT_GUIDE.md) for complete instructions.
```

**Checklist:**
- [ ] README.md updated
- [ ] Deployment section added
- [ ] Link to deployment guide
- [ ] Quick start commands included
- [ ] Benefits listed

---

### Update CLAUDE.md

**File:** `CLAUDE.md`

**Add section at end:**

```markdown
## Deployment to Fly.io

### Production Deployment

The MCP server can be deployed to Fly.io for remote access:

```bash
# Deploy
flyctl deploy

# View logs
flyctl logs

# SSH into container
flyctl ssh console

# Scale
flyctl scale count 1

# Stop
flyctl scale count 0
```

### Deployment Architecture

**Local Development:**
- Docker PostgreSQL (port 54320)
- MCP server via stdio
- Claude Desktop/Code connects locally

**Production (Fly.io):**
- Supabase PostgreSQL (Session Pooler)
- MCP server via SSE/HTTP (port 8000)
- Remote AI agents connect via HTTPS

**Both environments are independent and can run simultaneously.**

### Deployment Files

- `Dockerfile` - Multi-stage build with Playwright
- `fly.toml` - Fly.io configuration
- `.dockerignore` - Build optimization
- `docs/FLYIO_DEPLOYMENT_GUIDE.md` - Complete guide
- `docs/FLYIO_DEPLOYMENT_PLAN.md` - Technical planning doc

### Troubleshooting Deployment

**Container won't start:**
```bash
flyctl logs
flyctl ssh console
python -m src.mcp.server --transport sse --port 8000
```

**Database connection fails:**
- Verify DATABASE_URL secret is set
- Check Supabase Session Pooler URL (not Direct Connection)
- Test connection: `flyctl ssh console` → `python -c "from src.core.database import get_database; get_database()"`

**Health check fails:**
- Check `/health` endpoint: `curl https://rag-memory-mcp.fly.dev/health`
- View logs: `flyctl logs`
- Verify database connectivity

See [Fly.io Deployment Guide](./docs/FLYIO_DEPLOYMENT_GUIDE.md) for complete troubleshooting.
```

**Checklist:**
- [ ] CLAUDE.md updated
- [ ] Deployment commands documented
- [ ] Architecture comparison added
- [ ] Troubleshooting section added
- [ ] Links to guides included

---

## Phase 8: Final Testing (Day 8-9)

### Functionality Tests

**Run these tests via curl or AI agent:**

- [ ] `list_collections` - Returns existing collections
- [ ] `create_collection` - Creates new collection (with description)
- [ ] `search_documents` - Semantic search returns results
- [ ] `ingest_text` - Adds text to collection
- [ ] `ingest_url` - Crawls a web page (test with simple site)
- [ ] `get_document_by_id` - Retrieves document
- [ ] `update_document` - Updates document content
- [ ] `delete_document` - Deletes document
- [ ] `list_documents` - Lists documents in collection
- [ ] `get_collection_info` - Shows collection stats

**Acceptance:**
- All 10+ core tools tested and working
- No errors in Fly.io logs
- Database queries execute successfully
- Responses are properly formatted JSON

---

### Performance Tests

**Run these measurements:**

```bash
# Cold start (machine stopped)
flyctl scale count 0
sleep 60
time curl https://rag-memory-mcp.fly.dev/health
# Target: <5 seconds

# Warm request
time curl https://rag-memory-mcp.fly.dev/health
# Target: <500ms

# Search query
time curl -X POST https://rag-memory-mcp.fly.dev/mcp \
  -H "Content-Type: application/json" \
  -d '{"method":"search_documents","params":{"query":"test","limit":5}}'
# Target: <1 second

# Crawl URL (expected to be slow)
time curl -X POST https://rag-memory-mcp.fly.dev/mcp \
  -H "Content-Type: application/json" \
  -d '{"method":"ingest_url","params":{"url":"https://example.com","collection_name":"test"}}'
# Target: <10 seconds for simple page
```

**Checklist:**
- [ ] Cold start <5 seconds
- [ ] Warm health check <500ms
- [ ] Search query <1 second
- [ ] Web crawl completes successfully
- [ ] Performance metrics documented

---

### Reliability Tests

**Run these scenarios:**

1. **Concurrent Requests:**
   ```bash
   # Send 10 simultaneous requests
   for i in {1..10}; do
     curl https://rag-memory-mcp.fly.dev/health &
   done
   wait
   ```
   - [ ] All requests succeed
   - [ ] No rate limiting errors
   - [ ] Logs show concurrent handling

2. **Database Connection Recovery:**
   ```bash
   # Simulate database restart (pause Supabase temporarily)
   # Then resume and test
   curl https://rag-memory-mcp.fly.dev/health
   ```
   - [ ] Health check fails during downtime (503)
   - [ ] Health check recovers after database is back (200)
   - [ ] No manual intervention needed

3. **Long Running Operation:**
   ```bash
   # Crawl a documentation site (depth=2)
   curl -X POST https://rag-memory-mcp.fly.dev/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "method":"ingest_url",
       "params":{
         "url":"https://docs.python.org/3/",
         "collection_name":"test-crawl",
         "follow_links":true,
         "max_depth":2
       }
     }' \
     --max-time 600
   ```
   - [ ] Operation completes (may take 5-10 minutes)
   - [ ] Machine stays running during operation
   - [ ] No timeout errors
   - [ ] Documents ingested successfully

**Checklist:**
- [ ] Concurrent requests handled
- [ ] Database recovery automatic
- [ ] Long operations complete
- [ ] No crashes or restarts

---

## Final Acceptance

### Pre-Launch Checklist

**Infrastructure:**
- [ ] Docker image builds successfully
- [ ] Deployed to Fly.io (iad region)
- [ ] Health checks passing
- [ ] HTTPS accessible (SSL cert valid)
- [ ] Auto-stop/start configured
- [ ] Secrets configured (DATABASE_URL, OPENAI_API_KEY)

**Functionality:**
- [ ] All 14 MCP tools working
- [ ] Database connection to Supabase working
- [ ] Web crawling (Crawl4AI) working
- [ ] Search returns relevant results
- [ ] Document CRUD operations working

**Performance:**
- [ ] Cold start <5 seconds
- [ ] Warm requests <500ms
- [ ] Search queries <1 second
- [ ] Web crawls complete successfully

**Documentation:**
- [ ] FLYIO_DEPLOYMENT_GUIDE.md complete
- [ ] FLYIO_DEPLOYMENT_PLAN.md complete
- [ ] README.md updated
- [ ] CLAUDE.md updated
- [ ] Troubleshooting sections added

**Testing:**
- [ ] Local development still works (stdio)
- [ ] ChatGPT integration tested
- [ ] Concurrent requests handled
- [ ] Database recovery tested
- [ ] Long operations complete

**Monitoring:**
- [ ] Fly.io logs accessible (`flyctl logs`)
- [ ] Health checks configured
- [ ] Metrics visible in Fly.io dashboard
- [ ] Cost monitoring enabled

**Production Ready:**
- [ ] All acceptance criteria met
- [ ] No critical issues outstanding
- [ ] Deployment guide tested by second person
- [ ] Ready for user access

---

## Rollback Plan

**If deployment fails:**

```bash
# Option 1: Rollback to previous deployment
flyctl releases list
flyctl releases rollback <version>

# Option 2: Scale to zero (emergency stop)
flyctl scale count 0

# Option 3: Delete app (nuclear option)
flyctl apps destroy rag-memory-mcp
```

**Checklist:**
- [ ] Rollback procedure documented
- [ ] Previous working version identified
- [ ] Rollback tested (in staging if available)
- [ ] Communication plan for downtime

---

## Post-Deployment Tasks

**Day 10:**
- [ ] Monitor logs for 24 hours
- [ ] Check error rates
- [ ] Verify no memory leaks
- [ ] Confirm cost is as expected (~$5/month)
- [ ] Document any issues found
- [ ] Update troubleshooting guide

**Week 2:**
- [ ] Weekly check-ins on health and performance
- [ ] Review Fly.io metrics
- [ ] Check Supabase usage
- [ ] Update documentation based on learnings

**Month 1:**
- [ ] Monthly cost review
- [ ] Performance optimization if needed
- [ ] Scale up if usage increases
- [ ] Gather user feedback

---

**Status:** ✅ READY TO IMPLEMENT
**Next Step:** Review checklist → Begin Phase 1 (Dockerfile)
