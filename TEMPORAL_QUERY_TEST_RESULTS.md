# Temporal Query Testing - LLM Comparison
**Date:** October 28, 2025
**Purpose:** Test Graphiti temporal edge creation with different LLMs

---

## Test Setup

### Collection Configuration
- **Collection name:** `test-docs`
- **Description:** "Test collection for project documentation"
- **Domain:** "software-engineering"
- **Domain scope:** "RAG Memory project documentation and guides"
- **Metadata schema:** `{"project": "string", "status": "string"}`

### Documents Ingested (In Order)

1. **api-reference.md** (existing)
2. **deployment-guide.md** (existing)
3. **design-document.md** (existing)
4. **troubleshooting-guide.md** (existing - v1 with JWT)
5. **troubleshooting-guide-v2.md** (existing - v2 with OAuth as "legacy")
6. **authentication-policy-2025.md** (NEW - explicit JWT deprecation)

### Ingestion Commands Used

```bash
# Initial directory ingestion (files 1-5)
rag ingest directory /Users/timkitchens/projects/ai-projects/rag-memory/test-data/project-docs --collection test-docs --recursive

# Additional explicit deprecation document (file 6)
rag ingest file /Users/timkitchens/projects/ai-projects/rag-memory/test-data/project-docs/authentication-policy-2025.md --collection test-docs
```

---

## Test Results - Baseline (Default LLM)

### Current Graphiti LLM Configuration
- **Model:** (Check with: `echo $GRAPHITI_MODEL` or default from Graphiti)
- **Small Model:** (Check with: `echo $GRAPHITI_SMALL_MODEL` or default from Graphiti)

### Entity Extraction Results
**Neo4j Query:**
```cypher
MATCH (e:Entity)
RETURN e.name, e.name_embedding IS NOT NULL AS has_embedding
LIMIT 10
```

**Result:** 10 entities extracted including:
- GET /individual
- POST /individual
- DELETE /individual
- Bearer token
- Authentication
- User Management
- (others not captured in detail)

### Temporal Edge Creation - Key Findings

#### Total Temporal Edges Created
**Neo4j Query:**
```cypher
MATCH ()-[r]->()
WHERE r.invalid_at IS NOT NULL
RETURN count(r)
```

**Result:** 39 temporal edges with `invalid_at` populated

#### Authentication-Related Temporal Edges
**Neo4j Query:**
```cypher
MATCH (source)-[r]->(target)
WHERE r.invalid_at IS NOT NULL
  AND (r.fact CONTAINS 'authentication' OR r.fact CONTAINS 'JWT' OR r.fact CONTAINS 'OAuth')
RETURN
  source.name as from_entity,
  r.name as relationship_type,
  target.name as to_entity,
  r.fact as fact_text,
  r.valid_at as valid_from,
  r.invalid_at as invalidated_on
ORDER BY r.invalid_at DESC
```

**Result:** 6 authentication temporal edges created:

| From Entity | Relationship | To Entity | Fact | Valid From | Invalid At |
|------------|--------------|-----------|------|------------|------------|
| JWT token expiration settings | WILL_BE_REMOVED_IN | version 3.0 | JWT Authentication support will be removed in version 3.0. | 2025-10-28T18:51:43Z | 2025-12-31T00:00:00Z |
| Authentication | SECTION_RECOMMENDS_CHECKING | OAuth 2.0 token validation | The Authentication Failures section recommends checking OAuth 2.0 token validation. | 2025-10-28T18:15:40Z | 2025-10-28T18:51:43Z |
| Authentication | SECTION_RECOMMENDS_CHECKING | JWT token expiration settings | The Authentication Failures section suggests checking JWT token expiration settings (legacy). | 2025-10-28T18:15:40Z | 2025-10-28T18:51:43Z |
| Authentication | SECTION_RECOMMENDS_REVIEWING | log aggregation | The Authentication Failures section advises reviewing authentication service logs. | 2025-10-28T18:15:40Z | 2025-10-28T18:51:43Z |
| User Management Service v2.1.0 | SECTION_REPORTS_ERROR_CODE | 401 Unauthorized | The guide lists 401 Unauthorized as an error code meaning invalid or expired token and ties it to the OAuth flow. | 2025-10-28T18:15:40Z | 2025-10-28T18:51:43Z |
| 401 Unauthorized | ERROR_CODE_LINKS_TO_CONCEPT | OAuth flow | The 401 Unauthorized error is linked to problems in the OAuth flow (invalid or expired token). | 2025-10-28T18:15:40Z | 2025-10-28T18:51:43Z |

