# Architecture Research

**Domain:** Automated ad creative research pipeline — scraping, human review, remake tracking, launch automation
**Researched:** 2026-03-27
**Confidence:** HIGH (based on direct codebase inspection + verified patterns)

---

## System Overview

### Current Architecture (As-Is)

The system is a set of loosely coupled scripts with no shared state layer and no coordination between steps.

```
┌─────────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS (5 workflows)               │
│  daily-scrape    daily-pinterest  daily-products  launch     │
│  (decarba-remixer/  (pipeline/         (pipeline/  (launch/  │
│   TypeScript)    cloud_pinterest.py)   products)   meta_.py) │
└────────┬────────────────┬───────────────┬────────────┬───────┘
         │                │               │            │
         ▼                ▼               ▼            ▼
   scout/output/    Google Sheets    Google Drive  Meta Ads API
   (JSON files)     (intermediary)   (assets)      (direct)
         │
         ▼
   decarba-remixer/
   docs/ (GitHub Pages)
         │
         ▼
   Dashboard (GitHub Pages static HTML)
         ‖ (separate system, no shared DB)
   ad-command-center/ (Railway FastAPI + PostgreSQL)
   — syncs from Meta API independently
```

**Key observation:** There are actually TWO separate dashboards with no data connection:
1. GitHub Pages static HTML (built from decarba-remixer scrape output)
2. Railway FastAPI dashboard (ad-command-center, syncs from Meta)

Neither knows about the other. The discovery output and the ad performance data live in silos.

---

### Target Architecture (To-Be)

One shared state layer. Each component reads from and writes to it. The pipeline flows in one direction with explicit hand-off points.

```
┌─────────────────────────────────────────────────────────────────┐
│                      INGESTION LAYER                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ TikTok Scout │ │ PPSpy/PipiAds│ │  Pinterest   │            │
│  │  (Apify/     │ │  (Playwright │ │  Board       │            │
│  │   Oxylabs)   │ │   scraper)   │ │  Scraper     │            │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
│         └────────────────┴────────────────┘                     │
│                          │                                       │
│                          ▼  writes with dedup                    │
│              ┌───────────────────────┐                          │
│              │   STATE DB (SQLite    │                          │
│              │   or Railway Postgres)│                          │
│              │  - content items      │                          │
│              │  - seen_ids (dedup)   │                          │
│              │  - remake tracking    │                          │
│              │  - launch status      │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                   FILTER LAYER                                   │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │   Viral Filter        │                          │
│              │  - views threshold    │                          │
│              │  - engagement rate    │                          │
│              │  - age/staleness gate │                          │
│              │  - duplicate gate     │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │ only fresh, viral content passes
┌──────────────────────────┼──────────────────────────────────────┐
│                  DASHBOARD LAYER                                  │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │  ad-command-center/   │                          │
│              │  (Railway FastAPI)    │                          │
│              │                       │                          │
│              │  Tab 1: Discovery     │  ← reads content items  │
│              │  Tab 2: Remake Queue  │  ← reads remake status  │
│              │  Tab 3: Launched Ads  │  ← reads Meta insights  │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │ editor acts here
┌──────────────────────────┼──────────────────────────────────────┐
│                  HUMAN REVIEW LAYER                              │
│                          │                                       │
│   Editor sees dashboard → clicks "Queue for remake"             │
│   → status in DB changes to "queued"                            │
│   Editor completes remake → pastes Google Drive link            │
│   → status changes to "ready_to_launch"                        │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                  LAUNCH LAYER                                    │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │  launch/              │                          │
│              │  meta_campaign.py     │                          │
│              │  — reads "ready_to_   │                          │
│              │    launch" items      │                          │
│              │  — writes launch_id   │                          │
│              │    back to DB         │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                    Meta Ads API
```

---

## Component Boundaries

