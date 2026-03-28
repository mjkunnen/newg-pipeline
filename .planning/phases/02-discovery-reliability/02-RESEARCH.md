# Phase 2: Discovery Reliability - Research

**Researched:** 2026-03-28
**Domain:** GitHub Actions automation, TypeScript scraper refactoring, Apify Meta Ad Library, deduplication via Postgres, structured failure alerting
**Confidence:** HIGH (canonical code read directly; tooling choices verified against live actors and API docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dedup Strategy**
- D-01: Postgres `content_items` table is the single dedup mechanism. ON CONFLICT DO NOTHING handles idempotency. No Redis, no file-based dedup.
- D-02: Retire `scout/processed_tiktok.json`. TikTok scraper POSTs to content API like PPSpy.
- D-03: Pinterest dedup moves to Postgres. Remove Google Sheet read-only dedup. POST to content API.

**Source Consolidation**
- D-04: TypeScript scrapers in `decarba-remixer/src/scraper/` are canonical for PPSpy, TikTok, Pinterest.
- D-05: Archive `scout/tiktok_checker.py` — incompatible dedup format, uses Apify not EnsembleData.
- D-06: Archive `pipeline/cloud_pinterest.py` as a scraper. `daily-pinterest.yml` stays for remakes but its dedup reads Postgres.
- D-07: Both Pinterest workflows (`daily-scrape.yml` for discovery, `daily-pinterest.yml` for remakes) check Postgres for seen-content.

**Meta Ad Library**
- D-08: Use Apify Meta Ad Library actor. No Playwright. Research must identify best actor and input schema.
- D-09: Meta results POST to content API like all other sources.
- D-10: Replace `scout/config.py` subscription-box search terms with NEWGARMENTS competitor brands.

**Failure Alerting**
- D-11: GitHub Actions built-in failure email + `if: failure()` Slack webhook steps per workflow job.
- D-12: Each scraper step outputs structured result: source name, items found, items new, items skipped, errors. Feeds job summary and Phase 3 health dashboard.

**Central Config**
- D-13: One config file per source in `decarba-remixer/config/` (e.g., `tiktok-accounts.json`, `pinterest-boards.json`, `meta-competitors.json`, `ppspy-settings.json`).
- D-14: PPSpy search term "decarba" hardcoded in ppspy.ts — move to config.

### Claude's Discretion

- Viral filtering thresholds for TikTok (currently MIN_REACH=3000, MAX_AGE_DAYS=14) — planner can adjust
- Pinterest MAX_NEW_PINS limit (currently 2) — planner decides appropriate daily volume
- Meta Ad Library competitor list — researcher identifies relevant competitors
- Whether to keep triple-cron pattern (01:00, 04:00, 07:00) or simplify to single daily run with retry

### Deferred Ideas (OUT OF SCOPE)

- Redis dedup layer (ORCH-02) — v2
- Prefect orchestration (ORCH-01) — v2
- Slack/Discord alerts for top discoveries (ADV-04) — v2
- Auto-scheduling launches (ADV-05) — v2
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-01 | Seen-content tracking persists across runs — content shown once never resurfaces | Postgres ON CONFLICT DO NOTHING already live in content.py; tiktok.ts and pinterest.ts must stop writing to file/sheet and POST to content API instead |
| DISC-02 | TikTok content filtered by engagement rate (views/followers), not flat view count | EnsembleData has `/tt/user/info` endpoint returning `followerCount`; per-account user info call needed before filtering |
| DISC-03 | Pinterest flow checks seen-content state before acting — no old pins reprocessed | Replace `getProcessedPinIds()` (Google Sheet CSV fetch) with a GET /api/content query against Postgres; daily-pinterest.yml also needs this check |
| DISC-04 | Every workflow step logs structured results and sends alert on failure | GITHUB_STEP_SUMMARY for structured logs; ravsamhq/notify-slack-action@v2 or curl to SLACK_WEBHOOK_URL with `if: failure()` |
| DISC-05 | All scraping settings in one central config file per source — no hardcoded values | Create `decarba-remixer/config/tiktok-accounts.json`, `pinterest-boards.json`, `meta-competitors.json`, `ppspy-settings.json` |
| SRC-01 | TikTok scraping automated (already runs in daily-scrape.yml; needs dedup switch to Postgres) | tiktok.ts already automated; change is retiring processed_tiktok.json and wiring writeToContentAPI |
| SRC-02 | Pinterest scraping automated (already runs in daily-scrape.yml; needs dedup switch to Postgres) | pinterest.ts already automated; change is retiring Google Sheet dedup and wiring writeToContentAPI |
| SRC-03 | Meta Ad Library scraping automated via GitHub Actions | New: Apify actor call in daily-scrape.yml; TypeScript wrapper to call actor + POST results to content API |
| SRC-04 | PPSpy scraping continues working reliably | Harden existing ppspy.ts: move search term to config; add structured output logging; cookie expiry alert |
</phase_requirements>

---

## Summary

Phase 2 is primarily a **refactoring + wiring phase** — not greenfield. Three of four scrapers already run in GitHub Actions. The work is: (1) switch TikTok and Pinterest from file/sheet-based dedup to Postgres via the content API that Phase 1 built, (2) add a new Meta Ad Library step using an Apify actor, (3) move all hardcoded settings to per-source config files, and (4) add structured failure alerting to all workflows.

The only genuinely new capability is Meta Ad Library automation. The canonical path is the Apify `apify/facebook-ads-scraper` actor (maintained by Apify itself, high usage, GraphQL-based — not DOM scraping) called via a new TypeScript module that mirrors the ppspy/tiktok/pinterest pattern and POSTs results to the content API.

TikTok's DISC-02 requirement (engagement rate = views/followers, not flat view count) requires adding a per-account EnsembleData `/tt/user/info` call to get `followerCount` before filtering. This is a single additional HTTP call per account. The current `MIN_REACH=3000` flat filter stays as a secondary guard after the rate filter.

**Primary recommendation:** Wire tiktok.ts and pinterest.ts to writeToContentAPI (copy the pattern from index.ts lines 47–99), add EnsembleData user info calls for engagement rate, create config JSON files, add one Apify-based Meta scraper module, and add `if: failure()` Slack + GITHUB_STEP_SUMMARY steps to daily-scrape.yml and daily-pinterest.yml.

---

## Standard Stack

### Core (already in use — no new installs needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| playwright | 1.58.2 | PPSpy + Pinterest browser automation | Already installed in package.json and daily-scrape.yml workflow |
| dotenv | 16.6.1 | Env var loading | Already used in all scrapers |
| TypeScript | 5.9.3 | Canonical scraper language | All Phase 2 scraper work stays in TypeScript per D-04 |

### New Additions

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| apify-client (npm) | 2.10.x | Call Apify actors from TypeScript | Meta Ad Library scraper module only |

**Version verification:**
```bash
npm view apify-client version
# Expected: 2.10.x (current as of March 2026)
```

**Installation (decarba-remixer only):**
```bash
cd decarba-remixer && npm install apify-client
```

### No Additional Libraries Needed

- Dedup: Postgres ON CONFLICT already live — no Redis, no new dedup library
- HTTP: native `fetch` already used in tiktok.ts for EnsembleData calls — no httpx needed
- Alerting: GitHub Actions curl + `$GITHUB_STEP_SUMMARY` — no SDK needed
- Config: JSON files read with `JSON.parse(readFileSync(...))` — no config library needed

---

## Architecture Patterns

### Recommended Config Structure

```
decarba-remixer/config/
├── settings.yaml           # existing — max_ads, trim_seconds (keep)
├── products.yaml           # existing — NEWGARMENTS catalog (keep)
├── tiktok-accounts.json    # NEW — account list, MIN_REACH, MAX_AGE_DAYS, MAX_CAROUSELS
├── pinterest-boards.json   # NEW — board URL, MAX_NEW_PINS
├── meta-competitors.json   # NEW — competitor page URLs, country code, ad_type
└── ppspy-settings.json     # NEW — search term(s), max_ads, winning_filter flag
```

### Pattern 1: writeToContentAPI (canonical — already in index.ts)

The existing pattern at `decarba-remixer/src/index.ts` lines 47–99 must be replicated in tiktok.ts and pinterest.ts directly (or extracted to a shared utility). The source field changes per scraper.

```typescript
// Source: decarba-remixer/src/index.ts lines 47-99
async function writeToContentAPI(ads: ScrapedAd[], source: string): Promise<{written: number, skipped: number}> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log(`[content-api] CONTENT_API_URL or DASHBOARD_SECRET not set — skipping`);
    return { written: 0, skipped: 0 };
  }

  let written = 0;
  let skipped = 0;

  for (const ad of ads) {
    try {
      const body = {
        content_id: ad.id,
        source,                          // "tiktok" | "pinterest" | "meta" | "ppspy"
        creative_url: ad.creativeUrl ?? null,
        thumbnail_url: ad.thumbnailUrl ?? null,
        ad_copy: ad.adCopy ?? null,
        metadata_json: JSON.stringify({
          reach: ad.reach,
          daysActive: ad.daysActive,
          platforms: ad.platforms,
          type: ad.type,
        }),
      };
      const resp = await fetch(`${contentApiUrl}/api/content`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${dashboardSecret}`,
        },
        body: JSON.stringify(body),
      });
      if (resp.ok) { written++; } else { skipped++; }
    } catch { skipped++; }
  }
  return { written, skipped };
}
```

The `source` parameter must be one of the VALID_SOURCES in content.py: `"ppspy" | "tiktok" | "pinterest" | "meta"`.

### Pattern 2: TikTok Dedup Switch (DISC-01 + SRC-01)

Current flow in tiktok.ts:
1. `getProcessedIds()` reads `scout/processed_tiktok.json`
2. Filter candidates against processedIds
3. `saveProcessedId()` writes back to the JSON file

New flow:
1. Remove `getProcessedIds()` and `saveProcessedId()` — the entire file-based dedup
2. `selectTopCarousels()` still runs (viral filter), but processedIds is always an empty Set
3. After selecting carousels, call `writeToContentAPI(ads, "tiktok")`
4. Dedup is handled by Postgres ON CONFLICT DO NOTHING — a duplicate POST simply returns the existing row without writing

**Critical:** The content_id for TikTok must be stable across runs. Current format: `tiktok_${username}_${postId}` — this is already stable (postId is TikTok's aweme_id). No change needed to the ID format.

### Pattern 3: TikTok Engagement Rate Filter (DISC-02)

Current filter uses flat `MIN_REACH = 3000` (play_count). Required: filter by engagement rate = play_count / follower_count per account.

EnsembleData `/tt/user/info` endpoint returns `stats.followerCount`. One call per account per run (13 accounts = 13 calls + 13 units).

```typescript
// New: fetch follower counts once before filtering
async function fetchFollowerCounts(accounts: string[]): Promise<Map<string, number>> {
  const counts = new Map<string, number>();
  for (const username of accounts) {
    const url = `https://ensembledata.com/apis/tt/user/info?username=${username}&token=${ENSEMBLEDATA_TOKEN}`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) { counts.set(username, 0); continue; }
      const data = await resp.json() as { data?: { stats?: { followerCount?: number } } };
      counts.set(username, data?.data?.stats?.followerCount ?? 0);
    } catch { counts.set(username, 0); }
    await delay(300);
  }
  return counts;
}

