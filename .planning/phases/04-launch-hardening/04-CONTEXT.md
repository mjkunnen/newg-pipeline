# Phase 4: Launch Hardening - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Meta Ads launcher safe, idempotent, and Postgres-driven. The launcher reads `ready_to_launch` items from the content API, downloads creatives from Drive links in metadata_json, launches via the existing meta.ts campaign structure, and marks items `launched` in Postgres. Dry-run mode validates the entire flow without touching Meta. Google Sheets remains readable as fallback. System User token documented.

</domain>

<decisions>
## Implementation Decisions

### Postgres Read Integration (LAUNCH-01)
- **D-01:** Create `fromPostgres.ts` as a new launcher entrypoint alongside `fromSheet.ts`. It calls `GET /api/content?status=ready_to_launch` to get items, extracts `drive_link` and `landing_page` from `metadata_json`, maps to the existing `SubmissionInput` interface, then calls the same `launchBatch()` from `meta.ts`.
- **D-02:** After successful launch, `fromPostgres.ts` calls `PATCH /api/content/{id}/status` with `{"status": "launched"}` to advance the lifecycle. On failure, log the error but don't advance status — item stays at `ready_to_launch` for retry.
- **D-03:** Add `CONTENT_API_URL` and `DASHBOARD_SECRET` to `launch-campaigns.yml` secrets. Add a new npm script `launch:postgres` that runs `fromPostgres.ts`.
- **D-04:** Keep `fromSheet.ts` and `npm run launch` as fallback. The workflow runs `launch:postgres` first, falls back to `launch` (Sheets) if the content API is unreachable or returns zero items.
- **D-05:** The `metadata_json` field for `ready_to_launch` items must contain at minimum: `drive_link` (Google Drive URL) and `landing_page` (destination URL). If either is missing, skip the item with a warning log.

### Dry-Run Mode (LAUNCH-02)
- **D-06:** Add `--dry-run` CLI flag to both `fromPostgres.ts` and `fromSheet.ts`. When active: validate all inputs, download creative, verify file type, log what WOULD be launched (campaign name, ad name, creative type, landing page) — but skip all `fetch()` calls to `graph.facebook.com`.
- **D-07:** In `meta.ts`, add a `dryRun: boolean` parameter to `launchBatch()`, `findOrCreateCampaign()`, `findOrCreateAdSet()`, and `launchAd()`. When true, return mock success responses with placeholder IDs.
- **D-08:** Dry-run output format: structured JSON summary per item (`{ad_id, source, creative_type, landing_page, status: "would_launch" | "skipped", reason?}`). Logged to stdout and optionally written to a file.
- **D-09:** Add `--dry-run` flag support to `launch-campaigns.yml` via `workflow_dispatch` input. Manual trigger can select dry-run; automated trigger always runs live.

### System User Token (LAUNCH-03)
- **D-10:** No code change needed — `META_ACCESS_TOKEN` is already an env var. The fix is operational: document how to generate a System User token in Meta Business Manager, replace the current token value in Railway env vars and GitHub Actions secrets.
- **D-11:** Add a token type check at launcher startup: call `GET /me?fields=name,id` with the token. If the response contains `"name": "System User"` or similar, log confirmation. If it looks like a personal token (has a human name), log a warning.
- **D-12:** Document the System User token generation steps in a `docs/META_TOKEN_SETUP.md` file.

### Idempotency
- **D-13:** The launcher must be idempotent — re-running on already-launched items should be a no-op. `fromPostgres.ts` only queries `status=ready_to_launch`, so already-launched items (status=launched) won't appear. For `fromSheet.ts`, the existing `status=pending` filter handles this.

### Claude's Discretion
- Whether to add a Slack notification on successful launch (not just failure)
- Exact mock response structure for dry-run mode
- Whether to archive `launch/meta_campaign.py` (Python legacy launcher)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Launcher Code
- `decarba-remixer/src/launcher/fromSheet.ts` — Current Sheet-based launcher (pattern to follow)
- `decarba-remixer/src/launcher/meta.ts` — Meta API integration (campaign/adset/ad creation, to be extended with dryRun)
- `decarba-remixer/src/launcher/types.ts` — SubmissionInput, LaunchResult interfaces

### Content API
- `ad-command-center/routes/content.py` — GET /api/content, PATCH /api/content/{id}/status (with drive_link support from Phase 3)
- `ad-command-center/models.py` — ContentItem model, metadata_json field

### Shared Utilities
- `decarba-remixer/src/lib/contentApi.ts` — writeToContentAPI pattern (for reference, not direct reuse — launcher needs READ not WRITE)

### Workflows
- `.github/workflows/launch-campaigns.yml` — Current launch workflow (needs CONTENT_API_URL, dry-run input)

### Legacy (reference only)
- `launch/meta_campaign.py` — Python legacy launcher (not connected to anything, may archive)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `meta.ts` launchBatch/findOrCreateCampaign/findOrCreateAdSet/launchAd — entire Meta API integration, just needs dryRun parameter
- `fromSheet.ts` flow pattern — download creative → detect type → launchBatch → update status — same flow for Postgres version
- `SubmissionInput` interface — already defines the shape needed (adId, adCopy, driveLink, landingPage, date)
- `authFetch()` pattern from contentApi.ts — for reading from content API with Bearer token

### Established Patterns
- Campaign structure: 1 persistent campaign "NEWG-Scaling" + 1 adset "AdSet_Broad" + N ads
- Creative download: Google Drive share link → `uc?export=download` transform → fetch with redirect follow
- Ad copy rewrite via OpenAI GPT-4o-mini (optional, falls back to string-replace)
- Status write-back after launch (currently to Sheet, needs Postgres equivalent)

### Integration Points
- `GET /api/content?status=ready_to_launch` — items to launch
- `PATCH /api/content/{id}/status` — mark as launched
- `launch-campaigns.yml` — workflow to modify (add secrets, dry-run input)

</code_context>

<specifics>
## Specific Ideas

- The fallback to Sheets is important during transition — don't break the existing launch flow
- Meta Ads API v21.0 is currently used — confirm this is still current
- The `APPS_SCRIPT_URL` in fromSheet.ts is hardcoded — should be moved to env var if keeping Sheet fallback

</specifics>

<deferred>
## Deferred Ideas

- **Advantage+ campaign structure** — Current campaigns use manual targeting, Advantage+ would be a separate optimization
- **Budget management from dashboard** — The "Adjust Budget" modal in index.html is a stub, would need new API endpoint
- **Launch scheduling** — Auto-launch at optimal times based on time zones
- **A/B testing** — Launch multiple variants of the same creative

</deferred>

---

*Phase: 04-launch-hardening*
*Context gathered: 2026-03-28*
