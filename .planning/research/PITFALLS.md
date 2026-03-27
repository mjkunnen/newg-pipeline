# Pitfalls Research

**Domain:** Ad creative research pipeline — scraping, filtering, dashboard, launch automation (streetwear/ecom)
**Researched:** 2026-03-27
**Confidence:** HIGH (all pitfalls confirmed by known issues already experienced in this project)

---

## Critical Pitfalls

### Pitfall 1: Silent Failures With No Alerting

**What goes wrong:**
A script runs to completion, exits 0, and GitHub Actions shows green — but no data was written, no ads were discovered, and the dashboard is stale. The editor sees yesterday's content (or last week's) and has no way to know the pipeline broke. This compounds: by the time anyone notices, multiple days of competitor intelligence are lost and stale pins resurface.

**Why it happens:**
Scripts catch exceptions locally but swallow them — `except Exception: pass`, or return early without writing to sheet, or the scraper returns an empty result set (due to a rate limit or bot detection) and the script doesn't distinguish "zero results" from "error." GitHub Actions exits 0 either way.

**How to avoid:**
Every pipeline step must write a heartbeat/status row to a dedicated Google Sheet tab or send a Slack/webhook notification at end of run. Structure: `step_name | timestamp | status (ok/error) | record_count | error_message`. Any run producing 0 records should be treated as an error, not a success. GitHub Actions jobs should use `if: failure()` notification steps.

**Warning signs:**
- Dashboard shows same content two days in a row
- Google Sheets last-modified timestamp is >24h old
- Script logs show "0 items found" without raising an error
- GitHub Actions workflow history shows all green but content editor complains nothing is fresh

**Phase to address:** Discovery reliability phase (Phase 1 / foundational fix)

**Maps to known issue:** #8 (no error alerting), #5 (Meta launches fail silently), #3 (TikTok viral filtering), #2 (old content resurfaces)

---

### Pitfall 2: Scraper Returns 200 With Empty or Stale DOM

**What goes wrong:**
TikTok, Pinterest, and ad spy tools (PPSpy/PipiAds) all return HTTP 200 when they detect bot traffic — but the response body is empty, contains a CAPTCHA placeholder, or returns a skeleton page. The scraper parses zero results, writes nothing, and exits clean. No exception is raised because no HTTP error occurred.

**Why it happens:**
Modern platforms use "shadow banning" for scrapers: serve a valid-looking response that contains no useful data instead of returning 429 or 403. Scrapers built to check HTTP status codes only will never catch this. This is especially common after an IP has made too many requests or shown non-human behavioral patterns.

**How to avoid:**
Add result-count validation after every scrape: if `len(results) == 0`, raise or log a specific `EmptyResultError`. Set minimum expected records per run (e.g., "TikTok scout should return at least 5 results — if not, treat as failure"). Rotate user-agent strings and use Apify's residential proxy pools. Add post-scrape field validation: check that critical fields (video URL, view count, thumbnail) are non-null.

**Warning signs:**
- Scraper completes in unusually short time (no content to parse)
- Log shows "Scraped 0 items" more than once in a row
- Dashboard stops updating but no error emails arrive
- Response size is much smaller than typical runs

**Phase to address:** Discovery reliability phase — scraper hardening step

**Maps to known issue:** #1 (scripts crash on startup), #3 (TikTok viral filtering doesn't work)

---

### Pitfall 3: No Idempotency Check Before Writing to Google Sheets

**What goes wrong:**
Every pipeline run appends rows to Google Sheets without checking whether those rows already exist. After a week of daily runs, the same TikTok video or Pinterest pin appears 5-7 times. The editor wastes time on duplicate entries. Worse, the Pinterest remake pipeline re-processes old pins it has already acted on, creating redundant work or duplicate launches.

**Why it happens:**
Appending is simpler to implement than read-before-write. Early versions of the pipeline were built quickly and skipped the deduplication step. Over time, the sheet grows with duplicates and the problem is invisible until the editor notices.

**How to avoid:**
Before any write, read existing IDs from the sheet (TikTok video ID, Pinterest pin ID, Meta ad ID, PPSpy product ID) into a set. Only write rows whose ID is not already present. Store a `seen_ids` column or use a dedicated "processed" tab as the source of truth. For GitHub Actions, this read-check must happen inside the same run — not rely on a separate pre-run.

**Warning signs:**
- Same video/pin appearing in dashboard multiple times
- Editor reports "I already saw this last week"
- Sheet row count grows faster than expected
- Pinterest pipeline re-downloads content that was already remade

**Phase to address:** Data freshness and deduplication phase

