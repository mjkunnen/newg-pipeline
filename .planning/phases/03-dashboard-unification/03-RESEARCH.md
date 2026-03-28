# Phase 3: Dashboard Unification - Research

**Researched:** 2026-03-28
**Domain:** Vanilla JS frontend extension, FastAPI backend additions, GitHub Actions workflow cleanup
**Confidence:** HIGH

## Summary

This phase is a contained frontend + backend extension with no new external dependencies. All scaffolding (auth, CSS, Card grid, modal, API routes) already exists in `ad-command-center/static/index.html` and `ad-command-center/routes/content.py`. The planner does not need to introduce any new frameworks or libraries.

The one backend gap requiring a code change before the frontend can work is that `PATCH /api/content/{id}/status` does not accept or persist a `drive_link` (or any metadata update). D-10 requires storing a Google Drive link in `metadata_json` at the `queued → ready_to_launch` transition. The existing `StatusUpdate` Pydantic model accepts only `status: str`. This must be extended or a separate `PATCH /api/content/{id}/metadata` endpoint must be added.

Health panel data (DASH-05) can be derived entirely from the existing `GET /api/content` endpoint — no separate backend endpoint is required, but the query is: for each source, fetch the single most-recent row (`?source=X&limit=1`) for timestamp, and a count query for daily totals. Because the existing endpoint does not expose a count-only query, the frontend must either receive the full list and count client-side, or a lightweight `GET /api/content/health` aggregate endpoint can be added for efficiency.

**Primary recommendation:** Add a `drive_link` optional field to the status PATCH body (extend `StatusUpdate`). Add a `GET /api/content/health` aggregate endpoint. Then implement the three tab sections in `index.html` in order: tab nav, Content Discovery view, Remake Workflow interactions, Health panel. Finally retire GitHub Pages by removing two workflow steps.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Extend the existing `ad-command-center/static/index.html` with new sections/tabs. No React, no build step, no new framework. The current vanilla JS + CSS custom properties pattern works and auth is already wired.
- **D-02:** Add a tab/nav system to separate "Ad Performance" (existing) from "Content Discovery" (new) and "Pipeline Health" (new). The editor lands on Content Discovery by default.
- **D-03:** Keep the dark theme (`--bg: #1a1a2e`, `--card: #16213e`, `--accent: #e04400`). Reuse existing CSS custom properties and design patterns (card layout, radius, typography).
- **D-04:** Content cards show: thumbnail (or video frame), source badge (PPSpy/TikTok/Pinterest/Meta), ad copy snippet, engagement stats from metadata_json, discovered_at date, download link for original creative.
- **D-05:** Default view shows only `status=discovered` or `status=surfaced` content — no duplicates, no stale items from prior runs. Filterable by source and status.
- **D-06:** Fetch data from `GET /api/content?status=discovered` and `GET /api/content?status=surfaced`. Paginate or lazy-load if needed (current limit is 200).
- **D-07:** Click a content card to open a modal with full-size creative preview (image or video embed). For TikTok carousels, show slide gallery. Include download button that fetches the creative_url directly.
- **D-08:** Video content (PPSpy, some Meta) rendered with native `<video>` tag. Images with `<img>`. No external player needed.
- **D-09:** Each content card has action buttons to advance lifecycle: "Surface" (discovered→surfaced), "Queue for Remake" (surfaced→queued). The editor clicks to advance.
- **D-10:** When status is `queued`, show a Google Drive link input field. Editor pastes the Drive link to the remade creative, which calls `PATCH /api/content/{id}/status` to move to `ready_to_launch` and stores the Drive link in metadata_json.
- **D-11:** Status badges on cards: color-coded per lifecycle stage (discovered=blue, surfaced=amber, queued=green, ready_to_launch=accent, launched=muted).
- **D-12:** Health section shows one card per source (PPSpy, TikTok, Pinterest, Meta). Each card displays: last discovery timestamp (from most recent content_item per source), total items discovered today, success indicator.
- **D-13:** Health data derived from content API queries — no separate health endpoint needed. `GET /api/content?source=ppspy&limit=1` gives last timestamp; count query per source gives daily totals.
- **D-14:** After the Railway dashboard has content discovery working, remove `decarba-remixer/src/dashboard/generate.ts` and the docs/ deployment from `daily-scrape.yml`. The `deploy-pages.yml` workflow becomes unused.
- **D-15:** Keep the generate.ts code in archive/ for reference but stop generating and deploying the static site.

