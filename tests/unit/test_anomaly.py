"""
test_anomaly.py
---------------
Unit tests for anomaly_service
"""

import pytest
from app.models.schemas import RegionResult
from app.services.anomaly_service import build_anomaly_list


def _region(
    region: str,
    status_code: int,
    whitelist_match,
    ip: str = "1.2.3.4",
) -> RegionResult:
    return RegionResult(
        region=region,
        status_code=status_code,
        response_ip=ip,
        latency_ms=100.0,
        available=(status_code == 200),
        whitelist_match=whitelist_match,
        anomalies=[],
    )


class TestBuildAnomalyList:
    def test_no_anomalies_when_all_ok(self):
        regions = [_region("CN", 200, True), _region("US", 200, True)]
        anomalies = build_anomaly_list(regions)
        assert anomalies == []
        assert regions[0].anomalies == []
        assert regions[1].anomalies == []

    def test_non_200_triggers_anomaly(self):
        regions = [_region("US", 503, True)]
        anomalies = build_anomaly_list(regions)
        assert len(anomalies) == 1
        assert anomalies[0].reason == "NON_200_STATUS"
        assert "NON_200_STATUS" in regions[0].anomalies

    def test_whitelist_mismatch_triggers_anomaly(self):
        regions = [_region("US", 200, False, ip="8.8.8.8")]
        anomalies = build_anomaly_list(regions)
        assert len(anomalies) == 1
        assert anomalies[0].reason == "IP_NOT_IN_WHITELIST"

    def test_both_anomalies_on_same_region(self):
        regions = [_region("US", 503, False, ip="8.8.8.8")]
        anomalies = build_anomaly_list(regions)
        reasons = [a.reason for a in anomalies]
        assert "NON_200_STATUS" in reasons
        assert "IP_NOT_IN_WHITELIST" in reasons
        assert len(anomalies) == 2

    def test_no_whitelist_anomaly_when_whitelist_not_provided(self):
        """whitelist_match == None means no whitelist was given — no anomaly."""
        regions = [_region("US", 200, None)]
        anomalies = build_anomaly_list(regions)
        assert anomalies == []

    def test_anomaly_carries_ip_and_region(self):
        regions = [_region("EU", 500, None, ip="9.9.9.9")]
        anomalies = build_anomaly_list(regions)
        assert anomalies[0].region == "EU"
        assert anomalies[0].ip == "9.9.9.9"
