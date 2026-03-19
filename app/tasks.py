import logging
import asyncio
from datetime import datetime
from app.database import get_db_connection
from app.services import boce_client, metrics_service, anomaly_service, detect_service, ai_monitor_service, provider_manager, webhook_service

logger = logging.getLogger(__name__)

# Throttling Semaphore for concurrency control (Phase 2)
_semaphore = asyncio.Semaphore(20)

async def start_priority_scheduler():
    """
    Enterprise-Grade Priority Scheduler (v3)
    - Non-blocking: Handles 5000+ domains without delaying urgent ones.
    - Priority-Aware: Fetches tasks with highest weight/priority first.
    """
    logger.info("🚀 Priority Scheduler started.")
    while True:
        try:
            async with get_db_connection() as db:
                # Find pending tasks ordered by priority
                cursor = await db.execute(
                    "SELECT id, url, provider, error_code, webhook_url FROM detection_tasks WHERE status = 'pending' ORDER BY priority DESC, created_at ASC LIMIT 10"
                )
                tasks = await cursor.fetchall()
                
            for tid, url, prov, batch_id, webhook in tasks:
                # Trigger background worker (respecting semaphore internally)
                asyncio.create_task(run_detection_bg(tid, url, provider=prov, batch_id=batch_id, webhook_url=webhook))

                # Mark as processing immediately to avoid double-pick
                async with get_db_connection() as db:
                    await db.execute("UPDATE detection_tasks SET status = 'processing' WHERE id = ?", (tid,))
                    await db.commit()
            
            await asyncio.sleep(2) # Poll every 2 seconds
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
            await asyncio.sleep(5)

async def run_detection_bg(task_id: str, url: str, ip_whitelist: list[str] = None, provider: str = "boce", batch_id: str = None, webhook_url: str = None):
    """
    Unified Background Worker (Phase 1-5):
    - Throttling & Fault Recovery
    - AI Anomaly Detection
    """
    async with _semaphore:
        try:
            async with get_db_connection() as db:
                # 1. Recovery Check
                cursor = await db.execute(
                    "SELECT provider_task_id, status FROM detection_tasks WHERE id = ?", 
                    (task_id,)
                )
                row = await cursor.fetchone()
                if not row: return

                provider_task_id, status = row
                
                # 2. Create Task
                if not provider_task_id:
                    host = boce_client.extract_host(url)
                    provider_task_id = await boce_client.create_boce_task(host, "6,31,32")
                    
                    await db.execute(
                        "UPDATE detection_tasks SET provider_task_id = ?, status = 'processing' WHERE id = ? ",
                        (provider_task_id, task_id)
                    )
                    await db.commit()

            # 3. Poll for results
            raw_result = None
            for _ in range(30):
                await asyncio.sleep(10)
                raw_result = await boce_client.poll_boce_result(provider_task_id)
                if raw_result and raw_result.done: break
            
            if not raw_result or not raw_result.done:
                raise Exception("Provider polling timeout")

            # 4. Analyze & AI Triage
            if settings.BOCE_FORCE_MOCK:
                # Simulate a delay and then fake success for demo purposes
                await asyncio.sleep(3)
                summary = {"total_checked": 3, "total_available": 3, "global_availability": 100.0}
                regions = [] # Mocked region data
                anomalies = []
            else:
                raw_dict = {
                    "id": raw_result.id, "done": raw_result.done,
                    "list": [r.dict() for r in raw_result.list],
                    "max_node": raw_result.max_node
                }

                regions = detect_service.normalize_regions(raw_dict, ip_whitelist)
                summary = metrics_service.build_summary(regions)
                anomalies = anomaly_service.build_anomaly_list(regions)
            ai_anoms = ai_monitor_service.ai_monitor.analyze_batch(regions)
            anomalies.extend(ai_anoms)
            
            # 5. Heartbeat
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
                    """, (task_id, r.region, r.status_code, r.response_ip, r.latency_ms, r.available, r.whitelist_match, ",".join(reg_anoms)))
                await db.commit()

            # 8. Batch Level tracking (Database only, alerting removed as requested)
            # 5. Notify Webhook (Commercial Grade)
            if webhook_url:
                asyncio.create_task(webhook_service.send_webhook(webhook_url, {
                    "task_id": task_id,
                    "url": url,
                    "status": "completed",
                    "availability": summary.get("global_availability"),
                    "anomalies": len(anomalies)
                }))

            await db.execute(
                "UPDATE detection_tasks SET status = 'completed', global_availability_percent = ?, anomaly_count = ? WHERE id = ?",
                (summary.get("global_availability", 0.0), len(anomalies), task_id)
            )
            await db.commit()
            logger.info(f"✅ Task {task_id} completed. Webhook triggered if set.")

        except Exception as e:
            logger.error(f"❌ Worker Error for {task_id}: {e}")
            provider_manager.provider_manager.report_failure(provider)
            
            async with get_db_connection() as db:
                await db.execute("UPDATE detection_tasks SET status = 'failed', error_code = ? WHERE id = ?", (str(e), task_id))
                await db.commit()
            
            # Notify failure to webhook too
            if webhook_url:
                asyncio.create_task(webhook_service.send_webhook(webhook_url, {
                    "task_id": task_id,
                    "url": url,
                    "status": "failed",
                    "error": str(e)
                }))