// Modified filter: engagement rate check
function meetsEngagementThreshold(playCount: number, followerCount: number, minRate: number): boolean {
  if (followerCount === 0) return playCount >= MIN_REACH_FALLBACK; // flat fallback if follower data missing
  return (playCount / followerCount) >= minRate;
}
```

Config in `tiktok-accounts.json`:
```json
{
  "accounts": ["fiveleafsclo", "thefitscene", ...],
  "min_engagement_rate": 0.15,
  "min_reach_fallback": 3000,
  "max_age_days": 14,
  "max_carousels": 2
}
```

`min_engagement_rate: 0.15` means 15% of followers viewed the post — aggressive threshold appropriate for streetwear/fashion carousels. Planner should validate against actual account data.

### Pattern 4: Pinterest Dedup Switch (DISC-01 + DISC-03)

Current `getProcessedPinIds()` in pinterest.ts fetches Google Sheet CSV and returns a Set of known pin IDs (read-only — no write-back).

Replacement: Query the content API for all known pinterest pin IDs.

```typescript
async function getProcessedPinIds(): Promise<Set<string>> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    console.log("[pinterest] Content API not configured — dedup disabled for this run");
    return new Set();
  }

  try {
    const resp = await fetch(`${contentApiUrl}/api/content?source=pinterest&limit=1000`, {
      headers: { "Authorization": `Bearer ${dashboardSecret}` },
    });
    if (!resp.ok) return new Set();
    const items = await resp.json() as Array<{ content_id: string }>;
    const ids = new Set(items.map(i => i.content_id.replace("pinterest_", "")));
    console.log(`[pinterest] ${ids.size} seen pin IDs from Postgres`);
    return ids;
  } catch (err) {
    console.error(`[pinterest] Failed to load seen IDs from Postgres: ${err}`);
    return new Set(); // fail open — better to re-discover than to skip all
  }
}
```

**Note:** This requires the content API to support a `GET /api/content?source=pinterest` query. Check Phase 1 content.py for whether this endpoint exists. If not, a minimal GET with filtering is needed (a Phase 2 task).

For `daily-pinterest.yml` (cloud_pinterest.py), the Python remake script also reads the Google Sheet for dedup. Per D-06/D-07, that script's dedup must also switch to Postgres. However, cloud_pinterest.py is Python. Pattern: use `requests.get(f"{CONTENT_API_URL}/api/content?source=pinterest", headers={"Authorization": f"Bearer {DASHBOARD_SECRET}"})`.

### Pattern 5: Meta Ad Library via Apify (SRC-03)

Actor choice: `apify/facebook-ads-scraper` — maintained by Apify itself (highest trust), uses GraphQL interception not DOM scraping, returns structured JSON with `adArchiveID` as unique ID, `pageName`, `snapshot.images`, `snapshot.videos`, `startDate`, `endDate`.

Input schema (key fields):
```json
{
  "advertiserUrls": [
    "https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=NL&q=Decarba&search_type=page",
    "https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=NL&q=SomeBrand&search_type=page"
  ],
  "count": 20,
  "country": "NL",
  "adType": "all",
  "activeAdsOnly": false
}
```

Alternative input mode: `searchTerms` (keyword-based) — less precise than page URL mode for competitor tracking. Use page URL mode for known competitors.

New TypeScript module: `decarba-remixer/src/scraper/meta.ts`

```typescript
import { ApifyClient } from "apify-client";
import type { ScrapedAd } from "./types.js";

