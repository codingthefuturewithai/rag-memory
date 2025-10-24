# Baseline Search Results - Exact Output (Vanilla Graphiti .search())

**Captured:** 2025-10-23
**Strategy:** `await self.graphiti.search(query, num_results=num_results)` - NO config, NO threshold
**Code Location:** `src/unified/graph_store.py:368`

---

## Query 1: How does quantum computing relate to cryptography?

**Expected:** 0 results (quantum computing and cryptography NOT in graph)
**Actual:** 4 results (FALSE POSITIVES)

```
1. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

2. PARTNERS_WITH
   NVIDIA partners with Microsoft Azure to deliver AI computing capabilities
   ID: f41b1492-877d-424a-b238-44b53406dcec

3. PARTNERS_WITH
   NVIDIA partners with Google Cloud to deliver AI computing capabilities
   ID: 81af61e1-c840-44c2-98d5-f82f3403f428

4. PARTNERS_WITH
   NVIDIA partners with Amazon Web Services (AWS) to deliver AI computing capabilities
   ID: 0b5ef9dd-73a7-4a15-8caf-b479aa49c095
```

---

## Query 2: What is the history of blockchain and cryptocurrency?

**Expected:** 0 results (blockchain and cryptocurrency NOT in graph)
**Actual:** 5 results (MIXED - some relevant to AI, none to blockchain/crypto)

```
1. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

2. ABOUT
   The document by User is about AI.
   ID: cdf2a75f-dfc9-4b38-86cf-44effe63c21f

3. ABOUT
   The document by User is about machine learning.
   ID: 5779513b-7ac8-4c40-8d62-ca829df0ce0f

4. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

5. LED_BY
   Meta Platforms is led by Mark Zuckerberg
   ID: 5f403af7-dc62-46fd-ab96-ba398f11e7b0
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

3. INVOLVES
   Machine learning involves training models.
   ID: 493f7bbb-9a85-4db1-bcf2-64873d001c1d

4. ABOUT
   The document by User is about machine learning.
   ID: 5779513b-7ac8-4c40-8d62-ca829df0ce0f

5. INCLUDES
   Machine learning includes deployment strategies.
   ID: 911c35ba-3c6b-4e1f-b139-17f56ac955ad
```

---

## Query 4: How do neural networks relate to deep learning?

**Expected:** 5 results (Neural networks ARE in graph, "deep learning" might not be)
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

4. INVOLVES
   Machine learning involves training models.
   ID: 493f7bbb-9a85-4db1-bcf2-64873d001c1d

5. INCLUDES
   Machine learning includes deployment strategies.
   ID: 911c35ba-3c6b-4e1f-b139-17f56ac955ad
```

---

## Query 5: What is the connection between cloud computing and data storage?

**Expected:** Partial results (cloud services like Azure/AWS ARE in graph)
**Actual:** 5 results (MOSTLY RELEVANT - cloud partnerships found)

```
1. PARTNERS_WITH
   NVIDIA partners with Google Cloud to deliver AI computing capabilities
   ID: 81af61e1-c840-44c2-98d5-f82f3403f428

2. PARTNERS_WITH
   NVIDIA partners with Amazon Web Services (AWS) to deliver AI computing capabilities
   ID: 0b5ef9dd-73a7-4a15-8caf-b479aa49c095

3. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

4. PARTNERS_WITH
   NVIDIA partners with Microsoft Azure to deliver AI computing capabilities
   ID: f41b1492-877d-424a-b238-44b53406dcec

5. INTEGRATES_TECHNOLOGY_INTO
   Microsoft integrates OpenAI's technology into its Azure cloud platform
   ID: 6345235d-e901-4f06-8f89-3eaaec51b3ab
```

---

## Query 6: How do APIs relate to web services?

**Expected:** 0 results (APIs and web services NOT in graph)
**Actual:** 5 results (FALSE POSITIVES - AWS mentioned but not APIs/services)

```
1. RECEIVED_FUNDING_FROM
   Anthropic has received significant funding from Amazon Web Services
   ID: 86f72a77-c283-4b82-bf1c-6e8d7a105d45

2. PARTNERS_WITH
   NVIDIA partners with Amazon Web Services (AWS) to deliver AI computing capabilities
   ID: 0b5ef9dd-73a7-4a15-8caf-b479aa49c095

3. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

4. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

5. PARTNERS_WITH
   NVIDIA partners with Microsoft Azure to deliver AI computing capabilities
   ID: f41b1492-877d-424a-b238-44b53406dcec
```

---

## Query 7: Explain the relationship between DevOps and continuous integration

**Expected:** 0 results (DevOps and CI NOT in graph)
**Actual:** 5 results (FALSE POSITIVES - deployment strategy tangentially related)

```
1. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

2. INTEGRATES_TECHNOLOGY_INTO
   Microsoft integrates OpenAI's technology into its Azure cloud platform
   ID: 6345235d-e901-4f06-8f89-3eaaec51b3ab

3. COVERS
   The document by User covers deployment strategies.
   ID: 7530bc57-4c65-43b4-a65f-decab36996d9

4. PRODUCES
   NVIDIA produces the A100 GPU
   ID: ea2b97f0-753c-402d-abf1-4777707982ad

5. PRODUCES
   NVIDIA produces the H100 GPU
   ID: 83f23ed6-1aef-4286-b65f-99657f61ecb0
```

---

## Query 8: What is the relationship between cybersecurity and encryption?

**Expected:** 0 results (cybersecurity and encryption NOT in graph)
**Actual:** 5 results (FALSE POSITIVES - completely unrelated to query)

```
1. RELATED_TO
   AI is related to machine learning.
   ID: 09e7b215-03a6-423a-8e06-cbb1cb12ecd2

2. PARTNERED_WITH
   Together AI and Hugging Face are key players in the open-source AI ecosystem and partner with open-source projects
   ID: 47c759f0-55da-4b72-a50f-beda9633a5e4

3. ABOUT
   The document by User is about AI.
   ID: cdf2a75f-dfc9-4b38-86cf-44effe63c21f

4. ABOUT
   The document by User is about machine learning.
   ID: 5779513b-7ac8-4c40-8d62-ca829df0ce0f

5. LED_BY
   Meta Platforms is led by Mark Zuckerberg
   ID: 5f403af7-dc62-46fd-ab96-ba398f11e7b0
```

---

## Summary

| Query | Expected | Actual | Assessment |
|-------|----------|--------|------------|
| 1. Quantum → Crypto | 0 | 4 | FALSE POSITIVE |
| 2. Blockchain history | 0 | 5 | FALSE POSITIVE |
| 3. ML → AI | 5 | 5 | ✓ CORRECT |
| 4. NN → DL | ~5 | 5 | ✓ MOSTLY CORRECT |
| 5. Cloud → Storage | 3-5 | 5 | ✓ MOSTLY CORRECT |
| 6. APIs → Services | 0 | 5 | FALSE POSITIVE |
| 7. DevOps → CI | 0 | 5 | FALSE POSITIVE |
| 8. Cybersecurity → Encryption | 0 | 5 | FALSE POSITIVE |

**Problem:** Vanilla `.search()` returns 5 results for EVERY query, even those with zero relevant entities in the graph. This is extremely permissive and generates false positives.
