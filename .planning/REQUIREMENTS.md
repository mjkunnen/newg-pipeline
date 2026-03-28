# Requirements: NEWGARMENTS Creative Research Pipeline

**Defined:** 2026-03-27
**Core Value:** Reliable daily discovery of the best viral competitor content, surfaced in a dashboard the creative editor can trust and act on immediately.

**Reality baseline:** The active production pipeline is decarba-remixer (TypeScript) → Google Sheets → GitHub Actions → Meta API. The ad-command-center (Python/FastAPI) exists in code but has never been deployed. scout/ Python scripts require manual Claude invocation and are not automated.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Codebase Consolidation

- [x] **CLEAN-01**: All versioned scripts (pipiads v1-v4, slideshow data v3-v5) archived, one canonical file per component
- [x] **CLEAN-02**: Every automated script validates required env vars, API keys, and cookie freshness at startup before doing work
- [x] **CLEAN-03**: package.json (decarba-remixer) and requirements.txt (Python scripts) accurately reflect all dependencies with pinned versions
- [x] **CLEAN-04**: Dead/orphaned directories identified and archived (clone/, clone_runs/, bot/, tiktok-test/)

### Discovery Reliability

- [ ] **DISC-01**: Seen-content tracking persists across runs — content shown once in dashboard never resurfaces
- [ ] **DISC-02**: TikTok content filtered by engagement rate (views/followers) per account, not flat view count — only viral content surfaces
- [ ] **DISC-03**: Pinterest flow checks seen-content state before acting — no old pins reprocessed
- [ ] **DISC-04**: Every GitHub Actions workflow step logs structured results and sends alert on failure (no silent failures — use `if: always()` pattern)
- [x] **DISC-05**: All scraping settings (competitor URLs, thresholds, source configs) in one central config file per source

### State Layer

- [x] **STATE-01**: Deploy ad-command-center to Railway with Postgres — operationalize the existing but dormant database code
- [x] **STATE-02**: Content items table with dedup (unique content ID across all sources — PPSpy ad ID, TikTok video ID, Pinterest pin ID, Meta ad ID)
- [x] **STATE-03**: Status lifecycle per content item: discovered → surfaced → queued → ready_to_launch → launched
- [x] **STATE-04**: Migration path: Google Sheets remains readable during transition, new content writes to Postgres first

### Content Sources

- [ ] **SRC-01**: TikTok scraping automated via GitHub Actions (currently requires manual Claude invocation — needs to become automated like PPSpy)
- [ ] **SRC-02**: Pinterest scraping automated via GitHub Actions (currently partial — needs full automation)
- [x] **SRC-03**: Meta Ad Library scraping automated via GitHub Actions (currently manual via scout/daily_discovery.py + Claude)
- [ ] **SRC-04**: PPSpy scraping continues working reliably (already automated in decarba-remixer — maintain and harden)

### Dashboard

- [ ] **DASH-01**: Deploy ad-command-center as the single operational dashboard (retire GitHub Pages static dashboard for discovery)
- [ ] **DASH-02**: Dashboard shows only fresh, unprocessed content daily — reads from Postgres, never stale or duplicate
- [ ] **DASH-03**: Editor can download/preview original creative assets directly from dashboard
- [ ] **DASH-04**: Editor can submit Google Drive link for remade creative via dashboard form, updating content item status in Postgres
- [ ] **DASH-05**: Dashboard shows health indicators — did each source's scraping succeed today, how many items found, last run timestamp

### Launch Automation

- [ ] **LAUNCH-01**: Launcher reads pending remakes from Postgres (with fallback: Google Sheets remains readable during transition)
- [ ] **LAUNCH-02**: Dry-run mode available — test a launch without actually publishing to Meta
- [ ] **LAUNCH-03**: Meta integration uses System User token (non-expiring) instead of personal token (60-day expiry)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Features

- **ADV-01**: Competitor scoring/ranking by creative performance over time
- **ADV-02**: Audit trail — full history of every content item from discovery to launch
- **ADV-03**: Multi-brand support — run the pipeline for multiple brands
- **ADV-04**: Slack/Discord alerts for top-performing discoveries
- **ADV-05**: Auto-scheduling of launches based on optimal posting times

### Pipeline Orchestration

- **ORCH-01**: Prefect 3.x orchestration wrapping all pipeline steps with retries
- **ORCH-02**: Redis dedup layer for real-time seen-content checking
- **ORCH-03**: APScheduler on Railway for always-on scheduling (replace triple-cron GitHub Actions pattern)

## Out of Scope

| Feature | Reason |
|---------|--------|
| AI-generated product photography | Proven to fail for product shots — only extraction/segmentation works |
| Full autopilot (auto-remake) | Editor judgment on what to remake is valuable, human-in-the-loop required |
| Real-time scraping | Batch/daily is sufficient, real-time adds complexity and API risk |
| Direct Shopify API access | Zapier MCP only per existing policy |
| Mobile app | Web dashboard is sufficient for editor workflow |
| Rewriting decarba-remixer from scratch | Working TypeScript pipeline should be hardened, not replaced |
| Replacing Google Sheets entirely in v1 | Transition path: Postgres becomes primary, Sheets stays readable as fallback |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLEAN-01 | Phase 0 | Complete |
| CLEAN-02 | Phase 0 | Complete |
| CLEAN-03 | Phase 0 | Complete |
| CLEAN-04 | Phase 0 | Complete |
| STATE-01 | Phase 1 | Complete |
| STATE-02 | Phase 1 | Complete |
| STATE-03 | Phase 1 | Complete |
| STATE-04 | Phase 1 | Complete |
| DISC-01 | Phase 2 | Pending |
| DISC-02 | Phase 2 | Pending |
| DISC-03 | Phase 2 | Pending |
| DISC-04 | Phase 2 | Pending |
| DISC-05 | Phase 2 | Complete |
| SRC-01 | Phase 2 | Pending |
| SRC-02 | Phase 2 | Pending |
| SRC-03 | Phase 2 | Complete |
| SRC-04 | Phase 2 | Pending |
| DASH-01 | Phase 3 | Pending |
| DASH-02 | Phase 3 | Pending |
| DASH-03 | Phase 3 | Pending |
| DASH-04 | Phase 3 | Pending |
| DASH-05 | Phase 3 | Pending |
| LAUNCH-01 | Phase 4 | Pending |
| LAUNCH-02 | Phase 4 | Pending |
| LAUNCH-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 — traceability populated after roadmap creation*
