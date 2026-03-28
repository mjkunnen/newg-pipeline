# Roadmap: NEWGARMENTS Creative Research Pipeline

## Overview

The pipeline exists but is broken in ways that compound each other: wrong canonical scripts, no shared state, no error visibility, stale duplicated content, and a launch script that re-spends budget on already-launched rows. The journey is cleanup first, then a state layer that everything else depends on, then reliable discovery, then a unified dashboard, then hardened launch automation. Each phase delivers one verifiable capability. Nothing is built on sand.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, 3, 4): Planned milestone work
- Decimal phases (1.1, 2.1): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 0: Codebase Consolidation** - Archive all versioned scripts, establish one canonical entrypoint per function (completed 2026-03-28)
- [ ] **Phase 1: State Layer** - Deploy ad-command-center to Railway with Postgres as the shared truth store
- [x] **Phase 2: Discovery Reliability** - Automate all four sources with dedup, viral filtering, and no silent failures (completed 2026-03-28)
- [ ] **Phase 3: Dashboard Unification** - Single operational dashboard the editor trusts and acts on daily
- [ ] **Phase 4: Launch Hardening** - Safe, idempotent, dry-run-capable launch automation reading from Postgres

## Phase Details

### Phase 0: Codebase Consolidation
**Goal**: The codebase has one canonical file per pipeline function, every workflow references confirmed-active scripts, and every script validates its own prerequisites before doing any work
**Depends on**: Nothing (prerequisite)
**Requirements**: CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-04
**Success Criteria** (what must be TRUE):
  1. Running any GitHub Actions workflow invokes a single identifiable script with no ambiguity about which version is active
  2. Launching any script with missing env vars or stale credentials produces an immediate startup error before any API call is made
  3. package.json and requirements.txt match what is actually imported in active scripts (no phantom or missing deps)
  4. Directories clone/, clone_runs/, bot/, tiktok-test/ and all pipiads v1-v3 / slideshow_data v3-v4 variants are removed from the active codebase
**Plans**: 3 plans

Plans:
- [x] 00-01-PLAN.md — Archive dead directories and versioned scripts (CLEAN-01, CLEAN-04)
- [x] 00-02-PLAN.md — Add startup env var validation and PPSpy cookie expiry check (CLEAN-02)
- [x] 00-03-PLAN.md — Pin Python and Node dependencies, update .env.example (CLEAN-03)

### Phase 1: State Layer
**Goal**: Railway Postgres is live and all pipeline components can write and query a shared content_items table, with Google Sheets remaining readable as a fallback during the transition
**Depends on**: Phase 0
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04
**Success Criteria** (what must be TRUE):
  1. ad-command-center is deployed and reachable on Railway with a live Postgres connection
  2. A content_items row can be inserted with a unique content ID (PPSpy ad ID, TikTok video ID, Pinterest pin ID, Meta ad ID) and the insert is idempotent — re-inserting the same ID does not create a duplicate
  3. A content item can move through the status lifecycle (discovered → surfaced → queued → ready_to_launch → launched) via API calls, and each transition is observable in the database
  4. Existing Google Sheets data remains readable and the launcher can fall back to Sheets when querying items
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — ContentItem model + Alembic migration + pytest scaffold (STATE-01, STATE-02)
- [x] 01-02-PLAN.md — Content API routes (POST/GET/PATCH) + wire into main.py (STATE-02, STATE-03)
- [x] 01-03-PLAN.md — Fix fromSheet.ts hardcoded GOOGLE_SHEET_ID fallback (STATE-04)
- [x] 01-04-PLAN.md — decarba-remixer HTTP bridge: writeToContentAPI() after scrape (STATE-02)

### Phase 2: Discovery Reliability
**Goal**: All four content sources run automatically on schedule, each producing deduplicated, viral-filtered content written to Postgres, with structured failure alerts when any step breaks
**Depends on**: Phase 1
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04, DISC-05, SRC-01, SRC-02, SRC-03, SRC-04
**Success Criteria** (what must be TRUE):
  1. Content seen in a previous run never appears in a new run — seen_ids persists across GitHub Actions executions
  2. TikTok content reaching the dashboard has an engagement rate above the configured threshold; low-view content from high-follower accounts is filtered out before writing
  3. Pinterest flow checks seen-content state before processing any pin — no old pins are reprocessed even on re-run
  4. A GitHub Actions workflow failure sends a structured alert (email, Slack, or equivalent) within minutes — no failure goes unnoticed for more than one cycle
  5. All scraping settings (competitor URLs, viral thresholds, source on/off toggles) are readable from one central config file without touching any script
**Plans**: TBD

### Phase 3: Dashboard Unification
**Goal**: A single Railway-deployed dashboard replaces all operational interfaces, showing the editor fresh daily discoveries, their remake queue, and the health of each pipeline source
**Depends on**: Phase 1, Phase 2
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. The editor opens one URL and sees only content discovered since the last dashboard session — no duplicates, no stale items from prior runs
  2. The editor can click a content card and download or preview the original creative asset without leaving the dashboard
  3. The editor can paste a Google Drive link for a completed remake into the dashboard and the content item's status updates to queued in Postgres
  4. The dashboard shows a health panel with last-run timestamp, item count, and success/failure status for each source (TikTok, Pinterest, Meta Ad Library, PPSpy)
  5. GitHub Pages static dashboard is no longer used for operational discovery
**Plans**: 3 plans
**UI hint**: yes

Plans:
- [x] 03-01-PLAN.md — Backend: extend PATCH with drive_link + add health endpoint + tests (DASH-04, DASH-05)
- [ ] 03-02-PLAN.md — Frontend: tab navigation + content discovery cards + preview modal + remake workflow (DASH-01, DASH-02, DASH-03, DASH-04)
- [ ] 03-03-PLAN.md — Health panel frontend + retire GitHub Pages dashboard (DASH-05, DASH-01)

### Phase 4: Launch Hardening
**Goal**: The launch script reads from Postgres, checks item status atomically before calling the Meta API, supports dry-run mode, uses a non-expiring System User token, and alerts on failure
**Depends on**: Phase 1, Phase 3
**Requirements**: LAUNCH-01, LAUNCH-02, LAUNCH-03
**Success Criteria** (what must be TRUE):
  1. Re-running the launch script against the same set of items does not create duplicate Meta campaigns — already-launched items are skipped based on status column
  2. Running the launcher with --dry-run prints the full campaign payload that would be sent to Meta without making any API call or spending any budget
  3. A launch failure sends an alert and the content item's status is not advanced — the item remains in ready_to_launch state for manual retry
  4. The Meta token in use is a System User token that does not expire on a 60-day cycle
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 0 → 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Codebase Consolidation | 3/3 | Complete   | 2026-03-28 |
| 1. State Layer | 2/4 | In Progress|  |
| 2. Discovery Reliability | 1/1 | Complete   | 2026-03-28 |
| 3. Dashboard Unification | 1/3 | In Progress|  |
| 4. Launch Hardening | 0/TBD | Not started | - |
