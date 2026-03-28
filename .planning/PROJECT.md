# NEWGARMENTS — Creative Research Pipeline

## What This Is

An automated creative research and ad pipeline for NEWGARMENTS, a streetwear brand. The system discovers viral competitor content across TikTok, Pinterest, Meta Ad Library, and PPSpy — surfaces the best performers in a dashboard for a creative editor — and automates the remake-to-launch flow via Google Sheets → Meta Ads.

## Core Value

Reliable daily discovery of the best viral competitor content, surfaced in a dashboard the creative editor can trust and act on immediately.

## Requirements

### Validated

- ✓ Dashboard exists (Railway-deployed, `ad-command-center/`) — existing
- ✓ TikTok scraping infrastructure (`scout/`) — existing
- ✓ Pinterest remake pipeline (`pipeline/`) — existing
- ✓ PPSpy/PipiAds research scripts — existing
- ✓ Meta campaign launcher (`launch/`) — existing
- ✓ Decarba Remixer (PPSpy → Vision → fal.ai → Meta) — existing
- ✓ GitHub Actions workflows (5 active) — existing
- ✓ Google Sheets → Meta launch integration — existing
- ✓ Codebase consolidated: one canonical file per component, versioned scripts archived — Phase 0
- ✓ Startup validation: all active scripts validate env vars and credentials at startup — Phase 0
- ✓ Dependencies pinned with exact versions, .env.example documents all 21 secrets — Phase 0

### Active

- [ ] Reliable daily discovery across all sources (TikTok, Pinterest, Meta Ad Library, PPSpy)
- [ ] Viral filtering that actually works (only high-performers shown in dashboard)
- [ ] Dashboard shows fresh content daily, never stale/duplicate data
- [ ] Pinterest flow checks sheets before acting (no old pins re-used)
- [ ] TikTok flow filters by views/engagement (only viral content surfaces)
- [ ] PPSpy properly configured for NEWGARMENTS' competitor set
- [ ] Meta Ad Library integration for competitor ad discovery
- [ ] Remake flow: editor downloads → remakes → Google Drive link → dashboard → sheets → auto-launch
- [ ] End-to-end pipeline that starts without errors
- [ ] Error handling and alerting when steps fail (not silent failures)

### Out of Scope

- AI-generated product photography — proven to fail for product shots, only extraction/segmentation works
- Full autopilot (auto-remake without human review) — editor decides what gets remade
- Direct Shopify API access — Zapier MCP only

## Context

- Brand: NEWGARMENTS, Gen Z streetwear, NL-based
- Creative editor uses the dashboard daily as their primary tool
- Current pain: every step in the pipeline is fragile — scripts crash, APIs timeout, filters don't work, old content resurfaces, launches fail silently
- Multiple versions of scripts exist (pipiads v1-v4, slideshow data v3-v5) creating confusion
- The system has grown organically — it's a patchwork of Python, TypeScript, GitHub Actions, Railway, Google Sheets, and Zapier
- Priority #1: Discovery must work reliably before anything else matters

## Constraints

- **Credentials**: All via `.env` + env vars, never hardcoded (see CLAUDE.md security rules)
- **Shopify**: Zapier MCP only, never direct API
- **Product images**: AI generation fails, only extraction/segmentation works
- **Remakes**: Must be full outfit (top+bottom+shoes), not just hoodie swap
- **Hosting**: Dashboard on Railway, automation on GitHub Actions
- **Language**: Boss communicates in Dutch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus on discovery reliability first | Discovery is highest-impact — if content doesn't arrive, nothing else matters | — Pending |
| Keep human-in-the-loop for remakes | Editor judgment on what to remake is valuable, full autopilot not wanted | — Pending |
| Research best practices before rebuilding | Current patchwork approach keeps failing, need proven patterns | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after Phase 0 completion*
