# Project Research Summary

**Project:** NEWGARMENTS Automated Creative Research Pipeline
**Domain:** Ad creative intelligence pipeline — scraping, filtering, dashboard, remake tracking, launch automation
**Researched:** 2026-03-27
**Confidence:** MEDIUM-HIGH

## Executive Summary

The NEWGARMENTS pipeline is not a greenfield project. The infrastructure exists: Python scrapers, TypeScript remixer, Railway FastAPI dashboard, GitHub Actions scheduling, Google Sheets integration, and active credentials for Apify, fal.ai, OpenAI, and Oxylabs. The core problem is architectural fragility — no shared state layer, no deduplication, no error visibility, and multiple versioned scripts with no canonical entrypoint. The recommended approach is hardening in phases, not replacement. The goal is to converge the two disconnected dashboards (GitHub Pages static and Railway FastAPI) into one operational hub backed by Railway Postgres, with a status-column state machine coordinating discovery through launch.

The biggest reliability risk is the combination of silent failures and Google Sheets as the state store. Silent failures mean days of broken pipeline go unnoticed while the editor assumes everything is working. Google Sheets as truth store means every re-run appends duplicates, there are no dedup guarantees, and pipeline steps cannot reliably query prior state. Both must be fixed before any new feature work. The fix is well-understood: Railway Postgres already exists, Sentry + Slack webhooks are straightforward to add, and Prefect 3.x wraps existing Python scripts without requiring a rewrite.

The secondary risk is the PPSpy/PipiAds integration. No public API has been confirmed for either tool. The current approach is Playwright browser automation against the UI — fragile by nature and likely to break silently. Phase-specific research is needed before building any reliability story on top of these sources. All other integrations (Apify for TikTok/Meta, Meta Ads API for launch, Google Drive for assets, Zapier for Shopify) have confirmed patterns.

---

## Key Findings

### Recommended Stack

The existing stack is sound and should be extended, not replaced. Python 3.11+ remains the primary pipeline language. The critical addition is Prefect 3.6.23 as a workflow orchestrator — it provides retry logic, scheduling, state management, and alerting with no separate infrastructure, and it integrates natively with GitHub Actions. Tenacity handles per-request retries with exponential backoff. HTTPX replaces any remaining `requests` usage. Redis on Railway provides O(1) deduplication with TTL-based expiry. Sentry captures all exceptions that escape pipeline tasks.

**Core technologies:**
- Prefect 3.6.23 — workflow orchestration (retries, state, alerting) — no infra, free tier sufficient
- Tenacity 9.1.4 — per-request retry with exponential backoff — fills gap below Prefect's flow-level retries
- HTTPX 0.28.1 — async HTTP client — better timeout/retry handling than requests
- Redis 7.x (Railway addon) — dedup fingerprint store — O(1) SET NX with 24h TTL
- Pydantic 2.x — stage boundary validation — catches malformed data before it reaches Sheets or DB
- Sentry SDK 2.56.0 — error tracking — free tier covers workload, full stack traces
- Apify Client 2.5.0 — managed scraping for TikTok and Meta Ad Library — handles anti-bot, proxy rotation
- gspread 6.2.1 — Google Sheets read/write — retained for Zapier trigger output, not as state store

**Do not use:** `requests` (blocking), `time.sleep()` retry loops, multiple versioned filenames, `print()` for error reporting, direct Shopify API.

### Expected Features

The editor expects a reliable pipeline that surfaces fresh, filtered, deduplicated content daily — without any manual intervention. The current pipeline fails this baseline. Every P1 feature directly addresses a confirmed broken behavior, not a new capability.

**Must have (table stakes — P1):**
- Seen-content tracking — persistent state preventing old content from resurfacing between runs
- No silent failures — every step signals success/failure; GitHub Actions failure notification on every workflow
- Crash-resilient scripts — per-item try/catch; failed items log and skip, they do not halt the pipeline
- Viral filtering that works — configurable threshold (views + engagement rate), applied inline during scrape, not post-write
- Fresh content daily — dashboard filtered by ingestion date, not content creation date
- Cross-Sheets dedup — Pinterest and TikTok flows check existing IDs before surfacing content
- Central config file — viral thresholds, competitor list, source toggles in one place, not hardcoded in scripts

**Should have (P2 — add after 5+ consecutive reliable days):**
- Per-source health indicators — dashboard shows last run time, item count, status per source
- Ingestion audit trail — append-only log of every item ingested with source, timestamp, filter outcome
- Content scoring / priority queue — views + engagement + recency score visible in dashboard
- Source attribution on cards — scraper captures source URL and attribution at ingestion time

