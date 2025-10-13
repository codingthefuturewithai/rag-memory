# Multi-stage build for RAG Memory MCP Server on Fly.io
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
