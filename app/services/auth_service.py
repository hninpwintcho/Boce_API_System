import logging
from fastapi import Request, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from app.database import get_db_connection

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_authorized_user(api_key: str = Security(api_key_header)):
    """
    Dependency to validate API Key and Quota.
    Ensures that only authorized agents can drain Boce points.
    """
    if not api_key:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="API Key is missing")

    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id, owner_name, daily_quota, used_today, is_active FROM api_keys WHERE key_secret = ?",
            (api_key,)
        )
        row = await cursor.fetchone()
        
        if not row:
            logger.warning(f"Unauthorized access attempt with key: {api_key[:8]}...")
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key")
        
        user_id, owner, quota, used, active = row
        
        if not active:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="API Key is deactivated")
            
        if used >= quota:
            logger.error(f"Quota exceeded for {owner} ({used}/{quota})")
            raise HTTPException(status_code=429, detail="Daily point quota exceeded. High-cost mistake prevented.")

        return {"id": user_id, "owner": owner}
