import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

class WebhookService:
    """
    Commercial-Grade Webhook Delivery (Business Level)
    - Supports task-level overrides.
    - Asynchronous and non-blocking.
    - Basic retry logic for transient failures.
    """
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10)

    async def send_webhook(self, url: str, payload: dict, batch_id: str = None, event: str = "batch.completed"):
        if not url: return
        
        from app.database import get_db_connection
        import uuid
        import json

        delivery_id = str(uuid.uuid4())
        logger.info(f"📤 Sending webhook to {url} (ID: {delivery_id})")
        
        status = 'failed'
        status_code = None
        response_body = None

        for attempt in range(3):
            try:
                resp = await self.client.post(url, json=payload)
                status_code = resp.status_code
                response_body = resp.text[:500]
                if resp.status_code < 300:
                    logger.info(f"✅ Webhook delivered to {url}")
                    status = 'sent'
                    break
                logger.warning(f"⚠️ Webhook to {url} returned {resp.status_code} (Attempt {attempt+1})")
            except Exception as e:
                logger.error(f"❌ Webhook failure at {url}: {e} (Attempt {attempt+1})")
                response_body = str(e)
            
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        # Log delivery
        try:
            async with get_db_connection() as db:
                await db.execute("""
                    INSERT INTO webhook_deliveries (id, batch_id, url, event, payload, status_code, response_body, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (delivery_id, batch_id, url, event, json.dumps(payload), status_code, response_body, status))
                await db.commit()
        except Exception as db_err:
            logger.error(f"Failed to log webhook delivery: {db_err}")
        
        return status == 'sent'

webhook_service = WebhookService()
