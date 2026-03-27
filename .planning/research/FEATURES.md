# Feature Research

**Domain:** Automated creative ad research pipeline for DTC/streetwear brand
**Researched:** 2026-03-27
**Confidence:** MEDIUM — Core patterns verified via industry sources; specific tooling claims cross-referenced but some implementation details are WebSearch-only.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the creative editor assumes exist. Missing these = pipeline is useless, not just incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily automated discovery across all sources | Pipeline exists to eliminate manual research — if discovery doesn't run daily, editor does it by hand | MEDIUM | TikTok + Pinterest + Meta Ad Library + PPSpy must all run on schedule. Any source missing = gaps in competitive intelligence |
| Deduplication / seen-content tracking | Without this, old content resurfaces every run — editor wastes time on content already reviewed | MEDIUM | Requires persistent state (DB or flat file) keyed on content ID. Must survive between runs. Pattern: check-before-insert, not post-hoc dedup |
| Viral/engagement filtering that actually works | Low-performer content wastes editor attention. Editor should only see content worth remaking | MEDIUM | Threshold-based: views, engagement rate, share velocity. Must be configurable — what counts as "viral" changes. Currently broken in this pipeline |
| Fresh content daily, no stale data | Dashboard must show new content every day. Stale = editor loses trust in the tool and stops using it | LOW-MEDIUM | Requires timestamps on ingestion + dashboard filters by ingestion date, not content date |
| No silent failures | Pipeline fails → editor sees nothing → editor assumes pipeline ran fine. Silent failures are worse than visible errors | MEDIUM | Every step must emit structured success/failure signal. GitHub Actions `if: always()` notification step is the minimum viable pattern |
| Crash-resilient scripts | Scripts that crash on one bad item block all subsequent items | MEDIUM | Try/catch per item, not per run. Failed items log and skip — they don't halt the pipeline |
| Dashboard loads without broken states | Editor opens dashboard → sees content, status, actions. Broken UI = no adoption | LOW-MEDIUM | Railway deployment must be stable. Dashboard should gracefully handle empty states and loading errors |
| Content deduplicated against Google Sheets | If content is already in Sheets (already queued for remake), it must not appear again in dashboard | MEDIUM | Cross-reference Sheets before surfacing content. The Pinterest flow currently breaks here |
| Remake workflow: Drive link → Sheets → dashboard | Once editor uploads remake to Drive, the path to launch must be clear and automated | MEDIUM | Google Drive link captured → row written to Sheets → dashboard reflects status change → launch trigger fires |
| Launch confirmation, not silent launch | When Meta campaign fires, confirmation must be logged and visible | LOW | Webhook acknowledgement + log entry. Meta considers delivery successful only with proper response (HTTP 200 + JSON ack) |

---

### Differentiators (Competitive Advantage)

These move the pipeline from "functional" to giving NEWGARMENTS a real edge in creative research speed.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Engagement velocity scoring (not just raw views) | Views at 24h vs 48h vs 7d reveals whether content is still accelerating or peaked. Remakes of peaking content land while trend is live | HIGH | Requires historical snapshots of the same content ID over time. Storage cost low, logic moderate |
| Competitor set configurability | PPSpy/PipiAds are only useful if tracking the right competitors. Configurable competitor list = research stays targeted | LOW | Single config file (YAML or JSON) that all scrapers read. No hardcoded competitor handles anywhere |
| Content scoring / priority queue in dashboard | Not all viral content is equally worth remaking. A score combining views + engagement + recency lets editor prioritize instantly | MEDIUM | Scoring formula should be visible and adjustable. Avoid black-box ranking that editor can't reason about |
| Ingestion audit trail | Log every item ingested: source, timestamp, seen-before status, filter outcome. Enables debugging when pipeline behaves unexpectedly | LOW | Append-only log file or DB table. Cheap to build, high diagnostic value |
| Per-source health indicators in dashboard | Dashboard shows: "TikTok: 47 new items (2h ago) — Pinterest: 0 new items (26h ago, last run failed)". Editor knows immediately which sources are working | LOW-MEDIUM | Requires each scraper to write a health record (last run time, item count, status) that dashboard reads |
| Configurable viral thresholds | Min views, min engagement rate, max content age — all in one config, not buried in script logic | LOW | Currently hardcoded or missing. Central config file solves this without code changes |
| Remake brief auto-generation | From a viral ad, auto-generate a remake brief: hook structure, product positioning, format notes. Saves editor creative direction time | HIGH | Requires vision model (fal.ai or OpenAI Vision). Feasible given existing fal.ai integration. Validate on real editor workflow first |
| Source attribution on every item | Every dashboard card shows exactly where item came from (TikTok handle, PPSpy brand, Meta page name) + direct link to original. Editor can verify before remaking | LOW | Data field issue — scraper must capture source URL and attribution at ingestion time |