**Defer to v2+:**
- Engagement velocity scoring — requires historical snapshots per content ID, adds storage complexity
- Remake brief auto-generation — high value, high complexity; validate editor workflow first
- Multi-source performance correlation — connecting Meta launch performance back to source content

**Anti-features to reject:** full autopilot (auto-remake without human review), AI-generated product photography, real-time streaming scraping, per-item Slack notifications, automated campaign optimization.

### Architecture Approach

The target architecture is a single shared state DB (Railway Postgres, already deployed) with a status-column state machine coordinating pipeline stages. All components read from and write to this DB — no direct component-to-component coupling. The status column in `content_items` acts as the pipeline state machine: `raw → surfaced → queued → ready_to_launch → launched → archived`. This pattern is idempotent (re-running a step only processes items in the correct status), observable (dashboard queries the same DB), and trivially debuggable. GitHub Actions handles ephemeral scrape jobs; Railway handles the always-on dashboard and DB. The two disconnected dashboards (GitHub Pages static HTML and Railway FastAPI) must be consolidated into ad-command-center. GitHub Pages becomes redundant for operational use.

**Major components:**
1. Ingestion Layer (TikTok/Apify, PPSpy/Playwright, Pinterest/Playwright) — writes deduplicated content_items to State DB
2. Filter Layer (shared/filter.py) — post-ingestion pass marking items meeting viral threshold as status="surfaced"
3. Dashboard (ad-command-center Railway FastAPI) — single operational hub: Discovery tab, Remake Queue tab, Launched Ads tab
4. Remake Tracker — status lifecycle management via dashboard API endpoints; Drive link submission
5. Launcher (launch/meta_campaign.py) — reads ready_to_launch items from DB, writes launch_id and status back
6. Ad Performance Sync (ad-command-center/sync.py) — fetches Meta insights, links performance back to source content

**Shared State DB schema:** `content_items`, `seen_ids`, `remake_items`, `pipeline_runs` — all in existing Railway Postgres.

### Critical Pitfalls

1. **Silent failures** — Scripts exit 0 with empty results due to bot detection returning HTTP 200 with skeleton DOM. Fix: result-count validation after every scrape (zero results = error), Sentry capture on every escaped exception, `if: failure()` notification step in every GitHub Actions workflow.

2. **Google Sheets as state store** — Appending without dedup creates duplicates every re-run. Scripts cannot query prior state. Concurrent writes silently corrupt. Fix: Railway Postgres as truth store; Sheets retained only as Zapier trigger output for Meta launch.

3. **Multiple versioned scripts with no canonical entrypoint** — pipiads_v1 through v4 all exist; GitHub Actions calls into an unclear version; fixes applied to wrong file. Fix: one canonical file per function, archive or delete old versions, update all workflow references simultaneously. This is a prerequisite — do this before any other fixes.

4. **Viral filter applied at wrong stage or with flat threshold** — Low-view content appears in dashboard alongside viral content, forcing manual re-filtering. Fix: filter applied inline during scrape (not post-write), engagement rate used as primary signal (views / follower count), thresholds per competitor account in config.

5. **Meta launch without dry-run mode or status check** — Re-running the launch script re-launches already-launched rows, spending budget on duplicate campaigns. Fix: check status column before acting, write "launching" atomically before API call, add `--dry-run` flag, use System User token (non-expiring) not personal access token.

---

## Implications for Roadmap

### Phase 0: Codebase Consolidation (Prerequisite)

**Rationale:** Multiple versioned scripts (pipiads_v1-v4, slideshow_data_v3-v5) mean any fix applied to Phase 1 may target the wrong file. This must be resolved first or all subsequent work is unreliable. Confirmed: Pitfall 5 and 6 must be addressed before any architecture change.

**Delivers:** One canonical entrypoint per pipeline function. All GitHub Actions workflows reference confirmed-active scripts. Startup validation block in every script (env var presence check before any work begins). requirements.txt in sync.

**Addresses:** Pitfall 5 (versioned scripts), Pitfall 6 (startup crashes), known issues #1 and #7.

**Research flag:** None needed — this is cleanup, not architecture. Standard patterns apply.

---

### Phase 1: Discovery Reliability

**Rationale:** The load-bearing primitive is seen-content tracking. Deduplication, cross-Sheets checks, audit trail, and health indicators all depend on persistent state existing. Without this, every subsequent phase builds on sand. Error signaling must be built into scrapers at this stage — it cannot be retrofitted later.