**Maps to known issue:** #2 (old/stale content resurfaces, Pinterest uses old pins, doesn't check sheets), #6 (Google Sheets not checked before actions)

---

### Pitfall 4: Viral Filtering Applied at Wrong Stage or With Wrong Logic

**What goes wrong:**
The TikTok scout pulls 50 videos, but the view count filter is either (a) not applied at all, (b) applied after the data is written to the sheet instead of before, or (c) applied with a threshold that's hardcoded and wrong for the competitor accounts being monitored. The result: low-view content appears in the dashboard alongside genuinely viral content, making every piece of content look equal and forcing the editor to manually re-filter.

**Why it happens:**
View count thresholds vary enormously by account size. A 500k-view video from a 1M-follower account is underperforming; the same count from a 10k-follower account is extraordinary. If the filter uses a flat threshold (e.g., ">10k views"), it misses this context. Additionally, filters added as post-processing steps often get commented out during debugging and never re-enabled.

**How to avoid:**
Apply viral filters inline during scraping, not as a post-processing step. Define thresholds per competitor account, not globally — store in config. Use engagement rate (views / follower count) as the primary signal for TikTok rather than raw view count. Log how many items were filtered out each run so you can audit whether the threshold is calibrated correctly.

**Warning signs:**
- Dashboard shows videos with <1k views next to videos with 500k views
- Editor spends time manually filtering dashboard content
- Filter threshold config has not been reviewed since initial setup
- Filtering logic lives in a comment block in the script

**Phase to address:** Viral filtering calibration phase

**Maps to known issue:** #3 (TikTok viral filtering doesn't work)

---

### Pitfall 5: Multiple Script Versions With No Canonical Source

**What goes wrong:**
Four versions of `pipiads_scraper.py` exist (v1 through v4). Three versions of `slideshow_data.py` exist (v3 through v5). GitHub Actions workflow calls `pipiads_v3.py`. A fix was applied to `pipiads_v4.py` but never backported to v3. Nobody is sure which version is "production." Someone runs v2 manually to test something and overwrites the sheet. Debugging takes hours because you're not sure what code actually ran.

**Why it happens:**
Scripts are iterated quickly without a formal versioning strategy. Files are duplicated instead of modified in place. No convention exists for deprecating old versions. Git history exists but nobody checks it — they look at filenames instead.

**How to avoid:**
One canonical file per script, no version suffixes in filenames. Use git for version history. Archive old versions in a `/archive/` subdirectory if they must be preserved. Update all GitHub Actions workflow references at the same time as the script rename. Add a `# CANONICAL` comment at the top of the active production file. Delete deprecated versions — don't leave them in the repo.

**Warning signs:**
- Files with `_v2`, `_v3`, `_old`, `_backup` suffixes in the repo
- GitHub Actions workflow `.yml` references a different filename than what's in the repo root
- "Which version should I run?" is a question that gets asked
- Bug fix applied to one version file doesn't show up in production

**Phase to address:** Codebase consolidation phase (prerequisite to any other fixes)

**Maps to known issue:** #7 (multiple script versions create confusion — pipiads v1-v4, slideshow data v3-v5)

---

### Pitfall 6: Startup Crashes Due to Missing Dependencies or Unvalidated Config

**What goes wrong:**
Script starts, immediately crashes with `ModuleNotFoundError`, `KeyError`, or `AttributeError: NoneType`. The crash happens before any useful work is done. In GitHub Actions, this shows as a red run with a cryptic traceback. The fix is obvious once seen, but the run wasted a scheduled slot and the editor's day started with no new content.

**Why it happens:**
Scripts are developed locally with a populated `.env` file and a virtual environment with all packages installed. GitHub Actions has neither unless explicitly configured. Missing: `requirements.txt` kept in sync, `secrets` wired to the workflow `.yml`, validation that required env vars are non-empty before the script does any real work.

**How to avoid:**
Add a startup validation block at the top of every script that checks all required env vars are present and non-empty before doing any work — fail fast with a clear error message listing which var is missing. Keep `requirements.txt` updated (or use `pyproject.toml`). In GitHub Actions, add a dependency install step and verify secrets are mapped correctly in the workflow file. Test the full workflow run end-to-end in CI at least once after any dependency change.

**Warning signs:**
- Script works locally but crashes in GitHub Actions
- Error is `KeyError` or `NoneType` on first API call
- `requirements.txt` has not been updated in months
- New env var added to script but not added to GitHub Actions secrets

**Phase to address:** Codebase consolidation / startup hardening (same phase as Pitfall 5)

**Maps to known issue:** #1 (scripts crash on startup — missing deps, API timeouts)

