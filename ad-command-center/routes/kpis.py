from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Snapshot, Ad
from routes.auth import verify_auth
from datetime import datetime, timedelta

router = APIRouter(dependencies=[Depends(verify_auth)])

@router.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    def day_totals(date):
        rows = db.query(
            func.sum(Snapshot.spend),
            func.sum(Snapshot.clicks),
            func.sum(Snapshot.impressions),
            func.sum(Snapshot.add_to_carts),
            func.sum(Snapshot.purchases),
            func.sum(Snapshot.revenue),
        ).filter(
            cast(Snapshot.timestamp, Date) == date
        ).first()
        spend = rows[0] or 0
        return {
            "spend": round(spend, 2),
            "clicks": rows[1] or 0,
            "impressions": rows[2] or 0,
            "add_to_carts": rows[3] or 0,
            "purchases": rows[4] or 0,
            "revenue": round(rows[5] or 0, 2),
            "roas": round((rows[5] or 0) / spend, 2) if spend > 0 else 0,
            "cpc": round(spend / (rows[1] or 1), 2),
        }

    t = day_totals(today)
    y = day_totals(yesterday)
    # Flat format the frontend expects
    return {
        "spend": t["spend"],
        "roas": t["roas"],
        "cpc": t["cpc"],
        "atc": t["add_to_carts"],
        "purchases": t["purchases"],
        "revenue": t["revenue"],
        "clicks": t["clicks"],
        "impressions": t["impressions"],
        "spend_change": round(t["spend"] - y["spend"], 2),
        "roas_change": round(t["roas"] - y["roas"], 2),
        "cpc_change": round(t["cpc"] - y["cpc"], 2),
        "atc_change": t["add_to_carts"] - y["add_to_carts"],
        "purchases_change": t["purchases"] - y["purchases"],
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
