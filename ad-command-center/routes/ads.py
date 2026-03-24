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
def get_ads(days: int = 7, db: Session = Depends(get_db)):
    from datetime import timedelta
    since = datetime.utcnow().date() - timedelta(days=days)
    ads = db.query(Ad).filter(Ad.id != "account").all()
    result = []
    for ad in ads:
        # Aggregate snapshots over the selected period
        totals = db.query(
            func.sum(Snapshot.spend),
            func.sum(Snapshot.impressions),
            func.sum(Snapshot.clicks),
            func.sum(Snapshot.add_to_carts),
            func.sum(Snapshot.purchases),
            func.sum(Snapshot.revenue),
        ).filter(
            Snapshot.ad_id == ad.id,
            cast(Snapshot.timestamp, Date) >= since
        ).first()
        spend = totals[0] or 0
        clicks = totals[2] or 0
        impressions = totals[1] or 0
        revenue = totals[5] or 0
        result.append({
            "id": ad.id,
            "name": ad.name,
            "status": ad.status,
            "ad_copy": ad.ad_copy,
            "parent_ad_id": ad.parent_ad_id,
            "creative_url": ad.creative_url,
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
            "add_to_carts": totals[3] or 0,
            "purchases": totals[4] or 0,
            "revenue": round(revenue, 2),
            "roas": round(revenue / spend, 2) if spend > 0 else 0,
        })
    result.sort(key=lambda a: a["spend"], reverse=True)
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
