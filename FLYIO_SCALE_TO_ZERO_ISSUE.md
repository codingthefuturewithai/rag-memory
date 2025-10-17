# Fly.io Scale-to-Zero Cold Start Issue

## Problem Summary

The RAG Memory MCP server deployed on Fly.io experiences connection failures when waking from auto-scaled-to-zero state. The cold start process takes 15-20 seconds, during which client connections fail.

## Observed Behavior

### Timeline of Cold Start
1. **t=0s**: Client request arrives, triggers machine start
2. **t=0-7s**: Machine boots, server process starts, health check fails
3. **t=7-13s**: Server initializes RAG components (DB, embeddings, collections)
4. **t=13-20s**: Health check passes, server ready

### Connection Errors During Cold Start
- **Early connections (t=0-7s)**: "server closed connection unexpectedly"
- **Mid-startup (t=7-13s)**: Timeouts or connection refused
- **Some clients**: "405 Method Not Allowed" (POST instead of GET to /sse endpoint)

### After Warm-Up
- Server responds normally
- All MCP tools work as expected
- Performance is good

## Root Causes

1. **Long cold start time**: 15-20 seconds from sleep to ready
   - Firecracker VM boot: ~1s
   - Python process start: ~6s
   - RAG component initialization: ~6s
   - Health check validation: ~7s

2. **No graceful queueing**: Requests during startup are rejected rather than queued

3. **Health check timing**: Health checks fail initially, causing proxy to report service unavailable

## Impact

- **First request after idle**: 15-20 second delay or failure
- **User experience**: Appears broken until second retry
- **Demo risk**: Need to "warm up" server before showing functionality

## Current Workaround

**Before demo/usage:**
```bash
# Warm up the server with a simple request
curl https://rag-memory-mcp.fly.dev/sse
# Or make any MCP tool call and wait 20 seconds
```

## Potential Solutions

### Option 1: Disable Auto-Scaling (Simplest)
```toml
# In fly.toml
[http_service]
  auto_stop_machines = false  # Keep running 24/7
  min_machines_running = 1
```
**Cost**: ~$5/month vs ~$1/month
**Benefit**: No cold starts, instant response

### Option 2: Reduce Cold Start Time
- Use smaller base image (alpine instead of Playwright)
- Lazy-load components (don't initialize DB connection until first request)
- Pre-warm connections during health check

### Option 3: Configure Load Balancer Retries
```toml
# In fly.toml
[http_service]
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0
  [http_service.concurrency]
    type = "requests"
    soft_limit = 200
    hard_limit = 250
```

### Option 4: Add Request Queueing
- Implement server-side request queue
- Hold connections during startup
- Return 503 with Retry-After header

## Recommendation

**For demo**: Use Option 1 (disable auto-scaling) to ensure reliability

**For production**:
1. Implement Option 2 (reduce cold start time to <5s)
2. Add Option 4 (request queueing)
3. Keep auto-scaling enabled for cost efficiency

## Related Logs

Latest cold start observed: 2025-10-17T13:21:33Z
- Machine start: 13:21:33
- Server ready: 13:21:41 (8 second startup)
- Health pass: 13:22:00 (27 seconds total)

## Status

- **Issue identified**: 2025-10-17
- **Workaround documented**: Yes
- **Permanent fix**: Pending (post-demo)
- **Priority**: Medium (affects UX but has workaround)
