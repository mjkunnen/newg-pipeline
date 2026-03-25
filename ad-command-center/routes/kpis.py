import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from db import get_db
from models import Snapshot
from routes.auth import verify_auth
from datetime import datetime, timedelta
import meta_client

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_auth)])

DAYS_TO_PRESET = {
    1: "today",
    7: "last_7d",
    14: "last_14d",
    30: "last_30d",
}

DAYS_TO_PREV_PRESET = {
    1: "yesterday",
    7: "last_14d",   # will subtract current from this
    14: "last_28d",
    30: "last_60d",
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

def _extract_kpis(data: dict | None) -> dict:
    if not data:
        return {"spend": 0, "clicks": 0, "impressions": 0, "add_to_carts": 0, "purchases": 0, "revenue": 0, "roas": 0, "cpc": 0}
    spend = float(data.get("spend", 0))
    clicks = int(data.get("clicks", 0))
    impressions = int(data.get("impressions", 0))
    purchases = _parse_actions(data.get("actions"), "purchase")
    revenue = _parse_action_values(data.get("action_values"), "purchase")
    add_to_carts = _parse_actions(data.get("actions"), "add_to_cart")
    return {
        "spend": round(spend, 2),
        "clicks": clicks,
        "impressions": impressions,
        "add_to_carts": add_to_carts,
        "purchases": purchases,
        "revenue": round(revenue, 2),
        "roas": round(revenue / spend, 2) if spend > 0 else 0,
        "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
    }

@router.get("/api/kpis")
async def get_kpis(days: int = 1, db: Session = Depends(get_db)):
    date_preset = DAYS_TO_PRESET.get(days, f"last_{days}d")

    # Fetch current period from Meta API directly
    try:
        current_data = await meta_client.fetch_account_insights(date_preset)
        t = _extract_kpis(current_data)
    except Exception as e:
        logger.warning(f"Meta KPI fetch failed ({date_preset}): {e}, falling back to DB")
        t = _kpis_from_db(days, db)

    # Previous period from DB (cheaper, historical data already backfilled)
    today = datetime.utcnow().date()
    since = today - timedelta(days=days - 1)
    prev_start = since - timedelta(days=days)
    prev_end = since - timedelta(days=1)
    p = _kpis_from_db_range(prev_start, prev_end, db)

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

def _kpis_from_db(days: int, db: Session) -> dict:
    today = datetime.utcnow().date()
    since = today - timedelta(days=days - 1)
    return _kpis_from_db_range(since, today, db)

def _kpis_from_db_range(start_date, end_date, db: Session) -> dict:
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
    revenue = rows[5] or 0
    return {
        "spend": round(spend, 2),
        "clicks": clicks,
        "impressions": rows[2] or 0,
        "add_to_carts": rows[3] or 0,
        "purchases": rows[4] or 0,
        "revenue": round(revenue, 2),
        "roas": round(revenue / spend, 2) if spend > 0 else 0,
        "cpc": round(spend / clicks, 2) if clicks > 0 else 0,
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

    return {
        "dates": [str(r.date) for r in rows],
        "spend": [round(r.spend or 0, 2) for r in rows],
        "revenue": [round(r.revenue or 0, 2) for r in rows],
        "clicks": [r.clicks or 0 for r in rows],
        "impressions": [r.impressions or 0 for r in rows],
    }
