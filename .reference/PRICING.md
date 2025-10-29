# RAG Memory - OpenAI API Pricing

## Scope of This Pricing Guide

**This pricing covers API costs for a completely local deployment:**
- PostgreSQL + pgvector (local Docker container)
- Neo4j (local Docker container)
- MCP Server (local Docker container)
- All operations executed on your machine

**What's NOT included here:**
- Cloud hosting costs (Supabase, Neo4j Aura, Fly.io)
- Database storage costs
- Compute/bandwidth costs
- These vary by vendor and provisioning choices
- See `.reference/CLOUD_DEPLOYMENT.md` for cloud cost estimates

**Bottom line:** For local deployment, your ONLY costs are OpenAI API calls documented below.

---

## Current Pricing (2025)

### Embeddings (Always Required)
**Model:** text-embedding-3-small
**Price:** $0.02 per 1 million tokens (~$0.000013 per 500-word document)

### Knowledge Graph Entity Extraction (Always Required)

**IMPORTANT:** RAG Memory uses a unified ingestion architecture. Every document ingested goes to **BOTH** the vector store (RAG) AND the knowledge graph (Graphiti). There is no option to disable graph ingestion.

**Graphiti Models (Configurable):**

| Model | Context Window | Cost (Input) | Cost (Output) | Total Cost/1M* |
|-------|----------------|--------------|---------------|----------------|
| **GPT-4.1 Mini** | 1M tokens (~2,400 pages) | $0.40/1M | $1.60/1M | **$0.80/1M** |
| **GPT-5 Mini (Recommended)** | 272K tokens (~650 pages) | $0.25/1M | $2.00/1M | **$0.75/1M** |
| **GPT-4o Mini** | 128K tokens (~300 pages) | $0.15/1M | $0.60/1M | **$0.30/1M** |

*Assuming 1:0.25 input:output ratio for entity extraction

**Current Default (as of this writing):** GPT-4.1 Mini
**Recommended:** GPT-5 Mini (see "Model Selection Guide" below)

**Approximate cost per document:** ~$0.01 (varies by document complexity and entity density)

---

## Key Points

1. **All ingestion costs include BOTH embeddings AND graph extraction** - No way to disable graph
2. **Knowledge Graph is mandatory** - Every document is processed by Graphiti for entity extraction
3. **One-time ingestion cost** - You only pay when adding/updating documents
4. **Free queries** - Searching (RAG and Graph) is done locally (no API calls)
5. **No ongoing costs** - Once documents are processed, there's no recurring API cost
6. **Update costs** - Only pay to re-process when documents change
7. **Model configuration** - Graphiti models are configurable (GRAPHITI_MODEL, GRAPHITI_SMALL_MODEL)

---

## Model Selection Guide

### Why GPT-5 Mini is Recommended (Despite Higher Per-Token Cost)

**GPT-5 Mini advantages:**
- ✅ Better quality entity extraction
- ✅ Fewer hallucinations (critical for knowledge graphs)
- ✅ **90% prompt caching discount** (vs 75% for 4.1 Mini)
- ✅ Larger context than 4o Mini (272K vs 128K)
- ✅ Better balance of cost and performance

**Context Window Matters:**
- Documents are ingested **whole** (not pre-chunked)
- If document exceeds model context, Graphiti chunks it
- **Risk:** Chunking can lose cross-chunk entity relationships and co-references
- **Solution:** Choose model with context window matching your document sizes

### Recommendation by Document Size:

**< 128K tokens (~300 pages):**
- Use **GPT-4o Mini** (cheapest: $0.30/1M tokens)
- Works well for short documents
- Proven with Graphiti/Zep integration

**128K-272K tokens (~300-650 pages):**
- Use **GPT-5 Mini** (best quality: $0.75/1M tokens)
- Better extraction quality
- Fewer hallucinations
- 90% prompt caching saves cost on similar documents

**> 272K tokens (~650+ pages):**
- Use **GPT-4.1 Mini** (only option: $0.80/1M tokens)
- Only model with 1M token context window
- Handles very large documents without chunking

### Model Configuration

