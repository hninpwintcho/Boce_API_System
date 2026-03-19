import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db_connection
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# alert_service.telegram_enabled logic removed as requested by A11 (Alerting is considered unnecessary)
# Moving to a formal Stats API for efficient monitoring.

class KeyCreateRequest(BaseModel):
    owner_name: str
    daily_quota: float = 100.0
    webhook_url: Optional[str] = None

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
            "INSERT INTO api_keys (id, key_secret, owner_name, daily_quota, webhook_url) VALUES (?, ?, ?, ?, ?)",
            (new_id, secret, req.owner_name, req.daily_quota, req.webhook_url)
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
        cursor = await db.execute("SELECT id, owner_name, daily_quota, used_today, is_active, key_secret FROM api_keys")
        rows = await cursor.fetchall()
        return [dict(zip(["id", "owner", "quota", "used", "active", "secret"], r)) for r in rows]

@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str):
    """Business isolation: Destroy a key."""
    async with get_db_connection() as db:
        await db.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
        await db.commit()
    return {"success": True, "message": f"API Key {key_id} revoked."}

@router.patch("/keys/{key_id}")
async def update_api_key(
    key_id: str, 
    daily_quota: Optional[float] = None, 
    is_active: Optional[bool] = None,
    webhook_url: Optional[str] = None
):
    """Business isolation: Lifecycle management."""
    async with get_db_connection() as db:
        if daily_quota is not None:
            await db.execute("UPDATE api_keys SET daily_quota = ? WHERE id = ?", (daily_quota, key_id))
        if is_active is not None:
            await db.execute("UPDATE api_keys SET is_active = ? WHERE id = ?", (is_active, key_id))
        if webhook_url is not None:
            await db.execute("UPDATE api_keys SET webhook_url = ? WHERE id = ?", (webhook_url, key_id))
        await db.commit()
    return {"success": True, "message": f"API Key {key_id} updated."}

