---
description: Interactive guided tour of RAG Memory - learn concepts, capabilities, and setup step by step
argument-hint: ""
allowed-tools: ["Read", "Grep", "Glob", "Bash"]
---

# Welcome to RAG Memory! 🚀

I'm going to teach you about this tool step by step. We'll cover WHAT it is, WHY it's different, and THEN how to use it.

Before we dive into installation, let's make sure you understand what this is and why you might want it.

## Choose Your Learning Path

**What would you like to learn first?**

1. **Understand the Concepts** - What is RAG? Semantic search? Knowledge graphs? Why do I care?
2. **Learn the Capabilities** - What can RAG Memory actually DO for me?
3. **Just Get Started** - Skip explanations, install and configure now
4. **Show Me the Commands** - I know what this is, just show me how to use it

**Type 1, 2, 3, or 4** to choose your path.


## Note for AI Assistants - CRITICAL INSTRUCTIONS

### KNOWLEDGE BASE FIRST
Always read these .reference files BEFORE answering:
- `.reference/OVERVIEW.md` - Complete system overview and architecture
- `.reference/MCP_QUICK_START.md` - MCP server setup and 17 tools
- `.reference/PRICING.md` - Cost breakdown (embeddings + graph extraction)
- `.reference/KNOWLEDGE_GRAPH.md` - Graph capabilities and use cases
- `.reference/SEARCH_OPTIMIZATION.md` - Search quality and tuning

### PATH SELECTION

Based on user's choice (1, 2, 3, or 4), follow the appropriate path:

#### Path 1: Understand the Concepts

1. Start with fundamentals:

   **Concept**: The Problem RAG Solves
   - "Imagine you have 1000 documents and need to find where you explained 'authentication setup'"
   - "Traditional search requires exact keyword match: 'authentication setup' won't find 'auth configuration'"
   - "That's frustrating because you KNOW it's in there somewhere"
   - "Have you experienced this problem?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Concept**: What is Semantic Search?
   - "Semantic search understands MEANING, not just exact words"
   - "Search 'authentication setup' finds: 'auth configuration', 'user login setup', 'security initialization'"
   - "It works by converting text into 'vectors' (numbers that capture meaning)"
   - "Similar meanings = similar numbers = search finds them"
   - "Making sense so far?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Concept**: What is RAG?
   - "RAG = Retrieval-Augmented Generation"
   - "Step 1: Find relevant documents (Retrieval)"
   - "Step 2: Give those documents to an AI (Augmented)"
   - "Step 3: AI generates answer WITH your context (Generation)"
   - "Example: AI can answer 'How does our auth work?' using YOUR internal docs"
   - "Clear on what RAG does?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

2. Read `.reference/OVERVIEW.md` section "What Is RAG Memory?" and explain:

   **Concept**: Why Two Databases?
   - "RAG Memory uses BOTH vector search AND knowledge graphs"
   - "Vector Search (PostgreSQL + pgvector): Finds documents by meaning"
   - "Knowledge Graph (Neo4j): Tracks relationships between concepts"
   - "Example: Vector search finds 'auth docs', Graph shows 'auth connects to: user-service, database, API gateway'"
   - "You get both: content search + relationship mapping"
   - "See why both are useful?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Concept**: How It Actually Works
   Read `.reference/OVERVIEW.md` "Data Flow" section and explain:
   - "When you add a document: text → split into chunks → converted to vectors → stored in both databases"
   - "When you search: your question → converted to vector → finds similar vectors → returns matching chunks"
   - "Speed: ~400ms per search (includes AI processing)"
   - "Cost: You only pay when adding documents, searches are FREE (local database)"
   - "Questions about the process?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

3. After concepts, ask: "Want to see what you can DO with this?" → Path 2 or "Ready to install?" → Path 3

#### Path 2: Learn the Capabilities

