# Plan: Remove Topics and Auto-Apply Domain/Domain_Scope

## Decision Summary

1. **Remove `topics` entirely** - Not useful for RAG, causes inconsistency issues
2. **Keep `domain` and `domain_scope`** - Collection-level, immutable metadata
3. **Auto-apply domain/domain_scope** - Fetch from collection and apply to all ingested documents automatically
4. **Remove from ingestion APIs** - Clients should NOT pass domain/domain_scope on ingest

## Mandatory Metadata Schema (After Changes)

```json
{
  "mandatory": {
    "domain": "string (immutable)",
    "domain_scope": "string (immutable)"
  },
  "custom": { ... },
  "system": [ ... ]
}
```

---

## Phase 1: Code Analysis

### 1.1 Collection Creation Entry Points
- [ ] `src/mcp/server.py` - MCP tool `create_collection`
- [ ] `src/mcp/tools.py` - Implementation `create_collection_impl`
- [ ] `src/core/collections.py` - Core `CollectionManager.create_collection`
- [ ] `src/cli.py` - CLI command `collection create`

### 1.2 Collection Update Entry Points
- [ ] `src/mcp/server.py` - MCP tool `update_collection_metadata`
- [ ] `src/mcp/tools.py` - Implementation `update_collection_metadata_impl`
- [ ] `src/core/collections.py` - Core `CollectionManager.update_collection_metadata_schema`
- [ ] `src/cli.py` - CLI command `collection update-metadata`

### 1.3 Document Ingestion Entry Points (Need Auto-Apply Logic)
- [ ] `src/mcp/server.py` - MCP tools: `ingest_text`, `ingest_url`, `ingest_file`, `ingest_directory`
- [ ] `src/mcp/tools.py` - Implementations: `ingest_text_impl`, `ingest_url_impl`, `ingest_file_impl`, `ingest_directory_impl`
- [ ] `src/cli.py` - CLI commands: `ingest text`, `ingest url`, `ingest file`, `ingest directory`
- [ ] `src/ingestion/document_store.py` - Core ingestion logic (WHERE AUTO-APPLY HAPPENS)
- [ ] `src/unified/mediator.py` - Unified ingestion mediator (if it handles metadata)

### 1.4 Test Files Analysis

#### Unit Tests
- [ ] `tests/unit/test_collection_metadata_update.py` - Remove topics from mock schemas
- [ ] `tests/unit/test_mcp_metadata_update.py` - Remove topics from mock schemas

#### Integration Tests - MCP
- [ ] `tests/integration/mcp/test_collections.py` - Remove topics from create_collection calls
- [ ] `tests/integration/mcp/test_error_handling.py` - Remove topics from create_collection calls
- [ ] `tests/integration/mcp/test_search_documents.py` - Remove topics from create_collection calls

#### Integration Tests - CLI
- [ ] `tests/integration/cli/test_cli_integration.py` - Remove topics from CLI create commands

#### Integration Tests - Web
- [ ] `tests/integration/web/test_web_ingestion.py` - Remove topics from create_collection calls
- [ ] `tests/integration/web/test_recrawl.py` - Remove topics from create_collection calls
- [ ] `tests/integration/web/test_web_link_following.py` - Remove topics from create_collection calls

#### Integration Tests - Backend
- [ ] `tests/integration/backend/test_rag_graph.py` - Remove topics from create_collection calls
- [ ] `tests/integration/backend/test_document_chunking.py` - Remove topics from create_collection calls
- [ ] `tests/integration/test_delete_collection_graph_cleanup.py` - Remove topics from create_collection calls

#### Test Fixtures
- [ ] `tests/conftest.py` - Remove topics from setup_test_collection fixture

---

## Phase 2: Implementation Changes

### 2.1 Remove Topics from Collection Creation

#### File: `src/core/collections.py`
- [ ] Update `create_collection()` signature - remove `topics` parameter
- [ ] Update validation logic - remove topics validation
- [ ] Update metadata_schema initialization - remove topics from mandatory section
- [ ] Update docstring

