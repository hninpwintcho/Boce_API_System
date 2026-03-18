# Boce Detection API — v1.0  Phase 1 Documentation

## 1. Purpose

Unified URL detection service powered by the **Boce API**.  
Exposes a single endpoint that checks a URL across multiple global regions,
normalises raw Boce data into a standard JSON schema, calculates availability
metrics, validates optional IP whitelists, and tags anomalies.

---

## 2. Endpoint

```
POST /api/detect
Content-Type: application/json
```

---

## 3. Request Body

| Field         | Type       | Required | Description                              |
|---------------|------------|----------|------------------------------------------|
| `url`         | `string`   | ✅ Yes   | Full HTTP/HTTPS URL to detect            |
| `ip_whitelist`| `string[]` | ❌ No    | List of expected response IPs            |

### Example

```json
{
  "url": "https://example.com/api/v1/server/get_time",
  "ip_whitelist": ["1.2.3.4", "5.6.7.8"]
}
```

---

## 4. Success Response  `200 OK`

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
      "anomalies": ["IP_NOT_IN_WHITELIST", "NON_200_STATUS"]
    }
  ],
  "anomaly_list": [
    { "region": "US", "ip": "8.8.8.8", "reason": "NON_200_STATUS" },
    { "region": "US", "ip": "8.8.8.8", "reason": "IP_NOT_IN_WHITELIST" }
  ]
}
```

### Field Notes

| Field                              | Notes                                                  |
|------------------------------------|--------------------------------------------------------|
| `summary.global_availability_percent` | `available_regions / total_regions × 100`          |
| `regions[].available`              | `true` when `status_code == 200`                       |
| `regions[].whitelist_match`        | `null` when no `ip_whitelist` was provided             |
| `anomaly_list`                     | Flat list; one entry per anomaly per region            |

---

## 5. Error Responses

All errors follow this shape:

```json
{
  "success": false,
  "error_code": "ERROR_CODE",
  "message": "Human-readable description"
}
```

### Error Code Reference

| HTTP | `error_code`             | Cause                                         |
|------|--------------------------|-----------------------------------------------|
| 400  | `MISSING_URL`            | `url` field is absent or empty                |
| 400  | `INVALID_URL`            | `url` is not a valid HTTP/HTTPS URL           |
| 400  | `INVALID_REQUEST`        | Pydantic schema validation failure            |
| 400  | `INVALID_WHITELIST_FORMAT` | `ip_whitelist` is not an array              |
| 400  | `INVALID_WHITELIST_ENTRY`  | An entry in `ip_whitelist` is empty/invalid |
| 502  | `BOCE_INVALID_RESPONSE`  | Boce returned an unparseable response         |
| 503  | `BOCE_UNAVAILABLE`       | Boce API is unreachable or returned 5xx       |
| 504  | `BOCE_TIMEOUT`           | Boce did not respond within configured timeout|
| 500  | `INTERNAL_ERROR`         | Unexpected server error                       |

### Example — Invalid URL

```json
{
  "success": false,
  "error_code": "INVALID_URL",
  "message": "'not-a-url' is not a valid HTTP/HTTPS URL."
}
```

### Example — Boce Timeout

```json
{
  "success": false,
  "error_code": "BOCE_TIMEOUT",
  "message": "Boce API request timed out after 10s"
}
```

---

## 6. Anomaly Rules (MVP)

| Code                  | Trigger                                      |
|-----------------------|----------------------------------------------|
| `NON_200_STATUS`      | Region `status_code` is not 200              |
| `IP_NOT_IN_WHITELIST` | `response_ip` not found in `ip_whitelist`    |

More rules (e.g. `TIMEOUT`, `EMPTY_RESPONSE`) will be added in Phase 2.

---

## 7. Environment Variables

| Variable               | Default | Description                                       |
|------------------------|---------|---------------------------------------------------|
| `PORT`                 | `3000`  | Server port                                       |
| `BOCE_API_URL`         | `""`    | Boce endpoint — leave empty to use built-in mock  |
| `BOCE_API_KEY`         | `""`    | Boce auth key (Bearer token)                      |
| `BOCE_TIMEOUT_SECONDS` | `10`    | Request timeout in seconds                        |
| `BOCE_MAX_RETRIES`     | `2`     | Retry attempts (future use)                       |

---

## 8. Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start dev server (mock Boce by default)
uvicorn app.main:app --reload --port 3000
```

### Demo curl

```bash
curl -X POST http://localhost:3000/api/detect \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/api/v1/server/get_time",
    "ip_whitelist": ["1.2.3.4"]
  }'
```

### Run Tests

```bash
pytest -v
```

---

## 9. Interactive Docs

Swagger UI: [http://localhost:3000/docs](http://localhost:3000/docs)  
ReDoc:       [http://localhost:3000/redoc](http://localhost:3000/redoc)

---

*Phase 1 MVP — built with Python FastAPI + Pydantic + httpx*
