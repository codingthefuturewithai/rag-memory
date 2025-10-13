# Deploying Your Crawl4AI-Based MCP Server to Fly.io (with Supabase + SSE/Streamable HTTP)

> This guide walks you from a **working local MCP server** (with Docker Compose and PostgreSQL) to a **production deployment on Fly.io**, using **Supabase** for your database, **Crawl4AI** for web crawling, and **SSE/Streamable HTTP** for MCP client connections.
>
> Assumes:
> - MCP server already supports all three transports: **stdio**, **SSE**, and **Streamable HTTP**.
> - Local testing confirmed via Docker.
> - Database successfully migrated to **Supabase**.
> - You have the **Fly CLI** installed and a **Fly.io account**.
> - You’re based on the U.S. East Coast → region = `iad` (Ashburn, VA).

---

## 🧩 1. Prerequisites

### ✅ Install required tools
```bash
# Fly CLI
curl -L https://fly.io/install.sh | sh

# Log in to Fly
flyctl auth login
```

### ✅ Confirm Docker setup
Ensure your Dockerfile successfully builds and runs locally:
```bash
docker build -t my-mcp-server .
docker run -p 8000:8000 my-mcp-server
```

Your server should start and respond to HTTP/SSE requests at `http://localhost:8000`.

---

## 🏗️ 2. Dockerfile (Playwright + Crawl4AI Base)

Use Microsoft’s official Playwright image as your base. It includes Chromium and dependencies required by Crawl4AI.

```dockerfile
# Dockerfile
FROM --platform=linux/amd64 mcr.microsoft.com/playwright:v1.44.0-jammy

WORKDIR /app
COPY . /app

# Install Python dependencies (including Crawl4AI and your MCP server)
RUN pip install -U pip \
    && pip install crawl4ai==<version> \
    && pip install -r requirements.txt

# Environment
ENV PORT=8000
EXPOSE 8000

# Avoid re-downloading browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Run your MCP server
CMD ["python", "-m", "your_mcp_server_module"]
```

✅ This image:
- Runs Crawl4AI and Playwright fully in headless mode.
- Works identically locally and in Fly.
- Supports outbound HTTP/S (for crawling websites) and inbound SSE/Streamable HTTP.

---

## 🌎 3. Create and configure your Fly.io app

### Step 1: Launch app
```bash
flyctl launch --region iad --name my-mcp-server
```
When prompted:
- **App name**: choose something unique, e.g. `my-mcp-server`
- **Region**: `iad`
- **Deploy now?** → choose **No** (you’ll set secrets first)

This creates two files:
- `fly.toml` → Fly configuration
- `.dockerignore` → optional ignore rules

---

### Step 2: Add environment secrets

Set your Supabase connection string and other configuration values:
```bash
flyctl secrets set DATABASE_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
flyctl secrets set PORT=8000
```

You can verify your secrets later with:
```bash
flyctl secrets list
```

---

### Step 3: Verify your Fly configuration (`fly.toml`)

Open the generated `fly.toml` and ensure it contains:

```toml
app = "my-mcp-server"
primary_region = "iad"
kill_signal = "SIGINT"
kill_timeout = "5s"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"

[[services]]
  internal_port = 8000
  processes = ["app"]

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

  [services.concurrency]
    hard_limit = 25
    soft_limit = 20
    type = "connections"
```

✅ This config ensures:
- Your MCP server listens on port 8000.
- HTTPS (TLS) and SSE/Streamable HTTP are supported.
- The app runs in the U.S. East (`iad`) region.

---

## 🚀 4. Deploy your MCP server

```bash
flyctl deploy
```

The Fly builder packages your Docker image, uploads it, and deploys it to a VM in the `iad` region.

Once deployed, Fly gives you a public HTTPS URL, for example:
```
https://my-mcp-server.fly.dev
```

This URL now supports:
- `GET /sse` → SSE transport
- `POST /rpc` → Streamable HTTP transport
- `stdio` → still available for local dev

---

## ⚙️ 5. Enable scale-to-zero (optional but recommended)

If you’re only using your MCP server occasionally (e.g. 2 hours/day):

### Option A — Scale manually via CLI
```bash
flyctl scale count 0   # stop when not using
flyctl scale count 1   # start when needed
```

### Option B — Auto stop/start with Machines

Use **Fly Machines** (the newer runtime) to configure automatic idle shutdown.
```bash
flyctl apps create my-mcp-server
flyctl machine run . \
  --region iad \
  --auto-start \
  --auto-stop \
  --name my-mcp-machine
```
This lets the instance sleep when idle and wake instantly when a request arrives.

📘 Docs: [Fly Machines Auto-Stop](https://fly.io/docs/machines/autostop/)

---

## 🌐 6. Test your deployment

### SSE Test
```bash
curl -N -H "Accept: text/event-stream" https://my-mcp-server.fly.dev/sse
```

### Streamable HTTP Test
```bash
curl -X POST https://my-mcp-server.fly.dev/rpc \
  -H "Content-Type: application/json" \
  -d '{"method":"ping","params":{}}'
```

If you receive a valid JSON response or stream, you’re live.

---

## 🧠 7. Using your MCP server from ChatGPT or agents

In ChatGPT (or your custom agent configuration):
```json
{
  "url": "https://my-mcp-server.fly.dev",
  "transport": "sse",
  "description": "Crawl4AI-powered web analysis and similarity search MCP server."
}
```

Both **SSE** and **Streamable HTTP** will work; SSE is the most compatible with ChatGPT as of 2025.

---

## 🧩 8. Cost overview (Fly.io + Supabase)

| Component | Description | Est. Cost/Month |
|------------|--------------|----------------:|
| Fly.io (Machines) | 1 small app, scaled to zero | $0–$5 |
| Supabase | Managed PostgreSQL + pgVector | $25–$50 |
| DNS/SSL | Free via Fly.io | $0 |
| Total | **≈ $25–$55/mo** depending on DB usage |

---

## 🧰 9. Maintenance Tips

- Redeploy new versions: `flyctl deploy`
- View logs: `flyctl logs`
- SSH into VM: `flyctl ssh console`
- Set new env vars: `flyctl secrets set VAR=value`
- Remove: `flyctl apps destroy my-mcp-server`

---

## ✅ Summary

| Step | Action |
|------|---------|
| 1 | Confirm local MCP server works via Docker |
| 2 | Use Playwright base image for Crawl4AI |
| 3 | Create Fly.io app (`iad` region) |
| 4 | Set Supabase `DATABASE_URL` secret |
| 5 | Deploy via `flyctl deploy` |
| 6 | Test SSE + Streamable HTTP endpoints |
| 7 | Optionally enable auto-stop for scale-to-zero |
| 8 | Connect from ChatGPT or agents |

---

### 🔗 References
- Fly.io Docker Deployments: https://fly.io/docs/app-guides/dockerfile/
- Fly Machines Auto Start/Stop: https://fly.io/docs/machines/autostop/
- Playwright Docker Images: https://playwright.dev/docs/docker
- Supabase PostgreSQL Connections: https://supabase.com/docs/guides/database/connecting-to-postgres

---

**Result:** Your MCP server (with Crawl4AI + Supabase + SSE/Streamable HTTP) runs reliably on Fly.io, scales down when idle, and stays fully compatible with ChatGPT and your AI agents.