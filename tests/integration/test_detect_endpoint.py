"""
test_detect_endpoint.py
-----------------------
Integration tests for POST /api/detect
Uses httpx AsyncClient (ASGI transport) — no real network needed.
Boce mock is used automatically since BOCE_API_URL is unset.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx
import respx

from app.main import app
from app.config import settings


# ─── Helpers ──────────────────────────────────────────────────────────────────

DETECT_URL = "/api/detect"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ─── Happy path tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_success_no_whitelist(client):
    """Basic detect call — mock Boce response, no whitelist."""
    response = await client.post(
        DETECT_URL,
        json={"url": "https://example.com/api/v1/server/get_time"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "summary" in body
    assert "regions" in body
    assert "anomaly_list" in body
    assert body["summary"]["regions_checked"] >= 1


@pytest.mark.asyncio
async def test_detect_with_matching_whitelist(client):
    """IP whitelist contains all mock IPs → no IP_NOT_IN_WHITELIST anomaly."""
    response = await client.post(
        DETECT_URL,
        json={
            "url": "https://example.com/",
            "ip_whitelist": ["1.2.3.4", "5.6.7.8", "8.8.8.8"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    # All IPs are in whitelist — no whitelist anomalies expected
    whitelist_anomalies = [
        a for a in body["anomaly_list"] if a["reason"] == "IP_NOT_IN_WHITELIST"
    ]
    assert whitelist_anomalies == []


@pytest.mark.asyncio
async def test_detect_with_partial_whitelist(client):
    """Partial whitelist → IP_NOT_IN_WHITELIST anomaly for unmatched IPs."""
    response = await client.post(
        DETECT_URL,
        json={
            "url": "https://example.com/",
            "ip_whitelist": ["1.2.3.4"],   # only CN IP whitelisted
        },
    )
    assert response.status_code == 200
    body = response.json()
    whitelist_anomalies = [
        a for a in body["anomaly_list"] if a["reason"] == "IP_NOT_IN_WHITELIST"
    ]
    assert len(whitelist_anomalies) >= 1


@pytest.mark.asyncio
async def test_summary_anomaly_count_matches_list(client):
    """anomaly_count in summary must equal len(anomaly_list)."""
    response = await client.post(
        DETECT_URL,
        json={"url": "https://example.com/", "ip_whitelist": ["1.2.3.4"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["anomaly_count"] == len(body["anomaly_list"])


# ─── Validation error tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_missing_url_returns_400(client):
    response = await client.post(DETECT_URL, json={})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "error_code" in body


@pytest.mark.asyncio
async def test_detect_invalid_url_returns_400(client):
    response = await client.post(
        DETECT_URL, json={"url": "not-a-url"}
    )
    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_detect_whitelist_wrong_type_returns_400(client):
    """Whitelist must be array not a string."""
    response = await client.post(
        DETECT_URL,
        json={"url": "https://example.com", "ip_whitelist": "1.2.3.4"},
    )
    assert response.status_code == 400


# ─── Boce error simulation tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_boce_timeout(client, monkeypatch):
    """Simulate Boce timeout → expect 504."""
    from app.utils.errors import BoceTimeoutError
    from app.services import detect_service

    async def mock_run_detection(url, ip_whitelist):
        raise BoceTimeoutError("Boce timed out")

    monkeypatch.setattr(detect_service, "run_detection", mock_run_detection)

    response = await client.post(
        DETECT_URL, json={"url": "https://example.com"}
    )
    assert response.status_code == 504
    assert response.json()["error_code"] == "BOCE_TIMEOUT"


@pytest.mark.asyncio
async def test_detect_boce_unavailable(client, monkeypatch):
    """Simulate Boce being down → expect 503."""
    from app.utils.errors import BoceUnavailableError
    from app.services import detect_service

    async def mock_run_detection(url, ip_whitelist):
        raise BoceUnavailableError("Boce is down")

    monkeypatch.setattr(detect_service, "run_detection", mock_run_detection)

    response = await client.post(
        DETECT_URL, json={"url": "https://example.com"}
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "BOCE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
