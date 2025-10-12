# Documentation

This directory contains all project documentation organized by category.

## 📚 User Documentation

- **[MCP_SERVER_GUIDE.md](./MCP_SERVER_GUIDE.md)** - Complete guide to running and using the MCP server
  - Transport modes (stdio, SSE, streamable-http)
  - MCP Inspector testing
  - Claude Desktop configuration
  - Tool reference with examples
  - Common workflows and troubleshooting

- **[PROJECT_STATUS.md](./PROJECT_STATUS.md)** - Current project status and capabilities
  - Feature completion status
  - Test results
  - Performance metrics
  - Known issues and roadmap

## 📐 Design Specifications

Located in `specifications/`:

- **[pgvector-poc-specification.md](./specifications/pgvector-poc-specification.md)** - Original POC specification
  - Architecture design
  - Success criteria
  - Technical requirements

- **[pgvector-poc-extension-document-chunking.md](./specifications/pgvector-poc-extension-document-chunking.md)** - Document chunking design
  - Chunking strategy
  - Implementation approach
  - Performance considerations

- **[pgvector-poc-extension-rag-optimizations.md](./specifications/pgvector-poc-extension-rag-optimizations.md)** - RAG optimization design
  - Query expansion
  - Hybrid search (vector + keyword)
  - Reranking strategies

- **[pgvector-poc-extension-web-crawling.md](./specifications/pgvector-poc-extension-web-crawling.md)** - Web crawling design
  - Crawl4AI integration
  - Link following strategy
  - Metadata tracking

## 📦 Archive

Located in `archive/` - Historical working documents from feature development:

- **IMPLEMENTATION_SUMMARY.md** - Website analysis feature implementation notes
- **MCP_IMPLEMENTATION_COMPLETE.md** - MCP server completion report
- **MORNING_REPORT.md** - Daily status report from implementation
- **IMPLEMENTATION_PLAN.md** - RAG optimization implementation plan
- **MCP_IMPLEMENTATION_PLAN.md** - Original MCP server plan (55KB detailed plan)
- **web-crawling-planning.md** - Web crawling feature planning
- **RAG_OPTIMIZATION_RESULTS.md** - Benchmark results from optimization work

**Note:** Archive documents are kept for historical reference but are superseded by current implementation and documentation.

## 📖 Quick Reference

**For new users:**
1. Start with main [README.md](../README.md) for project overview and quick start
2. Read [PROJECT_STATUS.md](./PROJECT_STATUS.md) to understand current capabilities
3. Follow [MCP_SERVER_GUIDE.md](./MCP_SERVER_GUIDE.md) to set up the MCP server

**For developers:**
1. Check [CLAUDE.md](../CLAUDE.md) for development guidelines
2. Review specifications/ for feature designs
3. Reference archive/ for historical context

**For AI agents:**
- [CLAUDE.md](../CLAUDE.md) contains instructions specifically for Claude Code
- MCP server exposes 11 tools for programmatic access (see MCP_SERVER_GUIDE.md)