1. Read `.reference/OVERVIEW.md` "Key Features" and present progressively:

   **Concept**: Semantic Search is the Core Feature
   - "Ask questions naturally: 'How do I handle errors in Python?'"
   - "System finds relevant docs even if they say 'exception handling' or 'try/catch'"
   - "Get similarity scores (0.7-0.95 for good matches)"
   - "⚠️ CRITICAL: Use full questions, NOT keywords ('error handling' = bad, 'How do I handle errors?' = good)"
   - "Want to try an example?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

2. Read `.reference/MCP_QUICK_START.md` "Available Tools" and explain:

   **Concept**: 17 Tools for AI Agents
   - "You can use RAG Memory two ways:"
   - "1. CLI tool (`rag` command) for terminal"
   - "2. MCP server for AI agents (Claude Code, Claude Desktop, Cursor)"
   - "MCP gives your AI agent 17 tools to search, add, update, delete knowledge"
   - "Example: Tell Claude 'Search my knowledge base for authentication docs'"
   - "Understand the two modes?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Concept**: Document Ingestion (Adding Knowledge)
   - "Add content from multiple sources:"
   - "• Text: Direct paste/type"
   - "• Files: Upload .txt, .md, code files"
   - "• Directories: Batch import entire folders"
   - "• Websites: Crawl documentation sites (auto-follow links)"
   - "Example: `rag ingest url https://docs.python.org --follow-links` crawls entire Python docs"
   - "Make sense?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

3. Read `.reference/OVERVIEW.md` "Collections" section:

   **Concept**: Collections (Organization Layer)
   - "Collections = named groups for organizing by topic"
   - "Examples: 'python-docs', 'company-policies', 'personal-notes', 'project-x'"
   - "Search can be scoped: 'rag search query --collection python-docs'"
   - "Documents can belong to multiple collections (flexible organization)"
   - "Clear on collections?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

4. Read `.reference/KNOWLEDGE_GRAPH.md` "Use Cases" section:

   **Concept**: Knowledge Graph Queries
   - "Beyond search, you can query relationships:"
   - "• 'What is related to authentication?'"
   - "• 'How has our architecture evolved over time?'"
   - "• 'What entities connect UserService to Database?'"
   - "This uses Neo4j to map entities and connections automatically"
   - "Interested in relationships or just search?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

5. Read `.reference/PRICING.md` "Key Points" section:

   **Concept**: Cost Structure (Important!)
   - "Two costs when adding documents:"
   - "1. Embeddings: ~$0.000013 per 500-word doc (OpenAI)"
   - "2. Graph extraction: ~$0.01 per doc (entity extraction)"
   - "Total: ~$0.01 per document one-time"
   - "Searches are FREE (run on your local database, no API calls)"
   - "Example: 1,000 docs = ~$10 to ingest, then unlimited free searches"
   - "Cost concerns or ready to continue?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

6. After capabilities: "Want to install it now?" → Path 3 or "Need more details?" → Offer to read specific .reference files

#### Path 3: Just Get Started

1. Check environment first:

   **Step 1**: Verify Prerequisites
   ```bash
   docker --version 2>/dev/null && echo "✅ Docker installed" || echo "⚠️ Need Docker"
   test -f scripts/setup.py && echo "✅ Setup script ready" || echo "⚠️ Setup script missing"
   ```

   Based on results:
   - If missing Docker: "You need Docker installed. Visit https://docker.com/get-started, install, then come back here."
   - If setup script missing: "Something's wrong - let me check the project structure"

   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

2. Explain what setup does:

   **Concept**: What the Setup Script Will Do
   - "The setup script automates everything:"
   - "1. Checks Docker is running"
   - "2. Starts PostgreSQL, Neo4j, MCP server, and backup containers"
   - "3. Asks for your OpenAI API key (for embeddings)"
   - "4. Configures automated backups (schedule and location)"
   - "5. Creates local configuration (at OS-appropriate system location)"
   - "6. Initializes databases"
   - "7. Validates all services are healthy and reachable"
   - "8. Installs CLI tool globally"
   - "This takes ~5-10 minutes (mostly waiting for containers). Ready?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

