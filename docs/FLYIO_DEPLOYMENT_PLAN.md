# Fly.io Deployment Plan for RAG Memory MCP Server

**Branch:** `feature/flyio-deployment`
**Date:** 2025-10-13
**Status:** Planning Phase

---

## Executive Summary

This document outlines a comprehensive plan to deploy the RAG Memory MCP server to Fly.io as a production-ready service. The deployment will support SSE and Streamable HTTP transports for AI agent connectivity while maintaining compatibility with local development.

**Key Goals:**
1. Deploy MCP server to Fly.io with Playwright + Crawl4AI support
2. Connect to Supabase for production database (already configured)
3. Support both SSE and Streamable HTTP transports
4. Enable scale-to-zero for cost optimization (~$5/month with Supabase)
5. Maintain local development workflow (Docker + stdio transport)

---

## Architecture Overview

### Current State (Local Development)
```
┌─────────────────────┐
│  AI Agent (Local)   │
│  - Claude Desktop   │
│  - Claude Code      │
│  - Cursor           │
└──────────┬──────────┘
           │ stdio transport
           ↓
┌─────────────────────┐      ┌──────────────────┐
│  MCP Server (Local) │─────→│  PostgreSQL      │
│  - FastMCP          │      │  (Docker:54320)  │
│  - 14 Tools         │      │  + pgvector      │
│  - Crawl4AI         │      └──────────────────┘
└─────────────────────┘
```

### Target State (Production on Fly.io)
```
┌─────────────────────┐
│  AI Agent (Remote)  │
│  - ChatGPT          │
│  - Custom Agents    │
└──────────┬──────────┘
           │ SSE / HTTP
           ↓
┌─────────────────────────────────────┐
│         Fly.io (iad region)         │
│  ┌─────────────────────────────┐   │
│  │  MCP Server Container       │   │      ┌──────────────────────┐
│  │  - Playwright base image    │───┼─────→│  Supabase Database   │
│  │  - FastMCP (SSE + HTTP)     │   │      │  (us-east-1)         │
│  │  - Crawl4AI (headless)      │   │      │  - PostgreSQL 17     │
│  │  - Port 8000 exposed        │   │      │  - pgvector          │
│  └─────────────────────────────┘   │      │  - Session Pooler    │
│                                     │      └──────────────────────┘
│  Auto-start/stop (scale-to-zero)   │
└─────────────────────────────────────┘
```

---

## Current System Analysis

### ✅ What's Already Working
1. **Database Migration System**
   - Alembic migrations in place (`migrations/` directory)
   - Supabase schema setup documented (`docs/SUPABASE_SCHEMA_SETUP.md`)
   - Multi-environment config system (local Docker + Supabase)

2. **MCP Server Implementation**
   - FastMCP server with 14 tools (`src/mcp/server.py`)
   - Three transport modes: stdio (local), SSE, and Streamable HTTP
   - Entry points configured in `pyproject.toml`:
     - `rag-mcp-stdio` - Local development
     - `rag-mcp-sse` - SSE transport (port 3001)
     - `rag-mcp-http` - HTTP transport (port 3001)

3. **Web Crawling Infrastructure**
   - Crawl4AI integration (`src/ingestion/web_crawler.py`)
   - Playwright dependency (`playwright>=1.49.0`)
   - Headless browser support already configured
   - Works in async mode (required for MCP)

4. **Configuration System**
   - Three-tier config: env vars → project `.env` → global `~/.rag-memory-env`
   - DATABASE_URL and OPENAI_API_KEY management
   - Supabase connection strings tested and working

### ⚠️ What Needs to Be Created
1. **Docker Infrastructure**
   - `Dockerfile` based on Playwright image
   - `.dockerignore` for build optimization
   - Health check endpoint for Fly.io

2. **Fly.io Configuration**
   - `fly.toml` with service definitions
   - Region selection (iad = Ashburn, VA)
   - Port mapping (8000 internal → 80/443 external)
   - Scale-to-zero configuration

3. **Production Readiness**
   - Environment variable injection via Fly secrets
   - Logging configuration for Fly.io
   - Error handling for remote clients
   - Connection pooling optimization (if needed)

### 🔍 Potential Issues to Address
1. **Playwright Browser Installation**
   - Challenge: Chromium browsers are large (~350MB)
   - Solution: Use `mcr.microsoft.com/playwright:v1.44.0-jammy` base image
   - Already includes Chromium with proper dependencies

