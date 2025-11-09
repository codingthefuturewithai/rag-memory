# RAG Memory Reference Documentation

Complete reference documentation for RAG Memory - a PostgreSQL-based semantic search system with knowledge graph capabilities.

## Quick Navigation

**New to RAG Memory?**
→ Start with [WHAT_IS_IT.md](WHAT_IS_IT.md) - Conceptual overview

**Setting up locally?**
→ See [INSTALLATION.md](INSTALLATION.md) - Docker setup and verification

**Need CLI commands?**
→ See [CLI_GUIDE.md](CLI_GUIDE.md) - Complete command reference

**Configuring AI agents?**
→ See [MCP_GUIDE.md](MCP_GUIDE.md) - MCP server setup

**Deploying to cloud?**
→ See [CLOUD_SETUP.md](CLOUD_SETUP.md) - Supabase + Fly.io deployment

## Documentation Files

### Core Guides

**[WHAT_IS_IT.md](WHAT_IS_IT.md)** - Conceptual Overview
- What RAG Memory is and how it works
- Core capabilities and architecture
- Use cases and when to use it
- Read time: 5 minutes

**[INSTALLATION.md](INSTALLATION.md)** - Local Setup
- Docker installation and configuration
- Database initialization
- Verification steps
- Read time: 10 minutes

**[CLI_GUIDE.md](CLI_GUIDE.md)** - Command Reference
- All CLI commands with examples
- Service management (start/stop/status)
- Collection and document operations
- Search and ingestion commands
- Read time: 20 minutes

**[MCP_GUIDE.md](MCP_GUIDE.md)** - MCP Server Setup
- Configure Claude Desktop/Code/Cursor
- 18 available MCP tools
- Testing and troubleshooting
- Read time: 10 minutes

### Technical Details

**[VECTOR_SEARCH.md](VECTOR_SEARCH.md)** - Semantic Search
- How semantic search works
- Embedding model and dimensions
- Document chunking strategy
- Similarity scores and thresholds
- Query best practices
- Read time: 15 minutes

**[KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md)** - Entity Extraction
- What knowledge graphs provide
- Dual storage (RAG + Graph)
- Entity and relationship queries
- Temporal reasoning
- Configuration options
- Read time: 15 minutes

**[CONFIGURATION.md](CONFIGURATION.md)** - Settings
- Config file location and format
- Environment variables
- Database connection strings
- Security best practices
- Read time: 10 minutes

**[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common Issues
- Database connection errors
- Docker problems
- Ingestion issues
- Search problems
- Debugging commands
- Read time: 10 minutes

### Deployment

**[CLOUD_SETUP.md](CLOUD_SETUP.md)** - Cloud Deployment
- Supabase PostgreSQL setup
- Neo4j Aura configuration
- Fly.io MCP server deployment
- Production considerations
- Read time: 20 minutes

## Quick Reference

### Key Facts (Verified)

- **18 MCP tools** available for AI agents
- **text-embedding-3-small** model (1536 dimensions)
- **1000 character** chunks with **200 character** overlap
- **Port 54320** for PostgreSQL (local Docker)
- **Both PostgreSQL and Neo4j required** (no fallback)
- **Automatic synchronization** between RAG and Graph stores

### Common Commands

```bash
# Setup and status
rag status                    # Check all services
rag start                     # Start databases
rag stop                      # Stop databases

# Collections
rag collection create <name> --description "..." --domain "..." --domain-scope "..."
rag collection list
rag collection info <name>

# Ingestion
rag ingest text "content" --collection <name>
rag ingest file <path> --collection <name>
rag ingest url <url> --collection <name> --follow-links

# Search
rag search "query" --collection <name>
rag search "query" --threshold 0.7 --limit 10

# Knowledge graph
rag graph query-relationships "query"
rag graph query-temporal "how has X changed?"
```

### Similarity Score Ranges

- **0.90-1.00** - Near-identical (exact match)
- **0.70-0.89** - Highly relevant (what you're looking for)
- **0.50-0.69** - Related (relevant but less direct)
- **0.30-0.49** - Somewhat related (might be useful)
- **0.00-0.29** - Loosely related (usually noise)

### Recommended Thresholds

- **0.7** - Production/strict (high confidence only)
- **0.5** - Balanced (default, good mix)
- **0.3** - Exploratory (cast wide net)
- **None** - Top-N results regardless of score

## Learning Paths

### Quick Start (30 minutes)
1. Read [WHAT_IS_IT.md](WHAT_IS_IT.md)
2. Follow [INSTALLATION.md](INSTALLATION.md)
3. Test basic commands from [CLI_GUIDE.md](CLI_GUIDE.md)

### Complete Setup (2 hours)
1. Quick Start (above)
2. Configure MCP server via [MCP_GUIDE.md](MCP_GUIDE.md)
3. Read [VECTOR_SEARCH.md](VECTOR_SEARCH.md)
4. Review [CONFIGURATION.md](CONFIGURATION.md)

### Deep Dive (1 day)
1. Complete Setup (above)
2. Study [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md)
3. Explore [CLI_GUIDE.md](CLI_GUIDE.md) workflows
4. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
5. Plan [CLOUD_SETUP.md](CLOUD_SETUP.md) deployment

## What's Not Here

This directory contains **user-facing documentation only**. You will not find:

- Development status updates
- Implementation details (see source code)
- Performance benchmarks (vary by deployment)
- Pricing calculations (see OpenAI pricing docs)
- Third-party API details (see vendor docs)

## File Sizes

| File | Size | Read Time |
|------|------|-----------|
| WHAT_IS_IT.md | ~5 KB | 5 min |
| INSTALLATION.md | ~6 KB | 10 min |
| CLI_GUIDE.md | ~30 KB | 20 min |
| MCP_GUIDE.md | ~9 KB | 10 min |
| VECTOR_SEARCH.md | ~10 KB | 15 min |
| KNOWLEDGE_GRAPH.md | ~10 KB | 15 min |
| CONFIGURATION.md | ~9 KB | 10 min |
| TROUBLESHOOTING.md | ~11 KB | 10 min |
| CLOUD_SETUP.md | ~16 KB | 20 min |
| **Total** | **~106 KB** | **~115 min** |

## External Resources

**Neo4j:**
- Documentation: https://neo4j.com/docs/
- Cypher: https://neo4j.com/docs/cypher-manual/

**Graphiti:**
- Documentation: https://docs.graphiti.ai/
- GitHub: https://github.com/getzep/graphiti

**OpenAI:**
- Pricing: https://openai.com/api/pricing/
- Embeddings: https://platform.openai.com/docs/guides/embeddings

**PostgreSQL:**
- Documentation: https://www.postgresql.org/docs/
- pgvector: https://github.com/pgvector/pgvector

## Contributing

Found an error? Documentation unclear?

1. Check source code to verify facts
2. Update documentation with corrections
3. Remove any pollution (status declarations, benchmarks, etc.)
4. Keep it user-facing and verifiable

## Version

**Last Updated:** 2025-11-08
**Architecture:** Dual-store (PostgreSQL + Neo4j) with automatic synchronization