**Delivers:** Daily discovery that runs reliably with no silent failures. Deduplicated content surfaced to dashboard. Viral filtering calibrated and working. Sentry + Slack alerting on any failure. pipeline_runs table enables dashboard to show last-run status.

**Addresses:** P1 features (seen-content tracking, no silent failures, crash-resilient scripts, viral filtering, fresh content daily, cross-Sheets dedup, central config file). Pitfalls 1, 2, 3, 4, 9.

**Uses:** Prefect 3.x flow wrapping existing scraper scripts; Tenacity for per-request retry; Redis (or Railway Postgres seen_ids table) for dedup; Sentry SDK; central config/competitors.json.

**Implements:** Ingestion Layer + Filter Layer from target architecture.

**Research flag:** PPSpy/PipiAds integration needs phase-specific research. No public API confirmed. Playwright approach is fragile — assess whether CSV export, webhook trigger, or alternative data source exists before building reliability on top of it.

---

### Phase 2: Dashboard Unification

**Rationale:** With reliable ingestion producing fresh, deduplicated, filtered content, the editor needs one place to see and act on it. The two disconnected dashboards (GitHub Pages static, Railway FastAPI) produce split attention and no feedback loop. This phase consolidates them and adds structured human review actions.

**Delivers:** Single operational dashboard (ad-command-center) with three tabs: Discovery, Remake Queue, Launched Ads. Editor can queue items, submit Drive links, and see pipeline health — all in one place. GitHub Pages removed as operational interface. Per-source health indicators and ingestion audit trail added.

**Addresses:** P2 features (health indicators, audit trail, content scoring, source attribution). Architecture Breaks 1 and 2 (disconnected dashboards, Sheets as state).

**Uses:** Railway FastAPI (existing), Railway Postgres (existing), SQLAlchemy.

**Implements:** Dashboard Layer + Remake Tracker from target architecture.

**Research flag:** None — FastAPI + Railway Postgres is well-documented. Standard patterns apply.

---

### Phase 3: PPSpy/PipiAds Source Configuration

**Rationale:** Competitor set is likely wrong or stale. PPSpy integration is poorly understood (no confirmed API). Address source configuration separately from ingestion reliability — wrong competitors in a reliable pipeline is still wasted research.

**Delivers:** Confirmed-correct competitor set in config/competitors.json. PPSpy/PipiAds scraping approach validated (Playwright vs. API vs. alternative). Log line at start of each run listing monitored competitors.

**Addresses:** Pitfall 7 (competitor set wrong), known issue #4.

**Research flag:** Requires phase research — investigate whether PPSpy/PipiAds offer export APIs or webhook triggers. If not, assess Playwright session stability and add extra retry layers with manual fallback instructions in dashboard when these sources fail.

---

### Phase 4: Launch Hardening

**Rationale:** Launch automation touches real ad spend. It must not run without dry-run mode, status checks, and failure notification. Currently launches fail silently and have no re-run protection.

**Delivers:** Launch script reads from State DB (not Sheets). Status column checked atomically before API call. `--dry-run` flag available. Telegram/Slack notification on launch failure. Meta System User token (non-expiring) configured.

**Addresses:** Pitfall 8 (launch without dry-run), known issues #5 and #6. Architecture Flow 3 (Launch) fully implemented.

**Uses:** Prefect @flow with failure notification; status-column state machine; Meta Ads API v24+ (Advantage+ campaign structure).

**Research flag:** Meta Ads API v24+ Advantage+ campaign structure — legacy campaign creation API deprecated Q1 2026. Verify current required API structure before implementation.

---

### Phase 5: Competitive Intelligence Enhancements (v2)

**Rationale:** Defer until v1 reliability is proven over several weeks of consecutive successful daily runs.

**Delivers:** Engagement velocity scoring (historical snapshots per content ID), remake brief auto-generation (fal.ai / OpenAI Vision), multi-source performance correlation (Meta launch performance linked back to source content).

**Research flag:** Requires phase research for each feature — velocity scoring adds storage schema complexity, brief auto-generation requires editor workflow validation before build.

---

### Phase Ordering Rationale

- Phase 0 must precede all others — running fixes against the wrong script version compounds all problems.
- Phase 1 must precede Phase 2 — dashboard unification requires reliable data to display; a fresh unified dashboard showing stale data is worse than the status quo.
- Phase 3 (PPSpy/competitor config) can run in parallel with Phase 2 — they share no dependencies.
- Phase 4 must follow Phase 1 — launcher must read from State DB which is established in Phase 1.
- Phase 5 defers until Phase 1 reliability is demonstrated — competitive intelligence enhancements on an unreliable foundation are noise.

