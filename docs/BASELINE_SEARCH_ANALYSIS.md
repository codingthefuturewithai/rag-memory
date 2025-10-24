# Baseline Search Results - Vanilla Graphiti .search()

**Date:** 2025-10-23
**Strategy:** Basic Graphiti .search() with NO threshold, NO CrossEncoder, NO custom config
**Code Location:** `src/unified/graph_store.py:368` - `await self.graphiti.search(query, num_results=num_results)`

## Neo4j Graph State
- Total nodes: 47 (2 Episodic, 45 Entity)
- Node types: Episodic, Entity
- Relationship types: MENTIONS, RELATES_TO
- Entities in graph: User, AI, machine learning, neural networks, training models, deployment strategies, Speaker, OpenAI, NVIDIA, Microsoft, Google, Amazon, Anthropic, DeepMind, Meta, Hugging Face, Together AI, Sequoia Capital, Andreessen Horowitz, Greylock Partners

## Query Results (8 Test Queries)

| # | Query | Results | Status |
|---|-------|---------|--------|
| 1 | How does quantum computing relate to cryptography? | 4 | FALSE POSITIVE - NVIDIA partnerships returned |
| 2 | What is the history of blockchain and cryptocurrency? | 5 | RELEVANT but mixed |
| 3 | Explain how machine learning relates to artificial intelligence | 5 | RELEVANT |
| 4 | How do neural networks relate to deep learning? | 5 | RELEVANT |
| 5 | What is the connection between cloud computing and data storage? | 5 | RELEVANT |
| 6 | How do APIs relate to web services? | 5 | MIXED RELEVANCE |
| 7 | Explain the relationship between DevOps and continuous integration | 5 | MIXED RELEVANCE |
| 8 | What is the relationship between cybersecurity and encryption? | 5 | MIXED RELEVANCE |

## Key Problem

Query 1 returns 4 results for "quantum computing" and "cryptography" when:
- ZERO nodes about quantum computing in graph
- ZERO nodes about cryptography in graph
- Results are NVIDIA GPU partnerships (false positives)

This indicates Graphiti's default `.search()` is too permissive and returns loosely-related results without proper relevance filtering.

## Current Code Path

```
query_relationships_impl() [tools.py:1074]
  └─> graph_store.search_relationships() [graph_store.py:352]
      └─> self.graphiti.search(query, num_results=num_results) [graph_store.py:368]
```

**No custom configuration, filters, or thresholds applied.**