---

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full autopilot (auto-remake without human review) | Sounds efficient — skip the editor bottleneck | Remakes require full outfit (top + bottom + shoes), brand judgment, and quality gate. Auto-remakes produce wrong outfits and get launched without context. Already ruled out in PROJECT.md | Keep editor in loop. Automate the research delivery and launch mechanics — not the creative judgment |
| AI-generated product photography | Wants polished product shots without a photoshoot | Proven to fail for this use case (PROJECT.md). AI product shots require precise product segmentation — generates wrong colors, wrong logos, distorted product. Creates unusable assets at scale | Use only extraction/segmentation (cut product from existing photo). AI generation only for backgrounds/scenes |
| Multi-version script sprawl (v1/v2/v3/v4) | Each version "fixes" the previous one without removing it | Creates confusion about which is canonical. Debugging the wrong version wastes hours. Currently the main source of pipeline fragility | Single canonical version per component. Archive or delete old versions. Version via git, not filename |
| Real-time / streaming scraping | Wants instant notification when competitor posts | TikTok/Meta APIs are poll-based. Fake "real-time" via aggressive polling triggers rate limits and IP bans, breaking the pipeline for hours | Scheduled daily runs (3-6h cadence) is sufficient for creative research. Not a breaking news wire |
| Slack/email notification for every item | Wants to know about every new piece of content | Notification fatigue kills adoption. If 50 items trigger 50 messages, all are ignored | Dashboard-first. One daily digest notification maximum: "N new items surfaced, X high-priority" |
| Automated campaign optimization (bid/budget changes) | Wants Meta to auto-optimize after launch | Out of scope and high-risk. Auto-bid changes on untested creatives can spend budget incorrectly before human review | Manual review of first 24h performance. Automation only for launch, not optimization |
| Scraping without proxy rotation | Seems simpler — direct requests work initially | TikTok, Pinterest, and Meta Ad Library all implement bot detection. Direct scraping gets IP-banned within days, killing the pipeline | Use Apify (existing credential) or Oxylabs (existing credential) for all scraping. Never direct requests at scale |

---

## Feature Dependencies

```
[Seen-content tracking (DB/state)]
    └──required by──> [Deduplication]
    └──required by──> [Cross-Sheets dedup check]
    └──required by──> [Ingestion audit trail]

[Per-source health records]
    └──required by──> [Dashboard health indicators]

[Viral threshold config (central config file)]
    └──required by──> [Viral/engagement filtering]
    └──required by──> [Configurable thresholds]

[Structured source attribution at scrape time]
    └──required by──> [Source attribution on dashboard cards]
    └──required by──> [Competitor set configurability]

[Error signaling per step]
    └──required by──> [No silent failures]
    └──required by──> [Per-source health indicators]

[Google Drive link capture]
    └──required by──> [Remake workflow: Drive → Sheets → dashboard]
    └──required by──> [Launch trigger]

[Launch trigger]
    └──required by──> [Launch confirmation logging]
```

### Dependency Notes

