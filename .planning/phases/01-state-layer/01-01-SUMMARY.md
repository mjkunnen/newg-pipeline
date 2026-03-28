---
phase: 01-state-layer
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, postgres, pytest, railway, migrations]

requires:
  - phase: 00-codebase-consolidation
    provides: canonical ad-command-center codebase with pinned dependencies

provides:
  - ContentItem SQLAlchemy model with UniqueConstraint(content_id, source)
  - Alembic migration for content_items table (revision 9a7e80fe5cdc)
  - Procfile updated to run alembic upgrade head at Railway startup
  - pytest test scaffold with 5 passing tests for idempotency and uniqueness contracts
  - alembic.ini with placeholder DATABASE_URL (env.py overrides at runtime)

affects:
  - 01-02 (content CRUD API endpoints — builds on ContentItem model)
  - 01-03 (TypeScript bridge — POSTs to content API built on this model)
  - 01-04 (status lifecycle — extends ContentItem status field)

tech-stack:
  added:
    - alembic==1.14.0 (migration management)
    - pytest==8.3.5 (test runner)
  patterns:
    - TDD: tests written before implementation, RED commit before GREEN commit
    - Alembic env.py reads DATABASE_URL from environment; raises RuntimeError if missing
    - Railway postgres:// normalization to postgresql+psycopg:// in both db.py and alembic/env.py
    - Test conftest.py sets dummy env vars to allow db.py/config.py imports without real credentials
    - Procfile: alembic upgrade head runs before uvicorn for zero-downtime schema migration

key-files:
  created:
    - ad-command-center/alembic.ini
    - ad-command-center/alembic/env.py
    - ad-command-center/alembic/script.py.mako
    - ad-command-center/alembic/versions/9a7e80fe5cdc_add_content_items_table.py
    - ad-command-center/alembic/versions/.gitkeep
    - ad-command-center/tests/__init__.py
    - ad-command-center/tests/conftest.py
    - ad-command-center/tests/test_content_items.py
  modified:
    - ad-command-center/models.py (ContentItem class appended)
    - ad-command-center/requirements.txt (alembic, pytest appended)
    - ad-command-center/Procfile (alembic upgrade head prepended)

key-decisions:
  - "Manual migration (alembic revision -m) used instead of --autogenerate: Railway Postgres internal URL not reachable locally; migration SQL written manually to match ContentItem model exactly"
  - "conftest.py uses setdefault() for env vars: allows real .env values to take precedence if present; dummy test values only fill gaps"
  - "alembic/env.py raises RuntimeError on missing DATABASE_URL rather than using a fallback default, per CLAUDE.md security rules"

patterns-established:
  - "Alembic pattern: env.py reads DATABASE_URL from os.environ, normalizes postgres:// prefix, sets config option dynamically"
  - "Test pattern: conftest.py sets all required env vars before any app imports to prevent KeyError from config.py"
  - "TDD commit sequence: test(RED) commit -> feat(GREEN) commit per task"

requirements-completed: [STATE-01, STATE-02]

duration: 12min
completed: 2026-03-28
---

# Phase 01 Plan 01: ContentItem Model and Alembic Migrations Summary

**ContentItem SQLAlchemy model with UniqueConstraint(content_id, source), Alembic initialized with content_items migration, Railway Procfile updated to run alembic upgrade head on deploy, and 5-test pytest scaffold validating idempotency and uniqueness contracts**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-28T02:10:00Z
- **Completed:** 2026-03-28T02:23:16Z
- **Tasks:** 2 completed
- **Files modified:** 11

## Accomplishments