### Claude's Discretion

- Card grid layout (columns, spacing, responsive breakpoints)
- Modal design for creative preview
- Loading states and empty states
- Whether to add a simple search/text filter for content
- Tab navigation design (sidebar vs top tabs)
- Health panel refresh interval

### Deferred Ideas (OUT OF SCOPE)

- Suggested products matching — match content to NEWGARMENTS products from catalog, would require embedding products.yaml data
- Real-time pipeline monitoring — WebSocket updates for live scraping progress
- Multi-user roles — different views for editor vs boss (current DASHBOARD_SECRET is single shared password)
- Content analytics — track which discoveries lead to successful launches
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Deploy ad-command-center as the single operational dashboard (retire GitHub Pages static dashboard for discovery) | GitHub Pages retirement: remove generate step from daily-scrape.yml, disable deploy-pages.yml. Railway deploy is already live (Phase 1). |
| DASH-02 | Dashboard shows only fresh, unprocessed content daily — reads from Postgres, never stale or duplicate | Existing GET /api/content?status=discovered returns only status=discovered rows ordered by discovered_at desc. Postgres dedup (ON CONFLICT DO NOTHING) from Phase 2 guarantees no duplicates. No additional dedup logic needed in frontend. |
| DASH-03 | Editor can download/preview original creative assets directly from dashboard | creative_url and thumbnail_url fields exist on ContentItem. Download: anchor tag with href=creative_url download attribute or direct link. Preview: native video/img tags per D-08. |
| DASH-04 | Editor can submit Google Drive link for remade creative via dashboard form, updating content item status in Postgres | Backend gap: current PATCH /api/content/{id}/status only updates status field. Drive link must also be written to metadata_json. StatusUpdate model needs optional drive_link field. |
| DASH-05 | Dashboard shows health indicators — did each source's scraping succeed today, how many items found, last run timestamp | D-13 approach: 4 GET /api/content?source=X&limit=1 calls (last timestamp) + count queries per source. Alternatively a single GET /api/content/health aggregate endpoint for efficiency. Recommend the aggregate endpoint to avoid 8 separate API calls on health panel load. |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS (ES2020+) | — | All frontend logic | Locked (D-01) — no build step, no framework |
| CSS Custom Properties | — | Theming and design system | Already defined in index.html, reuse only |
| FastAPI | 0.135.2 | Backend API additions | Already the app server |
| SQLAlchemy | current (project lock) | ORM for new aggregate query | Already in use |
| Pydantic v2 | current (project lock) | Extend StatusUpdate model | Already in use |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Chart.js | 4.4.7 (CDN, already loaded) | Optional trend chart in health panel | Only if health panel needs a sparkline — not required for v1 |
| pytest | 8.x (project) | Test new PATCH behavior and health endpoint | All new API routes must have test coverage |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Vanilla JS tabs | Alpine.js / htmx | Both require adding a CDN dependency — not allowed per D-01 |
| Separate health endpoint | 8 content API calls | 8 calls is measurably slower and harder to reason about; aggregate endpoint is cleaner |
| Extending PATCH body | New PATCH /metadata endpoint | Either works; extending the existing body keeps the API surface smaller |

**Installation:** No new packages. All changes are to existing code.

## Architecture Patterns

### Recommended Project Structure

No new directories needed. Changes occur within:

```
ad-command-center/
├── static/
│   └── index.html           # All frontend additions go here
├── routes/
│   └── content.py           # Backend: extend StatusUpdate, add health endpoint
├── tests/
│   └── test_content_items.py  # Extend with new test cases
.github/workflows/
├── daily-scrape.yml         # Remove generate + deploy-pages steps
└── deploy-pages.yml         # Disable (remove trigger or delete)
decarba-remixer/
├── src/dashboard/
│   └── generate.ts          # Move to archive/
└── docs/                    # Stop committing to this path
```

### Pattern 1: Tab Navigation (Vanilla JS)

**What:** Three tabs — "Content Discovery" (default), "Ad Performance" (existing content moved), "Pipeline Health" (new). Tab state held in a JS variable; clicking a tab hides/shows the matching section and updates active class.

**When to use:** This is the only tab pattern allowed (no framework).

**Example:**

```javascript
// Tab switching — reuse existing CSS patterns
let activeTab = 'discovery'; // default landing tab

function switchTab(name) {
  activeTab = name;
  document.querySelectorAll('.tab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === name)
  );
  document.querySelectorAll('.tab-section').forEach(s =>
    s.classList.toggle('hidden', s.dataset.tab !== name)
  );
}
```

