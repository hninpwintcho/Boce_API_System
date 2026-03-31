# 🔱 Boce Unified Detection Proxy | Business Edition (v4)

Welcome to the **Enterprise Monitoring Platform**. This is the **Business Level** graduation of the Boce Detection Proxy, redesigned for high-volume commercial throughput, multi-tenant isolation, and automated asynchronous lifecycle management.

---

## 🧠 1. Core Business Logic (Architectural Step-by-Step)

The "Business Level" standard is built on three pillars of engineering excellence:

### ✨ Step 1: Request Ingress & Isolation
1.  **Authentication**: Every request must carry an `X-API-KEY`. The system identifies the business unit, checks its **is_active** status, and retrieves its **daily_quota**.
2.  **Validation**: URL patterns and JSON schemas are strictly validated BEFORE any points are spent or database resources are allocated.
3.  **Point-Safe Assurance**: Before accepting a task, the platform performs a **Pre-check** with the Boce balance API. It calculates the `total_cost` (e.g., 1 point per domain) and rejects the request immediately if the balance is insufficient, protecting your application from 502/504 external errors.

### ✨ Step 2: High-Performance Bulk Data Ingestion
1.  **Bulk Buffering**: When you submit 5,000 domains via `/api/detect/batch`, the system iterates through the list and flags invalid URLs as "skipped".
2.  **Chunked Persistence (2000 per write)**: To prevent blocking the API or causing SQLite lock-timeouts, the platform writes tasks in atomic chunks of 2,000 records using `executemany`.
3.  **Job Queuing**: Each task is assigned a `batch_id` and marked as `pending`. This ensures the API returns in **milliseconds**, even for massive volumes.

### ✨ Step 3: Priority-Aware Orchestration (The Brain)
1.  **Continuous Polling**: A background **Priority Scheduler** scans the `detection_tasks` table.
2.  **Strategic Retrieval**: It fetches tasks ordered by `priority DESC` and `created_at ASC`. Your urgent business requests jump the queue ahead of large background crawl batches.
3.  **Concurrency Management**: Tasks are dispatched to asynchronous workers, ensuring high-concurrency external detection without stalling the main API thread.

### ✨ Step 4: Hierarchical Webhook Propagation
1.  **The Trigger**: Upon task completion (Success or Failure), the system generates a result payload.
2.  **The Dispatcher**: 
    -   If the **task** provided a `webhook_url`, it is used.
    -   If not, the system uses the **Account Default Webhook** configured for that API key.
3.  **Reliability**: A delivery worker ensures your business application is notified via `POST` with a JSON payload, including the full detection results and global availability metrics.

---

## ⚙️ 2. Installation & Setup

### 🐳 Method A: Docker Compose (Recommended)
The platform is optimized for Docker, providing auto-recovery and volume persistence.

1.  **Clone & Configure**: Ensure `.env` contains your `BOCE_API_KEY`.
2.  **Deploy**:
    ```bash
    docker-compose up --build -d
    ```
3.  **Check Health**:
    ```bash
    docker ps --filter "name=boce-api-v4"
    ```
    *(Look for the `(healthy)` status!)*

### 🐍 Method B: Local Python Installation
Use this for debugging or development.

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Initialize & Run**:
    ```powershell
    # Windows
    python -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
    ```
3.  **Setup Keys**: Run `python setup_keys.py` to generate your initial `sk-` business keys.

---

## 🌐 3. Usage Guide: Domain Checking

### ✅ Single Domain Submission
Ideal for low-latency ad-hoc checks.
```powershell
Invoke-RestMethod -Uri "http://localhost:3000/api/detect/detect" `
  -Method Post `
  -Headers @{"X-API-KEY"="sk-test-points-safe-12345"} `
  -ContentType "application/json" `
  -Body '{"url": "http://example.com"}'
```

### ✅ Industrial Bulk Submission (5,000+ Domains)
High-volume ingestion for commercial crawling.
```powershell
Invoke-RestMethod -Uri "http://localhost:3000/api/detect/batch" `
  -Method Post `
  -Headers @{"X-API-KEY"="sk-test-points-safe-12345"} `
  -ContentType "application/json" `
  -Body '{"urls": ["http://domain1.com", "http://domain2.com"], "webhook_url": "http://your-app.com/callback"}'
```
*Note: This returns a `batch_id` instantly.*

### ✅ Monitoring Progress & Stats
```powershell
# Get Summary Dashboard Data
Invoke-RestMethod -Uri "http://localhost:3000/api/stats/summary" -Headers @{"X-API-KEY"="..."}

# Track Specific Batch Progress
Invoke-RestMethod -Uri "http://localhost:3000/api/detect/batch/<BATCH_ID>/progress" -Headers @{"X-API-KEY"="..."}
```

---

## ✅ 4. Verification & Diagnostics

1.  **System Health**: Access `http://localhost:3000/` – it should redirect to the **Visual Dashboard**.
2.  **Database Integrity**: Check `boce_api.db` (SQLite). 
    - Table `api_keys`: Contains business unit configurations.
    - Table `detection_tasks`: Contains the high-volume task ledger.
