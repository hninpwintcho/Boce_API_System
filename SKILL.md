---
name: boce-domain-check
description: Check domain availability across China's network using the Boce detection proxy. Use when asked to check if a domain/URL is accessible, detect DNS hijacking, verify CDN health, or batch-check multiple domains. Supports balance checking, batch submission with progress tracking, and scheduled monitoring.
---

# Boce Domain Check

## Overview

Use this skill to check whether domains/URLs are accessible from multiple regions in China via Boce detection nodes. Supports single checks, batch checks (up to 5000 domains), balance monitoring, and progress tracking.

## Authentication

Use API Key authentication via header:
```
X-API-KEY: <BOCE_PROXY_API_KEY>
```
Read from environment variable: `BOCE_PROXY_API_KEY`

## Quick Workflow

### Single Domain Check
1. Check balance first: `GET /api/balance`
2. Submit domain: `POST /api/detect` with `{"url": "https://example.com"}`
3. Poll result: `GET /api/detect/{task_id}`

### Batch Domain Check (100–5000 domains)
1. Check balance: `GET /api/balance`
2. Submit batch: `POST /api/detect/batch` with `{"urls": ["url1", "url2", ...]}`
3. Track progress: `GET /api/batch/{batch_id}/progress`
4. Wait until `is_done: true`

## Endpoints

### 1. Check Balance (ALWAYS do this first)
```
GET /api/balance
```
Response:
```json
{"error_code": 0, "data": {"balance": 85.5, "point": 1200}}
```
→ If `balance == 0`, do NOT submit any tasks.

### 2. Single Domain Check
```
POST /api/detect
Headers: X-API-KEY: <key>, Content-Type: application/json
Body: {"url": "https://example.com"}
```
Response (202):
```json
{"success": true, "task_id": "abc-123", "balance_remaining": 84.5}
```
Response (402 — no balance):
```json
{"success": false, "error": "INSUFFICIENT_BALANCE", "balance": 0}
```

### 3. Get Task Result
```
GET /api/detect/{task_id}
```
Response:
```json
{
  "id": "abc-123",
  "url": "https://example.com",
  "status": "completed",
  "global_availability_percent": 66.7,
  "regions_checked": 3,
  "regions_available": 2,
  "anomaly_count": 1
}
```
Key fields:
- `status`: `pending` | `processing` | `completed` | `failed`
- `global_availability_percent`: 0–100 (100 = all regions OK)

### 4. Batch Submit
```
POST /api/detect/batch
Headers: X-API-KEY: <key>, Content-Type: application/json
Body: {"urls": ["https://domain1.com", "https://domain2.com", ...]}
```
Response (202):
```json
{
  "success": true,
  "batch_id": "batch-a1b2c3d4",
  "total_queued": 8,
  "balance_before": 85.5,
  "progress_url": "/api/batch/batch-a1b2c3d4/progress"
}
```

### 5. Track Batch Progress
```
GET /api/batch/{batch_id}/progress
```
Response:
```json
{
  "batch_id": "batch-a1b2c3d4",
  "total": 8,
  "completed": 5,
  "failed": 1,
  "pending": 2,
  "progress_percent": 75.0,
  "is_done": false
}
```
→ Poll this every 30 seconds until `is_done: true`.

### 6. View History
```
GET /api/history?limit=10
```
Response:
```json
{
  "items": [
    {"id": "abc-123", "url": "https://example.com", "status": "completed", "provider": "boce", "timestamp": "2026-03-18T09:00:00"}
  ]
}
```

## Decision Logic for Agents

```
IF user asks "check domain X":
  → GET /api/balance
  → IF balance > 0: POST /api/detect with url
  → Poll GET /api/detect/{task_id} every 15s
  → Report availability %

IF user asks "check these domains" (list):
  → GET /api/balance
  → IF balance >= len(urls): POST /api/detect/batch
  → Poll GET /api/batch/{batch_id}/progress every 30s
  → Report summary when is_done

IF user asks "check every 10 minutes":
  → Loop: POST /api/detect → sleep 600s → repeat
  → Alert if availability < 80%
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOCE_PROXY_URL` | Yes | Base URL, e.g. `http://localhost:3000` |
| `BOCE_PROXY_API_KEY` | Yes | Your proxy API key |

## Response Summary Format (Token-Optimized)

When reporting to users, use this concise format:
```
Domain: example.com
Status: ✅ UP (100% availability)
Regions: 3/3 OK
Anomalies: 0
```

For batch results:
```
Batch: batch-a1b2c3d4
Progress: 8/8 done (100%)
✅ 6 domains UP
❌ 2 domains DOWN
```