CSS class `.hidden { display: none; }` added to the stylesheet.

### Pattern 2: Content Card Rendering

**What:** Content Discovery cards follow the existing `.ad-card` pattern. `metadata_json` is a JSON string stored in Postgres — the frontend must `JSON.parse(item.metadata_json)` to extract engagement stats (views, likes, etc.).

**When to use:** Every content item returned from GET /api/content.

**Example (card structure):**

```javascript
function renderContentCard(item) {
  const meta = item.metadata_json ? JSON.parse(item.metadata_json) : {};
  const isVideo = item.source === 'ppspy' || (meta.type === 'video');
  const thumb = item.thumbnail_url
    ? `<img class="ad-thumb" src="${item.thumbnail_url}" loading="lazy">`
    : `<div class="ad-thumb-placeholder">No preview</div>`;

  return `
    <div class="ad-card" data-id="${item.id}" data-status="${item.status}">
      ${thumb}
      <div class="ad-body">
        <div class="content-source-badge source-${item.source}">${item.source.toUpperCase()}</div>
        <div class="content-status-badge status-${item.status}">${item.status}</div>
        <div class="ad-name">${item.ad_copy || '—'}</div>
        <div class="content-meta">
          ${meta.views ? `Views: ${meta.views}` : ''}
          <span>${new Date(item.discovered_at).toLocaleDateString()}</span>
        </div>
        ${renderCardActions(item)}
      </div>
    </div>`;
}
```

### Pattern 3: Lifecycle Action Buttons

**What:** Each card renders context-sensitive action buttons based on current `status`. Clicking calls `PATCH /api/content/{id}/status`. After success, re-render that card or reload the section.

**Example:**

```javascript
function renderCardActions(item) {
  if (item.status === 'discovered') {
    return `<button class="ad-btn" onclick="advanceStatus('${item.id}', 'surfaced')">Surface</button>`;
  }
  if (item.status === 'surfaced') {
    return `
      <button class="ad-btn" onclick="advanceStatus('${item.id}', 'queued')">Queue for Remake</button>
      <a class="ad-btn" href="${item.creative_url}" download target="_blank">Download</a>`;
  }
  if (item.status === 'queued') {
    return `
      <input type="text" class="drive-link-input" id="drive-${item.id}" placeholder="Paste Google Drive link...">
      <button class="ad-btn" onclick="submitDriveLink('${item.id}')">Submit Remake</button>`;
  }
  return '';
}

async function advanceStatus(id, newStatus, driveLink = null) {
  const body = { status: newStatus };
  if (driveLink) body.drive_link = driveLink;
  await apiFetch(`/api/content/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(body)
  });
  loadContentDiscovery(); // reload section
}
```

### Pattern 4: Creative Preview Modal

**What:** Clicking a card thumbnail opens a full-screen modal overlay (reuse existing `.modal-overlay` pattern). Modal content: full-size image or video, download button, card metadata.

**Example:**

```javascript
function openPreviewModal(item) {
  const meta = item.metadata_json ? JSON.parse(item.metadata_json) : {};
  const isVideo = item.source === 'ppspy' || meta.type === 'video';
  const media = isVideo
    ? `<video controls style="max-width:100%;max-height:70vh" src="${item.creative_url}"></video>`
    : `<img style="max-width:100%;max-height:70vh;object-fit:contain" src="${item.creative_url}">`;

  // TikTok carousel: slides array in metadata_json
  const slides = meta.slides || [];
  const gallery = slides.length > 1
    ? slides.map(s => `<img style="max-width:100%" src="${s}">`).join('')
    : media;

  document.getElementById('preview-modal-content').innerHTML = `
    ${gallery}
    <a href="${item.creative_url}" download class="budget-btn" style="margin-top:16px">Download</a>`;
  document.getElementById('preview-modal').classList.add('open');
}
```

### Pattern 5: Backend — Extend PATCH to Accept Drive Link

**What:** `StatusUpdate` model must accept an optional `drive_link` field. On `queued → ready_to_launch` transition, merge the drive_link into the existing `metadata_json`.

**Example (content.py):**

```python
class StatusUpdate(BaseModel):
    status: str
    drive_link: Optional[str] = None