function requireEnv(key: string): string { /* same pattern as other scrapers */ }

const APIFY_TOKEN = requireEnv("APIFY_TOKEN");

interface MetaAdResult {
  adArchiveID: string;
  pageName?: string;
  snapshot?: {
    images?: Array<{ original_image_url?: string }>;
    videos?: Array<{ video_hd_url?: string; video_preview_image_url?: string }>;
    body?: { text?: string };
  };
  startDate?: string;
  isActive?: boolean;
}

export async function scrapeMetaAds(config: MetaConfig): Promise<ScrapedAd[]> {
  const client = new ApifyClient({ token: APIFY_TOKEN });

  const run = await client.actor("apify/facebook-ads-scraper").call({
    advertiserUrls: config.advertiserUrls,
    count: config.maxAdsPerCompetitor ?? 10,
    country: config.country ?? "NL",
    adType: "all",
    activeAdsOnly: false,
  });

  const { items } = await client.dataset(run.defaultDatasetId).listItems();

  const ads: ScrapedAd[] = [];
  for (const item of items as MetaAdResult[]) {
    const imageUrl = item.snapshot?.images?.[0]?.original_image_url;
    const videoUrl = item.snapshot?.videos?.[0]?.video_hd_url;
    const creativeUrl = videoUrl ?? imageUrl ?? "";
    const type = videoUrl ? "video" : "image";

    if (!creativeUrl || !item.adArchiveID) continue;

    ads.push({
      id: `meta_${item.adArchiveID}`,
      type,
      creativeUrl,
      thumbnailUrl: item.snapshot?.videos?.[0]?.video_preview_image_url,
      adCopy: item.snapshot?.body?.text,
      reach: 0,
      daysActive: 0,
      startedAt: item.startDate ?? new Date().toISOString().split("T")[0],
      platforms: ["meta"],
      scrapedAt: new Date().toISOString(),
    });
  }

  return ads;
}
```

### Pattern 6: Structured Logging + Failure Alerts (DISC-04)

Every scraper step in `daily-scrape.yml` must:
1. Emit a structured summary line to `$GITHUB_STEP_SUMMARY`
2. Have a `if: failure()` step that POSTs to `SLACK_WEBHOOK_URL`

```yaml
# In each scraper step (example for TikTok):
- name: Scrape TikTok carousels
  id: tiktok
  if: steps.check.outputs.already_ran == 'false'
  run: |
    OUTPUT=$(npm run scrape:tiktok 2>&1)
    echo "$OUTPUT"
    # Parse structured result line and write to job summary
    RESULT=$(echo "$OUTPUT" | grep -E "^\[content-api\]" | tail -1)
    echo "| TikTok | $RESULT |" >> $GITHUB_STEP_SUMMARY
  timeout-minutes: 12