**Environment variables:**
```bash
export GRAPHITI_MODEL="gpt-5-mini"         # Primary extraction model
export GRAPHITI_SMALL_MODEL="gpt-5-mini"   # Small task model
```

**Or in config.yaml:**
```yaml
server:
  graphiti_model: "gpt-5-mini"        # Recommended
  graphiti_small_model: "gpt-5-mini"  # Recommended
```

**Default (if not configured):** GPT-4.1 Mini

---

## Realistic Usage Scenarios

### Understanding Total Ingestion Cost

**Every document ingested incurs:**
1. Embedding cost (~$0.000013 per 500-word doc)
2. Graphiti extraction cost (~$0.01 per doc)

**Total cost per document:** ~$0.010013 (dominated by Graphiti)

### Small Knowledge Base (1,000 documents)
- Embeddings: $0.013
- Graphiti extraction: ~$10.00
- **Total one-time cost: ~$10.01**
- Per-query cost: $0 (free, runs locally)

### Medium Knowledge Base (10,000 documents)
- Embeddings: $0.13
- Graphiti extraction: ~$100.00
- **Total one-time cost: ~$100.13**
- Per-query cost: $0 (free, runs locally)

### Large Knowledge Base (100,000 documents)
- Embeddings: $1.30
- Graphiti extraction: ~$1,000.00
- **Total one-time cost: ~$1,001.30**
- Per-query cost: $0 (free, runs locally)

### Documentation Site Crawl (500 web pages)
- Embeddings: $0.03
- Graphiti extraction: ~$5.00
- **Total one-time cost: ~$5.03**
- Updates/recrawls: Same cost each time

---

## Example Monthly Budgets

### Typical Developer/Small Team
- Initial corpus: 5,000 documents = $50.07
- Weekly updates: 100 docs × 4 weeks = $4.00/month
- **Total first month: ~$54**
- **Ongoing: ~$4/month**

### Active Documentation Site
- Initial crawl: 2,000 pages = $20.03
- Daily updates: 50 pages × 30 days = $15.01/month
- **Total first month: ~$35**
- **Ongoing: ~$15/month**

### Enterprise Knowledge Base
- Initial corpus: 50,000 documents = $500.65
- Daily updates: 500 docs × 30 days = $150.20/month
- **Total first month: ~$650**
- **Ongoing: ~$150/month**

**Note:** These estimates assume GPT-4.1 Mini (default). Costs may vary based on:
- Document complexity (more entities = higher cost)
- Model choice (GPT-5 Mini recommended, GPT-4o Mini cheapest)
- Document size (larger docs = more tokens)

---

## Cost Breakdown by Operation

### Document Ingestion (Charged - OpenAI API Calls)

**EVERY ingestion method triggers BOTH:**
1. **Embedding generation** (text-embedding-3-small)
2. **Knowledge Graph extraction** (Graphiti with configured model)

**Ingestion operations:**
- `rag ingest text` - Charged for embeddings + Graphiti extraction
- `rag ingest file` - Charged for embeddings + Graphiti extraction
- `rag ingest directory` - Charged for embeddings + Graphiti extraction per file
- `rag ingest url` - Charged for embeddings + Graphiti extraction per page
- `rag document update` - Charged to re-embed + re-extract updated content
- `rag recrawl` - Charged to re-embed + re-extract all re-crawled pages

**MCP tools (same costs):**
- `ingest_text` - Charged for embeddings + Graphiti extraction
- `ingest_file` - Charged for embeddings + Graphiti extraction
- `ingest_directory` - Charged for embeddings + Graphiti extraction per file
- `ingest_url` - Charged for embeddings + Graphiti extraction per page
- `update_document` - Charged to re-embed + re-extract updated content

**No option to disable Knowledge Graph** - All ingestion goes to both RAG and Graph stores.

### Search Operations (Free - No API Calls)

**Vector search (RAG):**
- `rag search` - No API calls, uses local PostgreSQL pgvector
- MCP tool: `search_documents` - No API calls

**Knowledge Graph queries:**
- `rag graph query-relationships` - No API calls, queries local Neo4j
- `rag graph query-temporal` - No API calls, queries local Neo4j
- MCP tool: `query_relationships` - No API calls
- MCP tool: `query_temporal` - No API calls