3. Run setup:

   **Step 2**: Run Setup Script
   - "Open a new terminal window"
   - "Navigate to the rag-memory directory"
   - "Run: `python scripts/setup.py`"
   - "Follow the interactive prompts. The script will ask you for:"
   - "  • OpenAI API key (get one at https://platform.openai.com/api-keys)"
   - "  • Backup schedule (when to backup databases)"
   - "  • Backup location (where to save backup files)"
   - "  • Directory mounts (optional, for file ingestion)"
   - "It will then build containers and validate everything is working"
   - "Come back here when setup completes!"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

4. After setup completes:

   **Step 3**: Open a New Terminal
   - "The setup script installed the `rag` CLI tool"
   - "You need to open a NEW terminal window for the command to be available"
   - "This ensures your shell picks up the updated PATH"
   - "Once you've opened a new terminal, run: `rag status`"

   "You should see:"
   - "✅ PostgreSQL connected"
   - "✅ Neo4j connected"
   - "✅ Database schemas initialized"

   "Did it work?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   "Note: The setup script already initialized the Neo4j indices for you, so you're ready to go!"

5. First commands:

   **Step 4**: Create Your First Collection
   ```bash
   rag collection create my-first-kb --description "My first knowledge base"
   ```

   "Collections organize your documents by topic. This creates one called 'my-first-kb'."
   "Created successfully?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Step 5**: Add Your First Document
   ```bash
   rag ingest text "RAG Memory uses semantic search to find documents by meaning, not keywords. It combines PostgreSQL with pgvector for vector search and Neo4j for knowledge graphs." --collection my-first-kb
   ```

   "This adds a document to your collection. You'll see progress as it:"
   - "1. Chunks the text (~1000 chars per chunk)"
   - "2. Generates embeddings (calls OpenAI)"
   - "3. Extracts entities for knowledge graph"
   - "4. Stores in both databases"

   "Document added?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Step 6**: Search Your Knowledge Base
   ```bash
   rag search "What databases does RAG Memory use?" --collection my-first-kb
   ```

   "Notice you asked a QUESTION (good!), not keywords (bad)."
   "You should see:"
   - "Your document chunk returned"
   - "Similarity score (probably 0.7-0.9)"
   - "Source document info"

   "Found it?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Step 7**: Query the Knowledge Graph
   ```bash
   rag graph query-relationships "What is related to PostgreSQL?" --threshold 0.25
   ```

   "This queries entity relationships extracted from your documents."
   "You should see relationships like:"
   - "PostgreSQL connects to pgvector"
   - "PostgreSQL is used by RAG Memory"
   - "Fact descriptions showing how entities are related"

   "Note: We use a low threshold (0.25) because entity extraction is LLM-based and non-deterministic."
   "This ensures you see results even if entity names vary slightly."

   "Did you see relationships?"
   [WAIT FOR USER RESPONSE BEFORE CONTINUING]

   **Optional: Clean Up Test Collection**
   - "Since this was just a test, you may want to delete this collection"
   - "This removes the collection and all its documents from both databases"
   - "Command: `rag collection delete my-first-kb --confirm`"
   - "Would you like to clean up the test collection or keep it?"
   [WAIT FOR USER RESPONSE - if yes, guide them through deletion]

6. MCP server setup:

   **Step 8**: Connect to Claude Code (Optional)
   - "The MCP server is already running (started by setup script)"
   - "Look back at the setup.py output - find the 'Connect to AI Assistants' section"
   - "It shows the EXACT commands to use with the correct ports"

   "For Claude Code:"
   - "Copy the `claude mcp add` command from the setup output"
   - "Run it in your terminal"
   - "Restart Claude Code"
   - "Run `claude mcp list` to verify it shows 'connected'"

   "For other AI assistants (Claude Desktop, Cursor):"
   - "The setup output also shows a config.json snippet you can use"

   "Want to set this up now or skip?"
   [WAIT FOR USER RESPONSE - if yes, help them find the connection commands in setup output]

