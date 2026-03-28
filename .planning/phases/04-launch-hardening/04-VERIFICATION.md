---
phase: 04-launch-hardening
verified: 2026-03-28T05:30:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run npm run launch:postgres -- --dry-run locally with CONTENT_API_URL, DASHBOARD_SECRET, META_ACCESS_TOKEN set"
    expected: "Structured JSON dry-run output per item (would_launch/skipped), no Meta API calls, no Postgres status writes"
    why_human: "Requires real env vars and a reachable content API; can't verify without live Railway endpoint"
  - test: "Trigger launch-campaigns.yml via workflow_dispatch with dry_run=true in GitHub Actions UI"
    expected: "Launch from Postgres step appends --dry-run, Sheets fallback step also gets --dry-run if postgres_launch fails"
    why_human: "GitHub Actions expression evaluation can only be confirmed by running the workflow"
---

# Phase 04: Launch Hardening — Verification Report

**Phase Goal:** Safe, idempotent, dry-run-capable launch automation reading from Postgres, with Google Sheets fallback during transition
**Verified:** 2026-03-28T05:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Launcher reads ready_to_launch items from Postgres content API and launches via Meta | VERIFIED | `fromPostgres.ts:72` — `GET /api/content?status=ready_to_launch` with Bearer auth; calls `launchBatch()` at line 295 |
| 2 | Already-launched items are never re-launched (idempotent via status query) | VERIFIED | API filter `?status=ready_to_launch` means `launched` items are never returned; `markLaunched()` advances status on success, ensuring items exit the ready_to_launch pool |
| 3 | If content API is unreachable, workflow falls back to Google Sheets launcher | VERIFIED | `fromPostgres.ts:213` — `process.exit(1)` on fetch failure; `launch-campaigns.yml:64` — `if: steps.postgres_launch.outcome == 'failure'` triggers `npm run launch` |
| 4 | Items missing drive_link in metadata_json are skipped with a warning | VERIFIED | `fromPostgres.ts:110-115` — `extractMeta()` returns null and logs `no drive_link in metadata_json (D-05)`; skipped in main loop |
| 5 | After successful launch, item status is advanced to launched in Postgres | VERIFIED | `fromPostgres.ts:305-308` — `markLaunched(itemId)` called for each item in `launchedItemIds`; skipped in dry-run mode |
| 6 | Graph API calls use v23.0 (not expired v21.0) | VERIFIED | `meta.ts:16` — `export const GRAPH_API_VERSION = "v23.0"` |
| 7 | Running launcher with --dry-run validates inputs and logs what would be launched without calling Meta API | VERIFIED | `meta.ts:319-329` — dryRun guard returns mock BatchResult before any API call; `fromPostgres.ts:295` — `launchBatch(inputs, dryRun)` |
| 8 | Dry-run output is structured JSON per item with status would_launch or skipped | VERIFIED | `fromPostgres.ts:35-42` — `DryRunResult` interface; lines 276-283 and 250-257 populate results; `JSON.stringify(dryRunResults, null, 2)` at lines 288, 303 |
| 9 | Workflow supports manual dry-run trigger via workflow_dispatch input | VERIFIED | `launch-campaigns.yml:7-12` — `workflow_dispatch.inputs.dry_run` boolean; lines 59, 65 — appends `-- --dry-run` when true |
| 10 | Launcher startup checks whether token is a System User and warns if personal token | VERIFIED | `fromPostgres.ts:163-187` — `checkTokenType()` exported function; called at line 202 in `main()`, errors caught non-blocking |
| 11 | Documentation exists for generating a non-expiring System User token | VERIFIED | `docs/META_TOKEN_SETUP.md` — 95 lines; covers why, prerequisites, creation steps, permissions, where to set, verification, rotation, troubleshooting |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Requirement | Status | Details |
|----------|-------------|--------|---------|
| `decarba-remixer/src/launcher/fromPostgres.ts` | Plan 01 must_have | VERIFIED | 338 lines (min 80); exports `fetchReadyItems`, `extractMeta`, `markLaunched`, `checkTokenType`, `ContentItem` |
| `decarba-remixer/src/lib/driveDownload.ts` | Plan 01 must_have | VERIFIED | 57 lines; exports `downloadCreative`; imported in both `fromPostgres.ts:5` and `fromSheet.ts` |
| `decarba-remixer/src/launcher/__tests__/fromPostgres.test.ts` | Plan 01 must_have | VERIFIED | 91 lines (min 30); 5 tests: extractMeta edge cases + GRAPH_API_VERSION constant |
| `decarba-remixer/src/launcher/__tests__/meta.test.ts` | Plan 02 must_have | VERIFIED | 79 lines (min 20); tests dryRun mock structure, input length match, per-ad ID prefixes, no-fetch assertion |
| `decarba-remixer/src/launcher/__tests__/tokenCheck.test.ts` | Plan 02 must_have | VERIFIED | 86 lines (min 15); 5 tests: personal name, system user, bot name, network failure, 401 response |
| `docs/META_TOKEN_SETUP.md` | Plan 02 must_have | VERIFIED | 95 lines (min 30); sections: Why, Prerequisites, Steps, Where to Set, Verification, Rotation, Troubleshooting |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `fromPostgres.ts` | `/api/content?status=ready_to_launch` | fetch with Bearer token | WIRED | Line 72: `fetch(\`\${contentApiUrl}/api/content?status=ready_to_launch\`, { headers: { Authorization: \`Bearer \${dashboardSecret}\` } })` |
| `fromPostgres.ts` | `meta.ts` | import launchBatch | WIRED | Line 4: `import { launchBatch, type SubmissionInput } from "./meta.js"` |
| `fromPostgres.ts` | `/api/content/{id}/status` | PATCH fetch after launch | WIRED | Line 135-141: `fetch(\`\${contentApiUrl}/api/content/\${itemId}/status\`, { method: "PATCH", body: JSON.stringify({ status: "launched" }) })` |
| `.github/workflows/launch-campaigns.yml` | `npm run launch:postgres` | workflow step with continue-on-error fallback | WIRED | Line 57-61: step id `postgres_launch`, `run: npm run launch:postgres`, `continue-on-error: true` |
| `fromPostgres.ts` | `meta.ts` | dryRun parameter passed to launchBatch | WIRED | Line 295: `launchBatch(inputs, dryRun)` |
| `.github/workflows/launch-campaigns.yml` | `npm run launch:postgres -- --dry-run` | workflow_dispatch dry_run input | WIRED | Line 59: `npm run launch:postgres${{ github.event.inputs.dry_run == 'true' && ' -- --dry-run' || '' }}` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `fromPostgres.ts` | `items: ContentItem[]` | `GET /api/content?status=ready_to_launch` via fetch | Yes — queries live content API backed by Postgres | FLOWING |
| `fromPostgres.ts` | `dryRunResults: DryRunResult[]` | Built in main loop from real items | Yes — populated from actual API items | FLOWING |
| `meta.ts` dryRun=true | `BatchResult` | Mock return (dry-run guard) | Mock by design — correct for dry-run | VERIFIED by design |

