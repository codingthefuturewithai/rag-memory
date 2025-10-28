# Fly.io Scale-to-Zero Cold Start Issue

## Problem Summary

The RAG Memory MCP server deployed on Fly.io scales to zero when idle, causing 3-4 minute cold starts when waking from scaled-to-zero state. This is because:
1. Machine must be created and container fetched (~10-20 seconds)
2. Docker image rebuilt from scratch
3. Python environment initialized
4. FastMCP server starts up and loads all tools
5. Neo4j/PostgreSQL connections established

## Current Configuration (fly.toml)

```toml
[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true        # Scales to zero when idle
  auto_start_machines = true       # Restarts on demand
  min_machines_running = 0         # No machines kept running
  processes = ["app"]
```

## Impact

- **First request after idle period**: 3-4 minute delay or failure
- **User experience**: Very poor for AI agents accessing MCP tools
- **Reliability**: Client timeouts likely during cold start phase
- **Cost savings**: Only $0.50-1/month (negligible benefit for cost)

---

## Solution Options

### Option 1: Keep Server Always Active (Recommended for Active Development)

**Configuration:**
```toml
[http_service]
  auto_stop_machines = "off"        # Never stop
  auto_start_machines = true
  min_machines_running = 1          # Keep 1 running always
  processes = ["app"]
```

**Performance:** <100ms response times always

**Cost:** ~$3-5/month for continuous shared CPU/256MB

**Pros:**
- ✅ Sub-100ms response times always
- ✅ MCP tools available instantly
- ✅ Predictable costs
- ✅ Best for active AI agent usage

**Cons:**
- ❌ Machine paid for even when unused

---

### Option 2: Suspend Instead of Stop (Recommended - Testing This) ⭐ SELECTED

**Configuration:**
```toml
[http_service]
  auto_stop_machines = "suspend"    # Suspend (not stop) when idle
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]
```

**Performance:**
- Suspended machine startup: ~100-500ms (not 3-4 minutes)
- Trade-off: Accept brief initial latency for significant cost savings

**Cost:** ~$0.50-1/month (saves 80% vs always-running)

**Pros:**
- ✅ Fast startup (100-500ms, not 3-4 minutes)
- ✅ Much lower cost than always-running
- ✅ Good balance for occasional AI agent usage
- ✅ Machines only use RAM reservation when suspended (minimal cost)

**Cons:**
- ❌ First request to MCP tools will wait 100-500ms
- ❌ Limited Fly.io documentation on suspend behavior

---

### Option 3: Hybrid Approach (Minimum Running + Auto-Scale)

**Configuration:**
```toml
[http_service]
  auto_stop_machines = "stop"       # Stop excess machines only
  auto_start_machines = true
  min_machines_running = 1          # Always keep 1 running
  processes = ["app"]
```

**Performance:** <100ms for first request, auto-scales for traffic spikes

**Cost:** ~$3-5/month (same as Option 1 since min=1)

**Pros:**
- ✅ Instant response for MCP tools
- ✅ Auto-scales for traffic spikes
- ✅ Only slightly more expensive than suspend
- ✅ Most reliable for production use

**Cons:**
- ❌ Base cost ~$3-5/month minimum
- ❌ Additional machines cost more if traffic spikes

---

### Option 4: Aggressive Timeout for Suspend (Advanced - Theoretical)

**Configuration (if supported):**
```toml
[http_service]
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 0
  suspend_idle_timeout_sec = 3600   # Suspend after 1 hour idle
```

**Performance:** Same as Option 2, but with longer idle timeout before suspension

**Risk:** This setting may not exist in current Fly.io API (needs verification)

---

## Decision & Implementation

**Selected: Option 2 (Suspend)**

Rationale:
- 100-500ms cold starts acceptable for occasional AI agent usage
- Saves 80% of cost vs always-running ($0.50 vs $5/month)
- Significantly better than current 3-4 minute cold starts
- Easy to switch to Option 1 or 3 later if needed

**Status:**
- fly.toml updated for Option 2 (not yet deployed)
- Deployment pending to verify suspend performance
- If suspend performance unsatisfactory, easy rollback to Option 1

---

## Related Logs

Cold start measurements (updated 2025-10-20):
- Current behavior: 3-4 minutes (with scale-to-zero)
- Fly.io machines cold boot: ~300ms
- Stopped machine restart: <1 second (components already assembled)
- Created machine startup: ~10-20 seconds (needs container fetch + rebuild)

---

## Next Steps

1. ✅ Document all options (completed 2025-10-20)
2. ⏳ Update fly.toml for Option 2 (pending)
3. ⏳ Deploy to Fly.io and test
4. ⏳ Research Neo4j hosting solutions (in progress)
5. ⏳ Add Neo4j to cloud infrastructure

---

