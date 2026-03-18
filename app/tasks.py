import logging
from datetime import datetime
from app.database import get_db_connection
from app.services import boce_client, metrics_service, anomaly_service, detect_service
import asyncio

logger = logging.getLogger(__name__)

# Throttling Semaphore for concurrency control
_semaphore = asyncio.Semaphore(20)

async def run_detection_bg(task_id: str, url: str, ip_whitelist: list[str] = None, provider: str = "boce"):
    """
    Robust multi-provider background worker:
    1. Zero Point Wastage: Checks if provider_task_id exists before creating.
    2. Concurrency Control: Uses semaphore.
    3. Multi-Provider: Supports Boce and future providers via provider column.
    """
    async with _semaphore:
        try:
            async with get_db_connection() as db:
                # 1. Check existing state
                cursor = await db.execute(
                    "SELECT provider_task_id, status FROM detection_tasks WHERE id = ?", 
                    (task_id,)
                )
                row = await cursor.fetchone()
                if not row: return

                provider_task_id, status = row
                
                # 2. Point Conservation logic
                if not provider_task_id:
                    # Mark as processing locally first
                    await db.execute("UPDATE detection_tasks SET status = ? WHERE id = ?", ("processing", task_id))
                    await db.commit()

                    # Call provider (Boce is the only one for now)
                    if provider == "boce":
                        host = boce_client.extract_host(url)
                        # Atomic Creation: Save provider_task_id immediately after Boce returns it
                        provider_task_id = await boce_client.create_boce_task(host, "6,31,32")
                        
                        await db.execute(
                            "UPDATE detection_tasks SET provider_task_id = ?, status = ? WHERE id = ?",
                            (provider_task_id, "created", task_id)
                        )
                        await db.commit()
                        logger.info(f"Task {task_id} created on {provider} with ID {provider_task_id}")

                # 3. Poll and finalize
                raw_result = await boce_client.poll_boce_result(provider_task_id)
                
                # Normalize and Save
                regions = detect_service.normalize_regions(raw_result, ip_whitelist)
                summary = metrics_service.build_summary(regions)
                anomalies = anomaly_service.build_anomaly_list(regions)
                
                await db.execute("""
                    UPDATE detection_tasks SET 
                        status = 'completed', completed_at = ?, 
                        regions_checked = ?, regions_available = ?, 
                        global_availability_percent = ?, anomaly_count = ?
                    WHERE id = ?
                """, (datetime.utcnow().isoformat(), summary.regions_checked, summary.regions_available, 
                      summary.global_availability_percent, len(anomalies), task_id))

                for reg in regions:
                    reg_anoms = ",".join([a.reason for a in anomalies if a.region == reg.region])
                    await db.execute("""
                        INSERT INTO region_results 
                        (task_id, region, status_code, response_ip, latency_ms, available, whitelist_match, anomalies)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (task_id, reg.region, reg.status_code, reg.response_ip, reg.latency_ms, 
                          reg.available, reg.whitelist_match, reg_anoms))
                
                await db.commit()

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            async with get_db_connection() as db:
                await db.execute(
                    "UPDATE detection_tasks SET status = 'failed', error_message = ? WHERE id = ?",
                    (str(e), task_id)
                )
                await db.commit()
