# Multi-stage build for RAG Memory MCP Server on Fly.io
# Base: Microsoft Playwright image (includes Chromium for Crawl4AI)

# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy AS builder

WORKDIR /app

# Copy dependency files (README.md required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install pip, then uv, then sync dependencies
RUN apt-get update && apt-get install -y python3-pip && \
    python3 -m pip install --no-cache-dir -U uv && \
    uv sync --frozen --no-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

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
