---
description: Interactive guided tour of RAG Memory - learn concepts, capabilities, and setup step by step
argument-hint: ""
allowed-tools: ["Read", "Grep", "Glob", "Bash"]
---

# Welcome to RAG Memory! 🚀

I'm going to teach you about this tool step by step. We'll cover WHAT it is, WHY it's different, and THEN how to use it.

Before we dive in, I need to read the latest documentation from `.reference/` to ensure everything I tell you is accurate and up-to-date.

## Choose Your Learning Path

**What would you like to learn first?**

1. **Understand the Concepts** - What is RAG? Semantic search? Knowledge graphs? Why do I care?
2. **Learn the Capabilities** - What can RAG Memory actually DO for me?
3. **Just Get Started** - Skip explanations, install and configure now
4. **Show Me the Commands** - I know what this is, just show me how to use it

**Type 1, 2, 3, or 4** to choose your path.

---

## BEFORE Starting Any Path - Ask Detail Level

**CRITICAL: Before proceeding with the user's chosen path, ALWAYS ask:**

"How much detail do you want?

1. **Quick Overview** (5-10 minutes) - Essential concepts only, minimal examples
2. **Standard Tutorial** (15-20 minutes) - Balanced explanations with key examples
3. **Deep Dive** (30+ minutes) - Comprehensive training with full details

Type 1, 2, or 3"

[WAIT FOR USER RESPONSE]

**Then adjust all subsequent steps based on their detail level:**

- **Quick (1):** 1-2 paragraphs per concept, one example, skip "why this matters"
- **Standard (2):** 2-3 paragraphs per concept, 2-3 examples, brief explanations
- **Deep (3):** Full explanations (current behavior), multiple examples, complete context

---

## Note for AI Assistants - CRITICAL INSTRUCTIONS

### THE GOSPEL: .reference/ IS THE SINGLE SOURCE OF TRUTH

**ABSOLUTE RULE:** Every answer MUST come from reading `.reference/` files. NO hardcoded examples. NO paraphrasing. NO "improving" the docs.

**Required reading before EVERY response:**
1. `.reference/OVERVIEW.md` - System architecture, features, examples
2. `.reference/MCP_QUICK_START.md` - MCP tools and setup
3. `.reference/SEARCH_OPTIMIZATION.md` - Search behavior and examples
4. `.reference/KNOWLEDGE_GRAPH.md` - Graph capabilities and queries
5. `.reference/PRICING.md` - Cost breakdown

