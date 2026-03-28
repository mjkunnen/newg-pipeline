---
phase: 01-state-layer
plan: "04"
subsystem: scraper-integration
tags: [ppspy, decarba-remixer, content-api, typescript, bridge]

requires:
  - phase: 01-02
    provides: POST /api/content endpoint with Bearer auth and idempotent insert

provides:
  - writeToContentAPI() function in decarba-remixer/src/index.ts
  - PPSpy ads written to Postgres via HTTP API after every scrape run

affects:
  - Phase 02 (discovery pipeline — PPSpy path now has end-to-end write)

tech-stack:
  added: []
  patterns:
    - "Non-fatal API bridge: env var guard (CONTENT_API_URL + DASHBOARD_SECRET) before fetch — missing vars silently skip, scrape continues"
    - "Write before slice: writeToContentAPI(ads) called on full array before ads.slice(0, max_ads) — discovery record is complete, remix pipeline is bounded"
    - "Per-ad error isolation: try/catch per ad, network errors logged and counted, never propagate to abort scrape"

key-files:
  created: []
  modified:
    - decarba-remixer/src/index.ts

decisions:
  - "Typed field access over (ad as any) casts: ScrapedAd in types.ts has thumbnailUrl, adCopy, reach, daysActive, platforms as proper typed fields — no casts needed"
  - "Full array write before max_ads slice: writeToContentAPI sees all scraped ads for discovery tracking; remix pipeline still bounded by max_ads"

metrics:
  duration: "1min"
  completed_date: "2026-03-28"
  tasks_completed: 1
  files_modified: 1
---

# Phase 01 Plan 04: writeToContentAPI Bridge Summary

**One-liner:** Non-fatal HTTP bridge that POSTs all PPSpy-scraped ads to /api/content after scrapePPSpy() returns, closing the STATE-02 bridge without coupling decarba-remixer to DATABASE_URL.

## What Was Built

`writeToContentAPI(ads: ScrapedAd[])` added to `decarba-remixer/src/index.ts`, called in `main()` after `scrapePPSpy()` returns and before `ads.slice(0, settings.max_ads)`.

The function:
1. Guards on `CONTENT_API_URL` + `DASHBOARD_SECRET` — skips with a log message if either is unset
2. POSTs each ad to `${CONTENT_API_URL}/api/content` with `Authorization: Bearer ${DASHBOARD_SECRET}`
3. Maps typed `ScrapedAd` fields to the content API schema: `content_id=ad.id`, `source="ppspy"`, `creative_url`, `thumbnail_url`, `ad_copy`, `metadata_json` (reach, daysActive, platforms, type)
4. Per-ad error isolation: HTTP errors and network failures are logged and counted, never thrown — scrape pipeline always continues
5. Logs summary: `[content-api] Written: N, skipped/failed: M`

## Verification

- TypeScript compiles: `npx tsc --noEmit` exits 0
- `writeToContentAPI` appears at lines 47 (declaration) and 119 (call in main())
- Non-fatal guard present: `if (!contentApiUrl || !dashboardSecret)` with skip log
- No `DATABASE_URL`, `pg`, or `postgres` references in index.ts
- No hardcoded Railway URL — uses `CONTENT_API_URL` env var throughout
- `Authorization: Bearer ${dashboardSecret}` confirmed in headers

## Deviations from Plan

### Auto-fixed Issues

None.

### Improvements Applied

**Field name verification from types.ts:** Plan noted to use `(ad as any)` casts for `thumbnailUrl`, `adCopy`, `reach`, `daysActive`, `platforms` as a precaution. After reading `decarba-remixer/src/scraper/types.ts`, all these fields are properly typed on `ScrapedAd` — direct access used, no casts. This keeps the code type-safe.

## User Action Required

Before the Postgres write will activate in the daily-scrape GitHub Actions workflow, add these secrets to the repo:

- `CONTENT_API_URL` = `https://newg-pipeline-production.up.railway.app`
- `DASHBOARD_SECRET` = (same value already set in Railway env vars)

**Path:** GitHub repo Settings → Secrets and variables → Actions → New repository secret

Without these secrets, the daily scrape continues normally — the content write is silently skipped. No scrape failure.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 25ae866 | feat(01-04): add writeToContentAPI() to decarba-remixer index.ts |

## Known Stubs

None — `writeToContentAPI` is fully wired. The HTTP endpoint it calls (`POST /api/content`) was implemented in plan 01-02.

## Self-Check: PASSED

- FOUND: decarba-remixer/src/index.ts
- FOUND: commit 25ae866
