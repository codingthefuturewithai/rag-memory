# RAG Memory + Knowledge Graph Demo

## 1. The Problem
- AI agents need long-term memory across sessions
- Multiple agents (ChatGPT, Claude Desktop, Claude Code) in different environments
- Current approaches don't scale: file-based memory, session-only context, siloed per-agent
- Need: Shared, performant, semantic knowledge retrieval

## 2. Solution: RAG Memory MCP Server
**Demo: Same knowledge, three different AI agents**
- ChatGPT (cloud)
- Claude Desktop (cloud)
- Claude Code (local IDE)

TIP: If you're a long-time ChatGPT user, it has a lot of historical knowledge about you. That makes ChatGPT a great source to populate your knowledge base.

**Key Point:** Standardized MCP interface enables any AI agent to access shared knowledge

## 3. Why Add Knowledge Graphs?
**RAG:** "What does the documentation say?" (content retrieval)
**Graph:** "How do these concepts relate?" (relationship discovery)

**Two Critical Capabilities:**
- **Entity Relationships** - Understanding how concepts connect
- **Temporal Knowledge** - Tracking how knowledge evolves over time

## 4. Side-by-Side Comparison
**RAG Query:** Definition lookup, examples, "what" questions
**Graph Query:** Entity connections, "how" questions
**Neo4j Visualization:** Visual entity-relationship graph

## 5. Tech Stack
PostgreSQL + pgvector | Neo4j + Graphiti | OpenAI Embeddings | MCP Protocol

## 6. Open Discussion
- What AI memory challenges are you facing?
- What tools/approaches are you using?
- Questions about implementation?
