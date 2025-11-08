# RAG Memory CLI Reference

Complete command-line interface reference for RAG Memory.

**Version:** 0.13.0
**Last Updated:** 2025-11-08

---

## Table of Contents

1. [Overview](#overview)
2. [Service Management](#service-management)
3. [Initialization](#initialization)
4. [Collection Management](#collection-management)
5. [Document Ingestion](#document-ingestion)
6. [Search & Retrieval](#search--retrieval)
7. [Document Management](#document-management)
8. [Analysis Tools](#analysis-tools)
9. [Knowledge Graph](#knowledge-graph)
10. [Configuration](#configuration)
11. [Common Workflows](#common-workflows)

---

## Overview

The `rag` CLI provides complete control over your RAG Memory instance, including service management, document ingestion, search, and knowledge graph queries.

**Global Options:**
```bash
rag --version    # Show version
rag --help       # Show help
```

**Command Structure:**
```bash
rag <command> <subcommand> [options]
```

---

## Service Management

### `rag status`

Check the health status of all RAG Memory services (PostgreSQL, Neo4j, MCP, Backup).

**Usage:**
```bash
rag status
```

**Output:**
```
RAG Memory Status

  ✓ postgres: Up 10 minutes (healthy)
  ✓ neo4j: Up 10 minutes (healthy)
  ✓ mcp: Up 5 minutes (healthy)
  ✓ backup: Up 10 minutes (healthy)
```

**Health Check Details:**
- **PostgreSQL**: Tests connectivity + queryability (`SELECT 1`)
- **Neo4j**: Tests authentication + Cypher query execution
- **MCP Server**: Tests HTTP endpoint + database connections (`/health`)
- **Backup**: Verifies backup files exist within last 24 hours

**Status Indicators:**
- ✓ (green) = Healthy - service operational
- ⚠ (yellow) = Warning - service running but not healthy
- ✗ (red) = Down - service not running or failed health check

---

### `rag start`

Start all RAG Memory services using Docker Compose.

**Usage:**
```bash
rag start
```

**What it does:**
- Starts PostgreSQL container
- Starts Neo4j container
- Starts MCP server container
- Starts backup container
- Waits for health checks to pass

**Note:** Containers are started in dependency order (databases first, then MCP server).

---

### `rag stop`

Stop all RAG Memory services and remove containers.

**Usage:**
```bash
rag stop
```

**What it does:**
- Stops all running containers
- Removes containers
- Preserves data volumes (data is NOT lost)
- Removes Docker networks

**Data Safety:** Your data persists in Docker volumes even after stopping.

---

### `rag restart`

Restart all RAG Memory services.

**Usage:**
```bash
rag restart
```

**Equivalent to:** `rag stop && rag start`

---

### `rag logs`

View or export Docker container logs for debugging and troubleshooting.

**Usage:**
```bash
rag logs [OPTIONS]
```

**Options:**
- `--service <name>` - Filter to specific service (mcp, postgres, neo4j, backup)
- `--tail <n>` - Number of lines to show (default: 50)
- `-f, --follow` - Follow log output in real-time (requires --service)
- `--export <path>` - Export logs to a single text file
- `--export-all <path>` - Export all logs + system info to tar.gz archive

**Examples:**
```bash
# View all logs (last 50 lines from each service)
rag logs

# View specific service logs
rag logs --service mcp
rag logs --service postgres

# Show more lines
rag logs --tail 200

# Follow MCP logs in real-time
rag logs --service mcp --follow

# Export logs for bug report
rag logs --export bug-report.txt
rag logs --export-all diagnostics.tar.gz

# Export specific service logs
rag logs --service mcp --export mcp-logs.txt
```

**Export Formats:**

**Text Export (`--export`):**
- Single text file with all logs
- Includes metadata: timestamp, version, service names
- Separators between service sections

**Archive Export (`--export-all`):**
- tar.gz archive containing:
  - `system_info.txt` - Docker version, container status
  - `<service>_logs.txt` - Logs from each service
- Ideal for bug reports or support requests

**Use Cases:**
- Debugging connection issues
- Investigating errors
- Creating bug reports
- Monitoring service behavior

---

## Initialization

### `rag init`

Initialize database schemas for PostgreSQL and Neo4j.

**Usage:**
```bash
rag init
```

**What it does:**
- Verifies PostgreSQL schema exists (usually auto-created by Docker)
- Creates necessary tables if missing
- Initializes Neo4j indices and constraints via Graphiti
- Sets up vector indices for embeddings

**When to run:**
- After first installation
- After upgrading Graphiti version
- If database schemas become corrupted

**Notes:**
- Idempotent - safe to run multiple times
- No data loss - only adds missing schemas
- Automatically called by `setup.py`

---

## Collection Management

Collections organize documents by topic, source, or purpose. They enable scoped searches and flexible organization.

### `rag collection create`

Create a new collection.

**Usage:**
```bash
rag collection create <name> [OPTIONS]
```

**Options:**
- `--description <text>` - Collection description (required)
- `--domain <text>` - Domain category, e.g., "Engineering", "Marketing" (required, immutable)
- `--domain-scope <text>` - Scope description, e.g., "Internal APIs" (required, immutable)

**Examples:**
```bash
# Basic collection
rag collection create tech-docs \
  --description "Technical documentation" \
  --domain "Engineering" \
  --domain-scope "Public API and SDK documentation"

# Project-specific collection
rag collection create project-x \
  --description "Project X design docs and specs" \
  --domain "Product" \
  --domain-scope "Project X scope only"
```

**Notes:**
- Collection names must be unique
- Domain and domain-scope are immutable after creation
- Description can be updated later

---

### `rag collection list`

List all collections with document and chunk counts.

**Usage:**
```bash
rag collection list
```

**Output:**
```
Collections:
  tech-docs (42 documents, 523 chunks)
  project-x (15 documents, 187 chunks)
  meeting-notes (8 documents, 94 chunks)
```

---

### `rag collection info`

Show detailed information about a collection.

**Usage:**
```bash
rag collection info <name>
```

**Output:**
```
Collection: tech-docs
Description: Technical documentation
Domain: Engineering
Domain Scope: Public API and SDK documentation

Statistics:
  Documents: 42
  Chunks: 523
  Created: 2024-10-15 14:30:00

Sample Documents:
  - api-reference.md (25 chunks)
  - getting-started.md (18 chunks)
  - advanced-usage.md (32 chunks)

Metadata Schema:
  <metadata fields and types>
```

---

### `rag collection schema`

Display the metadata schema for a collection.

**Usage:**
```bash
rag collection schema <name>
```

**Output:**
```
Metadata Schema for collection: tech-docs

System Fields:
  - source
  - doc_type
  - created_at

Custom Fields:
  - version: string
  - author: string
  - tags: array
```

---

### `rag collection update-metadata`

Update collection metadata schema (additive only).

**Usage:**
```bash
rag collection update-metadata <name> --fields '<json>'
```

**Examples:**
```bash
# Add new optional fields
rag collection update-metadata tech-docs \
  --fields '{"version": "string", "author": "string"}'
```

**Notes:**
- Can only ADD fields, cannot remove
- New fields are optional by default
- Existing documents won't have new fields until updated

---

### `rag collection delete`

Delete a collection and all its documents (requires confirmation).

**Usage:**
```bash
rag collection delete <name>
```

**Interactive Confirmation:**
```
⚠️  WARNING: This will permanently delete collection 'tech-docs' and all 42 documents.
Type the collection name to confirm: tech-docs
```

**Notes:**
- Requires typing collection name to confirm
- Deletes all documents in collection
- Deletes associated knowledge graph data
- Cannot be undone

---

## Document Ingestion

### `rag ingest text`

Ingest text content directly.

**Usage:**
```bash
rag ingest text "<content>" --collection <name> [OPTIONS]
```

**Options:**
- `--collection <name>` - Target collection (required)
- `--title <text>` - Document title (optional, auto-generated if omitted)
- `--metadata '<json>'` - Custom metadata as JSON string
- `--chunk-size <n>` - Chunk size (default: 1000)
- `--chunk-overlap <n>` - Chunk overlap (default: 200)

**Examples:**
```bash
# Basic text ingestion
rag ingest text "PostgreSQL is a powerful database" \
  --collection tech-notes

# With title and metadata
rag ingest text "Our API uses OAuth 2.0 for authentication" \
  --collection tech-docs \
  --title "Authentication Guide" \
  --metadata '{"version": "2.0", "author": "Security Team"}'
```

---

### `rag ingest file`

Ingest a document from a file.

**Usage:**
```bash
rag ingest file <path> --collection <name> [OPTIONS]
```

**Options:**
- `--collection <name>` - Target collection (required)
- `--metadata '<json>'` - Custom metadata
- `--chunk-size <n>` - Chunk size (default: 1000)
- `--chunk-overlap <n>` - Chunk overlap (default: 200)

**Supported Formats:**
- Text files: .txt, .md, .markdown
- Code files: .py, .js, .java, .go, .rs, etc.
- Config files: .json, .yaml, .yml, .toml, .ini
- Documentation: .rst, .adoc

**Examples:**
```bash
# Ingest markdown file
rag ingest file docs/api-guide.md --collection tech-docs

# With metadata
rag ingest file specs/design.md \
  --collection project-x \
  --metadata '{"status": "approved", "version": "1.2"}'
```

---

### `rag ingest directory`

Batch ingest all files from a directory.

**Usage:**
```bash
rag ingest directory <path> --collection <name> [OPTIONS]
```

**Options:**
- `--collection <name>` - Target collection (required)
- `--extensions <list>` - File extensions to include (e.g., ".md,.txt")
- `--recursive` - Search subdirectories recursively
- `--metadata '<json>'` - Metadata applied to ALL files
- `--chunk-size <n>` - Chunk size (default: 1000)
- `--chunk-overlap <n>` - Chunk overlap (default: 200)

**Examples:**
```bash
# Ingest all markdown files (current directory only)
rag ingest directory ./docs \
  --collection tech-docs \
  --extensions ".md"

# Recursive ingestion with multiple formats
rag ingest directory ./project \
  --collection project-x \
  --extensions ".md,.txt,.rst" \
  --recursive

# With metadata for all files
rag ingest directory ./specs \
  --collection design-docs \
  --extensions ".md" \
  --recursive \
  --metadata '{"source": "internal", "status": "active"}'
```

---

### `rag ingest url`

Crawl and ingest web pages with optional link following.

**Usage:**
```bash
rag ingest url <url> --collection <name> [OPTIONS]
```

**Options:**
- `--collection <name>` - Target collection (required)
- `--mode <crawl|recrawl>` - Crawl mode (default: crawl)
  - `crawl` - Fresh crawl (error if URL already exists)
  - `recrawl` - Delete old pages, then crawl fresh
- `--follow-links` - Follow internal links for multi-page crawl
- `--max-depth <n>` - Maximum crawl depth when following links (default: 1)
- `--headless / --no-headless` - Run browser in headless mode (default: headless)
- `--verbose` - Show detailed crawling output
- `--metadata '<json>'` - Metadata applied to ALL crawled pages
- `--chunk-size <n>` - Chunk size for web pages (default: 2500)
- `--chunk-overlap <n>` - Chunk overlap (default: 300)

**Examples:**
```bash
# Single page only
rag ingest url https://example.com/guide --collection docs

# Multi-page crawl (follow direct links)
rag ingest url https://docs.python.org \
  --collection python-docs \
  --follow-links

# Deep crawl (2 levels)
rag ingest url https://docs.example.com \
  --collection api-docs \
  --follow-links \
  --max-depth 2

# Re-crawl to update existing content
rag ingest url https://docs.example.com \
  --collection api-docs \
  --mode recrawl \
  --follow-links

# With metadata and custom chunking
rag ingest url https://docs.example.com/api \
  --collection api-docs \
  --follow-links \
  --metadata '{"source": "official", "doc_type": "api"}' \
  --chunk-size 3000 \
  --chunk-overlap 400
```

**Metadata Tracking:**
Web crawls automatically add:
- `crawl_root_url` - Starting URL
- `crawl_session_id` - Unique session identifier
- `crawl_depth` - Distance from root (0 = start page)
- `crawl_timestamp` - When crawled (ISO 8601)
- `parent_url` - Which page linked to this one

**Recrawl Mode:**
- Finds all pages from previous crawls of the same URL
- Deletes old pages (identified by `crawl_root_url`)
- Crawls fresh content
- Preserves other documents in collection
- Prevents duplicate/stale content

---

## Search & Retrieval

### `rag search`

Search for semantically similar document chunks.

**Usage:**
```bash
rag search "<query>" [OPTIONS]
```

**Options:**
- `--collection <name>` - Search within specific collection
- `--limit <n>` - Maximum number of results (default: 10)
- `--threshold <0-1>` - Minimum similarity score filter
- `--metadata '<json>'` - Filter by metadata (JSON string)
- `--verbose` - Show full chunk content (not just preview)
- `--show-source` - Include full source document content

**Examples:**
```bash
# Basic search
rag search "How do I authenticate users?"

# Search specific collection
rag search "PostgreSQL performance tips" --collection tech-docs

# Strict matching (high confidence only)
rag search "API rate limits" --threshold 0.7

# More results
rag search "error handling" --limit 20

# Filter by metadata
rag search "deployment" \
  --metadata '{"doc_type": "guide", "version": "2.0"}'

# Full content display
rag search "authentication" --verbose --show-source
```

**Similarity Scores:**
- **0.90-1.00** - Near-identical (exact match or rephrasing)
- **0.70-0.89** - Highly relevant (what you're looking for)
- **0.50-0.69** - Related (relevant but less direct)
- **0.30-0.49** - Somewhat related (might be useful)
- **0.00-0.29** - Loosely related or unrelated

**Threshold Recommendations:**
- `0.7` - Production/strict (high confidence only)
- `0.5` - Balanced (good mix of precision + recall)
- `0.3` - Exploratory (cast wide net)
- None - Top-N results regardless of score

**Output Format:**
```
Results: 3 chunks found

[1] Similarity: 0.85 | tech-docs/api-guide.md (chunk 5/12)
Authentication uses OAuth 2.0 with JWT tokens. All API requests
must include an Authorization header...

[2] Similarity: 0.72 | tech-docs/security.md (chunk 2/8)
User authentication follows industry best practices. We support
multiple auth methods including OAuth, SAML, and API keys...

[3] Similarity: 0.68 | tech-docs/getting-started.md (chunk 3/10)
Before making API calls, authenticate by obtaining an access
token from the /auth endpoint...
```

---

## Document Management

### `rag document list`

List all source documents.

**Usage:**
```bash
rag document list [OPTIONS]
```

**Options:**
- `--collection <name>` - Filter by collection
- `--limit <n>` - Max documents to show (default: 50)
- `--offset <n>` - Skip first N documents for pagination (default: 0)
- `--verbose` - Show full metadata

**Examples:**
```bash
# List all documents
rag document list

# List documents in specific collection
rag document list --collection tech-docs

# Paginate results
rag document list --limit 20 --offset 40

# Show detailed information
rag document list --verbose
```

---

### `rag document view`

View a source document and its chunks.

**Usage:**
```bash
rag document view <document_id>
```

**Output:**
```
Document ID: 42
Title: api-guide.md
Collection: tech-docs
Chunks: 12
Created: 2024-10-15 14:30:00

Metadata:
  version: 2.0
  author: Engineering Team
  doc_type: guide

Content:
<full document content>

Chunks:
  [1] chars 0-1000
  [2] chars 800-1800
  ...
```

---

### `rag document update`

Update a document's content, title, or metadata.

**Usage:**
```bash
rag document update <document_id> [OPTIONS]
```

**Options:**
- `--content "<text>"` - New content (triggers re-chunking and re-embedding)
- `--title "<text>"` - New title
- `--metadata '<json>'` - Updated metadata (merged with existing)

**Examples:**
```bash
# Update content
rag document update 42 --content "New updated content here"

# Update title
rag document update 42 --title "API Reference v2.0"

# Update metadata
rag document update 42 --metadata '{"version": "2.1", "status": "reviewed"}'

# Update multiple fields
rag document update 42 \
  --title "Complete API Guide" \
  --metadata '{"version": "2.0"}'
```

**Notes:**
- Content updates trigger full re-chunking and re-embedding (has cost)
- Metadata is merged, not replaced (to remove a field, delete and re-ingest)
- Title updates are instant and free

---

### `rag document delete`

Delete a source document and all its chunks.

**Usage:**
```bash
rag document delete <document_id>
```

**Interactive Confirmation:**
```
⚠️  WARNING: This will permanently delete document 'api-guide.md' and all 12 chunks.
Type 'yes' to confirm: yes
```

**Notes:**
- Deletes document from PostgreSQL
- Deletes associated knowledge graph data from Neo4j
- Cannot be undone
- Free operation (no API calls)

---

## Analysis Tools

### `rag analyze website`

Analyze a website's structure to discover URL patterns before crawling.

**Usage:**
```bash
rag analyze website <url> [OPTIONS]
```

**Options:**
- `--include-urls` - Include sample URLs for each pattern (not just stats)
- `--max-urls <n>` - Max sample URLs per pattern (default: 10, requires --include-urls)
- `--timeout <n>` - DEPRECATED (timeout is hard-coded to 50 seconds)

**Examples:**
```bash
# Quick analysis (pattern statistics only)
rag analyze website https://docs.python.org

# Include sample URLs
rag analyze website https://docs.python.org --include-urls

# More samples per pattern
rag analyze website https://docs.python.org \
  --include-urls \
  --max-urls 20

# Analyze specific section of large site
rag analyze website https://docs.python.org/3.11
```

**What It Does:**
1. Tries sitemap.xml first (both provided URL and root domain)
2. Falls back to Common Crawl index if no sitemap
3. Groups URLs by path pattern (e.g., /api/*, /docs/*, /blog/*)
4. Returns up to 150 URLs grouped by pattern
5. Shows statistics: total URLs, pattern counts, sample URLs

**Output Format:**
```
Website Analysis: https://docs.python.org

Total URLs: 487
Patterns Found: 12

Pattern Statistics:
  /library/* - 234 URLs (avg depth: 2.1)
    - https://docs.python.org/library/os.html
    - https://docs.python.org/library/sys.html
    - https://docs.python.org/library/json.html

  /tutorial/* - 89 URLs (avg depth: 2.0)
    - https://docs.python.org/tutorial/introduction.html
    - https://docs.python.org/tutorial/controlflow.html

  /reference/* - 67 URLs (avg depth: 2.3)
    ...

Recommendation: Site has 487 pages. Consider targeted ingests:
  rag ingest url https://docs.python.org/library --follow-links --max-depth 2
  rag ingest url https://docs.python.org/tutorial --follow-links --max-depth 2
```

**Hard Timeout:** 50 seconds. If analysis exceeds this:
- Try analyzing a specific subsection instead (e.g., /docs, /api)
- Or use manual crawling with limited depth

**Use Case:**
Understand site structure and plan comprehensive crawls BEFORE ingesting. Helps you decide:
- Which URL patterns to target
- How deep to crawl
- Whether to split into multiple ingests (recommended for 20+ pages per section)

**Free Operation:** No API calls, just HTTP requests to discover URLs.

---

## Knowledge Graph

The knowledge graph tracks entities, relationships, and temporal knowledge evolution. See [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) for complete details.

### `rag graph query-relationships`

Search for entity relationships using natural language.

**Usage:**
```bash
rag graph query-relationships "<query>" [OPTIONS]
```

**Options:**
- `--collection <name>` - Scope to specific collection
- `--num-results <n>` - Max relationships to return (default: 5, max: 20)
- `--threshold <0-1>` - Relevance filter (default: 0.35)

**Examples:**
```bash
# Find relationships
rag graph query-relationships "How does the API relate to authentication?"

# Scoped search
rag graph query-relationships "What depends on the database?" \
  --collection tech-docs

# More results, higher threshold
rag graph query-relationships "What connects to the backend?" \
  --num-results 10 \
  --threshold 0.5
```

**Output Format:**
```
Relationships Found: 3

[1] API -> USES -> Authentication Service
    Fact: The API uses OAuth 2.0 authentication service for user validation
    Valid: 2024-10-01 to present

[2] Authentication Service -> DEPENDS_ON -> Database
    Fact: Authentication service stores user credentials in PostgreSQL
    Valid: 2024-09-15 to present

[3] API -> IMPLEMENTS -> Rate Limiting
    Fact: API implements rate limiting at 1000 requests per hour per key
    Valid: 2024-10-15 to present
```

---

### `rag graph query-temporal`

Query how knowledge evolved over time.

**Usage:**
```bash
rag graph query-temporal "<query>" [OPTIONS]
```

**Options:**
- `--collection <name>` - Scope to specific collection
- `--num-results <n>` - Max timeline items (default: 10, max: 50)
- `--threshold <0-1>` - Relevance filter (default: 0.35)
- `--valid-from <date>` - Return facts valid AFTER this date (ISO 8601)
- `--valid-until <date>` - Return facts valid BEFORE this date (ISO 8601)

**Examples:**
```bash
# Track evolution
rag graph query-temporal "How has our API architecture changed?"

# Time window
rag graph query-temporal "Authentication method changes" \
  --valid-from "2024-01-01" \
  --valid-until "2024-12-31"

# Recent changes only
rag graph query-temporal "What security updates were made?" \
  --valid-from "2024-10-01"
```

**Output Format:**
```
Timeline: 3 events found

[1] CURRENT (2024-10-15 - present)
    Fact: API uses OAuth 2.0 authentication
    Relationship: API -> USES -> OAuth 2.0
    Status: current

[2] SUPERSEDED (2024-09-01 - 2024-10-15)
    Fact: API used Basic Authentication
    Relationship: API -> USES -> Basic Auth
    Status: superseded (replaced on 2024-10-15)

[3] SUPERSEDED (2024-01-01 - 2024-09-01)
    Fact: API used API key authentication
    Relationship: API -> USES -> API Keys
    Status: superseded (replaced on 2024-09-01)
```

---

### `rag graph rebuild-communities`

Rebuild community detection for the Knowledge Graph.

**Usage:**
```bash
rag graph rebuild-communities
```

**What It Does:**
- Analyzes entity relationships to find communities (clusters)
- Groups related entities together
- Updates community metadata in Neo4j

**When to Run:**
- After major ingestion batches
- When relationship structure changes significantly
- If community detection seems stale

**Notes:**
- Can take several minutes for large graphs
- Safe to run multiple times (idempotent)
- Free operation (no API calls)

---

## Configuration

### `rag config show`

Display current configuration.

**Usage:**
```bash
rag config show
```

**Output:**
```
Configuration: /Users/you/Library/Application Support/rag-memory/config.yaml

Database:
  PostgreSQL: postgresql://raguser:***@localhost:54320/rag_memory
  Neo4j URI: bolt://localhost:7687
  Neo4j User: neo4j

OpenAI:
  API Key: sk-***************
  Embedding Model: text-embedding-3-small

Backup:
  Enabled: true
  Schedule: 5 2 * * * (daily at 2:05 AM)
  Archive: /path/to/backups

Directory Mounts:
  /Users/you/Documents -> /mnt/documents
  /Users/you/Projects -> /mnt/projects
```

---

### `rag config edit`

Open configuration file in system editor.

**Usage:**
```bash
rag config edit
```

**Opens:** `config.yaml` in `$EDITOR` (or default system editor)

**Common Edits:**
- Update OpenAI API key
- Change database connection strings
- Add directory mounts
- Modify backup settings

**After Editing:**
- Restart services: `rag restart`
- Verify configuration: `rag config show`

---

### `rag config set`

Set a specific configuration value.

**Usage:**
```bash
rag config set <key> <value>
```

**Examples:**
```bash
# Update OpenAI API key
rag config set openai.api_key "sk-new-key-here"

# Change backup schedule
rag config set backup.cron_expression "0 3 * * *"

# Add directory mount
rag config set mounts.my-docs "/Users/you/Documents"
```

**After Setting:**
- Restart services: `rag restart`
- Verify: `rag config show`

---

## Common Workflows

### Initial Setup

```bash
# 1. Start services
rag start

# 2. Verify everything is running
rag status

# 3. Initialize databases
rag init

# 4. Create first collection
rag collection create tech-docs \
  --description "Technical documentation" \
  --domain "Engineering" \
  --domain-scope "Public APIs and guides"

# 5. Ingest some content
rag ingest url https://docs.example.com \
  --collection tech-docs \
  --follow-links

# 6. Search it
rag search "How do I authenticate?"
```

---

### Comprehensive Documentation Crawl

```bash
# 1. Analyze site structure first
rag analyze website https://docs.python.org --include-urls

# Output shows patterns:
#   /library/* - 234 URLs
#   /tutorial/* - 89 URLs
#   /reference/* - 67 URLs

# 2. Create collection
rag collection create python-docs \
  --description "Official Python documentation" \
  --domain "Programming" \
  --domain-scope "Python 3.11 official docs"

# 3. Targeted ingests (one per major section)
rag ingest url https://docs.python.org/library \
  --collection python-docs \
  --follow-links \
  --max-depth 2

rag ingest url https://docs.python.org/tutorial \
  --collection python-docs \
  --follow-links \
  --max-depth 2

rag ingest url https://docs.python.org/reference \
  --collection python-docs \
  --follow-links \
  --max-depth 2

# 4. Verify ingestion
rag collection info python-docs
```

---

### Updating Stale Documentation

```bash
# 1. Check current state
rag collection info tech-docs

# 2. Re-crawl to update
rag ingest url https://docs.example.com \
  --collection tech-docs \
  --mode recrawl \
  --follow-links

# Recrawl will:
# - Find pages from previous crawl of docs.example.com
# - Delete old pages
# - Crawl fresh content
# - Report: "Deleted 12 old pages, crawled 15 new pages"
```

---

### Troubleshooting Service Issues

```bash
# 1. Check service status
rag status

# If services are down:
# 2. View recent logs
rag logs --tail 100

# 3. View specific service logs
rag logs --service mcp --tail 200
rag logs --service postgres --tail 200
rag logs --service neo4j --tail 200

# 4. Export all logs for bug report
rag logs --export-all diagnostics.tar.gz

# 5. Restart services
rag restart

# 6. Verify recovery
rag status
```

---

### Knowledge Graph Exploration

```bash
# 1. Ingest content (automatically builds graph)
rag ingest file architecture-doc.md --collection tech-docs

# 2. Find relationships
rag graph query-relationships "How does the API connect to services?"

# 3. Track changes over time
rag graph query-temporal "How has our authentication evolved?"

# 4. Rebuild communities after major changes
rag graph rebuild-communities
```

---

## Tips & Best Practices

### Search Optimization

1. **Use full questions, not keywords**
   - ✅ "How do I authenticate users in my application?"
   - ❌ "authentication users app"

2. **Adjust threshold based on use case**
   - Production: `--threshold 0.7` (high confidence)
   - General: `--threshold 0.5` (balanced)
   - Exploratory: `--threshold 0.3` (cast wide net)

3. **Start broad, then narrow**
   ```bash
   # First, see what's there
   rag search "authentication"

   # Then get specific
   rag search "OAuth 2.0 token refresh flow" --threshold 0.7
   ```

### Collection Organization

1. **One collection per domain/topic**
   - tech-docs (API documentation)
   - meeting-notes (team discussions)
   - project-x (specific project)

2. **Use metadata for filtering**
   ```bash
   # Tag during ingestion
   rag ingest url https://api-docs.com \
     --collection tech-docs \
     --metadata '{"doc_type": "api", "version": "2.0"}'

   # Filter during search
   rag search "endpoints" --metadata '{"doc_type": "api"}'
   ```

### Web Crawling

1. **Always analyze first for large sites**
   ```bash
   rag analyze website https://docs.example.com --include-urls
   # Review output, then plan targeted crawls
   ```

2. **Use targeted ingests for 20+ pages per section**
   ```bash
   # Better: multiple targeted ingests
   rag ingest url https://docs.example.com/api --follow-links --max-depth 2
   rag ingest url https://docs.example.com/guides --follow-links --max-depth 2

   # Worse: one giant crawl
   rag ingest url https://docs.example.com --follow-links --max-depth 3
   ```

3. **Use recrawl mode to keep documentation fresh**
   ```bash
   # Weekly cron job
   rag ingest url https://docs.example.com/api \
     --collection tech-docs \
     --mode recrawl \
     --follow-links
   ```

---

## Exit Codes

- `0` - Success
- `1` - General error (check error message)
- `130` - Interrupted (Ctrl+C)

---

## Environment Variables

- `OPENAI_API_KEY` - OpenAI API key (required)
- `DATABASE_URL` - PostgreSQL connection string
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USER` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password
- `RAG_CONFIG_PATH` - Override config file location

**Note:** These are typically set in `config.yaml`, not as environment variables.

---

## See Also

- [OVERVIEW.md](OVERVIEW.md) - Complete system overview
- [MCP_QUICK_START.md](MCP_QUICK_START.md) - MCP server setup
- [KNOWLEDGE_GRAPH.md](KNOWLEDGE_GRAPH.md) - Knowledge graph details
- [SEARCH_OPTIMIZATION.md](SEARCH_OPTIMIZATION.md) - Search tuning
- [PRICING.md](PRICING.md) - Cost analysis

---

**Last Updated:** 2025-11-08
**Version:** 0.13.0