#### File: `src/mcp/tools.py`
- [ ] Update `create_collection_impl()` signature - remove `topics` parameter
- [ ] Update call to `coll_mgr.create_collection()` - remove topics argument
- [ ] Update return value - remove topics field
- [ ] Update docstring

#### File: `src/mcp/server.py`
- [ ] Update `create_collection` tool signature - remove `topics` parameter
- [ ] Update call to `create_collection_impl()` - remove topics argument
- [ ] Update docstring

#### File: `src/cli.py`
- [ ] Update `collection create` command - remove `--topics` option
- [ ] Update call to `mgr.create_collection()` - remove topics argument

### 2.2 Remove Topics from Collection Updates

#### File: `src/core/collections.py`
- [ ] Update `update_collection_metadata_schema()` - remove topics merge logic
- [ ] Update validation - remove topics-related validation
- [ ] Update docstring

#### File: `src/mcp/tools.py`
- [ ] Update `update_collection_metadata_impl()` - remove topics counting/tracking
- [ ] Update return value - remove `topics_added`, `total_topics` fields
- [ ] Update docstring

### 2.3 Auto-Apply Domain/Domain_Scope on Ingestion

#### File: `src/ingestion/document_store.py`
**This is the CRITICAL change - where auto-apply happens**

- [ ] Locate `ingest_document()` method
- [ ] Add logic to fetch collection metadata:
  ```python
  collection = self.coll_mgr.get_collection(collection_name)
  mandatory_metadata = collection.get("metadata_schema", {}).get("mandatory", {})
  domain = mandatory_metadata.get("domain")
  domain_scope = mandatory_metadata.get("domain_scope")
  ```
- [ ] Merge domain/domain_scope into document metadata:
  ```python
  if metadata is None:
      metadata = {}
  metadata["domain"] = domain
  metadata["domain_scope"] = domain_scope
  ```
- [ ] Verify this happens BEFORE embedding/storage
- [ ] Update all ingestion methods: `ingest_text()`, `ingest_file()`, etc.

#### File: `src/unified/mediator.py` (if applicable)
- [ ] Check if unified mediator handles metadata merging
- [ ] If yes, add same auto-apply logic there
- [ ] If no, verify it delegates to document_store (which handles it)

### 2.4 Remove Domain/Domain_Scope from Ingestion APIs

#### File: `src/mcp/server.py`
- [ ] Update `ingest_text` tool - remove `domain`, `domain_scope` parameters
- [ ] Update `ingest_url` tool - remove `domain`, `domain_scope` parameters
- [ ] Update `ingest_file` tool - remove `domain`, `domain_scope` parameters
- [ ] Update `ingest_directory` tool - remove `domain`, `domain_scope` parameters
- [ ] Update all docstrings

#### File: `src/mcp/tools.py`
- [ ] Update `ingest_text_impl()` - remove parameters
- [ ] Update `ingest_url_impl()` - remove parameters
- [ ] Update `ingest_file_impl()` - remove parameters
- [ ] Update `ingest_directory_impl()` - remove parameters
- [ ] Update all calls to underlying ingestion methods
- [ ] Update all docstrings

#### File: `src/cli.py`
- [ ] Update `ingest text` command - remove `--domain`, `--domain-scope` options
- [ ] Update `ingest url` command - remove `--domain`, `--domain-scope` options
- [ ] Update `ingest file` command - remove `--domain`, `--domain-scope` options
- [ ] Update `ingest directory` command - remove `--domain`, `--domain-scope` options

---

## Phase 3: Test Updates

### 3.1 Unit Tests

#### File: `tests/unit/test_collection_metadata_update.py`
- [ ] Line 31-35: Remove topics from mock schema (5 occurrences)
- [ ] Line 89-93: Remove topics from mock schema
- [ ] Line 127-131: Remove topics from mock schema
- [ ] Line 169-173: Remove topics from mock schema
- [ ] Line 246-250: Remove topics from mock schema

