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
