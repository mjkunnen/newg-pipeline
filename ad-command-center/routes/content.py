import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pydantic import BaseModel
from db import get_db
from models import ContentItem
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

VALID_SOURCES = {"ppspy", "tiktok", "pinterest", "meta"}

VALID_TRANSITIONS = {
    "discovered": ["surfaced"],
    "surfaced": ["queued", "discovered"],
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
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    List content items, optionally filtered by status and/or source.
    Ordered by discovered_at descending. Max 200 items per call.
    """
    q = db.query(ContentItem)
    if status:
        q = q.filter_by(status=status)
    if source:
        q = q.filter_by(source=source)
    return q.order_by(ContentItem.discovered_at.desc()).limit(min(limit, 200)).all()


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
    db.commit()
    db.refresh(item)
    return {"id": item.id, "content_id": item.content_id, "source": item.source, "status": item.status}
