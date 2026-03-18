"""
test_metrics.py
---------------
Unit tests for metrics_service
"""

import pytest
from app.models.schemas import RegionResult
from app.services.metrics_service import build_summary, calculate_availability_percent


def _make_region(region: str, status_code: int) -> RegionResult:
    return RegionResult(
        region=region,
        status_code=status_code,
        response_ip="1.2.3.4",
        latency_ms=100.0,
        available=(status_code == 200),
        whitelist_match=None,
        anomalies=[],
    )


class TestCalculateAvailability:
    def test_all_available(self):
        assert calculate_availability_percent(3, 3) == 100.0

    def test_none_available(self):
        assert calculate_availability_percent(0, 3) == 0.0

    def test_partial(self):
        assert calculate_availability_percent(2, 3) == 66.67

    def test_zero_regions(self):
        assert calculate_availability_percent(0, 0) == 0.0


class TestBuildSummary:
    def test_all_up(self):
        regions = [_make_region("CN", 200), _make_region("US", 200)]
        summary = build_summary(regions)
        assert summary.regions_checked == 2
        assert summary.regions_available == 2
        assert summary.global_availability_percent == 100.0
        assert summary.anomaly_count == 0   # patched later

    def test_mixed(self):
        regions = [
            _make_region("CN", 200),
            _make_region("US", 503),
            _make_region("EU", 200),
        ]
        summary = build_summary(regions)
        assert summary.regions_checked == 3
        assert summary.regions_available == 2
        assert summary.global_availability_percent == 66.67

    def test_all_down(self):
        regions = [_make_region("CN", 500), _make_region("US", 503)]
        summary = build_summary(regions)
        assert summary.regions_checked == 2
        assert summary.regions_available == 0
        assert summary.global_availability_percent == 0.0

    def test_empty_regions(self):
        summary = build_summary([])
        assert summary.regions_checked == 0
        assert summary.global_availability_percent == 0.0
