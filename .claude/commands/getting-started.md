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

**CRITICAL FIRST STEP - Read the directory map:**
1. Read `.reference/README.md` FIRST to discover available documentation files
2. The README shows which files exist and what each contains
3. Use the README to find the right file for each topic

**Workflow for EVERY answer:**
1. Read `.reference/README.md` to find relevant documentation file
2. Read the specific file(s) mentioned in README for the topic
3. Extract exact examples, quotes, and explanations from those files
4. Present what you read (don't invent or paraphrase)
5. Wait for user response
6. Repeat

**DO NOT:**
- ❌ Hardcode examples (they go stale)
- ❌ Invent new examples (they may be wrong)
- ❌ Use keyword search examples (EVER - this is semantic search)
- ❌ Assume you know the content (READ IT FRESH)

**CRITICAL - SEMANTIC SEARCH EXAMPLES:**
When showing search examples, READ from `.reference/README.md` to find which files cover search, then read those files to get EXACT examples. These will be FULL QUESTIONS, not keywords. Never show keyword examples like "authentication setup" or "error handling".

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
- Read `.reference/README.md` to find which file covers "What RAG Memory is"
- Read that file's introduction section
- Present the problem traditional search has (keyword matching limitations)
- Explain how RAG Memory solves it (semantic understanding)
- Show performance data from docs (recall rates, accuracy)
- Ask: "Is this clear? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 2: What is Semantic Search?**
- Read `.reference/README.md` to find which file covers semantic search
- Read that file - look for semantic search explanation
- Explain how it works (vectors, meaning-based matching)
- Show examples from docs of semantic vs keyword search
- Present technical details (embeddings, similarity scores)
- Ask: "Clear on semantic search? Want more details or ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 3: What is RAG?**
- Read `.reference/README.md` to find which file covers RAG concepts
- Read that file's "What Is RAG Memory?" section
- Define RAG = Retrieval-Augmented Generation
- Explain the three steps (retrieve, augment, generate)
- Show the workflow and examples from the docs
- Ask: "Is the RAG concept clear? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 4: Why Two Databases?**
- Read `.reference/README.md` to find which file covers architecture
- Read that file's architecture section
- Explain PostgreSQL + pgvector for semantic search
- Explain Neo4j for knowledge graph relationships
- Show examples from the docs of when to use each
- Present the combined capabilities
- Ask: "Clear on the dual-database architecture? Want to continue?"
- [WAIT FOR USER RESPONSE]

**Step 5: How It Actually Works**
- Read `.reference/README.md` to find which file covers data flow
- Read that file's "Data Flow" section
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
- Read `.reference/README.md` to find which files cover search capabilities
- Read those files for search examples and key features
- Extract EXACT search query examples from the docs (they will be full questions)
- Explain similarity scores and what they mean (get ranges from docs)
- Show example queries and expected results
- **CRITICAL:** Emphasize semantic search uses QUESTIONS, not keywords (cite examples from docs)
- Ask: "Clear on how semantic search works? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 2: MCP Tools for AI Agents**
- Read `.reference/README.md` to find which file covers MCP server setup
- Read that file's "Available Tools" section
- Explain the two modes: CLI tool vs MCP server
- List the available tools from the docs
- Show examples from the docs of how AI agents use these tools
- Present use cases for each mode
- Ask: "Clear on CLI vs MCP modes? Want more details or ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 3: Document Ingestion**
- Read `.reference/README.md` to find which files cover ingestion
- Read those files' ingestion sections
- List all ingestion methods: text, files, directories, URLs
- Show command examples from the docs for each method
- Explain web crawling capabilities (follow_links, max_depth)
- Present what happens during ingestion (chunking, embedding, storage)
- Ask: "Clear on ingestion options? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 4: Collections**
- Read `.reference/README.md` to find which file covers collections
- Read that file's "Collections" section
- Explain what collections are and why they matter (from docs)
- Show collection examples and naming patterns from docs
- Explain scoping searches to specific collections
- Present organization strategies
- Ask: "Clear on how collections work? Want to continue?"
- [WAIT FOR USER RESPONSE]

**Step 5: Knowledge Graph Queries**
- Read `.reference/README.md` to find which file covers knowledge graphs
- Read that file's "Use Cases" section
- Extract exact query examples from docs
- Explain when to use graph queries vs RAG search (from docs)
- Show relationship query examples from docs
- Present the types of insights graphs provide
- Ask: "Clear on knowledge graph capabilities? Ready to move on?"
- [WAIT FOR USER RESPONSE]

**Step 6: Cost Structure (if pricing info exists)**
- Read `.reference/README.md` to check if pricing documentation exists
- If exists: Read that file's cost information
- If exists: Present embedding costs, graph extraction costs, and example calculations
- If exists: Emphasize that searches are FREE after ingestion
- If not exists: Note that costs are based on OpenAI API pricing (see OpenAI docs)
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
- **CRITICAL:** Tell user they MUST activate the virtual environment first:

  "Open a terminal and run these commands IN ORDER:

  ```bash
  cd rag-memory
  source .venv/bin/activate
  python scripts/setup.py
  ```

  ⚠️ IMPORTANT: You MUST run `source .venv/bin/activate` before running setup.py or it will fail with 'No module named graphiti_core' error."

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
- Read `.reference/CLI_REFERENCE.md` Service Management section (rag status)
- Tell user to run the status command (from docs)
- Explain expected output (from docs):
  - Each service shows health status with indicators
  - Healthy services show green checkmarks
  - Health checks verify actual service functionality, not just connectivity
- Ask: "Did status show all services healthy? (Type 'yes' or paste the output)"
- [WAIT FOR USER RESPONSE]

**Step 6: First Collection**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/README.md` to find which file has collection create examples
- Read that file for collection create example
- Tell user the exact command to run (from docs)
- Explain what it does
- Ask: "Have you created the collection? (Type 'yes' or paste output)"
- [WAIT FOR USER RESPONSE]

**Step 7: First Document**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/README.md` to find which file has ingestion examples
- Read that file for ingest example
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
- Read `.reference/README.md` to find which file has search examples
- Read that file for search example
- Tell user the EXACT search query to run from docs (will be a full question, not keywords)
- Explain what RAG search does: finds semantically similar content
- Show expected output (similarity scores, chunks, source IDs)
- Present performance data from docs (speed, accuracy)
- Ask: "Did the search work? Found the content? (Type 'yes' or paste results)"
- [WAIT FOR USER RESPONSE]

**Step 9: First Graph Query (Entity Relationships) - EQUAL IMPORTANCE**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Read `.reference/README.md` to find which file covers knowledge graph queries
- Read that file for relationship query example
- Tell user the exact graph query command to run from docs (query_relationships)
- Explain what graph queries do: finds entity relationships, connections, dependencies
- Show expected output (entities, relationships, facts, timestamps)
- Present what graph gives you that RAG doesn't (relationship mapping, multi-hop reasoning)
- Note about threshold tuning (from docs)
- **Emphasize:** This is why you paid the extraction cost - to get relationship intelligence
- Ask: "Did the graph query work? See the relationships? (Type 'yes' or paste results)"
- [WAIT FOR USER RESPONSE]

**Step 10: Compare RAG vs Graph**
- Read `.reference/README.md` to find which file has RAG vs Graph comparison
- Read that file's comparison section
- Show side-by-side examples from docs:
  - Same question answered with RAG search → returns content chunks
  - Same question answered with graph query → returns entity relationships
- Explain when to use each (from docs):
  - RAG: "What does the documentation say about X?"
  - Graph: "How does X relate to Y?" or "What depends on X?"
- Show combined usage pattern (from docs): graph for structure, RAG for details
- Ask: "Clear on when to use RAG vs Graph vs both together?"
- [WAIT FOR USER RESPONSE]

**Step 11: Exercise CLI Management Commands**
- **DO NOT RUN COMMANDS - ONLY PROVIDE INSTRUCTIONS**
- Tell user: "Now let's try some CLI commands to get familiar with managing your system."
- Read `.reference/README.md` to find which file has CLI command reference
- Read that file's sections: Service Management, Collection Management, Document Management
- Guide them to exercise these capabilities (read exact commands and options from that file):
  - Check service health and status
  - View service logs (including recent entries)
  - List all collections
  - List documents in their collection
  - View detailed collection information
- For each capability:
  - Read the relevant section from the CLI reference file
  - Present the command to run (from docs)
  - Explain what it does (from docs)
  - Show what output to expect (from docs)
- Tell them: "For complete CLI reference with all options and examples, check the README"
- Ask: "Tried these commands? Got a feel for managing the system? (Type 'yes' when ready to continue)"
- [WAIT FOR USER RESPONSE]

**Optional Step 12: Clean Up**
- Offer to delete test collection
- Read the CLI reference file's collection delete section
- Show command from docs
- Ask if they want to keep or delete
- [WAIT FOR USER RESPONSE]

**Step 13: MCP Server Setup (Optional)**
- Read `.reference/README.md` to find which file covers MCP server setup
- Read that file's configuration section
- Guide them to find setup.py output with connection commands
- Show how to connect Claude Code (from docs)
- Ask: "Want to set this up now or skip?"
- [WAIT FOR USER RESPONSE]

**You're All Set!**
- Summarize what they have (from setup)
- Offer next steps based on what's available in `.reference/README.md`:
  - "Learn more commands?" → Point to CLI reference
  - "Understand search better?" → Point to search documentation
  - "See all MCP tools?" → Point to MCP guide
  - "Ingest real documents?" → Guide through file/URL ingestion using docs

#### Path 4: Show Me the Commands

**Step 1: Service Management**
- Read `.reference/README.md` to find which file has CLI command reference
- Read that file's "Service Management" section
- Present the commands (status, start, stop, restart, logs)
- Show examples and options from docs
- Explain what each command does (from docs)
- Ask: "Clear on managing services? Ready for next section?"
- [WAIT FOR USER RESPONSE]

**Step 2: Initialization & Setup**
- Read the CLI reference file's "Initialization" section
- Present the init command
- Explain when to use it (from docs)
- Ask: "Understand initialization? Ready to continue?"
- [WAIT FOR USER RESPONSE]

**Step 3: Collection Management**
- Read the CLI reference file's "Collection Management" section
- Present collection commands (create, list, info, schema, update, delete)
- Show examples from docs
- Explain organization strategies (from docs)
- Ask: "Clear on collections? Ready for ingestion commands?"
- [WAIT FOR USER RESPONSE]

**Step 4: Document Ingestion**
- Read the CLI reference file's "Document Ingestion" section
- Present ingestion methods (text, file, directory, url)
- Show examples and options from docs
- Explain crawling capabilities (from docs)
- Ask: "Understand ingestion options? Ready for search?"
- [WAIT FOR USER RESPONSE]

**Step 5: Search & Retrieval**
- Read the CLI reference file's "Search & Retrieval" section
- Present search command and options
- Show examples from docs (FULL QUESTIONS, not keywords)
- Explain similarity scores and thresholds (from docs)
- Ask: "Clear on search? Ready for document management?"
- [WAIT FOR USER RESPONSE]

**Step 6: Document Management**
- Read the CLI reference file's "Document Management" section
- Present document commands (list, view, update, delete)
- Show examples from docs
- Explain cost implications (from docs)
- Ask: "Understand document management? Ready for advanced features?"
- [WAIT FOR USER RESPONSE]

**Step 7: Analysis & Knowledge Graph**
- Read the CLI reference file's "Analysis Tools" section
- Read the CLI reference file's "Knowledge Graph" section
- Present analysis commands (website analysis)
- Present graph commands (relationships, temporal, communities)
- Show examples from docs
- Explain when to use each (from docs)
- Ask: "Clear on analysis and graph features? Want to see workflows or done?"
- [WAIT FOR USER RESPONSE]

**Step 8: Common Workflows (Optional)**
- Read the CLI reference file's "Common Workflows" section
- Present workflow examples from docs (initial setup, comprehensive crawl, updates, troubleshooting)
- Show real-world usage patterns
- Ask: "Helpful? Want more details on anything?"
- [WAIT FOR USER RESPONSE]

**After completing Path 4 commands:**
- Present menu:
  1. Install It Now → Path 3
  2. Learn the Concepts → Path 1
  3. See What It Can Do → Path 2
  4. I'm Good → End
- If user chooses Path 3: IMMEDIATELY jump to Path 3, Step 1 (installation)
- If user chooses Path 1: IMMEDIATELY jump to Path 1, Step 1
- If user chooses Path 2: IMMEDIATELY jump to Path 2, Step 1
- DO NOT continue with more commands after they make a choice

### AFTER ANY PATH

Always offer contextual next steps based on what was just covered. Every answer should come from reading `.reference/` fresh.

### TROUBLESHOOTING

If user reports issues:
1. Read `.reference/README.md` to find which file has troubleshooting information
2. Read that file's troubleshooting section for the specific issue
3. Present the solution exactly as documented
4. Don't invent solutions - use what's in the docs

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