**Key Observation:**
- Temporal edges only created AFTER ingesting authentication-policy-2025.md
- troubleshooting-guide.md (v1) → troubleshooting-guide-v2.md (v2) alone did NOT create temporal edges
- Explicit contradiction language required: "deprecated", "no longer accepted", "will be removed"

---

## CLI Query Tests

### Test 1: Relationship Query (Baseline for Comparison)

**Command:**
```bash
rag graph query-relationships "What REST API endpoints exist and how do they relate?" --limit 5 --threshold 0.01
```

**Result:**
```
Found 4 relationship(s):

1. DOCUMENT_DESCRIBES
   The REST API Reference Documentation describes the User Management Service v2.1.0.

2. ENDPOINT_ACCEPTS_PARAMETER
   GET /api/v2/users accepts the order parameter.

3. USES_COMMUNICATION_TOOL
   The proposed architecture includes an API Gateway

4. ENDPOINT_ACCEPTS_PARAMETER
   GET /api/v2/users accepts the sort parameter.
```

**Threshold Behavior:**
- Default threshold (0.35): 0-1 results
- Threshold 0.1: 1-2 results
- Threshold 0.01: 4 results (shown above)

**Interpretation:** Cross-encoder reranker scores are very low for relationship queries. Even obviously relevant relationships score < 0.1.

---

### Test 2: Temporal Query - General Evolution

**Command:**
```bash
rag graph query-temporal "How has authentication changed?" --limit 10
```

**Result:**
```
Found 2 timeline item(s):

✅ 1. DEPRECATES
   The Authentication Policy Update (October 28, 2025) deprecates JWT Authentication.
   Valid from: 2025-10-28T18:51:43.614455+00:00
   Status: current

✅ 2. AUTHENTICATION_VIA_HEADER
   Bearer token authentication is provided via the Authorization header.
   Valid from: None
   Status: current
```

**Threshold:** Default (0.35) - worked fine, no adjustment needed

---

### Test 3: Temporal Query - Specific Deprecations

**Command:**
```bash
rag graph query-temporal "What authentication methods have been deprecated or removed?" --limit 10
```

**Result:**
```
Found 2 timeline item(s):

⏰ 1. WILL_BE_REMOVED_IN
   JWT Authentication support will be removed in version 3.0.
   Valid from: 2025-10-28T18:51:43.614455+00:00
   Valid until: 2025-12-31T00:00:00+00:00
   Status: superseded

✅ 2. DEPRECATES
   The Authentication Policy Update (October 28, 2025) deprecates JWT Authentication.
   Valid from: 2025-10-28T18:51:43.614455+00:00
   Status: current
```

**Threshold:** Default (0.35) - worked fine

**Key Detail:** Query successfully distinguished between "superseded" (JWT removal deadline Dec 31) vs "current" (JWT deprecation now)

---

### Test 4: Temporal Query - Troubleshooting Steps

**Command:**
```bash
rag graph query-temporal "What troubleshooting steps for authentication are no longer valid?" --limit 10
```

**Result:**
```
Found 1 timeline item(s):

✅ 1. DEPRECATES
   The Authentication Policy Update (October 28, 2025) deprecates JWT Authentication.
   Valid from: 2025-10-28T18:51:43.614455+00:00
   Status: current
```

**Threshold:** Default (0.35) - worked fine

---

## Key Findings Summary

### What Worked ✅
1. **Temporal edge creation** - When documents contain explicit contradiction language
2. **Temporal queries** - Default threshold (0.35) returns relevant results
3. **Status tracking** - "current" vs "superseded" correctly differentiated
4. **Date-based invalidation** - Captured future deadline (Dec 31, 2025) from document

### What Didn't Work ❌
1. **Subtle contradiction detection** - v1 "use JWT" → v2 "use OAuth (JWT is legacy)" did NOT create temporal edges
2. **Relationship query thresholds** - Required threshold < 0.1 to get any results
3. **Implicit timeline inference** - Graphiti didn't infer that v2 supersedes v1 just from file sequence

### Critical Success Factors
For temporal edges to be created, documents MUST contain:
- Explicit words: "deprecated", "no longer", "removed", "replaced by", "will be removed"
- Clear contradiction statements: "X is officially deprecated", "Y is ONLY supported"
- Temporal markers: dates, versions, timelines

---

## Test Replication Steps

### 1. Delete Collection
```bash
rag collection delete test-docs --yes
```

### 2. Reconfigure Graphiti LLM
Edit `config/config.dev.yaml` or set environment variables:
```yaml
server:
  graphiti_model: "gpt-4o"  # or "o1-mini", "claude-3-5-sonnet", etc.
  graphiti_small_model: "gpt-4o-mini"  # or smaller variant
```

