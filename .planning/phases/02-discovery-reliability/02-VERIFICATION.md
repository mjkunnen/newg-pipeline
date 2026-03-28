---
phase: 02-discovery-reliability
verified: 2026-03-28T05:00:00Z
status: gaps_found
score: 6/9 must-haves verified
gaps:
  - truth: "Pinterest flow checks seen-content state before acting — no old pins reprocessed (DISC-03 / SRC-02)"
    status: failed
    reason: "daily-pinterest.yml calls `pipeline/cloud_pinterest.py --max 2` at line 73, but that file was archived to archive/pipeline/cloud_pinterest.py in plan 02-05. The active pipeline/ directory contains no cloud_pinterest.py. Every scheduled run of daily-pinterest.yml will fail with FileNotFoundError before any Pinterest content is processed."
    artifacts:
      - path: ".github/workflows/daily-pinterest.yml"
        issue: "Line 73: `run: python pipeline/cloud_pinterest.py --max 2` — file does not exist in active codebase"
      - path: "pipeline/cloud_pinterest.py"
        issue: "MISSING — archived to archive/pipeline/cloud_pinterest.py in plan 02-05 Task 3, but workflow was not updated to reflect the archive"
    missing:
      - "Restore pipeline/cloud_pinterest.py from archive/pipeline/ into the active pipeline/ directory, OR update daily-pinterest.yml to call the TypeScript pinterest.ts scraper (npm run scrape:pinterest) instead of cloud_pinterest.py"
      - "If the Python remake pipeline is still needed for fal.ai processing, restore the file; if not, replace the workflow step with the TypeScript-based scraper"
  - truth: "All four content sources run automatically on schedule (phase goal)"
    status: partial
    reason: "Three sources (PPSpy, TikTok, Meta) run in daily-scrape.yml with scheduled automation. Pinterest TypeScript scraper runs in daily-scrape.yml (npm run scrape:pinterest) and writes to Postgres. However, the dedicated daily-pinterest.yml remake workflow is broken — it calls the archived cloud_pinterest.py. If the intent is that the TypeScript scraper in daily-scrape.yml counts as Pinterest automation, SRC-02 is satisfied. But the daily-pinterest.yml workflow's existence and failure means Pinterest is not reliably automated end-to-end."
    artifacts:
      - path: ".github/workflows/daily-pinterest.yml"
        issue: "References archived pipeline/cloud_pinterest.py — will fail every execution"
    missing:
      - "Determine whether daily-pinterest.yml is still needed after pinterest.ts handles discovery via daily-scrape.yml"
      - "Either fix daily-pinterest.yml or deprecate it — its current broken state causes failure alerts daily"
  - truth: "REQUIREMENTS.md accurately reflects completion status"
    status: failed
    reason: "REQUIREMENTS.md still marks DISC-03, SRC-02, and SRC-03 as [ ] (Pending) even though plans 02-02 through 02-05 have completed and implemented these requirements. The traceability table shows them as Pending at Phase 2. This is a documentation gap, not a code gap — the underlying code is implemented correctly for DISC-03 and SRC-03."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "DISC-03 line 23, SRC-02 line 37, SRC-03 line 38 all show [ ] (Pending) despite code implementation"
    missing:
      - "Update REQUIREMENTS.md to mark DISC-03 [x] (pinterest.ts uses Postgres dedup via getProcessedPinIds), SRC-03 [x] (meta.ts + daily-scrape.yml Meta step), and update traceability table status column"
      - "SRC-02 remains genuinely partial until the daily-pinterest.yml broken reference is fixed"
human_verification:
  - test: "Run daily-pinterest.yml workflow manually via workflow_dispatch"
    expected: "Workflow should either succeed (if cloud_pinterest.py is restored) or the step 'Run Pinterest remake pipeline' should be removed/replaced"
    why_human: "Cannot confirm workflow execution without triggering GitHub Actions; file existence check alone confirmed the break"
  - test: "Verify Slack webhook is configured as a GitHub Actions secret (SLACK_WEBHOOK_URL)"
    expected: "Failure alert step in both daily-scrape.yml and daily-pinterest.yml should send to real Slack channel"
    why_human: "Cannot verify GitHub Actions secrets from local filesystem"
  - test: "Verify CONTENT_API_URL and DASHBOARD_SECRET secrets are set in GitHub Actions"
    expected: "Pinterest dedup pre-fetch in daily-pinterest.yml and writeToContentAPI calls in all scrapers should reach live Railway Postgres"
    why_human: "Railway deployment and secrets are not verifiable from local filesystem"
