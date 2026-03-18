import logging
import httpx
import os
from app.config import settings

logger = logging.getLogger(__name__)

class AlertService:
    """
    Platform Engineering Alerting (Phase 4 + Phase 5).
    Sends intelligent alerts to Telegram and/or Webhook.
    """
    def __init__(self):
        self.webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    async def send_telegram(self, message: str):
        """Send a message to Telegram Bot."""
        if not self.telegram_enabled:
            logger.debug("Telegram not configured, skipping.")
            return False
        
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ Telegram alert sent to chat {self.telegram_chat_id}")
                    return True
                else:
                    logger.error(f"Telegram API returned {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    async def send_emergency_alert(self, message: str):
        """Sends critical platform-level alerts to all channels."""
        logger.critical(f"🔔 PLATFORM ALERT: {message}")
        
        # Send to Telegram
        await self.send_telegram(f"🚨 *Boce Proxy Alert*\n\n{message}")
        
        # Send to Webhook (Slack/Discord/Custom)
        if self.webhook_url:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(self.webhook_url, json={"text": f"🚨 Boce Proxy Alert: {message}"})
            except Exception as e:
                logger.error(f"Failed to send webhook: {e}")

    async def send_batch_complete(self, batch_id: str, total: int, completed: int, failed: int):
        """Alert when a batch job finishes."""
        msg = (
            f"📊 *Batch Complete*\n\n"
            f"Batch: `{batch_id}`\n"
            f"Total: {total}\n"
            f"✅ Completed: {completed}\n"
            f"❌ Failed: {failed}\n"
        )
        await self.send_telegram(msg)

    async def send_balance_warning(self, balance: float):
        """Alert when balance is running low."""
        msg = (
            f"⚠️ *Low Balance Warning*\n\n"
            f"Boce balance is low: *{balance}* points\n"
            f"Please top up to avoid service interruption."
        )
        await self.send_telegram(msg)

    async def send_domain_down(self, url: str, availability: float):
        """Alert when a domain's availability drops below threshold."""
        msg = (
            f"🔴 *Domain Down Alert*\n\n"
            f"URL: `{url}`\n"
            f"Availability: *{availability}%*\n"
            f"Action required!"
        )
        await self.send_telegram(msg)

alert_service = AlertService()