- **Seen-content tracking is the load-bearing primitive.** Deduplication, cross-Sheets checks, and audit trail all require it. Build this first — everything else is downstream.
- **Central config file unlocks three features at once:** viral thresholds, competitor set, and configurable filters. It's a multiplier — low cost, high unlock value.
- **Error signaling must be built into every scraper step.** You cannot retrofit it later. The pattern: each step writes a structured result (source, timestamp, item_count, error_message or null) to a health record store (Sheets row, DB table, or JSON file).
- **Attribution capture is a scraper responsibility, not a dashboard responsibility.** If the scraper doesn't write source URL + attribution at ingestion time, the dashboard cannot reconstruct it.

---

## MVP Definition

This is not a greenfield product — the pipeline exists. MVP here means "minimum reliable pipeline" — the baseline where the editor can trust and use it daily.

### Launch With (v1 — Reliability Baseline)

These are the features that make the pipeline trustworthy. Nothing else matters until these work.

- [ ] Seen-content tracking — persistent state that prevents old content resurfacing between runs
- [ ] No silent failures — every step signals success/failure; GitHub Actions notifications on failure
- [ ] Crash-resilient scripts — per-item try/catch, failed items skip not halt
- [ ] Viral filtering that works — configurable threshold (views + engagement), currently broken
- [ ] Fresh content daily — dashboard filtered by ingestion date, not content date
- [ ] Cross-Sheets dedup — Pinterest and TikTok flows check Sheets before surfacing content
- [ ] Central config file — viral thresholds, competitor list, source toggles all in one place

### Add After Validation (v1.x)

Add once daily discovery is running reliably for 5+ consecutive days.

- [ ] Per-source health indicators in dashboard — add once health records exist per scraper
- [ ] Ingestion audit trail — append-only log, enables debugging when pipeline behaves unexpectedly
- [ ] Content scoring / priority queue — once editor is getting fresh content daily, add scoring to reduce time-to-decision
- [ ] Source attribution on dashboard cards — scraper-side change, low cost once existing scrapers are stabilized

### Future Consideration (v2+)

Defer until v1 reliability is proven over several weeks.

- [ ] Engagement velocity scoring — requires historical snapshots per content ID, adds storage complexity
- [ ] Remake brief auto-generation — high value but high complexity; validate editor workflow first
- [ ] Multi-source performance correlation — connecting Meta launch performance back to source content to identify which source predicts winners

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Seen-content tracking | HIGH | MEDIUM | P1 |
| No silent failures | HIGH | LOW | P1 |
| Crash-resilient scripts | HIGH | LOW | P1 |
| Viral filtering that works | HIGH | LOW-MEDIUM | P1 |
| Central config file | HIGH | LOW | P1 |
| Cross-Sheets dedup | HIGH | MEDIUM | P1 |
| Fresh content daily | HIGH | LOW | P1 |
| Per-source health indicators | MEDIUM | LOW | P2 |
| Ingestion audit trail | MEDIUM | LOW | P2 |
| Content scoring / priority queue | MEDIUM | MEDIUM | P2 |
| Source attribution on cards | MEDIUM | LOW | P2 |
| Engagement velocity scoring | HIGH | HIGH | P3 |
| Remake brief auto-generation | MEDIUM | HIGH | P3 |
| Multi-source performance correlation | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Required for the pipeline to be usable at all — directly addresses current fragility
- P2: Improve editor efficiency and diagnostic capability once P1 is stable
- P3: Competitive advantage features; defer until foundation is solid

---

## Competitor Feature Analysis

Commercial ad intelligence tools (Segwise, Minea, PipiAds, SocialPeta) and what they do vs what this pipeline needs:

