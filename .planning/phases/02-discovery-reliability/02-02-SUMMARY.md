---
phase: 02-discovery-reliability
plan: 02
subsystem: tiktok-scraper
tags: [typescript, tiktok, dedup, postgres, engagement-rate, vitest, config]

requires:
  - phase: 02-discovery-reliability
    plan: 01
    provides: contentApi.ts writeToContentAPI utility, config.ts loadConfig utility, vitest infrastructure

provides:
  - meetsEngagementThreshold() exported function in tiktok.ts
  - fetchFollowerCounts() per-account follower lookup via EnsembleData
  - config/tiktok-accounts.json with 13 competitors, min_engagement_rate, min_reach_fallback, max_age_days, max_carousels
  - TikTok dedup via Postgres ON CONFLICT (file-based dedup removed)
  - writeToContentAPI(ads, "tiktok") call with structured result log
  - Real tests in tiktok-filter.test.ts and dedup.test.ts

affects:
  - 02-03 (Pinterest scraper — same contentApi pattern)
  - 02-04 (Meta Ad Library scraper — same contentApi pattern)
  - 02-05 (PPSpy config externalization — same config.ts pattern)
  - daily-scrape.yml (runs tiktok.ts — now writes to Postgres instead of file)

tech-stack:
  added:
    - vitest 4.1.2 (test runner, devDependency)
    - contentApi.ts (shared WriteResult + writeToContentAPI utility)
    - config.ts (shared loadConfig<T> utility)
  patterns:
    - Engagement rate filter: playCount/followerCount >= min_engagement_rate (not flat view count)
    - Follower=0 fallback: use min_reach_fallback flat view count check
    - Config externalization: loadConfig<TikTokConfig>("tiktok-accounts.json") at runtime
    - Postgres dedup: ON CONFLICT DO NOTHING via writeToContentAPI — no file writes
    - Structured result log: [result] source=tiktok found=N written=N skipped=N errors=0

key-files:
  created:
    - decarba-remixer/config/tiktok-accounts.json
    - decarba-remixer/src/scraper/contentApi.ts
    - decarba-remixer/src/scraper/config.ts
    - decarba-remixer/vitest.config.ts
    - decarba-remixer/src/scraper/__tests__/dedup.test.ts
    - decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts
    - decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts
    - decarba-remixer/src/scraper/__tests__/config.test.ts
    - decarba-remixer/src/scraper/__tests__/meta.test.ts
    - decarba-remixer/src/scraper/__tests__/ppspy-config.test.ts
  modified:
    - decarba-remixer/src/scraper/tiktok.ts (engagement rate filter, config loading, Postgres dedup)
    - decarba-remixer/src/index.ts (import from contentApi.ts, remove inline writeToContentAPI)
    - decarba-remixer/package.json (vitest devDep, test/test:watch scripts)

key-decisions:
  - "Moved ENSEMBLEDATA_TOKEN requireEnv call from module-level to inside scrapeTiktok() so tests can import tiktok.ts without the env var set"
  - "TikTok file-based dedup (scout/processed_tiktok.json) fully removed; Postgres ON CONFLICT DO NOTHING is the sole dedup mechanism per D-01, D-02"
  - "fetchFollowerCounts uses delay(300ms) between requests and sets count=0 on any error (non-fatal: falls back to min_reach_fallback check)"
  - "contentApi.ts and config.ts created as 02-01 foundation prerequisite (02-01 not yet executed in parallel — Rule 3 auto-fix blocking dependency)"

requirements-completed: [SRC-01, DISC-01, DISC-02, DISC-05]

duration: 4min
completed: 2026-03-28
---

# Phase 02 Plan 02: TikTok Postgres Dedup + Engagement Rate Filter Summary

**TikTok scraper rewired to use Postgres content API for dedup, engagement rate filter (views/followers per account) replacing flat view count, and all hardcoded settings externalized to config/tiktok-accounts.json**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-28T03:31:46Z
- **Completed:** 2026-03-28T03:36:00Z
- **Tasks:** 2 completed (+ 1 prerequisite deviation)
- **Files modified:** 13

## Accomplishments

- Created `contentApi.ts` shared utility: `writeToContentAPI(ads, source)` returning `WriteResult {written, skipped}` — extracted from index.ts inline function, generalized with `source` parameter
- Created `config.ts` loader: `loadConfig<T>(filename)` reads JSON from `decarba-remixer/config/` directory
- Installed vitest 4.1.2, added test/test:watch scripts, created vitest.config.ts
- Scaffolded 6 test stub files in `src/scraper/__tests__/` (all pass green)
- Created `config/tiktok-accounts.json` with 13 competitor accounts, `min_engagement_rate: 0.15`, `min_reach_fallback: 3000`, `max_age_days: 14`, `max_carousels: 2`
- Added `export function meetsEngagementThreshold(playCount, followerCount, minRate, minReachFallback)` to tiktok.ts — pure function, fully testable
- Added `fetchFollowerCounts()` calling EnsembleData `/tt/user/info` per account with 300ms delay and error fallback to 0
- Removed hardcoded constants: `TIKTOK_ACCOUNTS`, `MIN_REACH`, `MAX_AGE_DAYS`, `MAX_CAROUSELS` — all read from config
- Removed file-based dedup: `PROCESSED_FILE`, `getProcessedIds()`, `saveProcessedId()` — Postgres ON CONFLICT DO NOTHING is the sole dedup mechanism
- Updated `dedup.test.ts` with real tests importing `writeToContentAPI` directly — tests that env vars not set returns `{written:0, skipped:0}`
- All 13 tests pass (4 engagement rate, 2 dedup, 7 stub), TypeScript compiles clean

