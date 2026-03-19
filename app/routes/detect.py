import uuid
import logging
import httpx
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_db_connection
from app.models.schemas import DetectRequest, ErrorResponse, BatchDetectRequest
from app.services import boce_client
from app.services.validation_service import validate_detect_request
from app.services.auth_service import get_authorized_user
from app.services.provider_manager import provider_manager
# from app.tasks import run_detection_bg # Removed (Phase 5)
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)

# ─── Helper: Balance Pre-Check ────────────────────────────────────────────────
async def check_boce_balance(cost_estimate: float = 1.0) -> dict:
    """Boss Requirement: Check Boce balance BEFORE spending any points."""
    if not settings.BOCE_API_KEY:
        return {"sufficient": True, "balance": 999.99, "mock": True}
    if settings.BOCE_FORCE_MOCK:
        return {"sufficient": True, "balance": 9999, "mock": True}
    try:
        url = f"{settings.BOCE_API_URL}/balance"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"key": settings.BOCE_API_KEY})
            data = resp.json()
            remaining = data.get("data", {}).get("remaining", 0)
            return {"sufficient": remaining >= cost_estimate, "balance": remaining, "data": data}
    except Exception as e:
        logger.error(f"Balance pre-check failed: {e}")
        return {"sufficient": True, "balance": -1, "error": str(e)}

router = APIRouter(tags=["detect"])

@router.get("/balance", summary="Check Provider balance")
async def get_balance(provider: str = "boce"):
    """Check balance for a specific provider. Default is Boce."""
    if provider == "boce":
        if not settings.BOCE_API_KEY:
            return {"success": True, "balance": 999.99, "point": 1000000, "mock": True}
        
        # settings.BOCE_API_URL is "https://api.boce.com/v3"
        url = f"{settings.BOCE_API_URL}/balance"
        params = {"key": settings.BOCE_API_KEY}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return JSONResponse(status_code=502, content={"success": False, "message": "Failed to fetch balance from Boce."})
    
    return JSONResponse(status_code=400, content={"success": False, "message": f"Provider {provider} not supported."})

@router.post("/batch", summary="Queue robust high-volume batch")
async def create_batch_detect_tasks(
    req: BatchDetectRequest, 
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    try:
        # 1. Balance and Budget Pre-Check
        cost_per_url = 1.0 
        total_cost = len(req.urls) * cost_per_url
        balance_info = await check_boce_balance(total_cost)
        if not balance_info["sufficient"]:
            return JSONResponse(status_code=402, content={"success": False, "error": "INSUFFICIENT_BALANCE"})

        from app.services.batch_service import batch_service
        batch_id = await batch_service.create_monitoring_batch(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            items_list=req.urls,
            batch_type="detection",
            priority=req.priority,
            webhook_url=req.webhook_url
        )

        return JSONResponse(
            status_code=202,
            content={
                "success": True, 
                "batch_id": batch_id,
                "total": len(req.urls),
                "progress_url": f"/api/detect/batch/{batch_id}"
            }
        )
    except Exception as e:
        logger.error(f"Batch Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": "INTERNAL_ERROR"})

@router.get("/batch/{batch_id}", summary="Get batch progress (V1)")
async def get_batch_progress(batch_id: str, user: dict = Depends(get_authorized_user)):
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM scan_batches WHERE id = ? AND tenant_id = ?",
            (batch_id, user["tenant_id"])
        )
        batch = await cursor.fetchone()
        if not batch:
            return JSONResponse(status_code=404, content={"message": "Batch not found"})
        
        cols = [d[0] for d in cursor.description]
        batch_dict = dict(zip(cols, batch))
        
        # Calculate progress percent
        total = batch_dict["total_items"]
        done = batch_dict["success_items"] + batch_dict["failed_items"]
        batch_dict["progress_percent"] = round((done / total) * 100, 2) if total > 0 else 0
        
        return batch_dict

@router.get("/batch/{batch_id}/stats", summary="Get batch aggregated stats")
async def get_batch_stats(batch_id: str, user: dict = Depends(get_authorized_user)):
    """Layer 2: Aggregated availability and anomalies (ChatGPT Step 10)."""
    async with get_db_connection() as db:
        # 1. Basic counts
        cursor = await db.execute(
            "SELECT status, COUNT(*) as count FROM scan_batch_items WHERE batch_id = ? GROUP BY status",
            (batch_id,)
        )
        status_counts = dict(await cursor.fetchall())

        # 2. Availability bucket (Simplified demo logic)
        cursor = await db.execute("""
            SELECT 
                SUM(CASE WHEN instr(result_summary, '"available": true') THEN 1 ELSE 0 END) as good,
                SUM(CASE WHEN instr(result_summary, '"available": false') THEN 1 ELSE 0 END) as poor
            FROM scan_batch_items WHERE batch_id = ?
        """, (batch_id,))
        avail = await cursor.fetchone()
        
        return {
            "batch_id": batch_id,
           "counts": {
               "total": sum(status_counts.values()),
               "by_status": status_counts
           },
           "availability_summary": {
               "good": avail[0] or 0,
               "poor": avail[1] or 0
           }
        }


@router.post(
    "",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Queue a single detection task (Unified)",
)
async def detect(
    req: DetectRequest, 
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    """Queue a single task by creating a 1-item batch."""
    # reuse the batch logic
    batch_req = BatchDetectRequest(
        urls=[str(req.url)],
        ip_whitelist=req.ip_whitelist,
        priority=req.priority,
        webhook_url=req.webhook_url
    )
    return await create_batch_detect_tasks(batch_req, user)

@router.get("/detect/history", summary="View auditable task history with URL filter")
@router.get("/history", include_in_schema=False)
async def get_history(
    url: Optional[str] = None, 
    limit: int = 50, 
    offset: int = 0,
    user: dict = Depends(get_authorized_user)
):
    """
    Boss Requirement: List stored results for a URL, newest first.
    Isolation: Strictly filtered by the requesting API key.
    """
    async with get_db_connection() as db:
        if url:
            cursor = await db.execute(
                "SELECT id, domain, status, created_at, result_summary FROM scan_batch_items WHERE domain = ? AND tenant_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (url, user["tenant_id"], limit, offset)
            )
        else:
            cursor = await db.execute(
                "SELECT id, domain, status, created_at, result_summary FROM scan_batch_items WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user["tenant_id"], limit, offset)
            )
        task_rows = await cursor.fetchall()
        
        return {
            "items": [
                {
                    "id": r[0], 
                    "url": r[1], 
                    "provider": "boce",
                    "status": r[2], 
                    "timestamp": r[3],
                    "availability": 100 if r[2] == 'completed' else 0 # Placeholder for now
                } for r in task_rows
            ],
            "limit": limit,
            "offset": offset,
            "url_filter": url
        }

@router.get("/detect/{task_id}", summary="Get task status and result")
async def get_task_status(task_id: str, user: dict = Depends(get_authorized_user)):
    """Isolated status retrieval."""
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM detection_tasks WHERE id = ? AND api_key_id = ?", (task_id, user["id"]))
        task_row = await cursor.fetchone()
        if not task_row: return JSONResponse(status_code=404, content={"message": "Task not found or unauthorized"})

        cols = [d[0] for d in cursor.description]
        task = dict(zip(cols, task_row))

        if task["status"] == "completed":
            cursor = await db.execute("SELECT * FROM region_results WHERE task_id = ?", (task_id,))
            rows = await cursor.fetchall()
            cols_r = [d[0] for d in cursor.description]
            task["regions"] = [dict(zip(cols_r, r)) for r in rows]

    return task