**Document listing/viewing:**
- `rag document list` - No API calls, database query only
- `rag document view` - No API calls, database query only
- `rag collection list` - No API calls, database query only
- `rag collection info` - No API calls, database query only
- MCP tools: `list_documents`, `get_document_by_id`, `list_collections`, `get_collection_info` - No API calls

### Management Operations (Free - No API Calls)

- `rag document delete` - No API calls (removes from PostgreSQL + Neo4j)
- `rag collection delete` - No API calls (removes from PostgreSQL + Neo4j)
- `rag status` - No API calls (health checks only)
- `rag init` - No API calls (schema initialization only)
- MCP tools: `delete_document`, `delete_collection`, `update_collection_description` - No API calls

### Analysis Operations (Free - No API Calls)

- `rag analyze website` - No API calls, sitemap parsing only
- MCP tool: `analyze_website` - No API calls

---

## Token Estimation

### Approximate token counts:
- **1 token ≈ 0.75 words** (English)
- **1 token ≈ 4 characters** (English)
- 100 words ≈ 133 tokens
- 500 words ≈ 667 tokens
- 1,000 words ≈ 1,333 tokens
- 2,000 words ≈ 2,667 tokens

### Document type estimates (embedding cost only):
- Short email: 200 words = ~267 tokens = $0.0000053
- Blog post: 1,000 words = ~1,333 tokens = $0.000027
- Technical doc: 2,000 words = ~2,667 tokens = $0.000053
- Long article: 5,000 words = ~6,667 tokens = $0.00013
- Book chapter: 10,000 words = ~13,333 tokens = $0.00027

**Add ~$0.01 per document for Graphiti extraction** (varies by complexity)

---

## Cost Comparison

### text-embedding-3-small vs alternatives:

| Model | Price per 1M tokens | Relative Cost |
|-------|---------------------|---------------|
| **text-embedding-3-small** | **$0.02** | **1x (baseline)** |
| text-embedding-3-large | $0.13 | 6.5x more expensive |
| text-embedding-ada-002 (legacy) | $0.10 | 5x more expensive |
| Cohere Embed v3 | $0.10 | 5x more expensive |

text-embedding-3-small offers the best value for RAG applications.

### Graphiti Model Comparison:

| Model | Total Cost/1M tokens* | Context Window | Best For |
|-------|----------------------|----------------|----------|
| **GPT-4o Mini** | **$0.30** | 128K | Small docs, cost-sensitive |
| **GPT-5 Mini (Recommended)** | **$0.75** | 272K | Best quality, medium-large docs |
| **GPT-4.1 Mini (Default)** | **$0.80** | 1M | Very large documents |

*Assuming 1:0.25 input:output ratio

---

## Monitoring Costs

### How to estimate your actual costs:

1. **Before ingesting:**
   ```bash
   # Count words in your documents
   wc -w your_documents/*.txt

   # Multiply words by 1.33 to get approximate tokens
   # Embedding cost: tokens × $0.00000002
   # Graphiti cost: ~$0.01 per document
   ```

2. **Track your usage:**
   - OpenAI dashboard shows token usage: https://platform.openai.com/usage
   - Check monthly spend: https://platform.openai.com/account/billing/overview
   - Separate line items for embeddings and completions (Graphiti)

3. **Estimate before crawling:**
   ```bash
   # Use analyze command to see page count
   rag analyze https://docs.example.com

   # Estimate:
   # Embeddings: pages × 2000 words × 1.33 × $0.00000002
   # Graphiti: pages × $0.01
   # Total: embeddings + graphiti
   ```

---

## Budget Guidelines

### Free tier experimentation:
- OpenAI free tier: $5 credit (expires after 3 months)
- Can embed: 250 million tokens (embeddings only)
- Can extract: ~500 documents with Graphiti (at $0.01/doc)
- Enough for testing and small projects

### Production budgets:
- **Small team (<10 people):** $10-50/month
- **Medium team (10-50 people):** $50-200/month
- **Large organization (50+ people):** $200-1000/month
- **Enterprise with daily updates:** $1000-5000/month

Most users will spend $10-100/month depending on corpus size and update frequency.

---

## Cost Optimization Tips

