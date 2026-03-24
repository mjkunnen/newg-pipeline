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
    try:
        await run_sync()
        return {"status": "done"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

# Debug endpoint to check config
@app.get("/api/debug")
async def debug_info():
    from config import META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, DATABASE_URL
    from db import SessionLocal
    db = SessionLocal()
    try:
        from models import Campaign, Ad, Snapshot
        campaigns = db.query(Campaign).count()
        ads = db.query(Ad).count()
        snapshots = db.query(Snapshot).count()
    except Exception as e:
        campaigns = ads = snapshots = f"error: {e}"
    finally:
        db.close()
    return {
        "meta_token_set": bool(META_ACCESS_TOKEN) and len(META_ACCESS_TOKEN) > 10,
        "meta_token_prefix": META_ACCESS_TOKEN[:10] + "..." if META_ACCESS_TOKEN else "NOT SET",
        "ad_account_id": META_AD_ACCOUNT_ID or "NOT SET",
        "database_url_set": bool(DATABASE_URL),
        "db_counts": {"campaigns": campaigns, "ads": ads, "snapshots": snapshots},
    }

# Serve frontend - MUST be last (catches all unmatched routes)
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