7. After setup complete:

   **You're All Set! 🎉**
   "You now have:"
   - "✅ PostgreSQL + pgvector (semantic search)"
   - "✅ Neo4j (knowledge graph)"
   - "✅ CLI tool (`rag` command available globally)"
   - "✅ MCP server (if you set it up)"
   - "✅ Your first collection and document"

   "What next?"
   - "Learn more commands?" → Show `.reference/OVERVIEW.md` CLI section
   - "Understand search better?" → Read `.reference/SEARCH_OPTIMIZATION.md`
   - "See all MCP tools?" → Read `.reference/MCP_QUICK_START.md`
   - "Ingest real documents?" → Guide through file/URL ingestion

#### Path 4: Show Me the Commands

1. Read `.reference/OVERVIEW.md` CLI section and present:

**Quick Command Reference:**

```bash
# Collections
rag collection create <name> --description "text"
rag collection list
rag collection info <name>

# Ingestion (⚠️ Has cost: ~$0.01 per doc)
rag ingest text "content" --collection <name>
rag ingest file /path/to/file.txt --collection <name>
rag ingest directory /path/to/docs --collection <name> --extensions .txt,.md
rag ingest url https://docs.example.com --collection <name> --follow-links --max-depth 2

# Search (FREE - no API calls)
rag search "How do I configure authentication?" --collection <name>
rag search "error handling best practices" --collection <name> --threshold 0.7

# Document Management (FREE)
rag document list --collection <name>
rag document view <ID>
rag document update <ID> --content "new content"
rag document delete <ID>

# Knowledge Graph Queries (FREE)
rag graph query-relationships "What is related to authentication?"
rag graph query-temporal "How has our architecture evolved?"

# Status
rag status
```

**Key Things to Remember:**
- Use FULL QUESTIONS for search, not keywords ("How do I...?" not "authentication config")
- Ingestion has cost (~$0.01/doc), searches are free
- Collections organize by topic
- `--help` on any command for details

"Want detailed explanations?" → Read relevant `.reference/` sections
"Ready to start using it?" → Guide through setup if not done
"Need examples?" → Show use cases from `.reference/OVERVIEW.md`

### AFTER ANY PATH

Offer contextual next steps:
- After Path 1 (Concepts) → "Want to see capabilities?" → Path 2
- After Path 2 (Capabilities) → "Ready to install?" → Path 3
- After Path 3 (Setup) → "Want to learn advanced features?" → Read `.reference/` files
- After Path 4 (Commands) → "Need setup help?" → Path 3

### TROUBLESHOOTING

If user reports issues, read `.reference/OVERVIEW.md` or `.reference/MCP_QUICK_START.md` troubleshooting sections:

**Common Issues:**
- "Connection refused" → Check Docker containers running
- "Command not found" → CLI tool not installed
- "Search returns nothing" → Using keywords instead of questions
- "MCP server not showing" → Check config, restart Claude

For each issue, read the relevant troubleshooting section from `.reference/` files and present the solution.

### HELP AT ANY TIME

**User can always say:**
- "I don't understand" → Explain current concept differently with examples
- "Show me an example" → Provide concrete use case
- "Why do I need this?" → Explain problem it solves
- "How much will this cost?" → Read `.reference/PRICING.md` and explain
- "What's the difference between X and Y?" → Compare with examples

### REMEMBER

- **ONE concept at a time** - Never dump multiple concepts
- **Always wait for response** - Don't continue without user input
- **Use .reference files** - They have accurate, up-to-date information
- **Explain WHY before HOW** - Context before commands
- **Be encouraging** - Learning should feel guided, not overwhelming
- **Check understanding** - Ask "Does this make sense?" frequently
- **Offer choices** - User drives the journey

---

**Ready to begin? Pick your path (1, 2, 3, or 4)!** 🚀
