# Phase 1: State Layer - Research

**Researched:** 2026-03-27
**Domain:** Railway Postgres deployment, SQLAlchemy migrations, FastAPI content API, TypeScript-to-Postgres bridge, Google Sheets fallback
**Confidence:** HIGH

---

## Project Constraints (from CLAUDE.md)

- ALL secrets via `.env` + `os.getenv()` / `process.env` — NEVER hardcoded
- NEVER commit `.env` — only `.env.example`
- NEVER use real values as fallback defaults in `os.getenv("KEY", "real-value")` — use `None` or raise
- GitHub Actions secrets via `${{ secrets.* }}` only
- Shopify via Zapier MCP only (not relevant to this phase)
- Dashboard on Railway, automation on GitHub Actions
- Keep TypeScript (`decarba-remixer/`) as-is — isolated — do not rewrite
- Keep Python scrapers (`scout/`, `pipeline/`) — extend, not replace
- Keep Railway hosting (`ad-command-center/`) — keep Railway
- Google Sheets stays as human-facing fallback during v1 transition

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATE-01 | Deploy ad-command-center to Railway with Postgres | Service is already deployed (`newg-pipeline-production.up.railway.app`) and DATABASE_URL is configured — task is to verify the deploy is healthy and add content_items infrastructure, not start from scratch |
| STATE-02 | Content items table with dedup (unique content ID across all sources) | SQLAlchemy model + UNIQUE constraint on `content_id` column; `INSERT ... ON CONFLICT DO NOTHING` pattern for idempotent inserts |
| STATE-03 | Status lifecycle per content item (discovered → surfaced → queued → ready_to_launch → launched) | Postgres CHECK constraint on status column + FastAPI PATCH endpoint for transitions; observable via direct DB query or API |
| STATE-04 | Migration path: Google Sheets remains readable during transition | decarba-remixer/src/launcher/fromSheet.ts already reads Sheets via gviz CSV — that path stays untouched; new writes go to Postgres via HTTP API |
</phase_requirements>

---

## Summary

**Critical discovery: ad-command-center is already deployed.** The Railway service `newg-pipeline` at `newg-pipeline-production.up.railway.app` is live, returns `{"status":"ok"}` from `/health`, and the debug endpoint confirms `DATABASE_URL` is set and the DB has 7 campaigns, 134 ads, 422 snapshots. This fundamentally changes Phase 1 scope — there is no "deploy from scratch" task. The actual work is: (1) add the `content_items` table to the existing live deployment without breaking the existing Campaign/Ad/Snapshot tables, (2) expose CRUD endpoints for the discovery pipeline, and (3) make `decarba-remixer` write discovered items to Postgres instead of (or in addition to) Google Sheets.

The existing `models.py` has Campaign/Ad/Snapshot/AiAnalysis/Notification/IterationJob — none of which are the `content_items` table needed for Phase 1. The `db.py` pattern uses `Base.metadata.create_all()` on startup, which is additive (will create new tables without dropping old ones). However, for production safety, Alembic migration management is the correct approach — it prevents schema drift and allows rollback.

The TypeScript pipeline (`decarba-remixer`) has no Postgres client. It writes to Google Sheets via Apps Script webhook and reads via gviz CSV. The bridge for STATE-02/STATE-03 is for `decarba-remixer` to POST to the `ad-command-center` HTTP API — not to connect to Postgres directly. This keeps the TypeScript service decoupled and avoids adding a second Postgres client language.