2. **Build Time**
   - Challenge: Python dependencies + Playwright = slow builds
   - Solution: Multi-stage Docker build (separate dependency layer)
   - Cache dependency layer between builds

3. **Crawl4AI Performance**
   - Challenge: Headless browser crawling can be slow
   - Current: Already configured for headless mode
   - Mitigation: Document crawl performance expectations

4. **Database Connection Management**
   - Challenge: Fly.io may restart containers (transient connections)
   - Current: Using Supabase Session Pooler (persistent connections)
   - Solution: Ensure proper connection retry logic

---

## Implementation Plan

### Phase 1: Docker Setup ✅ (Week 1, Days 1-2)

**Goal:** Create production-ready Dockerfile that works locally and on Fly.io

**Tasks:**
1. Create `Dockerfile` with multi-stage build
   - Stage 1: Playwright base image + Python dependencies
   - Stage 2: Copy application code
   - Configure PORT environment variable (8000)
   - Set PLAYWRIGHT environment variables to skip browser downloads

2. Create `.dockerignore`
   - Exclude `.venv`, `__pycache__`, `.git`, test data
   - Minimize build context size

3. Test locally
   ```bash
   docker build -t rag-memory-mcp .
   docker run -p 8000:8000 \
     -e DATABASE_URL="..." \
     -e OPENAI_API_KEY="..." \
     rag-memory-mcp
   ```

4. Verify SSE endpoint works
   ```bash
   curl -N -H "Accept: text/event-stream" http://localhost:8000/sse
   ```

**Acceptance Criteria:**
- ✅ Docker image builds successfully (<10 minutes)
- ✅ Container starts and listens on port 8000
- ✅ SSE endpoint responds to curl requests
- ✅ Crawl4AI can fetch a test web page
- ✅ Database connection to Supabase works

---

### Phase 2: Fly.io Configuration ✅ (Week 1, Day 3)

**Goal:** Configure Fly.io app with proper networking and secrets

**Tasks:**
1. Install Fly CLI and authenticate
   ```bash
   curl -L https://fly.io/install.sh | sh
   flyctl auth login
   ```

2. Create Fly.io app (do NOT deploy yet)
   ```bash
   flyctl launch --region iad --name rag-memory-mcp --no-deploy
   ```

3. Configure `fly.toml`
   - App name: `rag-memory-mcp`
   - Region: `iad` (Ashburn, VA - closest to Supabase us-east-1)
   - Internal port: 8000
   - External ports: 80 (HTTP) and 443 (HTTPS/TLS)
   - Concurrency limits: soft=20, hard=25

4. Set Fly secrets
   ```bash
   flyctl secrets set DATABASE_URL="postgresql://postgres.[REF]:[PASS]@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
   flyctl secrets set OPENAI_API_KEY="sk-..."
   flyctl secrets set PORT=8000
   ```

5. Verify configuration
   ```bash
   flyctl secrets list
   flyctl config validate
   ```

**Acceptance Criteria:**
- ✅ Fly.io app created (not deployed)
- ✅ fly.toml configured with correct ports and region
- ✅ Secrets set and verified (masked output)

---

### Phase 3: Initial Deployment & Testing 🚀 (Week 1, Day 4)

**Goal:** Deploy to Fly.io and verify basic functionality

**Tasks:**
1. Deploy to Fly.io
   ```bash
   flyctl deploy
   ```
   - Wait for build and deployment (~5-10 minutes first time)
   - Check deployment logs for errors

2. Verify deployment
   ```bash
   flyctl status
   flyctl logs
   ```

3. Test SSE endpoint
   ```bash
   curl -N -H "Accept: text/event-stream" https://rag-memory-mcp.fly.dev/sse
   ```

4. Test Streamable HTTP endpoint
   ```bash
   curl -X POST https://rag-memory-mcp.fly.dev/mcp \
     -H "Content-Type: application/json" \
     -d '{"method":"tools/list","params":{}}'
   ```

5. Test from AI agent (ChatGPT custom action)
   ```json
   {
     "url": "https://rag-memory-mcp.fly.dev",
     "transport": "sse",
     "description": "RAG Memory semantic search and document management"
   }
   ```

**Acceptance Criteria:**
- ✅ Deployment completes without errors
- ✅ Container starts and stays healthy (>5 minutes)
- ✅ SSE endpoint accessible via HTTPS
- ✅ Streamable HTTP endpoint works
- ✅ AI agent can connect and list tools (14 tools visible)
- ✅ Basic search query returns results from Supabase

---