### Behavioral Spot-Checks

Step 7b: SKIPPED for live Meta API calls (requires real env vars and Railway endpoint). Static checks performed via grep patterns above cover all code paths. Human verification items capture what remains.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LAUNCH-01 | Plan 01 | Launcher reads pending remakes from Postgres with Google Sheets fallback | SATISFIED | `fromPostgres.ts` reads `ready_to_launch` from content API; `launch-campaigns.yml` implements Postgres-first + Sheets-fallback pattern |
| LAUNCH-02 | Plan 02 | Dry-run mode available — test launch without publishing to Meta | SATISFIED | `--dry-run` flag in both launchers; `dryRun` parameter in `launchBatch()`; structured JSON output; workflow `workflow_dispatch` input |
| LAUNCH-03 | Plan 02 | Meta integration uses System User token (non-expiring) | SATISFIED | `checkTokenType()` warns at startup about personal tokens; `docs/META_TOKEN_SETUP.md` provides full System User token generation guide |

All 3 requirements claimed by Phase 4 are satisfied. No orphaned requirements found — REQUIREMENTS.md traceability table maps LAUNCH-01, LAUNCH-02, LAUNCH-03 exclusively to Phase 4.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

No TODOs, placeholders, empty handlers, or stub returns found in phase artifacts. The `return null` in `extractMeta()` is a correct sentinel value (caller checks and skips), not a stub.

### Human Verification Required

#### 1. Dry-run end-to-end smoke test

**Test:** With `CONTENT_API_URL`, `DASHBOARD_SECRET`, and `META_ACCESS_TOKEN` set in `.env`, run `cd decarba-remixer && npm run build && npm run launch:postgres -- --dry-run`
**Expected:** Structured JSON output per item with `would_launch` or `skipped` status; no Meta API calls; no Postgres status writes; exit code 0
**Why human:** Requires a reachable Railway content API with at least one `ready_to_launch` item in Postgres

#### 2. GitHub Actions workflow_dispatch dry-run

**Test:** Go to GitHub Actions → Launch Campaigns → Run workflow → set `dry_run = true`
**Expected:** "Launch from Postgres" step appends `-- --dry-run`; if it exits 0, "Launch from Sheets (fallback)" step is skipped; structured dry-run JSON visible in step logs
**Why human:** GitHub Actions expression `github.event.inputs.dry_run == 'true'` can only be confirmed by running the workflow in the actual GitHub context

### Gaps Summary

No gaps. All 11 observable truths verified against actual code. All 6 required artifacts exist, are substantive, and are wired. All 3 requirement IDs (LAUNCH-01, LAUNCH-02, LAUNCH-03) are satisfied. No blocker anti-patterns found. Two items routed to human verification because they require live infrastructure (Railway content API, GitHub Actions runner).

---

_Verified: 2026-03-28T05:30:00Z_
_Verifier: Claude (gsd-verifier)_
