---
phase: 02-discovery-reliability
plan: 03
subsystem: scraping
tags: [pinterest, postgres, dedup, typescript, vitest, content-api]

requires:
  - phase: 01-state-layer
    provides: "Content API (POST/GET /api/content) + ContentItem Postgres model"
  - phase: 02-01
    provides: "contentApi.ts writeToContentAPI utility + config.ts loadConfig utility (created inline as blocking dep)"

provides:
  - "Pinterest scraper reads seen pins from Postgres via GET /api/content?source=pinterest"
  - "Pinterest scraper writes new discoveries to Postgres via writeToContentAPI"
  - "pinterest-boards.json externalizes board_url, max_new_pins, scroll_rounds, stale_rounds_limit"
  - "contentApi.ts shared utility (writeToContentAPI with source param, WriteResult interface)"
  - "config.ts loadConfig<T> generic JSON config loader"
  - "vitest test infrastructure + pinterest-dedup.test.ts (3 tests)"

affects: [02-discovery-reliability, 03-dashboard-unification]

tech-stack:
  added: [vitest 4.1.2]
  patterns:
    - "Postgres content API as single dedup mechanism — all scrapers POST discovered items, GET seen IDs before writing"
    - "Fail-open dedup — missing CONTENT_API_URL returns empty Set, never blocks scraping"
    - "Config externalization — per-source JSON in decarba-remixer/config/, loaded via loadConfig<T>"
    - "Structured result logging — [result] source=X found=N written=N skipped=N errors=N"

key-files:
  created:
    - decarba-remixer/src/scraper/contentApi.ts
    - decarba-remixer/src/scraper/config.ts
    - decarba-remixer/config/pinterest-boards.json
    - decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts
    - decarba-remixer/vitest.config.ts
  modified:
    - decarba-remixer/src/scraper/pinterest.ts
    - decarba-remixer/package.json

key-decisions:
  - "Fail-open dedup: if CONTENT_API_URL/DASHBOARD_SECRET missing, return empty Set and continue scraping (better to re-discover than skip all)"
  - "content_id prefix strip: Postgres stores 'pinterest_12345', dedup compares against raw pinId — strip prefix on GET"
  - "contentApi.ts and config.ts created in this plan as blocking dependency (02-01 not yet executed in parallel)"

patterns-established:
  - "getProcessedPinIds pattern: GET /api/content?source=X&limit=1000, strip source prefix, return Set<string>"
  - "writeToContentAPI(ads, source) call after building ads array, before return"

requirements-completed: [SRC-02, DISC-03, DISC-05]

duration: 8min
completed: 2026-03-28
---

# Phase 02 Plan 03: Pinterest Postgres Dedup Summary

**Pinterest scraper rewired to check Postgres for seen pins (replacing Google Sheet CSV), write new discoveries via content API, with board settings externalized to pinterest-boards.json**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T03:25:00Z
- **Completed:** 2026-03-28T03:33:51Z
- **Tasks:** 1
- **Files modified:** 7 (2 modified, 5 created)

## Accomplishments
- Removed Google Sheet CSV dedup (SHEET_ID, SHEET_CSV_URL, gviz endpoint) from pinterest.ts
- Added Postgres-backed getProcessedPinIds() — fetches seen pin IDs from content API
- Added writeToContentAPI(ads, "pinterest") call after building the ads array
- Externalized board_url, max_new_pins, scroll_rounds, stale_rounds_limit to pinterest-boards.json
- Created contentApi.ts shared utility (needed by this and future plans)
- Created config.ts loadConfig<T> utility for per-source JSON configs
- Installed vitest + config, created 3 real tests (all passing)

## Task Commits

1. **Task 1: Pinterest Postgres dedup + config externalization** - `85be308` (feat)

## Files Created/Modified
- `decarba-remixer/src/scraper/pinterest.ts` — Postgres dedup, config-driven settings, writeToContentAPI call
- `decarba-remixer/config/pinterest-boards.json` — board_url, max_new_pins, scroll_rounds, stale_rounds_limit
- `decarba-remixer/src/scraper/contentApi.ts` — writeToContentAPI(ads, source): Promise<WriteResult>
- `decarba-remixer/src/scraper/config.ts` — loadConfig<T>(filename): T from decarba-remixer/config/
- `decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts` — 3 tests for writeToContentAPI env-guard behavior
- `decarba-remixer/vitest.config.ts` — vitest config for Node ESM environment
- `decarba-remixer/package.json` — added vitest devDep + test/test:watch scripts

## Decisions Made
- Fail-open dedup: missing env vars return empty Set (not abort) — scraper always runs, dedup best-effort
- content_id prefix strip: stored as "pinterest_12345" in Postgres, compared as raw pinId in dedup Set
- contentApi.ts and config.ts created here as Rule 3 fix (02-01 is parallel, blocking dependency)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created contentApi.ts and config.ts inline**
- **Found during:** Task 1 (Pinterest dedup implementation)
- **Issue:** plan 02-03 depends_on 02-01 which creates contentApi.ts and config.ts, but 02-01 has not yet executed in parallel execution context
- **Fix:** Implemented contentApi.ts and config.ts as specified in 02-01-PLAN.md to unblock execution
- **Files modified:** decarba-remixer/src/scraper/contentApi.ts, decarba-remixer/src/scraper/config.ts
- **Verification:** npx tsc --noEmit exits 0, npx vitest run passes 3 tests
- **Committed in:** 85be308

---

**Total deviations:** 1 auto-fixed (1 blocking dependency)
**Impact on plan:** Essential — plan could not execute without contentApi.ts and config.ts. Strictly follows the 02-01 plan specification.

## Issues Encountered
None.

## Known Stubs
None — all implemented and tested.

## Next Phase Readiness
- Pinterest now uses Postgres dedup — ready for reliable daily discovery
- contentApi.ts and config.ts available as shared utilities for plans 02-02, 02-04, 02-05
- Plans 02-02 (TikTok) and 02-04 (Meta) can import writeToContentAPI and loadConfig directly

---
*Phase: 02-discovery-reliability*
*Completed: 2026-03-28*
