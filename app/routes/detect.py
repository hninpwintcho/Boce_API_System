import uuid
import logging
import httpx
from typing import List, Optional

from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_db_connection
from app.models.schemas import DetectRequest, ErrorResponse
from app.services import boce_client
from app.services.validation_service import validate_detect_request
from app.services.auth_service import get_authorized_user
from app.tasks import run_detection_bg
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)

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

@router.post("/detect/batch", summary="Queue multiple detection tasks")
async def detect_batch(
    urls: List[str], 
    background_tasks: BackgroundTasks, 
    provider: str = "boce",
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    """Submit multiple URLs. Auditable and Traceable."""
    task_ids = []
    async with get_db_connection() as db:
        for url in urls:
            try:
                validate_detect_request(url, [])
            except ValidationError:
                continue

            task_id = str(uuid.uuid4())
            # Traceability: Link task to the API Key ID
            await db.execute(
                "INSERT INTO detection_tasks (id, url, status, provider, api_key_id) VALUES (?, ?, 'pending', ?, ?)",
                (task_id, url, provider, user["id"])
            )
            # Quota Tracking: Deduct 1 point per task (placeholder for real cost calculation)
            await db.execute("UPDATE api_keys SET used_today = used_today + 1 WHERE id = ?", (user["id"],))
            
            task_ids.append(task_id)
            background_tasks.add_task(run_detection_bg, task_id, url, provider=provider)
        await db.commit()

    return JSONResponse(
        status_code=202,
        content={"success": True, "total_queued": len(task_ids), "task_ids": task_ids, "user": user["owner"]}
    )

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
    
    task_id = str(uuid.uuid4())
    async with get_db_connection() as db:
        await db.execute(
            "INSERT INTO detection_tasks (id, url, status, api_key_id) VALUES (?, ?, 'pending', ?)",
            (task_id, req.url, user["id"])
        )
        await db.execute("UPDATE api_keys SET used_today = used_today + 1 WHERE id = ?", (user["id"],))
        await db.commit()

    background_tasks.add_task(run_detection_bg, task_id, req.url, req.ip_whitelist)
    
    return JSONResponse(
        status_code=202,
        content={
            "success": True, 
            "task_id": task_id, 
            "message": "Detection queued.",
            "user": user["owner"]
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
