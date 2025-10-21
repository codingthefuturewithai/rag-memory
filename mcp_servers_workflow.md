# MCP Servers Overview for Your Application Users  
*Purpose*: Let your users provision, bootstrap, and later query/manage their cloud‑databases via agents — without you building custom MCP servers.

## 1. Supabase (Postgres + pgvector)  
### Capabilities  
- Hosted MCP server: `https://mcp.supabase.com/mcp`  
- Supports full tool‑groups: project creation, database creation, migrations, branching, SQL execution, docs generation.  
- Query parameters:  
  - `project_ref=<ref>` — scope to a specific project.  
  - `read_only=true|false` — disable mutating tools & run SQL in read‑only mode.  
  - `features=<comma‑list>` — limit the tool‑groups exposed (e.g., `database,development,docs`).  
- Provides a Management API (GA) for project create/manage.  
- Supabase emphasises: the hosted MCP is a **developer tool**, not necessarily meant directly for end‑users. They recommend wrapping the Management API if providing self‑service.  

### How it fits your workflow  
1. **Provision phase (write enabled)**  
   - Use MCP URL with no `project_ref`, `read_only=false`, and `features=account,database,branching`.  
   - Agent calls:  
     - `get_cost` → `confirm_cost`  
     - `create_project(org, name, region, plan)`  
     - Poll until ready → obtain `project_ref`  
     - `apply_migration`‑tool: enable `pgvector`, create schema, tables, indexes, seed data.  
2. **Lockdown phase (read‑only management)**  
   - Switch agent to: `https://mcp.supabase.com/mcp?project_ref=<PROJECT_REF>&read_only=true&features=database,development,docs`  
   - Allows user/agent to: query data, introspect schema, generate types, but **no mutations**.  
   - If later a schema change is required: temporarily drop `read_only=true`, optionally add `branching`, apply migration, then reenable read‑only.  
3. **Day‑2 operations**  
   - The agent can expose “run query”, “inspect performance”, “list tables”, “generate Typescript types” via the `database` + `development` tool groups.  
   - Mutations remain disabled unless explicitly enabled for a maintenance window.

### Notes / Safety  
- Keep user‑facing agent prompts **targeted**: only allow predefined bootstrap schema + roles + RLS.  
- Enforce *manual approval* of mutating tools (Supabase strongly recommends this).  
- Use minimal privileges for the service‑role keys you hand to the users.  
- Keep the “write‐enabled” window as short as possible.

### Primary Sources  
- Supabase MCP guide: https://supabase.com/docs/guides/getting-started/mcp  
- Supabase MCP repo: https://github.com/supabase-community/supabase-mcp  
- Supabase Management API: https://supabase.com/docs/reference/api/introduction  

---

## 2. Neo4j Aura  
### Capabilities  
- Vendor‑maintained MCP servers:  
  - `mcp-neo4j-cloud-aura-api` — create/scale/pause/resume/delete Aura instances.  
  - `mcp-neo4j-cypher` — natural‑language → Cypher, read/write support.  
  - `mcp-neo4j-data-modeling` — schema/model visualization + management.  
- Official Aura REST API: OAuth credentials, programmatically create instances.  

### How it fits your workflow  
1. **Provision phase**  
   - Agent calls: `create_instance(name, memory_size, region, gds_enabled)` via the Aura MCP server.  
   - Poll until instance is ready; return connection URI + credentials.  
   - Use `mcp-neo4j-cypher` to bootstrap: create nodes/relationships, indexes, seed data.  
2. **Day‑2 operations / query phase**  
   - Agent uses `mcp-neo4j-cypher` for read/write queries (if you allow), or just read if you restrict.  
   - Use `mcp-neo4j-data-modeling` for schema inspection, evolution planning, change tracking.  
3. **Manage & scale**  
   - Via `mcp-neo4j-cloud-aura-api`: `pause_instance`, `resume_instance`, `scale_instance`, `delete_instance`.  
   - Agent can monitor status and metrics, warn when limits approached.

### Primary Sources  
- Neo4j MCP GitHub org: https://github.com/neo4j-contrib/mcp-neo4j  
- Neo4j Aura creation tutorial: https://neo4j.com/docs/aura/tutorials/create-auradb-instance-from-terminal/  

---

## 3. Fly.io (application hosting + logs + config)  
### Capabilities  
- Fly offers an MCP server via their CLI (`flyctl`) which can run as a server and expose MCP‑style tools for agents.  
- Supported tool families: `apps`, `machines`, `secrets`, `certs`, `logs`, `status`, `volumes`, `orgs`.  
- Agent can: deploy an app, change config, rotate secrets, view logs, inspect status, scale machines/containers.

### How it fits your workflow  
1. **Provision / deploy**  
   - Agent uses MCP server to `apps.create(name, region, runtime)`, `deploy`, `machines.scale`, `secrets.set`.  
   - Returns URL/endpoint and access credentials.  
2. **Day‑2 operations / monitoring**  
   - Agent uses `logs.tail(app)`, `status.check(app)`, `secrets.rotate(app)`, `machines.list(app)`.  
   - Can alert user if errors spike in logs or CPU/memory metrics rise.  
3. **Configuration changes / upgrades**  
   - Agent uses `config.update(app, key, value)`, `machines.scale(app, count)`, `certs.create(app)`.  
   - Optionally lock certain actions behind human approval.

### Primary Sources  
- Fly.io MCP docs: https://fly.io/docs/mcp/  

---

# Summary Table

| Platform     | Bootstrap (write‑enabled)                    | Day‑2 (Query/Manage)                        | Key Points                                 |
|--------------|---------------------------------------------|---------------------------------------------|--------------------------------------------|
| Supabase     | Create project → enable `pgvector` → load schema | Switch to read–only, scoped project         | Hosted MCP works; vendor recommends wrapping for end‑users |
| Neo4j Aura   | Create instance → load schema via Cypher     | Query, model, scale, pause/resume           | Mature agent‑friendly tooling via MCP      |
| Fly.io       | Deploy app, configure secrets, scale machines| Tail logs, view status, change config       | Good agent‑tooling; full app host ICP      |

---

# Next Steps for Your Coding Assistant  
- Set up MCP clients for each URL and configure authentication (OAuth tokens) per user.  
- Parameterize the bootstrap workflow (region, plan size, initial schema bundle) so agent can ask user minimal questions.  
- Ensure mutating tools are **approved by user** (or your service) before execution.  
- In your agent’s UI, expose a “Provision new database/app” flow, followed by a “Monitor / Query / Maintenance” mode.  
- Store returned credentials securely, expire tokens as needed, rotate service roles/keys.  
- Document your service’s user‑facing prompts so the agent can ask: “Would you like me to enable `pgvector`, create tables X,Y,Z, seed data, and then lock your project to read‑only?”  
- For each platform, include fallback: “If an error occurs, please check the vendor console.”