**Primary recommendation:** Add `content_items` SQLAlchemy model + Alembic migration + CRUD FastAPI routes to the existing live `ad-command-center`, then add a `POST /api/content` call in `decarba-remixer/src/index.ts` after each successful scrape. Google Sheets fallback (STATE-04) requires no changes — `fromSheet.ts` already works.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.35 (already in requirements.txt) | ORM for content_items model | Already in use; 2.x declarative style is current pattern |
| psycopg[binary] | >=3.2.10 (already in requirements.txt) | Postgres adapter | Already in use; psycopg3 is current; Railway DATABASE_URL confirmed working |
| FastAPI | 0.115.0 (already in requirements.txt) | HTTP API for content CRUD | Already in use; all existing routes follow this pattern |
| Alembic | 1.14.x | Schema migrations | NOT currently in requirements.txt — must be added; prevents `create_all()` schema drift on live DB |
| python-dotenv | 1.0.1 (already in requirements.txt) | Env var loading | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fetch (built-in) | Node 24 built-in | HTTP POST from TypeScript to ad-command-center API | decarba-remixer calling content API; no new npm dep needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Alembic migrations | `Base.metadata.create_all()` on startup | create_all is already in use for existing tables; fine for greenfield, risky for live DB with existing data; Alembic is the correct path once you have a production DB |
| HTTP API bridge (TS → Python) | Add `pg` or `postgres` npm package to decarba-remixer | Direct DB connection from TS avoids the HTTP hop but couples TS to DB credentials; HTTP API is cleaner, already has auth, and keeps the architecture consistent |
| Alembic | Tortoise ORM / Beanie | Not in the stack; SQLAlchemy is already established |

**Installation (add to ad-command-center/requirements.txt):**
```bash
pip install alembic==1.14.0
```

**Version verification (confirmed 2026-03-27):**
- alembic: 1.14.0 (latest stable per PyPI)
- SQLAlchemy 2.0.35: already in use, confirmed working
- psycopg[binary] >=3.2.10: already in use, confirmed working

---

## Architecture Patterns

### Existing Structure (do not change)
```
ad-command-center/
├── main.py           # FastAPI app + lifespan (scheduler) — ADD content routes import here
├── db.py             # Engine, SessionLocal, Base, init_db() — NO CHANGES NEEDED
├── config.py         # Env var loading — NO CHANGES NEEDED
├── models.py         # Campaign/Ad/Snapshot etc — ADD ContentItem class here
├── requirements.txt  # ADD alembic==1.14.0
├── railway.toml      # builder = dockerfile — NO CHANGES NEEDED
├── Dockerfile        # python:3.12-slim, uvicorn — NO CHANGES NEEDED
└── routes/
    ├── ads.py        # Existing — NO CHANGES
    ├── auth.py       # Existing — NO CHANGES
    └── content.py    # NEW — ContentItem CRUD endpoints
```

### Pattern 1: SQLAlchemy ContentItem Model with UNIQUE constraint

**What:** Add a `ContentItem` class to `models.py` using the existing `Base`. Status stored as a Postgres-constrained string column.

**When to use:** All new discovery pipeline writes target this table.

**Example:**
```python
# models.py addition — Source: SQLAlchemy 2.0 declarative docs
from sqlalchemy import Column, String, Text, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func

class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(String, primary_key=True)  # internal UUID or surrogate key
    content_id = Column(String, nullable=False)  # external ID (PPSpy ad ID, TikTok video ID, etc.)
    source = Column(String, nullable=False)  # "ppspy" | "tiktok" | "pinterest" | "meta"
    status = Column(String, nullable=False, default="discovered")
    # discovered | surfaced | queued | ready_to_launch | launched
    creative_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    ad_copy = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # raw scrape data as JSON string
    discovered_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("content_id", "source", name="uq_content_id_source"),
        Index("ix_content_items_status", "status"),
        Index("ix_content_items_source", "source"),
    )
```

**Key design decisions:**
- `content_id` is the external ID (PPSpy ad ID, TikTok video ID, etc.) — unique per source
- `UniqueConstraint("content_id", "source")` allows the same video to appear on TikTok AND Meta without collision
- Use `INSERT ... ON CONFLICT DO NOTHING` for idempotent inserts (see routes pattern below)
- `id` (primary key) is a separate internal surrogate key — keeps API URLs stable if content_id changes format

### Pattern 2: Idempotent Insert (ON CONFLICT DO NOTHING)

**What:** Use SQLAlchemy's `insert().on_conflict_do_nothing()` to safely re-run scrapers.

