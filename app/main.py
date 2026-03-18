import logging
import asyncio
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import settings
from app.database import init_db, get_db_connection
from app.tasks import run_detection_bg
from app.routes.detect import router as detect_router
from app.routes.admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Unified Detection Proxy",
    version="3.0.0",
    description="Multi-provider, Fault-tolerant, Point-safe detection gateway."
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(detect_router)
app.include_router(admin_router)

# ─── Dashboard & Static Files ────────────────────────────────────────────────

# Ensure static directory exists
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("Database initialized.")

    # 2. Recovery Manager
    async def resume_tasks():
        await asyncio.sleep(1) # Wait for server to be fully ready
        async with get_db_connection() as db:
            cursor = await db.execute(
                "SELECT id, url, provider, status FROM detection_tasks WHERE status NOT IN ('completed', 'failed')"
            )
            rows = await cursor.fetchall()
            for row in rows:
                logger.info(f"Recovery: Resuming task {row[0]} on {row[2]}")
                asyncio.create_task(run_detection_bg(row[0], row[1], provider=row[2]))
        if rows: logger.info(f"Recovery complete. Resumed {len(rows)} tasks.")

    asyncio.create_task(resume_tasks())

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled: {exc}")
    return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