---

### Pitfall 7: PPSpy/PipiAds Competitor Set Not Configured, or Misconfigured

**What goes wrong:**
The ad spy scripts run and return results, but the competitor accounts being monitored are either (a) generic defaults from when the script was first set up, (b) wrong niche (not streetwear/Gen Z), or (c) haven't been updated as NEWGARMENTS' actual competitors evolved. The editor sees irrelevant ads from unrelated brands. Research time is wasted.

**Why it happens:**
Initial configuration is done once and never revisited. The competitor set lives as a hardcoded list in the script rather than in a config file, making it invisible unless someone reads the code. When the brand's competitive landscape shifts, nobody thinks to update the scraper config.

**How to avoid:**
Store competitor account lists in a dedicated config file (e.g., `config/competitors.json`) or a Google Sheet tab that the script reads at runtime. Review the competitor set quarterly or whenever entering a new market. Add a log line at the start of each run listing which competitors are being monitored, so the output is auditable without reading the code.

**Warning signs:**
- Ads in dashboard are from brands that don't compete with NEWGARMENTS
- "Competitor" config was last modified months ago
- Competitor accounts are hardcoded strings inside Python files
- No streetwear/Gen Z NL brands in the monitored set

**Phase to address:** PPSpy/PipiAds configuration phase

**Maps to known issue:** #4 (PPSpy not properly configured for their competitor set)

---

### Pitfall 8: Meta Campaign Launcher Has No Confirmation Step or Dry-Run Mode

**What goes wrong:**
The launch script creates and activates Meta campaigns based on a row in Google Sheets. If the sheet has bad data (wrong budget, missing creative URL, wrong ad account ID), the campaign launches with those bad values — or launches multiple times if the script is re-run to debug a different issue. Money is spent on misconfigured campaigns. There is no way to review what will happen before it happens.

**Why it happens:**
Launch automation is built for speed. Confirmation prompts are removed because "the sheet is the approval." But the sheet can contain stale data, test rows, or rows that were already processed. Without a "launched" status column being checked before action, re-running the script re-launches.

**How to avoid:**
Meta launch script must check a "status" column in the sheet before acting — only process rows where `status == "approved"` and immediately write `status = "launching"` (then `status = "launched"` on success) as an atomic operation. Add a dry-run mode (`--dry-run` flag) that logs what would happen without making API calls. Log every API call and response to a sheet audit tab. Never process a row twice — check for existing campaign IDs before creating new ones.

**Warning signs:**
- Same creative appears as multiple active Meta campaigns
- Sheet has rows in "approved" status that were already launched
- No "status" column or "launched" timestamp column in the sheet
- Launch script can be re-run without consequence check

**Phase to address:** Meta launch hardening phase

**Maps to known issue:** #5 (Meta launches fail silently), #6 (Google Sheets not checked before actions)

---

### Pitfall 9: API Token Expiry Causes Silent Auth Failures

**What goes wrong:**
Meta access tokens expire (short-lived tokens expire in hours; long-lived tokens expire in 60 days). Pinterest, PipiAds, and Apify tokens can also be revoked or rotated. When a token expires, API calls return 401 or a specific error code — but if the script doesn't handle auth errors explicitly, it may silently return zero results (same behavior as empty search results) rather than raising an alarm.

**Why it happens:**
Tokens are set once in `.env` and GitHub Actions secrets and forgotten. Scripts don't distinguish between "no results found" and "auth rejected." The first sign of expiry is often the editor noticing stale content.

**How to avoid:**
Test authentication before the main scraping logic in each script. Check the token validity at the start of the run and fail loudly if it's invalid (`raise AuthenticationError("META_ACCESS_TOKEN expired or invalid")`). Set calendar reminders to rotate long-lived Meta tokens before the 60-day expiry. For Meta specifically, use a System User token (no expiry) rather than a personal access token.

**Warning signs:**
- Pipeline returns 0 results after working for weeks
- Last known-good run was exactly 60 days ago (Meta token)
- Error logs show 401 or "Invalid OAuth access token"
- Suddenly all platforms fail simultaneously (Apify token revoked)

**Phase to address:** Discovery reliability phase — auth validation

