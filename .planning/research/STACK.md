# Stack Research

**Domain:** Automated competitive ad research pipeline — scraping, filtering, dashboard, remake-to-launch
**Researched:** 2026-03-27
**Confidence:** MEDIUM-HIGH (core stack HIGH, PPSpy/PipiAds integration LOW — no public API confirmed)

---

## Context: What the System Already Has

The existing system is a patchwork that must be hardened, not replaced wholesale:

- Python scrapers (`scout/`, `pipeline/`) — keep Python, extend it
- TypeScript (`decarba-remixer/`) — keep as-is, it's isolated
- Railway dashboard (`ad-command-center/`) — keep Railway hosting
- GitHub Actions (5 workflows) — keep as scheduler/trigger layer
- Google Sheets integration — keep as the human-facing data layer
- `fal.ai`, `OPENAI_API_KEY`, `APIFY_TOKEN` already in env

The reliability problem is not about replacing the stack. It is about adding:
1. Orchestration with proper retry/state/alerting (currently missing)
2. Deduplication (currently missing — old content resurfaces)
3. Error visibility (currently silent failures)
4. Consistent data contracts between stages (currently fragile hand-offs)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ | Primary pipeline language | Already in use; 3.11 is stable LTS with best async perf before 3.12 GIL changes |
| Prefect | 3.6.23 | Workflow orchestration — retry logic, scheduling, state management, alerting | Pythonic API, no separate infra needed, free cloud tier works for this scale, native GitHub Actions integration, strongest retry story of all orchestrators |
| Tenacity | 9.1.4 | Per-request retry logic with exponential backoff | Best-in-class decorator approach; works with async/httpx; fills the gap below Prefect's flow-level retries |
| HTTPX | 0.28.1 | Async HTTP client for all external API calls | Native async support, better timeout handling than requests, works cleanly with tenacity |
| Apify Client (Python) | 2.5.0 | Managed scraping for TikTok, Meta Ad Library, Pinterest | Proven actors exist for all three sources; handles anti-bot, proxy rotation, rate limits; far cheaper than maintaining custom scraper infra |
| FastAPI | 0.135.2 | Dashboard API layer on Railway | Already the standard for Railway Python deploys; adds typed endpoints to replace fragile ad-hoc scripts |
| gspread | 6.2.1 | Google Sheets read/write | Established library, Google Sheets API v4 under the hood; 300 req/min is sufficient for this scale |
| Sentry SDK | 2.56.0 | Error tracking and alerting | Free tier covers this workload; captures Python exceptions with full stack trace; integrates with GitHub Actions |
| Redis (Railway addon) | 7.x | Deduplication fingerprint store | O(1) content-hash lookups; 24h TTL prevents stale content from resurfacing; Railway has a managed Redis addon |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.x | Env var loading in local dev | All scripts — enforces `.env` pattern, never hardcode |
| Playwright (Python) | 1.58.0 | Browser automation fallback for sites that block httpx | PPSpy export pages if no API exists; last resort — prefer Apify actors |
| slack-sdk | 3.x | Slack webhook notifications | Pipeline failure alerts via `SLACK_WEBHOOK_URL` env var |
| pydantic | 2.x | Data validation between pipeline stages | Validate scraped records before writing to Sheets or Redis; catches malformed data at stage boundaries |
| pytest | 8.x | Unit + integration tests | Test viral filter logic, dedup logic, Sheets write contracts |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub Actions | Cron scheduling + trigger layer | Keep all 5 workflows; use `workflow_dispatch` for manual re-runs; add `on: failure` Slack notification step to every workflow |
| Railway | Dashboard hosting + Redis addon | Keep existing deploy; add Redis service for dedup store |
| Prefect Cloud (free tier) | Flow run dashboard, retry visibility | No infra to manage; free tier is 3 users, unlimited runs with limits; sufficient for this project |
| pre-commit | Secret scanning on commits | Already configured per CLAUDE.md; enforce it |

---

## Installation

