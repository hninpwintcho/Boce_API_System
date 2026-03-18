import logging
import httpx
import os
from app.config import settings

logger = logging.getLogger(__name__)

class AlertService:
    """
    Platform Engineering Alerting (Phase 4).
    Sends grouped, intelligent alerts to external systems.
    """
    def __init__(self):
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")

    async def send_emergency_alert(self, message: str):
        """
        Sends critical platform-level alerts.
        """
        logger.critical(f"🔔 PLATFORM ALERT: {message}")
        if not self.webhook_url:
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.post(self.webhook_url, json={"text": f"🚨 Boce Proxy Alert: {message}"})
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")

alert_service = AlertService()