| Component | Owns | Reads From | Writes To | Current Location |
|-----------|------|------------|-----------|-----------------|
| Ingestion — TikTok | Raw TikTok carousel data | Apify/Oxylabs APIs | State DB (content_items) | scout/ |
| Ingestion — PPSpy | Raw PPSpy competitor ad data | PPSpy via Playwright | State DB (content_items) | decarba-remixer/scraper/ |
| Ingestion — Pinterest | Raw Pinterest board data | Pinterest via Playwright | State DB (content_items) | pipeline/ |
| Filter | Filtering logic only | State DB raw items | State DB filtered_items flag | new: shared/filter.py |
| Dashboard | Display + human actions | State DB (all tables) | State DB (remake_status) | ad-command-center/ |
| Remake Tracker | Remake status lifecycle | Dashboard actions | State DB (remake_items) | new: in ad-command-center |
| Launcher | Meta campaign creation | State DB ready_to_launch | State DB (launch_id, status) | launch/ |
| Ad Performance Sync | Meta insights | Meta Ads API | State DB (snapshots) | ad-command-center/sync.py |

**Rule:** No component writes directly to another component's data. All communication goes through the State DB.

---

## Data Flow

### Flow 1: Daily Discovery

```
GitHub Actions cron (03:00 CET)
  → decarba-remixer/scraper (PPSpy + Pinterest + TikTok)
  → for each item: check seen_ids table in State DB
      → if seen: skip
      → if new: insert into content_items with source, url, metadata, raw_score
  → filter pass: mark items meeting viral threshold as status="surfaced"
  → dashboard reflects new items immediately (queries DB)
```

**Current breakage:** Scrapers write to local JSON files. Dashboard reads static HTML built from those files. No DB. No dedup. No filter. Stale content resurfaces because JSON is appended not deduplicated.

### Flow 2: Human Review → Remake Queue

```
Editor opens dashboard
  → sees Tab 1: Discovery (status="surfaced" items, sorted by score)
  → clicks "Queue" on item
  → PATCH /api/items/{id}/status body: {"status": "queued"}
  → State DB updated
  → item disappears from Tab 1, appears in Tab 2: Remake Queue
  → editor remakes content externally (own tools)
  → editor pastes Google Drive link into Tab 2 form
  → status changes to "ready_to_launch"
```

**Current breakage:** No status tracking in DB. Editor has no dashboard action that feeds back into pipeline. Remake state lives in editor's head.

### Flow 3: Launch

```
launch-campaigns workflow (manual trigger or daily)
  → reads content_items WHERE status="ready_to_launch"
  → for each: calls Meta Ads API via launch/meta_campaign.py
  → on success: writes launch_id, sets status="launched", records timestamp
  → on failure: sets status="launch_failed", records error
  → dashboard Tab 3 reflects launched ads
```

**Current breakage:** Launch reads from Google Sheets. No feedback loop to pipeline state. Failures are silent.

### Flow 4: Performance Feedback

```
ad-command-center/sync.py (APScheduler, runs every N minutes)
  → fetches Meta insights for launched ads
  → writes snapshots to State DB
  → dashboard Tab 3 shows ROAS, spend, CTR per ad
  → links ad performance back to original content source
```

This flow already mostly works — ad-command-center has it. The gap is linking performance data back to the content item that was its source.

---

## Component Build Order

Dependencies determine order. Build the layer that unblocks the next.