- name: Alert on TikTok failure
  if: failure() && steps.tiktok.outcome == 'failure'
  run: |
    curl -s -X POST "${{ secrets.SLACK_WEBHOOK_URL }}" \
      -H "Content-Type: application/json" \
      -d '{"text": ":red_circle: *daily-scrape* TikTok step failed — ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"}'
```

Simpler approach: one catch-all failure notification per job using `if: failure()` at the job level — post a single message with which job failed. Less noisy than per-step alerts.

```yaml
# End of each workflow job:
- name: Notify Slack on failure
  if: failure()
  run: |
    curl -s -X POST "${{ secrets.SLACK_WEBHOOK_URL }}" \
      -H "Content-Type: application/json" \
      -d "{\"text\": \":red_circle: *${{ github.workflow }}* failed on ${{ github.ref_name }} — <${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View run>\"}"
```

**GitHub GITHUB_STEP_SUMMARY usage:**
```bash
echo "## Scrape Results $(date +%Y-%m-%d)" >> $GITHUB_STEP_SUMMARY
echo "| Source | Found | New | Skipped | Errors |" >> $GITHUB_STEP_SUMMARY
echo "|--------|-------|-----|---------|--------|" >> $GITHUB_STEP_SUMMARY
echo "| PPSpy  | 15    | 12  | 3       | 0      |" >> $GITHUB_STEP_SUMMARY
```

This is HIGH confidence — confirmed in GitHub docs.

### Pattern 7: Central Config Loading (DISC-05)

```typescript
// decarba-remixer/src/scraper/config.ts (new utility)
import { readFileSync } from "fs";
import { join } from "path";

const CONFIG_DIR = join(import.meta.dirname, "../../config");

