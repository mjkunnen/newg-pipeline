from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Snapshot, Ad
from routes.auth import verify_auth
from datetime import datetime, timedelta

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/kpis")
def get_kpis(days: int = 1, db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    since = today - timedelta(days=days - 1)  # days=1 means today only
    prev_start = since - timedelta(days=days)
    prev_end = since - timedelta(days=1)

    def period_totals(start_date, end_date):
        rows = db.query(
            func.sum(Snapshot.spend),
            func.sum(Snapshot.clicks),
            func.sum(Snapshot.impressions),
            func.sum(Snapshot.add_to_carts),
            func.sum(Snapshot.purchases),
            func.sum(Snapshot.revenue),
        ).filter(
            cast(Snapshot.timestamp, Date) >= start_date,
            cast(Snapshot.timestamp, Date) <= end_date,
        ).first()
        spend = rows[0] or 0
        clicks = rows[1] or 0
        return {
            "spend": round(spend, 2),
            "clicks": clicks,
            "impressions": rows[2] or 0,
            "add_to_carts": rows[3] or 0,
            "purchases": rows[4] or 0,
            "revenue": round(rows[5] or 0, 2),
            "roas": round((rows[5] or 0) / spend, 2) if spend > 0 else 0,
            "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
        }

    t = period_totals(since, today)
    p = period_totals(prev_start, prev_end)
    return {
        "spend": t["spend"],
        "roas": t["roas"],
        "cpc": t["cpc"],
        "atc": t["add_to_carts"],
        "purchases": t["purchases"],
        "revenue": t["revenue"],
        "clicks": t["clicks"],
        "impressions": t["impressions"],
        "spend_change": round(t["spend"] - p["spend"], 2),
        "roas_change": round(t["roas"] - p["roas"], 2),
        "cpc_change": round(t["cpc"] - p["cpc"], 2),
        "atc_change": t["add_to_carts"] - p["add_to_carts"],
        "purchases_change": t["purchases"] - p["purchases"],
    }

@router.get("/api/kpis/history")
def get_kpis_history(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.utcnow().date() - timedelta(days=days)
    rows = db.query(
        cast(Snapshot.timestamp, Date).label("date"),
        func.sum(Snapshot.spend).label("spend"),
        func.sum(Snapshot.revenue).label("revenue"),
        func.sum(Snapshot.clicks).label("clicks"),
        func.sum(Snapshot.impressions).label("impressions"),
    ).filter(
        cast(Snapshot.timestamp, Date) >= since
    ).group_by(
        cast(Snapshot.timestamp, Date)
    ).order_by("date").all()

    # Frontend expects {dates:[], spend:[], revenue:[]}
    return {
        "dates": [str(r.date) for r in rows],
        "spend": [round(r.spend or 0, 2) for r in rows],
        "revenue": [round(r.revenue or 0, 2) for r in rows],
        "clicks": [r.clicks or 0 for r in rows],
        "impressions": [r.impressions or 0 for r in rows],
    }
