"""
detect.py
---------
POST /api/detect  route — Step 3 + orchestration

Flow:
  1. Parse + validate request body (Pydantic + extra validation_service)
  2. Call detect_service.run_detection()
  3. Patch anomaly_count into summary (after anomalies computed)
  4. Return DetectionResult JSON

Error conditions handled:
  • 400 — missing/invalid URL, invalid whitelist format
  • 502 — bad Boce response
  • 503 — Boce unreachable
  • 504 — Boce timeout
  • 500 — unexpected error
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.models.schemas import DetectRequest, DetectionResult, ErrorResponse
from app.services import detect_service
from app.services.validation_service import validate_detect_request
from app.utils.errors import (
    AppBaseError,
    ValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["detect"])


@router.post(
    "/detect",
    response_model=DetectionResult,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Detect URL availability across regions",
    description=(
        "Send a URL to Boce and receive normalised regional availability "
        "results, metrics, whitelist validation, and anomaly tagging."
    ),
)
async def detect(request: DetectRequest) -> JSONResponse:
    url = str(request.url)
    ip_whitelist = request.ip_whitelist

    # Extra validation beyond Pydantic (whitelist content checks)
    try:
        validate_detect_request(url, ip_whitelist)
    except ValidationError as exc:
        return _error_response(exc)

    try:
        result = await detect_service.run_detection(url, ip_whitelist)

        # Patch anomaly_count NOW that anomaly_service has populated it
        result.summary.anomaly_count = len(result.anomaly_list)

        return JSONResponse(content=result.dict(), status_code=200)

    except AppBaseError as exc:
        logger.warning("[%s] %s", exc.error_code, exc.message)
        return _error_response(exc)

    except Exception as exc:
        logger.exception("Unexpected error in /api/detect: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            },
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _error_response(exc: AppBaseError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "success": False,
            "error_code": exc.error_code,
            "message": exc.message,
        },
    )