export function loadConfig<T>(filename: string): T {
  const path = join(CONFIG_DIR, filename);
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as T;
  } catch (err) {
    throw new Error(`Failed to load config ${filename}: ${err}`);
  }
}
```

### Anti-Patterns to Avoid

- **Writing `scout/processed_tiktok.json` from the workflow**: The workflow currently commits this file via `git add scout/processed_tiktok.json`. Remove this after tiktok.ts stops writing to it.
- **Calling `getProcessedPinIds()` from Pinterest with no write-back**: The current pattern is read-only dedup (reads sheet, never writes back) — new pins will be re-seen on next run. The Postgres pattern is atomic: POST to content API immediately after discovering, ON CONFLICT absorbs re-discovery.
- **Calling Apify actor synchronously with no timeout**: Apify runs can take 2-5 minutes. Use `client.actor().call()` which waits for completion, but set a `timeout` parameter. Default is no timeout.
- **Hardcoding `if: steps.check.outputs.already_ran == 'false'` on the failure alert**: The failure alert step must use `if: failure()` alone — not gated on `already_ran`. If the check step itself fails, you still want an alert.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Meta Ad Library scraping | Custom Playwright script against facebook.com/ads/library | `apify/facebook-ads-scraper` actor | Meta actively detects automation; Apify actors use GraphQL interception + proxy rotation; maintained by Apify team |
| Per-run dedup | In-memory Set persisted to JSON/git | Postgres ON CONFLICT DO NOTHING | JSON file creates merge conflicts in multi-cron workflows; Postgres is already live from Phase 1 |
| Slack alerting | Custom Slack API client | `curl` POST to incoming webhook URL | One-liner; no SDK needed for simple failure notifications |
| TikTok follower data | Scraping TikTok profile pages with Playwright | EnsembleData `/tt/user/info` endpoint | EnsembleData already in use and paid for; profile scraping is fragile and rate-limited |

**Key insight:** The hardest problem in this phase (Meta Ad Library) is already solved by an Apify actor. The main work is wiring existing patterns.

---

## Common Pitfalls

### Pitfall 1: Commit Step Still Adds `scout/processed_tiktok.json`

**What goes wrong:** After removing file-based dedup from tiktok.ts, the workflow's commit step (`git add scout/processed_tiktok.json`) either fails (file gone) or commits a stale file.
**Why it happens:** The commit step in `daily-scrape.yml` line 104 explicitly adds `scout/processed_tiktok.json`.
**How to avoid:** Remove `scout/processed_tiktok.json` from the `git add` command in the workflow. The file should be archived (moved to `archive/`) not deleted, to preserve history.
**Warning signs:** Workflow commit step error: "pathspec 'scout/processed_tiktok.json' did not match any files".

### Pitfall 2: Pinterest Dedup Fails Open When Content API Unreachable

**What goes wrong:** If CONTENT_API_URL is not set or Railway is down, `getProcessedPinIds()` returns an empty Set — all pins look new. The scraper processes every pin on the board (up to MAX_NEW_PINS=2), which is safe due to the limit, but will keep rediscovering the same pins every day.
**Why it happens:** Fail-open is the correct choice for scraping (better to re-discover than to skip everything), but without Postgres, dedup is disabled.
**How to avoid:** Log a clear warning when falling back to empty Set. The content API's ON CONFLICT DO NOTHING will absorb re-posts without creating duplicates. The dashboard will just show re-discovered items that already exist in "discovered" status — Phase 3 dashboard handles this by showing only unprocessed items.
**Warning signs:** `[pinterest] Content API not configured — dedup disabled` in workflow logs.

### Pitfall 3: TikTok User Info Calls Add 13 Units Per Run

**What goes wrong:** Adding EnsembleData user info calls for engagement rate filter uses 13 additional API units per run (one per account). This increases daily EnsembleData consumption from ~13 units (posts) to ~26 units.
**Why it happens:** Each EnsembleData endpoint call consumes units based on the endpoint type.
**How to avoid:** Cache follower counts in memory across the run (already handled if called once before the filter loop). Consider caching to a JSON file with a 24h TTL to avoid calling on every run — but the simplest approach is to accept the 2x unit cost.
**Warning signs:** EnsembleData rate limit errors or unexpected billing increases.

### Pitfall 4: Apify Actor Run Timeout in GitHub Actions

**What goes wrong:** `client.actor("apify/facebook-ads-scraper").call(input)` waits synchronously for the actor to complete. If the actor takes longer than the workflow step timeout, the step fails with a timeout error — but the Apify run continues and costs money.
**Why it happens:** Apify actor runs for many ads can take 3-10 minutes depending on competitor count.
**How to avoid:** Set `timeout: 300` (5 minutes) on the actor call. Set `timeout-minutes: 8` on the workflow step. Keep `maxAdsPerCompetitor` to ≤10 to bound run time. Start with 3-5 competitors.
**Warning signs:** Workflow step times out but Apify dashboard shows run still running/succeeded.

### Pitfall 5: Pinterest Board URL Hardcoded in Two Places

**What goes wrong:** `pinterest.ts` has `BOARD_URL` hardcoded at line 7. `cloud_pinterest.py` has `BOARD_ID` hardcoded at line 45. After moving to config files, one of these gets updated while the other doesn't.
**Why it happens:** Two separate implementations scrape the same board.
**How to avoid:** `pinterest-boards.json` is the single source of truth for the board URL. Both pinterest.ts and cloud_pinterest.py must read from it (TypeScript reads JSON directly; Python reads JSON via `json.load()`).
**Warning signs:** pinterest.ts scrapes the correct board but cloud_pinterest.py uses stale BOARD_ID.

### Pitfall 6: PPSpy Cookie Expiry Silent Failure

**What goes wrong:** ppspy.ts throws `Error: PPSpy session cookies expired` but the workflow step is marked as `continue-on-error: true` (or is non-fatal). The scraper returns 0 ads but no alert fires.
**Why it happens:** Current ppspy.ts correctly detects expired cookies and throws — but if the step failure doesn't trigger an alert, the operator won't know PPSpy has been dark for days.
**How to avoid:** The `if: failure()` Slack alert pattern handles this — cookie expiry causes a step failure, which triggers the alert. Do NOT use `continue-on-error: true` on the PPSpy step.
**Warning signs:** Dashboard shows 0 PPSpy ads for multiple consecutive days with no alert.

---

## Code Examples

### Read Config JSON (TypeScript)

```typescript
// Source: pattern from decarba-remixer/src/index.ts loadSettings()
import { readFileSync } from "fs";
import { join } from "path";