**Workflow for EVERY answer:**
1. User picks path
2. Read relevant `.reference/` section(s)
3. Extract exact examples, quotes, and explanations
4. Present what you read (don't invent or paraphrase)
5. Wait for user response
6. Repeat

**DO NOT:**
- ❌ Hardcode examples (they go stale)
- ❌ Invent new examples (they may be wrong)
- ❌ Use keyword search examples (EVER - this is semantic search)
- ❌ Assume you know the content (READ IT FRESH)

**CRITICAL - SEMANTIC SEARCH EXAMPLES:**
When showing search examples, READ from `.reference/OVERVIEW.md` or `.reference/MCP_QUICK_START.md` to get the EXACT examples they provide. These will be FULL QUESTIONS, not keywords. Never show keyword examples like "authentication setup" or "error handling".

**CRITICAL - CONFIG FILE PATHS (OS-SPECIFIC):**
NEVER hardcode config file paths as `~/.config/rag-memory/` - this is LINUX ONLY and will mislead macOS/Windows users.

Correct paths by OS:
- macOS: `~/Library/Application Support/rag-memory/`
- Linux: `~/.config/rag-memory/`
- Windows: `%APPDATA%\rag-memory\`

setup.py uses `platformdirs.user_config_dir()` which handles this automatically and prints the actual path.

**When mentioning config location, say:**
- ✅ "OS-appropriate system configuration location"
- ✅ "System's standard config directory"
- ✅ "The setup script will show you the exact path"
- ❌ NEVER hardcode `~/.config/rag-memory/`

### PATH SELECTION

Based on user's choice (1, 2, 3, or 4), follow the appropriate path:

#### Path 1: Understand the Concepts

**Step 1: The Problem RAG Solves**
- Read `.reference/OVERVIEW.md` introduction section
- Present the problem traditional search has (keyword matching limitations)
- Explain how RAG Memory solves it (semantic understanding)
- Show performance data from docs (recall rates, accuracy)
- Ask: "Is this clear? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 2: What is Semantic Search?**
- Read `.reference/SEARCH_OPTIMIZATION.md` - look for semantic search explanation
- Explain how it works (vectors, meaning-based matching)
- Show examples from docs of semantic vs keyword search
- Present technical details (embeddings, similarity scores)
- Ask: "Clear on semantic search? Want more details or ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 3: What is RAG?**
- Read `.reference/OVERVIEW.md` "What Is RAG Memory?" section
- Define RAG = Retrieval-Augmented Generation
- Explain the three steps (retrieve, augment, generate)
- Show the workflow and examples from the docs
- Ask: "Is the RAG concept clear? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 4: Why Two Databases?**
- Read `.reference/OVERVIEW.md` architecture section
- Explain PostgreSQL + pgvector for semantic search
- Explain Neo4j for knowledge graph relationships
- Show examples from the docs of when to use each
- Present the combined capabilities
- Ask: "Clear on the dual-database architecture? Want to continue?"
- [WAIT FOR USER RESPONSE]

**Step 5: How It Actually Works**
- Read `.reference/OVERVIEW.md` "Data Flow" section
- Explain ingestion workflow: text → chunks → vectors → storage
- Explain search workflow: question → vector → similarity → results
- Show performance numbers from docs (speed, cost, accuracy)
- Present examples of the complete flow
- Ask: "Is the workflow clear? Any questions before moving on?"
- [WAIT FOR USER RESPONSE]

**After completing Path 1 concepts:**
- Present menu:
  1. See What You Can DO → Path 2
  2. Install It Now → Path 3
  3. See Commands → Path 4
  4. I'm Good → End
- If user chooses Path 2: IMMEDIATELY jump to Path 2, Step 1
- If user chooses Path 3: IMMEDIATELY jump to Path 3, Step 1 (installation)
- If user chooses Path 4: IMMEDIATELY jump to Path 4
- DO NOT continue with Path 1 content after they make a choice

#### Path 2: Learn the Capabilities

**Step 1: Semantic Search is the Core Feature**
- Read `.reference/OVERVIEW.md` "Key Features" section
- Read `.reference/SEARCH_OPTIMIZATION.md` for search examples
- Extract EXACT search query examples from the docs (they will be full questions)
- Explain similarity scores and what they mean (get ranges from docs)
- Show example queries and expected results
- **CRITICAL:** Emphasize semantic search uses QUESTIONS, not keywords (cite examples from docs)
- Ask: "Clear on how semantic search works? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 2: MCP Tools for AI Agents**
- Read `.reference/MCP_QUICK_START.md` "Available Tools" section
- Explain the two modes: CLI tool vs MCP server
- List the 17 available tools from the docs
- Show examples from the docs of how AI agents use these tools
- Present use cases for each mode
- Ask: "Clear on CLI vs MCP modes? Want more details or ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 3: Document Ingestion**
- Read `.reference/OVERVIEW.md` ingestion sections
- List all ingestion methods: text, files, directories, URLs
- Show command examples from the docs for each method
- Explain web crawling capabilities (follow_links, max_depth)
- Present what happens during ingestion (chunking, embedding, storage)
- Ask: "Clear on ingestion options? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 4: Collections**
- Read `.reference/OVERVIEW.md` "Collections" section
- Explain what collections are and why they matter (from docs)
- Show collection examples and naming patterns from docs
- Explain scoping searches to specific collections
- Present organization strategies
- Ask: "Clear on how collections work? Want to continue?"
- [WAIT FOR USER RESPONSE]

**Step 5: Knowledge Graph Queries**
- Read `.reference/KNOWLEDGE_GRAPH.md` "Use Cases" section
- Extract exact query examples from docs
- Explain when to use graph queries vs RAG search (from docs)
- Show relationship query examples from docs
- Present the types of insights graphs provide
- Ask: "Clear on knowledge graph capabilities? Ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 6: Cost Structure**
- Read `.reference/PRICING.md` "Key Points" section
- Present embedding costs with exact numbers from docs
- Present graph extraction costs with exact numbers from docs
- Show example cost calculations from docs
- Emphasize that searches are FREE after ingestion (from docs)
- Present total cost estimates for typical use cases
- Ask: "Clear on pricing? Any concerns or ready to continue?"
- [WAIT FOR USER RESPONSE]

**After completing Path 2 capabilities:**
- Present menu:
  1. Install It Now → Path 3
  2. See Commands → Path 4
  3. Go Back to Concepts → Path 1
  4. I'm Good → End
- If user chooses Path 3: IMMEDIATELY jump to Path 3, Step 1 (installation)
- If user chooses Path 4: IMMEDIATELY jump to Path 4
- If user chooses Path 1: IMMEDIATELY jump back to Path 1, Step 1
- DO NOT continue with more capabilities after they make a choice

#### Path 3: Just Get Started

**Step 1: Verify Prerequisites**
- Check Docker installed: `docker --version`
- Check setup script exists: `test -f scripts/setup.py && echo "✅ Ready"`
- Based on results, guide user
- [WAIT FOR USER RESPONSE]

**Step 2: Check for Existing Installation**
- Check for EXACT container names created by setup.py:
  - `rag-memory-postgres-local`
  - `rag-memory-neo4j-local`
  - `rag-memory-mcp-local`
  - `rag-memory-backup-local`
- Use: `docker ps --filter "name=rag-memory-postgres-local" --format "{{.Names}}"` (exact match)
- DO NOT use fuzzy matching or "contains" logic
- If ALL four containers exist: "You already have RAG Memory installed! Want to verify status or reinstall?"
- If SOME containers exist: "Partial installation detected. Recommend clean reinstall."
- If NO containers exist: Proceed to setup
- [WAIT FOR USER RESPONSE if containers found]

**Step 3: Explain Setup Script**
- Read setup.py or relevant docs to understand what it does
- List what the script will do (from code/docs)
- **CRITICAL:** When mentioning config file location, say:
  - "Creates system configuration at the OS-appropriate location"
  - OR "Creates config in your system's standard config directory"
  - **NEVER say** `~/.config/rag-memory/` (that's Linux only!)
  - Note: "The script will print the exact path when it runs"
- Warn about time required (~5-10 minutes)
- Ask: "Ready?"
- [WAIT FOR USER RESPONSE]

**Step 4: Run Setup**
- **DO NOT RUN THE SETUP SCRIPT - ONLY PROVIDE INSTRUCTIONS**
- Tell user: "Now open a terminal and run: `python scripts/setup.py`"
- Explain prompts they'll see (from setup.py code):
  - OpenAI API key
  - Database connection details
  - Backup configuration
  - Directory mounts
- List what they need ready: OpenAI API key
- **When explaining where config is created, use THIS EXACT WORDING:**
  - "The script will create your system configuration in the standard location for your OS"
  - "The setup script will show you the exact path when it completes"
  - **DO NOT mention any specific path like ~/.config/rag-memory/**
- Tell them: "Come back here when the script completes and says 'Setup complete!'"
- Ask: "Have you completed the setup? (Type 'yes' when done)"
- [WAIT FOR USER RESPONSE]

**Step 5: Verify Installation**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Tell user: "Open a NEW terminal window (important for PATH)"
- Tell user: "Run: `rag status`"
- Explain expected output:
  - ✅ PostgreSQL connected
  - ✅ Neo4j connected
  - ✅ Database schemas initialized
- Ask: "Did `rag status` show all green checkmarks? (Type 'yes' or paste the output)"
- [WAIT FOR USER RESPONSE]

**Step 6: First Collection**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/OVERVIEW.md` for collection create example
- Tell user the exact command to run (from docs)
- Explain what it does
- Ask: "Have you created the collection? (Type 'yes' or paste output)"
- [WAIT FOR USER RESPONSE]

**Step 7: First Document**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/OVERVIEW.md` or `.reference/MCP_QUICK_START.md` for ingest example
- Tell user the exact command to run (from docs)
- **CRITICAL:** Explain BOTH processes that happen:
  1. RAG ingestion: chunking → embeddings → vector storage
  2. Graph ingestion: entity extraction → relationship mapping → Neo4j storage
- Emphasize that ingestion goes to BOTH stores (dual storage architecture)
- Show timing and cost for both processes (from docs)
- Ask: "Have you ingested the document? (Type 'yes' or paste the output)"
- [WAIT FOR USER RESPONSE]

**Step 8: First RAG Search (Vector Similarity)**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/OVERVIEW.md` or `.reference/SEARCH_OPTIMIZATION.md` for search example
- Tell user the EXACT search query to run from docs (will be a full question, not keywords)
- Explain what RAG search does: finds semantically similar content
- Show expected output (similarity scores, chunks, source IDs)
- Present performance data from docs (speed, accuracy)
- Ask: "Did the search work? Found the content? (Type 'yes' or paste results)"
- [WAIT FOR USER RESPONSE]

**Step 9: First Graph Query (Entity Relationships) - EQUAL IMPORTANCE**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/KNOWLEDGE_GRAPH.md` for relationship query example
- Tell user the exact graph query command to run from docs (query_relationships)
- Explain what graph queries do: finds entity relationships, connections, dependencies
- Show expected output (entities, relationships, facts, timestamps)
- Present what graph gives you that RAG doesn't (relationship mapping, multi-hop reasoning)
- Note about threshold tuning (from docs)
- **Emphasize:** This is why you paid the $0.01/doc extraction cost - to get relationship intelligence
- Ask: "Did the graph query work? See the relationships? (Type 'yes' or paste results)"
- [WAIT FOR USER RESPONSE]

**Step 10: Compare RAG vs Graph**
- Read `.reference/KNOWLEDGE_GRAPH.md` "RAG vs Graph" comparison section
- Show side-by-side examples from docs:
  - Same question answered with RAG search → returns content chunks
  - Same question answered with graph query → returns entity relationships
- Explain when to use each (from docs):
  - RAG: "What does the documentation say about X?"
  - Graph: "How does X relate to Y?" or "What depends on X?"
- Show combined usage pattern (from docs): graph for structure, RAG for details
- Ask: "Clear on when to use RAG vs Graph vs both together?"
- [WAIT FOR USER RESPONSE]

**Optional Step 11: Clean Up**
- Offer to delete test collection
- Show command from docs
- Ask if they want to keep or delete
- [WAIT FOR USER RESPONSE]

**Step 12: MCP Server Setup (Optional)**
- Read `.reference/MCP_QUICK_START.md` configuration section
- Guide them to find setup.py output with connection commands
- Show how to connect Claude Code (from docs)
- Ask: "Want to set this up now or skip?"
- [WAIT FOR USER RESPONSE]

**You're All Set!**
- Summarize what they have (from setup)
- Offer next steps:
  - "Learn more commands?" → Read and present CLI section from `.reference/OVERVIEW.md`
  - "Understand search better?" → Read and present `.reference/SEARCH_OPTIMIZATION.md`
  - "See all MCP tools?" → Read and present `.reference/MCP_QUICK_START.md`
  - "Ingest real documents?" → Guide through file/URL ingestion using docs

#### Path 4: Show Me the Commands

**Read `.reference/OVERVIEW.md` CLI command section**
- Present the complete command reference exactly as documented
- Include all examples from the docs
- Show the sections on collections, ingestion, search, management
- Emphasize key points from the docs (questions not keywords, costs, etc.)

**After commands:** Offer:
- "Want detailed explanations?" → Read relevant `.reference/` sections
- "Ready to start using it?" → Path 3 if not set up
- "Need examples?" → Read and present use cases from `.reference/OVERVIEW.md`

### AFTER ANY PATH

Always offer contextual next steps based on what was just covered. Every answer should come from reading `.reference/` fresh.

### TROUBLESHOOTING

If user reports issues:
1. Read the relevant `.reference/` file's troubleshooting section
2. Present the solution exactly as documented
3. Don't invent solutions - use what's in the docs

**Never assume you know the answer. Always read from `.reference/` first.**

### REMEMBER

- **Read `.reference/` for EVERY answer** - Don't rely on memory
- **ONE concept at a time** - Never dump multiple concepts
- **Always wait for response** - Don't continue without user input
- **Extract, don't invent** - Use exact examples and quotes from docs
- **Full questions, not keywords** - When showing search examples (from docs)
- **Check understanding** - Ask "Does this make sense?" frequently
- **Offer choices** - User drives the journey

---

**Ready to begin? Pick your path (1, 2, 3, or 4)!** 🚀
