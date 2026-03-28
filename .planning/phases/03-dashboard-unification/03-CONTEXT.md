# Phase 3: Dashboard Unification - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the GitHub Pages static dashboard with a content discovery + remake workflow section in the existing Railway ad-command-center dashboard. The editor opens one URL, sees fresh discoveries, manages the remake queue, and monitors pipeline health. No new frontend framework — extend the existing vanilla JS `static/index.html`.

</domain>

<decisions>
## Implementation Decisions

### Dashboard Architecture
- **D-01:** Extend the existing `ad-command-center/static/index.html` with new sections/tabs. No React, no build step, no new framework. The current vanilla JS + CSS custom properties pattern works and auth is already wired.
- **D-02:** Add a tab/nav system to separate "Ad Performance" (existing) from "Content Discovery" (new) and "Pipeline Health" (new). The editor lands on Content Discovery by default.
- **D-03:** Keep the dark theme (`--bg: #1a1a2e`, `--card: #16213e`, `--accent: #e04400`). Reuse existing CSS custom properties and design patterns (card layout, radius, typography).

### Content Discovery View (DASH-01, DASH-02)
- **D-04:** Content cards show: thumbnail (or video frame), source badge (PPSpy/TikTok/Pinterest/Meta), ad copy snippet, engagement stats from metadata_json, discovered_at date, download link for original creative.
- **D-05:** Default view shows only `status=discovered` or `status=surfaced` content — no duplicates, no stale items from prior runs. Filterable by source and status.
- **D-06:** Fetch data from `GET /api/content?status=discovered` and `GET /api/content?status=surfaced`. Paginate or lazy-load if needed (current limit is 200).

### Creative Preview (DASH-03)
- **D-07:** Click a content card to open a modal with full-size creative preview (image or video embed). For TikTok carousels, show slide gallery. Include download button that fetches the creative_url directly.
- **D-08:** Video content (PPSpy, some Meta) rendered with native `<video>` tag. Images with `<img>`. No external player needed.

### Remake Workflow (DASH-04)
- **D-09:** Each content card has action buttons to advance lifecycle: "Surface" (discovered→surfaced), "Queue for Remake" (surfaced→queued). The editor clicks to advance.
- **D-10:** When status is `queued`, show a Google Drive link input field. Editor pastes the Drive link to the remade creative, which calls `PATCH /api/content/{id}/status` to move to `ready_to_launch` and stores the Drive link in metadata_json.
- **D-11:** Status badges on cards: color-coded per lifecycle stage (discovered=blue, surfaced=amber, queued=green, ready_to_launch=accent, launched=muted).

### Health Panel (DASH-05)
- **D-12:** Health section shows one card per source (PPSpy, TikTok, Pinterest, Meta). Each card displays: last discovery timestamp (from most recent content_item per source), total items discovered today, success indicator.
- **D-13:** Health data derived from content API queries — no separate health endpoint needed. `GET /api/content?source=ppspy&limit=1` gives last timestamp; count query per source gives daily totals.

### Retiring GitHub Pages (DASH-01)
- **D-14:** After the Railway dashboard has content discovery working, remove `decarba-remixer/src/dashboard/generate.ts` and the docs/ deployment from `daily-scrape.yml`. The `deploy-pages.yml` workflow becomes unused.
- **D-15:** Keep the generate.ts code in archive/ for reference but stop generating and deploying the static site.

### Claude's Discretion
- Card grid layout (columns, spacing, responsive breakpoints)
- Modal design for creative preview
- Loading states and empty states
- Whether to add a simple search/text filter for content
- Tab navigation design (sidebar vs top tabs)
- Health panel refresh interval

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Dashboard
- `ad-command-center/static/index.html` — Current dashboard UI (950 lines vanilla JS+CSS+HTML, dark theme, Chart.js)
- `ad-command-center/main.py` — FastAPI app, route registration, static file serving
- `ad-command-center/routes/content.py` — Content API (GET/POST/PATCH) — data source for all new views
- `ad-command-center/routes/auth.py` — Bearer token auth via DASHBOARD_SECRET
- `ad-command-center/models.py` — ContentItem model (fields, lifecycle, constraints)

### GitHub Pages Dashboard (reference for editor workflow patterns)
- `decarba-remixer/src/dashboard/template.ts` — HTML template generator for static dashboard (patterns to replicate)
- `decarba-remixer/src/dashboard/generate.ts` — Data pipeline for static dashboard (to be retired)

### Workflows to modify
- `.github/workflows/daily-scrape.yml` — Remove docs/ generation step
- `.github/workflows/deploy-pages.yml` — To be disabled/removed

### Config
- `decarba-remixer/config/products.yaml` — Product catalog for suggested product matching (may be useful in discovery cards)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `static/index.html` CSS custom properties — full dark theme color system, typography, card styles, modal patterns already defined
- Chart.js 4.4.7 CDN already loaded — can be used for health trend charts
- Auth flow — login, token storage, `authFetch()` wrapper already implemented
- Card grid pattern — existing `.creative-grid` with 3-column layout, status badges, action buttons
- Modal pattern — existing overlay + centered content box for budget adjustment (incomplete but pattern exists)
- Google Fonts DM Sans already loaded

### Established Patterns
- All API calls go through `authFetch(url)` which adds Bearer token
- State management via vanilla JS variables + DOM manipulation
- Period selector pattern (1d/7d/14d/30d) for date range filtering
- Toast/notification system exists (bell icon + dropdown)
- Status badges with color-coded left borders (ROAS thresholds → lifecycle stages)

### Integration Points
- `GET /api/content` — primary data source, already returns all needed fields
- `PATCH /api/content/{id}/status` — lifecycle transitions
- `static/` directory mount — any new JS/CSS files auto-served
- Potential new endpoints needed: health aggregation, content count by source/date

</code_context>

<specifics>
## Specific Ideas

- Editor (Jerson) currently uses the GitHub Pages dashboard daily — the new view must cover the same workflow: see new content → decide what to remake → download creative → submit remake
- The "Olivier view" from GitHub Pages (TikTok-only, numbered cards) is NOT needed in the unified dashboard — it was a one-off hack
- Suggested products per ad (from products.yaml) would be nice-to-have but not required for v1

</specifics>

<deferred>
## Deferred Ideas

- **Suggested products matching** — match content to NEWGARMENTS products from catalog, would require embedding products.yaml data
- **Real-time pipeline monitoring** — WebSocket updates for live scraping progress
- **Multi-user roles** — different views for editor vs boss (current DASHBOARD_SECRET is single shared password)
- **Content analytics** — track which discoveries lead to successful launches

</deferred>

---

*Phase: 03-dashboard-unification*
*Context gathered: 2026-03-28*