---

# Phase 2: Discovery Reliability Verification Report

**Phase Goal:** All four content sources run automatically on schedule, each producing deduplicated, viral-filtered content written to Postgres, with structured failure alerts when any step breaks
**Verified:** 2026-03-28T05:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Content seen in a previous run never appears in a new run — seen_ids persists across GitHub Actions | VERIFIED | TikTok: writeToContentAPI + ON CONFLICT DO NOTHING in Postgres. Pinterest: getProcessedPinIds() reads /api/content?source=pinterest. PPSpy/Meta: same writeToContentAPI pattern. Dedup is Postgres-backed across all sources. |
| 2 | TikTok content reaching dashboard has engagement rate above configured threshold; low-view content from high-follower accounts filtered out | VERIFIED | meetsEngagementThreshold(playCount, followerCount, min_engagement_rate) exported from tiktok.ts line 39. fetchFollowerCounts() calls EnsembleData per account. Config-driven min_engagement_rate=0.15 in tiktok-accounts.json. Tests pass (tiktok-filter.test.ts). |
| 3 | Pinterest flow checks seen-content state before processing any pin — no old pins reprocessed even on re-run | PARTIAL | pinterest.ts implements Postgres-backed getProcessedPinIds() correctly (lines 25-48). daily-scrape.yml runs npm run scrape:pinterest. BUT daily-pinterest.yml calls pipeline/cloud_pinterest.py which is ARCHIVED — that workflow will fail every run. |
| 4 | GitHub Actions workflow failure sends structured alert within minutes — no failure goes unnoticed | VERIFIED | daily-scrape.yml line 167: `if: failure()` step sends curl POST to SLACK_WEBHOOK_URL. daily-pinterest.yml line 76: same pattern. GITHUB_STEP_SUMMARY table written per-source in daily-scrape.yml. |
| 5 | All scraping settings readable from one central config file without touching any script | VERIFIED | Four config files verified: tiktok-accounts.json (13 accounts, min_engagement_rate=0.15), pinterest-boards.json (board_url, max_new_pins), ppspy-settings.json (search_terms), meta-competitors.json (advertiser_urls). All loaded via shared loadConfig<T>() utility. |