interface TikTokConfig {
  accounts: string[];
  min_engagement_rate: number;
  min_reach_fallback: number;
  max_age_days: number;
  max_carousels: number;
}

function loadTikTokConfig(): TikTokConfig {
  const path = join(import.meta.dirname, "../../config/tiktok-accounts.json");
  return JSON.parse(readFileSync(path, "utf-8")) as TikTokConfig;
}
```

### Structured Result Output for GITHUB_STEP_SUMMARY

```typescript
// Emit structured result at end of each scraper
function logScraperResult(source: string, found: number, written: number, skipped: number, errors: number): void {
  console.log(`[result] source=${source} found=${found} written=${written} skipped=${skipped} errors=${errors}`);
}
```

```bash
# In workflow step, parse and write to summary:
OUTPUT=$(npm run scrape:tiktok 2>&1)
echo "$OUTPUT"
RESULT=$(echo "$OUTPUT" | grep "^\[result\]" | tail -1)
FOUND=$(echo "$RESULT" | grep -oP 'found=\K\d+')
WRITTEN=$(echo "$RESULT" | grep -oP 'written=\K\d+')
SKIPPED=$(echo "$RESULT" | grep -oP 'skipped=\K\d+')
ERRORS=$(echo "$RESULT" | grep -oP 'errors=\K\d+')
echo "| TikTok | $FOUND | $WRITTEN | $SKIPPED | $ERRORS |" >> $GITHUB_STEP_SUMMARY
```

### Pinterest Dedup via Content API (Python, for cloud_pinterest.py)

```python
import os, requests

