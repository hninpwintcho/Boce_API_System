import uuid
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db_connection
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/alert/test", summary="Test Telegram alert")
async def test_telegram():
    """Send a test message to Telegram to verify the bot is configured correctly."""
    if not alert_service.telegram_enabled:
        return {"success": False, "message": "Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"}
    
    result = await alert_service.send_telegram(
        "✅ *Boce Proxy Test Alert*\n\n"
        "Your Telegram integration is working!\n"
        "You will receive alerts for:\n"
        "• Batch completion\n"
        "• Low balance warnings\n"
        "• Domain down alerts"
    )
    return {"success": result, "message": "Test alert sent!" if result else "Failed to send alert."}

class KeyCreateRequest(BaseModel):
    owner_name: str
    daily_quota: float = 100.0

@router.post("/keys")
async def create_api_key(req: KeyCreateRequest):
    """
    Admin endpoint to issue new API Keys.
    In a real system, this would itself be protected by a super-admin password.
    """
    new_id = str(uuid.uuid4())[:8]
    secret = "sk-" + str(uuid.uuid4()).replace("-", "")[:24]
    
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO api_keys (id, key_secret, owner_name, daily_quota) VALUES (?, ?, ?, ?)",
            (new_id, secret, req.owner_name, req.daily_quota)
        )
        await db.commit()
    
    return {
        "success": True,
        "api_key": secret,
        "owner": req.owner_name,
        "daily_quota": req.daily_quota,
        "instructions": "Add this key to your X-API-KEY header for all /api/detect calls."
    }

@router.get("/keys")
async def list_keys():
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT id, owner_name, daily_quota, used_today, is_active FROM api_keys")
        rows = await cursor.fetchall()
        return [dict(zip(["id", "owner", "quota", "used", "active"], r)) for r in rows]
