---
phase: "02-discovery-reliability"
plan: "02-01"
name: "Central config + Postgres dedup migration"
subsystem: "scraper"
tags: [dedup, config, tiktok, pinterest, ppspy, postgres]
dependency_graph:
  requires: ["01-04"]
  provides: ["central-scraper-config", "postgres-dedup-tiktok", "postgres-dedup-pinterest"]
  affects: ["daily-scrape.yml", "index.ts"]
tech_stack:
  added: ["src/lib/contentApi.ts"]
  patterns: ["shared content API client", "config-driven scraper settings", "Postgres ON CONFLICT dedup"]
key_files:
  created:
    - decarba-remixer/config/tiktok-accounts.json
    - decarba-remixer/config/pinterest-boards.json
    - decarba-remixer/config/meta-competitors.json
    - decarba-remixer/config/ppspy-settings.json
    - decarba-remixer/src/lib/contentApi.ts
  modified:
    - decarba-remixer/src/scraper/tiktok.ts
    - decarba-remixer/src/scraper/pinterest.ts
    - decarba-remixer/src/scraper/ppspy.ts
    - decarba-remixer/src/index.ts
    - .gitignore
    - .github/workflows/daily-scrape.yml
decisions:
  - "Central config files (one per source) replace all hardcoded account lists and thresholds"
  - "Shared contentApi.ts module used by all scrapers — no circular imports, no code duplication"
  - "TikTok and Pinterest dedup now via Postgres ON CONFLICT DO NOTHING — file-based dedup retired"
  - "scout/processed_tiktok.json removed from git tracking; daily-scrape.yml no longer stages it"
  - "meta-competitors.json created with enabled=false — actor selection deferred to plan 02-03"
metrics:
  duration: "6 min"
  completed: "2026-03-28"
  tasks: 6
  files: 11
---

# Phase 2 Plan 1: Central Config + Postgres Dedup Migration Summary

## One-liner

Externalized all scraper settings into per-source JSON config files and migrated TikTok/Pinterest dedup from file/Sheet-based tracking to Postgres ON CONFLICT via a shared contentApi.ts module.

## What Was Built

### Central Config Files (`decarba-remixer/config/`)

Four new JSON config files — one per scraping source:

- **tiktok-accounts.json**: 13 competitor TikTok accounts, viral filter thresholds (MIN_REACH=3000, MAX_AGE_DAYS=14, MAX_CAROUSELS=2)
- **pinterest-boards.json**: board URL array, max_new_pins_per_run=2
- **meta-competitors.json**: search terms placeholder (enabled=false — Apify actor TBD in plan 02-03)
- **ppspy-settings.json**: search term "decarba" externalised, max_ads_per_term=15, enabled toggle

All sources support `"enabled": false` to skip scraping without touching code.

### Shared Content API Module (`src/lib/contentApi.ts`)

Single reusable `writeToContentAPI(items, source)` function used by all scrapers. Handles:
- Env var check (non-fatal if CONTENT_API_URL/DASHBOARD_SECRET not set)
- Per-item POST to `/api/content`
- Structured logging: `source={} written={} skipped/failed={}`

Previously this logic was inlined in `index.ts` with `source` hardcoded to `"ppspy"` — now it's a typed, reusable module.

### TikTok Scraper Refactor

- Reads accounts and thresholds from `config/tiktok-accounts.json`
- Removed `getProcessedIds()`, `saveProcessedId()`, `PROCESSED_FILE` constant
- Calls `writeToContentAPI(ads, "tiktok")` after scraping
- Dedup is now handled by Postgres ON CONFLICT DO NOTHING in the content API

### Pinterest Scraper Refactor

- Reads board URL and `max_new_pins_per_run` from `config/pinterest-boards.json`
- Removed `getProcessedPinIds()` and `SHEET_CSV_URL` (Google Sheet dedup retired)
- Calls `writeToContentAPI(ads, "pinterest")` after scraping
- Supports multiple boards (iterates over `config.boards` array)

### PPSpy Scraper Refactor

- Reads search terms and `max_ads_per_term` from `config/ppspy-settings.json`
- Search term no longer hardcoded in URL constant
- Ad IDs now include search term: `ppspy_{term}_{date}_{i}`
- `buildPPSpyUrl()` helper for URL construction

### Index.ts Cleanup

- Removed 45-line inline `writeToContentAPI()` implementation
- Replaced with `import { writeToContentAPI } from "./lib/contentApi.js"`
- Call updated to `writeToContentAPI(ads, "ppspy")`

### Git Hygiene

- `scout/processed_tiktok.json` added to `.gitignore` and removed from git tracking
- `daily-scrape.yml`: removed `scout/processed_tiktok.json` from the commit step

## Verification Results

- All four config files exist with valid JSON
- `tiktok.ts`: no reference to `processed_tiktok.json` or `PROCESSED_FILE`
- `pinterest.ts`: no reference to `SHEET_CSV_URL` or `getProcessedPinIds`
- `ppspy.ts`: search URL built from config, not hardcoded constant
- `src/lib/contentApi.ts` exists and imported by index.ts, tiktok.ts, pinterest.ts
- `npm run build` (tsc --noEmit): 0 errors after installing node_modules
- `scout/processed_tiktok.json` in .gitignore

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Central config files (not env vars) for source settings | Competitor lists and thresholds are not secrets — JSON config files are the right layer; env vars reserved for API keys |
| Shared contentApi.ts module | Prevents copy-paste drift — any change to API auth or error handling applies to all scrapers at once |
| TikTok/Pinterest write to API after scraping, not before | Scrapers return results for downstream use; content API write is post-collection side effect |
| meta-competitors.json enabled=false | No Apify actor selected yet — placeholder created so config structure exists when plan 02-03 wires it |
| Postgres dedup replaces file-based dedup | ON CONFLICT DO NOTHING handles idempotency without state files that cause merge conflicts |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ContentApiItem index signature incompatible with ScrapedAd**
- **Found during:** TypeScript build verification
- **Issue:** `ContentApiItem` had `[key: string]: unknown` index signature making `ScrapedAd` (which lacks one) unassignable
- **Fix:** Removed index signature from `ContentApiItem` — all needed fields are explicitly typed
- **Files modified:** `decarba-remixer/src/lib/contentApi.ts`
- **Commit:** d55b312

## Known Stubs

None — all config values are real (matching previously hardcoded values). meta-competitors.json is intentionally `enabled=false` with a note explaining it's a placeholder for plan 02-03.

## Self-Check: PASSED

**Files verified:**
- FOUND: decarba-remixer/config/tiktok-accounts.json
- FOUND: decarba-remixer/config/pinterest-boards.json
- FOUND: decarba-remixer/config/meta-competitors.json
- FOUND: decarba-remixer/config/ppspy-settings.json
- FOUND: decarba-remixer/src/lib/contentApi.ts
- FOUND: d55b312 (type fix commit)
- FOUND: 7fe9b79 (gitignore commit)
- OK: scout/processed_tiktok.json in .gitignore
- Build: tsc --noEmit passes with 0 errors
