# Phase 2: Discovery Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-28
**Phase:** 02-discovery-reliability
**Areas discussed:** Dedup strategie, Source consolidatie, Meta Ad Library approach, Failure alerting
**Mode:** --auto (all decisions auto-selected)

---

## Dedup Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Postgres-based (content_items ON CONFLICT) | Use existing Phase 1 table, no extra infra | ✓ |
| Redis SET NX + TTL | Fast O(1) lookups, 24h TTL expiry | |
| File-based (processed_tiktok.json pattern) | Git-committed JSON, already exists for TikTok | |

**User's choice:** [auto] Postgres-based — already built, simplest, no new dependencies
**Notes:** Redis deferred to v2 (ORCH-02). File-based dedup creates merge conflicts and format incompatibilities.

---

## Source Consolidation

| Option | Description | Selected |
|--------|-------------|----------|
| TS scrapers canonical, archive Python | Keep decarba-remixer scrapers, archive scout/ and pipeline/ scrapers | ✓ |
| Python scrapers canonical, archive TS | Keep scout/ scrapers, rewrite TS pipeline | |
| Keep both, coordinate dedup | Run both TS and Python scrapers with shared dedup | |

**User's choice:** [auto] TS canonical — already automated in daily-scrape.yml, Python versions are local/legacy
**Notes:** cloud_pinterest.py remake logic (fal.ai) may be reused later but scraping moves to TS.

---

## Meta Ad Library Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Apify actor via GitHub Actions | Use existing Apify infrastructure, community-maintained actors | ✓ |
| Playwright browser automation | Direct scraping, more control but maintenance burden | |
| Manual (keep current Claude-driven) | daily_discovery.py prompt generator, no automation | |

**User's choice:** [auto] Apify actor — proven pattern, handles anti-bot, no Playwright maintenance
**Notes:** Research phase must identify best Apify Meta Ad Library actor and verify it returns the data fields we need.

---

## Failure Alerting

| Option | Description | Selected |
|--------|-------------|----------|
| GitHub Actions email + Slack webhook | Built-in email on failure + custom Slack step | ✓ |
| Sentry SDK integration | Error tracking with stack traces, free tier | |
| GitHub Actions email only | Simplest, no extra secrets | |

**User's choice:** [auto] GitHub email + Slack — good balance of simplicity and visibility
**Notes:** Sentry deferred — overkill for workflow-level alerting. SLACK_WEBHOOK_URL secret needed.

---

## Claude's Discretion

- Viral filtering thresholds (TikTok MIN_REACH, MAX_AGE_DAYS)
- Pinterest daily volume limit
- Meta competitor list selection
- Cron schedule optimization

## Deferred Ideas

- Redis dedup (v2)
- Prefect orchestration (v2)
- Top-discovery Slack alerts (v2)
- Auto-scheduling launches (v2)
