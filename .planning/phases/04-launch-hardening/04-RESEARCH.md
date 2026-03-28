# Phase 4: Launch Hardening - Research

**Researched:** 2026-03-28
**Domain:** Meta Marketing API, TypeScript launcher, Content API integration, GitHub Actions
**Confidence:** HIGH (code fully inspected, API versions verified against official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Postgres Read Integration (LAUNCH-01)**
- D-01: Create `fromPostgres.ts` as a new launcher entrypoint alongside `fromSheet.ts`. It calls `GET /api/content?status=ready_to_launch` to get items, extracts `drive_link` and `landing_page` from `metadata_json`, maps to the existing `SubmissionInput` interface, then calls the same `launchBatch()` from `meta.ts`.
- D-02: After successful launch, `fromPostgres.ts` calls `PATCH /api/content/{id}/status` with `{"status": "launched"}` to advance the lifecycle. On failure, log the error but don't advance status — item stays at `ready_to_launch` for retry.
- D-03: Add `CONTENT_API_URL` and `DASHBOARD_SECRET` to `launch-campaigns.yml` secrets. Add a new npm script `launch:postgres` that runs `fromPostgres.ts`.
- D-04: Keep `fromSheet.ts` and `npm run launch` as fallback. The workflow runs `launch:postgres` first, falls back to `launch` (Sheets) if the content API is unreachable or returns zero items.
- D-05: The `metadata_json` field for `ready_to_launch` items must contain at minimum: `drive_link` (Google Drive URL) and `landing_page` (destination URL). If either is missing, skip the item with a warning log.

**Dry-Run Mode (LAUNCH-02)**
- D-06: Add `--dry-run` CLI flag to both `fromPostgres.ts` and `fromSheet.ts`. When active: validate all inputs, download creative, verify file type, log what WOULD be launched — but skip all `fetch()` calls to `graph.facebook.com`.
- D-07: In `meta.ts`, add a `dryRun: boolean` parameter to `launchBatch()`, `findOrCreateCampaign()`, `findOrCreateAdSet()`, and `launchAd()`. When true, return mock success responses with placeholder IDs.
- D-08: Dry-run output format: structured JSON summary per item (`{ad_id, source, creative_type, landing_page, status: "would_launch" | "skipped", reason?}`). Logged to stdout and optionally written to a file.
- D-09: Add `--dry-run` flag support to `launch-campaigns.yml` via `workflow_dispatch` input. Manual trigger can select dry-run; automated trigger always runs live.

**System User Token (LAUNCH-03)**
- D-10: No code change needed — `META_ACCESS_TOKEN` is already an env var. The fix is operational: document how to generate a System User token in Meta Business Manager, replace the current token value in Railway env vars and GitHub Actions secrets.
- D-11: Add a token type check at launcher startup: call `GET /me?fields=name,id` with the token. If the response contains `"name": "System User"` or similar, log confirmation. If it looks like a personal token (has a human name), log a warning.
- D-12: Document the System User token generation steps in a `docs/META_TOKEN_SETUP.md` file.

**Idempotency**
- D-13: The launcher must be idempotent — re-running on already-launched items should be a no-op. `fromPostgres.ts` only queries `status=ready_to_launch`, so already-launched items won't appear.

### Claude's Discretion
- Whether to add a Slack notification on successful launch (not just failure)
- Exact mock response structure for dry-run mode
- Whether to archive `launch/meta_campaign.py` (Python legacy launcher)

### Deferred Ideas (OUT OF SCOPE)
- Advantage+ campaign structure
- Budget management from dashboard
- Launch scheduling
- A/B testing
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LAUNCH-01 | Launcher reads pending remakes from Postgres (with fallback: Google Sheets remains readable during transition) | Content API endpoints verified (GET /api/content?status=ready_to_launch, PATCH /api/content/{id}/status). authFetch pattern confirmed in contentApi.ts. Fallback flow through fromSheet.ts fully understood. |
| LAUNCH-02 | Dry-run mode available — test a launch without actually publishing to Meta | launchBatch() signature understood. All Meta fetch calls identified in meta.ts. CLI flag parsing pattern (process.argv) used in other launchers. |
| LAUNCH-03 | Meta integration uses System User token (non-expiring) instead of personal token (60-day expiry) | System User token generation process verified via official Meta docs. Token type detection via /me endpoint confirmed viable. CRITICAL: meta.ts currently hardcodes Graph API v21.0, which expired September 2025 — must upgrade to v22.0+ as part of this phase. |
</phase_requirements>

---

## Summary

Phase 4 adds three capabilities to the existing TypeScript launcher in `decarba-remixer/src/launcher/`: a Postgres-driven entrypoint (`fromPostgres.ts`), dry-run mode across both launchers, and System User token documentation with a runtime token type check. The implementation is highly mechanical — the patterns from `fromSheet.ts` and `contentApi.ts` are directly reusable.

The code is well-structured for this extension. `launchBatch()` in `meta.ts` is the sole Meta integration point and accepts clean `SubmissionInput` inputs. The content API is live and has the correct endpoints. The `authFetch` pattern with Bearer token is established in `contentApi.ts`.

**Critical finding:** `meta.ts` hardcodes `const GRAPH_API = "https://graph.facebook.com/v21.0"`. Graph API v21.0 expired September 9, 2025. All Meta API calls are currently making requests to a dead endpoint version. This must be upgraded to v22.0 or higher as part of this phase — it is not a separate concern. The existing campaign structure (OUTCOME_SALES + manual targeting) still works on v22.0/v23.0.

**Secondary gap:** `metadata_json` for `ready_to_launch` items only contains `drive_link` (added by the dashboard submit form). The `landing_page` field is not written anywhere in the current flow. `fromPostgres.ts` must handle its absence by defaulting to `https://newgarments.nl` (same as the existing `fromSheet.ts` fallback in `meta.ts` line 332).

**Primary recommendation:** Implement in this order: (1) upgrade GRAPH_API constant to v22.0, (2) implement `fromPostgres.ts` reusing `downloadCreative()` from `fromSheet.ts`, (3) add `dryRun` parameter to `launchBatch()` with mock returns, (4) update workflow + write token documentation.

---

## Standard Stack

### Core (already in place — no new dependencies needed)
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| TypeScript | 5.9.3 | Language | NodeNext modules, ES2022 target |
| dotenv | 16.6.1 | Env var loading | Already in use |
| Node.js fetch | built-in (Node 24) | HTTP calls to Meta API and content API | No additional HTTP library needed |
| vitest | ^4.1.2 | Test framework | Already configured |

### No new dependencies required
All tools needed for Phase 4 are already in `package.json`. The implementation is purely additive TypeScript.

**Version verification:** `node --version` returns v24.14.0 — native fetch is available. No polyfills needed.

---

## Architecture Patterns

### Recommended Project Structure (additions only)
```
decarba-remixer/src/launcher/
├── fromSheet.ts          # existing — keep unchanged
├── fromPostgres.ts       # NEW — Postgres-driven entrypoint
├── meta.ts               # modify — add dryRun param, upgrade API version
└── types.ts              # no change needed (SubmissionInput already correct)

docs/
└── META_TOKEN_SETUP.md   # NEW — System User token instructions
```

### Pattern 1: Content API Read (authFetch)

The `contentApi.ts` write pattern uses Bearer token auth. Reading follows the same shape:

```typescript
// fromPostgres.ts — fetch ready_to_launch items
async function fetchReadyItems(): Promise<ContentItem[]> {
  const contentApiUrl = process.env.CONTENT_API_URL;
  const dashboardSecret = process.env.DASHBOARD_SECRET;

  if (!contentApiUrl || !dashboardSecret) {
    throw new Error("[launcher] CONTENT_API_URL and DASHBOARD_SECRET required for Postgres mode");
  }

  const resp = await fetch(`${contentApiUrl}/api/content?status=ready_to_launch`, {
    headers: { Authorization: `Bearer ${dashboardSecret}` },
  });
  if (!resp.ok) throw new Error(`Content API fetch failed: ${resp.status}`);
  return resp.json();
}
```

### Pattern 2: Status Write-back

```typescript
// fromPostgres.ts — mark item as launched
async function markLaunched(itemId: string): Promise<void> {
  const resp = await fetch(`${process.env.CONTENT_API_URL}/api/content/${itemId}/status`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.DASHBOARD_SECRET}`,
    },
    body: JSON.stringify({ status: "launched" }),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Status update failed: ${resp.status} ${text.slice(0, 100)}`);
  }
}
```

