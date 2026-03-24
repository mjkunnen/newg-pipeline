import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import init_db
from config import SYNC_INTERVAL_MINUTES
from sync import run_sync
from analysis import run_analysis
from routes import auth, kpis, ads, notifications, analysis as analysis_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def safe_sync():
    try:
        await run_sync()
    except Exception as e:
        logger.error(f"Sync failed (will retry next interval): {e}")

def safe_analysis():
    try:
        run_analysis()
    except Exception as e:
        logger.error(f"Analysis failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(safe_sync, "interval", minutes=SYNC_INTERVAL_MINUTES, id="meta_sync")
    scheduler.add_job(safe_analysis, "cron", hour=0, minute=0, id="daily_analysis")
    scheduler.start()
    logger.info(f"Scheduler started: sync every {SYNC_INTERVAL_MINUTES}min, analysis daily at midnight")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# Health check - MUST be before static mount
@app.get("/health")
async def health():
    return {"status": "ok"}

# Routes
app.include_router(auth.router)
app.include_router(kpis.router)
app.include_router(ads.router)
app.include_router(notifications.router)
app.include_router(analysis_routes.router)

# Manual sync trigger
@app.post("/api/sync")
async def trigger_sync():
    await run_sync()
    return {"status": "done"}

# Serve frontend - MUST be last (catches all unmatched routes)
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