| Feature | Commercial Tools (e.g. Segwise, Minea) | This Pipeline's Approach |
|---------|----------------------------------------|--------------------------|
| Multi-source aggregation | Yes — Meta, TikTok, YouTube in one dashboard | Same goal: TikTok + Pinterest + Meta Ad Library + PPSpy |
| Deduplication | Yes — platform handles it internally | Must build: persistent state file or DB keyed on content ID |
| Engagement filtering | Yes — filter by views, CTR, IPM | Must build: configurable threshold config, currently broken |
| Competitor tracking | Yes — follow brand pages, auto-alert on new ads | Manual competitor list in config; auto-monitoring is v2 |
| Viral / trending detection | Yes — velocity scoring, trend alerts | v2 feature; v1 is threshold-based |
| Creative tagging / AI analysis | Yes (Segwise) — auto-tag by hook type, format | Not planned; editor does this manually with context |
| Launch workflow integration | No — commercial tools stop at research | Core differentiator of this pipeline: research → remake → launch is one flow |
| Cost | $200-500+/month for commercial tools | Custom pipeline: infrastructure cost only |

Key insight: **commercial tools solve discovery and filtering well but stop at research**. This pipeline's differentiator is the research-to-launch connection through Google Sheets + Meta. That integration is worth protecting and investing in reliability first.

---

## Reliability Patterns (What Makes Pipelines Robust)

Based on research into data pipeline best practices — specifically relevant to the current fragility:

**Idempotent runs.** Every scraper run should produce the same result if re-run on the same day. Pattern: check-before-insert using content ID as key. If already seen, skip. If new, insert. Never append blindly.

**Structured health records per step.** Each scraper writes: `{source, run_timestamp, items_found, items_new, items_skipped, error: null|string}`. Dashboard reads these records to show source health.

**Fail-open, not fail-closed.** A scraper failing for one source (e.g. Pinterest rate-limited) must not block TikTok or Meta Ad Library from running. Steps are independent — failure isolation is required.

**One canonical version per component.** The current v1-v4 script versioning is a reliability anti-pattern. Single file per component, version controlled via git. Old versions deleted or archived.

**Webhook acknowledgement for Meta launches.** Meta marks a webhook delivery as failed if it doesn't receive HTTP 200 + response body within a timeout. Zapier handles this if configured correctly — verify it does.

---

## Sources

- [5 Best Creative Intelligence Tools for DTC Brands in 2025 — Segwise](https://segwise.ai/blog/best-creative-intelligence-tools-dtc-brands) — LOW confidence (page returned CSS only, couldn't extract content)
- [The Ultimate Content Pipeline for Ads — Billo](https://billo.app/blog/content-pipeline-for-ads/) — MEDIUM confidence, verified via fetch
- [Meta Ad Library API for Scraping — Swipekit](https://swipekit.app/articles/meta-ad-library-api) — MEDIUM confidence, verified via fetch
- [4 Facebook Ad Library Scrapers for Competitor Research — BestEver](https://www.bestever.ai/post/facebook-ad-library-scraper) — MEDIUM confidence
- [Idempotent Pipelines: Build Once, Run Safely Forever — DEV Community](https://dev.to/alexmercedcoder/idempotent-pipelines-build-once-run-safely-forever-2o2o) — MEDIUM confidence
- [The Importance of Idempotent Data Pipelines for Resilience — Prefect](https://www.prefect.io/blog/the-importance-of-idempotent-data-pipelines-for-resilience) — MEDIUM confidence
- [Never Miss a GitHub Actions Failure: Instant Alerts — Echobell](https://echobell.one/en/blog/github-actions-notifications) — MEDIUM confidence
- [Top Creative Intelligence Tools — Segwise](https://segwise.ai/blog/top-creative-intelligence-tools) — MEDIUM confidence
- [Top 5 TikTok Ad Spy Tools — Segwise](https://segwise.ai/blog/tiktok-adspy-tools-creative-discovery) — MEDIUM confidence
- [Automation of creative testing and campaign launching for Meta ads — n8n](https://n8n.io/workflows/6038-automation-of-creative-testing-and-campaign-launching-for-meta-ads/) — MEDIUM confidence

---

*Feature research for: Automated creative ad research pipeline — NEWGARMENTS streetwear brand*
*Researched: 2026-03-27*
