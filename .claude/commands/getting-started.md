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
- `rag status` (database connection check)
- `rag collection list`
- `rag document list`
- `pwd` (get current directory path)
- `ls`, `cat .env.example` (read non-secret files)

### ASK PERMISSION BEFORE RUNNING (write operations)
- `docker-compose up -d` (starts database)
- `rag init` (creates schema)
- `rag collection create`
- `rag ingest ...` (adds data)
- Offer: "Would you like me to run this command for you?"
- Wait for explicit "yes" or permission

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
- Mention there are 11 tools available (don't list them all yet)

**STOP and wait for user response before continuing to Step 4**

---

#### Step 4 - The 11 MCP Tools

[Read from .reference/OVERVIEW.md "Why MCP Server?" section - tools list]

**Present:**
- Show the 11 tools grouped by category
- Brief description for each (tool name + one phrase)
- Keep it scannable, not wordy

**STOP and wait for user response before continuing to Step 5**

---

#### Step 6 - Use Cases

[Read from .reference/OVERVIEW.md "Use Cases" section]

**Present:**
- Three main use cases (agent memory, knowledge base, documentation management)
- 1-2 sentences per use case
- Keep it concrete with examples

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
"Initialize the schema:"
```bash
rag init
```

**Ask:** "Would you like me to run this? (yes/no)"

**WAIT FOR PERMISSION**

**Verify:**
[Run: `rag status`]

**STOP and wait for user response**

---

#### Step 10 - Environment Configuration (for CLI usage)

**If user chose "MCP only" → SKIP this step, go to Step 11**

**Present:**
"For CLI usage, RAG Memory has a first-run setup wizard. Let's test it now:"

**Run:**
[Run: `rag status`]

**Expected behavior:**
- If `~/.rag-memory-env` doesn't exist, the wizard will prompt for DATABASE_URL and OPENAI_API_KEY
- Tell user: "The wizard will prompt you for configuration. Use these values:"
  - DATABASE_URL: `postgresql://raguser:ragpass@localhost:54320/rag_poc`
  - OPENAI_API_KEY: Your OpenAI API key (get from https://platform.openai.com/api-keys)

**After wizard completes:**
"✓ Configuration saved to ~/.rag-memory-env"
"The `rag status` command should now show database statistics."

**Important notes:**
- First-run wizard only runs ONCE (when ~/.rag-memory-env doesn't exist)
- This config is used for ALL CLI commands
- MCP server gets config from MCP client, NOT from ~/.rag-memory-env
- You can edit ~/.rag-memory-env manually anytime

**STOP and wait for confirmation**

---

#### Step 11 - MCP Client Configuration

**If user chose "CLI only" → SKIP this step, go to Step 12**

[Read from .reference/MCP_QUICK_START.md]

**Ask:** "Which MCP client are you using?"
1. Claude Desktop
2. Claude Code
3. Cursor
4. Custom agent
5. Show me all options

**WAIT FOR RESPONSE**

**Based on choice:**
[Read appropriate section from .reference/MCP_QUICK_START.md]

**Show:**
1. Config file location
2. JSON config with BOTH environment variables:
   - `OPENAI_API_KEY`: User's API key
   - `DATABASE_URL`: `postgresql://raguser:ragpass@localhost:54320/rag_poc`
3. Explain that DATABASE_URL is for the default Docker setup (port 54320)
4. Instructions to save the config

**NEVER edit their config files - only show what to add**

**Important reminder:**
"The MCP server needs BOTH the OpenAI API key AND the database URL to function."

**STOP and wait for user to edit config**

---

#### Step 12 - Connection Test

**Present:**
"After editing the config, restart your AI agent (quit and reopen)."

**Ask:** "Have you restarted? (yes/no)"

**WAIT FOR RESPONSE**

**When yes:**

**Option A:** "Ask your AI agent: 'List available RAG collections'"

**Option B:** "Or I can test via CLI:"
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
rag collection create test-collection
rag ingest text "PostgreSQL with pgvector enables semantic search for AI agents. RAG Memory provides 11 MCP tools for document management." --collection test-collection
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
- MCP server users: "Your AI agent can now use all 11 RAG tools!"
- CLI users: "You can now use all CLI commands!"
- Both: "You have both MCP and CLI access!"

1. Ingest real documents (files, directories, websites)
2. Learn about web crawling
3. Understand document chunking
4. See complete MCP tools reference
5. Learn CLI commands
6. Troubleshooting
7. Ask specific questions

**WAIT FOR RESPONSE**

**Based on choice:**
1. [Read from CLAUDE.md ingestion commands section]
2. [Read from .reference/OVERVIEW.md web crawling section]
3. [Read from .reference/OVERVIEW.md chunking section]
4. [Point to .reference/MCP_QUICK_START.md tools section or docs/MCP_SERVER_GUIDE.md]
5. [Read from CLAUDE.md CLI commands section]
6. [Read from .reference/MCP_QUICK_START.md troubleshooting section]
7. [Answer from documentation as needed]

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