## Neo4j Hosting Research (Completed 2025-10-20)

**Requirements:**
- Cost-effective (~$50-100/month budget)
- Easy to manage (no ops overhead)
- Compatible with Graphiti
- Already have PostgreSQL at Supabase + MCP server at Fly.io

---

### Option A: Neo4j Aura Free Tier ⭐ RECOMMENDED

**What it is:** Neo4j's fully managed cloud database service (official offering)

**Free Tier:**
- ✅ No credit card required
- ✅ Runs 24/7 (no scaling to zero)
- ✅ Up to 50,000 nodes + 175,000 relationships
- ✅ Fully managed (zero ops)
- ✅ Automatic backups

**Cost:** $0/month

**Perfect for:**
- Development and testing
- Small to medium knowledge graphs
- Graphiti compatibility (native support)
- Zero operations overhead

**Limitations:**
- Limited to 50K nodes / 175K relationships (may hit limit with large ingestions)
- No SLA or premium support
- Data retention period unclear

**Setup:** Sign up at neo4j.com/cloud, create free instance, get connection string

---

### Option B: Neo4j Aura Professional

**What it is:** Fully managed service with performance guarantees

**Pricing:** Starting at $65/month per GB (minimum 1GB)

**Features:**
- ✅ Up to 128GB storage
- ✅ Daily backups + 7-day retention
- ✅ Professional support
- ✅ Multi-region options
- ✅ Fully managed

**Cost:** $65/month minimum (within budget)

**Perfect for:**
- Production deployments
- Larger knowledge graphs (500K+ nodes)
- SLA requirements
- When free tier becomes too small

---

### Option C: Self-Hosted Docker on Fly.io

**What it is:** Run Neo4j as Docker container on same Fly.io infrastructure

**Pros:**
- ✅ All in one place (MCP + Neo4j on Fly.io)
- ✅ Same Fly.io bill
- ✅ No vendor lock-in (portable)
- ✅ Full control over configuration

**Cons:**
- ❌ You manage infrastructure/backups/scaling
- ❌ More operational overhead
- ❌ Requires persistent storage (additional cost)
- ❌ Manual monitoring/maintenance

**Cost:** ~$15-30/month (1 MCP + 1 Neo4j machine + storage)

**Setup complexity:** Moderate (need Dockerfile, volumes, environment config)

**Current status:** Not evaluated in detail (requires more research on Fly.io persistent storage)

---

### Option D: Self-Hosted Docker on DigitalOcean Droplet

**What it is:** Cheapest self-hosted option using third-party provider

**Cost:** $4-12/month (basic droplet)

**Pros:**
- ✅ Extremely cheap
- ✅ Full control
- ✅ Separate from MCP server (isolation)

**Cons:**
- ❌ Manual backups/maintenance
- ❌ You manage everything
- ❌ Need to manage SSH keys, firewalls
- ❌ No auto-scaling

**Setup complexity:** High (requires DevOps knowledge)

---

### Option E: Elestio (Managed Docker)

**What it is:** Managed wrapper around self-hosted Docker

**Features:**
- ✅ Managed Neo4j instance
- ✅ Automatic backups
- ✅ Security/encryption/monitoring
- ✅ OS + software updates handled
- ✅ Firewall management

**Pricing:** Similar to managed services (~$50-100/month estimated)

**Pros:**
- ✅ Best of both worlds (managed + self-hosted flexibility)
- ✅ Portable between providers
- ✅ Good support

**Cons:**
- ❌ Less mature than Neo4j Aura
- ❌ Pricing not clearly listed online

---

### Option F: GrapheneDB (Alternative Managed Service)

**What it is:** Alternative Neo4j hosting platform

**Status:** Appears to be older/less actively maintained compared to Aura

**Pricing:** Not clearly listed, appears premium

**Recommendation:** Skip unless Aura unavailable

---

## Recommendation Summary

### Development/Testing: **Option A (Neo4j Aura Free)**
- $0/month
- Perfect for your current work with Graphiti
- 50K nodes should handle significant knowledge graphs
- Switch to Professional when you hit limits
- **Action:** Create free instance at neo4j.com/cloud

### Production Ready: **Option B (Neo4j Aura Professional)**
- $65/month (within budget)
- Same managed platform as free tier (no migration)
- Professional support + SLA
- Easy upgrade path from free tier
- **Action:** Upgrade free tier when needed

### Cost Conscious: **Option C (Self-Hosted on Fly.io)**
- $15-30/month (all-in with MCP)
- More work required
- **Action:** Investigate Fly.io persistent volumes (not yet researched)

### Absolute Budget: **Option D (DigitalOcean + Docker)**
- $4-12/month
- Requires DevOps expertise
- **Action:** Only if Aura free tier insufficient and budget critical

---

## Implementation Plan

