# MCP Inspector Manual Test Payloads

These are the four manual test cases for validating the metadata schema feature in MCP Inspector.

## Test 1: Create Collection with Metadata Schema

**Tool:** `create_collection`

**Arguments (JSON):**
```json
{
  "name": "test_collection_manual",
  "description": "Test collection for manual MCP Inspector validation",
  "metadata_schema": {
    "custom": {
      "author": {
        "type": "string",
        "required": true
      },
      "version": {
        "type": "number"
      },
      "status": {
        "type": "string",
        "enum": ["draft", "published", "archived"]
      }
    },
    "system": ["file_type", "source_type", "ingested_at"]
  }
}
```

**Expected Response:**
- `created: true`
- `name: "test_collection_manual"`
- `description: "Test collection for manual MCP Inspector validation"`

---

## Test 2: Get Collection Metadata Schema

**Tool:** `get_collection_metadata_schema`

**Arguments (JSON):**
```json
{
  "collection_name": "test_collection_manual"
}
```

**Expected Response:**
- `collection_name: "test_collection_manual"`
- `custom_fields` object with `author`, `version`, `status`
- `system_fields` array with `file_type`, `source_type`, `ingested_at`
- Each custom field shows `type`, `required` (if specified), and `enum` values (if specified)

---

## Test 3: Ingest Text with Metadata

**Tool:** `ingest_text`

**Arguments (JSON):**
```json
{
  "content": "This is a test document about AI and machine learning. It covers neural networks, training models, and deployment strategies.",
  "collection_name": "test_collection_manual",
  "document_title": "AI Fundamentals Guide",
  "metadata": {
    "author": "John Smith",
    "version": 1.0,
    "status": "published"
  }
}
```

**Expected Response:**
- `source_document_id: <integer>`
- `chunk_count: <integer>` (should be 1 for this short document)
- `chunks_created: <integer>`
- `document_title: "AI Fundamentals Guide"`

---

## Test 4: Search Documents

**Tool:** `search_documents`

**Arguments (JSON):**
```json
{
  "query": "machine learning models",
  "collection_name": "test_collection_manual",
  "limit": 5
}
```

**Expected Response:**
- `results` array with at least 1 item
- Each result includes:
  - `chunk_id: <integer>`
  - `content: "..."` (matching text)
  - `similarity: <float>` (0.7-1.0 range for relevant matches)
  - `source_document_id: <integer>`
  - `metadata` object with `author`, `version`, `status` from Test 3

---

## How to Use in MCP Inspector

1. Open MCP Inspector browser window
2. For each test in order (1 → 2 → 3 → 4):
   - Select the tool name from the left panel dropdown
   - Paste the JSON from "Arguments (JSON)" into the Arguments field
   - Click "Call Tool"
   - Verify the response matches "Expected Response"

## Quick Reference (Copy-Paste Ready)

### Test 1 Arguments
```
{"name":"test_collection_manual","description":"Test collection for manual MCP Inspector validation","metadata_schema":{"custom":{"author":{"type":"string","required":true},"version":{"type":"number"},"status":{"type":"string","enum":["draft","published","archived"]}},"system":["file_type","source_type","ingested_at"]}}
```

### Test 2 Arguments
```
{"collection_name":"test_collection_manual"}
```

### Test 3 Arguments
```
{"content":"This is a test document about AI and machine learning. It covers neural networks, training models, and deployment strategies.","collection_name":"test_collection_manual","document_title":"AI Fundamentals Guide","metadata":{"author":"John Smith","version":1.0,"status":"published"}}
```

### Test 4 Arguments
```
{"query":"machine learning models","collection_name":"test_collection_manual","limit":5}
```
