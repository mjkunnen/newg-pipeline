# Phase 2: Discovery Reliability - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Automate all four content sources (PPSpy, TikTok, Pinterest, Meta Ad Library) to run on schedule via GitHub Actions, each producing deduplicated viral-filtered content written to Postgres, with structured failure alerts when any step breaks. No dashboard changes — Phase 3 handles that.

</domain>

<decisions>
## Implementation Decisions

### Dedup Strategy
- **D-01:** Use Postgres content_items table as the single dedup mechanism for all sources. The Phase 1 ON CONFLICT DO NOTHING insert handles idempotency. Before writing, each scraper POSTs to the content API — duplicates are silently absorbed. No Redis, no file-based dedup needed.
- **D-02:** Retire `scout/processed_tiktok.json` file-based dedup. TikTok scraper should POST to content API like PPSpy already does (via writeToContentAPI pattern from Phase 1). The git-committed JSON file creates merge conflicts and format incompatibilities between TS/Python scrapers.
- **D-03:** Pinterest dedup also moves to Postgres. The Google Sheet read-only dedup in pinterest.ts is partial (no write-back). POST to content API instead, same pattern as PPSpy/TikTok.

### Source Consolidation
- **D-04:** TypeScript scrapers in `decarba-remixer/src/scraper/` are canonical for PPSpy, TikTok, and Pinterest. They already run in `daily-scrape.yml`.
- **D-05:** Archive `scout/tiktok_checker.py` — it writes incompatible dedup format and uses Apify instead of EnsembleData. The canonical `tiktok.ts` (EnsembleData) is already automated and has better viral filtering.
- **D-06:** Archive `pipeline/cloud_pinterest.py` as a scraper — its fal.ai remake logic may be reused later but the scraping/dedup should go through the canonical `pinterest.ts`. The `daily-pinterest.yml` workflow stays for now (it does remakes, not just scraping) but its dedup should read from Postgres.
- **D-07:** Keep both Pinterest workflows: `daily-scrape.yml` (discovery → Postgres) and `daily-pinterest.yml` (remake pipeline). But both must check Postgres for seen-content, not the Google Sheet.

### Meta Ad Library Approach
- **D-08:** Use Apify Meta Ad Library actor for automated discovery. No Playwright — Meta actively blocks scrapers and Apify actors handle anti-bot. Research phase must identify the best Apify actor and its input schema.
- **D-09:** Add Meta Ad Library scraping as a new step in `daily-scrape.yml` or as a separate workflow. Results POST to content API like all other sources.
- **D-10:** Replace `scout/config.py` search terms (currently subscription box brands) with NEWGARMENTS competitor brands. Central config needed per DISC-05.

### Failure Alerting
- **D-11:** Enable GitHub Actions built-in failure email notifications (repository Settings → Notifications). Add `if: failure()` steps to each workflow job that post a structured summary to a Slack webhook (`SLACK_WEBHOOK_URL` secret).
- **D-12:** Each scraper step should output a structured result line: source name, items found, items new, items skipped (dedup), errors. This feeds both the job summary and the Phase 3 health dashboard.

### Central Config
- **D-13:** Create one config file per source in `decarba-remixer/config/` (e.g., `tiktok-accounts.json`, `pinterest-boards.json`, `meta-competitors.json`, `ppspy-settings.json`). Each contains competitor URLs/accounts, viral thresholds, and source-specific settings. No more hardcoded account lists in scraper code.
- **D-14:** PPSpy search term currently hardcoded as "decarba" in ppspy.ts. Move to config. Research whether multiple search terms per run are feasible.

### Claude's Discretion
- Viral filtering thresholds for TikTok (currently MIN_REACH=3000, MAX_AGE_DAYS=14) — planner can adjust based on research
- Pinterest MAX_NEW_PINS limit (currently 2) — planner decides appropriate daily volume
- Meta Ad Library competitor list — researcher identifies relevant competitors based on NEWGARMENTS' market segment
- Whether to keep triple-cron pattern (01:00, 04:00, 07:00) or simplify to single daily run with retry

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scraper Code (canonical implementations)
- `decarba-remixer/src/scraper/ppspy.ts` — PPSpy Playwright scraper, cookie-based auth, DOM selectors
- `decarba-remixer/src/scraper/tiktok.ts` — TikTok EnsembleData API scraper, carousel detection, viral filter
- `decarba-remixer/src/scraper/pinterest.ts` — Pinterest Playwright scraper, board URL, scroll-and-collect
- `decarba-remixer/src/index.ts` — Main orchestrator, writeToContentAPI() bridge pattern (lines 47-90)

