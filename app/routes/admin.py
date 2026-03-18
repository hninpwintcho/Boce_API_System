import uuid
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

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
