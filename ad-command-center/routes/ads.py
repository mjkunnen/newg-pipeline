import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Ad, Snapshot, IterationJob
from routes.auth import verify_auth
import meta_client
from datetime import datetime
import base64

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/ads")
def get_ads(db: Session = Depends(get_db)):
    ads = db.query(Ad).all()
    result = []
    for ad in ads:
        latest = db.query(Snapshot).filter_by(ad_id=ad.id).order_by(Snapshot.timestamp.desc()).first()
        thumb_b64 = None
        if ad.creative_cached:
            thumb_b64 = base64.b64encode(ad.creative_cached).decode()
        result.append({
            "id": ad.id,
            "name": ad.name,
            "status": ad.status,
            "ad_copy": ad.ad_copy,
            "parent_ad_id": ad.parent_ad_id,
            "thumbnail": thumb_b64,
            "creative_url": ad.creative_url,
            "spend": latest.spend if latest else 0,
            "impressions": latest.impressions if latest else 0,
            "clicks": latest.clicks if latest else 0,
            "ctr": latest.ctr if latest else 0,
            "cpc": latest.cpc if latest else 0,
            "add_to_carts": latest.add_to_carts if latest else 0,
            "purchases": latest.purchases if latest else 0,
            "revenue": latest.revenue if latest else 0,
            "roas": latest.roas if latest else 0,
        })
    result.sort(key=lambda a: a["metrics"]["spend"], reverse=True)
    return result

@router.get("/api/ads/{ad_id}")
def get_ad_detail(ad_id: str, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if not ad:
        raise HTTPException(404, "Ad not found")
    snapshots = db.query(Snapshot).filter_by(ad_id=ad_id).order_by(Snapshot.timestamp).all()
    return {
        "id": ad.id,
        "name": ad.name,
        "status": ad.status,
        "history": [
            {"timestamp": str(s.timestamp), "spend": s.spend, "roas": s.roas, "cpc": s.cpc, "clicks": s.clicks}
            for s in snapshots
        ]
    }

@router.post("/api/ads/{ad_id}/pause")
async def pause_ad(ad_id: str, db: Session = Depends(get_db)):
    await meta_client.pause_ad(ad_id)
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if ad:
        ad.status = "PAUSED"
        db.commit()
    return {"success": True}

@router.post("/api/ads/{ad_id}/activate")
async def activate_ad(ad_id: str, db: Session = Depends(get_db)):
    await meta_client.activate_ad(ad_id)
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if ad:
        ad.status = "ACTIVE"
        db.commit()
    return {"success": True}

@router.post("/api/ads/{ad_id}/iterate")
async def iterate_ad(ad_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    ad = db.query(Ad).filter_by(id=ad_id).first()
    if not ad:
        raise HTTPException(404, "Ad not found")
    job = IterationJob(ad_id=ad_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    from iteration import run_iteration
    background_tasks.add_task(run_iteration, job.id)
    return {"job_id": job.id, "status": "pending"}