### Phase 4: Scale-to-Zero Configuration 💰 (Week 1, Day 5)

**Goal:** Enable cost optimization with auto-stop/start

**Tasks:**
1. Enable Fly Machines auto-scaling
   ```bash
   flyctl scale count 1
   flyctl machine update --auto-start --auto-stop <machine-id>
   ```

2. Configure auto-stop timeout (5 minutes idle)
   - Update `fly.toml` with auto_stop_machines section

3. Test auto-stop behavior
   - Wait 5 minutes with no requests
   - Verify machine stops: `flyctl status`
   - Send request, verify machine wakes up

4. Document wake-up latency
   - Measure time from request to first response
   - Expected: 2-5 seconds for cold start

**Acceptance Criteria:**
- ✅ Machine stops after 5 minutes idle
- ✅ Machine auto-starts on incoming request
- ✅ Cold start latency documented (<5 seconds)
- ✅ Cost projection confirmed (~$5/month with Supabase)

---

### Phase 5: Production Hardening 🔒 (Week 2, Days 1-2)

**Goal:** Add production-grade reliability and monitoring

**Tasks:**
1. **Health Check Endpoint**
   - Add `/health` endpoint to MCP server
   - Returns database connection status + version info
   - Update fly.toml with health check configuration

2. **Logging Enhancement**
   - Configure structured logging (JSON format)
   - Add request ID tracking for debugging
   - Set appropriate log levels (INFO for production)

3. **Error Handling**
   - Graceful degradation for database connection failures
   - Retry logic for transient Supabase connection issues
   - Proper HTTP error codes for client errors

4. **Connection Management**
   - Verify psycopg3 connection pooling behavior
   - Test connection recovery after Supabase maintenance
   - Document connection timeout settings

5. **Security Review**
   - Verify DATABASE_URL and OPENAI_API_KEY are in secrets (not fly.toml)
   - Check that .env files are in .dockerignore
   - Confirm HTTPS enforced for all endpoints

**Acceptance Criteria:**
- ✅ /health endpoint returns 200 with database status
- ✅ Logs visible in `flyctl logs` with proper format
- ✅ Server recovers from database connection loss
- ✅ Security audit passes (no secrets in config files)
- ✅ Error messages are helpful for debugging

---

### Phase 6: Documentation & Deployment Guide 📚 (Week 2, Day 3)

**Goal:** Document deployment process for future maintenance

**Tasks:**
1. Create `docs/FLYIO_DEPLOYMENT_GUIDE.md`
   - Step-by-step deployment instructions
   - Troubleshooting common issues
   - Cost analysis and scaling options

2. Update `README.md`
   - Add "Deployment to Fly.io" section
   - Link to deployment guide
   - Update architecture diagram

3. Create deployment scripts
   - `scripts/deploy-production.sh` - Deploy with validation
   - `scripts/check-production-health.sh` - Health checks
   - `scripts/rollback-deployment.sh` - Emergency rollback

4. Document AI agent connection
   - ChatGPT custom action configuration
   - Make.com / Zapier webhook setup
   - Custom agent integration examples

**Acceptance Criteria:**
- ✅ Deployment guide complete and tested
- ✅ README.md updated with Fly.io section
- ✅ Deployment scripts tested and working
- ✅ AI agent connection examples documented

---

### Phase 7: Testing & Validation ✅ (Week 2, Days 4-5)

**Goal:** Comprehensive end-to-end testing

**Test Categories:**

1. **Functionality Tests**
   - [ ] Search documents (semantic search working)
   - [ ] Create collection
   - [ ] Ingest text content
   - [ ] Ingest URL (Crawl4AI working in container)
   - [ ] Update document
   - [ ] Delete document
   - [ ] List collections

2. **Performance Tests**
   - [ ] Query latency (<500ms for search)
   - [ ] Crawl latency (document expected slowness)
   - [ ] Cold start time (<5 seconds)
   - [ ] Warm request time (<100ms)

3. **Reliability Tests**
   - [ ] Handles 10 concurrent requests
   - [ ] Recovers from database connection loss
   - [ ] Handles malformed requests gracefully
   - [ ] Survives 1 hour of continuous requests

4. **Integration Tests**
   - [ ] ChatGPT can connect and use tools
   - [ ] Claude Desktop can connect (local stdio still works)
   - [ ] Make.com webhook integration
   - [ ] Direct HTTP API calls

