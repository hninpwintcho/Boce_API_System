import asyncio
import logging
import argparse
from app.main import app
from app.tasks import start_priority_scheduler
import uvicorn
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_api():
    logger.info("🚀 Starting API Service...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=False)

def run_scheduler():
    logger.info("🚀 Starting Scheduler Service...")
    asyncio.run(start_priority_scheduler())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Boce Unified Proxy CLI")
    parser.add_argument("command", choices=["api", "scheduler"], help="Command to run")
    args = parser.parse_args()

    if args.command == "api":
        run_api()
    elif args.command == "scheduler":
        run_scheduler()