```bash
# Core orchestration + HTTP
pip install prefect==3.6.23 tenacity==9.1.4 httpx==0.28.1

# Data layer
pip install gspread==6.2.1 pydantic==2.* redis

# Scraping
pip install apify-client==2.5.0 playwright==1.58.0
playwright install chromium  # only if browser fallback needed

# Monitoring
pip install sentry-sdk==2.56.0 slack-sdk python-dotenv

# Testing
pip install pytest pytest-asyncio
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Prefect 3.x | Dagster | Dagster is asset-centric and adds significant overhead for a pipeline that doesn't have dbt/data warehouse; overkill here |
| Prefect 3.x | Airflow | Airflow requires its own server (Celery/Kubernetes executor); too heavy for a Railway-based pipeline that already uses GitHub Actions |
| Prefect 3.x | Celery | Celery is a task queue, not a workflow orchestrator — no built-in retry visibility, scheduling, or state tracking across multi-step flows |
| Apify | Custom Playwright/Selenium scrapers | TikTok and Meta actively block scrapers; maintaining anti-bot measures is a full-time job; Apify actors are maintained by the community and updated when sites change |
| Redis (Railway) | SQLite dedup table | SQLite works for single-process; Redis is better for dedup because TTL-based expiry (24h) is native and atomic SET NX prevents race conditions |
| Sentry | Datadog / New Relic | Datadog/NR are enterprise-priced; Sentry free tier covers 5k errors/month which is enough; already integrates with GitHub Actions |
| Pydantic v2 | Marshmallow / manual dicts | Pydantic v2 is 5-50x faster than v1/Marshmallow; stage boundary validation prevents silent data corruption |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `requests` (sync) | Blocking; poor timeout/retry handling; no native async | `httpx` with `tenacity` |
| Custom TikTok/Meta scrapers from scratch | Anti-bot changes break them constantly; no maintenance guarantee | Apify actors (clockworks/tiktok-scraper, whoareyouanas/meta-ad-scraper) |
| `time.sleep()` retry loops | No backoff, no jitter, swallows exceptions | `tenacity` with `wait_exponential` + `stop_after_attempt` |
| Hardcoded API keys / fallback defaults | Security violation per project CLAUDE.md | `os.getenv("KEY")` — raise if None, never default to real value |
| Multiple script versions (v1-v4 pattern) | Creates confusion about which is canonical; old versions get run accidentally | Single canonical script per function; use git tags for versioning |
| `print()` for error reporting | Silent in production; not queryable | `logging` module + Sentry capture; every pipeline error should be a Sentry event |
| Direct Shopify API | Explicitly out of scope per PROJECT.md | Zapier webhook (`ZAPIER_WEBHOOK_URL`) only |
| AI-generated product photography | Proven to fail for product shots per PROJECT.md | fal.ai extraction/segmentation only |

---

## Stack Patterns by Phase

**For discovery reliability (Phase 1 priority):**
- Wrap every Apify actor call in a Prefect `@task` with `retries=3, retry_delay_seconds=60`
- Use Redis SET NX with 24h TTL as the dedup gate before writing to Sheets
- Use Sentry to capture any exception that escapes a task
- GitHub Actions cron triggers Prefect flow; Prefect manages retries internally

**For dashboard freshness:**
- FastAPI endpoint reads from a Postgres/Sheets staging table that is only written to after dedup passes
- Dashboard should show `last_updated` timestamp so the editor knows if a run failed
- Stale data is worse than no data — use Redis TTL to expire content after 48h

**For PPSpy / PipiAds (LOW confidence — needs phase research):**
- No public API confirmed for either tool
- Current approach is likely Playwright browser automation against the UI
- Treat these as brittle — wrap in extra retry layers and add manual fallback instructions in the dashboard when they fail
- Research needed: do PPSpy/PipiAds offer CSV export APIs or webhook triggers?

**For the remake-to-launch flow:**
- Google Drive link → dashboard → Sheets is the correct pattern (human review required)
- Meta Ads launcher (`launch/`) uses `META_ACCESS_TOKEN` — wrap in Prefect `@flow` with failure notification
- Zapier webhook (`ZAPIER_WEBHOOK_URL`) for Shopify actions only

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| prefect==3.6.23 | Python 3.10–3.14 | Do NOT use Prefect 2.x — breaking API changes; 3.x is current |
| tenacity==9.1.4 | Python 3.10+ | v9 dropped Python 3.9 support; use v8.x if stuck on 3.9 |
| httpx==0.28.1 | Python 3.8+ | HTTP/2 requires `pip install httpx[http2]` |
| gspread==6.2.1 | google-auth>=2.0 | gspread 6.x uses Service Account or OAuth2; do NOT use deprecated `gspread.authorize()` pattern from gspread 5.x docs |
| sentry-sdk==2.56.0 | Python 3.6–3.14 | Initialize before any imports in main script: `sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))` |
| pydantic==2.x | Python 3.8+ | Pydantic v1 and v2 are NOT compatible — pick one; v2 is current |

---

## Sources

- PyPI (verified live): prefect 3.6.23, tenacity 9.1.4, httpx 0.28.1, gspread 6.2.1, sentry-sdk 2.56.0, apify-client 2.5.0, fastapi 0.135.2, playwright 1.58.0 — HIGH confidence
- [Prefect release notes](https://docs.prefect.io/v3/release-notes) — version and retry features verified — HIGH confidence
- [Apify TikTok Scraper](https://apify.com/clockworks/tiktok-scraper) and [Meta Ad Scraper](https://apify.com/whoareyouanas/meta-ad-scraper) — actors confirmed active — MEDIUM confidence (actor quality varies, test before committing)
- [Redis deduplication patterns](https://redis.io/tutorials/data-deduplication-with-redis/) — SET NX + TTL pattern verified — HIGH confidence
- [ZenML orchestration comparison](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow) — Prefect vs Dagster vs Airflow comparison — MEDIUM confidence
- [FreeAgent engineering: orchestration tools 2025](https://engineering.freeagent.com/2025/05/29/decoding-data-orchestration-tools-comparing-prefect-dagster-airflow-and-mage/) — current comparison — MEDIUM confidence
- PPSpy / PipiAds API availability — NOT confirmed, no official API docs found — LOW confidence, needs phase research
- gspread maintenance status — actively looking for new maintainers per GitHub README — noted as risk; current latest is 6.2.1 and functional

---

*Stack research for: NEWGARMENTS automated creative research pipeline*
*Researched: 2026-03-27*
