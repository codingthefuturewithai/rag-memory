# RAG Memory - OpenAI API Pricing

## Current Pricing (2025)

**Model:** text-embedding-3-small
**Price:** $0.02 per 1 million tokens

## Key Points

1. **Extremely affordable** - Most users spend less than $1/month
2. **One-time embedding cost** - You only pay when ingesting documents
3. **Free queries** - Searching is done locally in PostgreSQL (no API calls)
4. **No ongoing costs** - Once documents are embedded, there's no recurring API cost
5. **Update costs** - Only pay to re-embed when documents change

## Realistic Usage Scenarios

### Small Knowledge Base (1,000 documents)
- Avg document size: ~500 words (750 tokens)
- Total tokens: 750,000
- **One-time cost: $0.015 (~2 cents)**
- Per-query cost: ~$0.000015 (essentially free)

### Medium Knowledge Base (10,000 documents)
- Avg document size: ~500 words (750 tokens)
- Total tokens: 7.5 million
- **One-time cost: $0.15 (15 cents)**
- Per-query cost: ~$0.000015 (essentially free)

### Large Knowledge Base (100,000 documents)
- Avg document size: ~500 words (750 tokens)
- Total tokens: 75 million
- **One-time cost: $1.50**
- Per-query cost: ~$0.000015 (essentially free)

### Documentation Site Crawl
- 500 web pages × 2,000 words avg (3,000 tokens)
- Total tokens: 1.5 million
- **One-time cost: $0.03 (3 cents)**
- Updates/recrawls: Same cost each time

## Example Monthly Budgets

### Typical Developer/Small Team
- Initial corpus: 5,000 documents = $0.08
- Weekly updates: 100 docs × 4 weeks = $0.03/month
- **Total: ~$0.11/month**

### Active Documentation Site
- Initial crawl: 2,000 pages = $0.12
- Daily updates: 50 pages × 30 days = $0.09/month
- **Total: ~$0.21/month**

### Enterprise Knowledge Base
- Initial corpus: 50,000 documents = $0.75
- Daily updates: 500 docs × 30 days = $0.30/month
- **Total: ~$1.05/month**

## Cost Breakdown by Operation

### Document Ingestion (Charged)
- `rag ingest text` - Charged per token
- `rag ingest file` - Charged per token in file
- `rag ingest directory` - Charged per token across all files
- `rag ingest url` - Charged per token on crawled pages
- `rag document update` - Charged to re-embed updated content
- `rag recrawl` - Charged to re-embed all re-crawled pages

### Search Operations (Free)
- `rag search` - No API calls, uses local PostgreSQL pgvector
- `rag document list` - No API calls, database query only
- `rag document view` - No API calls, database query only
- `rag collection list` - No API calls, database query only
- `rag collection info` - No API calls, database query only

### Management Operations (Free)
- `rag document delete` - No API calls
- `rag collection delete` - No API calls
- `rag status` - No API calls
- `rag init` - No API calls

## Token Estimation

### Approximate token counts:
- **1 token ≈ 0.75 words** (English)
- **1 token ≈ 4 characters** (English)
- 100 words ≈ 133 tokens
- 500 words ≈ 667 tokens
- 1,000 words ≈ 1,333 tokens
- 2,000 words ≈ 2,667 tokens

### Document type estimates:
- Short email: 200 words = ~267 tokens = $0.0000053
- Blog post: 1,000 words = ~1,333 tokens = $0.000027
- Technical doc: 2,000 words = ~2,667 tokens = $0.000053
- Long article: 5,000 words = ~6,667 tokens = $0.00013
- Book chapter: 10,000 words = ~13,333 tokens = $0.00027

## Cost Comparison

### text-embedding-3-small vs alternatives:

| Model | Price per 1M tokens | Relative Cost |
|-------|---------------------|---------------|
| **text-embedding-3-small** | **$0.02** | **1x (baseline)** |
| text-embedding-3-large | $0.13 | 6.5x more expensive |
| text-embedding-ada-002 (legacy) | $0.10 | 5x more expensive |
| Cohere Embed v3 | $0.10 | 5x more expensive |

text-embedding-3-small offers the best value for most RAG applications.

## Monitoring Costs

### How to estimate your actual costs:

1. **Before ingesting:**
   ```bash
   # Count words in your documents
   wc -w your_documents/*.txt

   # Multiply words by 1.33 to get approximate tokens
   # Multiply tokens by $0.00000002 to get cost
   ```

2. **Track your usage:**
   - OpenAI dashboard shows token usage: https://platform.openai.com/usage
   - Check monthly spend: https://platform.openai.com/account/billing/overview

3. **Estimate before crawling:**
   ```bash
   # Use analyze command to see page count
   rag analyze https://docs.example.com

   # Estimate: pages × 2000 words × 1.33 × $0.00000002
   ```

## Budget Guidelines

### Free tier experimentation:
- OpenAI free tier: $5 credit (expires after 3 months)
- Can embed: 250 million tokens = 187.5 million words = ~375,000 typical documents
- More than enough for testing and small projects

### Production budgets:
- **Small team (<10 people):** $1-5/month
- **Medium team (10-50 people):** $5-20/month
- **Large organization (50+ people):** $20-100/month
- **Enterprise with daily updates:** $100-500/month

Most users will be well under $10/month.

## Cost Optimization Tips

1. **Avoid duplicate ingestion** - Use `rag document list` to check before re-ingesting
2. **Use `rag recrawl` instead of delete + ingest** - Same cost, but cleaner tracking
3. **Filter files before ingesting** - Use `--extensions` to skip binary files
4. **Analyze before crawling** - Use `rag analyze` to understand site size
5. **Update only changed documents** - Use `rag document update` instead of delete + ingest
6. **Chunk strategically** - Larger chunks = fewer embeddings = lower cost (but may reduce search quality)

## Frequently Asked Questions

**Q: Do I pay for every search query?**
A: No! Searches use PostgreSQL's pgvector locally. Only document ingestion requires API calls.

**Q: What if I update a document?**
A: You only pay to re-embed the updated document. Other documents are unaffected.

**Q: Can I use a free/local embedding model?**
A: Currently RAG Memory only supports OpenAI. Self-hosted models (like Sentence Transformers) could be added in the future.

**Q: Does the MCP server cost more than CLI?**
A: No. Both use the same embedding API. Costs are identical.

**Q: What happens if I hit rate limits?**
A: OpenAI has rate limits (default: 3,000 RPM for text-embedding-3-small). RAG Memory processes documents sequentially, so you're unlikely to hit limits for typical use.

**Q: Can I switch to a different model later?**
A: Yes, but you'd need to re-embed all documents with the new model. This would incur the full ingestion cost again.

## Further Information

- **OpenAI Pricing Page:** https://openai.com/api/pricing/
- **OpenAI Usage Dashboard:** https://platform.openai.com/usage
- **Token Calculator:** https://platform.openai.com/tokenizer
- **Rate Limits:** https://platform.openai.com/docs/guides/rate-limits
