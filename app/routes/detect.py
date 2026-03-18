import uuid
import logging
import httpx
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_db_connection
from app.models.schemas import DetectRequest, ErrorResponse
from app.services import boce_client
from app.services.validation_service import validate_detect_request
from app.services.auth_service import get_authorized_user
from app.services.provider_manager import provider_manager
from app.tasks import run_detection_bg
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)

# ─── Helper: Balance Pre-Check ────────────────────────────────────────────────
async def _check_balance_sufficient(cost_estimate: float = 1.0) -> dict:
    """Boss Requirement: Check Boce balance BEFORE spending any points."""
    if not settings.BOCE_API_KEY:
        return {"sufficient": True, "balance": 999.99, "mock": True}
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

# ─── Batch Request Model ──────────────────────────────────────────────────────
class BatchDetectRequest(BaseModel):
    urls: List[str]
    ip_whitelist: Optional[List[str]] = None

router = APIRouter(prefix="/api", tags=["detect"])

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

@router.post("/detect/batch", summary="Queue a batch of domains (Boss-level)")
async def detect_batch(
    req: BatchDetectRequest,
    background_tasks: BackgroundTasks, 
    provider: str = "boce",
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    """
    Boss-Level Batch Submission:
    - Pre-checks balance before spending ANY points
    - Creates a batch_id to track progress of ALL domains together
    - Returns progress endpoint URL
    """
    urls = req.urls
    
    # 1. BALANCE PRE-CHECK (Boss Requirement #6)
    balance_info = await _check_balance_sufficient(cost_estimate=len(urls))
    if not balance_info["sufficient"]:
        return JSONResponse(status_code=402, content={
            "success": False,
            "error": "INSUFFICIENT_BALANCE",
            "message": f"Not enough Boce points. Need ~{len(urls)}, have {balance_info['balance']}.",
            "balance": balance_info["balance"]
        })
    
    # 2. CREATE BATCH ID (Boss Requirement #8: Track 100-5000 domains)
    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    task_ids = []
    skipped = []
    
    async with get_db_connection() as db:
        for url in urls:
            try:
                validate_detect_request(url, req.ip_whitelist)
            except ValidationError as e:
                skipped.append({"url": url, "reason": str(e)})
                continue

            task_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO detection_tasks (id, url, status, provider, api_key_id, error_code) VALUES (?, ?, 'pending', ?, ?, ?)",
                (task_id, str(url), provider, user["id"], batch_id)
            )
            await db.execute("UPDATE api_keys SET used_today = used_today + 1 WHERE id = ?", (user["id"],))
            
            task_ids.append(task_id)
            background_tasks.add_task(run_detection_bg, task_id, str(url), provider=provider, batch_id=batch_id)
        await db.commit()

    return JSONResponse(
        status_code=202,
        content={
            "success": True, 
            "batch_id": batch_id,
            "total_queued": len(task_ids), 
            "total_skipped": len(skipped),
            "skipped": skipped,
            "task_ids": task_ids, 
            "user": user["owner"],
            "balance_before": balance_info["balance"],
            "progress_url": f"/api/batch/{batch_id}/progress"
        }
    )

@router.get("/batch/{batch_id}/progress", summary="Track batch progress (Boss-level)")
async def get_batch_progress(batch_id: str):
    """Boss Requirement: How to track 100-5000 domains?"""
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id, url, status, global_availability_percent FROM detection_tasks WHERE error_code = ?",
            (batch_id,)
        )
        rows = await cursor.fetchall()
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Batch not found"})
        
        total = len(rows)
        completed = sum(1 for r in rows if r[2] == "completed")
        failed = sum(1 for r in rows if r[2] == "failed")
        pending = total - completed - failed
        
        progress_percent = round((completed + failed) / total * 100, 1) if total > 0 else 0
        
        return {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percent": progress_percent,
            "is_done": pending == 0,
            "tasks": [
                {"id": r[0], "url": r[1], "status": r[2], "availability": r[3]} for r in rows
            ]
        }

@router.post(
    "/detect",
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Queue a single detection task",
)
async def detect(
    req: DetectRequest, 
    background_tasks: BackgroundTasks, 
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    """Async entry point for single domain detection."""
    validate_detect_request(req.url, req.ip_whitelist)
    
    # BALANCE PRE-CHECK (Boss Requirement #6)
    balance_info = await _check_balance_sufficient(cost_estimate=1.0)
    if not balance_info["sufficient"]:
        return JSONResponse(status_code=402, content={
            "success": False,
            "error": "INSUFFICIENT_BALANCE",
            "message": f"Not enough Boce points. Balance: {balance_info['balance']}",
            "balance": balance_info["balance"]
        })
    
    task_id = str(uuid.uuid4())
    # Phase 4: Auto-Decision (Failover Logic)
    target_provider = provider_manager.get_best_provider()
    
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO detection_tasks (id, url, status, provider, api_key_id) VALUES (?, ?, 'pending', ?, ?)",
            (task_id, str(req.url), target_provider, user["id"])
        )
        await db.execute("UPDATE api_keys SET used_today = used_today + 1 WHERE id = ?", (user["id"],))
        await db.commit()

    # Start Background Task
    background_tasks.add_task(run_detection_bg, task_id, str(req.url), req.ip_whitelist, provider=target_provider)
    
    return JSONResponse(
        status_code=202,
        content={
            "success": True, 
            "task_id": task_id, 
            "message": "Detection queued.",
            "user": user["owner"],
            "balance_remaining": balance_info["balance"]
        }
    )

@router.get("/history", summary="View auditable task history")
async def get_history(limit: int = 50, offset: int = 0):
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id, url, provider, status, created_at FROM detection_tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        task_rows = await cursor.fetchall()
        
        return {
            "items": [{"id": r[0], "url": r[1], "provider": r[2], "status": r[3], "timestamp": r[4]} for r in task_rows]
        }

@router.get("/detect/{task_id}", summary="Get task status and result")
async def get_task_status(task_id: str):
    async with get_db_connection() as db:
        cursor = await db.execute("SELECT * FROM detection_tasks WHERE id = ?", (task_id,))
        task_row = await cursor.fetchone()
        if not task_row: return JSONResponse(status_code=404, content={"message": "Not found"})

        cols = [d[0] for d in cursor.description]
        task = dict(zip(cols, task_row))

        if task["status"] == "completed":
            cursor = await db.execute("SELECT * FROM region_results WHERE task_id = ?", (task_id,))
            rows = await cursor.fetchall()
            cols_r = [d[0] for d in cursor.description]
            task["regions"] = [dict(zip(cols_r, r)) for r in rows]

    return task
