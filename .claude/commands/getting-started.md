---
description: Get started with RAG Memory - understand what it is, choose MCP server or CLI usage, and complete setup
allowed-tools: ["Read", "Bash"]
---

# Welcome to RAG Memory!

I'm going to guide you through understanding and setting up RAG Memory. We'll cover WHAT it is, WHY you'd use it, whether you want MCP server OR CLI usage (or both), and THEN how to set it up.

---

## AI Assistant Instructions - How to Execute This Command

**START HERE - DO THIS FIRST:**
Go directly to "PHASE 1: EDUCATION" (Step 1) below. Do NOT run any commands yet. Do NOT check prerequisites yet. Start with education.

### CRITICAL RULES

**ABSOLUTE REQUIREMENTS:**
- **STOP after each major section** - Wait for user response
- **NEVER run commands that expose secrets** - Never check/display API keys
- **ASK PERMISSION before write operations** - docker-compose up, rag init, etc.
- **ALL content comes from .reference/** - Read and present, don't create
- **Keep responses SHORT** - 2-3 sentences per concept, not paragraphs
- **Follow the step sequence** - Don't skip ahead
- **If user says "yes" to understanding check** - THEN proceed to setup

### REQUIRED READING

Before starting, verify these files exist:
- `.reference/OVERVIEW.md`
- `.reference/MCP_QUICK_START.md`

If missing: "Reference documentation not found. Please ensure .reference/ directory is present."

---

## WHAT TO RUN vs WHAT TO SHOW

### ALWAYS SAFE TO RUN (read-only checks)
- `docker --version`, `uv --version`, `python --version`
- `docker-compose ps` (check container status)
- `pwd` (get current directory path)
- `ls`, `cat .env.example` (read non-secret files)
- `which rag-mcp-stdio` (check if installed)

### ASK PERMISSION BEFORE RUNNING (write operations)
- `docker-compose up -d` (starts database)
- Offer: "Would you like me to run this command for you?"
- Wait for explicit "yes" or permission

### NEVER RUN - USER MUST RUN THESE IN TERMINAL
- `rag init` - triggers first-run wizard asking for API key
- `rag status` - triggers first-run wizard asking for API key
- `rag collection create` - triggers first-run wizard asking for API key
- `rag ingest ...` - triggers first-run wizard asking for API key
- ANY `rag` command if ~/.rag-memory-env doesn't exist
- Tell user: "Run this command yourself in your terminal"

### SHOW BUT NEVER RUN (system changes)
- Config file edits (show JSON, tell location, they edit)
- .env file edits (show what to add, they edit)
- IDE/editor restarts (inform them, don't do it)
- System software installation (show commands, they run)

### NEVER CHECK OR DISPLAY (security)
- `echo $OPENAI_API_KEY` ❌ NEVER - exposes secret
- `cat .env` ❌ NEVER - exposes API keys
- Any command that would display API keys to the LLM
- Instead: "Check your .env file contains OPENAI_API_KEY=sk-..."

---

### PHASE 1: EDUCATION (MUST COMPLETE FIRST)

#### Step 1 - What Is RAG Memory?

[Read from .reference/OVERVIEW.md "What Is This?" section]

**Present:**
- 2-3 sentences on what RAG Memory is
- Emphasize: semantic search + full document retrieval (not just chunks)
- Keep it brief

**STOP and wait for user response before continuing to Step 2**

---

#### Step 2 - Two Ways to Use RAG Memory

[Read from .reference/OVERVIEW.md "Two ways to use it" section]

**Present:**
- Option 1: MCP Server (for AI agents like Claude Desktop, Claude Code, Cursor)
- Option 2: CLI Tool (for direct command-line usage, testing, automation)
- Mention you can use BOTH if needed
- Keep it brief (2-3 sentences)

**STOP and wait for user response before continuing to Step 3**

---

#### Step 3 - Why MCP Server? (If interested)

[Read from .reference/OVERVIEW.md "Why MCP Server?" section]

**Present:**
- What MCP is (1 sentence)
- Which AI agents are supported (list)
- Mention there are 14 tools available (don't list them all yet)

**STOP and wait for user response before continuing to Step 4**

---

#### Step 4 - The 16 MCP Tools

[Read from .reference/MCP_QUICK_START.md "Available Tools (16 Total)" section]

**Present:**
- Show the 16 tools grouped by 7 categories
- Brief description for each
- Key point: 2 graph tools are experimental, not for production yet
- Keep it scannable, not wordy

**STOP and wait for user response before continuing to Step 5**

---

#### Step 5 - Use Cases

[Read from .reference/OVERVIEW.md "Use Cases" section]

**Present:**
- Three main use cases (agent memory, knowledge base, documentation management)
- 1-2 sentences per use case
- Keep it concrete with examples

**STOP and wait for user response before continuing to Step 6**

---

#### Step 6 - API Costs (Quick Overview)

[Read from .reference/PRICING.md "Key Points" and "Realistic Usage Scenarios" sections]

**Present:**
- **Keep it brief** - Just give high-level cost estimates
- Small knowledge base (1,000 docs): ~$0.02 one-time
- Medium knowledge base (10,000 docs): ~$0.15 one-time
- Large knowledge base (100,000 docs): ~$1.50 one-time
- Emphasize: Searches are FREE (no API calls), only ingestion costs
- Tell them: "More details in .reference/PRICING.md if you want specifics"

**If they ask for more details:**
- Read more from .reference/PRICING.md as needed
- But keep initial presentation brief!

**STOP and wait for user response before continuing to Step 7**

---

#### Step 7 - Understanding Check & Usage Choice

**Ask:**
"Do you understand what RAG Memory does? And which usage mode interests you?"

**Options:**
- MCP server only → Proceed to MCP setup (Step 8)
- CLI only → Proceed to CLI setup (Step 8-alt)
- Both MCP and CLI → Proceed to full setup (Step 8)
- I have questions → [Read relevant section from .reference/OVERVIEW.md and explain]
- explain more about [topic] → [Read that specific section and elaborate]

**WAIT FOR USER RESPONSE**

**DO NOT proceed to setup until they confirm understanding AND choice**

**Important:** Based on their choice, follow the appropriate setup path:
- MCP server: Steps 8-12 (current flow)
- CLI only: Modified flow focusing on first-run wizard and CLI commands
- Both: Complete all steps

---

### PHASE 2: SETUP (ONLY AFTER PHASE 1 COMPLETE)

**Note:** The steps below cover the FULL setup (both MCP and CLI). If user chose "CLI only", skip Steps 9-10 (MCP configuration). If user chose "MCP only", they still need database and installation steps.

#### Step 8 - Installation Check

**Present:**
"Let me check if RAG Memory is installed globally. Is that okay?"

**WAIT FOR PERMISSION**

**If yes:**
[Run: `which rag-mcp-stdio`]

**If NOT found:**
"RAG Memory needs to be installed globally:"
```bash
uv tool install rag-memory
```

**Ask:** "Would you like me to run this? (yes/no)"

**WAIT FOR PERMISSION**

**If found:**
"✓ RAG Memory is installed!"

**STOP and wait for user response**

---

#### Step 9 - Database Setup

**Present:**
"The database needs to run from the cloned repository. Do you have the repo cloned?"

**If no:**
"Clone the repository to get docker-compose.yml:"
```bash
git clone https://github.com/YOUR-USERNAME/rag-memory.git
cd rag-memory
```

**Check status:**
[Run: `docker-compose ps`]

**If NOT running:**
"Start the database (from the cloned repo directory):"
```bash
docker-compose up -d
```

**Ask:** "Would you like me to run this? (yes/no)"

**WAIT FOR PERMISSION**

**After database starts:**
"Initialize the schema by running this command yourself in your terminal:"
```bash
rag init
```

**IMPORTANT: I cannot run this command because it may trigger the first-run wizard which asks for your API key.**

"After you run `rag init` yourself, let me know when it's done."

**STOP and wait for user response**

---

#### Step 10 - Environment Configuration (for CLI usage)

**If user chose "MCP only" → SKIP this step, go to Step 11**

**Present:**
"For CLI usage, you need to configure ~/.rag-memory-env with your database URL and OpenAI API key."

**NEVER RUN `rag init` or `rag status` - these trigger interactive prompts for API keys!**

**Instead, SHOW them:**
"You'll need to create ~/.rag-memory-env manually with these values:"

```
DATABASE_URL=postgresql://raguser:ragpass@localhost:54320/rag_poc
OPENAI_API_KEY=your-api-key-here
```

**Instructions:**
1. Get your OpenAI API key from https://platform.openai.com/api-keys
2. Create the file manually or run any `rag` command and follow the prompts **in your terminal**
3. The wizard runs interactively in your terminal - I cannot help with that part

**Important notes:**
- First-run wizard only runs ONCE (when ~/.rag-memory-env doesn't exist)
- The wizard is interactive and asks for keys directly in the terminal
- I cannot and will not run commands that would expose your API keys
- After setup, you can test with: `rag status` (run this yourself)

**STOP and wait for confirmation**

---

#### Step 11 - MCP Client Configuration

**If user chose "CLI only" → SKIP this step, go to Step 12**

**Ask:** "Which MCP client are you using?"
1. Claude Code (use `claude mcp add-json` command)
2. Claude Desktop (manual JSON config file)
3. Cursor (manual JSON config file)
4. Custom agent

**WAIT FOR RESPONSE**

**For Claude Code:**
"Run this command in your terminal to add the RAG Memory MCP server GLOBALLY (accessible from any directory):"

```bash
claude mcp add-json --scope user rag-memory '{"type":"stdio","command":"rag-mcp-stdio","args":[],"env":{"OPENAI_API_KEY":"sk-your-api-key-here","DATABASE_URL":"postgresql://raguser:ragpass@localhost:54320/rag_poc"}}'
```

**CRITICAL - The `--scope user` flag is REQUIRED:**
- Without it, the server only works in the current directory
- With `--scope user`, the server is available globally across all projects
- This ensures the MCP server works everywhere, not tied to any specific repo

**IMPORTANT:**
1. Replace `sk-your-api-key-here` with your actual OpenAI API key
2. Run this command yourself in your terminal - I cannot do this for you
3. After running, restart Claude Code

**For Claude Desktop:**
[Read appropriate section from .reference/MCP_QUICK_START.md]

Config file location: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add this JSON (edit the file manually):
```json
{
  "mcpServers": {
    "rag-memory": {
      "command": "rag-mcp-stdio",
      "args": [],
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key-here",
        "DATABASE_URL": "postgresql://raguser:ragpass@localhost:54320/rag_poc"
      }
    }
  }
}
```

**For Cursor or Custom:**
[Read appropriate section from .reference/MCP_QUICK_START.md]

**NEVER edit their config files or run the add-json command - only show what to do**

**Important reminder:**
"The MCP server needs BOTH the OpenAI API key AND the database URL to function."

**STOP and wait for user to configure**

---

#### Step 12 - Connection Test

**Present:**
"After editing the config, restart your AI agent (quit and reopen)."

**Ask:** "Have you restarted? (yes/no)"

**WAIT FOR RESPONSE**

**When yes:**

**For MCP users:**
"Ask your AI agent: 'List available RAG collections'"

**For CLI users:**
[Run: `rag collection list`]

**Ask:** "Which test would you like? (agent/CLI/both)"

**WAIT FOR RESPONSE**

[Execute their choice]

**STOP and wait for confirmation it worked**

---

#### Step 13 - First Document Test

**Present:**
"Let's add test data:"

```bash
rag collection create test-collection --description "Test collection"
rag ingest text "PostgreSQL with pgvector enables semantic search for AI agents. RAG Memory provides 14 MCP tools for document management." --collection test-collection
rag search "semantic search" --collection test-collection
```

**Ask:** "Would you like me to run these? (yes/no)"

**WAIT FOR PERMISSION**

[If yes, run the commands]

**Then suggest:**
"Now ask your AI agent: 'Search for documents about semantic search in test-collection'"

**STOP and wait for confirmation**

---

#### Step 14 - Next Steps

**Present:**
"✅ Your RAG Memory setup is complete! What would you like to explore next?"

**Adapt based on their usage choice:**
- MCP server users: "Your AI agent can now use all 16 RAG tools!"
- CLI users: "You can now use all CLI commands!"
- Both: "You have both MCP and CLI access!"

**Advanced Topics Available:**
1. Ingest real documents (files, directories, websites)
2. Learn about web crawling and re-crawl for updates
3. Understand document chunking strategy
4. Explore search optimization (vector-only is optimal)
5. Learn CLI commands (25+ available)
6. Advanced topics:
   - Knowledge graph & entity relationships (Experimental)
   - Similarity score tuning
   - Metadata filtering
   - Collections organization
   - Deployment options
7. Troubleshooting

**WAIT FOR RESPONSE**

**Based on choice:**
1. [Read from CLAUDE.md ingestion section]
2. [Read from .reference/OVERVIEW.md "Web Crawling & Link Following" + "Re-Crawl for Updates"]
3. [Read from .reference/OVERVIEW.md "Document Chunking"]
4. [Read from .reference/SEARCH_OPTIMIZATION.md "Baseline Search - RECOMMENDED"]
5. [Read from CLAUDE.md CLI Commands section]
6. **Advanced topics:**
   - Knowledge graph: [Read from .reference/KNOWLEDGE_GRAPH.md intro + use cases]
   - Similarity tuning: [Read from .reference/SEARCH_OPTIMIZATION.md "Threshold Tuning Guide"]
   - Metadata: [Read from .reference/OVERVIEW.md "Key Features Explained" - #4]
   - Collections: [Read from .reference/OVERVIEW.md "Collections (Organization Layer)"]
   - Deployment: [Read from .reference/OVERVIEW.md "Deployment Options"]
7. [Read from .reference/MCP_QUICK_START.md troubleshooting section]

---

### REMEMBER

**This is an EDUCATION + SETUP command:**
- Teach WHAT and WHY first (Phase 1)
- Check understanding before HOW (Step 5)
- One step at a time, wait for responses
- User-paced, not AI-paced
- **Short responses** (2-3 sentences per concept)
- **All content from .reference/** - Read and present
- Guide setup with permission for write operations
- Never expose secrets (API keys)

**You are a guide, not an operator. Help them understand and configure, don't do it for them.**
