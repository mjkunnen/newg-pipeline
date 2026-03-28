---
phase: 03-dashboard-unification
plan: "01"
subsystem: api
tags: [fastapi, pydantic, sqlalchemy, pytest, sqlite, tdd]

requires:
  - phase: 01-state-layer
    provides: ContentItem model, content router with auth, DB session fixtures

provides:
  - PATCH /api/content/{id}/status accepts optional drive_link field, merged into metadata_json
  - GET /api/content/health returns per-source last_seen, today_count, ok for ppspy/tiktok/pinterest/meta
  - 10 passing tests covering all new backend behavior (4 drive_link + 6 health)

affects:
  - 03-02 (frontend dashboard remake workflow — needs drive_link PATCH)
  - 03-03 (frontend health panel — needs /api/content/health)

tech-stack:
  added: []
  patterns:
    - "Health endpoint placed before wildcard routes to avoid FastAPI path collision with {item_id}"
    - "Naive datetime made tz-aware (replace tzinfo=timezone.utc) for SQLite test compatibility"
    - "TDD: RED commit (failing tests) then GREEN commit (implementation) per task"

key-files:
  created:
    - ad-command-center/tests/test_content_health.py
  modified:
    - ad-command-center/routes/content.py
    - ad-command-center/tests/test_content_items.py

key-decisions:
  - "Direct function call tests (not TestClient) for health endpoint — simpler, bypasses auth, works cleanly with db fixture"
  - "Naive datetime tz-awareness fix applied in content_health() not in tests — production-safe, handles both SQLite (naive) and Postgres (aware)"
  - "_make_item helper signature fixed to accept explicit status kwarg — avoids collision with **kwargs pattern"

patterns-established:
  - "Route ordering: specific paths (health) before parameterized paths ({item_id}) in FastAPI routers"
  - "metadata_json: always json.loads(item.metadata_json or '{}') before merge — null-safe pattern"

requirements-completed: [DASH-04, DASH-05]

duration: 15min
completed: "2026-03-28"
---

# Phase 03 Plan 01: Backend Extensions for Dashboard Remake + Health Panel Summary

**FastAPI PATCH endpoint extended with optional drive_link (stored in metadata_json) and new GET /api/content/health endpoint returning per-source last_seen/today_count/ok — 15 tests all green.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-28T04:10:00Z
- **Completed:** 2026-03-28T04:25:00Z
- **Tasks:** 2
- **Files modified:** 3 (routes/content.py, tests/test_content_items.py, tests/test_content_health.py)

## Accomplishments

- Extended `StatusUpdate` Pydantic model with `drive_link: Optional[str] = None`
- `update_status` route merges drive_link into metadata_json (null-safe, non-destructive to existing fields)
- New `GET /api/content/health` endpoint aggregates per-source: `last_seen` (ISO or null), `today_count` (int), `ok` (bool)
- 4 drive_link tests + 6 health tests, all passing with 0 regressions on existing 5 tests

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: drive_link failing tests** - `7da5866` (test)
2. **Task 1 GREEN: drive_link implementation** - `23120ca` (feat)
3. **Task 2: health endpoint + tests** - `c1850ee` (feat)

## Files Created/Modified

- `ad-command-center/routes/content.py` - drive_link in StatusUpdate + update_status logic; new content_health endpoint
- `ad-command-center/tests/test_content_items.py` - 4 drive_link test cases; fixed _make_item signature
- `ad-command-center/tests/test_content_health.py` - 6 health endpoint test cases (new file)

## Decisions Made

- Direct function call tests (not TestClient) for health endpoint — simpler, no auth setup needed, works with db fixture
- Naive datetime tz-awareness fixed inside `content_health()` (not in tests) — SQLite returns naive datetimes, Postgres returns aware; fix is safe in both environments
- `_make_item` helper bug (status kwarg collision) fixed as Rule 1 auto-fix — existing tests unaffected

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _make_item status kwarg collision in test helper**
- **Found during:** Task 1 RED phase
- **Issue:** `_make_item("ad-010", status="queued")` raised TypeError because helper hardcoded `status="discovered"` in body then also received status via **kwargs
- **Fix:** Changed `_make_item` signature to `def _make_item(content_id, source="ppspy", status="discovered", **kwargs)` — explicit param, no collision
- **Files modified:** ad-command-center/tests/test_content_items.py
- **Verification:** Tests ran and produced correct AttributeError (drive_link missing) as expected for RED phase
- **Committed in:** 7da5866 (Task 1 RED commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Necessary for TDD RED phase to fail for the right reason. No scope creep.

## Issues Encountered

- SQLite returns naive datetimes while production Postgres returns tz-aware datetimes. Applied `replace(tzinfo=timezone.utc)` in the route function when `tzinfo is None` — covers both environments without changing test behavior.

## User Setup Required

None - no external service configuration required. All new endpoints use existing auth middleware and DB session.

## Next Phase Readiness

- Plan 02 (frontend remake workflow) can now implement drive_link submission to `PATCH /api/content/{id}/status`
- Plan 03 (frontend health panel) can now render data from `GET /api/content/health`
- No blockers

---
*Phase: 03-dashboard-unification*
*Completed: 2026-03-28*