## Task Commits

1. **Prerequisite foundation** - `5be7963` (chore) — vitest + contentApi.ts + config.ts + 6 test stubs
2. **Task 1 RED** - `1bd6b65` (test) — failing tests for meetsEngagementThreshold
3. **Task 1 GREEN** - `de4947a` (feat) — engagement rate filter + config/tiktok-accounts.json
4. **Task 2** - `ba7b7bf` (feat) — Postgres dedup + real dedup.test.ts

## Files Created/Modified

- `decarba-remixer/config/tiktok-accounts.json` — 13 accounts, thresholds
- `decarba-remixer/src/scraper/contentApi.ts` — shared writeToContentAPI with source param
- `decarba-remixer/src/scraper/config.ts` — loadConfig<T> JSON loader
- `decarba-remixer/vitest.config.ts` — vitest Node ESM config
- `decarba-remixer/src/scraper/tiktok.ts` — engagement rate, config loading, Postgres dedup
- `decarba-remixer/src/index.ts` — import from contentApi.ts, writeToContentAPI(ads, "ppspy")
- `decarba-remixer/package.json` — vitest devDep, test scripts
- `decarba-remixer/src/scraper/__tests__/dedup.test.ts` — real writeToContentAPI tests
- `decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts` — real meetsEngagementThreshold tests
- `decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts` — stub
- `decarba-remixer/src/scraper/__tests__/config.test.ts` — stub
- `decarba-remixer/src/scraper/__tests__/meta.test.ts` — stub
- `decarba-remixer/src/scraper/__tests__/ppspy-config.test.ts` — stub

## Decisions Made

- `ENSEMBLEDATA_TOKEN` `requireEnv` call moved from module-level to inside `scrapeTiktok()` — this allows vitest to import `tiktok.ts` in tests without the env var set (previously caused module-level crash in test env)
- File-based dedup (`scout/processed_tiktok.json`) fully removed per D-02 — Postgres `ON CONFLICT DO NOTHING` is sufficient and removes the git-committed JSON merge conflict problem
- `fetchFollowerCounts` is non-fatal: any error sets follower count to 0, which triggers the `min_reach_fallback` flat view check — scraper never crashes on follower lookup failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created 02-01 foundation files before 02-02 could execute**
- **Found during:** Pre-execution — plan depends_on: ["02-01"] but 02-01 had not been executed in any worktree
- **Issue:** `contentApi.ts`, `config.ts`, vitest infrastructure all missing — Task 1 cannot import `loadConfig` or set up test infra
- **Fix:** Created all 02-01 artifacts (vitest install, contentApi.ts, config.ts, 6 test stubs, index.ts refactor) as a prerequisite commit before starting Task 1
- **Files modified:** package.json, vitest.config.ts, contentApi.ts, config.ts, 6 test stubs, index.ts
- **Commit:** 5be7963

**2. [Rule 1 - Bug] ENSEMBLEDATA_TOKEN requireEnv moved from module level to function scope**
- **Found during:** Task 1 RED phase — vitest failed to import tiktok.ts due to module-level requireEnv("ENSEMBLEDATA_TOKEN") throwing before any test could run
- **Issue:** Plan specified `const ENSEMBLEDATA_TOKEN = requireEnv(...)` at module top level. This prevents importing tiktok.ts in tests without the env var.
- **Fix:** Moved `requireEnv("ENSEMBLEDATA_TOKEN")` call inside `scrapeTiktok()` function body
- **Files modified:** tiktok.ts
- **Verification:** All 4 tiktok-filter tests pass after fix

## Known Stubs

The following test files contain stubs (expect(true).toBe(true)) pending implementation in later plans:

- `src/scraper/__tests__/pinterest-dedup.test.ts` — Pinterest Postgres dedup (02-03)
- `src/scraper/__tests__/config.test.ts` — loadConfig real tests (02-05 or standalone)
- `src/scraper/__tests__/meta.test.ts` — Meta Ad Library scraper (02-04)
- `src/scraper/__tests__/ppspy-config.test.ts` — PPSpy config (02-05)

These stubs are intentional scaffolding — they pass now and will be replaced with real implementations in their respective plans.

## Self-Check: PASSED

Files verified:
- decarba-remixer/config/tiktok-accounts.json: FOUND
- decarba-remixer/src/scraper/contentApi.ts: FOUND
- decarba-remixer/src/scraper/config.ts: FOUND
- decarba-remixer/src/scraper/tiktok.ts: FOUND (updated)
- decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts: FOUND (4 real tests)
- decarba-remixer/src/scraper/__tests__/dedup.test.ts: FOUND (2 real tests)

Commits verified in git log:
- 5be7963: FOUND
- 1bd6b65: FOUND
- de4947a: FOUND
- ba7b7bf: FOUND

All 13 tests pass: VERIFIED

---
*Phase: 02-discovery-reliability*
*Completed: 2026-03-28*