### Phase 1: Start with Neo4j Aura Free ⭐ NOW

**Rationale:** Get everything running in cloud immediately with minimal setup

**Actions:**
1. ✅ Sign up for Neo4j Aura Free at neo4j.com/cloud
2. ✅ Create free instance (no credit card required)
3. ✅ Get connection string
4. ✅ Update environment files (.env, .env.dev, .env.test)
5. ✅ Update Graphiti configuration to use Aura connection
6. ✅ Test ingestion and queries
7. ✅ Deploy MCP server to Fly.io (with suspend option - Option 2)
8. ✅ Verify Supabase PostgreSQL is configured
9. ✅ Test full stack: MCP → Graphiti → Aura + Supabase RAG

**Timeline:** 2-3 hours to get everything running
**Cost:** $0 (Aura Free) + $25-35 (Supabase Pro) + $5-10 (Fly.io MCP + suspend)
**Status:** ✅ Production-ready for immediate AI agent use

### Phase 2: Monitor Usage (After 2-4 weeks)

**Decision points:**
- Is knowledge graph < 50K nodes? → Stay on Aura Free
- Is knowledge graph hitting 50K limit? → Upgrade to Aura Professional ($65/month)
- Want to consolidate infrastructure? → Move to Fly.io (proceed to Phase 3)

### Phase 3: Advanced Setup (Optional, when needed)

**When to consider moving Neo4j to Fly.io:**
- Knowledge graph significantly exceeds 50K nodes
- Need backup automation with restore points
- Want to consolidate all infrastructure on one vendor
- Cost optimization important after months of usage

**For Fly.io Neo4j deployment:**
- See `docs/NEO4J_BACKUP_STRATEGIES.md` for comprehensive backup automation
- Option 2 (Local backups) recommended: $0 additional cost, 30-day recovery window
- Option 3 (S3 backups) for mission-critical: +$1-5/month, 90-day recovery

**Migration path:**
1. Set up Neo4j on Fly.io with automated backups (docs/NEO4J_BACKUP_STRATEGIES.md)
2. Export data from Aura Free
3. Import data to Fly.io Neo4j
4. Update Graphiti connection string
5. Decommission Aura Free instance

---

## Current Stack (Phase 1 - Recommended Now)

```
┌──────────────────────────────────────────┐
│ AI Agents (Claude Desktop, etc.)         │
│ └─ MCP Server: rag-memory                │
└──────────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│ Fly.io (One Vendor)                      │
├──────────────────────────────────────────┤
│ Machine 1: MCP Server                    │
│   ├─ FastMCP framework                   │
│   ├─ Graphiti client                     │
│   ├─ RAG search (pgvector)               │
│   └─ $5/month (suspend on idle)          │
└──────────────────────────────────────────┘
        ↙                      ↘
      RAG                    Graph
        ↙                      ↘
┌──────────────────┐   ┌──────────────────┐
│ Supabase         │   │ Neo4j Aura       │
├──────────────────┤   ├──────────────────┤
│ PostgreSQL       │   │ Graph DB         │
│ pgvector         │   │ Graphiti         │
│ ~$25-35/month    │   │ $0/month (Free)  │
└──────────────────┘   └──────────────────┘

Total Monthly Cost: ~$30-40
Vendors: 2 (Fly.io for compute, Aura for managed Neo4j)
Setup Time: 2-3 hours
Reliability: High (managed services + automated Fly backups)
```

---

## Future Stack (Phase 3 - Infrastructure Consolidation)

```
┌──────────────────────────────────────────┐
│ AI Agents                                │
│ └─ MCP Server: rag-memory                │
└──────────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────┐
│ Fly.io (Single Vendor)                   │
├──────────────────────────────────────────┤
│ Machine 1: MCP Server                    │
│   ├─ FastMCP framework                   │
│   ├─ Graphiti client                     │
│   └─ $5/month (suspend)                  │
├──────────────────────────────────────────┤
│ Machine 2: Neo4j Database                │
│   ├─ Neo4j graph database                │
│   ├─ Automated backups (Option 2)        │
│   └─ $5/month                            │
├──────────────────────────────────────────┤
│ Persistent Storage                       │
│   ├─ Neo4j data + 30-day backups         │
│   └─ $1.50/month (10GB @ $0.15/GB)       │
└──────────────────────────────────────────┘
        ↙
      RAG
        ↙
┌──────────────────┐
│ Supabase         │
├──────────────────┤
│ PostgreSQL       │
│ pgvector         │
│ ~$25-35/month    │
└──────────────────┘

Total Monthly Cost: ~$37-47 (saves $46-69/month vs Aura Pro)
Vendors: 2 (Fly.io for compute+Neo4j, Supabase for RAG)
Reliability: High (automated backups + Fly snapshots)
Complexity: Medium (backup management required)
```