**Example:**
```python
# routes/content.py — Source: SQLAlchemy 2.0 PostgreSQL dialect docs
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models import ContentItem

def upsert_content_item(db: Session, item_data: dict) -> ContentItem | None:
    stmt = pg_insert(ContentItem).values(**item_data)
    stmt = stmt.on_conflict_do_nothing(
        constraint="uq_content_id_source"
    )
    db.execute(stmt)
    db.commit()
    # Return existing or newly created row
    return db.query(ContentItem).filter_by(
        content_id=item_data["content_id"],
        source=item_data["source"]
    ).first()
```

### Pattern 3: Status Transition Endpoint

**What:** PATCH endpoint that validates the transition is valid before applying.

**Example:**
```python
# routes/content.py
VALID_TRANSITIONS = {
    "discovered": ["surfaced"],
    "surfaced": ["queued", "discovered"],  # allow un-surface
    "queued": ["ready_to_launch", "surfaced"],
    "ready_to_launch": ["launched", "queued"],
    "launched": [],  # terminal
}

@router.patch("/api/content/{item_id}/status")
def update_status(item_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
    allowed = VALID_TRANSITIONS.get(item.status, [])
    if body.status not in allowed:
        raise HTTPException(400, f"Cannot transition {item.status} → {body.status}")
    item.status = body.status
    db.commit()
    return {"id": item_id, "status": item.status}
```

### Pattern 4: Alembic Migration Setup

**What:** Initialize Alembic so schema changes are tracked and applied safely to the live Railway Postgres.

**Setup commands (run once, not at runtime):**
```bash
cd ad-command-center
pip install alembic==1.14.0
alembic init alembic
# Edit alembic/env.py to import Base from db.py and use DATABASE_URL from env
```

**alembic/env.py key change:**
```python
# Source: Alembic docs — async-safe pattern for psycopg3
import os
from db import Base
from models import ContentItem  # ensure model is imported before autogenerate

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
target_metadata = Base.metadata
```

**Generate and apply migration:**
```bash
alembic revision --autogenerate -m "add content_items table"
alembic upgrade head
```

**Railway deploy note:** The migration must run BEFORE the new code that references `content_items`. Add a startup command or run `alembic upgrade head` as a Railway deploy step (Railway supports `startCommand` override in railway.toml or as a pre-deploy hook in Procfile).

**Procfile pattern for Railway:**
```
web: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Pattern 5: TypeScript → Postgres via HTTP API

**What:** `decarba-remixer` POSTs discovered items to the `ad-command-center` HTTP API. No direct DB connection from TypeScript.

**Why:** TypeScript already uses `fetch()` for Apps Script and Google Sheets. Adding a direct `pg` connection would require DATABASE_URL secret in GitHub Actions and tighter coupling. The HTTP API approach is already authenticated via `DASHBOARD_SECRET`.

**Example (add to decarba-remixer/src/index.ts after scrape):**
```typescript
// Source: standard fetch API — Node 24 has built-in fetch
const CONTENT_API = process.env.CONTENT_API_URL; // e.g. https://newg-pipeline-production.up.railway.app
const CONTENT_API_SECRET = process.env.DASHBOARD_SECRET;

