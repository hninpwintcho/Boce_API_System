import logging
import asyncio
import os
import uvicorn
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db, get_db_connection
from app.tasks import run_batch_item_worker, start_priority_scheduler
from app.routes.detect import router as detect_router
from app.routes.admin import router as admin_router
from app.routes.stats import router as stats_router
from app.routes.dns import router as dns_router
from app.routes.certs import router as certs_router

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    logger.info("🚀 Database initialized.")

    # Recovery Manager
    async def resume_tasks():
        await asyncio.sleep(1) # Wait for server to be fully ready
        async with get_db_connection() as db:
            cursor = await db.execute(
                "SELECT id, domain, batch_id, tenant_id FROM scan_batch_items WHERE status = 'processing'"
            )
            rows = await cursor.fetchall()
            for row in rows:
                logger.info(f"🔄 Recovery: Resuming item {row[0]} in batch {row[2]}")
                asyncio.create_task(run_batch_item_worker(row[0], row[1], row[2], row[3]))
        if rows: logger.info(f"✅ Recovery complete. Resumed {len(rows)} items.")

    asyncio.create_task(resume_tasks())
    # Scheduler is now a separate service (Phase 5)
    # asyncio.create_task(start_priority_scheduler())
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down gracefully...")

app = FastAPI(
    title="Boce Unified Proxy",
    version="3.0.0",
    description="Professional-grade, fault-tolerant detection gateway.",
    lifespan=lifespan
)

# ─── Middleware: Tracing & Performance ────────────────────────────────────────
@app.middleware("http")
async def add_tracing_and_timer(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()
    
    # Inject context for logging
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    response.headers["X-Request-ID"] = request_id
    
    logger.info(f"REQ {request_id} | {request.method} {request.url.path} | {response.status_code} | {process_time:.2f}ms")
    return response

# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    """Liveness & Readiness probe for professional deployments."""
    status = {"status": "ok", "database": "unknown", "version": "3.0.0"}
    try:
        async with get_db_connection() as db:
            await db.execute("SELECT 1")
            status["database"] = "connected"
    except Exception as e:
        status["status"] = "degraded"
        status["database"] = f"error: {str(e)}"
    
    return status

# ─── Routers ──────────────────────────────────────────────────────────────────

@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root_redirect(request: Request):
    return RedirectResponse(url="/dashboard")

app.include_router(detect_router, prefix="/api/detect", tags=["Detection"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(stats_router, prefix="/api/stats", tags=["Stats"])
app.include_router(dns_router, prefix="/api/dns", tags=["DNS Management"])
app.include_router(certs_router, prefix="/api/certs", tags=["Certificates"])

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# Serve static files for the dashboard
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ...
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled: {exc}")
    return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
