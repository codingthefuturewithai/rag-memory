# Why Build RAG Memory vs Using Zep Cloud?

**Date:** October 25, 2025
**Decision:** Build and maintain custom RAG Memory solution
**Status:** Validated through implementation and testing

## Executive Summary

After careful analysis, we determined that our custom RAG Memory solution (pgvector + Graphiti OSS) is superior to Zep Cloud for our specific use cases. Our solution costs ~$50-100/month in API costs versus $499+/month for Zep Cloud, while providing better performance for static documentation search (0.73-0.95 similarity scores) and the flexibility to optimize for our exact needs.

## The Comparison

### Our Solution: RAG Memory
- **Architecture:** PostgreSQL with pgvector + Neo4j with Graphiti OSS
- **Cost:** ~$50-100/month (OpenAI API costs only)
- **Control:** Full ownership of code and data
- **Performance:** 0.73-0.95 similarity scores (validated)

### Alternative: Zep Cloud
- **Architecture:** Hosted Graphiti with integrated vector/graph storage
- **Cost:** $499+/month for teams
- **Control:** Vendor-managed service
- **Performance:** Unknown for our use cases

## Key Use Cases Analysis

### 1. Static Documentation Search (Primary Use Case)

**Our Need:** Search API docs, design documents, deployment guides

**RAG Memory Advantage:**
- Optimized chunking strategy (1000 chars with 200 overlap)
- Proper vector normalization achieving 0.73+ similarity
- Custom metadata schemas per collection
- Fine-tuned for technical documentation

**Zep Cloud Limitation:**
- Designed for conversational memory, not static docs
- Episodes/facts model doesn't fit documentation structure
- Would need to force documentation into conversation format

**Verdict:** RAG Memory is purpose-built for this; Zep would be a square peg in round hole

### 2. Strategic Conversation Capture (Secondary Use Case)

**Our Need:** Deliberately capture key discussions from AI sessions, NOT continuous logging

**RAG Memory Advantage:**
- Conscious decision about what to capture
- Works across any AI assistant (ChatGPT, Claude, Cursor)
- Project-based partitioning via collections

**Zep Cloud Limitation:**
- Designed for automatic session recording
- Single-application memory model
- Continuous capture creates noise for strategic knowledge

**Verdict:** Our deliberate capture model fits better than Zep's automatic recording

### 3. Multi-Domain Knowledge Management

**Our Need:** ~12 different project domains (engineering, finance, planning)

**RAG Memory Advantage:**
- Collection-based partitioning with metadata schemas
- group_id creates isolated subgraphs per domain
- Can query within or across domains as needed

**Zep Cloud Limitation:**
- Single graph for all knowledge
- Would mix unrelated domains
- No clear partitioning strategy

**Verdict:** Our collection → group_id mapping provides superior domain isolation

## Cost Analysis

### RAG Memory (Current)
- OpenAI API: ~$50-100/month
- Infrastructure: Local Docker or Fly.io (~$20/month)
- **Total:** $70-120/month

### Zep Cloud
- Subscription: $499+/month (team tier)
- OpenAI API: Still required (~$50-100/month)
- **Total:** $549-599/month

**Cost Difference:** 5-8x more expensive for Zep Cloud

## Technical Performance Comparison

### Vector Search Performance

**RAG Memory (Validated):**
- 0.73-0.95 similarity for relevant content
- 0.07-0.15 for unrelated content
- Clear separation between relevant/irrelevant

**Zep Cloud (Theoretical):**
- Uses same embedding approach (cosine similarity)
- Adds BM25 hybrid search (may not help for technical docs)
- No evidence it would outperform our tuned solution

### Knowledge Graph Capabilities

**Both Use Graphiti:** Same underlying graph technology

**RAG Memory Advantages:**
- Direct control over entity extraction
- Custom community rebuilding (admin command)
- Can optimize prompts for technical content

**Zep Advantages:**
- Managed service (less maintenance)
- Automatic community detection (but computationally expensive)

## Why Zep Cloud Makes Sense (For Others)

Zep Cloud is excellent for:
1. **Conversational AI:** Chatbots, virtual assistants
2. **User-specific memory:** Each user has their own memory graph
3. **Real-time updates:** Facts changing constantly
4. **Session management:** Automatic conversation tracking

These are NOT our use cases.

## Why RAG Memory Makes Sense (For Us)

Our solution is optimal because:

1. **Static Content Focus:** Documentation doesn't change every message
2. **Deliberate Capture:** We choose what's worth remembering
3. **Cross-Platform:** Works with ANY AI assistant
4. **Domain Partitioning:** Clean separation of unrelated projects
5. **Cost Effective:** 5-8x cheaper than Zep Cloud
6. **Proven Performance:** 0.73+ similarity scores already validated
7. **Full Control:** Can optimize for our exact needs

## The Temporal Query Challenge

**Important Note:** Both solutions face the same challenge with temporal queries on static documentation.

When ingesting a document that says "Q2 2024 migration planned", both systems would:
- Store it with today's timestamp (when ingested)
- NOT automatically extract "Q2 2024" as the valid_at date
- Require custom logic to parse dates from content

Neither Zep nor RAG Memory solves this automatically. The temporal advantages of Graphiti work best for real-time events, not historical documentation.

## Decision Validation Points

### What Would Make Us Reconsider?

We would only switch to Zep Cloud if:
1. Our use case shifted to real-time conversational AI
2. We needed user-specific memory isolation
3. The cost dropped to <$100/month
4. They added specific features for static documentation

### What Confirms Our Decision?

1. ✅ Successfully achieving 0.73+ similarity scores
2. ✅ Collection-based partitioning working as designed
3. ✅ Graph isolation via group_id confirmed
4. ✅ Community rebuilding implemented as admin function
5. ✅ Cross-platform knowledge capture working

## Conclusion

**We are building the right tool for our needs.** Zep Cloud is building a different tool for different needs (conversational AI memory).

Our requirements:
- Static documentation search
- Strategic conversation capture
- Multi-domain knowledge management
- Cost-effective solution
- Full control over implementation

Zep Cloud would be overkill, more expensive, and potentially less performant for our specific use cases. The development time saved by using Zep would be negated by the time spent adapting it to work with static documentation.

## Future Considerations

### If We Need Conversational Memory Later

We could:
1. Add a "conversations" collection with appropriate schema
2. Implement session tracking in our existing system
3. Or run Zep alongside RAG Memory for that specific use case

### If Zep Evolves

We should revisit if Zep adds:
- Static documentation mode
- Collection-based partitioning
- Significantly lower pricing
- Export/migration tools

---

**Bottom Line:** We built RAG Memory because existing solutions solve different problems. Zep is great for conversational AI. We needed something for knowledge management. That's why we built our own.