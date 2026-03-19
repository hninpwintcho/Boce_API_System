import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.database import get_db_connection
from app.models.schemas import CertCheckRequest, ErrorResponse
from app.services.auth_service import get_authorized_user
from app.services.batch_service import batch_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["certificates"])

@router.post("/check", summary="Queue batch certificate expiry scan")
async def create_cert_check_batch(
    req: CertCheckRequest, 
    user: dict = Depends(get_authorized_user)
) -> JSONResponse:
    try:
        batch_id = await batch_service.create_monitoring_batch(
            tenant_id=user["tenant_id"],
            user_id=user["id"],
            items_list=req.domains,
            batch_type="cert",
            priority=req.priority,
            webhook_url=req.webhook_url
        )

        return JSONResponse(
            status_code=202,
            content={
                "success": True, 
                "batch_id": batch_id,
                "total": len(req.domains),
                "progress_url": f"/api/detect/batch/{batch_id}"
            }
        )
    except Exception as e:
        logger.error(f"Cert Batch Error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": "INTERNAL_ERROR"})

@router.get("/summary", summary="Get certificate expiry insights")
async def get_cert_summary(user: dict = Depends(get_authorized_user)):
    """
    Boss Requirement: Critical insights for CDN operations.
    Returns counts for expired and expiring-soon certs.
    """
    async with get_db_connection() as db:
        # We query the latest result_summary for each unique domain in the tenant's cert batches
        cursor = await db.execute("""
            SELECT result_summary FROM scan_batch_items 
            WHERE tenant_id = ? AND status = 'success' 
            AND batch_id IN (SELECT id FROM scan_batches WHERE batch_type = 'cert')
        """, (user["tenant_id"],))
        
        summaries = [r[0] for r in await cursor.fetchall()]
        
        expired = 0
        critical_7d = 0
        warning_30d = 0
        
        import json
        for s in summaries:
            try:
                data = json.loads(s)
                days = data.get("days_remaining", 999)
                if days <= 0: expired += 1
                elif days < 7: critical_7d += 1
                elif days < 30: warning_30d += 1
            except: pass
            
        return {
            "metrics": {
                "total_monitored": len(summaries),
                "expired": expired,
                "critical_7d": critical_7d,
                "warning_30d": warning_30d
            }
        }

@router.get("/items", summary="Get detailed certificate audit logs")
async def get_cert_items(
    limit: int = 50, 
    offset: int = 0,
    user: dict = Depends(get_authorized_user)
):
    async with get_db_connection() as db:
        cursor = await db.execute("""
            SELECT id, domain, status, created_at, result_summary, error_message 
            FROM scan_batch_items 
            WHERE tenant_id = ? 
            AND batch_id IN (SELECT id FROM scan_batches WHERE batch_type = 'cert')
            ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (user["tenant_id"], limit, offset))
        
        rows = await cursor.fetchall()
        
        items = []
        import json
        for r in rows:
            summary = {}
            if r[4]:
                try: summary = json.loads(r[4])
                except: pass
            
            items.append({
                "id": r[0],
                "domain": r[1],
                "status": r[2],
                "created_at": r[3],
                "issuer": summary.get("issuer", "N/A"),
                "expiry_date": summary.get("expiry_date", "N/A"),
                "days_remaining": summary.get("days_remaining", -1),
                "error": r[5]
            })
            
        return {"items": items}