**Acceptance Criteria:**
- ✅ All functionality tests pass
- ✅ Performance meets targets
- ✅ Reliability tests pass without intervention
- ✅ Integration tests pass with real AI agents

---

## File Structure (New & Modified)

### New Files to Create
```
rag-memory/
├── Dockerfile                           # Multi-stage build with Playwright
├── .dockerignore                        # Build context optimization
├── fly.toml                             # Fly.io configuration
├── docs/
│   ├── FLYIO_DEPLOYMENT_GUIDE.md       # Complete deployment guide
│   └── FLYIO_DEPLOYMENT_PLAN.md        # This document
└── scripts/
    ├── deploy-production.sh             # Automated deployment
    ├── check-production-health.sh       # Health check script
    └── rollback-deployment.sh           # Emergency rollback
```

### Files to Modify
```
rag-memory/
├── README.md                            # Add Fly.io deployment section
├── src/mcp/server.py                    # Add /health endpoint
└── CLAUDE.md                            # Document deployment workflow
```

---

## Technical Specifications

### Dockerfile Structure
```dockerfile
# Stage 1: Playwright base with dependencies
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy AS builder

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install -U uv && \
    uv sync --frozen --no-dev

# Stage 2: Application
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY . /app

# Environment configuration
ENV PORT=8000
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Run MCP server with SSE transport
CMD ["python", "-m", "src.mcp.server", "--transport", "sse", "--port", "8000"]
```

### fly.toml Structure
```toml
app = "rag-memory-mcp"
primary_region = "iad"
kill_signal = "SIGINT"
kill_timeout = "5s"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"

[[services]]
  internal_port = 8000
  processes = ["app"]
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"

  [[services.http_checks]]
    grace_period = "10s"
    interval = "30s"
    method = "GET"
    path = "/health"
    timeout = "5s"
```

---

## Cost Analysis

### Fly.io Costs (Estimated)
```
Base Configuration:
- 1 shared-cpu-1x machine (256MB RAM)
- Scale-to-zero enabled
- iad region (US East)

Projected Usage (2 hours/day):
- Active time: ~60 hours/month
- Cost: $0.0000008/sec * 216,000 sec = ~$1.73/month
- With overhead: ~$3-5/month

Heavy Usage (24/7):
- Active time: ~720 hours/month
- Cost: ~$40/month
- Solution: Upgrade to dedicated CPU if needed
```

### Supabase Costs
```
Free Tier:
- 500MB database storage
- Unlimited API requests
- Session Pooler included
- Cost: $0/month

Pro Tier (if needed):
- 8GB database storage
- Automated backups
- Point-in-time recovery
- Cost: $25/month
```

### OpenAI Costs
```
text-embedding-3-small:
- $0.02 per 1M tokens
- Search: ~$0.00003 per query (negligible)
- Ingestion: ~$0.15 per 10K documents
- Typical monthly usage: <$5
```

**Total Monthly Cost:**
- Minimal usage: **$5-10/month** (Fly.io free tier + Supabase free tier)
- Production usage: **$30-50/month** (Fly.io + Supabase Pro)

---

## Risk Assessment & Mitigation

### High Risks

1. **Risk:** Playwright/Chromium compatibility issues in container
   - **Likelihood:** Low (using official Playwright image)
   - **Impact:** High (blocks deployment)
   - **Mitigation:** Test Crawl4AI locally in Docker first
   - **Contingency:** Fall back to requests-based crawling (no JS)

2. **Risk:** Supabase connection limit exceeded
   - **Likelihood:** Medium (free tier = 60 connections)
   - **Impact:** Medium (requests fail)
   - **Mitigation:** Use Session Pooler (already configured)
   - **Contingency:** Upgrade to Supabase Pro (500 connections)

3. **Risk:** Cold start latency unacceptable for users
   - **Likelihood:** Medium (large container = slow start)
   - **Impact:** Low (only first request affected)
   - **Mitigation:** Document expected latency (2-5 seconds)
   - **Contingency:** Keep machine warm with cron job

### Medium Risks

4. **Risk:** Docker build time too slow (>10 minutes)
   - **Likelihood:** Medium (many dependencies)
   - **Impact:** Low (only affects deployments)
   - **Mitigation:** Multi-stage build with caching
   - **Contingency:** Pre-build dependency layer image

5. **Risk:** Fly.io costs higher than expected
   - **Likelihood:** Low (usage is predictable)
   - **Impact:** Low (budget allows $50/month)
   - **Mitigation:** Enable scale-to-zero immediately
   - **Contingency:** Monitor usage and adjust scaling

