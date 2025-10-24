# CrossEncoder Search Results - Exact Output (Graphiti .search_() with COMBINED_HYBRID_SEARCH_CROSS_ENCODER)

**Captured:** 2025-10-23
**Strategy:** `await self.graphiti.search_(query, config=COMBINED_HYBRID_SEARCH_CROSS_ENCODER)` - Advanced search with cross-encoder reranking
**Code Location:** `src/unified/graph_store.py:352`

---

## Query 1: How does quantum computing relate to cryptography?

**Expected:** 0 results (quantum computing and cryptography NOT in graph)
**Actual:** 5 results (FALSE POSITIVES persist)

```
1. RECEIVED_FUNDING_FROM
   Anthropic has received significant funding from Google
   ID: 031f374b-cdfc-412d-9765-5cca4a78b5cb

2. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

3. FUNDED_BY
   Anthropic has been funded by Andreessen Horowitz (a16z)
   ID: e346c679-6ba3-4ffa-b9c2-4ec931e1639f

4. RECEIVED_FUNDING_FROM
   Anthropic has received significant funding from Amazon Web Services
   ID: 86f72a77-c283-4b82-bf1c-6e8d7a105d45

5. PARTNERS_WITH
   NVIDIA partners with Google Cloud to deliver AI computing capabilities
   ID: 81af61e1-c840-44c2-98d5-f82f3403f428
```

---

## Query 2: What is the history of blockchain and cryptocurrency?

**Expected:** 0 results (blockchain and cryptocurrency NOT in graph)
**Actual:** 5 results (FALSE POSITIVES persist)

```
1. PRODUCES
   NVIDIA produces the H100 GPU
   ID: 83f23ed6-1aef-4286-b65f-99657f61ecb0

2. DEVELOPS
   Anthropic developed the Claude language model
   ID: 45e3ac9d-bb3a-479b-ac81-e197de2f3543

3. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem
   and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

4. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

5. PROVIDES
   Hugging Face provides the transformers library
   ID: f9037590-9f09-4ffb-996a-4a5a4b61f35b
```

---

## Query 3: Explain how machine learning relates to artificial intelligence

**Expected:** 5 results (Both ML and AI ARE in graph)
**Actual:** 5 results (ALL RELEVANT)

```
1. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

2. USES
   Machine learning involves neural networks.
   ID: a91d1682-a498-46a1-97af-912cc664a049

3. ABOUT
   The document by User is about machine learning.
   ID: 5779513b-7ac8-4c40-8d62-ca829df0ce0f

4. ABOUT
   The document by User is about AI.
   ID: cdf2a75f-dfc9-4b38-86cf-44effe63c21f

5. INVOLVES
   Machine learning involves training models.
   ID: 493f7bbb-9a85-4db1-bcf2-64873d001c1d
```

---

## Query 4: How do neural networks relate to deep learning?

**Expected:** 5 results (Neural networks ARE in graph)
**Actual:** 5 results (MOSTLY RELEVANT - ML→NN but no deep learning found)

```
1. USES
   Machine learning involves neural networks.
   ID: a91d1682-a498-46a1-97af-912cc664a049

2. COVERS
   The document by User covers neural networks.
   ID: ffe7a657-7043-4242-9384-569ec2bddfe2

3. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

4. ABOUT
   The document by User is about machine learning.
   ID: 5779513b-7ac8-4c40-8d62-ca829df0ce0f

5. INVOLVES
   Machine learning involves training models.
   ID: 493f7bbb-9a85-4db1-bcf2-64873d001c1d
```

---

## Query 5: What is the connection between cloud computing and data storage?

**Expected:** Partial results (cloud services like Azure/AWS ARE in graph)
**Actual:** 5 results (MOSTLY RELEVANT - cloud partnerships found)

```
1. PARTNERS_WITH
   NVIDIA partners with Amazon Web Services (AWS) to deliver AI computing
   capabilities
   ID: 0b5ef9dd-73a7-4a15-8caf-b479aa49c095

2. PARTNERS_WITH
   NVIDIA partners with Google Cloud to deliver AI computing capabilities
   ID: 81af61e1-c840-44c2-98d5-f82f3403f428

3. INTEGRATES_TECHNOLOGY_INTO
   Microsoft integrates OpenAI's technology into its Azure cloud platform
   ID: 6345235d-e901-4f06-8f89-3eaaec51b3ab

4. PARTNERS_WITH
   NVIDIA partners with Microsoft Azure to deliver AI computing capabilities
   ID: f41b1492-877d-424a-b238-44b53406dcec

5. LED_BY
   Meta Platforms is led by Mark Zuckerberg
   ID: 5f403af7-dc62-46fd-ab96-ba398f11e7b0
```

---

## Query 6: How do APIs relate to web services?

**Expected:** 0 results (APIs and web services NOT in graph)
**Actual:** 5 results (FALSE POSITIVES persist)