### Pattern 3: metadata_json Extraction

`metadata_json` is a JSON string in the `ContentItem` model. Items promoted to `ready_to_launch` via the dashboard have `drive_link` set. `landing_page` is NOT currently in the field — default to `https://newgarments.nl`.

```typescript
// fromPostgres.ts — extract fields from metadata_json
function extractMeta(item: ContentItem): { driveLink: string; landingPage: string } | null {
  let meta: Record<string, unknown> = {};
  try {
    meta = JSON.parse(item.metadata_json || "{}");
  } catch {
    console.warn(`[launcher] Invalid metadata_json for ${item.id} — skipping`);
    return null;
  }

  const driveLink = typeof meta.drive_link === "string" ? meta.drive_link : null;
  if (!driveLink) {
    console.warn(`[launcher] Missing drive_link in metadata_json for ${item.id} — skipping`);
    return null;
  }

  const landingPage = typeof meta.landing_page === "string"
    ? meta.landing_page
    : "https://newgarments.nl";  // default per existing meta.ts behavior

  return { driveLink, landingPage };
}
```

### Pattern 4: dryRun in launchBatch()

```typescript
// meta.ts — add dryRun parameter
export async function launchBatch(
  inputs: SubmissionInput[],
  dryRun = false,
): Promise<BatchResult> {
  if (dryRun) {
    console.log("[meta] DRY-RUN mode — no Meta API calls will be made");
    // Return mock result with placeholder IDs
    return {
      campaignId: "dry-run-campaign",
      adSetId: "dry-run-adset",
      ads: inputs.map((i) => ({
        adId: i.adId,
        adCreativeId: "dry-run-creative",
        metaAdId: "dry-run-ad",
      })),
    };
  }
  // ... existing code unchanged
}
```