```
Phase 1: State DB + Ingestion reliability
  Why: Everything else depends on having a trustworthy data source.
  Build:
    1. Define State DB schema (content_items, seen_ids, remake_items, launch_items)
    2. Add SQLite (for GitHub Actions) or use existing Railway Postgres (for Railway)
    3. Rewrite ingestion scripts to write to DB with dedup
    4. Add viral filter as a post-ingestion pass
  Unblocks: Dashboard showing real, fresh, filtered data

Phase 2: Dashboard unification
  Why: Editor needs one place to see everything.
  Build:
    1. Extend ad-command-center to read from content_items table (new tab)
    2. Add status management endpoints (queue, submit drive link, etc.)
    3. Remove GitHub Pages static dashboard (it becomes redundant)
  Unblocks: Human review loop with structured feedback

Phase 3: Remake tracking
  Why: Closes the loop between discovery and launch.
  Build:
    1. Remake queue view in dashboard
    2. Drive link submission form
    3. Status lifecycle: surfaced → queued → ready_to_launch → launched → failed
  Unblocks: Launch automation reading from DB instead of Sheets

Phase 4: Launch automation reliability
  Why: Launches currently fail silently.
  Build:
    1. Rewrite launcher to read from DB
    2. Add retry logic + error status
    3. Add Telegram/Slack notification on failure (optional: webhook to .env)
  Unblocks: Closed-loop pipeline with observable state
```

---

## Where the Current Architecture Breaks

### Break 1: Two disconnected dashboards

**Problem:** GitHub Pages static HTML (discovery) and Railway FastAPI (ad performance) share no data. The editor has to check two places. They can never be linked.

**Fix:** Consolidate into ad-command-center. Kill GitHub Pages as dashboard. Use it only for public-facing outputs if needed.

### Break 2: Google Sheets as state store

**Problem:** Google Sheets has no dedup guarantees, no transactions, API rate limits, and no foreign key relationships. Re-runs append duplicate rows. Pipeline steps cannot reliably query "has this item been processed?"

**Fix:** State DB in the same Postgres instance Railway already provides for ad-command-center. Ingestion scripts write to DB directly. Google Sheets can remain as a *notification output* (e.g., Zapier triggers) but not as truth store.

**Important constraint:** Google Sheets stays in the Meta launch flow temporarily (Zapier webhook for Meta campaign creation). This is acceptable short-term — the sheet becomes a trigger for Zapier, not the state store. Zapier reads one row, fires, done.

### Break 3: Silent failures in GitHub Actions

**Problem:** Workflows have backup crons but no alerting when all attempts fail. Scripts crash midway and leave partial output that gets treated as complete.

**Fix:**
- Add `continue-on-error: false` with explicit error steps
- Add a final step in each workflow: on failure, POST to a webhook (can be a Zapier webhook or Telegram bot) with the workflow name and error
- Write failed run status back to DB so dashboard shows "last run failed"

### Break 4: No viral filter with enforced thresholds

**Problem:** All scraped content surfaces regardless of engagement. Stale content resurfaces because the scraper has no memory of what was shown before.

**Fix:**
- `seen_ids` table with (source, content_id, first_seen_date)
- Filter gate runs after ingestion: only items passing threshold get `status="surfaced"`
- TikTok threshold: >50k views at time of scrape (configurable in config/)
- Pinterest: based on repin count
- Age gate: skip items first seen >7 days ago that haven't been queued

### Break 5: Multiple script versions with no canonical entrypoint

**Problem:** pipiads_research_v1 through v4, slideshow_data_v3 through v5, clone/ and clone_runs/ directories. No clear which is active.

**Fix:** During Phase 1, establish one canonical entrypoint per function. Archive old versions. This is a cleanup task, not architecture.

---

## Shared State DB Schema

```
content_items
  id              TEXT PRIMARY KEY  (source:content_id)
  source          TEXT              (tiktok / ppspy / pinterest / meta_ad_library)
  url             TEXT
  thumbnail_url   TEXT
  raw_score       REAL              (views, repin_count, etc — source-specific)
  scraped_at      DATETIME
  status          TEXT              (raw / surfaced / queued / ready_to_launch / launched / archived)
  metadata        JSON

seen_ids
  source          TEXT
  content_id      TEXT
  first_seen      DATETIME
  PRIMARY KEY (source, content_id)

remake_items
  id              INTEGER PRIMARY KEY
  content_item_id TEXT REFERENCES content_items(id)
  drive_link      TEXT
  queued_at       DATETIME
  submitted_at    DATETIME
  launched_at     DATETIME
  launch_id       TEXT              (Meta campaign/ad ID)
  launch_error    TEXT

pipeline_runs
  id              INTEGER PRIMARY KEY
  workflow        TEXT              (daily-scrape / daily-pinterest / etc)
  started_at      DATETIME
  finished_at     DATETIME
  status          TEXT              (running / success / failed)
  items_scraped   INTEGER
  items_new       INTEGER
  error           TEXT
```