### Legacy Code (to understand what exists, NOT to build on)
- `scout/tiktok_checker.py` — Python TikTok scraper (Apify), incompatible dedup format — ARCHIVE
- `pipeline/cloud_pinterest.py` — Python Pinterest scraper + fal.ai remake — remake logic may be reused
- `scout/daily_discovery.py` — Meta Ad Library prompt generator — manual workflow, not automated
- `scout/apify_collect.py` — One-shot Apify batch collector — forensic only
- `scout/ad_library_scraper.py` — Parsing library only, no actual scraping

### Config
- `decarba-remixer/config/settings.yaml` — PPSpy pipeline config (max_ads, collections)
- `decarba-remixer/config/products.yaml` — NEWGARMENTS product catalog
- `config/automation-settings.json` — Posting schedule, thresholds (mostly placeholders)
- `scout/config.py` — Subscription box config (WRONG domain — needs replacement)

### Workflows
- `.github/workflows/daily-scrape.yml` — Main scraping workflow (PPSpy + Pinterest + TikTok)
- `.github/workflows/daily-pinterest.yml` — Pinterest remake pipeline
- `.github/workflows/launch-campaigns.yml` — Meta campaign launcher (triggered by daily-scrape)

### Phase 1 Artifacts
- `ad-command-center/routes/content.py` — Content API (POST/GET/PATCH) — the target for all scraper writes
- `ad-command-center/models.py` — ContentItem model with UniqueConstraint(content_id, source)

### Dedup State Files (being retired)
- `scout/processed_tiktok.json` — Git-committed TikTok dedup file (to be replaced by Postgres)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `writeToContentAPI()` in index.ts — POST bridge to content API, already handles auth + non-fatal guard. Extend this pattern for TikTok and Pinterest scrapers.
- `scrapePPSpy()` pattern — Playwright launch → cookie inject → navigate → scroll → extract → download. Pinterest uses same pattern.
- EnsembleData API client in tiktok.ts — proven HTTP-based scraping, no browser needed
- Cookie expiry validation in ppspy.ts — good pattern to replicate for other auth-dependent scrapers

### Established Patterns
- TypeScript scrapers return typed arrays (ScrapedAd[], etc.) that feed into writeToContentAPI
- GitHub Actions triple-cron (01:00, 04:00, 07:00) with "skip if already done today" guard
- Playwright in GitHub Actions uses `npx playwright install chromium` in workflow setup
- Non-fatal scraper steps — individual source failures don't block other sources

### Integration Points
- Content API POST /api/content — all scrapers write here (PPSpy already does, TikTok/Pinterest/Meta need wiring)
- GitHub Actions secrets — new secrets needed: ENSEMBLEDATA_TOKEN (exists), SLACK_WEBHOOK_URL (new), possibly APIFY_TOKEN for Meta
- `daily-scrape.yml` orchestrates all TS scrapers sequentially — Meta Ad Library step would be added here

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Key constraint from STATE.md: "PPSpy/PipiAds: No confirmed public API. Playwright approach is fragile. Phase 2 planning must investigate CSV export, webhook trigger, or alternative before committing."

</specifics>

<deferred>
## Deferred Ideas

- **Redis dedup layer** (ORCH-02) — v2 requirement, Postgres ON CONFLICT is sufficient for v1 volumes
- **Prefect orchestration** (ORCH-01) — v2 requirement, GitHub Actions sufficient for v1
- **Slack/Discord alerts for top discoveries** (ADV-04) — v2, Phase 2 only adds failure alerts
- **Auto-scheduling launches** (ADV-05) — v2 feature

</deferred>

---

*Phase: 02-discovery-reliability*
*Context gathered: 2026-03-28*