**Maps to known issue:** #1 (scripts crash on startup — API timeouts), #8 (no error alerting)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding competitor list in script | Fast to set up | Can't update without editing code; invisible to non-devs | Never — use config file |
| Appending to sheet without dedup check | Simpler write logic | Sheet fills with duplicates; editor loses trust | Never in production |
| Multiple versioned filenames (v1, v2, v3) | Preserves old versions "just in case" | Confusion about what's running; bugs fixed in wrong version | Never — use git |
| Catching all exceptions silently | Script never crashes | Failures are invisible for days | Never — always log errors |
| Flat view-count threshold for viral filter | Simple to implement | Wrong results for accounts of different sizes | Only in prototype, not production |
| Personal Meta access token | Fast to set up | Expires in 60 days, causes silent auth failures | Never — use System User token |
| No dry-run mode on launch scripts | Less code to write | One typo launches wrong campaign | Never for money-touching scripts |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Meta Ads API | Using personal access token that expires in 60 days | Use a System User token (non-expiring) via Business Manager |
| Meta Ads API | Legacy campaign creation API (pre-v24) deprecated Q1 2026 | Use Advantage+ campaign structure via v24+ API |
| Meta Ads API | Not checking `status` field in API response — 200 ≠ success | Parse response body for `error` field, not just HTTP status |
| TikTok scraping | Flat request loop without delays or proxy rotation | Use Apify actor with residential proxies, human-like timing |
| Pinterest scraping | Re-processing already-seen pins because seen_ids not persisted | Store processed pin IDs in Google Sheets column, check before scrape |
| PipiAds/PPSpy | Hardcoded competitor IDs that drift from actual competitor set | Config file or sheet-based competitor list, reviewed quarterly |
| GitHub Actions | Secrets not available in reusable workflows unless explicitly passed | Map every secret explicitly in the workflow `env:` block |
| Google Sheets API | Quota exceeded (100 requests/100 seconds per user) causes silent drops | Batch reads/writes; add exponential backoff on 429 responses |
| Apify | Actor run succeeds but dataset is empty due to bot detection | Check dataset item count post-run; treat 0-item result as failure |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Reading entire Google Sheet on every write | Slow runs, Sheets API quota exhaustion | Cache the sheet read at run start, reuse for all writes in that run | When sheet exceeds ~1000 rows |
| Scraping all competitor accounts sequentially with no concurrency | Runs take 20+ minutes, GitHub Actions timeout (6h limit) | Parallelize per-account scraping; use Apify's built-in parallel runs | When competitor set grows beyond 10 accounts |
| Storing all discovered content in one sheet tab | Sheet becomes unmanageable, formulas slow down | Separate tabs per source (TikTok, Pinterest, Meta, PPSpy); archive rows older than 30 days | When sheet exceeds ~5000 rows |
| Re-downloading already-processed images/videos for dedup | Redundant bandwidth, slow runs | Track by ID, never by content hash — IDs are always available and free to check | From the very first run |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Meta access token in script comments or logs | Token scraped from GitHub, used to create/spend on ad account | Treat `META_ACCESS_TOKEN` as a password — never log, always use `os.getenv()` |
| PipiAds/PPSpy credentials in script for "testing" | Competitor intelligence account hijacked | All credentials via `.env` only; pre-commit hook blocks secrets in code |
| Apify token hardcoded in workflow `.yml` | Token exposed in public repo, Apify account drained | Use `${{ secrets.APIFY_TOKEN }}` only — never inline |
| Google Sheet ID hardcoded as constant | Sheets accessed by unintended scripts if ID leaks | Keep in `.env`; treat Sheet IDs as semi-sensitive config, not public constants |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dashboard shows all content regardless of viral status | Editor manually filters every day — wastes 30+ min | Apply viral filter before writing to dashboard; show only qualified content |
| No "last updated" timestamp visible on dashboard | Editor can't tell if today's run succeeded | Show "Last updated: [timestamp]" prominently on dashboard; turn red if >24h stale |
| Stale/duplicate content resurfaces | Editor sees same content repeatedly, loses trust in tool | Enforce dedup at write time; dashboard = only fresh, unseen content |
| No clear status on which sheet rows have been launched | Editor accidentally approves already-launched content for re-launch | Add status column with clear states: `pending / approved / launching / launched / failed` |
| AI-generated product images shown as options | Editor wastes time on images that look wrong for product photography | Product image AI generation is out of scope — only extraction/segmentation is valid |

---

## "Looks Done But Isn't" Checklist

