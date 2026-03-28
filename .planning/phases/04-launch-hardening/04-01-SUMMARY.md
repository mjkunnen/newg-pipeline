---
phase: 04-launch-hardening
plan: 01
subsystem: launcher
tags: [meta-api, postgres, launcher, typescript, tdd]
dependency_graph:
  requires: []
  provides:
    - fromPostgres.ts (Postgres-driven launcher entrypoint)
    - driveDownload.ts (shared Drive download logic)
    - launch:postgres npm script
    - Graph API v23.0 fix
  affects:
    - decarba-remixer/src/launcher/meta.ts
    - decarba-remixer/src/launcher/fromSheet.ts
    - .github/workflows/launch-campaigns.yml
tech_stack:
  added:
    - driveDownload.ts extracted shared module
  patterns:
    - requireEnv() pattern for mandatory env vars
    - exit(1) on API failure triggers workflow fallback
    - exit(0) on zero items / dry-run bypasses fallback
    - ESM entry-point guard for testable main()
key_files:
  created:
    - decarba-remixer/src/launcher/fromPostgres.ts
    - decarba-remixer/src/lib/driveDownload.ts
    - decarba-remixer/src/launcher/__tests__/fromPostgres.test.ts
  modified:
    - decarba-remixer/src/launcher/meta.ts (v21.0 -> v23.0, export GRAPH_API_VERSION)
    - decarba-remixer/src/launcher/fromSheet.ts (use shared driveDownload, env APPS_SCRIPT_URL)
    - decarba-remixer/package.json (launch:postgres script, deduped test entries)
    - decarba-remixer/.env.example (CONTENT_API_URL, DASHBOARD_SECRET, APPS_SCRIPT_URL, META_PIXEL_ID, META_PAGE_ID)
    - .github/workflows/launch-campaigns.yml (Postgres-first + Sheets-fallback pattern)
decisions:
  - Graph API upgraded from expired v21.0 to v23.0 — all Meta API calls were silently failing
  - Entry-point guard pattern (import.meta.url check) used to prevent main() from firing during vitest imports
  - APPS_SCRIPT_URL moved to env var — hardcoded Apps Script URL removed from fromSheet.ts source
  - driveDownload.ts extracted as shared lib — DRY between fromSheet.ts and fromPostgres.ts
metrics:
  duration: 8min
  completed_date: "2026-03-28"
  tasks_completed: 2
  files_created: 3
  files_modified: 5
---

# Phase 4 Plan 1: Postgres Launcher + Graph API v23.0 Summary

**One-liner:** Postgres-driven ad launcher reading `ready_to_launch` from content API with Sheets fallback, Graph API upgraded from dead v21.0 to v23.0.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Graph API upgrade + driveDownload + fromPostgres.ts + tests | d015099 | meta.ts, driveDownload.ts, fromSheet.ts, fromPostgres.ts, fromPostgres.test.ts, package.json, .env.example |
| 2 | Update launch-campaigns.yml with Postgres-first fallback | 8e4d82c | launch-campaigns.yml |

## What Was Built

### fromPostgres.ts
Postgres-driven launcher that:
1. Calls `GET /api/content?status=ready_to_launch` with Bearer auth (requireEnv for both `CONTENT_API_URL` and `DASHBOARD_SECRET`)
2. For each item: parses `metadata_json`, extracts `drive_link` (skips with warning if absent — D-05), defaults `landing_page` to `https://newgarments.nl` when absent
3. Downloads creative via shared `downloadCreative()` from `lib/driveDownload.ts`
4. Calls `launchBatch()` from `meta.ts` with all valid inputs
5. On success: `PATCH /api/content/{id}/status` with `{"status": "launched"}` for each item (D-02)
6. On content API failure: `process.exit(1)` — triggers Sheets fallback in workflow (D-04)
7. On zero items: `process.exit(0)` — no fallback needed (D-04)

### driveDownload.ts
Extracted shared module from `fromSheet.ts`. Both launchers use the same Drive link conversion logic, content-type detection, and HTML-confirmation-page guard.

### Graph API fix
`GRAPH_API_VERSION` changed from `v21.0` to `v23.0` in `meta.ts`. v21.0 expired September 2025 — this was blocking all Meta API calls silently. `GRAPH_API_VERSION` exported as named export for test verification.

### Workflow pattern
```
Launch from Postgres (continue-on-error: true)
  -> success (exit 0): done, no fallback
  -> failure (exit 1, API unreachable): trigger Sheets fallback
Launch from Sheets (fallback)
  -> only runs when postgres_launch.outcome == 'failure'
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] fromPostgres.ts main() fired during vitest import**
- **Found during:** Task 1, GREEN phase
- **Issue:** When vitest imports `fromPostgres.ts` for tests, the top-level `main().catch(console.error)` ran immediately, hit `requireEnv("CONTENT_API_URL")` with no env vars set, and called `process.exit(1)`, causing an unhandled rejection in the test runner.
- **Fix:** Wrapped `main()` call with an ESM entry-point guard: `if (import.meta.url === 'file:///...process.argv[1]...' || process.argv[1]?.endsWith('fromPostgres.js'))` — runs only when the file is executed directly, not when imported.
- **Files modified:** `decarba-remixer/src/launcher/fromPostgres.ts`
- **Commit:** d015099

**2. [Rule 2 - Missing] package.json had duplicate `test` and `test:watch` entries**
- **Found during:** Task 1
- **Issue:** Duplicate script keys in package.json (test appeared twice, test:watch appeared twice). Only one of each is honored by npm.
- **Fix:** Deduplicated in the rewrite when adding `launch:postgres`.
- **Files modified:** `decarba-remixer/package.json`
- **Commit:** d015099

## Known Stubs

None. All data flows are wired:
- `fromPostgres.ts` reads real content API data
- `extractMeta` parses real `metadata_json` from content items
- `markLaunched` writes real status updates via PATCH
- `downloadCreative` downloads real Drive files
- Workflow wires real GitHub Actions secrets

## Self-Check: PASSED

Files exist:
- decarba-remixer/src/launcher/fromPostgres.ts: FOUND
- decarba-remixer/src/lib/driveDownload.ts: FOUND
- decarba-remixer/src/launcher/__tests__/fromPostgres.test.ts: FOUND
- .github/workflows/launch-campaigns.yml: FOUND (updated)

Commits exist:
- d015099: FOUND
- 8e4d82c: FOUND