Or:
```bash
export GRAPHITI_MODEL="gpt-4o"
export GRAPHITI_SMALL_MODEL="gpt-4o-mini"
```

### 3. Recreate Collection
```bash
rag collection create test-docs \
  --description "Test collection for project documentation" \
  --domain "software-engineering" \
  --domain-scope "RAG Memory project documentation and guides"

rag collection update-metadata test-docs --add-fields '{"project": "string", "status": "string"}'
```

### 4. Ingest Documents (Same Order)
```bash
# Ingest initial 5 docs
rag ingest directory /Users/timkitchens/projects/ai-projects/rag-memory/test-data/project-docs \
  --collection test-docs --recursive

# Wait for completion, then ingest explicit deprecation doc
rag ingest file /Users/timkitchens/projects/ai-projects/rag-memory/test-data/project-docs/authentication-policy-2025.md \
  --collection test-docs
```

### 5. Run Verification Queries

**Check entity count:**
```cypher
MATCH (e:Entity) RETURN count(e)
```

**Check temporal edge count:**
```cypher
MATCH ()-[r]->() WHERE r.invalid_at IS NOT NULL RETURN count(r)
```

**Check authentication temporal edges:**
```cypher
MATCH (source)-[r]->(target)
WHERE r.invalid_at IS NOT NULL
  AND (r.fact CONTAINS 'authentication' OR r.fact CONTAINS 'JWT' OR r.fact CONTAINS 'OAuth')
RETURN
  source.name as from_entity,
  r.name as relationship_type,
  target.name as to_entity,
  r.fact as fact_text,
  r.valid_at as valid_from,
  r.invalid_at as invalidated_on
ORDER BY r.invalid_at DESC
```

### 6. Run CLI Queries (Exact Same Commands)

```bash
# Test 1: Relationship query
rag graph query-relationships "What REST API endpoints exist and how do they relate?" --limit 5 --threshold 0.01

# Test 2: Temporal - general evolution
rag graph query-temporal "How has authentication changed?" --limit 10

# Test 3: Temporal - specific deprecations
rag graph query-temporal "What authentication methods have been deprecated or removed?" --limit 10

# Test 4: Temporal - troubleshooting steps
rag graph query-temporal "What troubleshooting steps for authentication are no longer valid?" --limit 10
```

---

## Comparison Metrics

### Quantitative Metrics
- [ ] Total entities extracted: ____
- [ ] Total temporal edges created: ____
- [ ] Authentication temporal edges: ____
- [ ] Relationship query results (threshold 0.01): ____
- [ ] Temporal query 1 results: ____
- [ ] Temporal query 2 results: ____
- [ ] Temporal query 3 results: ____

### Qualitative Observations
- [ ] Quality of relationship names extracted
- [ ] Accuracy of temporal edge detection
- [ ] Relevance of query results
- [ ] Difference in "fact" text quality
- [ ] Cross-encoder reranker threshold behavior

### Performance Metrics
- [ ] Time to ingest directory (5 docs)
- [ ] Time to ingest single file
- [ ] Query response times

---

## Notes for Next Test Run

**Current LLM Configuration:**
- Model: ________________
- Small Model: ________________

**Alternative LLM to Test:**
- Model: ________________
- Small Model: ________________

**Hypothesis:**
Will a different LLM (e.g., o1-mini, claude-3-5-sonnet) detect contradictions more reliably or extract better relationship facts?

---

## Appendix: Document Contents Summary

### troubleshooting-guide.md (v1)
- Authentication solution: "Check JWT token expiration settings"
- No mention of OAuth
- Problem/Solution format

### troubleshooting-guide-v2.md (v2)
- Header: "UPDATED VERSION with new OAuth solutions"
- Authentication solution: "Check OAuth 2.0 token validation" (marked NEW)
- JWT solution: "Check JWT token expiration settings (legacy)" (marked as legacy)
- Added: pgbouncer, SSL/TLS, Redis caching, read replicas
- Added: 503 error code

### authentication-policy-2025.md (Explicit Deprecation)
- Title: "Authentication Policy Update - October 2025"
- "BREAKING CHANGE: JWT Authentication Deprecated"
- "JWT is officially deprecated"
- "OAuth 2.0 is now the ONLY supported authentication method"
- "JWT tokens are no longer accepted"
- "JWT authentication support will be completely removed in version 3.0"
- Migration deadline: December 2025

**Key Difference:** Only the explicit deprecation document triggered temporal edge creation.
