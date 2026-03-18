import logging
from typing import List
from app.models.schemas import RegionResult, AnomalyItem

logger = logging.getLogger(__name__)

class AIMonitorService:
    """
    Intelligent Monitoring Agent (Phase 4).
    Goes beyond simple status codes to identify 'Silent Failures'.
    """

    @staticmethod
    def analyze_batch(regions: List[RegionResult]) -> List[AnomalyItem]:
        """
        Analyze a batch of results for patterns and silent anomalies.
        """
        ai_anomalies = []
        
        # 1. Statistical Thresholds
        latencies = [r.latency_ms for r in regions if r.available]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        for region in regions:
            # Rule: Silent Failure (200 OK but 0ms latency)
            if region.available and region.latency_ms < 1.0:
                ai_anomalies.append(
                    AnomalyItem(
                        region=region.region,
                        ip=region.response_ip,
                        reason="AI_SILENT_FAILURE_SUSPECTED"
                    )
                )
                region.anomalies.append("AI_SILENT_FAILURE")

            # Rule: Latency Outlier (5x average)
            if region.available and avg_latency > 0 and region.latency_ms > (avg_latency * 5):
                ai_anomalies.append(
                    AnomalyItem(
                        region=region.region,
                        ip=region.response_ip,
                        reason="AI_LATENCY_OUTLIER"
                    )
                )
                region.anomalies.append("AI_LATENCY_WARM")
        
        return ai_anomalies

ai_monitor = AIMonitorService()
