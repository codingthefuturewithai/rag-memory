# CLI Test Plan

**Status**: Updated after CLI alignment changes (2025-10-24)

**Coverage Goal**: Achieve >80% coverage on src/cli.py (~1,700 lines)

**Strategy**:
- ~20 unit tests (Click CliRunner with mocked components) - tests parameter handling, validation, help text
- ~2-3 integration tests (real database) - tests core workflows (search, ingest, collection management)

---

## Test Categories

### 1. Collection Commands (~8 tests)

**Unit Tests (Click CliRunner + mocks):**
- `test_collection_create_valid` - Create with valid name/description
- `test_collection_create_missing_description` - Error when description missing
- `test_collection_list` - List returns all collections
- `test_collection_list_empty` - List returns empty when no collections
- `test_collection_info_valid` - Info shows correct stats
- `test_collection_info_not_found` - Error on missing collection
- `test_collection_schema_valid` - Schema displays metadata schema (NEW)
- `test_collection_delete_confirmation` - Delete with confirmation prompt

**Notes:**
- Removed: `test_collection_update_*` tests (command removed - immutable collections)
- Added: `test_collection_schema_valid` (new command)

---

### 2. Ingest Commands (~8 tests)

**Unit Tests (Click CliRunner + mocks):**
- `test_ingest_text_valid` - Ingest text with valid parameters
- `test_ingest_text_missing_collection` - Error on missing collection
- `test_ingest_file_valid` - Ingest file with valid path
- `test_ingest_file_not_found` - Error on missing file
- `test_ingest_directory_valid` - Ingest directory with extensions filter
- `test_ingest_url_crawl_mode` - Ingest URL with --mode crawl (NEW)
- `test_ingest_url_recrawl_mode` - Ingest URL with --mode recrawl (NEW - replaces recrawl command)
- `test_ingest_url_follow_links` - Ingest URL with --follow-links and --max-depth

**Notes:**
- Merged: `ingest_url` and `recrawl` now unified with `--mode` parameter
- Removed: Separate `test_recrawl_*` tests (command merged)
- Added: Tests for both `--mode crawl` and `--mode recrawl` options

---

### 3. Search Commands (~2 tests)

**Unit Tests (Click CliRunner + mocks):**
- `test_search_valid` - Search with valid query and collection
- `test_search_with_threshold` - Search with similarity threshold filter

---

### 4. Document Commands (~2 tests)

**Unit Tests (Click CliRunner + mocks):**
- `test_document_delete_valid` - Delete document with ID
- `test_document_get_valid` - Get document content

---

## Integration Tests (~3 tests)

**Real database, real CLI invocation:**
- `test_end_to_end_ingest_and_search` - Create collection → ingest text → search
- `test_collection_lifecycle` - Create → list → info → delete
- `test_ingest_url_recrawl_workflow` - Ingest URL → recrawl same URL → verify old docs deleted

---

## Implementation Notes

**Click CliRunner Setup:**
```python
from click.testing import CliRunner
from src.cli import main

def test_collection_create_valid(mocker):
    # Mock database components
    mock_db = mocker.patch("src.cli.get_database")
    mock_mgr = mocker.patch("src.cli.get_collection_manager")

    runner = CliRunner()
    result = runner.invoke(main, ["collection", "create", "test-col", "--description", "Test"])

    assert result.exit_code == 0
    assert "Created collection" in result.output
```

**Mocked Components:**
- `get_database()`
- `get_collection_manager()`
- `get_document_store()`
- `get_embedding_generator()`
- `get_similarity_search()`
- `analyze_website()`
- `WebCrawler` (for URL crawling tests)

---

## Test Organization

**File**: `tests/unit/cli/test_cli_commands.py`

**Fixtures:**
- `cli_runner`: CliRunner instance
- `mock_components`: Mocked database/embedding/search components
- `mock_collection`: Sample collection data

---

## Coverage Targets

| Component | Current | Target | Notes |
|-----------|---------|--------|-------|
| Collection commands | 0% | 90% | Now includes schema command |
| Ingest commands | 0% | 85% | Merged ingest_url/recrawl |
| Search commands | 0% | 80% | Basic coverage |
| Overall CLI | 0% | >80% | ~16-20 tests needed |

---

## Next Steps

1. Create `tests/unit/cli/` directory structure
2. Implement ~20 unit tests with Click CliRunner
3. Implement ~3 integration tests with real database
4. Run full test suite and verify >80% coverage
5. Update CI/CD to run CLI tests
