"""
metrics_service.py
------------------
Metrics calculation — Step 4

From a list of normalised RegionResult objects, compute:
  • regions_checked
  • regions_available
  • global_availability_percent
  • anomaly_count (delegated: counted after anomaly_service runs,
    but we expose a helper for the test stage too)
"""

from __future__ import annotations

from typing import List

from app.models.schemas import DetectionSummary, RegionResult


def build_summary(regions: List[RegionResult]) -> DetectionSummary:
    """
    Calculate detection summary from normalised region results.

    Note: anomaly_count is 0 here; it is updated in the route handler
    AFTER anomaly_service has populated region anomalies.
    (We keep this function pure / side-effect-free for easy testing.)
    """
    regions_checked = len(regions)
    regions_available = sum(1 for r in regions if r.available)

    if regions_checked > 0:
        global_availability_percent = round(
            regions_available / regions_checked * 100, 2
        )
    else:
        global_availability_percent = 0.0

    # Anomaly count is not known yet at this stage; set 0 as placeholder.
    # detect_service updates it after anomaly_service runs.
    return DetectionSummary(
        regions_checked=regions_checked,
        regions_available=regions_available,
        global_availability_percent=global_availability_percent,
        anomaly_count=0,
    )


def calculate_availability_percent(available: int, total: int) -> float:
    """Standalone helper, useful for unit tests."""
    if total == 0:
        return 0.0
    return round(available / total * 100, 2)