1. **Choose the right model** - GPT-5 Mini recommended for most use cases
2. **Avoid duplicate ingestion** - Use `rag document list` to check before re-ingesting
3. **Use `rag recrawl` instead of delete + ingest** - Same cost, but cleaner tracking
4. **Filter files before ingesting** - Use `--extensions` to skip binary files
5. **Analyze before crawling** - Use `rag analyze` to understand site size
6. **Update only changed documents** - Use `rag document update` instead of delete + ingest
7. **Batch similar documents** - Prompt caching (90% discount) benefits similar content

---

## Frequently Asked Questions

**Q: Do I pay for every search query?**
A: No! Searches are FREE (both RAG search and graph queries). You only pay during document ingestion. Once documents are embedded and extracted, all queries are local to PostgreSQL/Neo4j.

**Q: What if I update a document?**
A: You only pay to re-process the updated document (embeddings + Graphiti extraction). Other documents are unaffected.

**Q: Can I disable the Knowledge Graph to save money?**
A: No. RAG Memory uses a unified ingestion architecture where every document goes to both the vector store (RAG) AND the knowledge graph (Graphiti). There is no option to disable graph ingestion. This is an "all-or-nothing" design decision.

**Q: Can I use a free/local embedding model?**
A: Currently RAG Memory only supports OpenAI embeddings. Self-hosted models (like Sentence Transformers) could be added in the future.

**Q: What models does Graphiti use and can I change them?**
A: As of this writing, Graphiti defaults to GPT-4.1 Mini. You can configure different models via:
- Environment variables: `GRAPHITI_MODEL` and `GRAPHITI_SMALL_MODEL`
- Config file: `graphiti_model` and `graphiti_small_model` settings
- Supported: GPT-4o Mini, GPT-4.1 Mini, GPT-5 Mini
- Recommended: GPT-5 Mini (better quality, fewer hallucinations, 90% caching)

**Q: How much does Graphiti cost compared to embeddings?**
A: Graphiti entity extraction costs ~$0.01 per document, which is approximately **770x more expensive** than embeddings alone (~$0.000013 per document). However, it enables powerful relationship and temporal queries that RAG alone cannot provide.

**Q: Does the MCP server cost more than CLI?**
A: No. Both use the same embedding API and Graphiti extraction. Costs are identical.

**Q: What happens if I hit rate limits?**
A: OpenAI has rate limits (default: 3,000 RPM for text-embedding-3-small, varies for completion models). RAG Memory processes documents sequentially, so you're unlikely to hit limits for typical use.

**Q: Can I switch to a different model later?**
A: Yes for Graphiti (just update config and re-ingest). For embeddings, you'd need to re-embed all documents with the new model, incurring the full ingestion cost again.

**Q: Does this pricing include cloud hosting costs?**
A: No. This pricing ONLY covers OpenAI API calls for a local deployment (all services running in Docker on your machine). Cloud hosting costs (Supabase, Neo4j Aura, Fly.io) are separate and vary by vendor and provisioning. See `.reference/CLOUD_DEPLOYMENT.md` for cloud estimates.

**Q: Why is GPT-5 Mini recommended if it's more expensive per token?**
A: GPT-5 Mini has better quality entity extraction, fewer hallucinations (critical for knowledge graphs), and 90% prompt caching discount (vs 75% for others). The caching benefit and quality improvement outweigh the higher per-token cost for most use cases. Plus it has a larger context window (272K vs 128K for 4o Mini) which reduces the risk of document chunking.

---

## Further Information

- **OpenAI Pricing Page:** https://openai.com/api/pricing/
- **OpenAI Usage Dashboard:** https://platform.openai.com/usage
- **Token Calculator:** https://platform.openai.com/tokenizer
- **Rate Limits:** https://platform.openai.com/docs/guides/rate-limits
- **Cloud Deployment Costs:** `.reference/CLOUD_DEPLOYMENT.md`
- **Knowledge Graph Details:** `.reference/KNOWLEDGE_GRAPH.md`

---

**Last Updated:** 2025-10-28
**Status:** Reflects unified ingestion architecture (mandatory Knowledge Graph)
**Version:** 0.13.0