---

## Keep or Replace: GitHub Actions + Railway

**Decision: Keep both. Fix the coupling between them.**

| Component | Keep? | Reason |
|-----------|-------|--------|
| GitHub Actions (cron scraping) | Yes | Free, already works for scheduled jobs, good enough for daily scrapes. Failure rate is acceptable if alerts exist. |
| GitHub Actions (launch-campaigns) | Yes | Manual trigger for human-controlled launches is appropriate. |
| GitHub Actions (deploy-pages) | Reduce scope | Keep for any public-facing assets but stop using it as the primary discovery dashboard. |
| Railway (ad-command-center) | Yes, expand | Already has Postgres, FastAPI, APScheduler. This becomes the single operational hub. |
| Railway Cron Jobs | No | GitHub Actions covers this well enough. Railway cron adds no benefit for this use case. |
| Google Sheets as state | Replace with DB | Keep as Zapier trigger output only. |
| Google Drive for assets | Keep | No reason to change. Editor workflow stays the same. |

**Why not move scraping to Railway:** GitHub Actions runners are ephemeral and free. Scraping tasks are stateless and short-lived. Railway is better suited for the always-on dashboard + DB. Keep them separate by concern.

---

## Orchestration Pattern: Shared DB, Not Message Queue

At this scale (one brand, daily batch, one editor), a message queue (Redis, RabbitMQ, Celery) is overkill and adds operational surface area. The right pattern is:

**Status-column orchestration:** Each pipeline step reads items in a specific status and advances them to the next. The status column in `content_items` is the pipeline state machine. This pattern is:
- Simple to debug (query DB to see state)
- Idempotent (re-running a step only processes items in the right status)
- Observable (dashboard queries the same DB)

This is the same pattern used by job queues like Faktory and Solid Queue — just without the message broker.

---

## Integration Points

### External Services

| Service | Integration Pattern | Current | Target |
|---------|---------------------|---------|--------|
| Apify | REST API, APIFY_TOKEN env var | scout/apify_collect.py | Same, write to DB |
| Oxylabs | HTTP proxy, OXYLABS_USERNAME/PASSWORD | scout/ various | Same, proxy config stays |
| PPSpy | Playwright session + cookies | decarba-remixer/scraper/ | Same, write to DB |
| Pinterest | Playwright scrape | pipeline/cloud_pinterest.py | Same, write to DB |
| fal.ai | REST API, FAL_KEY | decarba-remixer/remixer/ | Unchanged |
| Meta Ads API | REST, META_ACCESS_TOKEN | launch/ + ad-command-center/ | Unchanged |
| Google Sheets | gspread / Apps Script webhook | intermediary state store | Zapier trigger only |
| Google Drive | Drive API | asset delivery | Unchanged |
| Zapier | Webhook, ZAPIER_WEBHOOK_URL | Meta launch trigger | Keep for Shopify |
| Railway Postgres | SQLAlchemy, DATABASE_URL | ad-command-center only | Shared state DB |

### Internal Boundaries

| Boundary | Communication | Rule |
|----------|---------------|------|
| GitHub Actions → State DB | Direct DB write (psycopg2 / SQLAlchemy) | Actions scripts must connect to Railway Postgres via DATABASE_URL secret |
| ad-command-center → content_items | SQLAlchemy query | Dashboard reads same DB ingestion writes to |
| launch/ → State DB | Read ready_to_launch, write back launch result | Replaces Google Sheets read |
| Editor → Dashboard | HTTP PATCH endpoints | Status transitions happen only via dashboard API |

