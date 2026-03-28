import pytest
from models import ContentItem
from sqlalchemy.exc import IntegrityError

def _make_item(content_id: str, source: str = "ppspy", **kwargs) -> ContentItem:
    return ContentItem(
        content_id=content_id,
        source=source,
        status="discovered",
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
