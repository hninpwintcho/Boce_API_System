import logging
import asyncio
from datetime import datetime
from app.database import get_db_connection
from app.services import boce_client, metrics_service, anomaly_service, detect_service, ai_monitor_service, provider_manager, alert_service

logger = logging.getLogger(__name__)

# Throttling Semaphore for concurrency control (Phase 2)
_semaphore = asyncio.Semaphore(20)

async def run_detection_bg(task_id: str, url: str, ip_whitelist: list[str] = None, provider: str = "boce"):
    """
    Unified Background Worker (Phase 1-4):
    - Throttling (Semaphore)
    - Fault Recovery (Zero-Point-Wastage)
    - AI Anomaly Detection
    - Autonomous Health Reporting (Failover)
    """
    async with _semaphore:
        try:
            async with get_db_connection() as db:
                # 1. Recovery Check: Has Boce already taken our points?
                cursor = await db.execute(
                    "SELECT provider_task_id, status FROM detection_tasks WHERE id = ?", 
                    (task_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return

                provider_task_id, status = row
                
                # 2. Create Task if it doesn't exist yet
                if not provider_task_id:
                    logger.info(f"Task {task_id}: Creating new {provider} task for {url}")
                    # Extract host manually since we might be mocking
                    host = boce_client.extract_host(url)
                    provider_task_id = await boce_client.create_boce_task(host, "6,31,32")
                    
                    await db.execute(
                        "UPDATE detection_tasks SET provider_task_id = ?, status = 'processing' WHERE id = ?",
                        (provider_task_id, task_id)
                    )
                    await db.commit()
                else:
                    logger.info(f"Task {task_id}: Resuming existing {provider} task {provider_task_id}")

            # 3. Poll for results
            raw_result = None
            for _ in range(30):
                await asyncio.sleep(10)
                raw_result = await boce_client.poll_boce_result(provider_task_id)
                # Note: raw_result is a BoceResultResponse object (if successful) or raises error
                if raw_result and raw_result.done:
                    break
            
            if not raw_result or not raw_result.done:
                raise Exception("Provider polling timeout")

            # 4. Analyze & AI Triage
            # Convert BoceResultResponse to dict for normalization if needed, 
            # or update services to accept the object.
            # Our services usually expect dicts from raw API.
            raw_dict = {
                "id": raw_result.id,
                "done": raw_result.done,
                "list": [r.dict() for r in raw_result.list],
                "max_node": raw_result.max_node
            }

            regions = detect_service.normalize_regions(raw_dict, ip_whitelist)
            summary = metrics_service.build_summary(regions)
            anomalies = anomaly_service.build_anomaly_list(regions)
            
            # Phase 4 Intelligence
            ai_anoms = ai_monitor_service.ai_monitor.analyze_batch(regions)
            anomalies.extend(ai_anoms)
            
            # 5. Heartbeat: Report Health for Auto-Failover
            provider_manager.provider_manager.report_success(provider)

            # 6. Final Save
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE detection_tasks SET 
                        status = 'completed', completed_at = ?, 
                        regions_checked = ?, regions_available = ?, 
                        global_availability_percent = ?, anomaly_count = ?
                    WHERE id = ?
                """, (
                    datetime.now().isoformat(),
                    summary["total_checked"], summary["total_available"],
                    summary["global_availability"], len(anomalies),
                    task_id
                ))
                
                for r in regions:
                    reg_anoms = [a.reason for a in anomalies if a.region == r.region]
                    await db.execute("""
                        INSERT INTO region_results 
                        (task_id, region, status_code, response_ip, latency_ms, available, whitelist_match, anomalies)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task_id, r.region, r.status_code, r.response_ip, 
                        r.latency_ms, r.available, r.whitelist_match, ",".join(reg_anoms)
                    ))
                await db.commit()
                logger.info(f"Task {task_id} completed successfully.")

        except Exception as e:
            logger.error(f"Task {task_id} failed on {provider}: {e}")
            provider_manager.provider_manager.report_failure(provider)
            await alert_service.alert_service.send_emergency_alert(f"Platform Error: Task {task_id} failed. {str(e)[:100]}")
            
            async with get_db_connection() as db:
                await db.execute(
                    "UPDATE detection_tasks SET status = 'failed', error_message = ? WHERE id = ?",
                    (str(e), task_id)
                )
                await db.commit()