### Low Risks

6. **Risk:** SSL certificate issues with Fly.io
   - **Likelihood:** Very Low (Fly.io handles this)
   - **Impact:** Medium (blocks HTTPS)
   - **Mitigation:** Use Fly.io automatic certificates
   - **Contingency:** Fly.io support has 24/7 availability

---

## Success Metrics

### Phase 1-3 (Deployment)
- [ ] Docker image builds successfully
- [ ] Deployed to Fly.io (iad region)
- [ ] HTTPS accessible at https://rag-memory-mcp.fly.dev
- [ ] Database connection to Supabase works
- [ ] All 14 MCP tools functional

### Phase 4-5 (Optimization)
- [ ] Scale-to-zero working (stops after 5 min idle)
- [ ] Cold start <5 seconds
- [ ] Query latency <500ms (warm)
- [ ] /health endpoint returns 200

### Phase 6-7 (Production Ready)
- [ ] Documentation complete
- [ ] All functionality tests pass
- [ ] Integration with ChatGPT/Claude working
- [ ] Monitoring and logging configured
- [ ] Cost <$10/month (initial usage)

---

## Timeline Estimate

**Total Duration:** 2 weeks (10 working days)

**Week 1:**
- Days 1-2: Docker setup and local testing
- Day 3: Fly.io configuration
- Day 4: Initial deployment and validation
- Day 5: Scale-to-zero configuration

**Week 2:**
- Days 1-2: Production hardening (logging, error handling)
- Day 3: Documentation and deployment scripts
- Days 4-5: Comprehensive testing and validation

**Contingency:** +3 days for unexpected issues

---

## Next Steps (Immediate Actions)

1. **Review this plan** with stakeholders
2. **Create branch:** `feature/flyio-deployment` ✅ (Done)
3. **Start Phase 1:** Create Dockerfile
4. **Test locally:** Verify Docker image works before Fly.io deployment
5. **Proceed sequentially:** Don't skip phases

---

## Questions to Answer Before Starting

### Technical Questions
1. ✅ Do we have a Supabase account set up? **YES** (documented in SUPABASE_MIGRATION.md)
2. ✅ Is the database schema current on Supabase? **YES** (Alembic migrations working)
3. ✅ Do we have budget approval for $30-50/month? **ASSUMED YES** (user Tim Kitchens)
4. ⚠️ What's the desired public URL? **DEFAULT:** rag-memory-mcp.fly.dev (can customize later)
5. ⚠️ Do we need authentication for remote access? **DEFAULT:** No (open API initially)

### Operational Questions
6. ⚠️ Who will have access to deploy? **DEFAULT:** Tim Kitchens (single developer)
7. ⚠️ What's the rollback strategy if deployment fails? **TO DOCUMENT:** Manual rollback via Fly CLI
8. ⚠️ What monitoring do we need? **DEFAULT:** Fly.io built-in metrics + logs
9. ⚠️ What's the SLA target? **DEFAULT:** Best-effort (not mission-critical)
10. ⚠️ How do we handle Fly.io region outages? **DEFAULT:** Accept downtime (no multi-region)

---

## References

1. **Deployment Guide from User:** `docs/deploy_mcp_flyio_crawl_4_ai_supabase.md`
2. **Supabase Migration:** `docs/SUPABASE_MIGRATION.md`
3. **MCP Server Implementation:** `src/mcp/server.py`
4. **Web Crawler:** `src/ingestion/web_crawler.py`
5. **Fly.io Docker Guide:** https://fly.io/docs/app-guides/dockerfile/
6. **Fly.io Auto-Stop:** https://fly.io/docs/machines/autostop/
7. **Playwright Docker:** https://playwright.dev/docs/docker

---

## Appendix: Local Development Workflow (Unchanged)

**Local development will continue to work exactly as before:**

```bash
# Start local database
docker-compose up -d

# Run CLI locally
export DATABASE_URL="postgresql://raguser:ragpassword@localhost:54320/rag_memory"
uv run rag status

# Run MCP server locally (stdio for Claude Desktop)
uv run python -m src.mcp.server --transport stdio

# Claude Desktop continues to connect via stdio (no changes needed)
```

**Production and local are completely independent:**
- Local: Docker database (port 54320) + stdio transport
- Production: Supabase database + SSE/HTTP transports on Fly.io

---

**Plan Status:** ✅ READY FOR REVIEW
**Next Action:** Review plan → Approve → Start Phase 1 (Dockerfile)
