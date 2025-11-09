# Developer Documentation

**Last Updated:** November 9, 2025

This directory contains **developer-focused** technical documentation for RAG Memory maintainers, contributors, and developers who need to understand the system internals.

---

## 👥 For Different Audiences

### **Are you a RAG Memory user?**

**→ See the [`.reference/`](../.reference/) directory** for:
- [Installation & Quick Start](../.reference/INSTALLATION.md)
- [MCP Server Setup](../.reference/MCP_GUIDE.md)
- [CLI Usage Guide](../.reference/CLI_GUIDE.md)
- [Cloud Deployment](../.reference/CLOUD_SETUP.md)
- [Troubleshooting](../.reference/TROUBLESHOOTING.md)
- [Knowledge Graph Queries](../.reference/KNOWLEDGE_GRAPH.md)
- [Vector Search Optimization](../.reference/VECTOR_SEARCH.md)

### **Are you setting up the development environment?**

**→ See [`CLAUDE.md`](../CLAUDE.md)** in the root directory for:
- Project overview and architecture summary
- Development commands (`uv`, `docker`, `pytest`)
- Code organization patterns
- Common development tasks
- Testing guidelines
- Debugging tips

### **Are you a developer/maintainer?**

**→ You're in the right place!** See documentation below.

---

## 📚 Developer Documentation

### Architecture & Design

**Essential reading for understanding how RAG Memory works:**

1. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture overview
   - High-level component diagram
   - Dual storage architecture (PostgreSQL+pgvector + Neo4j+Graphiti)
   - Module organization and responsibilities
   - Configuration system (3-tier priority)
   - Database schemas

2. **[FLOWS.md](./FLOWS.md)** - Operational flows with sequence diagrams
   - Ingest URL flow (complete web crawling → dual storage)
   - Ingest text flow (simplified content ingestion)
   - Search documents flow (vector similarity search)
   - Query relationships flow (knowledge graph queries)
   - Query temporal flow (evolution tracking)
   - Startup validation flow (health checks)
   - Collection creation flow

### Technical References

**Detailed guides for specific technical tasks:**

4. **[DATABASE_MIGRATION_GUIDE.md](./DATABASE_MIGRATION_GUIDE.md)** - Alembic migrations
   - Creating new migrations (`alembic revision --autogenerate`)
   - Running migrations (`uv run rag migrate`)
   - Reverting migrations
   - Handling migration conflicts
   - Best practices for schema changes

5. **[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md)** - Configuration reference
   - All environment variables and their defaults
   - Configuration file locations (system vs project)
   - 3-tier priority (ENV → .env → system config)
   - Database connection strings
   - API keys and credentials

---

## 🧭 Documentation Philosophy

We follow **DRY principles** (Don't Repeat Yourself):

- **User documentation** lives in [`.reference/`](../.reference/) - Installation, MCP setup, CLI usage, troubleshooting
- **Developer documentation** lives in `docs/` (this directory) - Architecture, internals, technical references
- **Development setup** lives in [`CLAUDE.md`](../CLAUDE.md) - Commands, patterns, common tasks

**When docs need to reference other docs:** We link rather than duplicate content.

---

## 🗺️ Quick Navigation

**I want to...**

| Task | Documentation |
|------|---------------|
| Understand the overall architecture | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| See how ingestion works end-to-end | [FLOWS.md](./FLOWS.md) - Ingest URL Flow |
| Create a database migration | [DATABASE_MIGRATION_GUIDE.md](./DATABASE_MIGRATION_GUIDE.md) |
| Configure environment variables | [ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md) |
| Set up local development | [`CLAUDE.md`](../CLAUDE.md) - Development Commands |
| Install RAG Memory as a user | [`.reference/INSTALLATION.md`](../.reference/INSTALLATION.md) |
| Configure MCP server | [`.reference/MCP_GUIDE.md`](../.reference/MCP_GUIDE.md) |
| Use the CLI tool | [`.reference/CLI_GUIDE.md`](../.reference/CLI_GUIDE.md) |
| Deploy to production | [`.reference/CLOUD_SETUP.md`](../.reference/CLOUD_SETUP.md) |
| Troubleshoot issues | [`.reference/TROUBLESHOOTING.md`](../.reference/TROUBLESHOOTING.md) |

---

## 📝 Contributing to Documentation

When adding new documentation:

1. **Determine the audience:**
   - End users → Add to `.reference/`
   - Developers → Add to `docs/`
   - Development setup → Update `CLAUDE.md`

2. **Follow DRY principles:**
   - Link to existing docs rather than duplicating
   - Keep related information together
   - Update this README.md when adding new docs

3. **Use clear structure:**
   - Start with "Last Updated" date
   - Include table of contents for long docs
   - Use Mermaid diagrams (embedded code, not PNG files)
   - Link to related documentation at the end

4. **Keep diagrams as code:**
   - Use Mermaid for all diagrams (renders on GitHub)
   - No PNG/SVG files (they become stale quickly)
   - Diagrams live in the same markdown file as the content

---

## 🔗 External Resources

- **RAG Memory Repository:** [github.com/yourusername/rag-memory](https://github.com/yourusername/rag-memory)
- **MCP Specification:** [modelcontextprotocol.org](https://modelcontextprotocol.org)
- **FastMCP Framework:** [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)
- **Graphiti Library:** [github.com/getzep/graphiti](https://github.com/getzep/graphiti)
- **pgvector Extension:** [github.com/pgvector/pgvector](https://github.com/pgvector/pgvector)
