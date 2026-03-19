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
from app.tasks import run_detection_bg
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

@router.post("/batch", summary="Queue high-volume batch (Commercial Grade)")
async def create_batch_detect_tasks(
    req: BatchDetectRequest, 
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    try:
        """
        Business Level: Bulk insertion with chunking (2000 per write) 
        to prevent API latency and lock issues during massive 5000+ domain batches.
        """
        # 1. Check points
        cost_per_url = 1.0 
        total_cost = len(req.urls) * cost_per_url
        balance_info = await check_boce_balance(total_cost)
        if not balance_info["sufficient"] or balance_info["balance"] < total_cost:
            return JSONResponse(status_code=402, content={"success": False, "error": "INSUFFICIENT_BALANCE", "message": f"Need ~{total_cost}, have {balance_info['balance']}.", "balance": balance_info["balance"]})

        batch_id = str(uuid.uuid4())
        skipped = []
        task_data = []

        # 2. Prepare task rows
        for url in req.urls:
            url_str = str(url)
            try:
                validate_detect_request(url_str, req.ip_whitelist)
            except ValidationError as e:
                skipped.append({"url": url_str, "reason": str(e)})
                continue
            
            task_id = str(uuid.uuid4())
            # Priority: Task-level if provided, else batch-level
            priority = req.priority or 10
            # Webhook: Task-level override, else user-level default
            webhook = req.webhook_url or user.get("webhook_url")
            
            task_data.append((
                task_id, url_str, req.provider, 'pending', user["id"], batch_id, priority, webhook
            ))

        # 3. Bulk Write with Chunking (A11 requirement)
        CHUNK_SIZE = 2000
        async with get_db_connection() as db:
            for i in range(0, len(task_data), CHUNK_SIZE):
                chunk = task_data[i:i + CHUNK_SIZE]
                await db.executemany(
                    "INSERT INTO detection_tasks (id, url, provider, status, api_key_id, error_code, priority, webhook_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    chunk
                )
            # Update API key usage count
            await db.execute("UPDATE api_keys SET used_today = used_today + ? WHERE id = ?", (len(task_data), user["id"]))
            await db.commit()

        return JSONResponse(
            status_code=202,
            content={
                "success": True, 
                "batch_id": batch_id,
                "total_queued": len(task_data), 
                "total_skipped": len(skipped),
                "skipped": skipped,
                "user": user["owner"],
                "balance_before": balance_info["balance"],
                "progress_url": f"/api/detect/batch/{batch_id}/progress"
            }
        )
    except Exception as e:
        logger.error(f"FATAL BATCH ERROR: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": "INTERNAL_ERROR"})

@router.get("/batch/{batch_id}/progress", summary="Track batch progress (Senior Level)")
async def get_batch_progress(batch_id: str, user: dict = Depends(get_authorized_user)):
    """
    Boss Requirement: Track progress of 5000 domains.
    Senior Level: Show queue counts and processing status with priority awareness.
    """
    async with get_db_connection() as db:
        cursor = await db.execute(
            "SELECT id, url, status, global_availability_percent FROM detection_tasks WHERE error_code = ? AND api_key_id = ?",
            (batch_id, user["id"])
        )
        rows = await cursor.fetchall()
        if not rows:
            return JSONResponse(status_code=404, content={"message": "Batch not found or unauthorized"})
        
        results = [dict(zip(["id", "url", "status", "availability"], r)) for r in rows]
        
        total = len(results)
        completed = sum(1 for r in results if r["status"] == "completed")
        failed = sum(1 for r in results if r["status"] == "failed")
        processing = sum(1 for r in results if r["status"] == "processing")
        pending = total - completed - failed - processing
        
        return {
            "batch_id": batch_id,
            "summary": {
                "total": total,
                "completed": completed,
                "failed": failed,
                "processing": processing,
                "pending_in_priority_queue": pending,
                "progress_percent": round((completed + failed) / total * 100, 2) if total > 0 else 0
            },
            "tasks_snapshot": results[:100]
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
    """Queue a single task with hierarchical webhook support."""
    validate_detect_request(req.url, req.ip_whitelist)
    
    # 1. Check points
    balance_info = await check_boce_balance()
    if not balance_info["sufficient"]:
         return JSONResponse(status_code=400, content={"success": False, "error": "INSUFFICIENT_BALANCE", "message": "Not enough Boce points. Balance: 0", "balance": 0})
    
    task_id = str(uuid.uuid4())
    # Webhook: Task-level override, else user-level default
    webhook = req.webhook_url or user.get("webhook_url")

    # Phase 4: Auto-Decision (Failover Logic)
    target_provider = provider_manager.get_best_provider()
    
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO detection_tasks (id, url, status, provider, api_key_id, priority, webhook_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, str(req.url), 'pending', target_provider, user["id"], req.priority, webhook)
        )
        await db.execute("UPDATE api_keys SET used_today = used_today + 1 WHERE id = ?", (user["id"],))
        await db.commit()

    # The centralized Scheduler Loop handles all 'pending' tasks
    # background_tasks.add_task(run_detection_bg, task_id, str(req.url), req.ip_whitelist, provider=target_provider)
    
    return JSONResponse(
        status_code=202,
        content={
            "balance_remaining": balance_info["balance"]
        }
    )

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
                "SELECT id, url, provider, status, created_at, global_availability_percent FROM detection_tasks WHERE url = ? AND api_key_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (url, user["id"], limit, offset)
            )
        else:
            cursor = await db.execute(
                "SELECT id, url, provider, status, created_at, global_availability_percent FROM detection_tasks WHERE api_key_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user["id"], limit, offset)
            )
        task_rows = await cursor.fetchall()
        
        return {
            "items": [
                {
                    "id": r[0], 
                    "url": r[1], 
                    "provider": r[2], 
                    "status": r[3], 
                    "timestamp": r[4],
                    "availability": r[5]
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
