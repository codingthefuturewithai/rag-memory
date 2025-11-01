# Multi-stage build for RAG Memory MCP Server on Fly.io
# Base: Microsoft Playwright image (includes Chromium for Crawl4AI)

# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM mcr.microsoft.com/playwright:v1.55.0-jammy AS builder

WORKDIR /app

# Copy dependency files (README.md required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install pip, then uv, then sync dependencies
RUN apt-get update && apt-get install -y python3-pip && \
    python3 -m pip install --no-cache-dir -U uv && \
    uv sync --frozen --no-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy local patched crawl4ai and install it (replaces pyproject.toml version)
COPY crawl4ai-local /tmp/crawl4ai-local
RUN uv pip uninstall -y crawl4ai || true && \
    uv pip install /tmp/crawl4ai-local

# ============================================================================
# Stage 2: Runtime image
# ============================================================================
FROM mcr.microsoft.com/playwright:v1.55.0-jammy

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src /app/src
COPY deploy/alembic /app/alembic
COPY deploy/alembic/alembic.ini /app/alembic.ini
COPY deploy/docker/init.sql /app/init.sql
COPY pyproject.toml /app/pyproject.toml

# Environment variables
ENV PORT=8000
ENV FASTMCP_HOST=0.0.0.0
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Note: Health checks are handled by Fly.io TCP checks in fly.toml
# FastMCP does not support HTTP health endpoints

# Run MCP server with SSE transport on port 8000
CMD ["python", "-m", "src.mcp.server", "--transport", "sse", "--port", "8000"]