- ContentItem model added to models.py with UniqueConstraint(content_id, source, name="uq_content_id_source"), indexes on status and source, UUID4 auto-generated primary key, and default status "discovered"
- Alembic initialized: alembic.ini (placeholder URL), env.py (reads DATABASE_URL from environment, normalizes postgres:// prefix, no hardcoded credentials), manual migration 9a7e80fe5cdc creating content_items table with full schema
- All 5 pytest tests pass green: idempotent insert, unique constraint enforcement, same content_id different source allowed, default status, UUID auto-generation
- Procfile updated: `alembic upgrade head` runs before uvicorn — migration applies automatically on next Railway deploy

## Task Commits

Each task was committed atomically:

1. **Task 1 RED (failing tests)** - `11487be` (test)
2. **Task 1 GREEN (ContentItem + deps + Procfile)** - `6ca8547` (feat)
3. **Task 2 (Alembic init + migration)** - `678b9b1` (feat)

## Files Created/Modified

- `ad-command-center/models.py` - ContentItem class appended with UniqueConstraint and indexes
- `ad-command-center/requirements.txt` - alembic==1.14.0 and pytest==8.3.5 appended
- `ad-command-center/Procfile` - alembic upgrade head prepended before uvicorn
- `ad-command-center/alembic.ini` - Alembic config; sqlalchemy.url set to placeholder (overridden by env.py)
- `ad-command-center/alembic/env.py` - Custom env with DATABASE_URL from environment, postgres:// normalization, Base.metadata target
- `ad-command-center/alembic/versions/9a7e80fe5cdc_add_content_items_table.py` - Manual migration: create_table content_items, UniqueConstraint, 2 indexes
- `ad-command-center/alembic/versions/.gitkeep` - Tracks empty versions directory
- `ad-command-center/tests/__init__.py` - Empty package marker
- `ad-command-center/tests/conftest.py` - Dummy env vars + SQLite in-memory db fixture
- `ad-command-center/tests/test_content_items.py` - 5 tests for idempotency, uniqueness, default values, UUID generation

## Decisions Made

- Manual migration over --autogenerate: Railway Postgres internal URL is not reachable locally; --autogenerate requires a live DB connection to inspect current schema. Manual migration SQL written to exactly match the ContentItem model.
- conftest.py uses `os.environ.setdefault()` so real `.env` values take precedence if present; test-only dummies only fill missing vars.
- env.py raises `RuntimeError` on missing DATABASE_URL instead of defaulting — per CLAUDE.md security rules ("NEVER put real values as fallback defaults").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] conftest.py extended to set all required env vars**
- **Found during:** Task 1 (RED phase — running tests for first time)
- **Issue:** config.py requires META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, OPENAI_API_KEY, DASHBOARD_SECRET at import time. Plan's conftest.py only set DATABASE_URL. Import of `db` failed with KeyError on META_AD_ACCOUNT_ID.
- **Fix:** Extended conftest.py to set all env vars required by config.py using setdefault() with dummy test-only values.
- **Files modified:** ad-command-center/tests/conftest.py
- **Verification:** All 5 pytest tests pass after fix.
- **Committed in:** 11487be (Task 1 RED commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical env var setup)
**Impact on plan:** Required for test execution; no scope creep. Fix is correct and safe (setdefault preserves real env values).

## Issues Encountered

- Python executable: `python` and `python3` both resolve to the Windows Store stub on this machine. Used explicit path `/c/Users/maxku/AppData/Local/Python/pythoncore-3.14-64/python.exe` for all test runs.

## User Setup Required

None - no external service configuration required for this plan. The Alembic migration will run automatically on next Railway deploy via the updated Procfile.

## Next Phase Readiness

- ContentItem model is in place — Plan 01-02 (CRUD API endpoints) can build on it immediately
- All 5 tests pass; contract for idempotent insert is locked
- Migration will apply on Railway at next `git push` — no manual DB intervention needed
- Railway Postgres live DB (7 campaigns, 134 ads, 422 snapshots) is safe — migration only adds the new table, no modifications to existing tables

## Self-Check: PASSED

- All 9 key files found on disk
- All 3 task commits verified in git log (11487be, 6ca8547, 678b9b1)
- All 5 pytest tests pass in final run

---
*Phase: 01-state-layer*
*Completed: 2026-03-28*