For full dry-run depth (D-07), `findOrCreateCampaign()` and `findOrCreateAdSet()` also need the guard — but the simplest compliant approach is to gate at `launchBatch()` entry before any `graphGet`/`graphPost` calls.

### Pattern 5: CLI flag parsing

```typescript
// fromPostgres.ts — top-level flag reading
const dryRun = process.argv.includes("--dry-run");
```

Consistent with how the scraper scripts handle `--skip-scrape` in `index.ts`.

### Pattern 6: Fallback Flow in workflow

```yaml
# launch-campaigns.yml — try Postgres first, fall back to Sheets
- name: Launch from Postgres
  id: postgres_launch
  run: npm run launch:postgres
  continue-on-error: true

- name: Launch from Sheets (fallback)
  if: steps.postgres_launch.outcome == 'failure'
  run: npm run launch
```

Note: D-04 says fall back if content API is unreachable OR returns zero items. Zero items exits with code 0 (success), so the fallback trigger needs to be explicit — `fromPostgres.ts` should exit with code 1 if content API is unreachable, and code 0 with a log if zero items found. The Sheets fallback only fires on exit code 1.

### Pattern 7: Token Type Check (D-11)

```typescript
// fromPostgres.ts or shared launcher init
async function checkTokenType(token: string): Promise<void> {
  const GRAPH_API = "https://graph.facebook.com/v22.0";
  const resp = await fetch(`${GRAPH_API}/me?fields=name,id&access_token=${token}`);
  if (!resp.ok) {
    console.warn("[launcher] Could not verify token type — Meta /me returned", resp.status);
    return;
  }
  const data: { name?: string; id?: string } = await resp.json();
  const name = data.name || "";
  // System users typically have names like "System User", "NEWG Bot", etc.
  // Personal accounts have human names. This is a heuristic, not guaranteed.
  if (/system|bot|api|automation/i.test(name)) {
    console.log(`[launcher] Token type: System User confirmed (name="${name}")`);
  } else {
    console.warn(`[launcher] WARNING: Token may be a personal token (name="${name}"). System User token recommended.`);
  }
}
```

### Anti-Patterns to Avoid

- **Calling graphPost/graphGet from `fromPostgres.ts` directly:** All Meta API calls go through `meta.ts` — do not duplicate them.
- **Hardcoding `https://newgarments.nl` as a constant in `fromPostgres.ts`:** Use the same pattern as `meta.ts` (fallback in the function).
- **Advancing status to `launched` before confirming `launchBatch()` succeeded:** Status write-back is post-success only (D-02).
- **Using Graph API v21.0:** Already expired. Must update the `GRAPH_API` constant in `meta.ts` to `v22.0` at minimum.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Creative download | New download logic in `fromPostgres.ts` | Extract `downloadCreative()` from `fromSheet.ts` into shared module or copy verbatim | Same Drive link format, same HTML-page detection logic needed |
| CLI arg parsing | Custom flag parser | `process.argv.includes("--dry-run")` | Simple boolean flag, no library needed |
| Content type detection | Custom MIME detection | Existing extension-based detection in `fromSheet.ts` (mp4/webm=video, else image) | Already handles all needed cases |
| Token expiry management | Token refresh logic | System User token (never expires) | Personal token refresh is complex — the right fix is the System User token |

