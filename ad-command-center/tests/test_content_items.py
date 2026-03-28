import json
import pytest
from models import ContentItem
from sqlalchemy.exc import IntegrityError
from routes.content import StatusUpdate

def _make_item(content_id: str, source: str = "ppspy", status: str = "discovered", **kwargs) -> ContentItem:
    return ContentItem(
        content_id=content_id,
        source=source,
        status=status,
        **kwargs,
    )

def test_idempotent_insert(db):
    """Inserting the same (content_id, source) twice produces exactly one row."""
    item1 = _make_item("ad-001", "ppspy")
    db.add(item1)
    db.commit()

    # Attempt second insert — should fail on UNIQUE constraint
    item2 = _make_item("ad-001", "ppspy")
    db.add(item2)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    count = db.query(ContentItem).filter_by(content_id="ad-001", source="ppspy").count()
    assert count == 1, f"Expected 1 row, got {count}"

def test_unique_constraint_same_source(db):
    """UniqueConstraint(content_id, source) blocks identical pairs."""
    db.add(_make_item("ad-002", "tiktok"))
    db.commit()

    db.add(_make_item("ad-002", "tiktok"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

def test_same_content_id_different_source_allowed(db):
    """Same content_id with different source is allowed — two distinct rows."""
    db.add(_make_item("ad-003", "ppspy"))
    db.commit()
    db.add(_make_item("ad-003", "tiktok"))
    db.commit()

    count = db.query(ContentItem).filter_by(content_id="ad-003").count()
    assert count == 2, f"Expected 2 rows (different sources), got {count}"

def test_default_status_is_discovered(db):
    """ContentItem defaults to 'discovered' status."""
    item = _make_item("ad-004")
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.status == "discovered"

def test_id_is_auto_generated(db):
    """ContentItem.id is auto-generated UUID if not provided."""
    item = _make_item("ad-005")
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.id is not None
    assert len(item.id) == 36  # UUID4 format


# --- drive_link tests ---

def _apply_drive_link_patch(item: ContentItem, body: StatusUpdate) -> None:
    """Simulate the update_status route logic for drive_link merging."""
    item.status = body.status
    if body.drive_link:
        existing = json.loads(item.metadata_json or '{}')
        existing['drive_link'] = body.drive_link
        item.metadata_json = json.dumps(existing)


def test_drive_link_stored_in_metadata_json(db):
    """PATCH with drive_link stores it inside metadata_json."""
    item = _make_item("ad-010", status="queued")
    db.add(item)
    db.commit()

    body = StatusUpdate(status="ready_to_launch", drive_link="https://drive.google.com/file/d/abc")
    _apply_drive_link_patch(item, body)
    db.commit()
    db.refresh(item)

    assert item.status == "ready_to_launch"
    meta = json.loads(item.metadata_json)
    assert meta["drive_link"] == "https://drive.google.com/file/d/abc"


def test_patch_without_drive_link_still_works(db):
    """PATCH without drive_link does not touch metadata_json."""
    item = _make_item("ad-011", status="discovered")
    db.add(item)
    db.commit()

    body = StatusUpdate(status="surfaced")
    _apply_drive_link_patch(item, body)
    db.commit()
    db.refresh(item)

    assert item.status == "surfaced"
    assert item.metadata_json is None


def test_drive_link_merges_with_existing_metadata(db):
    """PATCH with drive_link merges into existing metadata_json without losing other fields."""
    existing_meta = json.dumps({"views": 1000, "engagement": 0.05})
    item = _make_item("ad-012", status="queued", metadata_json=existing_meta)
    db.add(item)
    db.commit()

    body = StatusUpdate(status="ready_to_launch", drive_link="https://drive.google.com/file/d/xyz")
    _apply_drive_link_patch(item, body)
    db.commit()
    db.refresh(item)

    meta = json.loads(item.metadata_json)
    assert meta["drive_link"] == "https://drive.google.com/file/d/xyz"
    assert meta["views"] == 1000
    assert meta["engagement"] == 0.05


def test_drive_link_on_null_metadata_creates_json(db):
    """PATCH with drive_link on null metadata_json creates a new JSON object with drive_link key."""
    item = _make_item("ad-013", status="queued", metadata_json=None)
    db.add(item)
    db.commit()

    body = StatusUpdate(status="ready_to_launch", drive_link="https://drive.google.com/file/d/new")
    _apply_drive_link_patch(item, body)
    db.commit()
    db.refresh(item)

    assert item.metadata_json is not None
    meta = json.loads(item.metadata_json)
    assert "drive_link" in meta
    assert meta["drive_link"] == "https://drive.google.com/file/d/new"