**Score:** 4/5 truths verified (Truth 3 partial)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `decarba-remixer/config/tiktok-accounts.json` | TikTok scraper configuration | VERIFIED | 13 accounts, min_engagement_rate=0.15, min_reach_fallback=3000, max_age_days=14, max_carousels=2 |
| `decarba-remixer/config/pinterest-boards.json` | Pinterest board configuration | VERIFIED | board_url, max_new_pins=2, scroll_rounds=15, stale_rounds_limit=2 |
| `decarba-remixer/config/ppspy-settings.json` | PPSpy scraper configuration | VERIFIED | search_terms=["decarba"], enabled=true, order_by, direction |
| `decarba-remixer/config/meta-competitors.json` | Meta competitor configuration | VERIFIED | advertiser_urls (3 NL competitors: Decarba, Strhvn, FIVELEAF), max_ads_per_competitor=10 |
| `decarba-remixer/src/scraper/tiktok.ts` | TikTok scraper with Postgres dedup and engagement rate filter | VERIFIED | meetsEngagementThreshold() exported, fetchFollowerCounts(), loadConfig, writeToContentAPI(ads, "tiktok"), no PROCESSED_FILE/getProcessedIds/saveProcessedId |
| `decarba-remixer/src/scraper/pinterest.ts` | Pinterest scraper with Postgres dedup | VERIFIED | getProcessedPinIds() reads Postgres, writeToContentAPI(ads, "pinterest"), no SHEET_CSV_URL, loadConfig from pinterest-boards.json |
| `decarba-remixer/src/scraper/ppspy.ts` | PPSpy with config-driven search term | VERIFIED | buildPPSpyUrl() function, loadConfig("ppspy-settings.json"), [result] structured log. Minor: fallback `|| "decarba"` exists but primary path reads from config. |
| `decarba-remixer/src/scraper/meta.ts` | Meta Ad Library scraper using Apify actor | VERIFIED | scrapeMetaAds() and transformMetaResults() exported, ApifyClient, writeToContentAPI(ads, "meta"), loadConfig from meta-competitors.json |
| `decarba-remixer/src/scraper/contentApi.ts` | Shared content API client | VERIFIED | writeToContentAPI(ads, source) exported, handles all four sources, graceful fallback when CONTENT_API_URL not set |
| `decarba-remixer/src/lib/contentApi.ts` | Shared lib version imported by index.ts | VERIFIED | index.ts imports from "./lib/contentApi.js" — no circular imports |
| `.github/workflows/daily-scrape.yml` | All four sources with Meta step + Slack alerts | VERIFIED | scrape:ppspy, scrape:pinterest, scrape:tiktok, scrape:meta all present. GITHUB_STEP_SUMMARY table. Slack failure notification. No scout/processed_tiktok.json reference. |
| `.github/workflows/daily-pinterest.yml` | Pinterest remake with Postgres dedup check | PARTIAL | CONTENT_API_URL env, processed_pin_ids.txt pre-fetch, Slack alert — all present. FATAL: line 73 calls `python pipeline/cloud_pinterest.py --max 2` which does NOT EXIST (archived). |
| `pipeline/cloud_pinterest.py` | Pinterest remake pipeline (active) | MISSING | Archived to archive/pipeline/cloud_pinterest.py in plan 02-05 Task 3. Active pipeline/ directory has no cloud_pinterest.py. |
| `.gitignore` | scout/processed_tiktok.json excluded | VERIFIED | `scout/processed_tiktok.json` present in .gitignore |
| `archive/scout/tiktok_checker.py` | Archived legacy TikTok scraper | VERIFIED | Exists at archive/scout/tiktok_checker.py |
| `archive/scout/config.py` | Archived legacy config | VERIFIED | Exists at archive/scout/config.py |
| `archive/pipeline/cloud_pinterest.py` | Archived Pinterest remake pipeline | VERIFIED | Exists at archive/pipeline/cloud_pinterest.py — but workflow still references it in active path |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tiktok.ts` | `contentApi.ts` (scraper/) | `import { writeToContentAPI } from "./contentApi.js"` | WIRED | Line 8: import present. Line 321: writeToContentAPI(ads, "tiktok") called. |
| `tiktok.ts` | `tiktok-accounts.json` | `loadConfig("tiktok-accounts.json")` | WIRED | Line 7: import loadConfig. Line 230: loadConfig<TikTokConfig>("tiktok-accounts.json") |
| `pinterest.ts` | `contentApi.ts` | `import { writeToContentAPI } from "./contentApi.js"` | WIRED | Line 6: import. Line 205: writeToContentAPI(ads, "pinterest") |
| `pinterest.ts` | `CONTENT_API_URL/api/content?source=pinterest` | GET fetch in getProcessedPinIds() | WIRED | Lines 35-36: fetch to ${contentApiUrl}/api/content?source=pinterest&limit=1000 |
| `meta.ts` | `apify-client` | `new ApifyClient({ token })` | WIRED | Line 66: ApifyClient constructor. apify-client ^2.22.3 in package.json dependencies. |
| `meta.ts` | `contentApi.ts` | `import { writeToContentAPI } from "./contentApi.js"` | WIRED | Line 4: import. Line 86: writeToContentAPI(ads, "meta") |
| `ppspy.ts` | `ppspy-settings.json` | `loadConfig("ppspy-settings.json")` | WIRED | Line 5: import loadConfig. Line 56: loadConfig<PPSpyConfig>("ppspy-settings.json") |
| `daily-scrape.yml` | `SLACK_WEBHOOK_URL secret` | `curl POST in if: failure() step` | WIRED | Line 167-170: if: failure(), curl to secrets.SLACK_WEBHOOK_URL |
| `daily-scrape.yml` | `GITHUB_STEP_SUMMARY` | `echo >> $GITHUB_STEP_SUMMARY` | WIRED | Lines 83-143: summary table initialized and per-source rows appended |
| `daily-pinterest.yml` | `Content API GET /api/content` | `curl check before cloud_pinterest.py` | WIRED (pre-fetch only) | Lines 55-64: pre-fetch runs correctly. But the next step calls archived cloud_pinterest.py. |
| `daily-pinterest.yml` | `pipeline/cloud_pinterest.py` | `python pipeline/cloud_pinterest.py` | NOT_WIRED | File does not exist in active codebase — archived. Workflow will fail at this step. |
| `index.ts` | `lib/contentApi.ts` | `import { writeToContentAPI } from "./lib/contentApi.js"` | WIRED | Line 12: import. Line 68: writeToContentAPI(ads, "ppspy") |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `tiktok.ts` | `ads: ScrapedAd[]` | EnsembleData API via fetchFollowerCounts + carousel extraction | Yes — real API calls with follower counts and engagement filtering | FLOWING |
| `pinterest.ts` | `ads: ScrapedAd[]` | Playwright browser scrape of Pinterest board | Yes — Playwright scrapes live board, getProcessedPinIds reads Postgres | FLOWING |
| `meta.ts` | `ads: ScrapedAd[]` | Apify facebook-ads-scraper actor | Yes — actor runs against real Meta Ad Library, transformMetaResults maps output | FLOWING |
| `ppspy.ts` | `ads: ScrapedAd[]` | Playwright browser scrape of PPSpy dashboard | Yes — config-driven search term used (with "decarba" fallback) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| tiktok-filter.test.ts passes | `grep -n "meetsEngagementThreshold(45000, 300000, 0.15)" decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts` | Found at line 6 | PASS (test file substantive) |
| meta.test.ts passes | `grep -n "transformMetaResults\|skips items without adArchiveID" decarba-remixer/src/scraper/__tests__/meta.test.ts` | Found — 4 test cases present | PASS (test file substantive) |
| meta.ts compiles (in CI) | dist/scraper/meta.js | Not built locally — daily-scrape.yml runs `npm run build` before scraping | SKIP (CI-only, workflow handles build) |
| cloud_pinterest.py called by daily-pinterest.yml | `ls pipeline/cloud_pinterest.py` | File NOT FOUND — archived | FAIL |
| No processed_tiktok.json in daily-scrape.yml commit step | `grep -c "processed_tiktok" .github/workflows/daily-scrape.yml` | 0 | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| DISC-01 | 02-01, 02-02 | Seen-content tracking persists across runs | SATISFIED | Postgres ON CONFLICT DO NOTHING via writeToContentAPI in all scrapers. TikTok file-based dedup removed. Pinterest no longer reads Google Sheet CSV for dedup. |
| DISC-02 | 02-02 | TikTok filtered by engagement rate (views/followers), not flat view count | SATISFIED | meetsEngagementThreshold(playCount, followerCount, minRate) in tiktok.ts. fetchFollowerCounts() per account. Tested in tiktok-filter.test.ts. |
| DISC-03 | 02-03 | Pinterest flow checks seen-content state before acting | SATISFIED IN CODE, BLOCKED IN WORKFLOW | pinterest.ts reads Postgres via getProcessedPinIds(). daily-scrape.yml runs scrape:pinterest. BUT daily-pinterest.yml fails before reaching Pinterest due to missing cloud_pinterest.py. REQUIREMENTS.md incorrectly shows [ ] Pending. |
| DISC-04 | 02-05 | Every workflow step logs structured results and sends alert on failure | SATISFIED | [result] source=X log lines in all four scrapers. GITHUB_STEP_SUMMARY table in daily-scrape.yml. Slack failure notifications on both workflows. |
| DISC-05 | 02-01, 02-02, 02-03, 02-04, 02-05 | All scraping settings in one central config file per source | SATISFIED | Four JSON config files, all loaded via shared loadConfig<T>. No hardcoded accounts, URLs, or thresholds in scraper scripts (ppspy.ts has "decarba" as fallback only). |
| SRC-01 | 02-02 | TikTok scraping automated via GitHub Actions | SATISFIED | daily-scrape.yml runs npm run scrape:tiktok. TypeScript scraper with Postgres dedup. |
| SRC-02 | 02-03, 02-05 | Pinterest scraping automated via GitHub Actions | PARTIAL | daily-scrape.yml runs npm run scrape:pinterest (TypeScript, Postgres dedup). daily-pinterest.yml is broken — calls missing cloud_pinterest.py. REQUIREMENTS.md shows [ ] Pending (incorrect for the TypeScript path). |
| SRC-03 | 02-04, 02-05 | Meta Ad Library scraping automated via GitHub Actions | SATISFIED | meta.ts with Apify actor. npm run scrape:meta script. daily-scrape.yml "Scrape Meta Ad Library" step at line 132. REQUIREMENTS.md incorrectly shows [ ] Pending. |
| SRC-04 | 02-01, 02-05 | PPSpy scraping continues working reliably | SATISFIED | ppspy.ts reads config, buildPPSpyUrl(), structured result log. daily-scrape.yml runs npm run scrape. |

**Orphaned requirements check:** No Phase 2 requirements in REQUIREMENTS.md are unaccounted for in plans.

**REQUIREMENTS.md documentation debt:** DISC-03, SRC-02, SRC-03 are incorrectly marked Pending in REQUIREMENTS.md traceability table despite code implementation. This is a documentation gap, not a code gap (except SRC-02 which is genuinely partial due to the workflow break).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.github/workflows/daily-pinterest.yml` | 73 | `python pipeline/cloud_pinterest.py --max 2` — file does not exist | Blocker | Every scheduled run of daily-pinterest.yml fails. Pinterest remake pipeline is non-functional. |
| `decarba-remixer/src/scraper/ppspy.ts` | 131, 293 | `config.search_terms[0] \|\| "decarba"` — fallback to hardcoded value | Warning | If ppspy-settings.json is missing or search_terms is empty, scraper silently uses hardcoded search term. Should throw instead of defaulting. |
| `.planning/REQUIREMENTS.md` | 23, 37, 38, 101, 105, 106 | DISC-03, SRC-02, SRC-03 marked [ ] Pending despite implementation | Info | Misleading state tracking; operators reading REQUIREMENTS.md think these are still outstanding. |