---

### Research Flags

Phases needing deeper research during planning:

- **Phase 1:** PPSpy/PipiAds integration — no public API confirmed; Playwright approach fragile; assess alternatives before committing to implementation approach
- **Phase 3:** Competitor set validation — PPSpy/PipiAds configuration requires understanding of actual current competitor landscape
- **Phase 4:** Meta Ads API v24+ — legacy campaign creation deprecated Q1 2026; verify Advantage+ campaign structure before writing any launch code
- **Phase 5:** All three v2 features need individual research — velocity scoring, brief auto-generation, performance correlation each have distinct unknowns

Phases with standard patterns (skip research-phase):

- **Phase 0:** Cleanup and consolidation — no research needed, apply standard git versioning patterns
- **Phase 2:** FastAPI + Railway Postgres — well-documented, established patterns, existing infrastructure

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core stack (Prefect, Tenacity, HTTPX, Sentry, Redis) verified on PyPI with live version checks. Apify actor quality varies — test before committing. gspread actively seeking new maintainers per GitHub README — monitor. |
| Features | MEDIUM | Core patterns verified via industry sources. P1 features are confirmed broken behaviors (not speculative). P2/P3 features are pattern-based. |
| Architecture | HIGH | Based on direct codebase inspection. Target architecture uses only confirmed-existing infrastructure (Railway Postgres, FastAPI, GitHub Actions). No speculative components. |
| Pitfalls | HIGH | All critical pitfalls confirmed by known issues already experienced in this project (#1-#9). Not theoretical. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **PPSpy/PipiAds API availability** — No public API confirmed for either tool. Current Playwright approach is assumed. Phase 1 and Phase 3 research must resolve this before committing to implementation. If no stable access method exists, assess whether these sources should be deprioritized or replaced with an alternative (e.g., Meta Ad Library coverage expanded, Minea API explored).

- **Meta token type in current config** — Research flagged that personal access tokens expire in 60 days. Current `META_ACCESS_TOKEN` in env may be a personal token. Verify it is a System User token before Phase 4. If not, rotate before any launch automation is touched.

- **gspread maintainership** — gspread 6.2.1 is functional but the library is seeking new maintainers. If it becomes unmaintained during this project, migration path is to google-api-python-client directly. Not urgent — monitor.

- **GitHub Actions cron reliability** — Three cron triggers per workflow is a known fragile anti-pattern. The fix (single cron + alerting) is clear. Confirm the skip-if-ran guard logic before removing redundant triggers — removing without adding alerting first leaves the pipeline blind.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection (`.github/workflows/`, `ad-command-center/`, `scout/`, `pipeline/`, `decarba-remixer/`, `launch/`) — architecture findings
- PyPI live verification — Prefect 3.6.23, Tenacity 9.1.4, HTTPX 0.28.1, gspread 6.2.1, Sentry-SDK 2.56.0, Apify-client 2.5.0, FastAPI 0.135.2, Playwright 1.58.0
- Redis deduplication SET NX + TTL pattern — redis.io/tutorials/data-deduplication-with-redis
- Known issues #1-#9 from project milestone context — all pitfalls confirmed by prior experience

### Secondary (MEDIUM confidence)

- Prefect release notes — docs.prefect.io/v3/release-notes — retry features and version confirmed
- Apify TikTok Scraper (clockworks/tiktok-scraper) and Meta Ad Scraper (whoareyouanas/meta-ad-scraper) — actors confirmed active, quality varies
- ZenML orchestration comparison — Prefect vs Dagster vs Airflow
- FreeAgent engineering: orchestration tools 2025
- Idempotent Pipelines — dev.to/alexmercedcoder + prefect.io/blog
- Meta Ads API deprecation of legacy campaign APIs (PPC.land) — v24+ Advantage+ required
- GitHub Actions secrets troubleshooting (mindfulchase.com)
- Understanding idempotency in data pipelines (Airbyte)
- Content pipeline patterns (Billo, Swipekit, BestEver)

### Tertiary (LOW confidence)

- PPSpy / PipiAds API availability — NOT confirmed, no official API docs found — needs phase research
- ai-ad-creative-strategist reference pipeline (GitHub/bitsandbrains) — illustrative only, different stack
- Segwise creative intelligence tools page — page returned CSS only, couldn't extract content

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
