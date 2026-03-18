import asyncio
import logging
from app.services.provider_manager import provider_manager
from app.services.ai_monitor_service import ai_monitor
from app.models.schemas import RegionResult

logging.basicConfig(level=logging.INFO)

async def test_phase4_logic():
    print("--- 🧠 Testing AI Anomaly Detection ---")
    mock_regions = [
        RegionResult(region="CN-North", status_code=200, latency_ms=10.5, available=True, response_ip="1.1.1.1", whitelist_match=True, anomalies=[]),
        RegionResult(region="CN-South", status_code=200, latency_ms=0.0, available=True, response_ip="1.1.1.1", whitelist_match=True, anomalies=[]), # SILENT FAILURE
        RegionResult(region="US-West", status_code=200, latency_ms=500.0, available=True, response_ip="1.1.1.1", whitelist_match=True, anomalies=[]), # OUTLIER
    ]
    
    anoms = ai_monitor.analyze_batch(mock_regions)
    print(f"Detected {len(anoms)} anomalies:")
    for a in anoms:
        print(f" - [{a.region}] {a.reason}")

    print("\n--- 🔥 Testing Auto-Failover Logic ---")
    print(f"Initial Provider: {provider_manager.get_best_provider()}")
    
    print("Simulating multiple failures...")
    for _ in range(6):
        provider_manager.report_failure("boce")
    
    new_provider = provider_manager.get_best_provider()
    print(f"Post-Failure Provider: {new_provider}")
    
    if new_provider == "mock_itdog":
        print("✅ Failover Success!")
    else:
        print("❌ Failover Failed")

if __name__ == "__main__":
    asyncio.run(test_phase4_logic())
