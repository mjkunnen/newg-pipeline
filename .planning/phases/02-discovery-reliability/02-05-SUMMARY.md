---
phase: 02-discovery-reliability
plan: 05
subsystem: infra
tags: [github-actions, ppspy, playwright, slack, postgres, dedup, archival]

# Dependency graph
requires:
  - phase: 02-02
    provides: contentApi.ts generalized writeToContentAPI with source parameter
  - phase: 02-03
    provides: TikTok Postgres dedup via ON CONFLICT DO NOTHING
  - phase: 02-04
    provides: Meta Ad Library scraper (scrape:meta command)

provides:
  - PPSpy config externalized to ppspy-settings.json, read via shared loadConfig<T>
  - All workflow scraper steps emit [result] source=X structured log lines
  - daily-scrape.yml has GITHUB_STEP_SUMMARY table with per-source metrics
  - daily-scrape.yml has Meta Ad Library step (npm run scrape:meta)
  - Slack failure notifications on both daily-scrape.yml and daily-pinterest.yml
  - daily-pinterest.yml fetches Postgres pin IDs before running remake pipeline (D-07)
  - cloud_pinterest.py merged into archive with Postgres dedup logic included
  - scout/tiktok_checker.py, pipeline/cloud_pinterest.py, scout/config.py archived

affects:
  - 02-discovery-reliability verification
  - any phase that triggers GitHub Actions workflows

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "[result] source=X found=N written=N skipped=N errors=N structured log line parsed by workflow into GITHUB_STEP_SUMMARY"
    - "Slack webhook failure notification pattern: if: failure() + secrets.SLACK_WEBHOOK_URL guard"
    - "Postgres dedup pre-fetch: curl content API → write IDs to /tmp/processed_pin_ids.txt → pass via PROCESSED_PINS_FILE env var"

key-files:
  created:
    - decarba-remixer/config/ppspy-settings.json (already existed, unchanged structure confirmed)
  modified:
    - decarba-remixer/src/scraper/ppspy.ts (use shared loadConfig<T>, add [result] log line)
    - decarba-remixer/src/scraper/__tests__/ppspy-config.test.ts (real config test replacing placeholder)
    - .github/workflows/daily-scrape.yml (Meta step, structured logging, Slack alert, fix commit step)
    - .github/workflows/daily-pinterest.yml (Postgres dedup pre-fetch, Slack alert, CONTENT_API_URL env)
    - archive/pipeline/cloud_pinterest.py (archived with Postgres dedup logic added before move)
    - archive/scout/tiktok_checker.py (archived per D-05)
    - archive/scout/config.py (archived per D-10)

key-decisions:
  - "PPSpy inline async loadConfig replaced with shared sync loadConfig<T> from config.ts — consistent with all other scrapers"
  - "cloud_pinterest.py archived after adding Postgres dedup — archive preserves final state including D-07 logic"
  - "Postgres dedup is primary source, Google Sheet CSV is fallback — merged set prevents re-processing pins in either store"

patterns-established:
  - "Structured result line pattern: [result] source=X found=N written=N skipped=N errors=N — all scrapers should emit this"
  - "Slack alert pattern: if: failure() step at job end, guard with -n check on secret"
  - "Workflow Postgres dedup: fetch IDs via curl → file → env var → Python reads file"

requirements-completed: [SRC-04, DISC-04, DISC-05]

# Metrics
duration: 5min
completed: 2026-03-28
---

# Phase 02 Plan 05: Pipeline Hardening + Archival Summary

**PPSpy config externalized via shared loadConfig, all four scraping sources in daily-scrape.yml with GITHUB_STEP_SUMMARY structured output and Slack failure alerts, Pinterest workflow gets Postgres dedup pre-fetch, legacy Python scrapers archived**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-28T03:40:00Z
- **Completed:** 2026-03-28T03:44:36Z
- **Tasks:** 3 completed
- **Files modified:** 7

## Accomplishments

- PPSpy scraper now uses shared `loadConfig<T>` from config.ts instead of its own inline async version; emits `[result] source=ppspy` for workflow parsing
- daily-scrape.yml: all four scrapers (PPSpy, Pinterest, TikTok, Meta) wrapped with structured output parsing → GITHUB_STEP_SUMMARY table; `scout/processed_tiktok.json` removed from commit step; Slack alert on failure
- daily-pinterest.yml: Postgres pre-fetch step downloads already-processed pin IDs via content API, passes to `cloud_pinterest.py` via `PROCESSED_PINS_FILE`; Slack alert added
- `cloud_pinterest.py` updated to merge Postgres + Sheet IDs before archiving; `scout/tiktok_checker.py` and `scout/config.py` also archived

## Task Commits

1. **Task 1: Externalize PPSpy config + structured output** - `2486290` (feat)
2. **Task 2: Workflows — Meta step, logging, Slack, Pinterest Postgres dedup** - `20a27ed` (feat)
3. **Task 3: Archive legacy scripts** - `8c54434` (chore)

## Files Created/Modified

- `decarba-remixer/src/scraper/ppspy.ts` - uses shared loadConfig<T>, adds [result] structured log
- `decarba-remixer/src/scraper/__tests__/ppspy-config.test.ts` - real config loading test
- `.github/workflows/daily-scrape.yml` - Meta step, GITHUB_STEP_SUMMARY, Slack, fixed commit step
- `.github/workflows/daily-pinterest.yml` - Postgres dedup pre-fetch, Slack, CONTENT_API_URL env
- `archive/pipeline/cloud_pinterest.py` - archived with merged Postgres+Sheet dedup logic
- `archive/scout/tiktok_checker.py` - archived per D-05
- `archive/scout/config.py` - archived per D-10

## Decisions Made

- Used shared sync `loadConfig<T>` rather than keeping async version in ppspy.ts — consistent with all other scrapers that already use the shared version
- Added Postgres dedup logic to `cloud_pinterest.py` before archiving it — the archive preserves the final state of the file including D-07 changes
- Postgres pin IDs are primary dedup source; Google Sheet CSV is merged as fallback — both sets unioned before filtering new pins

## Deviations from Plan

None - plan executed exactly as written. The ppspy.ts already had `buildPPSpyUrl()` and the config file already existed from a previous agent's work; the plan changes (switching to shared loadConfig, adding [result] log line) were applied cleanly on top.

## Issues Encountered

None.

## User Setup Required

**External service requires manual configuration.** Add this GitHub Actions secret to both repositories:

- `SLACK_WEBHOOK_URL` — Slack App → Incoming Webhooks → Create new webhook → Copy URL → repo Settings → Secrets → New repository secret → name: `SLACK_WEBHOOK_URL`

Without this secret, the Slack notification steps will silently skip (guarded by `if [ -n "${{ secrets.SLACK_WEBHOOK_URL }}" ]`). All other workflow functionality is unaffected.

## Next Phase Readiness

- All four scraping sources (PPSpy, TikTok, Pinterest, Meta) are wired into daily-scrape.yml with structured output and failure visibility
- Dashboard editor can see per-source stats in GitHub Actions job summary after each run
- Postgres dedup is active for Pinterest; daily-scrape.yml no longer references retired file-based dedup
- Legacy Python scrapers archived; canonical TypeScript scrapers are the only active implementations
- Phase 02 verification can now confirm all discovery sources run daily with observable output

---
*Phase: 02-discovery-reliability*
*Completed: 2026-03-28*