---

## Scaling Considerations

This system runs for one brand with one creative editor. Scaling is not a concern. What matters is:

| Concern | At current scale | What breaks first |
|---------|-----------------|-------------------|
| DB size | SQLite viable, Postgres better (already on Railway) | Irrelevant — use Railway Postgres |
| Scrape volume | 50-200 items/day across sources | No concern |
| API rate limits | Meta API is the most restrictive | Backoff already needed in sync.py |
| Dashboard latency | Single-user tool | No concern |

---

## Anti-Patterns

### Anti-Pattern 1: Treating Google Sheets as a database

**What's happening:** Google Sheets is the intermediary between scraping and launching. Scripts append rows, other scripts read rows. No dedup, no transactions, no foreign keys.

**Why it breaks:** Every re-run appends. Old content resurfaces. Scripts don't know if they've processed an item. API has rate limits. Concurrent writes silently corrupt.

**Do this instead:** Railway Postgres via SQLAlchemy. Already deployed. Content items get an ID. Status column replaces the "check sheet" pattern.

### Anti-Pattern 2: Using GitHub Pages as the operational dashboard

**What's happening:** The primary editor-facing view is a static HTML file committed to git and deployed via Pages.

**Why it breaks:** The editor cannot take actions (queue, submit drive link). The dashboard cannot be updated in real-time. It requires a commit+deploy cycle to refresh.

**Do this instead:** All editor interactions go through ad-command-center (Railway FastAPI). Static Pages can serve as public-facing outputs if needed but not as the operational tool.

### Anti-Pattern 3: Three separate cron schedules per workflow for reliability

**What's happening:** daily-scrape.yml has three cron triggers (03:00, 06:00, 09:00 CET) as "backups."

**Why it's fragile:** GitHub Actions cron reliability issues are real during high-load periods, but three triggers with a git-log "skip if ran" guard means three runs compete. If the skip guard fails (e.g., git log takes too long), all three run. The real problem is no alerting when scraping fails — not that it needs more triggers.

**Do this instead:** Keep one cron. Add `workflow_dispatch` for manual retry. Add a final failure step that POSTs to a webhook. Remove the three-cron pattern after adding alerting.

### Anti-Pattern 4: Multiple versioned scripts without a canonical entrypoint

**What's happening:** pipiads_research_v1 through v4 all exist. `daily-scrape.yml` calls into decarba-remixer which calls v-something. It's unclear which is the live path.

**Why it breaks:** Future changes go to the wrong file. Debugging is slowed. New sessions (human or AI) can't identify the live code path.

**Do this instead:** One entrypoint per function. Archive old versions. The pipeline_runs table makes it observable which entrypoint ran.

---

## Sources

- Direct codebase inspection: `.github/workflows/`, `ad-command-center/`, `scout/`, `pipeline/`, `decarba-remixer/`, `launch/`
- [Idempotent Pipelines: Build Once, Run Safely Forever](https://dev.to/alexmercedcoder/idempotent-pipelines-build-once-run-safely-forever-2o2o) — MEDIUM confidence
- [Understanding Idempotency in Data Pipelines (Airbyte)](https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines) — MEDIUM confidence
- [Railway Cron Jobs Docs](https://docs.railway.com/cron-jobs) — HIGH confidence
- [GitHub Actions Scheduled Workflows](https://oneuptime.com/blog/post/2025-12-20-scheduled-workflows-cron-github-actions/view) — MEDIUM confidence
- [ai-ad-creative-strategist reference pipeline](https://github.com/bitsandbrains/ai-ad-creative-strategist) — LOW confidence (illustrative only, different stack)

---

*Architecture research for: NEWGARMENTS ad creative research pipeline*
*Researched: 2026-03-27*
