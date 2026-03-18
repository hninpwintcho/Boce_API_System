"""
main.py
-------
FastAPI application entry point — Step 8

Registers:
  • /api/detect  route
  • Pydantic validation error handler (returns 400 JSON)
  • Global 500 handler
  • /health  liveness endpoint
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes.detect import router as detect_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Boce Detection API",
    version="1.0.0",
    description=(
        "Phase 1 MVP — wraps the Boce API and exposes a unified "
        "POST /api/detect endpoint with normalised regional results, "
        "metrics, whitelist validation, and anomaly tagging."
    ),
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(detect_router)


# ─── Exception handlers ───────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic 422 errors into our standard 400 JSON format."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = " → ".join(str(loc) for loc in first.get("loc", []))
    msg = first.get("msg", "Validation error")
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error_code": "INVALID_REQUEST",
            "message": f"Field '{field}': {msg}",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
        },
    )


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="Liveness check")
async def health() -> dict:
    return {"status": "ok"}


# ─── Dev server entry ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
    )
