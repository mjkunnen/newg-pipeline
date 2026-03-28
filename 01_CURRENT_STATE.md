# Current State — 2026-03-27

## GSD Project Status

**GSD is geïnitialiseerd.** Alle planning artifacts staan in `.planning/`.

| Artifact | Location | Status |
|---|---|---|
| Project context | `.planning/PROJECT.md` | ✓ Committed |
| Config | `.planning/config.json` | ✓ Committed |
| Research (4 docs + summary) | `.planning/research/` | ✓ Committed |
| Requirements (25 v1) | `.planning/REQUIREMENTS.md` | ✓ Committed |
| Roadmap (5 phases) | `.planning/ROADMAP.md` | ✓ Committed |
| State tracking | `.planning/STATE.md` | ✓ Committed |

**Next step:** `/gsd:discuss-phase 0` of `/gsd:plan-phase 0` (Codebase Consolidation)

### Roadmap Overview

| Phase | Goal | Requirements | Status |
|---|---|---|---|
| 0 | Codebase Consolidation | CLEAN-01–04 | Not started |
| 1 | State Layer (Railway Postgres) | STATE-01–04 | Not started |
| 2 | Discovery Reliability | DISC-01–05, SRC-01–04 | Not started |
| 3 | Dashboard Unification | DASH-01–05 | Not started |
| 4 | Launch Hardening | LAUNCH-01–03 | Not started |

## Reality Check Findings (2026-03-27)

Belangrijke bevindingen uit de codebase analyse:

### Wat ECHT werkt in productie
- PPSpy scraping (daily via GitHub Actions + decarba-remixer TypeScript)
- Google Sheets form submissions (via Apps Script webhook)
- Meta campaign launch vanuit Sheet (via `fromSheet.ts`)
- fal.ai image remixing
- GitHub Pages dashboard (gegenereerd van scrape data)

### Wat NIET werkt
- Railway Postgres — code bestaat in ad-command-center maar is **nooit gedeployed**
- ad-command-center dashboard — gebouwd maar **draait nergens**
- scout/ Python scripts — vereisen **handmatige Claude invocatie**, niet geautomatiseerd
- TikTok/Pinterest/Meta Ad Library scraping — **niet geautomatiseerd**
- Unified data pipeline — systemen praten niet met elkaar

### Echte actieve pipeline
`decarba-remixer` (TypeScript) → Google Sheets (Apps Script) → GitHub Actions → Meta API

### Google Sheets als truth store
- Sheet ID: `1p8pdlNQKYRoX8HydJAHqAX6NhK_FAMxt2WHmWWps-yw`
- Tracks: editor, date, ad_id, ad_copy, original_reach, drive_link, landing_page, platforms, submitted_at, status
- Launcher (`fromSheet.ts`) leest pending submissions, launched, en update status

## Confirmed Current Facts

- **Git branch**: `master`
- **GitHub Actions workflows** (5 active): `daily-scrape.yml`, `daily-pinterest.yml`, `daily-products.yml`, `launch-campaigns.yml`, `deploy-pages.yml`
- **Ad Command Center**: code-ready maar NIET gedeployed op Railway
- **Decarba Remixer**: TypeScript, actieve pipeline, configs in `config/products.yaml` en `config/settings.yaml`
- **Scout module**: Python, vereist handmatige Claude/Playwright invocatie
- **Pipeline module**: Python, handmatige invocatie
- **Credentials**: all via `.env` + env vars (see `CLAUDE.md` for full list)
- **Shopify access**: Zapier MCP only, never direct API

## Active Automation

| Workflow | Schedule | Purpose | Real? |
|---|---|---|---|
| `daily-scrape.yml` | Cron 01:00, 04:00, 07:00 UTC | PPSpy scrape → Dashboard → Pages deploy | ✓ Active |
| `launch-campaigns.yml` | After daily-scrape | Launch pending from Sheet | ✓ Active |
| `daily-products.yml` | Cron 08:00 UTC | Product pipeline + Make webhooks | ✓ Active |
| `daily-pinterest.yml` | Cron | Pinterest pin remake | Partial |
| `deploy-pages.yml` | On push | GitHub Pages deploy | ✓ Active |

## Key Working Files

### Scripts that run regularly (via GitHub Actions)
- `decarba-remixer/src/scraper/ppspy.ts` — PPSpy scraping (MAIN ACTIVE SCRAPER)
- `decarba-remixer/src/launcher/fromSheet.ts` — Launch from Google Sheets
- `decarba-remixer/src/launcher/meta.ts` — Meta campaign creation
- `build_dashboard.py` — Dashboard builder for GitHub Pages

### Scripts that exist but are NOT automated
- `scout/daily_discovery.py` — Requires Claude/Playwright, not standalone
- `scout/remake_competitor_ads.py` — Manual execution only
- `pipeline/remake_pipeline.py` — Manual multi-stage pipeline
- `launch/meta_campaign.py` — Standalone Python launcher (parallel to TS version)

### Config files
- `config/automation-settings.json`
- `config/generation-config.json`
- `config/brand-voice.md`
- `config/target-audience.md`
- `config/clothing-catalog.json`
- `decarba-remixer/config/products.yaml`
- `decarba-remixer/config/settings.yaml`

## Unresolved Ambiguity

- Multiple slideshow data JS files (`v3`, `v4`, `v5`) — Phase 0 will resolve
- Multiple PipiAds scripts (`v1`–`v4`) — Phase 0 will archive old versions
- `clone/`, `clone_runs/`, `bot/`, `tiktok-test/`, `tiktok_profile/` — Phase 0 will clean up
- Root-level `snapshot_*.md` files — temporary browser state dumps

## Known Risks for Fresh Sessions

1. **Do not assume research .md files are current** — they are point-in-time outputs
2. **Always check which version** of multi-version files is active before editing
3. **Security**: never hardcode credentials, always use env vars (see `CLAUDE.md`)
4. **Shopify**: only via Zapier MCP, never direct API
5. **Product images**: AI generation fails for product shots, only extraction/segmentation works
6. **Remakes**: must be full outfit (top+bottom+shoes), not just hoodie swap
7. **ad-command-center is NOT deployed** — don't assume Railway Postgres is live
8. **scout/ scripts need Claude** — they are not standalone automated scripts