def get_seen_pin_ids() -> set:
    """Replace Google Sheet CSV read with Postgres query via content API."""
    api_url = os.getenv("CONTENT_API_URL")
    secret = os.getenv("DASHBOARD_SECRET")
    if not api_url or not secret:
        logging.warning("Content API not configured — dedup disabled")
        return set()
    try:
        resp = requests.get(
            f"{api_url}/api/content",
            params={"source": "pinterest", "limit": 1000},
            headers={"Authorization": f"Bearer {secret}"},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json()
        return {item["content_id"].replace("pinterest_", "") for item in items}
    except Exception as e:
        logging.error(f"Failed to load seen IDs: {e}")
        return set()
```

### Apify Meta Actor Call (TypeScript skeleton)

```typescript
// Source: Apify client docs + actor apify/facebook-ads-scraper
import { ApifyClient } from "apify-client";

const client = new ApifyClient({ token: requireEnv("APIFY_TOKEN") });

const run = await client.actor("apify/facebook-ads-scraper").call({
  advertiserUrls: config.advertiserUrls,
  count: 10,
  country: "NL",
  adType: "all",
  activeAdsOnly: false,
}, { timeout: 300 });  // 5 minute timeout

const { items } = await client.dataset(run.defaultDatasetId).listItems();
// items[0].adArchiveID, items[0].snapshot.images[0].original_image_url
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| File-based dedup (processed_tiktok.json) | Postgres ON CONFLICT DO NOTHING | Phase 2 | No more git merge conflicts from cron race conditions |
| Google Sheet CSV read for Pinterest dedup | Postgres content API query | Phase 2 | Write-back dedup — pins actually marked as seen |
| Manual Meta Ad Library scouting (daily_discovery.py + Claude invocation) | Apify actor automated in daily-scrape.yml | Phase 2 | Meta becomes a fully automated source |
| Flat view count filter for TikTok | Engagement rate (views/followers) per account | Phase 2 | Catches viral content from small accounts; filters low-views on mega-accounts |
| Hardcoded account lists in scraper files | Per-source JSON config files | Phase 2 | Adding/removing competitors requires no code change |

---

## Open Questions

1. **Does `GET /api/content?source=pinterest` exist in Phase 1's content.py?**
   - What we know: content.py was written in Phase 1 but only POST /api/content and PATCH /api/content/{id}/status were confirmed in the phase description.
   - What's unclear: Whether GET with source filter is implemented.
   - Recommendation: Planner must add a task to inspect content.py routes and add `GET /api/content?source={source}&limit={n}` if missing. This is a small addition (5-10 lines in the existing router).

2. **EnsembleData unit cost for user/info endpoint**
   - What we know: user/posts uses 1 unit per account. user/info cost not confirmed in docs.
   - What's unclear: Could be 1 or more units per call.
   - Recommendation: Planner note this as an implementation-time check. If user/info is expensive, cache follower counts to `decarba-remixer/output/cache/follower-counts.json` with 7-day TTL.

3. **NEWGARMENTS Meta competitor Facebook page URLs**
   - What we know: scout/config.py has subscription-box brands (wrong domain). No NEWGARMENTS competitor list exists.
   - What's unclear: Which streetwear brands are NEWGARMENTS' direct competitors on Meta.
   - Recommendation (Claude's Discretion): Based on product catalog (checkered zippers, Y2K hoodies, graphic jeans — streetwear/y2k niche), likely competitors include: Decarba (already tracked), Strhvn, Copenhagenlove, FIVELEAF, similar European streetwear DTC brands. Planner should create meta-competitors.json with 3-5 page URLs to start. Owner can update without code changes.

4. **Does apify/facebook-ads-scraper support advertiser page URL input or only keyword search?**
   - What we know: Input schema includes both `advertiserUrls` (array of Ad Library URLs) and `searchTerms` keywords. Page URL mode is more precise.
   - What's unclear: Whether the page URL must be the Ad Library URL or the Facebook Page URL.
   - Recommendation: Use the Ad Library search URL format: `https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=NL&q={PageName}&search_type=page`. Verify with a test run before committing to the plan.

5. **Triple-cron vs. single daily run (Claude's Discretion)**
   - What we know: Current 01:00/04:00/07:00 triple-cron runs have a "skip if already done today" guard. The guard works by grepping git log for a commit with today's date.
   - Recommendation: Keep the triple-cron. The skip guard works reliably (confirmed by existing workflow). Adding a Meta step increases total runtime but stays under 30 minutes. Single-run with retry would require Prefect (deferred to v2).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | All TypeScript scrapers | ✓ | v24.14.0 (local), v20 (Actions) | — |
| Playwright (chromium) | PPSpy, Pinterest | ✓ | 1.58.2 | — |
| APIFY_TOKEN | Meta Ad Library | ✓ (in env per CLAUDE.md) | — | — |
| ENSEMBLEDATA_TOKEN | TikTok scraper | ✓ (in env per daily-scrape.yml) | — | — |
| CONTENT_API_URL | All scrapers (Postgres write) | Conditionally — set after Phase 1 Railway deploy | — | Scrapers log and skip write (non-fatal) |
| DASHBOARD_SECRET | All scrapers (auth) | Conditionally — set after Phase 1 Railway deploy | — | Same non-fatal skip |
| SLACK_WEBHOOK_URL | Failure alerting | Not yet set (new secret) | — | No alerts — blocking for DISC-04 |

**Missing dependencies with no fallback:**
- `SLACK_WEBHOOK_URL` GitHub Actions secret — must be created before failure alerting works (DISC-04). Owner must set up a Slack incoming webhook and add the secret.

**Missing dependencies with fallback:**
- `CONTENT_API_URL` and `DASHBOARD_SECRET` — scrapers have non-fatal guards; if Railway not yet deployed, scraping continues but Postgres writes are skipped.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected — no jest.config, vitest.config, or test directories found |
| Config file | Wave 0 gap — needs creation |
| Quick run command | `cd decarba-remixer && npx vitest run --reporter=verbose` (after Wave 0 setup) |
| Full suite command | `cd decarba-remixer && npx vitest run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | Duplicate content_id POST returns 200/existing row, not 201/new row | Integration (mock content API) | `npx vitest run src/scraper/__tests__/dedup.test.ts` | ❌ Wave 0 |
| DISC-02 | Carousel with 500 views and 10k followers (5% rate) filtered out at 15% threshold | Unit | `npx vitest run src/scraper/__tests__/tiktok-filter.test.ts` | ❌ Wave 0 |
| DISC-03 | Pinterest dedup returns correct Set from mocked content API response | Unit | `npx vitest run src/scraper/__tests__/pinterest-dedup.test.ts` | ❌ Wave 0 |
| DISC-04 | Workflow failure triggers Slack POST — manual smoke test only | Manual-only | n/a — requires GitHub Actions environment | — |
| DISC-05 | Config load throws on missing file, returns typed object on success | Unit | `npx vitest run src/scraper/__tests__/config.test.ts` | ❌ Wave 0 |
| SRC-01 | scrapeTiktok() returns ScrapedAd[] with no file writes to processed_tiktok.json | Unit (spy on fs) | `npx vitest run src/scraper/__tests__/tiktok.test.ts` | ❌ Wave 0 |
| SRC-02 | scrapePinterest() calls content API for dedup, not Sheet CSV | Unit (mock fetch) | `npx vitest run src/scraper/__tests__/pinterest.test.ts` | ❌ Wave 0 |
| SRC-03 | scrapeMetaAds() returns ScrapedAd[] with `id` prefixed "meta_" | Unit (mock apify-client) | `npx vitest run src/scraper/__tests__/meta.test.ts` | ❌ Wave 0 |
| SRC-04 | scrapePPSpy() reads search term from config, not hardcoded string | Unit | `npx vitest run src/scraper/__tests__/ppspy-config.test.ts` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd decarba-remixer && npx vitest run --reporter=dot`
- **Per wave merge:** `cd decarba-remixer && npx vitest run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `decarba-remixer/vitest.config.ts` — vitest setup for Node.js ESM environment
- [ ] `decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts` — engagement rate filter unit tests
- [ ] `decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts` — Postgres dedup via mocked fetch
- [ ] `decarba-remixer/src/scraper/__tests__/meta.test.ts` — Apify actor mock
- [ ] `decarba-remixer/src/scraper/__tests__/config.test.ts` — config loader
- [ ] `decarba-remixer/src/scraper/__tests__/dedup.test.ts` — end-to-end dedup with mock content API
- [ ] `decarba-remixer/package.json` — add `vitest` to devDependencies; add `"test": "vitest run"` script

**Note:** vitest is preferred over jest for this codebase because it supports ESM natively (the codebase uses `import.meta.dirname`, NodeNext modules, and `.js` extensions throughout — jest requires additional transform configuration for this).

---

## Project Constraints (from CLAUDE.md)

All directives apply to Phase 2 work. Key ones for this phase:

| Directive | Implication for Phase 2 |
|-----------|------------------------|
| NEVER hardcode API keys or secrets | Config JSON files contain URLs and thresholds only, never tokens. All tokens stay in `.env` / GitHub Actions secrets |
| ALWAYS use `process.env.*` (TS) or `os.getenv()` (Python) | requireEnv() pattern already in all scrapers — extend to all new modules |
| GitHub Actions secrets via `${{ secrets.* }}` — never inline | SLACK_WEBHOOK_URL, APIFY_TOKEN added to workflow env block via secrets |
| NEVER `.env` files in git | `.env.example` updated with new var names: SLACK_WEBHOOK_URL (new), CONTENT_API_URL (new), DASHBOARD_SECRET (new) |
| All secrets go in `.env` only | meta-competitors.json contains page URLs (not sensitive); APIFY_TOKEN stays in env |
| Pre-commit hook will block commits with secrets | No real values in any committed file |
| Shopify: Zapier MCP only | Not relevant to Phase 2 |
| GSD workflow enforcement | All file changes go through /gsd:execute-phase |

---

## Sources

### Primary (HIGH confidence)

- Direct code read: `decarba-remixer/src/scraper/tiktok.ts` — current file-based dedup implementation
- Direct code read: `decarba-remixer/src/scraper/pinterest.ts` — current Google Sheet dedup implementation
- Direct code read: `decarba-remixer/src/index.ts` lines 47–99 — writeToContentAPI pattern
- Direct code read: `ad-command-center/routes/content.py` — Postgres ON CONFLICT, VALID_SOURCES enum
- Direct code read: `.github/workflows/daily-scrape.yml` — current workflow structure
- EnsembleData guide: https://ensembledata.com/guide/guides/tiktok/user-info/ — `stats.followerCount` field confirmed
- GitHub Docs: GITHUB_STEP_SUMMARY confirmed in workflow commands docs

### Secondary (MEDIUM confidence)

- Apify store search results: `apify/facebook-ads-scraper` identified as Apify-maintained actor; output fields `adArchiveID`, `snapshot.images`, `snapshot.videos` referenced from search results
- WebSearch: ravsamhq/notify-slack-action@v2 and `if: failure()` curl pattern confirmed from multiple GitHub Marketplace sources

### Tertiary (LOW confidence — validate before implementing)

- Apify actor input schema (`advertiserUrls` vs `searchTerms`) — confirmed from blog post but not from direct input-schema page read; validate with test run
- EnsembleData user/info unit cost — not confirmed; verify before scaling to 13 accounts per run
- `GET /api/content?source={source}` endpoint existence — Phase 1 code not fully read; assumed from content API design pattern

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing code read directly; only apify-client is new
- Architecture: HIGH — patterns derived from existing working code in the repo
- Pitfalls: HIGH — derived from direct analysis of the existing code paths being changed
- Meta Ad Library actor: MEDIUM — actor identity confirmed, exact input schema needs test validation
- EnsembleData unit cost: LOW — not documented; needs verification before planning unit budget

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (30 days; Apify actor schemas change infrequently)
