"""
detect_service.py
-----------------
Detection orchestration — wires all services together.

Maps real Boce field names to internal schema:
  node_name  → region
  http_code  → status_code
  remote_ip  → response_ip   (the server IP seen from that node)
  time_total * 1000 → latency_ms
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.models.schemas import (
    BoceResultResponse,
    RegionResult,
    DetectionSummary,
    DetectionResult,
)
from app.services.metrics_service import build_summary
from app.services.anomaly_service import build_anomaly_list
from app.services import boce_client

logger = logging.getLogger(__name__)


async def run_detection(
    url: str,
    ip_whitelist: Optional[List[str]],
) -> DetectionResult:
    """
    Full detection pipeline:
      1. Call Boce (create task → poll until done)
      2. Normalize raw regions to internal schema
      3. Calculate metrics
      4. Build anomaly list
    """
    raw: BoceResultResponse = await boce_client.detect_url(url)

    regions = normalize_regions(raw, ip_whitelist)
    summary = build_summary(regions)
    anomaly_list = build_anomaly_list(regions)

    return DetectionResult(
        success=True,
        url=url,
        summary=summary,
        regions=regions,
        anomaly_list=anomaly_list,
    )


def normalize_regions(
    raw: BoceResultResponse,
    ip_whitelist: Optional[List[str]],
) -> List[RegionResult]:
    """
    Convert each BoceRegionData into a RegionResult.

    Field mapping:
      node_name  → region
      http_code  → status_code
      remote_ip  → response_ip  (the target server's IP as seen by the probe)
      time_total → latency_ms   (converted from seconds to milliseconds)
    """
    whitelist_set = {ip.strip() for ip in ip_whitelist} if ip_whitelist else None

    results: List[RegionResult] = []
    for item in raw.list:
        available = item.http_code == 200
        response_ip = item.remote_ip or item.origin_ip  # fallback to node IP

        if whitelist_set is not None:
            whitelist_match: Optional[bool] = response_ip in whitelist_set
        else:
            whitelist_match = None

        results.append(
            RegionResult(
                region=item.node_name,
                status_code=item.http_code,
                response_ip=response_ip,
                latency_ms=round(item.time_total * 1000, 2),
                available=available,
                whitelist_match=whitelist_match,
                anomalies=[],
            )
        )

    return results
