import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Override all required env vars before any app imports
# These are test-only dummy values — no real credentials
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("META_ACCESS_TOKEN", "test-token")
os.environ.setdefault("META_AD_ACCOUNT_ID", "test-account-id")
os.environ.setdefault("META_PAGE_ID", "test-page-id")
os.environ.setdefault("META_PIXEL_ID", "test-pixel-id")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("DASHBOARD_SECRET", "test-secret")
os.environ.setdefault("FAL_KEY", "test-fal-key")

# Must import after env vars are set
from db import Base
import models  # registers all models on Base.metadata including ContentItem

@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # SQLite does not enforce UNIQUE constraints in on_conflict_do_nothing the same
    # way Postgres does — use session-level upsert helper in tests instead of dialect insert
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
