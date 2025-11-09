---
description: Audit .reference/ directory to ensure all implementation claims match actual source code
argument-hint: ""
allowed-tools: ["Read", "Grep", "Glob", "Bash", "Edit"]
---

# Reference Audit

I'm going to audit the .reference/ directory to verify all implementation claims match the actual source code.

## What .reference/ Contains

The .reference/ directory has 10 files for teaching new users about RAG Memory:

1. **WHAT_IS_IT.md** - Conceptual overview
2. **INSTALLATION.md** - Docker setup and verification
3. **CLI_GUIDE.md** - CLI command reference
4. **MCP_GUIDE.md** - MCP server setup and tools
5. **VECTOR_SEARCH.md** - Semantic search technical details
6. **KNOWLEDGE_GRAPH.md** - Graph features and usage
7. **CONFIGURATION.md** - Config files and environment variables
8. **TROUBLESHOOTING.md** - Common errors and solutions
9. **CLOUD_SETUP.md** - Cloud deployment guide
10. **README.md** - Navigation and quick reference

## What I'm Going to Do

For each file, I'll:

1. **Read it** to identify implementation claims (ports, database names, tool counts, chunk sizes, config paths, etc.)
2. **Find the source code** where those claims should be verified
3. **Verify accuracy** by reading the actual source
4. **Fix any errors** immediately
5. **Report briefly** what I found and fixed

I'll focus on verifiable facts about RAG Memory's implementation - things like:
- Configuration values (database URLs, ports, passwords)
- Technical specifications (embedding model, dimensions, chunk sizes)
- Tool and command counts and names
- Docker setup details (container names, volume names)
- File paths and directory structures

I won't verify general knowledge about vector stores, semantic search, or how external tools work.

## How I'll Verify

I'll discover where things are in the codebase by searching for them. I won't assume anything is in a specific location - I'll find it.

When I'm done, I'll give you a short summary for each file showing:
- What claims I verified
- What errors I found and fixed
- Evidence available if you want to see it

Starting the audit now.
