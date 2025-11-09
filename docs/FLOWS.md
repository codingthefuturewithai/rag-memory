# RAG Memory Operational Flows

**Last Updated:** November 9, 2025
**Status:** Current and accurate

---

## Table of Contents

- [Ingest URL Flow](#ingest-url-flow)
- [Ingest Text Flow](#ingest-text-flow)
- [Search Documents Flow](#search-documents-flow)
- [Query Relationships Flow](#query-relationships-flow)
- [Query Temporal Flow](#query-temporal-flow)
- [Startup Validation Flow](#startup-validation-flow)
- [Collection Creation Flow](#collection-creation-flow)

---

## Ingest URL Flow

Complete flow for ingesting web pages with link following, content filtering, and dual-store ingestion.

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant Dedup as Deduplication
    participant Analyzer as Website Analyzer
    participant Crawler as Web Crawler
    participant Mediator as Unified Mediator
    participant Chunker as Chunking Engine
    participant Embedder as Embedding Generator
    participant RAG as RAG Store<br/>(PostgreSQL)
    participant Graph as Graph Store<br/>(Neo4j)

    User->>MCP: ingest_url(url, collection, follow_links=True, max_pages=20)

    Note over MCP: Validate inputs
    MCP->>Dedup: check_duplicate_request()
    alt Request already processing
        Dedup-->>MCP: Error: duplicate request
        MCP-->>User: Error: Please wait for current operation
    else New request
        Dedup-->>MCP: OK, proceed
    end

    Note over MCP: Optional: Analyze website first
    alt User wants analysis
        MCP->>Analyzer: analyze_website(url)
        Analyzer->>Analyzer: Check sitemap.xml
        alt Sitemap found
            Analyzer->>Analyzer: Parse sitemap
        else No sitemap
            Analyzer->>Analyzer: Query Common Crawl
        end
        Analyzer-->>MCP: {total_urls, pattern_stats}
        MCP-->>User: Analysis results (for planning)
    end

    Note over MCP: Start crawl
    MCP->>Crawler: crawl(url, follow_links=True, max_pages=20)

    loop For each page (up to max_pages)
        Crawler->>Crawler: Fetch HTML (Playwright)
        Crawler->>Crawler: Filter content (remove nav/footer/etc)
        Crawler->>Crawler: Extract links
        Crawler->>Crawler: Add to queue if within domain
    end

    Crawler-->>MCP: pages[]<br/>(content + metadata)

    Note over MCP: Ingest each page
    loop For each crawled page
        MCP->>Mediator: ingest_text(page.content, collection, metadata)

        Note over Mediator: Phase 1 - RAG Store
        Mediator->>Chunker: chunk_document(content)
        Chunker->>Chunker: Hierarchical split<br/>(headers → paragraphs → sentences)
        Chunker-->>Mediator: chunks[] (~1000 chars each)

        loop For each chunk
            Mediator->>Embedder: generate_embedding(chunk.content)
            Embedder->>Embedder: OpenAI API call<br/>(text-embedding-3-small)
            Embedder-->>Mediator: embedding[1536]
        end

        Mediator->>RAG: INSERT source_document
        RAG-->>Mediator: document_id

        Mediator->>RAG: INSERT document_chunks + embeddings
        RAG-->>Mediator: chunk_ids[]

        Mediator->>RAG: INSERT chunk_collections (junction)
        RAG-->>Mediator: OK

        Note over Mediator: Phase 2 - Graph Store
        Mediator->>Graph: add_episode(content, metadata)
        Graph->>Graph: Graphiti extracts entities<br/>(LLM-powered)
        Graph->>Graph: Store Entity nodes
        Graph->>Graph: Store Relationship edges
        Graph->>Graph: Set temporal validity
        Graph-->>Mediator: {entities_count, relationships_count}

        Mediator-->>MCP: {document_id, num_chunks, entities_extracted}
    end

    MCP->>Dedup: mark_request_complete()
    MCP-->>User: {pages_crawled, pages_ingested, total_chunks}
```

**Key Points:**

1. **Deduplication:** Prevents concurrent identical requests
2. **Web Crawling:** Playwright-based, respects max_pages limit
3. **Content Filtering:** Removes navigation noise before ingestion
4. **Sequential Dual Storage:** RAG first, then Graph (not atomic yet)
5. **Progress Tracking:** MCP can send progress notifications during long crawls

**Note:**
- Processing time varies by content size and complexity
- Multi-page ingests can take extended time depending on page count and content

---

## Ingest Text Flow

Simplified flow for ingesting text content directly (no web crawling).

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant Mediator as Unified Mediator
    participant Chunker as Chunking Engine
    participant Embedder as Embedding Generator
    participant RAG as RAG Store
    participant Graph as Graph Store

    User->>MCP: ingest_text(content, collection, title, metadata)

    Note over MCP: Validate collection exists
    MCP->>MCP: validate_collection_exists(collection)

    Note over MCP: Check for duplicates (mode="ingest")
    alt Document with same title exists
        MCP-->>User: Error: Duplicate<br/>Suggest mode="reingest"
    else No duplicate
        MCP->>Mediator: ingest_text(content, collection, title, metadata)
    end

    Note over Mediator: Phase 1 - RAG Store
    Mediator->>Chunker: chunk_document(content)
    Chunker->>Chunker: Hierarchical split<br/>~1000 chars/chunk, 200 char overlap
    Chunker-->>Mediator: chunks[]

    loop For each chunk
        Mediator->>Embedder: generate_embedding(chunk.content)
        Embedder->>Embedder: OpenAI API call
        Embedder-->>Mediator: embedding[1536]
    end

    Mediator->>RAG: BEGIN TRANSACTION
    Mediator->>RAG: INSERT source_document
    RAG-->>Mediator: document_id
    Mediator->>RAG: INSERT document_chunks (batch)
    RAG-->>Mediator: chunk_ids[]
    Mediator->>RAG: INSERT chunk_collections (batch)
    Mediator->>RAG: COMMIT
    RAG-->>Mediator: OK

    Note over Mediator: Phase 2 - Graph Store
    Mediator->>Graph: add_episode(content, metadata)
    Graph->>Graph: Graphiti entity extraction<br/>(LLM call)
    Graph->>Graph: MERGE Entity nodes
    Graph->>Graph: CREATE Relationship edges
    Graph->>Graph: SET temporal properties
    Graph-->>Mediator: {entities_extracted, relationships_created}

    Mediator-->>MCP: {document_id, num_chunks, entities_extracted}
    MCP-->>User: Success response
```

**Important Notes:**

- **Not Atomic:** RAG and Graph writes are sequential, not in a distributed transaction
- **Failure Scenario:** If Graph extraction fails, RAG data persists (potential inconsistency)
- **Future Enhancement:** Two-phase commit for true atomicity

---

## Search Documents Flow

Vector similarity search over document chunks.

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant Search as Similarity Search
    participant Embedder as Embedding Generator
    participant RAG as RAG Store<br/>(pgvector)

    User->>MCP: search_documents(query, collection, limit=5, threshold=0.35)

    MCP->>Search: search(query, collection, limit, threshold)

    Note over Search: Embed query
    Search->>Embedder: generate_embedding(query)
    Embedder->>Embedder: OpenAI API call<br/>(text-embedding-3-small)
    Embedder-->>Search: query_embedding[1536]

    Note over Search: Vector similarity search
    Search->>RAG: SQL Query with cosine similarity
    Note over RAG: SELECT content, metadata,<br/>embedding <=> query_embedding AS similarity<br/>FROM document_chunks<br/>JOIN chunk_collections<br/>WHERE collection_id = ?<br/>AND similarity > threshold<br/>ORDER BY similarity ASC<br/>LIMIT ?
    Note over RAG: HNSW index used for fast ANN
    RAG-->>Search: chunks[] with similarity scores

    Note over Search: Post-processing
    Search->>Search: Filter by threshold (>= 0.35)
    Search->>Search: Sort by similarity DESC (closest first)
    Search->>Search: Enrich with source document metadata

    Search-->>MCP: results[]<br/>(content, similarity, source_filename, metadata)
    MCP-->>User: Ranked results
```

**Note:**
- HNSW index provides fast approximate nearest neighbor search
- Results ranked by cosine similarity (higher scores indicate better matches)
- Default threshold: 0.35 (configurable by user)

---

## Query Relationships Flow

Knowledge graph query with LLM-powered entity matching.

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant Graph as Graph Store
    participant Graphiti as Graphiti Library
    participant LLM as OpenAI API
    participant Neo4j as Neo4j Database

    User->>MCP: query_relationships(query, collection, num_results=5, threshold=0.35)

    MCP->>Graph: search_edges(query, collection, num_results, threshold)

    Note over Graph,Graphiti: Step 1: Extract entities from query
    Graph->>Graphiti: search(query)
    Graphiti->>LLM: Prompt: "Extract entities from: {query}"
    LLM-->>Graphiti: entities[]<br/>(e.g., ["authentication", "API"])

    Note over Graph,Neo4j: Step 2: Match entities in graph
    loop For each extracted entity
        Graphiti->>Neo4j: MATCH (n:Entity)<br/>WHERE n.name CONTAINS entity<br/>RETURN n
        Neo4j-->>Graphiti: matching_nodes[]
    end

    Note over Graph,Neo4j: Step 3: Find relationships
    Graphiti->>Neo4j: MATCH (a:Entity)-[r]->(b:Entity)<br/>WHERE a IN matched_entities<br/>OR b IN matched_entities<br/>RETURN a, r, b
    Neo4j-->>Graphiti: relationships[]<br/>(source, edge, target)

    Note over Graphiti: Step 4: Rerank by relevance
    Graphiti->>LLM: Rerank relationships by query relevance
    LLM-->>Graphiti: scored_relationships[]

    Graphiti->>Graphiti: Filter by threshold
    Graphiti->>Graphiti: Sort by score DESC
    Graphiti->>Graphiti: Limit to num_results

    Graphiti-->>Graph: ranked_relationships[]
    Graph-->>MCP: results[]<br/>(relationship_type, fact, entities, validity_dates)
    MCP-->>User: Relationship results
```

**Note:** Graph queries include LLM calls for entity matching and reranking

**Key Features:**
- **LLM-Powered Matching:** Handles synonyms and variations (e.g., "auth" matches "authentication")
- **Collection Scoping:** Only searches within specified collection's graph
- **Relevance Scoring:** Reranks results by semantic relevance to query

---

## Query Temporal Flow

Track how knowledge evolves over time.

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant Graph as Graph Store
    participant Graphiti as Graphiti Library
    participant Neo4j as Neo4j Database

    User->>MCP: query_temporal(query, collection,<br/>valid_from="2024-01-01", valid_until="2025-01-01")

    MCP->>Graph: search_temporal(query, collection, date_range)

    Note over Graph,Graphiti: Step 1: Extract entities
    Graph->>Graphiti: search(query)
    Graphiti->>Graphiti: LLM extracts entities from query

    Note over Graph,Neo4j: Step 2: Find temporal facts
    Graphiti->>Neo4j: MATCH (a:Entity)-[r]->(b:Entity)<br/>WHERE a IN entities OR b IN entities<br/>AND r.valid_from >= date_from<br/>AND r.valid_until <= date_to<br/>RETURN r ORDER BY r.valid_from DESC
    Neo4j-->>Graphiti: temporal_facts[]

    Note over Graphiti: Step 3: Group by status
    Graphiti->>Graphiti: Classify as "current" or "superseded"
    Note over Graphiti: Current: valid_until is NULL or future<br/>Superseded: valid_until in past

    Graphiti->>Graphiti: Sort by valid_from (recent first)
    Graphiti->>Graphiti: Limit to num_results

    Graphiti-->>Graph: timeline[]<br/>(fact, valid_from, valid_until, status)
    Graph-->>MCP: Temporal results
    MCP-->>User: Timeline of how knowledge evolved
```

**Use Cases:**
- "How has the authentication system evolved since 2024?"
- "What changed in the API between January and March?"
- "Show me the history of the deployment process"

**Temporal Fields:**
- `valid_from`: When this fact became true
- `valid_until`: When this fact was superseded (NULL = still current)
- `status`: "current" or "superseded"

---

## Startup Validation Flow

MCP server startup with fail-fast health checks.

```mermaid
sequenceDiagram
    participant CLI as CLI/Docker
    participant Server as MCP Server
    participant Config as Config Loader
    participant DB as Database
    participant PG as PostgreSQL
    participant Graph as Graph Store
    participant Neo4j as Neo4j

    CLI->>Server: Start MCP server

    Note over Server: Lifespan startup
    Server->>Config: load_environment_variables()
    Config->>Config: Check ENV vars
    alt ENV vars set
        Config-->>Server: Use ENV vars
    else Check .env file
        Config->>Config: Read .env
        alt .env exists
            Config-->>Server: Use .env values
        else Check system config
            Config->>Config: Read config.yaml
            alt config.yaml exists
                Config-->>Server: Use system config
            else No config found
                Config-->>Server: ERROR: No configuration
                Server-->>CLI: Exit 1
            end
        end
    end

    Note over Server: Initialize RAG components
    Server->>DB: Database(DATABASE_URL)
    DB->>PG: Test connection
    alt Connection failed
        PG-->>Server: ERROR
        Server-->>CLI: Exit 1
    else Connected
        DB->>PG: validate_schema()
        PG->>PG: Check tables exist<br/>(collections, source_documents, document_chunks)
        PG->>PG: Check pgvector extension
        PG->>PG: Check HNSW indexes
        alt Schema invalid
            PG-->>Server: ERROR: Missing tables/indexes
            Server-->>CLI: Exit 1 (with helpful message)
        else Schema valid
            PG-->>DB: {status: "valid"}
            DB-->>Server: OK
        end
    end

    Note over Server: Initialize Graph components
    Server->>Graph: GraphStore(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    Graph->>Neo4j: Test connection
    alt Connection failed
        Neo4j-->>Server: ERROR
        Server-->>CLI: Exit 1
    else Connected
        Graph->>Neo4j: validate_schema()
        Neo4j->>Neo4j: SHOW INDEXES
        Neo4j->>Neo4j: MATCH (n) RETURN COUNT(n) LIMIT 1
        alt Schema invalid
            Neo4j-->>Server: ERROR: Graph not initialized
            Server-->>CLI: Exit 1 (with helpful message)
        else Schema valid
            Neo4j-->>Graph: {status: "valid", indexes_found: 3}
            Graph-->>Server: OK
        end
    end

    Note over Server: All validations passed
    Server->>Server: Initialize remaining components<br/>(Embedder, CollectionManager, etc.)
    Server-->>CLI: Server ready<br/>Listening on port 8000

    CLI-->>CLI: Health check: GET /health
    Server-->>CLI: 200 OK
```

**Fail-Fast Design:**
- Server won't start if PostgreSQL OR Neo4j unavailable
- Startup validations are lightweight
- Clear error messages guide users to fix configuration issues

**Health Check Endpoint:** `/health` returns 200 OK when all systems operational

---

## Collection Creation Flow

Create a new collection with metadata schema validation.

```mermaid
sequenceDiagram
    participant User as User/AI Agent
    participant MCP as MCP Server
    participant CollMgr as Collection Manager
    participant RAG as RAG Store

    User->>MCP: create_collection(name, description,<br/>domain, domain_scope, metadata_schema)

    Note over MCP: Validate inputs
    MCP->>MCP: Check name not empty
    MCP->>MCP: Check description not empty
    alt Invalid inputs
        MCP-->>User: ERROR: Validation failed
    end

    MCP->>CollMgr: create_collection(...)

    Note over CollMgr: Check for duplicate
    CollMgr->>RAG: SELECT * FROM collections WHERE name = ?
    alt Collection exists
        RAG-->>CollMgr: Row found
        CollMgr-->>MCP: ERROR: Collection already exists
        MCP-->>User: ERROR: Duplicate collection name
    else No duplicate
        RAG-->>CollMgr: No rows
    end

    Note over CollMgr: Validate metadata schema
    alt metadata_schema provided
        CollMgr->>CollMgr: Validate JSON structure<br/>(must have "custom" and "system" keys)
        alt Invalid schema
            CollMgr-->>MCP: ERROR: Invalid schema
            MCP-->>User: ERROR: Schema validation failed
        end
    else No schema provided
        CollMgr->>CollMgr: Use default: {"custom": {}, "system": []}
    end

    Note over CollMgr: Create collection
    CollMgr->>RAG: INSERT INTO collections<br/>(name, description, metadata_schema)
    RAG-->>CollMgr: collection_id

    CollMgr-->>MCP: {collection_id, name, description, metadata_schema}
    MCP-->>User: Success response
```

**Important Constraints:**
- `description` is REQUIRED (NOT NULL constraint in database)
- `name` must be unique
- `metadata_schema` is optional but must be valid JSON if provided

---

## Related Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System components and data models
- **[DATABASE_MIGRATION_GUIDE.md](./DATABASE_MIGRATION_GUIDE.md)** - Schema migration process

For user-facing documentation (installation, MCP setup, usage), see **[`.reference/`](../.reference/README.md)**
