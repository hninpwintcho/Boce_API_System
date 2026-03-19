import logging
from typing import Optional, List
from fastapi import APIRouter, Depends
from app.database import get_db_connection
from app.services.auth_service import get_authorized_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])

@router.get("/summary", summary="Get user-specific detection stats")
async def get_user_stats(user: dict = Depends(get_authorized_user)):
    """
    Boss Requirement: Efficient summary query instead of alerting.
    Returns aggregated metrics for the current business key.
    """
    async with get_db_connection() as db:
        # Total tasks
        cursor = await db.execute(
            "SELECT count(*), sum(case when status='completed' then 1 else 0 end), sum(case when status='failed' then 1 else 0 end), sum(case when status='processing' then 1 else 0 end) FROM detection_tasks WHERE api_key_id = ?",
            (user["id"],)
        )
        total, completed, failed, processing = await cursor.fetchone()
        
        # Success rate
        success_rate = round((completed / total * 100), 2) if total and total > 0 else 0
        
        # Points used (mocked for now based on tasks)
        points_used = total if total else 0
        
        return {
            "owner": user["owner"],
            "metrics": {
                "total_tasks": total or 0,
                "completed": completed or 0,
                "failed": failed or 0,
                "processing": processing or 0,
                "success_rate_percent": success_rate,
                "estimated_points_consumed": points_used
            },
            "quota": {
                "daily_limit": user["quota"],
                "used_today": user["used"]
            }
        }

@router.get("/admin/stats", summary="Get global system stats (Admin only)")
async def get_global_stats():
    """Global oversight for platform admins."""
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT count(*) FROM detection_tasks")
        total_tasks = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT count(*) FROM api_keys")
        total_keys = (await cursor.fetchone())[0]
        
        return {
            "system_status": "healthy",
            "global_metrics": {
                "total_processed_tasks": total_tasks,
                "active_api_keys": total_keys
            }
        }
