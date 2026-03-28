---
phase: 00-codebase-consolidation
plan: 03
subsystem: dependencies
tags: [python, nodejs, dependencies, secrets, env]
requires: []
provides: [pinned-requirements-txt, pinned-package-json, complete-env-example]
affects: [pipeline, decarba-remixer, github-actions]
tech_stack_added: [playwright==1.58.0, pytest==9.0.2]
tech_stack_patterns: [exact-version-pinning, lock-file-consistency]
key_files_created: []
key_files_modified:
  - requirements.txt
  - decarba-remixer/package.json
  - .env.example
decisions:
  - "Pin package.json versions to lock file actuals (not RESEARCH.md suggestions) to ensure npm ci consistency"
duration_minutes: 8
completed_date: 2026-03-28
---

# Phase 00 Plan 03: Dependency Pinning and Secret Inventory Summary

**One-liner:** Pinned all Python and Node deps to exact versions matching their lock files and documented all 21 GitHub Actions secrets in .env.example.

## What Was Built

- `requirements.txt` — 6 existing packages pinned with exact `==` versions, playwright==1.58.0 and pytest==9.0.2 added (8 packages total, no `>=` ranges)
- `decarba-remixer/package.json` — all 9 `^` ranges replaced with exact versions sourced from package-lock.json
- `.env.example` — 6 missing secrets added (META_PAGE_ID, META_INSTAGRAM_ACCOUNT_ID, PPSPY_COOKIES_JSON, ENSEMBLEDATA_TOKEN, PINTEREST_APPS_SCRIPT_URL, MAKE_WEBHOOK_URL); total now 21 entries

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pin Python dependencies and add playwright | 78a90aa | requirements.txt |
| 2 | Pin package.json and update .env.example | 9f7c604 | decarba-remixer/package.json, .env.example |

## Verification Results

- `grep ">=" requirements.txt` — 0 lines (PASS)
- `grep "playwright==" requirements.txt` — 1 line (PASS)
- `grep "pytest==" requirements.txt` — 1 line (PASS)
- `pip install -r requirements.txt --dry-run` — exits 0 (PASS)
- `grep '"^' decarba-remixer/package.json` — 0 lines (PASS)
- `npm ci --dry-run` — exits 0 (PASS)
- `grep -c "^[A-Z].*=" .env.example` — 21 (PASS, expected 21+)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] package.json versions aligned to lock file actuals, not RESEARCH.md suggestions**

- **Found during:** Task 2 verification (npm ci --dry-run failed with ETARGET for typescript@5.8.0)
- **Issue:** RESEARCH.md listed typescript@5.8.0 but package-lock.json resolved `^5.8.0` to 5.9.3 (and similar mismatches for cheerio, dotenv, openai, yaml, @types/node). Pinning to RESEARCH.md versions breaks `npm ci` which requires consistency with the lock file.
- **Fix:** Used `node -e` to extract actual resolved versions from package-lock.json and pinned those instead.
- **Files modified:** decarba-remixer/package.json
- **Commit:** 9f7c604

## Known Stubs

None.

## Self-Check: PASSED
