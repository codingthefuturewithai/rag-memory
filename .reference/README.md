# RAG Memory Reference Documentation

Welcome! This directory contains all the reference documentation for RAG Memory.

---

## 🚀 Quick Start: Choose Your Path

### Are you setting up locally or in the cloud?

**👨‍💻 LOCAL SETUP (Docker on your machine)**
- Best for: Development, testing, learning
- Time: 30 minutes
- Command: `/getting-started`
- Read next: [OVERVIEW.md](OVERVIEW.md)

**☁️ CLOUD DEPLOYMENT (Supabase + Aura + Fly.io)**
- Best for: Production, team access, cloud AI agents
- Time: 1 hour
- Command: `/cloud-setup`
- Read next: [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md)

---

## Quick Navigation

### 🎯 Starting Out?
**Choose above, then come back here for reference.**

For detailed CLI commands: [OVERVIEW.md](OVERVIEW.md)

### 🔍 Looking for Something Specific?

**"How do I deploy to the cloud?"**
→ [CLOUD_DEPLOYMENT.md](CLOUD_DEPLOYMENT.md) - Complete reference guide

**"How do I set up an MCP server?"**
→ [MCP_QUICK_START.md](MCP_QUICK_START.md)

**"What are the 17 MCP tools and how do I use them?"**
→ [MCP_QUICK_START.md](MCP_QUICK_START.md) - "Available Tools (17 Total)"

**"How does the search work? Is it good?"**
→ [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md)

**"What's this Knowledge Graph thing?"**
→ [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md)

**"How much will this cost me (OpenAI)?"**
→ [PRICING.md](PRICING.md)

**"Tell me everything about RAG Memory"**
→ [OVERVIEW.md](OVERVIEW.md)

---

## 📚 Complete File Reference

### Core Documentation

| File | Purpose | When to Read |
|------|---------|--------------|
| **OVERVIEW.md** | Comprehensive guide to everything | When first learning, or need complete reference |
| **MCP_QUICK_START.md** | Setup & tool reference for AI agents | When configuring Claude Desktop/Code/Cursor |
| **SEARCH_OPTIMIZATION.md** | Search quality & optimization | When tuning search quality or understanding performance |
| **KNOWLEDGE_GRAPH.md** | Entity relationships & temporal tracking | When exploring knowledge graph features |
| **PRICING.md** | Cost analysis & budgets | When estimating costs or budgeting |
| **DOCUMENTATION_UPDATE_SUMMARY.md** | What's new in documentation (this session) | When reviewing changes made 2025-10-20 |

### Related Files (Project Root)

- **CLAUDE.md** - Complete CLI commands reference
- **README.md** - Project overview

---

## 🚀 Common Workflows

### Setup & First Run
1. Read: [OVERVIEW.md](OVERVIEW.md) - "What Is RAG Memory?" section
2. Read: [OVERVIEW.md](OVERVIEW.md) - "Two Ways to Use RAG Memory" section
3. Do: `/getting-started` command in Claude Code
4. Read: [MCP_QUICK_START.md](MCP_QUICK_START.md) for agent configuration

### Building Knowledge Base
1. Read: [OVERVIEW.md](OVERVIEW.md) - "Web Crawling & Link Following"
2. Read: [OVERVIEW.md](OVERVIEW.md) - "Re-Crawl for Updates"
3. Reference: CLAUDE.md - CLI ingestion commands
4. Use: `rag ingest url`, `rag ingest file`, `rag ingest directory`