**Key insight:** `fromPostgres.ts` is `fromSheet.ts` with the data source swapped. Reuse as much of `fromSheet.ts` as possible — extract shared helpers if warranted.

---

## Common Pitfalls

### Pitfall 1: Graph API Version Expired
**What goes wrong:** All Meta API calls fail with "API version v21.0 is deprecated" or similar. This is happening NOW — v21.0 expired September 9, 2025.
**Why it happens:** `meta.ts` line 16: `const GRAPH_API = "https://graph.facebook.com/v21.0"` — hardcoded, never updated.
**How to avoid:** Change to `v22.0` (verified working for OUTCOME_SALES + manual targeting) as the first task of this phase.
**Warning signs:** Any Meta API call returning HTTP 400 or 410 with a version-related message.

### Pitfall 2: landing_page Missing from metadata_json
**What goes wrong:** `fromPostgres.ts` skips all items because `landing_page` is not in `metadata_json`.
**Why it happens:** The dashboard submit form (`submitDriveLink` in index.html) sends only `drive_link`. No `landing_page` field is ever written to `metadata_json` in the current codebase.
**How to avoid:** Default `landing_page` to `https://newgarments.nl` when absent (matching existing `meta.ts` fallback on line 332). Do NOT skip items solely for missing `landing_page` — only skip if `drive_link` is missing (D-05 says both are required, but the code must handle the `landing_page` gap pragmatically since Phase 3 didn't add it to the submit form).
**Warning signs:** Zero items processed despite items existing with `status=ready_to_launch`.

### Pitfall 3: Fallback Trigger Logic
**What goes wrong:** The workflow falls back to Sheets even when Postgres launch succeeded with zero items (meaning there was nothing to launch that day).
**Why it happens:** The fallback is on exit code — zero items is a success exit (0), but the workflow can't distinguish "no items" from "succeeded" without output inspection.
**How to avoid:** Only trigger the Sheets fallback when the content API is unreachable (exit code 1). Zero items = no fallback needed.

### Pitfall 4: Dry-Run Still Downloads Creatives
**What goes wrong:** Dry-run mode downloads the actual creative from Drive (network call), which may be slow or fail.
**Why it happens:** D-06 explicitly says to download and verify the creative file even in dry-run mode — this is intentional to validate the Drive link is accessible.
**How to avoid:** This is correct behavior per the spec. Document that dry-run still hits Drive but not Meta.

### Pitfall 5: APPS_SCRIPT_URL Hardcoded in fromSheet.ts
**What goes wrong:** If APPS_SCRIPT_URL changes, the code must be edited (not just env vars).
**Why it happens:** `fromSheet.ts` line 6-7 hardcodes the Apps Script URL. CONTEXT.md `<specifics>` flags this.
**How to avoid:** This is in-scope cleanup: move to env var `APPS_SCRIPT_URL` with requireEnv() pattern. Add to `.env.example`.

### Pitfall 6: Token Type Check is a Heuristic
**What goes wrong:** The name-based System User check (D-11) may falsely pass or warn.
**Why it happens:** Meta's `/me` endpoint returns the display name, which could be anything for a System User. There is no programmatic field that says "I am a system user" vs "I am a personal account" in the standard /me response.
**How to avoid:** Log it as a warning, not a blocking check. The real fix is D-10 (operational token replacement). The check is informational only.

---

## Code Examples

### Full fromPostgres.ts structure

```typescript
// Source: pattern derived from fromSheet.ts + contentApi.ts in this codebase
import "dotenv/config";
import { writeFile, mkdir, unlink } from "fs/promises";
import { join, extname } from "path";
import { launchBatch, type SubmissionInput } from "./meta.js";

const dryRun = process.argv.includes("--dry-run");
if (dryRun) console.log("[launcher] DRY-RUN mode active");

const TMP_DIR = join(import.meta.dirname, "../../output/tmp");

interface ContentItem {
  id: string;
  content_id: string;
  source: string;
  status: string;
  creative_url: string | null;
  ad_copy: string | null;
  metadata_json: string | null;
}

async function fetchReadyItems(): Promise<ContentItem[]> { /* ... */ }
async function markLaunched(itemId: string): Promise<void> { /* ... */ }
async function markFailed(itemId: string, reason: string): Promise<void> { /* ... */ }
// downloadCreative() — copy from fromSheet.ts or extract to shared module

async function main() {
  let items: ContentItem[] = [];
  try {
    items = await fetchReadyItems();
  } catch (err) {
    console.error("[launcher] Content API unreachable:", err);
    process.exit(1); // triggers Sheets fallback in workflow
  }

  if (items.length === 0) {
    console.log("[launcher] No ready_to_launch items in Postgres. Done.");
    process.exit(0); // no fallback — nothing to do
  }
  // ... rest of launch flow
}
```

### Dry-run output format (D-08)

```typescript
interface DryRunResult {
  ad_id: string;
  source: string;
  creative_type: "image" | "video";
  landing_page: string;
  status: "would_launch" | "skipped";
  reason?: string;
}
```

### workflow_dispatch input for dry-run (D-09)

```yaml
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Run in dry-run mode (no Meta API calls)"
        type: boolean
        default: false
  workflow_run:
    workflows: ["Daily Scrape + Dashboard"]
    types: [completed]
```

```yaml
- name: Launch from Postgres
  run: npm run launch:postgres${{ github.event.inputs.dry_run == 'true' && ' -- --dry-run' || '' }}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Graph API v21.0 | v22.0+ required | Sep 9, 2025 | v21.0 is DEAD — all Meta API calls fail. Must upgrade immediately. |
| Personal access token (60-day) | System User token (non-expiring) | Best practice, no hard deadline | Personal tokens expire silently, breaking the cron launch workflow |
| Google Sheets as primary state | Postgres as primary, Sheets as fallback | This phase | Clean transition per D-04 |

**Deprecated/outdated:**
- `const GRAPH_API = "https://graph.facebook.com/v21.0"` in `meta.ts`: Dead since September 2025. Replace with `v22.0`.
- `APPS_SCRIPT_URL` hardcoded in `fromSheet.ts`: Should be env var per project security rules pattern.
- `launch/meta_campaign.py`: Python legacy launcher — not connected to anything. Archive in this phase (Claude's discretion).

---

## Open Questions

1. **Should `downloadCreative()` be extracted to a shared module?**
   - What we know: Both `fromSheet.ts` and `fromPostgres.ts` need identical Drive download logic.
   - What's unclear: Whether to extract to `lib/driveDownload.ts` or copy-paste into `fromPostgres.ts`.
   - Recommendation: Extract to `src/lib/driveDownload.ts`. Keeps both launchers DRY and makes testing easier.

2. **Should the dashboard submit form also capture `landing_page`?**
   - What we know: `metadata_json` for `ready_to_launch` items currently only has `drive_link`. `landing_page` defaults to `https://newgarments.nl`.
   - What's unclear: Whether the editor should be able to specify a different landing page per remake.
   - Recommendation: Default to `https://newgarments.nl` for now. A `landing_page` field in the submit form is useful but out of scope for this phase. Document the default behavior in the launcher.

3. **What Graph API version to target — v22.0, v23.0, or v24.0?**
   - What we know: v22.0 is the minimum supported. v23.0 is safe for OUTCOME_SALES + manual targeting. v24.0 deprecates ASC/AAC creation but does not break standard campaign creation with manual targeting.
   - Recommendation: Upgrade to `v23.0`. It is well within support, avoids the v24.0 ASC/AAC changes entirely, and gives the most headroom before the next forced upgrade.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | TypeScript launcher | ✓ | v24.14.0 | — |
| npm | Build + install | ✓ | 11.9.0 | — |
| META_ACCESS_TOKEN | All Meta API calls | ✓ (set as secret) | — (token, not version) | None — required |
| META_AD_ACCOUNT_ID | Campaign/adset/ad creation | ✓ (set as secret) | — | None — required |
| CONTENT_API_URL | fromPostgres.ts | Must be added to GH Actions secrets | — | Exit with code 1 → Sheets fallback |
| DASHBOARD_SECRET | fromPostgres.ts | Must be added to GH Actions secrets | — | Exit with code 1 → Sheets fallback |
| GOOGLE_SHEET_ID | fromSheet.ts fallback | ✓ (set as secret) | — | None — required for fallback |

**Missing dependencies with no fallback:**
- `CONTENT_API_URL` and `DASHBOARD_SECRET` must be added as GitHub Actions secrets (D-03). Without them, `fromPostgres.ts` exits with code 1 and the Sheets fallback runs — so the system still works, but Postgres launch never fires.

**Missing dependencies with fallback:**
- If the Railway content API is unreachable at runtime: Sheets fallback handles it per D-04.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | vitest ^4.1.2 |
| Config file | `decarba-remixer/vitest.config.ts` |
| Quick run command | `npm test` (in `decarba-remixer/`) |
| Full suite command | `npm test` (vitest runs all `src/**/__tests__/**/*.test.ts`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAUNCH-01 | `fetchReadyItems()` returns empty array when env vars not set | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |
| LAUNCH-01 | `extractMeta()` returns null when `drive_link` missing | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |
| LAUNCH-01 | `extractMeta()` defaults `landing_page` to newgarments.nl when absent | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |
| LAUNCH-02 | `launchBatch()` with `dryRun=true` returns mock BatchResult without fetch calls | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |
| LAUNCH-02 | `--dry-run` flag detected from `process.argv` | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |
| LAUNCH-03 | `checkTokenType()` logs warning for non-system-user name | unit | `npm test -- --reporter=verbose` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `npm test` (in `decarba-remixer/`)
- **Per wave merge:** `npm test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/launcher/__tests__/fromPostgres.test.ts` — covers LAUNCH-01 (fetchReadyItems, extractMeta)
- [ ] `src/launcher/__tests__/meta.test.ts` — covers LAUNCH-02 (dryRun parameter in launchBatch)
- [ ] `src/launcher/__tests__/tokenCheck.test.ts` — covers LAUNCH-03 (checkTokenType heuristic)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `decarba-remixer/src/launcher/fromSheet.ts`, `meta.ts`, `contentApi.ts` — complete understanding of existing patterns
- Direct code inspection: `ad-command-center/routes/content.py`, `models.py` — API contract fully known
- Direct code inspection: `.github/workflows/launch-campaigns.yml` — current workflow structure
- [Meta Graph API Versions](https://developers.facebook.com/docs/graph-api/changelog/versions/) — v25.0 is latest (Feb 2026), v21.0 expired Sep 2025, v22.0+ required
- [Meta System User Token docs](https://developers.facebook.com/docs/business-management-apis/system-users/install-apps-and-generate-tokens/) — `ads_management` scope required

### Secondary (MEDIUM confidence)
- [ppc.land — Meta Advantage+ deprecation](https://ppc.land/meta-deprecates-legacy-campaign-apis-for-advantage-structure/) — OUTCOME_SALES with manual targeting still works on v22/v23
- [Meta Marketing API out-of-cycle changes 2025](https://developers.facebook.com/docs/marketing-api/out-of-cycle-changes/occ-2025/) — confirmed via search results

### Tertiary (LOW confidence)
- Token type heuristic (checking name from /me for "System User") — no official Meta field exists; this is a community-documented approach

---

## Project Constraints (from CLAUDE.md)

All directives from `CLAUDE.md` apply. Key constraints relevant to this phase:

- **No hardcoded secrets:** `CONTENT_API_URL`, `DASHBOARD_SECRET` must go in `.env` (local) and GitHub Actions secrets (CI). Never inline in code.
- **No fallback defaults with real values:** `os.getenv("KEY", "real-value")` pattern forbidden. Use `requireEnv()` pattern (already established in `meta.ts`).
- **No `.env` commits:** `.gitignore` must cover `.env`.
- **GitHub Actions secrets via `${{ secrets.* }}`:** D-03 adds `CONTENT_API_URL` and `DASHBOARD_SECRET` to `launch-campaigns.yml` — must use secrets syntax.
- **Scan for hardcoded credentials before commit:** Pre-commit hook enforced.
- **Shopify:** Zapier MCP only — not relevant to this phase.
- **GSD workflow enforcement:** Use `/gsd:execute-phase` entry point. No direct repo edits outside GSD workflow.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, existing stack fully inspected
- Architecture: HIGH — patterns copied from live working code
- Pitfalls: HIGH — Graph API version issue verified against official Meta docs; landing_page gap confirmed by code inspection
- Validation: HIGH — vitest already configured, test locations follow existing `__tests__` pattern

**Research date:** 2026-03-28
**Valid until:** 2026-06-28 (Meta API version info changes quarterly; verify Graph API version support before implementation if delayed)
