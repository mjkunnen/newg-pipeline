import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pydantic import BaseModel
from db import get_db
from models import ContentItem
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

VALID_SOURCES = {"ppspy", "tiktok", "pinterest", "meta"}

VALID_TRANSITIONS = {
    "discovered": ["surfaced", "queued", "ready_to_launch"],
    "surfaced": ["queued", "ready_to_launch", "discovered"],
    "queued": ["ready_to_launch", "surfaced"],
    "ready_to_launch": ["launched", "queued"],
    "launched": [],  # terminal state
}


class ContentItemCreate(BaseModel):
    content_id: str
    source: str  # ppspy | tiktok | pinterest | meta
    creative_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ad_copy: Optional[str] = None
    metadata_json: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str
    drive_link: Optional[str] = None


@router.post("/api/content", status_code=201)
def create_content_item(body: ContentItemCreate, db: Session = Depends(get_db)):
    """
    Idempotent insert: if (content_id, source) already exists, returns the existing row.
    Returns 400 if source is not a known value.
    """
    if body.source not in VALID_SOURCES:
        raise HTTPException(400, f"Invalid source '{body.source}'. Must be one of: {sorted(VALID_SOURCES)}")

    item_data = body.model_dump()
    item_data["id"] = str(uuid.uuid4())
    item_data["status"] = "discovered"

    stmt = pg_insert(ContentItem).values(**item_data).on_conflict_do_nothing(
        constraint="uq_content_id_source"
    )
    db.execute(stmt)
    db.commit()

    # Return existing or newly created row
    item = db.query(ContentItem).filter_by(
        content_id=body.content_id,
        source=body.source,
    ).first()
    return item


@router.get("/api/content")
def list_content_items(
    status: Optional[str] = None,
    source: Optional[str] = None,
    today: bool = False,
    per_source: Optional[int] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    List content items, optionally filtered by status and/or source.
    If today=true, only return items from last 24h (default per_source=2).
    per_source limits results per source (e.g. per_source=2 = max 2 ppspy + 2 tiktok + ...).
    """
    from datetime import timedelta

    q = db.query(ContentItem)
    if status:
        q = q.filter_by(status=status)
    if source:
        q = q.filter_by(source=source)
    if today:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        q = q.filter(ContentItem.discovered_at >= cutoff)
        if per_source is None:
            per_source = 2  # default: max 2 per source for today view

    all_items = q.order_by(ContentItem.discovered_at.desc()).limit(min(limit, 1000)).all()

    if per_source is not None and not source:
        # Group by source, take top N per source
        from collections import defaultdict
        grouped = defaultdict(list)
        for item in all_items:
            grouped[item.source].append(item)
        result = []
        for src_items in grouped.values():
            result.extend(src_items[:per_source])
        result.sort(key=lambda x: x.discovered_at, reverse=True)
        return result

    return all_items


@router.get("/api/content/health")
def content_health(db: Session = Depends(get_db)):
    """Return per-source health data: last_seen timestamp, today_count, and ok flag."""
    sources = ["ppspy", "tiktok", "pinterest", "meta"]
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = {}
    for source in sources:
        last = (
            db.query(ContentItem)
            .filter_by(source=source)
            .order_by(ContentItem.discovered_at.desc())
            .first()
        )
        today_count = (
            db.query(func.count(ContentItem.id))
            .filter(
                ContentItem.source == source,
                ContentItem.discovered_at >= today_start,
            )
            .scalar()
        )
        last_seen_dt = last.discovered_at if last and last.discovered_at else None
        # Make naive datetimes timezone-aware for comparison
        if last_seen_dt is not None and last_seen_dt.tzinfo is None:
            last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
        ok = last_seen_dt is not None and last_seen_dt >= today_start
        result[source] = {
            "last_seen": last_seen_dt.isoformat() if last_seen_dt else None,
            "today_count": today_count,
            "ok": ok,
        }
    return result


@router.patch("/api/content/{item_id}/status")
def update_status(item_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    """
    Advance a content item through the status lifecycle.
    Invalid transitions return 400. Terminal state (launched) cannot be changed.
    """
    item = db.query(ContentItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")

    allowed = VALID_TRANSITIONS.get(item.status, [])
    if body.status not in allowed:
        if not allowed:
            raise HTTPException(400, f"'{item.status}' is a terminal state — no transitions allowed")
        raise HTTPException(
            400,
            f"Invalid transition: {item.status} → {body.status}. Allowed: {allowed}",
        )

    item.status = body.status
    if body.drive_link:
        existing = json.loads(item.metadata_json or '{}')
        existing['drive_link'] = body.drive_link
        item.metadata_json = json.dumps(existing)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "content_id": item.content_id, "source": item.source, "status": item.status}
