import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Ad, Snapshot, IterationJob, Campaign
from routes.auth import verify_auth
import meta_client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_auth)])

DAYS_TO_PRESET = {
    1: "today",
    7: "last_7d",
    14: "last_14d",
    30: "last_30d",
}

def _parse_actions(actions: list[dict] | None, action_type: str) -> int:
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == action_type:
            return int(a.get("value", 0))
    return 0

def _parse_action_values(action_values: list[dict] | None, action_type: str) -> float:
    if not action_values:
        return 0.0
    for a in action_values:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0

@router.get("/api/ads")
async def get_ads(days: int = 7, db: Session = Depends(get_db)):
    # Map days to Meta API date_preset
    date_preset = DAYS_TO_PRESET.get(days, f"last_{days}d")

    # Fetch ads with insights for the requested period directly from Meta
    try:
        all_ads = await meta_client.fetch_all_ads(date_preset=date_preset)
    except Exception as e:
        logger.error(f"Meta API fetch failed for ads (preset={date_preset}): {e}")
        all_ads = []

    result = []
    for ad in all_ads:
        ad_id = ad["id"]
        insights_data = ad.get("insights", {}).get("data", [])
        insights = insights_data[0] if insights_data else None

        spend = float(insights.get("spend", 0)) if insights else 0
        impressions = int(insights.get("impressions", 0)) if insights else 0
        clicks = int(insights.get("clicks", 0)) if insights else 0
        revenue = _parse_action_values(insights.get("action_values"), "purchase") if insights else 0
        purchases = _parse_actions(insights.get("actions"), "purchase") if insights else 0
        add_to_carts = _parse_actions(insights.get("actions"), "add_to_cart") if insights else 0

        # Get creative URL from local DB (cached during sync)
        local_ad = db.query(Ad).filter_by(id=ad_id).first()
        creative_url = local_ad.creative_url if local_ad else None

        result.append({
            "id": ad_id,
            "name": ad["name"],
            "status": ad["status"],
            "ad_copy": local_ad.ad_copy if local_ad else None,
            "parent_ad_id": local_ad.parent_ad_id if local_ad else None,
            "creative_url": creative_url,
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0,
            "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
            "add_to_carts": add_to_carts,
            "purchases": purchases,
            "revenue": round(revenue, 2),
            "roas": round(revenue / spend, 2) if spend > 0 else 0,
        })

    result.sort(key=lambda a: a["spend"], reverse=True)

    # Sum daily budgets from active campaigns (stored in cents)
    total_budget_cents = db.query(func.sum(Campaign.daily_budget)).filter(
        Campaign.status == "ACTIVE"
    ).scalar() or 0

    return {"ads": result, "budget": round(total_budget_cents / 100, 2)}

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