3.  **API Key Verification**:
    ```powershell
    # This should fail with 403 (No Key)
    Invoke-WebRequest -Uri "http://localhost:3000/api/detect/history"
    ```

---

## 🏁 Enterprise Conclusion
The system is now **Wallet Ready** and **Audit Compliant**. It ensures your detection infrastructure is as reliable as the business it supports.

**Project Status: Ready for Production.** 🚀💎

---
*Developed for hninpwintcho by Antigravity AI.*



This is another project "Your Project: boce-aggregated-api-system
What is the project?
This is a Node.js + TypeScript backend API that your boss ordered built. Its purpose:

Wrapper/aggregator around Boce.com — a Chinese website monitoring service. It tests websites from multiple locations in China (DNS, speed, HTTP status, etc.) and gives you a unified, standardized result.

Think of it like a quality inspector: you ask "Is www.baidu.com healthy from China?" — it sends probes from 许多 nodes (Node 31 = Fujian, Node 32 = elsewhere), collects results, calculates availability rates, detects anomalies, and returns clean JSON.

📂 Project Architecture
boce-aggregated-api-system/
├── src/
│   ├── app.ts              ← Express app setup
│   ├── index.ts            ← Start HTTP server (port 3000)
│   ├── config/             ← Env variables (API keys, ports, etc.)
│   ├── middleware/         ← Rate limiting (30 req/min)
│   ├── routes/             ← HTTP endpoints (/api/detect, /health)
│   ├── services/
│   │   ├── boce/           ← Calls Boce.com API (create task, poll result)
│   │   ├── detection/      ← Normalizes + calculates metrics + anomalies
│   │   ├── queue/          ← BullMQ + Redis (async job queue)
│   │   └── db/             ← Postgres (saves detection history)
│   ├── types/              ← TypeScript type definitions
│   └── mcp/
│       └── server.ts       ← 🤖 MCP server (explained below!)
├── Dockerfile              ← Container for production
├── docker-compose.yml      ← Runs app + Redis + Postgres together
└── package.json
🔄 How a Request Flows
Your Client (curl/app)
       │
       ▼
POST /api/detect  ──→  Boce.com API (create task)
                           │
                       poll every 10s (max 2min)
                           │
                       get results from nodes
                           │
                  normalize → metrics → anomaly detection
                           │
                      save to Postgres
                           │
                  return JSON response to you
🤖 MCP Server — What is it?
MCP = Model Context Protocol

This is the most modern and exciting part of your project! Let me explain it step by step.

🧠 The Problem MCP Solves
Normally, an AI like Claude or ChatGPT only knows what you type to it. It cannot call your APIs or run code on its own. So if you ask it "Is www.baidu.com healthy right now?" — it would say "I don't know, I can't check."

MCP fixes this. It gives AI assistants a standardized way to call your backend tools.

📡 How MCP Works (Simple Analogy)
Without MCP:
   You → AI Chat → "I don't know, can't check"
With MCP:
   You → AI Chat → [AI calls your MCP Server] → Your API → Real Data → AI answers!
Think of MCP as a waiter between your AI assistant and your backend kitchen.

🛠️ Your MCP Server Has 4 Tools
Tool	What it does
certificate_summary	Checks if a website's SSL certificate is valid/expiring
boce_probe_summary	Probes a domain from Chinese nodes via Boce.com
investigate_domain	Combines cert + probe into one full investigation report
investigate_domains_batch	Investigates up to 20 domains at once (parallel)
💻 Your MCP Server Has 2 Modes
Mode	Command	Use case
stdio	npm run mcp:start:stdio	Local debug in Cursor IDE
HTTP	npm run mcp:start	Remote AI clients connect via http://localhost:3010/mcp
🔌 Practical Example: Cursor IDE Integration
Your .cursor/mcp.json config (already in your project!) lets Cursor IDE automatically use these tools. You can type in Cursor chat:

Call MCP tool investigate_domain with {"domain":"www.baidu.com","nodeIds":"31,32"}
And Cursor will call your 

src/mcp/server.ts
, which calls Boce.com, and return a real result like:

domain: www.baidu.com
final_status: HEALTHY
availability_rate: 1.0
certificate_ok: true
days_remaining: 142
🗺️ Technology Stack Summary
Technology	Role
TypeScript/Node.js	Main language + runtime
Express.js	HTTP web server
Redis + BullMQ	Async job queue (don't block while waiting for Boce)
PostgreSQL	Store detection history
Docker Compose	Run everything together easily
@modelcontextprotocol/sdk	The MCP library — lets AI agents use your tools
Zod	Validate inputs (type-safe)
🎯 Summary (Boss's Vision)
Your boss built a system where:

Any client can call /api/detect to check website health from China
Async queue handles bulk jobs without timeouts
Postgres stores history so you can track health over time
MCP server lets AI agents (Claude, Cursor, etc.) automatically investigate domains by calling your tools — making the system "AI-agent ready"
This is a commercial-grade platform — it has auth, rate limiting, webhooks, pagination, and AI integration all in one project. Very impressive boss requirements! 🎉

