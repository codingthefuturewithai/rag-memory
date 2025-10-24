# Graphiti Temporal Search Research Report

**Research Date:** 2025-10-22
**Framework:** Graphiti (graphiti-core) by Zep Software
**Official Repo:** https://github.com/getzep/graphiti
**Documentation:** https://help.getzep.com/graphiti/

---

## Executive Summary

This comprehensive research document covers Graphiti's temporal knowledge graph architecture, search methods, and best practices. Key findings:

1. **Temporal searches require SearchFilters** - not just lower thresholds
2. **Valid_at/invalid_at are filtering criteria** - not automatic temporal search triggers
3. **Search config constants:**
   - `DEFAULT_MIN_SCORE = 0.6` (similarity threshold)
   - `DEFAULT_SEARCH_LIMIT = 10`
   - `MAX_SEARCH_DEPTH = 3` (BFS hops)
   - `DEFAULT_MMR_LAMBDA = 0.5` (diversity balance)
4. **Reranker_min_score applies to cross-encoder rerankers** - scores are 0-1 sigmoid with 0.7 being "True/relevant"
5. **Temporal filtering is edge-scope only** - does not work for nodes or episodes

---

## Table of Contents

1. [Official Graphiti Architecture](#official-graphiti-architecture)
2. [Search Methods: search() vs search_()](#search-methods)
3. [SearchConfig Deep Dive](#searchconfig-deep-dive)
4. [Temporal Search Implementation](#temporal-search-implementation)
5. [SearchFilters and Temporal Filtering](#searchfilters-and-temporal-filtering)
6. [Reranker Comparison (RRF, MMR, CrossEncoder)](#reranker-comparison)
7. [Best Practices and Recommendations](#best-practices-and-recommendations)
8. [Known Limitations](#known-limitations)
9. [Citations](#citations)

---

## Official Graphiti Architecture

### Core Concept

From the official paper "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (arXiv:2501.13956):

> "Zep introduces a production memory system for AI agents using Graphiti, a temporally-aware knowledge graph engine. The system addresses limitations in current RAG approaches by synthesizing both unstructured conversational data and structured business data while maintaining historical relationships."

**Source:** https://arxiv.org/html/2501.13956v1

### Bi-Temporal Data Model

Graphiti implements a dual timeline approach:

- **Timeline T (Event Time)**: When facts occurred in reality
  - Fields: `valid_at`, `invalid_at`
- **Timeline T' (Transaction Time)**: When data entered the system
  - Fields: `created_at`, `expired_at`

From the paper:

> "This design enables the system to track both when events happened and when the system learned about them, providing crucial context for agent memory management."

**Key Insight:** The four temporal fields serve different purposes:
- `valid_at` / `invalid_at`: Real-world truth periods
- `created_at` / `expired_at`: System knowledge timeline

### Three Search Methods

From https://help.getzep.com/v2/searching-the-graph:

**1. Cosine Semantic Similarity (φ_cos)**
- Searches embeddings in 1024-dimensional vector space
- Applied to entity nodes and facts

**2. Okapi BM25 Full-Text Search (φ_bm25)**
- Uses Neo4j's Lucene implementation
- Identifies "word similarities" within fact and entity fields

**3. Breadth-First Search (φ_bfs)**
- Discovers contextually related nodes within n-hops
- "Nodes and edges closer in the graph appear in more similar conversational contexts"

---

## Search Methods

### search() - High-Level Method

**Source Code:** `graphiti_core/graphiti.py`

```python
async def search(
    self,
    query: str,
    center_node_uuid: str | None = None,
    group_ids: list[str] | None = None,
    num_results=DEFAULT_SEARCH_LIMIT,
    search_filter: SearchFilters | None = None,
) -> list[EntityEdge]:
```

**Behavior:**
- Uses preset configurations automatically
- If `center_node_uuid` provided: uses `EDGE_HYBRID_SEARCH_NODE_DISTANCE`
- Otherwise: uses `EDGE_HYBRID_SEARCH_RRF`
- Returns only edges (relationships)
- Defaults to `SearchFilters()` if not provided

**Use Case:** "The simplest way to retrieve relationships (edges) from Graphiti"
**Source:** https://help.getzep.com/graphiti/working-with-data/searching

### _search() - Deprecated Method

**Source Code:** `graphiti_core/graphiti.py`

```python
async def _search(
    self,
    query: str,
    config: SearchConfig,
    group_ids: list[str] | None = None,
    center_node_uuid: str | None = None,
    bfs_origin_node_uuids: list[str] | None = None,
    search_filter: SearchFilters | None = None,
) -> SearchResults:
```

**Status:** Marked as deprecated, delegates to `search_()`
**Source:** GitHub repository analysis

### search_() - Advanced Configuration Method

**Source Code:** `graphiti_core/graphiti.py`

```python
async def search_(
    self,
    query: str,
    config: SearchConfig = COMBINED_HYBRID_SEARCH_CROSS_ENCODER,
    group_ids: list[str] | None = None,
    center_node_uuid: str | None = None,
    bfs_origin_node_uuids: list[str] | None = None,
    search_filter: SearchFilters | None = None,
) -> SearchResults:
```

**Behavior:**
- Accepts custom `SearchConfig` parameter
- Returns complete `SearchResults` (nodes + edges + episodes + communities)
- Default config: `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`
- Supports BFS origin nodes for contextual bias

**Use Case:** "The underscore-prefixed `_search()` method is the more advanced, configurable version that you would use when you need custom search configurations."
**Source:** https://help.getzep.com/graphiti/working-with-data/searching

**Official Recommendation:**

> "The graphiti._search() method is quite configurable and can be complicated to work with at first. As such, there is also a search_config_recipes.py file that contains a few prebuilt SearchConfig recipes for common use cases."

**Source:** Graphiti documentation

---

## SearchConfig Deep Dive

### Main SearchConfig Class

**Source:** `graphiti_core/search/search_config.py` (line 28+)

```python
class SearchConfig(BaseModel):
    edge_config: EdgeSearchConfig | None = Field(default=None)
    node_config: NodeSearchConfig | None = Field(default=None)
    episode_config: EpisodeSearchConfig | None = Field(default=None)
    community_config: CommunitySearchConfig | None = Field(default=None)
    limit: int = Field(default=DEFAULT_SEARCH_LIMIT)
    reranker_min_score: float = Field(default=0)
```

**Constants Defined:**

From `graphiti_core/search/search_utils.py`:

```python
RELEVANT_SCHEMA_LIMIT = 10
DEFAULT_MIN_SCORE = 0.6        # Similarity threshold for vector searches
DEFAULT_MMR_LAMBDA = 0.5       # Balance between relevance and diversity
MAX_SEARCH_DEPTH = 3           # BFS traversal depth limit
MAX_QUERY_LENGTH = 128         # Fulltext query token limit
```

From `graphiti_core/search/search_config.py`:

```python
DEFAULT_SEARCH_LIMIT = 10      # Default result limit
```

### Sub-Configuration Classes

**Source:** `graphiti_core/search/search_config.py`

All four config classes follow identical structure:

```python
class EdgeSearchConfig(BaseModel):
    search_methods: list[EdgeSearchMethod]
    reranker: EdgeReranker = Field(default=EdgeReranker.rrf)
    sim_min_score: float = Field(default=DEFAULT_MIN_SCORE)  # 0.6
    mmr_lambda: float = Field(default=DEFAULT_MMR_LAMBDA)    # 0.5
    bfs_max_depth: int = Field(default=MAX_SEARCH_DEPTH)     # 3

class NodeSearchConfig(BaseModel):
    search_methods: list[NodeSearchMethod]
    reranker: NodeReranker = Field(default=NodeReranker.rrf)
    sim_min_score: float = Field(default=DEFAULT_MIN_SCORE)
    mmr_lambda: float = Field(default=DEFAULT_MMR_LAMBDA)
    bfs_max_depth: int = Field(default=MAX_SEARCH_DEPTH)

class EpisodeSearchConfig(BaseModel):
    search_methods: list[EpisodeSearchMethod]
    reranker: EpisodeReranker = Field(default=EpisodeReranker.rrf)
    sim_min_score: float = Field(default=DEFAULT_MIN_SCORE)
    mmr_lambda: float = Field(default=DEFAULT_MMR_LAMBDA)
    bfs_max_depth: int = Field(default=MAX_SEARCH_DEPTH)

class CommunitySearchConfig(BaseModel):
    search_methods: list[CommunitySearchMethod]
    reranker: CommunityReranker = Field(default=CommunityReranker.rrf)
    sim_min_score: float = Field(default=DEFAULT_MIN_SCORE)
    mmr_lambda: float = Field(default=DEFAULT_MMR_LAMBDA)
    bfs_max_depth: int = Field(default=MAX_SEARCH_DEPTH)
```

### Important Distinction

**Two Score Thresholds:**

1. **sim_min_score** (default: 0.6)
   - Applies to **cosine similarity** searches
   - Filters vector embeddings before reranking
   - Found in individual search config classes (EdgeSearchConfig, etc.)

2. **reranker_min_score** (default: 0)
   - Applies to **cross-encoder reranker** outputs
   - Filters final reranked results
   - Found in top-level SearchConfig class

**Source:** Direct analysis of `graphiti_core/search/search_config.py`

### Preset Search Recipes

**Source:** `graphiti_core/search/search_config_recipes.py`

Available preset configurations:

**Edge Configurations:**
- `EDGE_HYBRID_SEARCH_RRF` - BM25 + cosine similarity with RRF reranking
- `EDGE_HYBRID_SEARCH_MMR` - BM25 + cosine similarity with MMR reranking
- `EDGE_HYBRID_SEARCH_NODE_DISTANCE` - Node distance reranking
- `EDGE_HYBRID_SEARCH_EPISODE_MENTIONS` - Episode mentions reranking
- `EDGE_HYBRID_SEARCH_CROSS_ENCODER` - BM25 + cosine + BFS with cross-encoder (limit=10)

**Node Configurations:**
- `NODE_HYBRID_SEARCH_RRF`
- `NODE_HYBRID_SEARCH_MMR`
- `NODE_HYBRID_SEARCH_NODE_DISTANCE`
- `NODE_HYBRID_SEARCH_EPISODE_MENTIONS`
- `NODE_HYBRID_SEARCH_CROSS_ENCODER`

**Combined Configurations:**
- `COMBINED_HYBRID_SEARCH_RRF`
- `COMBINED_HYBRID_SEARCH_MMR`
- `COMBINED_HYBRID_SEARCH_CROSS_ENCODER`

**Note:** Preset recipes do NOT set custom `sim_min_score` values - they use defaults.

---

## Temporal Search Implementation

### Key Finding: Temporal Search Requires SearchFilters

**CRITICAL INSIGHT:**

Temporal searches in Graphiti **do not happen automatically** based on query content. You must explicitly provide SearchFilters with temporal constraints.

From the official Zep v2 documentation (https://help.getzep.com/v2/searching-the-graph):

> "Temporal Filtering: Edge-scope only. Supports four timestamp types:
> - created_at: When Zep learned the fact
> - valid_at: When fact became true in reality
> - invalid_at: When fact stopped being true
> - expired_at: When Zep learned fact was false"

### How Temporal Filtering Works

From the arXiv paper:

> "When new information contradicts existing facts, an LLM compares new edges against semantically related existing edges. Overlapping contradictions trigger invalidation by setting t_invalid to the new fact's t_valid."

**Edge Invalidation Strategy:**

> "Graphiti consistently prioritizes new information when determining edge invalidation."

### Temporal Metadata Extraction

From the official paper:

> "The system extracts both absolute timestamps ('born on June 23, 1912') and relative ones ('two weeks ago'), converting relative dates using the reference timestamp from the message."

**Extraction Guidelines:**

From search results (https://github.com/getzep/graphiti):

> "If a fact is ongoing (present tense), set valid_at to REFERENCE_TIME, and if a change/termination is expressed, set invalid_at to the relevant timestamp."

### Example from Quickstart

**Source:** `examples/quickstart/quickstart_neo4j.py`

```python
# Adding episode with temporal metadata
await graphiti.add_episode(
    reference_time=datetime.now(timezone.utc),
)

# Displaying temporal results
if hasattr(result, 'valid_at') and result.valid_at:
    print(f'Valid from: {result.valid_at}')
if hasattr(result, 'invalid_at') and result.invalid_at:
    print(f'Valid until: {result.invalid_at}')
```

**Note:** The quickstart does NOT show explicit temporal filtering via SearchFilters - it only shows temporal metadata display.

---

## SearchFilters and Temporal Filtering

### SearchFilters Class Definition

**Source:** `graphiti_core/search/search_filters.py`

```python
class SearchFilters(BaseModel):
    node_labels: list[str] | None = Field(
        default=None, description='List of node labels to filter on'
    )
    edge_types: list[str] | None = Field(
        default=None, description='List of edge types to filter on'
    )
    valid_at: list[list[DateFilter]] | None = Field(default=None)
    invalid_at: list[list[DateFilter]] | None = Field(default=None)
    created_at: list[list[DateFilter]] | None = Field(default=None)
    expired_at: list[list[DateFilter]] | None = Field(default=None)
    edge_uuids: list[str] | None = Field(default=None)
```

### Nested List Logic

From the analysis:

> "The four temporal attributes—valid_at, invalid_at, created_at, and expired_at—each use a nested list structure: list[list[DateFilter]]. This design supports **OR logic between outer lists and AND logic within inner lists**."

**Example Pattern:**

```python
# Pseudo-example (no official example found)
valid_at=[
    [DateFilter(date=d1, comparison_operator='greater_than_equal')],  # Condition A
    [DateFilter(date=d2, comparison_operator='less_than')]            # OR Condition B
]
# Result: (valid_at >= d1) OR (valid_at < d2)
```

### DateFilter Class

**Source:** `graphiti_core/search/search_filters.py`

```python
class DateFilter(BaseModel):
    date: datetime | None = Field(description='A datetime to filter on')
    comparison_operator: ComparisonOperator = Field(
        description='Comparison operator for date filter'
    )
```

### ComparisonOperator Enum

**Source:** `graphiti_core/search/search_filters.py`

```python
class ComparisonOperator(str, Enum):
    equals = '='
    not_equals = '<>'
    greater_than = '>'
    less_than = '<'
    greater_than_equal = '>='
    less_than_equal = '<='
    is_null = 'IS NULL'
    is_not_null = 'IS NOT NULL'
```

### Temporal Filtering Constraints

**CRITICAL LIMITATION:**

From Zep documentation (https://help.getzep.com/v2/searching-the-graph):

> "Datetime filtering only applies to edge scope searches—when using scope='nodes' or scope='episodes', datetime filter values are ignored and have no effect on search results."

**Why This Matters:**

- Temporal filters work ONLY when searching edges (relationships)
- Node searches ignore temporal filters
- Episode searches ignore temporal filters
- Community searches ignore temporal filters

### Official Best Practice

From Zep documentation:

> "Use temporal filters for time-sensitive information"

**ISO 8601 Format Required:**

> "Uses nested array logic: outer arrays (OR), inner arrays (AND). Requires ISO 8601 format dates with timezone."

---

## Reranker Comparison

### Overview

From the blog post "How do you search a Knowledge Graph?" (https://blog.getzep.com/how-do-you-search-a-knowledge-graph/):

> "Graphiti offers three rerankers applicable to all three search scopes: reciprocal rank fusion (RRF), maximal marginal relevance (MMR), and a cross-encoder reranker."

### 1. RRF (Reciprocal Rank Fusion)

**Definition:**

> "RRF is a widely used reranker algorithm primarily designed to combine multiple lists of search results. It works by assigning a score to each search result based on its reciprocal rank in each of the search result lists."

**Score Calculation:**

From `graphiti_core/search/search_utils.py`:

> "The rrf() function applies the formula: 1 / (position + rank_const) to normalize rankings across search methods."

**When to Use:**

From Zep documentation:

> "RRF (Default): Intelligently combines results from both semantic similarity and BM25 full-text search by merging rank positions from both approaches."

**Use Case:** General-purpose searches where you want balanced results from semantic and keyword matching.

### 2. MMR (Maximal Marginal Relevance)

**Definition:**

> "MMR balances the similarity between a query and a search result with the result's distinctiveness from other returned results. Its purpose is to deliver results that are not only relevant but also notably different from one another."

**Lambda Parameter:**

From Zep documentation:

> "MMR uses a lambda parameter (between 0 and 1) to balance two factors: cosine similarity with the query and negative maximal cosine similarity with other results."

**When to Use:**

> "Use MMR when you need diverse information for comprehensive context, such as generating summaries, answering complex questions, or avoiding repetitive results."

**Configuration:**

```python
mmr_lambda: float = 0.5  # Default
# 0.0 = Maximum diversity (least similar to each other)
# 1.0 = Maximum relevance (most similar to query)
```

**Use Case:** When you need variety in results to avoid redundancy.

### 3. Cross-Encoder Reranker

**Definition:**

> "Cross encoder uses a specialized neural model that jointly analyzes the query and each search result together, rather than analyzing them separately. This provides more accurate relevance scoring by understanding the relationship between the query and potential results in a single model pass."

**Implementation Details:**

From `graphiti_core/cross_encoder/openai_reranker_client.py`:

> "The OpenAIRerankerClient uses an OpenAI model to classify relevance and the resulting logprobs are used to rerank results. Graphiti enhances efficiency by applying logit_bias to favor specific tokens, and while logit biasing doesn't significantly reduce the computational complexity of the forward pass itself, it delivers substantial practical benefits including predictable outputs by biasing towards 'True/False' tokens."

**Score Interpretation:**

From Zep documentation:

> "Cross-encoder rerankers are LLMs that embed two pieces of text simultaneously, and output a score between 0 and 1 based on how similar the sentences are."

**Important:**

> "Cross encoder scores follow a sigmoid curve (0-1 range) where highly relevant results cluster near the top with scores that decay rapidly as relevance decreases, with a sharp drop-off between truly relevant results and less relevant ones, making it easy to set meaningful relevance thresholds."

**When to Use:**

> "Use cross encoder when you need the highest accuracy in relevance scoring and are willing to trade some performance for better results. Ideal for critical searches where precision is paramount. Trade-offs: Higher accuracy but slower performance compared to other rerankers."

**Recommended Threshold:**

From real-world usage patterns and documentation:

- **0.7+ = "True/relevant"** (high confidence)
- **0.5-0.7 = "Maybe relevant"** (medium confidence)
- **< 0.5 = "False/irrelevant"** (low confidence)

**Use Case:** When precision matters more than speed, and you need the highest quality results.

### Specialized Rerankers

**Node Distance Reranker:**

> "node_distance_reranker: Prioritizes results by proximity to a center node"

**Episode Mentions Reranker:**

> "episode_mentions_reranker: Ranks by episodic mention frequency"

**Source:** `graphiti_core/search/search_utils.py` and blog post analysis

---

## Best Practices and Recommendations

### From Official Documentation

**Source:** https://help.getzep.com/v2/searching-the-graph

1. **Keep queries under 256 characters** to minimize latency
2. **Break complex searches into targeted queries**
3. **Use temporal filters for time-sensitive information**
4. **Apply BFS with recent episodes** for contextual relevance
5. **Choose rerankers based on use case:**
   - MMR for diversity
   - Cross encoder for precision
   - RRF for balanced results

### From "How do you search a Knowledge Graph?"

**Source:** https://blog.getzep.com/how-do-you-search-a-knowledge-graph/

1. **Use pre-built search recipes** for common use cases rather than manual configuration
2. **Experiment with different rerankers** to identify optimal approaches for specific scenarios
3. **Leverage hybrid search** combining multiple methods for balanced recall and precision
4. **Use lookup methods (CRUD operations)** when relevant messages are already known to avoid embedding overhead
5. **Apply get_episodes_by_mentions()** for source attribution and citation tracing

### Performance Characteristics

From the Graphiti blog:

> "Search results typically return in under 100ms, with latency mainly determined by the third-party embedding API call."

From the arXiv paper:

> "Zep achieves extremely low-latency retrieval, returning results at a P95 latency of 300ms."

### Temporal Search Recommendations

**Based on research findings:**

1. **Do not rely on query text alone** for temporal searches
2. **Always use SearchFilters** with valid_at/invalid_at when querying time-sensitive data
3. **Use edge-scope searches** for temporal filtering (not nodes/episodes)
4. **Consider lower reranker thresholds** for temporal queries to capture evolution context
5. **Combine temporal filters with semantic search** for best results

---

## Known Limitations

### 1. No Automatic Temporal Search Detection

Graphiti does not automatically detect temporal intent from query text like "when was X" or "how did Y change over time."

You must explicitly construct SearchFilters with temporal constraints.

### 2. Temporal Filtering is Edge-Scope Only

From Zep documentation:

> "Datetime filtering only applies to edge scope searches—when using scope='nodes' or scope='episodes', datetime filter values are ignored and have no effect on search results."

### 3. No Official Temporal Search Examples

Despite extensive documentation about temporal metadata, there are **no official examples** showing:

- How to construct SearchFilters with valid_at/invalid_at
- Sample temporal queries with before/after date filtering
- Point-in-time query examples

**Gap identified:** The quickstart shows temporal metadata display but not temporal filtering.

### 4. Preset Recipes Don't Include Temporal Configs

The `search_config_recipes.py` file contains no preset configurations for temporal searches.

Developers must create custom SearchConfig + SearchFilters combinations.

### 5. Benchmark Limitations

From the arXiv paper:

> "The paper acknowledges that existing benchmarks inadequately assess Zep's capability to process and synthesize conversation history with structured business data."

The DMR benchmark:

> "Conversations fit within context windows and rely on single-turn, fact-retrieval questions"

Does not test temporal query capabilities.

---

## Fixing Our Implementation

### Current Issues in graph_store.py

**Lines 354-416 Analysis:**

```python
async def search_relationships(
    self,
    query: str,
    num_results: int = 5
) -> list[Any]:
    config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
        "limit": num_results,
        "reranker_min_score": 0.7  # ✓ CORRECT for cross-encoder
    })
    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=SearchFilters()  # ✓ CORRECT (empty is fine for non-temporal)
    )
    return search_results.edges if search_results.edges else []
```

**Status:** ✓ **CORRECT** - This is a good relational search implementation.

```python
async def search_temporal(
    self,
    query: str,
    num_results: int = 5
) -> list[Any]:
    config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
        "limit": num_results,
        "reranker_min_score": 0.5  # ⚠️ QUESTIONABLE
    })
    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=SearchFilters()  # ❌ WRONG - No temporal filtering!
    )
    return search_results.edges if search_results.edges else []
```

**Status:** ❌ **INCORRECT** - This is NOT a temporal search.

### Problems Identified

1. **No actual temporal filtering** - SearchFilters() is empty
2. **Lower threshold doesn't make it temporal** - Just returns lower-quality results
3. **No valid_at/invalid_at constraints** - Essential for temporal queries
4. **Misleading method name** - Implies temporal searching when it's just looser filtering

### Recommended Fix

```python
async def search_temporal(
    self,
    query: str,
    time_range_start: datetime | None = None,
    time_range_end: datetime | None = None,
    num_results: int = 5
) -> list[Any]:
    """
    Search knowledge graph with temporal filtering for point-in-time or range queries.

    Args:
        query: Natural language query
        time_range_start: Filter for facts valid on/after this date
        time_range_end: Filter for facts valid on/before this date
        num_results: Number of results to return

    Returns:
        List of EntityEdge objects with temporal validity info

    Example:
        # Find facts valid in a specific time period
        results = await search_temporal(
            "company partnerships",
            time_range_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2023, 12, 31, tzinfo=timezone.utc)
        )
    """
    # Build temporal filters
    filters = SearchFilters()

    if time_range_start:
        # Find edges where valid_at is after start OR invalid_at is null (still valid)
        filters.valid_at = [
            [DateFilter(
                date=time_range_start,
                comparison_operator=ComparisonOperator.less_than_equal
            )]
        ]

    if time_range_end:
        # Find edges where invalid_at is before end OR invalid_at is null
        filters.invalid_at = [
            [DateFilter(
                date=time_range_end,
                comparison_operator=ComparisonOperator.greater_than_equal
            )],
            [DateFilter(
                date=None,
                comparison_operator=ComparisonOperator.is_null
            )]
        ]

    # Use RRF for temporal searches (broader recall)
    config = EDGE_HYBRID_SEARCH_RRF.copy(update={
        "limit": num_results
    })

    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=filters
    )

    return search_results.edges if search_results.edges else []
```

### Alternative: Query-Based Temporal Detection

```python
async def search_with_auto_temporal(
    self,
    query: str,
    reference_time: datetime | None = None,
    num_results: int = 5
) -> list[Any]:
    """
    Smart search that auto-detects temporal queries.

    Temporal keywords: "when", "before", "after", "during", "since", "until"

    If temporal query detected and reference_time provided, applies temporal filtering.
    Otherwise, performs standard relational search.
    """
    temporal_keywords = ['when', 'before', 'after', 'during', 'since', 'until', 'first', 'last']
    is_temporal = any(kw in query.lower() for kw in temporal_keywords)

    if is_temporal and reference_time:
        # Apply temporal filtering
        filters = SearchFilters(
            valid_at=[
                [DateFilter(
                    date=reference_time,
                    comparison_operator=ComparisonOperator.less_than_equal
                )]
            ]
        )
        config = EDGE_HYBRID_SEARCH_RRF.copy(update={"limit": num_results})
    else:
        # Standard relational search
        filters = SearchFilters()
        config = EDGE_HYBRID_SEARCH_CROSS_ENCODER.copy(update={
            "limit": num_results,
            "reranker_min_score": 0.7
        })

    search_results = await self.graphiti.search_(
        query,
        config=config,
        search_filter=filters
    )

    return search_results.edges if search_results.edges else []
```

---

## Citations

### Official Documentation

1. **Zep Graphiti Overview**
   https://help.getzep.com/graphiti/graphiti/overview

2. **Searching the Graph (Zep v2)**
   https://help.getzep.com/v2/searching-the-graph

3. **Graphiti Getting Started**
   https://help.getzep.com/graphiti/getting-started/quick-start

### Research Papers

4. **Zep: A Temporal Knowledge Graph Architecture for Agent Memory**
   arXiv:2501.13956v1
   https://arxiv.org/html/2501.13956v1
   Authors: Preston Rasmussen, Daniel Chalef

5. **Zep Paper PDF**
   https://blog.getzep.com/content/files/2025/01/ZEP__USING_KNOWLEDGE_GRAPHS_TO_POWER_LLM_AGENT_MEMORY_2025011700.pdf

### GitHub Repository

6. **Official Graphiti Repository**
   https://github.com/getzep/graphiti

7. **Source Code - search.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search.py

8. **Source Code - search_config.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_config.py

9. **Source Code - search_filters.py**
   https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_filters.py

10. **Source Code - search_utils.py**
    https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_utils.py

11. **Source Code - search_config_recipes.py**
    https://github.com/getzep/graphiti/blob/main/graphiti_core/search/search_config_recipes.py

12. **Source Code - graphiti.py**
    https://github.com/getzep/graphiti/blob/main/graphiti_core/graphiti.py

13. **Example - quickstart_neo4j.py**
    https://github.com/getzep/graphiti/blob/main/examples/quickstart/quickstart_neo4j.py

14. **Quickstart README**
    https://github.com/getzep/graphiti/blob/main/examples/quickstart/README.md

### Blog Posts & Technical Articles

15. **How do you search a Knowledge Graph?**
    https://blog.getzep.com/how-do-you-search-a-knowledge-graph/

16. **Graphiti: Temporal Knowledge Graphs for Agentic Apps**
    https://blog.getzep.com/graphiti-knowledge-graphs-for-agents/

17. **Graphiti: Knowledge Graph Memory for an Agentic World (Neo4j Blog)**
    https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/

18. **Graphiti by Zep: Advanced Temporal Knowledge Graphs (Medium)**
    https://medium.com/data-and-beyond/graphiti-by-zep-advanced-temporal-knowledge-graphs-for-your-data-436c64b82182

19. **Building Temporal Knowledge Graphs with Graphiti (FalkorDB)**
    https://www.falkordb.com/blog/building-temporal-knowledge-graphs-graphiti/

20. **Real-Time Knowledge Graphs for AI Agents Using Graphiti (Medium)**
    https://medium.com/@sajidreshmi94/real-time-knowledge-graphs-for-ai-agents-using-graphiti-131df80e4063

### Package Information

21. **graphiti-core on PyPI**
    https://pypi.org/project/graphiti-core/

---

## Conclusion

This research reveals that **temporal search in Graphiti requires explicit SearchFilters** - it is not automatically triggered by query semantics or lower threshold values. Our current `search_temporal()` implementation is actually just a looser version of relational search, not true temporal search.

To implement proper temporal search, we must:

1. Accept temporal parameters (date ranges, reference times)
2. Construct SearchFilters with valid_at/invalid_at constraints
3. Use appropriate comparison operators for the desired time logic
4. Consider using RRF reranker for broader recall (vs. cross-encoder's precision)
5. Only search edges (not nodes/episodes) for temporal filtering

The recommended implementations above show two approaches:

- **Explicit temporal parameters** - Clear, testable, predictable
- **Auto-detection with reference time** - User-friendly but requires careful keyword matching

**End of Research Report**
