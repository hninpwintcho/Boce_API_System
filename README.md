# Boce Detection API — Phase 1 MVP

A lightweight **URL availability detection service** built on top of the **Boce API**.  
Send a URL, get back normalised regional availability results, metrics, optional IP whitelist validation, and anomaly tagging — all in one clean JSON response.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
  - [POST /api/detect](#post-apidetect)
  - [GET /health](#get-health)
- [Request & Response Examples](#request--response-examples)
- [Error Codes](#error-codes)
- [Anomaly Rules](#anomaly-rules)
- [Running Tests](#running-tests)
- [Local Development (Mock Mode)](#local-development-mock-mode)
- [Phase Roadmap](#phase-roadmap)

---

## Overview

**Phase 1 goal:** prove the core pipeline works end-to-end.

```
URL in  →  Boce call  →  normalise  →  metrics  →  whitelist check  →  anomaly tags  →  clean JSON out
```

This service wraps Boce, translates its raw response into a standard internal schema, and adds business-level enrichment on top.

---

## Architecture

```
Client
  │
  │  POST /api/detect
  ▼
┌─────────────────────────────┐
│  detect.py  (route)         │  validate input
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  boce_client.py             │  call Boce API (or built-in mock)
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  detect_service.py          │  normalize + orchestrate
│    ├─ metrics_service       │  calculate availability %
│    ├─ anomaly_service       │  tag NON_200_STATUS / IP_NOT_IN_WHITELIST
│    └─ validation_service    │  validate input
└────────────┬────────────────┘
             │
             ▼
       Standard JSON Response
```

---

## Project Structure

```
phase1/
├── app/
│   ├── main.py                   # FastAPI app + error handlers + /health
│   ├── config.py                 # Settings from environment / .env
│   ├── models/
│   │   └── schemas.py            # All Pydantic models
│   ├── routes/
│   │   └── detect.py             # POST /api/detect
│   ├── services/
│   │   ├── boce_client.py        # Boce API wrapper (+ built-in mock)
│   │   ├── detect_service.py     # Pipeline orchestration
│   │   ├── validation_service.py # Input validation
│   │   ├── metrics_service.py    # Availability calculations
│   │   └── anomaly_service.py    # Anomaly detection
│   └── utils/
│       └── errors.py             # Custom exception hierarchy
├── tests/
│   ├── unit/
│   │   ├── test_metrics.py       # availability calculation tests
│   │   ├── test_anomaly.py       # anomaly rule tests
│   │   └── test_whitelist.py     # validation tests
│   └── integration/
│       └── test_detect_endpoint.py  # end-to-end API tests
├── docs/
│   └── API.md                    # Full API documentation
├── .env.example                  # Environment variable template
├── requirements.txt
└── pytest.ini
```

---

## Quick Start

### 1. Clone & Install

```bash
# Install dependencies (wheel-only — no Rust compiler required)
pip install fastapi==0.100.1 pydantic==1.10.26 uvicorn[standard] httpx python-dotenv \
            pytest pytest-asyncio respx --only-binary :all:
```

> **Python note:** The project runs on Python 3.9+.  
> If you are on Python 3.15 alpha (no pydantic v2 wheels yet) use the command above which pins to pydantic v1.

### 2. Configure

```bash
cp .env.example .env
# Edit .env and fill in BOCE_API_URL and BOCE_API_KEY
# Leave BOCE_API_URL empty to use the built-in mock (great for local dev)
```

### 3. Start the Server

```bash
uvicorn app.main:app --reload --port 3000
```

Server is live at `http://localhost:3000`.  
Interactive docs: `http://localhost:3000/docs`

### 4. Run Your First Detection

```bash
curl -X POST http://localhost:3000/api/detect \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/api/v1/server/get_time",
    "ip_whitelist": ["1.2.3.4"]
  }'
```

---

## Environment Variables

| Variable               | Default | Required | Description                                                  |
|------------------------|---------|----------|--------------------------------------------------------------|
| `PORT`                 | `3000`  | No       | Uvicorn server port                                          |
| `BOCE_API_URL`         | `""`    | No       | Full Boce endpoint URL. **Leave empty to use built-in mock** |
| `BOCE_API_KEY`         | `""`    | No       | Boce Bearer token. Only used when `BOCE_API_URL` is set      |
| `BOCE_TIMEOUT_SECONDS` | `10`    | No       | HTTP timeout for Boce requests (seconds)                     |
| `BOCE_MAX_RETRIES`     | `2`     | No       | Reserved for Phase 2 retry logic                             |

---

## API Reference

### POST /api/detect

Detect URL availability across all Boce regions.

**Request Body**

| Field          | Type       | Required | Description                                   |
|----------------|------------|----------|-----------------------------------------------|
| `url`          | `string`   | ✅ Yes   | Full HTTP/HTTPS URL to check                  |
| `ip_whitelist` | `string[]` | ❌ No    | Expected response IPs. Anomaly tagged if mismatch |

**Response**

| Field                                  | Type      | Description                                              |
|----------------------------------------|-----------|----------------------------------------------------------|
| `success`                              | `boolean` | `true` on success                                        |
| `url`                                  | `string`  | The URL that was checked                                 |
| `summary.regions_checked`              | `int`     | Total number of regions queried                          |
| `summary.regions_available`            | `int`     | Regions returning HTTP 200                               |
| `summary.global_availability_percent`  | `float`   | `available / total * 100`, rounded to 2 decimal places  |
| `summary.anomaly_count`                | `int`     | Total anomalies across all regions                       |
| `regions[]`                            | `array`   | Per-region breakdown (see below)                         |
| `anomaly_list[]`                       | `array`   | Flat list of all anomalies                               |

**Region object**

| Field            | Type            | Description                                          |
|------------------|-----------------|------------------------------------------------------|
| `region`         | `string`        | Region code (e.g. `CN`, `US`, `EU`)                 |
| `status_code`    | `int`           | HTTP status returned from that region                |
| `response_ip`    | `string`        | IP address observed in that region                   |
| `latency_ms`     | `float`         | Response latency in milliseconds                     |
| `available`      | `boolean`       | `true` when `status_code == 200`                     |
| `whitelist_match`| `boolean\|null` | `null` when no whitelist provided, else IP match     |
| `anomalies`      | `string[]`      | Anomaly codes for this region                        |

---

### GET /health

Liveness check.

```json
{ "status": "ok" }
```

---

## Request & Response Examples

### Success — with partial whitelist

**Request**
```json
{
  "url": "https://example.com/api/v1/server/get_time",
  "ip_whitelist": ["1.2.3.4", "5.6.7.8"]
}
```

**Response `200 OK`**
```json
{
  "success": true,
  "url": "https://example.com/api/v1/server/get_time",
  "summary": {
    "regions_checked": 3,
    "regions_available": 2,
    "global_availability_percent": 66.67,
    "anomaly_count": 2
  },
  "regions": [
    {
      "region": "CN",
      "status_code": 200,
      "response_ip": "1.2.3.4",
      "latency_ms": 320,
      "available": true,
      "whitelist_match": true,
      "anomalies": []
    },
    {
      "region": "US",
      "status_code": 503,
      "response_ip": "8.8.8.8",
      "latency_ms": 810,
      "available": false,
      "whitelist_match": false,
      "anomalies": ["NON_200_STATUS", "IP_NOT_IN_WHITELIST"]
    },
    {
      "region": "EU",
      "status_code": 200,
      "response_ip": "5.6.7.8",
      "latency_ms": 450,
      "available": true,
      "whitelist_match": true,
      "anomalies": []
    }
  ],
  "anomaly_list": [
    { "region": "US", "ip": "8.8.8.8", "reason": "NON_200_STATUS" },
    { "region": "US", "ip": "8.8.8.8", "reason": "IP_NOT_IN_WHITELIST" }
  ]
}
```

### Success — no whitelist

```json
{ "url": "https://example.com" }
```

All regions will have `"whitelist_match": null` and no `IP_NOT_IN_WHITELIST` anomalies.

### Error — invalid URL

**Request**
```json
{ "url": "not-a-url" }
```

**Response `400 Bad Request`**
```json
{
  "success": false,
  "error_code": "INVALID_URL",
  "message": "'not-a-url' is not a valid HTTP/HTTPS URL."
}
```

---

## Error Codes

| HTTP Status | `error_code`               | Cause                                            |
|-------------|----------------------------|--------------------------------------------------|
| 400         | `MISSING_URL`              | `url` field absent or empty                      |
| 400         | `INVALID_URL`              | Not a valid HTTP/HTTPS URL                       |
| 400         | `INVALID_REQUEST`          | Schema validation failure (e.g. wrong type)      |
| 400         | `INVALID_WHITELIST_FORMAT` | `ip_whitelist` is not an array                   |
| 400         | `INVALID_WHITELIST_ENTRY`  | An entry in `ip_whitelist` is empty/non-string   |
| 502         | `BOCE_INVALID_RESPONSE`    | Boce returned unparseable data                   |
| 503         | `BOCE_UNAVAILABLE`         | Boce API unreachable or returned 5xx             |
| 504         | `BOCE_TIMEOUT`             | Boce did not respond within configured timeout   |
| 500         | `INTERNAL_ERROR`           | Unexpected server-side error                     |

---

## Anomaly Rules

| Code                  | Trigger                                                         |
|-----------------------|-----------------------------------------------------------------|
| `NON_200_STATUS`      | Region returned a non-200 HTTP status code                      |
| `IP_NOT_IN_WHITELIST` | Region's `response_ip` is not in the provided `ip_whitelist`   |

> Phase 2 will add: `TIMEOUT`, `EMPTY_RESPONSE`, and configurable custom rules.

---

## Running Tests

```bash
pytest -v
```

**Current test coverage:**

| Suite                                        | Tests | Status     |
|----------------------------------------------|-------|------------|
| `tests/unit/test_metrics.py`                 | 8     | ✅ Passing |
| `tests/unit/test_anomaly.py`                 | 6     | ✅ Passing |
| `tests/unit/test_whitelist.py`               | 8     | ✅ Passing |
| `tests/integration/test_detect_endpoint.py`  | 10    | ✅ Passing |
| **Total**                                    | **32**| ✅ **All passing** |

---

## Local Development (Mock Mode)

When `BOCE_API_URL` is **not set** (or empty), the service automatically uses a **built-in mock** that simulates 3 regions:

| Region | Status | IP      | Latency |
|--------|--------|---------|---------|
| CN     | 200    | 1.2.3.4 | 320 ms  |
| US     | 503    | 8.8.8.8 | 810 ms  |
| EU     | 200    | 5.6.7.8 | 450 ms  |

This lets you develop and run all tests with zero external dependencies.

---

## Phase Roadmap

### ✅ Phase 1 — MVP (current)
- Boce API integration (+ mock fallback)
- Unified `POST /api/detect` endpoint
- Response normalisation to standard JSON
- Regional metrics calculation
- Optional IP whitelist validation
- Anomaly tagging (`NON_200_STATUS`, `IP_NOT_IN_WHITELIST`)
- Basic error handling (400/502/503/504/500)
- Unit + integration test coverage
- API documentation

### 🔜 Phase 2 — Production Hardening
- Result storage (database)
- History logs
- Retry + timeout policy
- Queue system (Celery / Redis)
- Concurrent detection jobs
- Rate limiting
- Stronger test coverage

### 🔮 Phase 3 — Platform
- Dashboard (Grafana or custom UI)
- Alert system
- Multi-provider support (Boce + ITDOG + others)
- Real-time monitoring
- AI-generated availability summary

---

## Tech Stack

| Layer      | Technology                      |
|------------|---------------------------------|
| Framework  | Python + FastAPI 0.100          |
| Validation | Pydantic v1                     |
| HTTP client| httpx (async)                   |
| Testing    | pytest + pytest-asyncio + respx |
| Server     | Uvicorn                         |

---

*Built for Phase 1 delivery. See [`docs/API.md`](docs/API.md) for the full API specification.*