async function writeToContentAPI(ads: ScrapedAd[]): Promise<void> {
  if (!CONTENT_API || !CONTENT_API_SECRET) {
    console.log("[content-api] CONTENT_API_URL or DASHBOARD_SECRET not set — skipping Postgres write");
    return;
  }
  for (const ad of ads) {
    try {
      await fetch(`${CONTENT_API}/api/content`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${CONTENT_API_SECRET}`,
        },
        body: JSON.stringify({
          content_id: ad.id,
          source: "ppspy",
          creative_url: ad.creativeUrl,
          thumbnail_url: ad.thumbnailUrl,
          ad_copy: ad.adCopy,
          metadata_json: JSON.stringify({ reach: ad.reach, daysActive: ad.daysActive, platforms: ad.platforms }),
        }),
      });
    } catch (err) {
      console.error(`[content-api] Failed to write ${ad.id}:`, err);
      // Non-fatal — scrape continues
    }
  }
}
```

### Anti-Patterns to Avoid
- **Using `Base.metadata.create_all()` as the migration strategy for production:** `create_all()` only creates missing tables — it will NOT add new columns to existing tables. Once you have a live DB, use Alembic for all schema changes.
- **Storing status as an unconstrained string:** Without a CHECK constraint or enum, invalid statuses can be written silently. Use a Postgres CHECK constraint via `__table_args__` or validate at the API layer.
- **Hardcoding `GOOGLE_SHEET_ID` as a fallback default:** `fromSheet.ts` line 64 has `process.env.GOOGLE_SHEET_ID || "1p8pdlNQKYRoX8HydJAHqAX6NhK_FAMxt2WHmWWps-yw"`. This is a CLAUDE.md violation (real value as fallback). Fix this when touching `fromSheet.ts`.
- **Adding direct Postgres connection to decarba-remixer:** Would require duplicating DATABASE_URL secret in GitHub Actions decarba-remixer jobs. Use HTTP API instead.
- **Restarting Railway service to apply schema migrations:** Railway rebuild does NOT rerun `create_all()` for columns added to existing tables. Alembic is required.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migration for live DB | Custom SQL scripts, `create_all()` | Alembic | Alembic tracks migration history, handles rollback, generates SQL from model diffs automatically |
| Idempotent insert | Python try/except around INSERT | SQLAlchemy `insert().on_conflict_do_nothing()` | Race-condition safe, atomic, single DB roundtrip |
| Status validation | Manual if/else in every route | Transition table dict + 400 raise at PATCH endpoint | Central definition, easy to extend, clear error messages |
| Railway Postgres connection | Custom connection pool | SQLAlchemy `create_engine` with `pool_pre_ping=True` | Railway internal network can drop connections; `pool_pre_ping=True` detects stale connections before use |

**Key insight:** The live Railway DB already has 134 ads and 422 snapshots. Any schema change that drops or modifies existing tables will break the running service. Alembic additive migrations (only add new tables/columns, never drop) are the only safe path.

---

## Runtime State Inventory

> Included because this phase adds a new table to a live production database.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Railway Postgres: 7 campaigns, 134 ads, 422 snapshots in existing tables (verified via /api/debug) | Code edit only — add new `content_items` table additively; existing tables untouched |
| Live service config | Railway service `newg-pipeline` is live at `newg-pipeline-production.up.railway.app`; `DATABASE_URL` already set pointing to internal Postgres | No config change needed — DATABASE_URL is already correct |
| OS-registered state | None | None |
| Secrets/env vars | `DATABASE_URL` (Railway internal URL, set in Railway variables); `DASHBOARD_SECRET` (set in Railway); `GOOGLE_SHEET_ID` hardcoded fallback in `fromSheet.ts` (CLAUDE.md violation) | Fix hardcoded fallback in `fromSheet.ts`; add `CONTENT_API_URL` + `DASHBOARD_SECRET` to decarba-remixer GitHub Actions secrets for HTTP bridge |
| Build artifacts | None — Railway builds from Dockerfile on each push | None |

**Railway internal vs. public hostname:** `DATABASE_URL` uses `postgres.railway.internal` — only reachable from within Railway. Alembic migrations must run inside Railway (via Procfile or Railway shell), not from local dev machine.

---

## Common Pitfalls

### Pitfall 1: `create_all()` Does Not Migrate Existing Databases
**What goes wrong:** Developer adds `ContentItem` to `models.py`, redeploys, and sees the table is not created because `create_all()` only acts on tables that do not exist yet — but if a partial schema exists from a previous deploy, behavior is unpredictable.
**Why it happens:** `Base.metadata.create_all()` is idempotent only in the "skip existing tables" sense. It does not add columns to existing tables.
**How to avoid:** Add Alembic before making any schema changes. Run `alembic upgrade head` at service startup (Procfile pattern).
**Warning signs:** New model added but table not appearing in DB after redeploy.

### Pitfall 2: Railway Internal DB Not Reachable Locally
**What goes wrong:** Developer tries to run `alembic upgrade head` locally with `DATABASE_URL=postgres.railway.internal:5432/...` and gets a connection refused error.
**Why it happens:** `postgres.railway.internal` is a Railway-private hostname only resolvable inside the Railway network.
**How to avoid:** Run migrations via Railway shell (`railway run alembic upgrade head`) or via the Procfile startup command. Alternatively, use Railway's TCP proxy to get a public URL for local dev (Railway dashboard → Postgres service → Connect → Public).
**Warning signs:** `could not translate host name "postgres.railway.internal"` in local terminal.

### Pitfall 3: TypeScript Scraper Writes Block the Pipeline on API Failure
**What goes wrong:** `decarba-remixer` calls the content API for each scraped ad, and an API timeout or 5xx causes the entire scrape pipeline to fail.
**Why it happens:** Synchronous await in a for-loop with no try/catch isolation.
**How to avoid:** Wrap each `fetch()` call in try/catch and treat failures as non-fatal (log and continue). The scrape itself is the primary output; Postgres write is secondary.
**Warning signs:** GitHub Actions daily-scrape failing with network errors after adding API calls.

### Pitfall 4: Duplicate Content IDs Across Sources
**What goes wrong:** A TikTok video appears in both the TikTok scraper and the Meta Ad Library scraper with different IDs, creating two rows that should be one.
**Why it happens:** Cross-source dedup is a hard problem. `content_id` is source-specific.
**How to avoid:** Phase 1 dedup is per-source only (`UNIQUE(content_id, source)`). Cross-source dedup is a Phase 2 concern (DISC-01). Document this limitation clearly in the API.
**Warning signs:** Same creative appearing twice in the dashboard with different source labels.

### Pitfall 5: Status Transitions Without Auth
**What goes wrong:** The PATCH status endpoint is callable without auth, allowing any external actor to advance items to `launched`.
**Why it happens:** Forgetting to add `Depends(verify_auth)` on the new routes router.
**How to avoid:** All new routes in `routes/content.py` must use `router = APIRouter(dependencies=[Depends(verify_auth)])` — matching the pattern in `routes/ads.py`.
**Warning signs:** `curl -X PATCH .../api/content/x/status` succeeds without Authorization header.

---

## Code Examples

### Full `routes/content.py` skeleton
```python
# Source: FastAPI docs + SQLAlchemy 2.0 PostgreSQL insert docs
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from pydantic import BaseModel
from typing import Optional
from db import get_db
from models import ContentItem
from routes.auth import verify_auth

router = APIRouter(dependencies=[Depends(verify_auth)])

class ContentItemCreate(BaseModel):
    content_id: str
    source: str  # ppspy | tiktok | pinterest | meta
    creative_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    ad_copy: Optional[str] = None
    metadata_json: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str

VALID_TRANSITIONS = {
    "discovered": ["surfaced"],
    "surfaced": ["queued", "discovered"],
    "queued": ["ready_to_launch", "surfaced"],
    "ready_to_launch": ["launched", "queued"],
    "launched": [],
}

@router.post("/api/content", status_code=201)
def create_content_item(body: ContentItemCreate, db: Session = Depends(get_db)):
    import uuid
    item_data = body.model_dump()
    item_data["id"] = str(uuid.uuid4())
    item_data["status"] = "discovered"
    stmt = pg_insert(ContentItem).values(**item_data).on_conflict_do_nothing(
        constraint="uq_content_id_source"
    )
    db.execute(stmt)
    db.commit()
    return db.query(ContentItem).filter_by(
        content_id=body.content_id, source=body.source
    ).first()

@router.get("/api/content")
def list_content_items(status: Optional[str] = None, source: Optional[str] = None,
                        db: Session = Depends(get_db)):
    q = db.query(ContentItem)
    if status:
        q = q.filter_by(status=status)
    if source:
        q = q.filter_by(source=source)
    return q.order_by(ContentItem.discovered_at.desc()).limit(200).all()

@router.patch("/api/content/{item_id}/status")
def update_status(item_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")
    allowed = VALID_TRANSITIONS.get(item.status, [])
    if body.status not in allowed:
        raise HTTPException(400, f"Invalid transition: {item.status} → {body.status}")
    item.status = body.status
    db.commit()
    return {"id": item_id, "status": item.status}
```

### Alembic env.py key section
```python
# alembic/env.py — after alembic init
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Load DATABASE_URL from environment (never hardcode)
database_url = os.environ["DATABASE_URL"]
# Railway uses postgres:// — normalize to postgresql+psycopg://
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

config.set_main_option("sqlalchemy.url", database_url)

from db import Base
import models  # ensure all models are registered on Base.metadata
target_metadata = Base.metadata
```

### Procfile with migration startup
```
web: alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Railway CLI | Deploy/configure service | Yes | 4.33.0 | — |
| Railway Postgres service | DATABASE_URL | Yes | postgresql (internal) | — |
| Python 3.x (local) | Alembic setup | Yes (confirmed pip3 works) | 3.x | — |
| SQLAlchemy 2.0.35 | ORM | Yes (in requirements.txt) | 2.0.35 | — |
| psycopg[binary] | Postgres adapter | Yes (in requirements.txt) | >=3.2.10 | — |
| Alembic | Schema migrations | NOT in requirements.txt | Need to add 1.14.0 | Cannot run migrations without it |
| Node 24 / fetch() | TypeScript HTTP bridge | Yes | v24.14.0 | — |
| `DASHBOARD_SECRET` | API auth for TS bridge | Yes (set in Railway variables) | `newg2024command` | — |
| `CONTENT_API_URL` | decarba-remixer → API | NOT set in GitHub Actions secrets | Need to add | Skip Postgres write (non-fatal) |

**Missing dependencies with no fallback:**
- `alembic` not in `ad-command-center/requirements.txt` — must be added before schema migration can run

**Missing dependencies with fallback:**
- `CONTENT_API_URL` not in GitHub Actions secrets — TypeScript bridge fails gracefully (non-fatal log)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (from CLAUDE.md stack — not yet installed in ad-command-center) |
| Config file | none — see Wave 0 |
| Quick run command | `cd ad-command-center && pytest tests/ -x -q` |
| Full suite command | `cd ad-command-center && pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATE-01 | /health returns 200 | smoke | `curl -sf https://newg-pipeline-production.up.railway.app/health` | Manual (live endpoint) |
| STATE-02 | Insert content_item with same content_id twice → 1 row only | unit | `pytest tests/test_content_items.py::test_idempotent_insert -x` | Wave 0 |
| STATE-02 | content_id + source unique constraint enforced | unit | `pytest tests/test_content_items.py::test_unique_constraint -x` | Wave 0 |
| STATE-03 | Valid status transition succeeds | unit | `pytest tests/test_content_items.py::test_status_transition_valid -x` | Wave 0 |
| STATE-03 | Invalid status transition returns 400 | unit | `pytest tests/test_content_items.py::test_status_transition_invalid -x` | Wave 0 |
| STATE-04 | fromSheet.ts fetches pending submissions from Sheets | manual-only | Manual: `npm run launch` with pending Sheet row | Existing code works |

### Sampling Rate
- **Per task commit:** `pytest tests/test_content_items.py -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `ad-command-center/tests/__init__.py` — test package init
- [ ] `ad-command-center/tests/test_content_items.py` — covers STATE-02, STATE-03
- [ ] `ad-command-center/tests/conftest.py` — SQLite in-memory fixture (use `sqlite:///:memory:` for unit tests, no Railway connection needed)
- [ ] Framework install: `pip install pytest==8.x` in requirements.txt or test-requirements.txt

**Note for conftest.py:** Override `DATABASE_URL` env var with `sqlite:///:memory:` for unit tests. SQLAlchemy 2.x + SQLite supports the same `on_conflict_do_nothing` API as Postgres for test purposes via `sqlite_upsert`. Alternatively, test idempotency at the model layer only (not via Postgres-specific dialect).

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psycopg2 | psycopg3 (psycopg[binary]) | 2023 | db.py already uses `postgresql+psycopg://` scheme — correct |
| `declarative_base()` from sqlalchemy.ext.declarative | `class Base(DeclarativeBase)` | SQLAlchemy 2.0 (2023) | db.py already uses the new style — correct |
| `gspread.authorize()` | `gspread.service_account()` or OAuth2 client | gspread 6.x | Not relevant to Phase 1 (Sheets stays read-only via gviz CSV) |
| Railway `startCommand` in service config | `Procfile` with multi-command startup | Railway 2024 | Procfile pattern is supported and simpler for `alembic upgrade head && uvicorn ...` |

---

## Open Questions

1. **Alembic migration against Railway Postgres from local dev**
   - What we know: `postgres.railway.internal` is not publicly reachable
   - What's unclear: Whether developer wants to run migrations locally (requires Railway TCP proxy) or rely on Procfile startup command
   - Recommendation: Use Procfile startup command — `alembic upgrade head && uvicorn ...`. This is the simplest path with no local config changes.

2. **`fromSheet.ts` hardcoded GOOGLE_SHEET_ID fallback**
   - What we know: Line 64 has `process.env.GOOGLE_SHEET_ID || "1p8pdlNQKYRoX8HydJAHqAX6NhK_FAMxt2WHmWWps-yw"` — violates CLAUDE.md
   - What's unclear: Whether to fix this in Phase 1 (touching fromSheet.ts) or defer to Phase 4
   - Recommendation: Fix in Phase 1 plan as a one-line change when we're already touching decarba-remixer for the content API bridge. Low risk, high compliance value.

3. **Content ID stability for PPSpy scraped items**
   - What we know: `ppspy.ts` generates IDs as `decarba_${todayDir()}_${i}` (index-based, not stable across runs)
   - What's unclear: If PPSpy scraper runs twice on the same day, the first 15 ads get the same IDs — but if order changes, dedup breaks
   - Recommendation: Phase 1 dedup uses `(content_id, source)` uniqueness. For PPSpy, the `content_id` field should eventually be the actual PPSpy ad ID (a stable hash or URL component), not an index. This is a Phase 2 improvement (DISC-01). For Phase 1, the current index-based ID is acceptable — document the limitation.

---

## Sources

### Primary (HIGH confidence)
- Live Railway service `/health` and `/api/debug` endpoints — deployment status, DATABASE_URL, existing table counts verified 2026-03-27
- `railway variables list` CLI output — all Railway env vars verified 2026-03-27
- `ad-command-center/models.py`, `db.py`, `main.py`, `requirements.txt` — existing code read directly
- `decarba-remixer/src/launcher/fromSheet.ts`, `src/index.ts`, `package.json` — TypeScript pipeline read directly
- SQLAlchemy 2.0 docs pattern (DeclarativeBase, `insert().on_conflict_do_nothing()`) — confirmed in codebase usage

### Secondary (MEDIUM confidence)
- Alembic 1.14.0 — latest version per `pip show alembic` absence + knowledge of PyPI current; pattern from Alembic docs
- Railway Procfile multi-command pattern — standard Railway documentation pattern for pre-start hooks

### Tertiary (LOW confidence)
- SQLite in-memory for pytest conftest as substitute for Postgres dialect in unit tests — `on_conflict_do_nothing` is Postgres-specific; unit tests may need to mock at the service layer instead

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing requirements.txt confirmed, Railway service confirmed live
- Architecture: HIGH — existing code patterns read directly, deployment state verified via live endpoints
- Pitfalls: HIGH — derived from direct code reading (hardcoded fallback found, create_all limitation documented)
- Test gaps: MEDIUM — pytest framework not yet in requirements.txt, test files don't exist yet

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable stack; Railway config unlikely to change)
