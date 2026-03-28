---
phase: 04-launch-hardening
plan: "02"
subsystem: launcher
tags: [dry-run, meta-api, token-safety, github-actions, documentation]
dependency_graph:
  requires: ["04-01"]
  provides: ["dry-run launch mode", "token type check", "System User token docs"]
  affects: ["decarba-remixer/src/launcher/meta.ts", "decarba-remixer/src/launcher/fromPostgres.ts", "decarba-remixer/src/launcher/fromSheet.ts", ".github/workflows/launch-campaigns.yml"]
tech_stack:
  added: []
  patterns: ["dryRun guard at launchBatch entry point", "informational-only token check at startup", "structured JSON dry-run output"]
key_files:
  created:
    - decarba-remixer/src/launcher/__tests__/meta.test.ts
    - decarba-remixer/src/launcher/__tests__/tokenCheck.test.ts
    - docs/META_TOKEN_SETUP.md
    - archive/launch/meta_campaign.py
  modified:
    - decarba-remixer/src/launcher/meta.ts
    - decarba-remixer/src/launcher/fromPostgres.ts
    - decarba-remixer/src/launcher/fromSheet.ts
    - .github/workflows/launch-campaigns.yml
    - .gitignore
decisions:
  - "dryRun guard placed at launchBatch() entry point — gates all Meta API calls (getConfig, findOrCreateCampaign, findOrCreateAdSet, uploadCreative) without modifying each individually, per D-07"
  - "checkTokenType() is informational only — awaited but errors caught inline, never blocks launch (D-11)"
  - "Creatives downloaded in dry-run mode — validates Drive links as required by D-06"
  - "META_TOKEN_SETUP.md gitignore exception added — *_token* pattern was blocking the doc file due to case-insensitive glob on Windows"
  - "archive/launch/meta_campaign.py archived via git mv — legacy Python launcher not connected to anything, history preserved"
metrics:
  duration: "5min"
  completed_date: "2026-03-28T04:51:35Z"
  tasks_completed: 2
  files_changed: 9
---

# Phase 04 Plan 02: Dry-Run Mode + Token Safety Summary

**One-liner:** Dry-run mode via `launchBatch(inputs, true)` gates all Meta API calls and returns mock BatchResult with `dry-run-` prefixed IDs; token type check at startup warns about personal tokens; System User token docs added.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Add dryRun to meta.ts + --dry-run flag to both launchers + tests | `2d6e53a` | Done |
| 2 | Token type check + workflow dry-run input + META_TOKEN_SETUP.md | `e09cf49` | Done |

## What Was Built

### Task 1 — dryRun parameter + --dry-run flag

**`meta.ts`:** `launchBatch()` accepts optional `dryRun = false` parameter. When true, returns immediately with mock `BatchResult` (`campaignId: "dry-run-campaign"`, `adSetId: "dry-run-adset"`, ads with `dry-run-creative-{adId}` and `dry-run-ad-{adId}` IDs). All real Meta API calls (getConfig, findOrCreateCampaign, findOrCreateAdSet, uploadCreative, graphPost, graphGet) are gated after this guard.

**`fromPostgres.ts`:** `DryRunResult` interface added. Main loop collects `DryRunResult[]` entries for each item (`would_launch` for valid items, `skipped` with reason for failed downloads or missing metadata). Passes `dryRun` to `launchBatch()`. After launch, logs structured JSON summary when in dry-run mode. Skips `markLaunched()` in dry-run. Creative download still runs (validates Drive links per D-06).

**`fromSheet.ts`:** Reads `--dry-run` from `process.argv`. Logs dry-run mode active. Same `DryRunResult` tracking pattern. Passes `dryRun` to `launchBatch()`. Skips `updateSheetStatus()` calls in dry-run.

**`meta.test.ts`** (5 tests): verifies mock BatchResult structure, input length match, per-ad ID prefixes, and no fetch calls in dry-run mode.

### Task 2 — Token check, workflow, docs, archive

**`checkTokenType(token)`** (exported from fromPostgres.ts): fetches `GET /me?fields=name,id` from Meta Graph API. If name matches `/system|bot|api|automation/i` — logs confirmation. Otherwise — logs warning with reference to docs. Handles non-ok responses and network errors gracefully (never throws). Called at start of `main()` with token from env var; error caught inline so it can never block launch.

**`tokenCheck.test.ts`** (5 tests): personal name warning, system user confirmation, NEWG Bot confirmation, network failure no-throw, 401 response graceful handling.

**`launch-campaigns.yml`:** `workflow_dispatch` now has `dry_run: boolean` input (default false). Both launch steps append `-- --dry-run` when `github.event.inputs.dry_run == 'true'`. Automated `workflow_run` triggers always run live (dry_run not set = false per default).

**`docs/META_TOKEN_SETUP.md`** (50 lines): Why System User tokens, prerequisites, step-by-step creation guide (Business Manager UI), 5 required permissions, where to set the token (Railway/GitHub/local), verification curl command, token rotation instructions, troubleshooting table with 4 common errors.

**`archive/launch/meta_campaign.py`:** Moved from `launch/` via git mv — legacy Python launcher not wired to anything in the current pipeline. History preserved.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] .gitignore exception for META_TOKEN_SETUP.md**
- **Found during:** Task 2 git add
- **Issue:** Root `.gitignore` pattern `*_token*` matched `META_TOKEN_SETUP.md` case-insensitively on Windows (git on Windows uses case-insensitive glob matching), blocking the documentation file from being committed
- **Fix:** Added `!docs/META_TOKEN_SETUP.md` exception line immediately after the `*_token*` pattern in `.gitignore`
- **Files modified:** `.gitignore`
- **Commit:** `e09cf49`

## Known Stubs

None. All dry-run output paths are fully implemented and produce real structured JSON. Token check makes real API calls in production.

## Test Results

```
Test Files  9 passed (9)
Tests       32 passed (32)
Duration    399ms
```

## Self-Check: PASSED

Files verified to exist:
- decarba-remixer/src/launcher/__tests__/meta.test.ts — FOUND
- decarba-remixer/src/launcher/__tests__/tokenCheck.test.ts — FOUND
- docs/META_TOKEN_SETUP.md — FOUND
- archive/launch/meta_campaign.py — FOUND

Commits verified:
- 2d6e53a (feat 04-02 Task 1) — FOUND
- e09cf49 (feat 04-02 Task 2) — FOUND
