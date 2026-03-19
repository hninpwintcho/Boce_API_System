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

    async def send_webhook(self, url: str, payload: dict):
        if not url: return
        
        logger.info(f"📤 Sending webhook to {url}")
        for attempt in range(3):
            try:
                resp = await self.client.post(url, json=payload)
                if resp.status_code < 300:
                    logger.info(f"✅ Webhook delivered to {url}")
                    return True
                logger.warning(f"⚠️ Webhook to {url} returned {resp.status_code} (Attempt {attempt+1})")
            except Exception as e:
                logger.error(f"❌ Webhook failure at {url}: {e} (Attempt {attempt+1})")
            
            await asyncio.sleep(2 ** attempt) # Exponential backoff
        
        return False

webhook_service = WebhookService()