- [ ] **TikTok scraper:** Check that viral filter is applied *before* sheet write, not after — verify by checking if low-view videos appear in sheet
- [ ] **Pinterest pipeline:** Check that seen_ids are loaded from sheet *before* scraping begins — verify by running twice and confirming no duplicates appear on second run
- [ ] **Meta launcher:** Check that "launched" status is written to sheet *atomically* with the API call — verify by re-running launcher and confirming no duplicate campaigns are created
- [ ] **Error alerting:** Check that a real failure (invalid API key) produces a notification — verify by temporarily setting a wrong key and confirming alert fires
- [ ] **PPSpy/PipiAds config:** Check that competitor list matches NEWGARMENTS' actual competitors — verify by reviewing what brands appear in dashboard results
- [ ] **GitHub Actions secrets:** Check that all required env vars are mapped in every workflow `.yml` — verify by comparing `os.getenv()` calls in scripts against workflow `env:` blocks
- [ ] **Script versions:** Check there is exactly one canonical version of each script — verify by counting files matching `*_v*.py` pattern in repo root (should be zero)
- [ ] **Auth tokens:** Check Meta token type is System User (non-expiring) — verify in Meta Business Manager under System Users

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Silent failures discovered after 3+ days | HIGH | Manual backfill run; audit sheet for gaps; check competitor content manually for missed days |
| Sheet filled with duplicates | MEDIUM | Export sheet, deduplicate by ID column with script, re-import clean version; add dedup guard going forward |
| Wrong Meta campaigns launched due to bad sheet data | HIGH | Pause campaigns immediately in Ads Manager; audit spend; fix sheet data; add dry-run mode before next launch |
| Script version confusion causes wrong code to run | MEDIUM | Check git log for what actually ran; identify which version GitHub Actions called; archive unused versions; update workflow reference |
| Meta token expired, days of silent failures | MEDIUM | Rotate token immediately; add token validation check to script startup; set 50-day renewal reminder |
| PPSpy competitor set wrong for months | LOW-MEDIUM | Update config to correct competitors; re-run historical scrape for past 7 days if data is important |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Silent failures, no alerting | Phase 1: Discovery reliability — add heartbeat logging | Trigger a deliberate failure; confirm notification fires |
| Empty scrape results treated as success | Phase 1: Discovery reliability — add result-count validation | Run with invalid credentials; confirm error is raised, not silent |
| No Google Sheets dedup before write | Phase 2: Data freshness — implement seen_ids check | Run pipeline twice; confirm sheet row count doesn't double |
| Viral filter applied wrong / not at all | Phase 2: Data freshness — inline filter during scrape | Check lowest-view-count item in dashboard; should exceed threshold |
| Multiple versioned script files | Phase 0: Codebase consolidation — prerequisite to everything | `find . -name "*_v*.py"` returns zero results |
| Startup crashes, missing deps | Phase 0: Codebase consolidation — startup validation block | Run each script with all env vars unset; confirm clear error messages |
| PPSpy competitor set wrong | Phase 3: Source configuration — review and update competitor config | Audit 10 random dashboard ads; all should be from relevant streetwear brands |
| Meta silent launch failures | Phase 4: Launch hardening — status column + dry-run mode | Re-run launcher against already-launched rows; confirm no duplicate campaigns |
| API token expiry silent failure | Phase 1: Discovery reliability — auth validation at startup | Manually expire/revoke test token; confirm error fires immediately |

---

## Sources

- Known issues from milestone context (issues #1-#9) — direct project experience, HIGH confidence
- [Why Scraping Pipelines Fail in Production](https://rayobyte.com/blog/why-scraping-pipelines-fail-production) — confirmed silent failure patterns
- [Top Web Scraping Challenges in 2025](https://www.scrapingbee.com/blog/web-scraping-challenges/) — bot detection, empty DOM returns
- [Meta Ads API deprecation of legacy campaign APIs](https://ppc.land/meta-deprecates-legacy-campaign-apis-for-advantage-structure/) — v24+ required
- [Troubleshooting GitHub Actions secrets issues](https://mindfulchase.com/explore/troubleshooting-tips/ci-cd-continuous-integration-continuous-deployment/troubleshooting-github-actions-fixing-workflow-failures,-secrets-issues,-matrix-errors,-caching-bugs,-and-runtime-problems-in-ci-cd-pipelines.html) — secrets not available in reusable workflows
- [Understanding Idempotency in Data Pipelines](https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines) — read-before-write patterns
- [Data Pipeline Technical Debt](https://www.clouddatainsights.com/data-pipeline-pitfalls-unraveling-the-technical-debt-tangle/) — naming, versioning, debt patterns
- [Dealing with flaky GitHub Actions](https://epiforecasts.io/posts/2022-04-11-robust-actions/) — scheduled workflow unreliability
- [Meta Ads API Complete Guide](https://www.adstellar.ai/blog/meta-ads-api) — auth, retry, permission scope

---
*Pitfalls research for: ad creative research pipeline (scraping → filtering → dashboard → launch)*
*Researched: 2026-03-27*