#### File: `tests/unit/test_mcp_metadata_update.py`
- [ ] Line 20-26: Remove topics from existing_collection mock
- [ ] Line 36-42: Remove topics from updated_collection mock
- [ ] Line 71-76: Remove topics from existing mock
- [ ] Line 85-90: Remove topics from updated mock
- [ ] Line 122-128: Remove topics from existing mock
- [ ] Remove `topics_added`, `total_topics` assertions

### 3.2 Integration Tests - MCP

#### File: `tests/integration/mcp/test_collections.py`
- [ ] Line 23-29: Remove topics from create_collection call (8 total calls in file)
- [ ] Update response assertions - remove topics checks
- [ ] Verify all 8 create_collection calls are updated

#### File: `tests/integration/mcp/test_error_handling.py`
- [ ] Line 107-113: Remove topics from create_collection call
- [ ] Line 118-124: Remove topics from create_collection call

#### File: `tests/integration/mcp/test_search_documents.py`
- [ ] Line 80-86: Remove topics from create_collection call
- [ ] Line 87-93: Remove topics from create_collection call

### 3.3 Integration Tests - CLI

#### File: `tests/integration/cli/test_cli_integration.py`
- [ ] Line 37-44: Remove `--topics` from CLI create command
- [ ] Verify command still works with just domain and domain_scope

### 3.4 Integration Tests - Web

#### File: `tests/integration/web/test_web_ingestion.py`
- [ ] Line 29-35: Remove topics from create_collection call
- [ ] Line 40-46: Remove topics from create_collection call

#### File: `tests/integration/web/test_recrawl.py`
- [ ] Line 29-35: Remove topics from create_collection call
- [ ] Line 40-46: Remove topics from create_collection call

#### File: `tests/integration/web/test_web_link_following.py`
- [ ] Line 29-35: Remove topics from create_collection call
- [ ] Line 40-46: Remove topics from create_collection call

### 3.5 Integration Tests - Backend

#### File: `tests/integration/backend/test_rag_graph.py`
- [ ] Line 95-101: Remove topics from create_collection call
- [ ] Line 181-187: Remove topics from create_collection call

#### File: `tests/integration/backend/test_document_chunking.py`
- [ ] Line 56-62: Remove topics from create_collection call

#### File: `tests/integration/test_delete_collection_graph_cleanup.py`
- [ ] Line 90-96: Remove topics from create_collection call

### 3.6 Test Fixtures

#### File: `tests/conftest.py`
- [ ] Line 400-406: Remove topics from create_collection call in setup_test_collection fixture

---

## Phase 4: Verification

### 4.1 Run Targeted Tests
- [ ] Run all unit tests: `uv run pytest tests/unit/ -xvs`
- [ ] Run all MCP integration tests: `uv run pytest tests/integration/mcp/ -xvs`
- [ ] Run CLI integration test: `uv run pytest tests/integration/cli/test_cli_integration.py -xvs`
- [ ] Run web integration tests: `uv run pytest tests/integration/web/ -xvs`
- [ ] Run backend integration tests: `uv run pytest tests/integration/backend/ -xvs`
- [ ] Run delete collection test: `uv run pytest tests/integration/test_delete_collection_graph_cleanup.py -xvs`

### 4.2 Full Test Suite
- [ ] Run complete test suite: `uv run pytest -xvs`
- [ ] Verify all tests pass

### 4.3 Manual Verification
- [ ] Test MCP create_collection with only domain and domain_scope
- [ ] Test CLI create collection with only domain and domain_scope
- [ ] Test document ingestion and verify domain/domain_scope are auto-applied to metadata
- [ ] Verify search still works correctly

---

## Status Tracking

**Current Phase:** Not Started

**Completed Phases:**
- None

**Blocked Items:**
- None

**Notes:**
- This plan will be updated as implementation progresses
- Each checkbox will be marked as work is completed
- Any issues discovered will be documented here
