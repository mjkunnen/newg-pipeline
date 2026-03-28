---
phase: 00-codebase-consolidation
plan: 02
subsystem: infra
tags: [python, typescript, env-validation, startup-guards, security]

# Dependency graph
requires: []
provides:
  - Startup validation helpers (_require/requireEnv) in all active pipeline scripts
  - Hard fail on missing env vars before any API call or browser launch
  - PPSpy cookie expiry check before Playwright browser launch
  - Removed hardcoded META_PAGE_ID fallback "337283139475030" from meta.ts
affects: [pipeline, decarba-remixer, all-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_require(key) Python pattern: raises RuntimeError at module load if env var missing"
    - "requireEnv(key) TypeScript pattern: throws Error at module load if env var missing"
    - "Cookie expiry check: filter rawCookies by expirationDate < nowSec before browser launch"

key-files:
  created: []
  modified:
    - pipeline/cloud_pinterest.py
    - decarba-remixer/src/scraper/tiktok.ts
    - decarba-remixer/src/scraper/taobao.ts
    - decarba-remixer/src/converter/size-chart.ts
    - decarba-remixer/src/launcher/meta.ts
    - decarba-remixer/src/scraper/ppspy.ts

key-decisions:
  - "igAccountId left as optional (process.env) in meta.ts — used only for Instagram placements, not required for core launch flow"
  - "Removed hardcoded META_PAGE_ID fallback '337283139475030' — was masking misconfiguration, must be explicit in env"
  - "Redundant late guards removed after startup validation added — fail-fast at module load is the only guard needed"

patterns-established:
  - "Python _require(key): place after load_dotenv(), before any module-level var that uses the key"
  - "TypeScript requireEnv(key): place at module top level before const declarations"
  - "Cookie expiry check: insert between rawCookies parse and playwrightCookies map — never after browser.launch()"

requirements-completed: [CLEAN-02]

# Metrics
duration: 15min
completed: 2026-03-28
---

# Phase 00 Plan 02: Startup Validation Guards Summary

**Hard-fail startup validation added to all 6 active pipeline scripts via _require()/requireEnv() — eliminates silent || "" fallbacks and adds PPSpy cookie expiry check before browser launch**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-28T02:52:00Z
- **Completed:** 2026-03-28T03:08:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `_require()` Python helper to `pipeline/cloud_pinterest.py` — FAL_KEY and PINTEREST_APPS_SCRIPT_URL now raise RuntimeError at module load if missing
- Added `requireEnv()` TypeScript helper to all 5 decarba-remixer scraper/converter/launcher files
- Removed all `|| ""` empty-string fallbacks for secret env vars (ENSEMBLEDATA_TOKEN, APIFY_TOKEN, OXYLABS_USERNAME, OXYLABS_PASSWORD)
- Removed hardcoded META_PAGE_ID fallback `"337283139475030"` from meta.ts
- Added PPSpy cookie expiry check — throws before Playwright browser launch if any session cookies are expired
- TypeScript build passes clean (`npm run build` exits 0, no errors)

## Task Commits

1. **Task 1: Add _require() validation to pipeline/cloud_pinterest.py** - `a5a230a` (feat)
2. **Task 2: Add requireEnv() to TypeScript scrapers and fix || "" fallback patterns** - `03ef2ec` (feat)

## Files Created/Modified

- `pipeline/cloud_pinterest.py` - Added _require() helper; replaced os.getenv() calls; removed late guards
- `decarba-remixer/src/scraper/tiktok.ts` - Added requireEnv(); replaced ENSEMBLEDATA_TOKEN || ""; removed silent skip guard
- `decarba-remixer/src/scraper/taobao.ts` - Added requireEnv(); replaced APIFY_TOKEN || ""; removed mid-function guard
- `decarba-remixer/src/converter/size-chart.ts` - Added requireEnv(); replaced OXYLABS_USERNAME/PASSWORD || ""; removed skip guard
- `decarba-remixer/src/launcher/meta.ts` - Added requireEnv(); replaced hardcoded META_PAGE_ID fallback; marked igAccountId as optional
- `decarba-remixer/src/scraper/ppspy.ts` - Added requireEnv(); added expiredCookies filter block before browser launch

## Decisions Made

- `igAccountId` left as `process.env.META_INSTAGRAM_ACCOUNT_ID` (not requireEnv) — it's conditionally used only for Instagram placements and is genuinely optional
- Removed late `if (!FAL_KEY)` / `if (!ENSEMBLEDATA_TOKEN)` guards — now redundant since module-level requireEnv/\_require throws before those code paths can be reached
- Hardcoded `"337283139475030"` META_PAGE_ID removed — was a real page ID used as fallback, masking misconfiguration; must be explicit in env

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Removed redundant skip guard in size-chart.ts fetchTaobaoDescriptionImages()**
- **Found during:** Task 2
- **Issue:** After replacing OXYLABS_USER/PASS with requireEnv(), the `if (!OXYLABS_USER || !OXYLABS_PASS) return []` guard at the start of `fetchTaobaoDescriptionImages()` became dead code — module load would have already thrown
- **Fix:** Removed the redundant guard; requireEnv() at module level is the correct single enforcement point
- **Files modified:** decarba-remixer/src/converter/size-chart.ts
- **Committed in:** 03ef2ec (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical / dead code cleanup)
**Impact on plan:** Necessary for correctness — dead guard created false sense of security without providing any protection.

## Issues Encountered

- Python not available in PATH in the worktrees environment — syntax validation via `python -c "import ast..."` could not be run. File was verified by direct content review instead. Syntax is valid standard Python 3.x.

## Known Stubs

None — all validation patterns are fully wired.

## Next Phase Readiness

- All 6 active scripts now fail fast at startup with actionable error messages
- CLEAN-02 requirement satisfied
- Ready for Phase 00 Plan 03 (dependency consolidation) or next phase work

---
*Phase: 00-codebase-consolidation*
*Completed: 2026-03-28*
