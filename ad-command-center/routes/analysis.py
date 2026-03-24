from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from db import get_db
from models import AiAnalysis
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/analysis")
def get_analysis(db: Session = Depends(get_db)):
    latest = db.query(AiAnalysis).order_by(AiAnalysis.timestamp.desc()).first()
    if not latest:
        return {"analysis": None, "recommendations": None, "timestamp": None}
    return {
        "analysis": latest.analysis_json,
        "recommendations": latest.recommendations,
        "timestamp": str(latest.timestamp),
    }

@router.post("/api/analysis/refresh")
async def refresh_analysis(background_tasks: BackgroundTasks):
    from analysis import run_analysis
    background_tasks.add_task(run_analysis)
    return {"status": "started"}
