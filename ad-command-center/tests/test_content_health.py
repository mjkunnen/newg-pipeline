"""Tests for GET /api/content/health endpoint.

Tests call the content_health route function directly using the db fixture,
bypassing HTTP and auth middleware.
"""
import pytest
from datetime import datetime, timezone
from models import ContentItem
from routes.content import content_health


def _make_item(content_id: str, source: str, discovered_at: datetime) -> ContentItem:
    return ContentItem(
        content_id=content_id,
        source=source,
        status="discovered",
        discovered_at=discovered_at,
    )


TODAY = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_health_returns_all_sources(db):
    """GET /api/content/health returns JSON with keys ppspy, tiktok, pinterest, meta."""
    result = content_health(db=db)
    assert set(result.keys()) == {"ppspy", "tiktok", "pinterest", "meta"}


def test_health_source_structure(db):
    """Each source entry has last_seen, today_count, and ok keys."""
    result = content_health(db=db)
    for source, data in result.items():
        assert "last_seen" in data, f"Missing last_seen for {source}"
        assert "today_count" in data, f"Missing today_count for {source}"
        assert "ok" in data, f"Missing ok for {source}"


def test_health_empty_source_returns_null_and_false(db):
    """Source with no content items returns last_seen=null, today_count=0, ok=false."""
    result = content_health(db=db)
    for source in ["ppspy", "tiktok", "pinterest", "meta"]:
        assert result[source]["last_seen"] is None, f"{source}: expected null last_seen"
        assert result[source]["today_count"] == 0, f"{source}: expected today_count=0"
        assert result[source]["ok"] is False, f"{source}: expected ok=false"


def test_health_source_with_today_content_is_ok(db):
    """Source with item discovered today returns ok=true and today_count >= 1."""
    item = _make_item("ad-h-001", "tiktok", TODAY)
    db.add(item)
    db.commit()

    result = content_health(db=db)

    assert result["tiktok"]["ok"] is True
    assert result["tiktok"]["today_count"] >= 1
    assert result["tiktok"]["last_seen"] is not None
    # Other sources unaffected
    assert result["ppspy"]["ok"] is False
    assert result["ppspy"]["today_count"] == 0


def test_health_source_with_old_content_only_is_not_ok(db):
    """Source with item discovered before today returns ok=false."""
    item = _make_item("ad-h-002", "pinterest", OLD)
    db.add(item)
    db.commit()

    result = content_health(db=db)

    assert result["pinterest"]["ok"] is False
    assert result["pinterest"]["today_count"] == 0
    assert result["pinterest"]["last_seen"] is not None  # has a timestamp but not today


def test_health_mixed_sources(db):
    """Mixed: one source with today content (ok=true), one with old (ok=false)."""
    db.add(_make_item("ad-h-003", "ppspy", TODAY))
    db.add(_make_item("ad-h-004", "meta", OLD))
    db.commit()

    result = content_health(db=db)

    assert result["ppspy"]["ok"] is True
    assert result["ppspy"]["today_count"] >= 1
    assert result["meta"]["ok"] is False
    assert result["meta"]["today_count"] == 0
