import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas import DNSRecordCreate, DNSRecordUpdate, ErrorResponse
from app.services.dns_center_service import dns_center_service
from app.services.auth_service import get_authorized_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["DNS Management"])

@router.post("/records", summary="Create DNS records (Bulk supported)")
async def create_dns_records(
    req: DNSRecordCreate,
    user: dict = Depends(get_authorized_user)
):
    """
    Create one or more DNS records for a domain.
    Implements reliable single-request loop for bulk operations.
    """
    try:
        # Convert Pydantic models to dicts for the service
        records_data = [r.dict() for r in req.records]
        results = await dns_center_service.create_records(req.domain, records_data)
        
        return {
            "success": True,
            "domain": req.domain,
            "results": results
        }
    except Exception as e:
        logger.error(f"DNS Creation Error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.put("/records/{record_id}", summary="Update a DNS record")
async def update_dns_record(
    record_id: str,
    req: DNSRecordUpdate,
    user: dict = Depends(get_authorized_user)
):
    try:
        result = await dns_center_service.update_record(record_id, req.dict(exclude_unset=True))
        return result
    except Exception as e:
        logger.error(f"DNS Update Error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.delete("/records/{record_id}", summary="Delete a DNS record")
async def delete_dns_record(
    record_id: str,
    user: dict = Depends(get_authorized_user)
):
    try:
        result = await dns_center_service.delete_record(record_id)
        return result
    except Exception as e:
        logger.error(f"DNS Delete Error: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@router.get("/query", summary="Query authoritative DNS records")
async def query_dns(
    domain: str,
    user: dict = Depends(get_authorized_user)
):
    """Bridge to the DNS Center query API."""
    result = await dns_center_service.query_dns(domain)
    if not result:
        return JSONResponse(status_code=404, content={"success": False, "message": "No records found or API error"})
    return result
