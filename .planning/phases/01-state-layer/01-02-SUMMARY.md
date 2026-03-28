---
phase: 01-state-layer
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, pydantic, content-lifecycle]

requires:
  - phase: 01-01
    provides: ContentItem SQLAlchemy model with uq_content_id_source constraint and status field

provides:
  - POST /api/content — idempotent insert using pg ON CONFLICT DO NOTHING
  - GET /api/content — filterable list by status/source, ordered by discovered_at desc
  - PATCH /api/content/{item_id}/status — lifecycle transition enforcement via VALID_TRANSITIONS
  - content router wired into main FastAPI app

affects:
  - 01-03 (dedup layer — writes to /api/content)
  - 01-04 (scraper integration — calls POST /api/content)
  - Phase 02 (discovery pipeline — all scrapers write via this API)

tech-stack:
  added: []
  patterns:
    - "Router-level auth: router = APIRouter(dependencies=[Depends(verify_auth)]) — all routes protected without per-route decoration"
    - "Idempotent insert: pg_insert().on_conflict_do_nothing(constraint=...) then fetch — avoids race conditions on duplicate writes"
    - "Lifecycle enforcement: VALID_TRANSITIONS dict maps current_status -> allowed_next_statuses; invalid transitions return 400"

key-files:
  created:
    - ad-command-center/routes/content.py
  modified:
    - ad-command-center/main.py

key-decisions:
  - "Router-level dependency injection for auth (not per-route) — consistent with pattern in plan spec; reduces boilerplate and ensures no route is accidentally unprotected"
  - "pg_insert ON CONFLICT DO NOTHING for idempotent insert — matches plan spec; concurrent inserts from multiple scrapers cannot produce duplicates"

patterns-established:
  - "Pattern: All new API routers use router = APIRouter(dependencies=[Depends(verify_auth)]) — no per-route auth decoration"
  - "Pattern: Status transitions enforced at API boundary via VALID_TRANSITIONS dict — pipeline scripts cannot skip states"

requirements-completed: [STATE-02, STATE-03]

duration: 4min
completed: "2026-03-28"
---

# Phase 01 Plan 02: Content CRUD Endpoints Summary

**Three authenticated FastAPI endpoints enforcing ContentItem lifecycle with idempotent insert, filterable list, and validated status transitions via VALID_TRANSITIONS dict**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-28T02:26:47Z
- **Completed:** 2026-03-28T02:30:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `routes/content.py` with POST /api/content (idempotent via pg ON CONFLICT DO NOTHING), GET /api/content (filterable + ordered), PATCH /api/content/{item_id}/status (lifecycle enforcement)
- All routes protected at router level with `dependencies=[Depends(verify_auth)]`
- VALID_TRANSITIONS dict enforces discovered→surfaced→queued→ready_to_launch→launched with 400 on invalid transitions
- Wired content router into `main.py` — `/api/content` routes now live in the FastAPI app alongside existing routes

## Task Commits

Each task was committed atomically:

1. **Task 1: Create routes/content.py with POST, GET, PATCH endpoints** - `7e65114` (feat)
2. **Task 2: Wire content router into main.py** - `62598fb` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `ad-command-center/routes/content.py` — ContentItem CRUD endpoints with lifecycle enforcement
- `ad-command-center/main.py` — Added content import and `app.include_router(content.router)`

## Decisions Made

- Router-level auth dependency (`APIRouter(dependencies=[Depends(verify_auth)])`) instead of per-route decoration — consistent with plan spec, prevents accidental unprotected routes
- pg_insert ON CONFLICT DO NOTHING for idempotent insert — handles concurrent scraper writes without 409 errors; fetch-after-insert returns existing row on conflict

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — Python 3.14 Pydantic v1 compatibility warning from openai library on import; this is a pre-existing warning from the openai package (unrelated to this plan's changes), not a new issue.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Content CRUD API is ready — all scrapers can now write discovered content via POST /api/content
- Dedup layer (01-03, already completed) can use this endpoint as its write target
- Phase 02 scrapers can begin integration against these endpoints

---
*Phase: 01-state-layer*
*Completed: 2026-03-28*

## Self-Check: PASSED

- FOUND: ad-command-center/routes/content.py
- FOUND: ad-command-center/main.py
- FOUND: .planning/phases/01-state-layer/01-02-SUMMARY.md
- FOUND: commit 7e65114 (feat: create routes/content.py)
- FOUND: commit 62598fb (feat: wire content router into main.py)
