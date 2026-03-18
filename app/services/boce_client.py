"""
boce_client.py
--------------
Boce Wrapper Service — Real two-step API flow

Real Boce API flow:
  1. Create task  →  GET /v3/task/create/curl?key=KEY&node_ids=6,31,32&host=example.com
                     ← { "error_code": 0, "data": { "id": "LxiB1jZP..." } }

  2. Poll result  →  GET /v3/task/curl/{id}?key=KEY    (every 10s, up to 2 min)
                     ← { "done": true, "list": [...] }

When BOCE_API_KEY is empty the module returns a built-in mock so you can
develop and run tests without a live Boce account.

Node list API (cached):
  GET /v3/node/list?key=KEY
  Returns node id, name, ISP — loaded once at startup.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.models.schemas import BoceRegionData, BoceResultResponse
from app.utils.errors import (
    BoceTimeoutError,
    BoceUnavailableError,
    BoceInvalidResponseError,
)

logger = logging.getLogger(__name__)

# ─── Node cache ───────────────────────────────────────────────────────────────
# Loaded once at startup (or first call). Mapping: node_id → node_name
_node_cache: dict[int, str] = {}
_node_cache_loaded: bool = False


# ─── Mock data ────────────────────────────────────────────────────────────────

_MOCK_REGIONS: List[dict] = [
    {
        "node_id": 6,
        "node_name": "河北电信",
        "host": "",
        "http_code": 200,
        "remote_ip": "1.2.3.4",
        "origin_ip": "123.181.72.232",
        "ip_isp": "电信",
        "ip_region": "中国河北电信",
        "time_total": 0.320,
        "download_time": 0.134,
        "time_connect": 0.023,
        "time_namelookup": 0.008,
        "error_code": 0,
        "error": "",
    },
    {
        "node_id": 31,
        "node_name": "美国",
        "host": "",
        "http_code": 503,
        "remote_ip": "8.8.8.8",
        "origin_ip": "104.20.1.1",
        "ip_isp": "海外",
        "ip_region": "美国",
        "time_total": 0.810,
        "download_time": 0.400,
        "time_connect": 0.120,
        "time_namelookup": 0.010,
        "error_code": 0,
        "error": "",
    },
    {
        "node_id": 32,
        "node_name": "欧洲",
        "host": "",
        "http_code": 200,
        "remote_ip": "5.6.7.8",
        "origin_ip": "185.60.216.1",
        "ip_isp": "海外",
        "ip_region": "欧洲",
        "time_total": 0.450,
        "download_time": 0.200,
        "time_connect": 0.060,
        "time_namelookup": 0.012,
        "error_code": 0,
        "error": "",
    },
]


# ─── Public entry point ───────────────────────────────────────────────────────

async def detect_url(url: str) -> BoceResultResponse:
    """
    Run a Boce curl detection for *url* across the configured node set.
    Returns BoceResultResponse with a populated .list of BoceRegionData.

    If BOCE_API_KEY is empty, returns the built-in mock response.
    """
    if not settings.BOCE_API_KEY:
        logger.info("BOCE_API_KEY not set — using built-in mock response.")
        return _build_mock(url)

    host = _extract_host(url)
    node_ids = settings.BOCE_NODE_IDS  # comma-separated string

    task_id = await _create_task(host, node_ids)
    return await _poll_result(task_id)


async def fetch_node_list() -> dict[int, str]:
    """
    Fetch and cache the full Boce node list.
    Returns a dict mapping node_id → node_name.
    """
    global _node_cache, _node_cache_loaded
    if _node_cache_loaded:
        return _node_cache

    if not settings.BOCE_API_KEY:
        return {}

    url = f"{settings.BOCE_API_URL}/node/list"
    params = {"key": settings.BOCE_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=settings.BOCE_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
        data = resp.json()
        nodes = data.get("data", {}).get("list", [])
        _node_cache = {n["id"]: n["node_name"] for n in nodes}
        _node_cache_loaded = True
        logger.info("Loaded %d Boce nodes.", len(_node_cache))
    except Exception as exc:
        logger.warning("Failed to load Boce node list: %s", exc)
    return _node_cache


# ─── Step 1: create task ──────────────────────────────────────────────────────

async def _create_task(host: str, node_ids: str) -> str:
    """
    Call POST /v3/task/create/curl and return the task ID string.
    node_ids is a comma-separated string like "6,31,32".
    """
    create_url = f"{settings.BOCE_API_URL}/task/create/curl"
    params = {
        "key": settings.BOCE_API_KEY,
        "node_ids": node_ids,
        "host": host,
    }

    logger.info("Creating Boce task: host=%s node_ids=%s", host, node_ids)

    try:
        async with httpx.AsyncClient(timeout=settings.BOCE_TIMEOUT_SECONDS) as client:
            resp = await client.get(create_url, params=params)
    except httpx.TimeoutException:
        raise BoceTimeoutError(
            f"Boce create-task timed out after {settings.BOCE_TIMEOUT_SECONDS}s"
        )
    except httpx.RequestError as exc:
        raise BoceUnavailableError(f"Boce API unreachable: {exc}")

    if resp.status_code >= 500:
        raise BoceUnavailableError(f"Boce returned HTTP {resp.status_code} on create-task")

    try:
        body = resp.json()
    except Exception:
        raise BoceInvalidResponseError("Boce create-task returned non-JSON response")

    if body.get("error_code", -1) != 0:
        err_msg = body.get("error", "unknown error")
        raise BoceUnavailableError(f"Boce create-task error {body.get('error_code')}: {err_msg}")

    task_id = (body.get("data") or {}).get("id", "")
    if not task_id:
        raise BoceInvalidResponseError("Boce create-task returned no task ID")

    logger.info("Boce task created: id=%s", task_id)
    return task_id


# ─── Step 2: poll until done ──────────────────────────────────────────────────

async def _poll_result(task_id: str) -> BoceResultResponse:
    """
    Poll GET /v3/task/curl/{task_id} every BOCE_POLL_INTERVAL_SECONDS
    until done==true or BOCE_POLL_TIMEOUT_SECONDS elapses.
    """
    result_url = f"{settings.BOCE_API_URL}/task/curl/{task_id}"
    params = {"key": settings.BOCE_API_KEY}
    deadline = time.monotonic() + settings.BOCE_POLL_TIMEOUT_SECONDS

    logger.info(
        "Polling Boce result for task_id=%s (interval=%ss, timeout=%ss)",
        task_id, settings.BOCE_POLL_INTERVAL_SECONDS, settings.BOCE_POLL_TIMEOUT_SECONDS,
    )

    while True:
        try:
            async with httpx.AsyncClient(timeout=settings.BOCE_TIMEOUT_SECONDS) as client:
                resp = await client.get(result_url, params=params)
        except httpx.TimeoutException:
            raise BoceTimeoutError(
                f"Boce poll-result timed out after {settings.BOCE_TIMEOUT_SECONDS}s"
            )
        except httpx.RequestError as exc:
            raise BoceUnavailableError(f"Boce API unreachable during poll: {exc}")

        if resp.status_code >= 500:
            raise BoceUnavailableError(f"Boce returned HTTP {resp.status_code} on poll")

        try:
            body = resp.json()
        except Exception:
            raise BoceInvalidResponseError("Boce poll returned non-JSON response")

        done = body.get("done", False)
        logger.debug("Boce poll response: done=%s task_id=%s", done, task_id)

        if done:
            return _parse_result(body)

        # Check timeout before sleeping
        if time.monotonic() >= deadline:
            raise BoceTimeoutError(
                f"Boce task {task_id} did not complete within "
                f"{settings.BOCE_POLL_TIMEOUT_SECONDS}s"
            )

        await asyncio.sleep(settings.BOCE_POLL_INTERVAL_SECONDS)


def _parse_result(body: dict) -> BoceResultResponse:
    try:
        region_list = [BoceRegionData(**item) for item in body.get("list", [])]
        return BoceResultResponse(
            done=True,
            id=body.get("id", ""),
            list=region_list,
            max_node=body.get("max_node", 0),
        )
    except Exception as exc:
        raise BoceInvalidResponseError(f"Failed to parse Boce result list: {exc}")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_host(url: str) -> str:
    """Extract bare hostname (+ path) from a full URL for Boce's 'host' param."""
    parsed = urlparse(url)
    # Boce expects the host without scheme but with path, e.g. "example.com/api/v1/ping"
    host = parsed.netloc
    if parsed.path and parsed.path != "/":
        host += parsed.path
    return host


def _build_mock(url: str) -> BoceResultResponse:
    host = _extract_host(url)
    regions = []
    for r in _MOCK_REGIONS:
        item = dict(r)
        item["host"] = host
        regions.append(BoceRegionData(**item))
    return BoceResultResponse(done=True, id="mock-task-id", list=regions, max_node=len(regions))