### Human Verification Required

### 1. daily-pinterest.yml Runtime Fix

**Test:** Restore `pipeline/cloud_pinterest.py` from `archive/pipeline/cloud_pinterest.py` to `pipeline/cloud_pinterest.py`, then trigger `daily-pinterest.yml` via workflow_dispatch.
**Expected:** Workflow completes all steps including "Run Pinterest remake pipeline" and sends no Slack failure alert.
**Why human:** File restoration requires a git operation (git mv or git copy) and workflow trigger; cannot verify execution from filesystem alone.

### 2. Slack Alert Delivery

**Test:** Intentionally fail a step in daily-scrape.yml (e.g., break the npm run build step), observe whether Slack channel receives the alert.
**Expected:** Slack message with workflow name, branch, and run URL appears within 2 minutes.
**Why human:** GitHub Actions secret SLACK_WEBHOOK_URL value is not verifiable from local filesystem; only execution confirms the alert is delivered.

### 3. End-to-End Postgres Write from TikTok Scraper

**Test:** Trigger daily-scrape.yml manually. After run completes, query Railway Postgres content_items table for rows with source='tiktok' added today.
**Expected:** Rows exist with source='tiktok', content_id prefixed 'tiktok_', created_at = today.
**Why human:** Cannot query Railway Postgres from local filesystem. Requires Railway dashboard or psql access.

