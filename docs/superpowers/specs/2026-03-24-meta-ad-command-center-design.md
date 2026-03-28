# NEWG Ad Command Center — Design Spec

## Overview

A self-hosted ad performance dashboard on Railway that goes beyond Meta Ads Manager by providing AI-powered creative analysis, pattern detection, and one-click ad iteration + launch. Replaces manual Ads Manager checking with an automated command center.

## Problem

- Meta Ads Manager shows data but doesn't analyze *why* creatives work
- No automated way to iterate on top performers
- Manual process to pause losers and shift budget
- No pattern detection across creatives

## Platform & Hosting

- **Railway** — single deployment, backend + frontend, one URL
- **No separate frontend hosting** — everything served from one service
- **Database:** PostgreSQL (Railway managed, free tier) — Railway containers are ephemeral so SQLite would be wiped on redeploy

## Data Source

- **Meta Marketing API** (Graph API v21.0) — free, no cost per call
- **Existing credentials:** `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, `META_PAGE_ID`, `META_PIXEL_ID` (from decarba-remixer .env)
- **Token management:** Meta long-lived tokens expire after ~60 days. Dashboard monitors for OAuthException errors and shows a prominent "Token expired — refresh needed" alert with instructions. Future: system user token for permanent access.
- **Sync interval:** Every 10 minutes (well within 200 calls/hour rate limit)
- **Multi-channel ready:** Architecture supports adding TikTok as second channel when API access is obtained

## Layout (Style A — Scroll-based)

### 1. KPI Cards (top of page)
- **Spend** — today's total, with % change vs yesterday
- **ROAS** — return on ad spend, color-coded (green >2x, yellow 1-2x, red <1x)
- **CPC** — cost per click, trend arrow
- **Add to Carts** — count today, change vs yesterday
- **Purchases** — count + revenue
- Each card shows sparkline mini-trend (last 7 days)

### 2. Spend/Revenue Chart
- Daily bar/line chart
- Toggle: 7 / 14 / 30 days
- Spend bars + Revenue line overlay
- Hover for daily breakdown

### 3. Creative Grid
Per active ad:
- Thumbnail (from Meta creative asset)
- Ad name / copy preview
- Spend, ROAS, CPC, CTR, ATCs, Purchases
- Status badge (Active / Paused / Learning)
- Sortable by any metric
- Color-coded: green border for top performers, red for losers
- **Action buttons per ad:**
  - ⏸ Pause / ▶ Activate
  - ⚡ Make Iterations (top performers only)

### 4. AI Analysis Section (Comparative)
- **Top vs Bottom comparison** — what do the top 3 ads have in common vs bottom 3
- **Pattern detection:**
  - Visual patterns (flat lay vs lifestyle, dark vs light background, product focus vs outfit)
  - Copy patterns (urgency vs casual, short vs long, which hooks convert)
  - Audience patterns (which countries/demographics respond to which creatives)
- **Recommendations** — concrete, actionable suggestions based on patterns
- Refreshed once per day (automated, e.g. midnight). Also refreshable on-demand via button. Keeps OpenAI costs minimal (~$0.10-0.30/day).

### 5. Notification Center
- In-dashboard notification bell/badge
- Alert types:
  - ROAS drops below threshold (configurable, default 1.5x)
  - Single ad CPA spikes above threshold
  - Daily budget nearly exhausted
  - Ad in learning phase completed
  - Iteration launched successfully

## Actions

### Pause / Activate Ads
- Toggle ad status directly from dashboard
- Calls `POST /{ad_id}?status=PAUSED` or `ACTIVE` via Meta API
- Instant effect, dashboard updates on next sync

### Adjust Budget
- Adjust the ad set daily budget (Meta budget lives at ad set level, not per-ad)
- Shows current ad set budget + spend pace
- Calls Meta API to update ad set daily budget
- Note: follows existing structure (1 campaign NEWG-Scaling, 1 ad set AdSet_Broad)

### Make Iterations (Core Feature)
Triggered per top-performing ad:
1. **Fetch original creative** — download image/video from Meta
2. **AI Analysis** — GPT-4o Vision analyzes what makes it work (composition, colors, copy, hook)
3. **Generate variations:**
   - 3 visual variations via fal.ai (same style, different products/angles)
   - 3 copy variations via GPT-4o-mini (different hooks/angles, maintaining winning patterns)
4. **Create combinations** — visual × copy matrix (up to 9 combinations, pick top 3-5)
5. **Auto-launch** — create new ads in same ad set via Meta API (uses existing `findOrCreateCampaign` + `findOrCreateAdSet` pattern from decarba-remixer)
6. **Track iterations** — link new ads back to parent ad for performance comparison

**Error handling:** Each step tracked in `iteration_jobs` table (pending → generating → launching → done/failed). If any step fails, job is marked failed with error message. User can retry from dashboard. No partial state — if launch fails, no orphaned creatives.

## Tech Stack

### Backend (Python)
- **FastAPI** — lightweight async API framework
- **APScheduler** — cron-like scheduler for 10-min sync
- **PostgreSQL** — via SQLAlchemy, Railway managed, stores:
  - `campaigns` — id, channel, name, status, daily_budget
  - `ad_sets` — id, channel, name, campaign_id, status, targeting
  - `ads` — id, channel, name, ad_set_id, status, creative_url, creative_cached (binary), ad_copy, parent_ad_id (for iterations)
  - `snapshots` — id, channel, ad_id, timestamp, spend, impressions, clicks, ctr, cpc, add_to_carts, purchases, revenue, roas
  - `ai_analyses` — id, channel, timestamp, analysis_json, recommendations
  - `notifications` — id, type, message, created_at, read
  - `iteration_jobs` — id, ad_id, status (pending/generating/launching/done/failed), error, created_at, completed_at
- **Meta API client** — Python reimplementation of launch logic (findOrCreateCampaign, findOrCreateAdSet, uploadCreative, createAd). Maintained in Python only — no dependency on TypeScript decarba-remixer code.
- **Creative caching** — thumbnails downloaded and cached in DB on first sync. Avoids reliance on Meta's expiring signed URLs.
- **OpenAI client** — GPT-4o for creative analysis, GPT-4o-mini for copy generation
- **fal.ai client** — for visual iteration generation

### Frontend (No framework)
- Single HTML file with inline CSS/JS (same pattern as decarba dashboard)
- **Chart.js** — for spend/revenue charts (CDN loaded)
- **NEWG brand styling** — dark theme (#1a1a2e background), accent #e04400, DM Sans font
- Fetches data from backend API endpoints
- Auto-refreshes every 10 minutes (matches sync interval)

### API Endpoints
```
GET  /api/kpis              — current KPI summary
GET  /api/kpis/history      — daily KPI history (for charts)
GET  /api/ads               — all ads with latest metrics
GET  /api/ads/:id           — single ad detail + metric history
GET  /api/analysis          — latest AI analysis
GET  /api/notifications     — unread notifications
POST /api/ads/:id/pause     — pause ad
POST /api/ads/:id/activate  — activate ad
POST /api/ads/:id/iterate   — trigger iteration pipeline
POST /api/notifications/:id/read — mark notification as read
POST /api/sync              — trigger manual sync
POST /api/analysis/refresh  — trigger AI analysis refresh on-demand
```

## Authentication
- All routes protected by `DASHBOARD_SECRET` — simple shared password
- Login page: enter password → stored in browser localStorage
- API checks `Authorization: Bearer {secret}` header
- Prevents unauthorized access to ad actions

## Environment Variables (Railway)
```
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=...
META_PAGE_ID=...
META_PIXEL_ID=...
OPENAI_API_KEY=...
FAL_KEY=...
DATABASE_URL=postgresql://... (Railway provides this)
DASHBOARD_SECRET=... (basic auth password)
SYNC_INTERVAL_MINUTES=10
ROAS_ALERT_THRESHOLD=1.5
CPA_ALERT_THRESHOLD=15.0
```

## Multi-Channel Architecture
- All database tables include `channel` field (default: "meta")
- API client is abstracted behind `AdPlatformClient` interface
- Adding TikTok = implementing `TikTokClient` with same interface
- Frontend filters by channel tab

## Iteration Tracking
- `ads.parent_ad_id` links iterations to original
- Dashboard shows iteration tree: original → v1, v2, v3
- Compare iteration performance vs original
- AI learns which iteration directions work

## Out of Scope (for now)
- TikTok integration (needs API approval first)
- Telegram/email alerts (dashboard-only for now)
- Multi-account support (single ad account)
- A/B test management
- Automated rules (auto-pause at threshold) — manual actions only for now