### Optimizing Search
1. Read: [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - "Baseline Search (RECOMMENDED)"
2. Read: [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - "Threshold Tuning Guide"
3. Use: `rag search "query" --threshold 0.7` (or 0.5, 0.3)

### Exploring Knowledge Graphs
1. Read: [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - "Overview"
2. Read: [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - "Setup & Prerequisites"
3. Understand: Experimental status (Phase 4 in progress)
4. Use: `query_relationships()` and `query_temporal()` tools

### Budgeting Costs
1. Read: [PRICING.md](PRICING.md) - "Typical Costs"
2. Reference: [OVERVIEW.md](OVERVIEW.md) - "Costs & Budgets"
3. Calculate: tokens × $0.02 per 1M tokens

### Deploying to Production
1. Read: [OVERVIEW.md](OVERVIEW.md) - "Deployment Options"
2. Reference: scripts/deploy.sh for Fly.io
3. Choose: Local, Fly.io, or Hybrid approach
4. Setup: Database + MCP server + Environment variables

---

## 🔧 Reference Tables

### Similarity Score Interpretation

| Score Range | Meaning | Use Case |
|-------------|---------|----------|
| 0.90-1.00 | Near-identical | Exact match or close rephrasing |
| 0.70-0.89 | Highly relevant | What you're looking for |
| 0.50-0.69 | Related | Relevant but less direct |
| 0.30-0.49 | Somewhat related | Might be useful, requires review |
| 0.00-0.29 | Loosely related | Noise, usually ignore |

### Recommended Thresholds

| Threshold | Use Case | Example |
|-----------|----------|---------|
| 0.70 | Strict/Production | Customer support Q&A - only high confidence |
| 0.50 | Balanced/Default | General search - good mix of precision+recall |
| 0.30 | Exploratory/Research | Discovery mode - cast wide net |
| None | Top-N Results | Return top 10 regardless of score |

### What's Included vs Not

**✅ Production Ready:**
- PostgreSQL + pgvector
- Vector normalization
- Document chunking
- Collections
- Web crawling & re-crawl
- 16 MCP tools
- 25+ CLI commands

**⚠️ Experimental (Phase 3 complete, Phase 4 pending):**
- Knowledge graph (entity extraction, relationships, temporal)

**❌ Analyzed but Not Recommended:**
- Hybrid search (vector + keyword)
- Multi-query retrieval
- Re-ranking with cross-encoders

---

## 📊 Feature Status

### By Category

**Vector Search (RAG) - PRODUCTION READY ✅**
- Baseline vector-only: Optimal performance (81% recall@5)
- Chunking: 1000 chars, 200 overlap
- Similarity: 0.7-0.95 for good matches
- Speed: 413ms average latency

**Web Crawling - PRODUCTION READY ✅**
- Single page ingestion
- Multi-page link following (BFS)
- Metadata tracking (crawl_root_url, session_id, depth)
- Re-crawl for updates (safe, targeted)

**Collections - PRODUCTION READY ✅**
- Many-to-many relationships
- Flexible organization
- No duplication needed

**MCP Server - PRODUCTION READY ✅**
- 16 tools available
- Multiple transports (stdio, SSE, HTTP)
- Graceful degradation if graph unavailable

**Knowledge Graph - EXPERIMENTAL ⚠️**
- Phase 3 complete: Ingestion works
- Phase 4 pending: Cleanup not implemented
- Issue: Graph not updated on document edit/delete
- Issue: Graph orphans accumulate on recrawl
- Recommendation: Use for research only, not production

---

## 🎓 Learning Paths

### Path 1: Quick Start (30 minutes)
1. `/getting-started` command
2. Run sample ingestion
3. Try first search
4. Done! Ready to explore

### Path 2: Thorough Understanding (2-3 hours)
1. [OVERVIEW.md](OVERVIEW.md) - Read completely
2. [MCP_QUICK_START.md](MCP_QUICK_START.md) - Read tools section
3. [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - Read baseline section
4. Try: Ingest real documents, tune search
5. Reference: CLAUDE.md for CLI when needed

### Path 3: Complete Deep Dive (Full day)
1. All Path 2 materials
2. [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - Entire doc
3. [PRICING.md](PRICING.md) - Complete cost analysis
4. [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - All optimization details
5. Project files: CLAUDE.md, README.md
6. Try: Setup local instance, experiment with all features

---

## 🐛 Troubleshooting

### I can't find the answer to my question

1. Try searching [OVERVIEW.md](OVERVIEW.md)
2. Check [MCP_QUICK_START.md](MCP_QUICK_START.md) - Troubleshooting section
3. Reference [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - FAQ section
4. Search CLAUDE.md for CLI-specific issues

### My search results aren't good

Read: [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - "Threshold Tuning Guide"

### What's this graph error about?

Read: [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - "Known Issues & Debugging"

### How much will this cost?

Read: [PRICING.md](PRICING.md) then [OVERVIEW.md](OVERVIEW.md) - "Costs & Budgets"

### Is this ready for production?

See [OVERVIEW.md](OVERVIEW.md) - "What's Included & What's Not"
- RAG (vector search): ✅ Yes
- Web crawling: ✅ Yes
- MCP Server: ✅ Yes
- Knowledge graph: ⚠️ No (Phase 4 pending)

---

## 📖 Document Sizes & Read Time

| Document | Size | Read Time |
|----------|------|-----------|
| OVERVIEW.md | 19 KB | 15-20 min |
| MCP_QUICK_START.md | 14 KB | 10-15 min |
| SEARCH_OPTIMIZATION.md | 14 KB | 12-18 min |
| KNOWLEDGE_GRAPH.md | 21 KB | 15-20 min |
| PRICING.md | 6.5 KB | 5-8 min |
| DOCUMENTATION_UPDATE_SUMMARY.md | 17 KB | 10-12 min |
| This README | 4 KB | 5 min |
| **Total** | **~95 KB** | **~90 min** |

**Pro tip:** Start with OVERVIEW.md, then reference specific docs as needed.

---

## 🔗 Important Links

**In This Repository:**
- [CLAUDE.md](../CLAUDE.md) - CLI reference
- [README.md](../README.md) - Project overview
- [scripts/deploy.sh](../scripts/deploy.sh) - Fly.io deployment

**External:**
- PostgreSQL: https://www.postgresql.org/
- pgvector: https://github.com/pgvector/pgvector
- Neo4j: https://neo4j.com/
- Graphiti: https://docs.graphiti.ai/
- OpenAI Pricing: https://openai.com/api/pricing/

---

## 📝 Last Updated

- **Documentation Date:** 2025-10-20
- **RAG Memory Version:** 0.7.0
- **Status:** Production Ready (except graph - Phase 4 pending)
- **Next Review:** When Phase 4 (Graph Cleanup) completes

---

## 💡 Pro Tips

1. **Bookmark this README** - It's your navigation hub
2. **Use Ctrl+F** - Search within each doc for keywords
3. **Start with OVERVIEW** - It's the most comprehensive
4. **Reference specific docs** - Don't read everything sequentially
5. **Check section titles** - Quick way to find what you need
6. **Read warnings (⚠️)** - Important limitations and gotchas
7. **Try examples** - Most docs include runnable code samples

---

**Happy learning! 🚀**

Questions? Check the relevant doc above, or run `/getting-started` for guided setup.