### 4. Meta Ad Library Apify Actor

**Test:** Run `npm run scrape:meta` with a valid APIFY_TOKEN in .env. Observe whether Apify actor completes and items are returned.
**Expected:** Actor run completes, `[result] source=meta found=N written=N` log line emitted, N > 0.
**Why human:** Requires Apify API token and actor to actually execute — cannot confirm without running against live Apify platform.

### Gaps Summary

**Two gaps block full goal achievement:**

**Gap 1 (Blocker): daily-pinterest.yml calls archived cloud_pinterest.py.**
Plan 02-05 Task 3 correctly archived `pipeline/cloud_pinterest.py` to `archive/pipeline/`. However, the `daily-pinterest.yml` workflow was not updated to remove or redirect the `python pipeline/cloud_pinterest.py --max 2` call at line 73. The Postgres dedup pre-fetch step and Slack alert step in the workflow are correctly implemented — only the Pinterest execution step is broken. This causes every scheduled Pinterest workflow run to fail at the execution step, triggering a Slack alert for a problem that the team didn't introduce in this phase but also didn't clean up.

**Root cause:** The plan called for archiving cloud_pinterest.py (Task 3) while Task 2 had modified it to add Postgres dedup — but Task 2's modification to the workflow (`run: python pipeline/cloud_pinterest.py --max 2`) was not changed to use the TypeScript scraper that already runs in daily-scrape.yml.

**Gap 2 (Documentation): REQUIREMENTS.md stale.**
DISC-03, SRC-02, SRC-03 are still marked Pending. SRC-03 (Meta) is fully satisfied. DISC-03 (Pinterest Postgres dedup) is satisfied in code. SRC-02 (Pinterest automation) is partially satisfied — the TypeScript path works but the Python remake path is broken. These should be updated to reflect actual status.

---

_Verified: 2026-03-28T05:00:00Z_
_Verifier: Claude (gsd-verifier)_