```
1. PARTNERS_WITH
   NVIDIA partners with Microsoft Azure to deliver AI computing capabilities
   ID: f41b1492-877d-424a-b238-44b53406dcec

2. PARTNERS_WITH
   NVIDIA partners with Google Cloud to deliver AI computing capabilities
   ID: 81af61e1-c840-44c2-98d5-f82f3403f428

3. RECEIVED_FUNDING_FROM
   Anthropic has received significant funding from Amazon Web Services
   ID: 86f72a77-c283-4b82-bf1c-6e8d7a105d45

4. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

5. PARTNERED_WITH
   OpenAI maintains a strategic partnership with Microsoft
   ID: da66c356-b0ab-497d-9b7a-f4dae75cf4fa
```

---

## Query 7: Explain the relationship between DevOps and continuous integration

**Expected:** 0 results (DevOps and CI NOT in graph)
**Actual:** 5 results (FALSE POSITIVES persist)

```
1. COVERS
   The document by User covers deployment strategies.
   ID: 7530bc57-4c65-43b4-a65f-decab36996d9

2. DEVELOPS
   Anthropic developed the Claude language model
   ID: 45e3ac9d-bb3a-479b-ac81-e197de2f3543

3. PROVIDES
   Hugging Face provides the transformers library
   ID: f9037590-9f09-4ffb-996a-4a5a4b61f35b

4. COVERS
   The document by User covers neural networks.
   ID: ffe7a657-7043-4242-9384-569ec2bddfe2

5. PRODUCES
   NVIDIA produces the H100 GPU
   ID: 83f23ed6-1aef-4286-b65f-99657f61ecb0
```

---

## Query 8: What is the relationship between cybersecurity and encryption?

**Expected:** 0 results (cybersecurity and encryption NOT in graph)
**Actual:** 5 results (FALSE POSITIVES persist)

```
1. PRODUCES
   NVIDIA produces the A100 GPU
   ID: ea2b97f0-753c-402d-abf1-4777707982ad

2. LED_BY
   Meta Platforms is led by Mark Zuckerberg
   ID: 5f403af7-dc62-46fd-ab96-ba398f11e7b0

3. PRODUCES
   NVIDIA produces the H100 GPU
   ID: 83f23ed6-1aef-4286-b65f-99657f61ecb0

4. PROVIDES
   Hugging Face provides the transformers library
   ID: f9037590-9f09-4ffb-996a-4a5a4b61f35b

5. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem
   and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4
```

---

## Summary

| Query | Expected | Baseline | CrossEncoder | Assessment |
|-------|----------|----------|--------------|------------|
| 1. Quantum → Crypto | 0 | 4 FALSE POS | 5 FALSE POS | ❌ WORSE - More false positives |
| 2. Blockchain history | 0 | 5 FALSE POS | 5 FALSE POS | ❌ NO CHANGE - Same false positives |
| 3. ML → AI | 5 ✓ | 5 CORRECT | 5 CORRECT | ✓ SAME - Still accurate |
| 4. NN → DL | ~5 ✓ | 5 MOSTLY OK | 5 MOSTLY OK | ✓ SAME - Still mostly accurate |
| 5. Cloud → Storage | 3-5 ✓ | 5 MOSTLY OK | 5 MOSTLY OK | ✓ SAME - Still mostly accurate |
| 6. APIs → Services | 0 | 5 FALSE POS | 5 FALSE POS | ❌ NO CHANGE - Same false positives |
| 7. DevOps → CI | 0 | 5 FALSE POS | 5 FALSE POS | ❌ NO CHANGE - Same false positives |
| 8. Cybersecurity → Encryption | 0 | 5 FALSE POS | 5 FALSE POS | ❌ NO CHANGE - Same false positives |

---

## Key Finding: CrossEncoder Did Not Improve False Positives

**Problem:** The `COMBINED_HYBRID_SEARCH_CROSS_ENCODER` configuration returns 5 results for EVERY query, including those with zero relevant entities in the graph.

**Why:** The cross-encoder is reranking results, but the default limit is still set to 5 and there's no minimum relevance threshold being enforced.

**Comparison:**
- **Baseline** (vanilla `.search()`): 5 results for EVERY query
- **CrossEncoder** (`.search_()` with cross-encoder): 5 results for EVERY query

**Conclusion:** The CrossEncoder reranker is functioning but not solving the fundamental problem: there's no mechanism to reject results below a relevance threshold. The cross-encoder scores are present but not being used to filter.

---

## Next Steps

To properly implement false positive filtering, we need to:
1. Check if SearchConfig has a `reranker_min_score` parameter that filters by threshold
2. If not, post-filter results in the `search_relationships()` method based on reranker scores
3. Extract the cross-encoder scores from results and only return items above a threshold (e.g., 0.7)

The current implementation reranks results but doesn't filter them.
