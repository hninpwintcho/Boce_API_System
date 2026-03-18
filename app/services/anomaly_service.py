"""
anomaly_service.py
------------------
Anomaly detection — Step 6

MVP anomaly rules:
  • NON_200_STATUS    — status_code != 200
  • IP_NOT_IN_WHITELIST — response_ip not in provided whitelist

Each anomaly carries: region, ip, reason.

Side effect: populates region.anomalies list in-place so the
serialised RegionResult also shows the anomaly codes.
"""

from __future__ import annotations

from typing import List

from app.models.schemas import AnomalyItem, RegionResult


def build_anomaly_list(regions: List[RegionResult]) -> List[AnomalyItem]:
    """
    Scan all regions, attach anomaly codes to each RegionResult.anomalies,
    and return the flat anomaly_list for the top-level response.
    """
    anomalies: List[AnomalyItem] = []

    for region in regions:
        region.anomalies = []   # reset (detect_service sets [] initially too)

        # Rule 1 — non-200 status
        if region.status_code != 200:
            _add_anomaly(
                region, anomalies,
                reason="NON_200_STATUS",
            )

        # Rule 2 — IP not in whitelist (only when whitelist was provided)
        if region.whitelist_match is False:
            _add_anomaly(
                region, anomalies,
                reason="IP_NOT_IN_WHITELIST",
            )

    return anomalies


def _add_anomaly(
    region: RegionResult,
    anomaly_list: List[AnomalyItem],
    reason: str,
) -> None:
    region.anomalies.append(reason)
    anomaly_list.append(
        AnomalyItem(
            region=region.region,
            ip=region.response_ip,
            reason=reason,
        )
    )
