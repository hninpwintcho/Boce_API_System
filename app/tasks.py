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
    Platform-Grade Priority Scheduler (Step 5/7 Suggestion)
    - Fetches from scan_batch_items
    - Priority-Aware (Higher priority first)
    """
    logger.info("🚀 Platform Scheduler started.")
    while True:
        try:
            async with get_db_connection() as db:
                # 1. Fetch pending items across all batches
                cursor = await db.execute("""
                    SELECT i.id, i.domain, i.batch_id, i.tenant_id, b.source_type
                    FROM scan_batch_items i
                    JOIN scan_batches b ON i.batch_id = b.id
                    WHERE i.status = 'pending' 
                    ORDER BY i.priority DESC, i.created_at ASC 
                    LIMIT 20
                """)
                items = await cursor.fetchall()
                
            for iid, domain, bid, tid, source in items:
                # Mark as processing immediately to avoid double-pick
                async with get_db_connection() as db:
                    await db.execute("UPDATE scan_batch_items SET status = 'processing', started_at = ? WHERE id = ?", (datetime.now().isoformat(), iid))
                    # Also update batch started_at if not set
                    await db.execute("UPDATE scan_batches SET started_at = ?, status = 'processing' WHERE id = ? AND started_at IS NULL", (datetime.now().isoformat(), bid))
                    await db.commit()

                # Trigger background worker
                asyncio.create_task(run_batch_item_worker(iid, domain, bid, tid))
            
            await asyncio.sleep(2) 
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
            await asyncio.sleep(5)

async def run_batch_item_worker(item_id: str, domain: str, batch_id: str, tenant_id: str):
    """Refined Worker (Phase 8: Multiplexed Task Handler)"""
    async with _semaphore:
        try:
            async with get_db_connection() as db:
                cursor = await db.execute("SELECT batch_type FROM scan_batches WHERE id = ?", (batch_id,))
                batch_type = (await cursor.fetchone())[0]

            import json
            summary_data = {}

            if batch_type == "detection":
                # Original BOCE Logic
                provider_task_id = await boce_client.create_boce_task(domain, "6,31,32")
                async with get_db_connection() as db:
                    await db.execute("UPDATE scan_batch_items SET provider_task_id = ? WHERE id = ?", (provider_task_id, item_id))
                    await db.commit()

                raw_result = None
                for _ in range(30):
                    await asyncio.sleep(10)
                    raw_result = await boce_client.poll_boce_result(provider_task_id)
                    if raw_result and raw_result.done: break
                
                if not raw_result or not raw_result.done:
                    raise Exception("Provider polling timeout")

                from app.services import detect_service, metrics_service
                regions = detect_service.normalize_regions(raw_result, None)
                summary = metrics_service.build_summary(regions)
                summary_data = summary.dict()
            
            elif batch_type == "cert":
                # New Certificate Logic
                from app.services.cert_service import cert_service
                cert_info = await cert_service.get_cert_info(domain)
                if not cert_info:
                    raise Exception("Certificate fetch returned no data")
                summary_data = cert_info

            # Final Save Item & Update Batch
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE scan_batch_items SET 
                        status = 'success', completed_at = ?, 
                        result_summary = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), json.dumps(summary_data), item_id))
                
                await db.execute("""
                    UPDATE scan_batches SET 
                        pending_items = pending_items - 1,
                        success_items = success_items + 1
                    WHERE id = ?
                """, (batch_id,))
                
                # Check for completion and trigger webhook
                cursor = await db.execute("SELECT pending_items, webhook_url, tenant_id, success_items, failed_items FROM scan_batches WHERE id = ?", (batch_id,))
                row = await cursor.fetchone()
                if row and row[0] == 0:
                    await db.execute("UPDATE scan_batches SET status = 'completed', completed_at = ? WHERE id = ?", (datetime.now().isoformat(), batch_id))
                    
                    webhook_url = row[1]
                    if webhook_url:
                        from app.services.webhook_service import webhook_service
                        payload = {
                            "event": "batch.completed",
                            "batch_id": batch_id,
                            "batch_type": batch_type,
                            "tenant_id": row[2],
                            "summary": {
                                "success": row[3],
                                "failed": row[4],
                                "total": row[3] + row[4]
                            }
                        }
                        asyncio.create_task(webhook_service.send_webhook(webhook_url, payload, batch_id=batch_id))
                    
                await db.commit()
            
            logger.info(f"✅ Item {item_id} ({batch_type}) completed.")

        except Exception as e:
            logger.error(f"❌ Worker Error for {item_id}: {e}", exc_info=True)
            async with get_db_connection() as db:
                await db.execute("""
                    UPDATE scan_batch_items SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?
                """, (str(e), datetime.now().isoformat(), item_id))
                await db.execute("""
                    UPDATE scan_batches SET 
                        pending_items = pending_items - 1,
                        failed_items = failed_items + 1
                    WHERE id = ?
                """, (batch_id,))
                await db.commit()