@router.patch("/api/content/{item_id}/status")
def update_status(item_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter_by(id=item_id).first()
    if not item:
        raise HTTPException(404, "Content item not found")

    allowed = VALID_TRANSITIONS.get(item.status, [])
    if body.status not in allowed:
        if not allowed:
            raise HTTPException(400, f"'{item.status}' is a terminal state")
        raise HTTPException(400, f"Invalid transition: {item.status} → {body.status}. Allowed: {allowed}")

    item.status = body.status

    if body.drive_link:
        import json
        existing = json.loads(item.metadata_json or '{}')
        existing['drive_link'] = body.drive_link
        item.metadata_json = json.dumps(existing)

    db.commit()
    db.refresh(item)
    return {"id": item.id, "content_id": item.content_id, "source": item.source, "status": item.status}
```

### Pattern 6: Health Aggregate Endpoint

**What:** A single endpoint that returns, per source, last_seen timestamp and today's item count. Avoids 8 separate API calls from the frontend.

**Example (content.py):**

```python
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

@router.get("/api/content/health")
def content_health(db: Session = Depends(get_db)):
    """
    Returns health summary per source: last discovery timestamp and today's count.
    """
    sources = ["ppspy", "tiktok", "pinterest", "meta"]
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = {}
    for source in sources:
        last = (
            db.query(ContentItem)
            .filter_by(source=source)
            .order_by(ContentItem.discovered_at.desc())
            .first()
        )
        today_count = (
            db.query(func.count(ContentItem.id))
            .filter(
                ContentItem.source == source,
                ContentItem.discovered_at >= today_start,
            )
            .scalar()
        )
        result[source] = {
            "last_seen": last.discovered_at.isoformat() if last else None,
            "today_count": today_count,
            "ok": last is not None and last.discovered_at >= today_start,
        }
    return result
```

Note: `GET /api/content/health` must be registered before the static file catch-all in `main.py`. It already will be because `content.router` is registered before the static mount.

**IMPORTANT:** Because FastAPI routes are matched in order, `GET /api/content/health` must be defined in `content.py` BEFORE `GET /api/content/{item_id}` if that route exists. Currently there is no `GET /api/content/{item_id}` route, so order is not a problem — but the health route should come before any future `/{item_id}` route to avoid path collision.

### Pattern 7: Retiring GitHub Pages

**What:** Two changes to workflow files.

**daily-scrape.yml:**
- Remove the `generate dashboard` step (`npm run dashboard`)
- Remove the `commit and push` step that commits `decarba-remixer/docs/`
- Remove the `deploy-pages` job at the bottom of the file
- Remove `pages: write` and `id-token: write` from top-level `permissions` if no longer needed

**deploy-pages.yml:**
- Either delete the file or change the `on:` trigger to only `workflow_dispatch` with no `push` trigger (disables automatic deployment while preserving the file for reference)
- Recommended: delete the file. It has no value if docs/ is never updated.

**decarba-remixer/src/dashboard/generate.ts:**
- `git mv decarba-remixer/src/dashboard/generate.ts decarba-remixer/archive/generate.ts`
- Do NOT delete — preserves git history and the D-15 requirement.

### Anti-Patterns to Avoid

- **Fetching all content then filtering client-side for health:** The content list can be large (up to 200 items). Use the health endpoint or targeted queries.
- **Using innerHTML to inject creative_url directly without validation:** creative_url may contain characters that break HTML. Use `encodeURIComponent` for href attributes or set via `.setAttribute('href', url)`.
- **Triggering a full page reload after status transitions:** Instead, remove the transitioned card from the current view or re-fetch only the content section. A full reload loses tab state.
- **Hardcoding credentials or API URL as fallback:** `API_BASE` is already `''` (relative) — do not add a hardcoded Railway URL as fallback.
- **JSON.parse(metadata_json) without try/catch:** metadata_json may be null, an empty string, or malformed. Always guard: `const meta = (() => { try { return JSON.parse(item.metadata_json || '{}'); } catch { return {}; } })();`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth token management | Custom session store | Existing `getToken()` / `setToken()` / `apiFetch()` in index.html | Already handles 401 → logout flow |
| Video playback | Custom video player | Native `<video>` tag per D-08 | No external dependency; works for all browser-supported formats |
| Dedup on frontend | Client-side seen-set | Postgres ON CONFLICT DO NOTHING (Phase 2) | Dedup is already solved at write time |
| Status transition validation | Frontend guard | Backend VALID_TRANSITIONS dict in content.py | Backend enforces; frontend can trust 400 responses |
| Creative download proxy | Server-side download relay | Direct link to `creative_url` with `download` attribute | creative_url already points to public URLs (PPSpy CDN, TikTok CDN, etc.) |

**Key insight:** This phase is almost entirely additive UI work on top of a complete backend. Don't add backend complexity without a clear reason.

## Common Pitfalls

### Pitfall 1: metadata_json is a JSON string, not an object

**What goes wrong:** The `metadata_json` column is `Column(Text)` — it stores raw JSON as a string. Treating it as a dict in Python or an object in JS without parsing causes silent failures or attribute errors.

**Why it happens:** SQLAlchemy Text column does not auto-serialize/deserialize JSON.

**How to avoid:** In Python: `json.loads(item.metadata_json or '{}')`. In JS: `JSON.parse(item.metadata_json || '{}')` wrapped in try/catch.

**Warning signs:** `TypeError: string indices must be integers` (Python) or `TypeError: Cannot read properties of string` (JS).

### Pitfall 2: Route order conflict for /api/content/health

**What goes wrong:** If a `GET /api/content/{item_id}` route is ever added before `/api/content/health`, FastAPI will match `health` as the `item_id` path parameter and return 404 (no content item with id "health").

**Why it happens:** FastAPI matches routes in registration order.

**How to avoid:** Define `/api/content/health` before any `/{item_id}` route in `content.py`.

**Warning signs:** Health endpoint returns 404 or unexpected content item lookup response.

### Pitfall 3: creative_url may not be directly downloadable

**What goes wrong:** TikTok and Meta CDN URLs for videos/images may have short-lived signed tokens or CORS restrictions that prevent direct `<a href download>` behavior in the browser.

**Why it happens:** CDN URLs for social platforms often expire or are restricted to same-origin.

**How to avoid:** Test each source's creative_url in browser. If blocked, the download button should open the URL in a new tab (`target="_blank"`) rather than attempting a forced download. This is acceptable per D-07 ("download or preview").

**Warning signs:** Download button triggers 403 or file saves as 0 bytes.

### Pitfall 4: Tab state lost on content API errors

**What goes wrong:** If the content load fails and the page shows an error state, a full reload resets the active tab to the default (Content Discovery), disorienting the editor.

**Why it happens:** Tab state is in-memory JS variable, lost on reload.

**How to avoid:** Never do a hard `location.reload()` to recover from errors. Use `loadContentDiscovery()` to re-fetch just that section's data. Show an inline error state instead.

### Pitfall 5: daily-scrape.yml still has pages write permissions after retirement

**What goes wrong:** After removing the deploy steps, leaving `pages: write` and `id-token: write` in the workflow permissions is unnecessary and slightly broadens the token scope.

**Why it happens:** Permissions are inherited by all jobs in the workflow.

**How to avoid:** After removing the `deploy-pages` job, also remove `pages: write` and `id-token: write` from the top-level `permissions` block if the remaining jobs don't need them.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitHub Pages static HTML dashboard (generate.ts) | Railway FastAPI dashboard with live Postgres queries | This phase | Editor no longer depends on a nightly HTML build — data is live |
| Manual status tracking in Google Sheets | Postgres status lifecycle via PATCH API | Phase 1 | Structured state, API-driven |

**Deprecated/outdated after this phase:**
- `decarba-remixer/src/dashboard/generate.ts` — replaced by Railway dashboard
- `decarba-remixer/docs/` — no longer generated or deployed
- `.github/workflows/deploy-pages.yml` — no longer needed

## Environment Availability

> Only relevant external dependency is the Railway-deployed FastAPI app. Verified to be live from Phase 1.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Railway (FastAPI app) | All DASH-* requirements | Verified live (Phase 1) | — | — |
| Postgres on Railway | All DASH-* requirements | Verified live (Phase 1) | — | — |
| GitHub Actions | DASH-01 workflow retirement | Always available | — | — |

No missing dependencies.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `ad-command-center/` (no pytest.ini, uses conftest.py) |
| Quick run command | `cd ad-command-center && pytest tests/ -x -q` |
| Full suite command | `cd ad-command-center && pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-04 | PATCH accepts drive_link, writes to metadata_json | unit | `pytest tests/test_content_items.py -k drive_link -x` | Wave 0 — test must be added |
| DASH-05 | GET /api/content/health returns correct counts per source | unit | `pytest tests/test_content_health.py -x` | Wave 0 — new test file |
| DASH-02 | GET /api/content?status=discovered returns only discovered rows | unit | `pytest tests/test_content_items.py -k status_filter -x` | Wave 0 — test must be added |
| DASH-01 | generate step removed from daily-scrape.yml | manual | inspect YAML — no `npm run dashboard` step | N/A |
| DASH-03 | creative_url present on returned content items | unit | `pytest tests/test_content_items.py -k creative_url -x` | Wave 0 — test must be added |

### Sampling Rate

- **Per task commit:** `cd ad-command-center && pytest tests/ -x -q`
- **Per wave merge:** `cd ad-command-center && pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_content_health.py` — covers DASH-05: GET /api/content/health per-source aggregation
- [ ] New test cases in `tests/test_content_items.py` — covers DASH-04 (drive_link field), DASH-02 (status filter), DASH-03 (creative_url field presence)

## Open Questions

1. **Is creative_url publicly accessible for all four sources?**
   - What we know: creative_url is stored as-is from scraper output. PPSpy and TikTok use CDN URLs. Pinterest and Meta may use signed URLs with short TTL.
   - What's unclear: Whether direct download from the browser works for all sources without CORS issues.
   - Recommendation: Test during implementation. Fallback: open in new tab instead of forced download. The D-07 requirement says "download or preview" — new tab satisfies "preview".

2. **Should the Content Discovery view show `status=surfaced` items alongside `status=discovered`?**
   - What we know: D-05 says default view shows both `discovered` and `surfaced`. D-06 says fetch both separately.
   - What's unclear: Whether both are fetched in one combined request or two separate requests merged client-side.
   - Recommendation: Two fetches (`?status=discovered` and `?status=surfaced`), merge in JS before rendering, sort by `discovered_at` descending.

3. **TikTok carousel: where are slide URLs stored in metadata_json?**
   - What we know: template.ts references `slides: string[]` on `DashboardAd`. Phase 2 TikTok scraper writes to Postgres via `writeToContentAPI`.
   - What's unclear: The exact field name used in metadata_json for carousel slides by the TikTok scraper.
   - Recommendation: Before implementing the carousel gallery, read the Phase 2 TikTok scraper output or query a real Postgres row to confirm the field name.

## Project Constraints (from CLAUDE.md)

All of the following apply and the planner must verify each task complies:

- NEVER hardcode API keys, tokens, passwords, or secrets in source code
- ALWAYS use environment variables: `process.env.*` (TypeScript/JS) or `os.getenv()` (Python)
- NEVER log or print credentials
- NEVER commit `.env` files
- GitHub Actions secrets via `${{ secrets.* }}` only
- NEVER put real values as fallback defaults in `os.getenv("KEY", "real-value-here")` — use `None` or raise
- NEVER put credentials in `.yaml`, `.json`, `.toml` config files
- Pre-commit hook must not be bypassed with `--no-verify`
- Shopify: Zapier MCP only, never direct API
- AI-generated product photography: out of scope (extraction/segmentation only)
- Hosting: Dashboard on Railway, automation on GitHub Actions — do not change hosting

## Sources

### Primary (HIGH confidence)

- `ad-command-center/routes/content.py` — read directly, all route signatures verified
- `ad-command-center/static/index.html` — read directly, CSS variables, patterns, and existing JS functions verified
- `ad-command-center/models.py` — read directly, ContentItem fields confirmed
- `ad-command-center/main.py` — read directly, route registration order confirmed
- `.github/workflows/daily-scrape.yml` — read directly, generate and deploy-pages job structure confirmed
- `.github/workflows/deploy-pages.yml` — read directly, trigger conditions confirmed

### Secondary (MEDIUM confidence)

- `decarba-remixer/src/dashboard/template.ts` — read directly (first 100 lines), DashboardAd interface and slide/carousel pattern confirmed

### Tertiary (LOW confidence)

- TikTok carousel `metadata_json` field names — inferred from template.ts `slides: string[]` field; actual field name in scraper output unverified (flagged as Open Question 3)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already present in project, no new dependencies needed
- Architecture: HIGH — patterns are direct extensions of existing code verified by reading source files
- Pitfalls: HIGH — identified from direct code inspection (route order, JSON string parsing, permissions)
- Backend gap (drive_link): HIGH — confirmed by reading StatusUpdate model; it accepts only `status: str`

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable domain — vanilla JS + FastAPI, no fast-moving dependencies)
