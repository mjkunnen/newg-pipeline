# Phase 0: Codebase Consolidation - Research

**Researched:** 2026-03-27
**Domain:** Python/TypeScript codebase hygiene — dead code removal, env var validation, dependency pinning
**Confidence:** HIGH (all findings from direct codebase inspection)

## Summary

The codebase has grown organically and has three distinct hygiene problems that this phase must fix before any new features can be added reliably.

**Problem 1 — Versioned script proliferation (CLEAN-01):** Seven root-level pipiads Python files (`pipiads_research.py` through `pipiads_research_v4.py`, `pipiads_analyze.py`, `pipiads_analyze_v2.py`, `pipiads_discover.py`, `pipiads_monitor.py`, `pipiads_step1_login.py`) and four slideshow data files (`slideshow_data_new.js`, `slideshow_data_v3.js`, `slideshow_data_v4.js`, `slideshow_data_v5.js`) exist at the root. None of these are referenced by any GitHub Actions workflow. The `decarba-remixer` TypeScript pipeline is the only active automated scraper — these versioned scripts are dead weight.

**Problem 2 — Missing or inconsistent env var validation (CLEAN-02):** Validation is inconsistent across the codebase. `decarba-remixer/src/scraper/ppspy.ts` throws correctly if `PPSPY_COOKIES_JSON` is absent. `launch/meta_campaign.py` raises on missing `META_ACCESS_TOKEN`. But `pipeline/cloud_pinterest.py` silently continues with `FAL_KEY = os.getenv("FAL_KEY")` (no raise). Several TypeScript files use `|| ""` fallback patterns (e.g., `OXYLABS_USERNAME || ""`, `APIFY_TOKEN || ""`, `ENSEMBLEDATA_TOKEN || ""`), meaning missing secrets silently produce empty strings and only fail mid-execution. No script validates cookie freshness (expiry date check) for PPSpy cookies before making API calls.

**Problem 3 — Dependency mismatches (CLEAN-03):** The root `requirements.txt` lists 5 packages (`requests`, `gspread`, `google-api-python-client`, `google-auth`, `python-dotenv`, `Pillow`) but active Python scripts in `scout/`, `pipeline/`, and `launch/` also import `playwright` and `dotenv` (covered), and `scout/tiktok_checker.py` imports `requests` and `dotenv`. The `requirements.txt` is missing `playwright`. The `decarba-remixer/package.json` has no missing deps but has no version pins (uses `^` ranges). The root `package.json` has empty `dependencies` and `devDependencies`, which is accurate for a project-root manifest with no Node scripts that run in CI.

**Problem 4 — Dead directories (CLEAN-04):** `clone/`, `clone_runs/`, `bot/`, `tiktok-test/` all exist. `clone/` and `clone_runs/` are empty or contain only a `suppliers/` subdirectory (no Python files, no workflows reference them). `tiktok-test/` contains two files (`fiveleafs-remake/` folder + `slide1.jpeg`). `bot/` is a substantial Python package (competitor intelligence bot) but is not referenced by any workflow and was replaced by the `scout/` + `decarba-remixer` pattern. The versioned pipiads scripts and slideshow_data files at root also qualify as dead code under CLEAN-01/CLEAN-04.

**Primary recommendation:** Delete `clone/`, `clone_runs/`, `tiktok-test/` outright; move `bot/` to `archive/bot/`; move versioned pipiads and slideshow files to `archive/`; add startup validation guards to all active scripts; pin Python deps with exact versions; add missing secrets to `.env.example`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLEAN-01 | All versioned scripts archived, one canonical file per component | Versioned scripts identified: pipiads v1-v4, analyze v1-v2, slideshow_data v3-v5+new. None referenced in workflows. Canonical versions identified. |
| CLEAN-02 | Every automated script validates required env vars, API keys, and cookie freshness at startup | Gaps found: pipeline/cloud_pinterest.py (FAL_KEY silently None), decarba-remixer uses `|| ""` fallbacks for APIFY_TOKEN, OXYLABS_*, ENSEMBLEDATA_TOKEN. No cookie expiry check in ppspy.ts. |
| CLEAN-03 | package.json and requirements.txt accurately reflect all dependencies with pinned versions | requirements.txt missing `playwright`. decarba-remixer uses `^` semver ranges (not pinned). .env.example missing 6 secrets used in workflows. |
| CLEAN-04 | Dead/orphaned directories removed: clone/, clone_runs/, bot/, tiktok-test/ | All confirmed empty or unreferenced. bot/ is a full package but no workflow invokes it. Safe to archive. |
</phase_requirements>

---

## Standard Stack

### Core (existing — do not change)
| Component | Version | Purpose | Active |
|-----------|---------|---------|--------|
| decarba-remixer | TypeScript, Node 20 | Primary scraping pipeline (PPSpy, Pinterest, TikTok) | YES — 3 workflows |
| scout/ | Python 3.11 | Ad library + daily discovery scripts | YES — manual invocation |
| pipeline/ | Python 3.11 | Pinterest remake pipeline | YES — daily-pinterest.yml |
| launch/ | Python 3.11 | Meta campaign launcher | YES — within decarba-remixer flow |
| ad-command-center/ | Python/FastAPI | Dashboard (undeployed) | NO — Phase 1 |

### Dependencies: decarba-remixer (package.json)
| Package | Current Range | Pinned Version | Purpose |
|---------|---------------|----------------|---------|
| @fal-ai/client | ^1.9.4 | 1.9.4 | Image generation |
| cheerio | ^1.0.0 | 1.0.0 | HTML parsing |
| dotenv | ^16.4.7 | 16.4.7 | Env var loading |
| openai | ^4.77.0 | 4.77.0 | GPT-4o Vision analysis |
| playwright | ^1.58.2 | 1.58.2 | Browser scraping |
| sharp | ^0.33.5 | 0.33.5 | Image processing |
| yaml | ^2.7.0 | 2.7.0 | Config file parsing |
| typescript | ^5.8.0 | 5.8.0 | Build toolchain |
| @types/node | ^22.15.0 | 22.15.0 | Node type defs |

### Dependencies: Python (root requirements.txt — needs update)
| Package | Current State | Correct Pin | Used By |
|---------|--------------|-------------|---------|
| requests | >=2.31 | requests==2.32.3 | scout/tiktok_checker.py, pipeline/cloud_pinterest.py |
| gspread | >=6.0 | gspread==6.2.1 | scout/* |
| google-api-python-client | >=2.100 | google-api-python-client==2.166.0 | scout/* |
| google-auth | >=2.25 | google-auth==2.40.0 | scout/* |
| python-dotenv | >=1.0 | python-dotenv==1.1.0 | all Python scripts |
| Pillow | >=10.0 | Pillow==11.2.1 | pipeline/* |
| playwright | MISSING | playwright==1.51.0 | pipeline/cloud_pinterest.py |

Note: Version pins above are approximate. The planner task MUST run `pip index versions <package>` or check PyPI to confirm exact current stable versions before writing them into requirements.txt.

## Architecture Patterns

### Active Pipeline Map (what workflows actually invoke)

```
GitHub Actions: daily-scrape.yml (3x cron)
  └── decarba-remixer/
      ├── npm run scrape        → src/scraper/ppspy.ts
      ├── npm run scrape:pinterest → src/scraper/pinterest.ts
      ├── npm run scrape:tiktok → src/scraper/tiktok.ts
      └── npm run dashboard     → src/dashboard/generate.ts

GitHub Actions: daily-pinterest.yml (3x cron)
  └── pipeline/cloud_pinterest.py

GitHub Actions: launch-campaigns.yml (on: daily-scrape success)
  └── decarba-remixer/
      └── npm run launch        → src/launcher/fromSheet.ts → src/launcher/meta.ts

GitHub Actions: daily-products.yml (1x cron)
  └── decarba-remixer/
      └── npm run products      → src/converter/taobao-to-shopify.ts

GitHub Actions: deploy-pages.yml (on: push to docs/)
  └── Deploys decarba-remixer/docs/ to GitHub Pages
```

**Dead / never-invoked by workflows:**
- `bot/` — full Python package, no workflow entry point
- `scout/daily_discovery.py` — manual Claude invocation only
- `scout/apify_collect.py` — not invoked anywhere
- `scout/ad_library_scraper.py` — not invoked anywhere
- All root-level `pipiads_*.py` files
- All root-level `slideshow_data_*.js` files
- `build_dashboard.py`, `content_dashboard.py`, `competitor_page_finder.py`, `generate_report.py`, `newgarments_tiktok_finder.py` — root-level orphans

### Canonical File Pattern (post-consolidation target)

```
root/
├── decarba-remixer/          # TypeScript pipeline (untouched)
├── scout/                    # Python discovery scripts (keep active subset)
├── pipeline/                 # Python remake pipeline (keep)
├── launch/                   # Python Meta launcher (keep)
├── ad-command-center/        # FastAPI dashboard (keep — Phase 1 work)
├── archive/                  # Moved dead code (git history preserved)
│   ├── bot/
│   ├── pipiads-versioned/
│   └── slideshow-data-versioned/
├── requirements.txt          # Updated with pins + playwright
├── .env.example              # Updated with all 16 required secrets
└── .github/workflows/        # Untouched (already clean)
```

### Env Var Validation Pattern (for CLEAN-02)

**Python pattern — raise at startup, never default to real value:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Required env var {key!r} is not set. Check .env or GitHub Actions secrets.")
    return val

FAL_KEY = _require("FAL_KEY")
APIFY_TOKEN = _require("APIFY_TOKEN")
```

**TypeScript pattern — throw at module load, not at call site:**
```typescript
function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) throw new Error(`Required env var ${key} is not set`);
  return val;
}

const APIFY_TOKEN = requireEnv("APIFY_TOKEN");
const OXYLABS_USERNAME = requireEnv("OXYLABS_USERNAME");
```

**PPSpy cookie freshness check (decarba-remixer/src/scraper/ppspy.ts):**
```typescript
// After parsing rawCookies, check if session cookies are expired
const now = Date.now() / 1000;
const expired = rawCookies.filter(c => c.expirationDate && c.expirationDate < now);
if (expired.length > 0) {
  throw new Error(
    `PPSpy session cookies expired: ${expired.map(c => c.name).join(", ")}. ` +
    "Update PPSPY_COOKIES_JSON in GitHub Actions secrets."
  );
}
```

### Anti-Patterns to Avoid

- **`|| ""` silent fallback:** `process.env.APIFY_TOKEN || ""` passes validation but produces an empty string that fails mid-execution with an opaque API error. Replace with `requireEnv()`.
- **`os.getenv("KEY")` with no raise:** Returns `None` silently. Replace with the `_require()` helper pattern above.
- **`|| "real-value-here"` hardcoded fallbacks:** Violates CLAUDE.md security rule 1. Found in `taobao-to-shopify.ts` (MAKE_WEBHOOK_URL, PRODUCT_SHEET_ID) and `meta.ts` (META_PAGE_ID). These are Google Sheet IDs and webhook URLs, not API keys, but they still mask misconfiguration. Move to env vars with no default or raise.
- **Running `bot/` or pipiads scripts without knowing which version is canonical:** The versioning pattern (`_v2`, `_v3`, `_v4`) is the exact problem CLEAN-01 targets.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Env var validation boilerplate | Custom validation class | Single `requireEnv()` / `_require()` helper function | Lightweight, no dependencies, consistent error messages |
| Dependency version lookup | Manual PyPI browsing | `pip index versions <package>` or `pip install <package>==` (prints latest) | Direct, accurate, fast |
| Archive of dead code | Delete files permanently | Move to `archive/` subdirectory | Git history must be preserved; hard deletes make bisect impossible |
| Dependency audit | Manual import scanning | `pip check` (for installed env) + manual import grep | `pip check` catches broken deps in installed env |

## Common Pitfalls

### Pitfall 1: Archiving vs Deleting
**What goes wrong:** Files deleted from root are gone from the working tree. If a future phase needs to reference the pipiads v4 scraping logic, it's gone.
**Why it happens:** "Dead code" feels like it should be deleted.
**How to avoid:** Move to `archive/` with a single `git mv` command. Git history is preserved, the file is accessible via `git log --all -- archive/pipiads_research_v4.py`, and the working tree is clean.
**Warning signs:** Any plan that says "delete" instead of "archive/move".

### Pitfall 2: Breaking the daily-scrape.yml workflow
**What goes wrong:** Adding a `requireEnv()` call for a secret that is not set in GitHub Actions secrets causes the workflow to fail immediately on the next run.
**Why it happens:** The `.env` file on the developer machine may have the secret, but GitHub Actions secrets are a separate store.
**How to avoid:** Cross-reference each new required env var against the list of secrets already referenced in `.github/workflows/*.yml`. The 16 secrets listed in the Environment Availability section are already in use — any new required var must be added to both `.env.example` AND documented for the user to add to GitHub Actions secrets.
**Warning signs:** A new `requireEnv()` call for a key not in the workflow's `Create .env` step.

### Pitfall 3: requirements.txt scope confusion
**What goes wrong:** There are two `requirements.txt` files — root-level (for `scout/`, `pipeline/`, `launch/` Python scripts) and `ad-command-center/requirements.txt` (for the FastAPI app). Updating the wrong one or merging them breaks the ad-command-center deploy.
**Why it happens:** Both are named identically.
**How to avoid:** Touch only the root-level `requirements.txt` in this phase. `ad-command-center/requirements.txt` is its own isolated dependency set and is correct as-is.
**Warning signs:** Any plan task that touches `ad-command-center/requirements.txt`.

### Pitfall 4: decarba-remixer package.json pinning breakage
**What goes wrong:** Pinning `playwright` to `1.58.2` in package.json but having a different version of Playwright browsers cached in GitHub Actions causes a mismatch error (`Executable doesn't exist`).
**Why it happens:** `npx playwright install chromium` installs the browser version that matches the installed package. Pinning is safe as long as the `npm ci` + `npx playwright install` sequence is preserved in the workflow.
**How to avoid:** The existing workflow already does `npm ci` (honors package-lock.json) then `npx playwright install chromium --with-deps`. Pinning in package.json is safe because `npm ci` enforces the lock file anyway. The main risk is if someone runs `npm install` (not `ci`) in CI.
**Warning signs:** Changing `npm run install` to `npm install` in any workflow.

### Pitfall 5: Hardcoded Google Apps Script URL is intentional
**What goes wrong:** The `APPS_SCRIPT_URL` in `decarba-remixer/src/launcher/fromSheet.ts` looks like a hardcoded credential but is actually a public Apps Script deployment URL (not a secret). Moving it to an env var breaks the existing working submissions pipeline described in `decarba-remixer/CLAUDE.md`.
**Why it happens:** It looks like a secret but is a public endpoint.
**How to avoid:** Leave `APPS_SCRIPT_URL` as-is. The CLAUDE.md note in decarba-remixer explicitly says "Submissions Pipeline (WERKEND)" and documents this URL. Do not touch it.
**Warning signs:** Any task that moves `APPS_SCRIPT_URL` to an env var.

### Pitfall 6: `bot/` has real functionality
**What goes wrong:** `bot/main.py` is a full competitor intelligence bot with audience profiling, brand profiling, ad library checking, and website analysis. Its `config.py` loads `META_ACCESS_TOKEN` — so if archived while the token is active, that's fine, but it should not be silently deleted.
**Why it happens:** It's in the dead-directory list (`bot/`) but is not trivially empty like `clone/` or `clone_runs/`.
**How to avoid:** Archive (move to `archive/bot/`), document that it exists in case future phases want to revive it.

## Code Examples

### Python Startup Validation Helper
```python
# Source: Direct codebase inspection — pattern matches launch/meta_campaign.py lines 57-59
import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    """Raise at startup if a required env var is missing. Never silent."""
    val = os.getenv(key)
    if not val:
        raise RuntimeError(
            f"Required env var {key!r} is not set. "
            "Add it to .env (local) or GitHub Actions secrets (CI)."
        )
    return val
```

### TypeScript Startup Validation Helper
```typescript
// Source: Direct codebase inspection — extends pattern from scraper/ppspy.ts line 33-34
function requireEnv(key: string): string {
  const val = process.env[key];
  if (!val) {
    throw new Error(
      `Required env var ${key} is not set. ` +
      "Add it to .env (local) or GitHub Actions secrets (CI)."
    );
  }
  return val;
}
```

### PPSpy Cookie Freshness Check
```typescript
// Source: Direct codebase inspection — ppspy.ts line 56 already reads expirationDate
// Add after rawCookies are parsed, before playwright launch:
const nowSec = Math.floor(Date.now() / 1000);
const expiredCookies = rawCookies.filter(
  (c) => c.expirationDate !== undefined && c.expirationDate < nowSec
);
if (expiredCookies.length > 0) {
  const names = expiredCookies.map((c) => c.name).join(", ");
  throw new Error(
    `PPSpy session cookies expired: [${names}]. ` +
    "Update PPSPY_COOKIES_JSON in GitHub Actions secrets."
  );
}
```

### Safe git move to archive
```bash
# Source: git documentation
mkdir -p archive
git mv bot archive/bot
git mv pipiads_research.py archive/pipiads_research.py
# ... repeat per file
git commit -m "chore: archive dead directories and versioned scripts (CLEAN-01, CLEAN-04)"
```

## Runtime State Inventory

> This is a consolidation/cleanup phase with no renames. No runtime state is affected by the archiving tasks.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no databases in use yet (Postgres is Phase 1) | None |
| Live service config | GitHub Pages deployment reads `decarba-remixer/docs/` — this path is NOT touched | None |
| OS-registered state | None — no cron jobs, task scheduler entries, or pm2 processes for the scripts being archived | None |
| Secrets/env vars | No secret keys are renamed. New `requireEnv()` calls may require adding missing secrets to GitHub Actions | Document in .env.example; user adds to GitHub Actions manually |
| Build artifacts | `decarba-remixer/dist/` — compiled output, regenerated on `npm run build` in every workflow run | None — not affected by pinning changes |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js 20 | decarba-remixer build | GitHub Actions: `actions/setup-node@v4` | 20.x | — |
| Python 3.11 | pipeline/, scout/, launch/ scripts | GitHub Actions: `actions/setup-python@v5` | 3.11 | — |
| pip | requirements.txt update | Available with Python | — | — |
| git | Archiving via `git mv` | Available in all environments | — | — |

Step 2.6 note: All dependencies for this phase are git, Node.js, and Python — all available in GitHub Actions and locally. No external services are required for the cleanup tasks themselves.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — no pytest.ini, jest.config, or test directories in active scripts |
| Config file | None — Wave 0 must create |
| Quick run command | `pytest tests/ -x -q` (after Wave 0 setup) |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLEAN-01 | No `pipiads_research_v*.py` or `slideshow_data_v*.js` at repo root | smoke | `pytest tests/test_consolidation.py::test_no_versioned_files_at_root -x` | Wave 0 |
| CLEAN-02 (Python) | `_require("MISSING_KEY")` raises `RuntimeError` before any I/O | unit | `pytest tests/test_startup_validation.py::test_require_raises_on_missing -x` | Wave 0 |
| CLEAN-02 (TypeScript) | `requireEnv("MISSING_KEY")` throws `Error` before any I/O | unit | Manual (no Jest config) or inline `node -e` test | Wave 0 / manual |
| CLEAN-02 (cookies) | PPSpy startup throws if any cookie is expired | unit | `pytest tests/test_startup_validation.py::test_ppspy_cookie_expiry -x` | Wave 0 |
| CLEAN-03 (Python) | `pip check` passes with updated requirements.txt | smoke | `pip install -r requirements.txt && pip check` | No test file needed |
| CLEAN-03 (Node) | `npm ci` succeeds with pinned package.json | smoke | `cd decarba-remixer && npm ci` | No test file needed |
| CLEAN-04 | `clone/`, `clone_runs/`, `bot/`, `tiktok-test/` not in working tree root | smoke | `pytest tests/test_consolidation.py::test_dead_dirs_removed -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (< 5 seconds — file existence checks only)
- **Per wave merge:** `pytest tests/ -v && pip install -r requirements.txt && pip check`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_consolidation.py` — covers CLEAN-01, CLEAN-04 (file/directory existence checks)
- [ ] `tests/test_startup_validation.py` — covers CLEAN-02 (Python `_require()` helper unit tests)
- [ ] `tests/conftest.py` — shared fixtures (repo root path)
- [ ] Framework install: `pip install pytest==8.3.5` — no pytest detected in requirements.txt

## .env.example Gap Analysis

Secrets in workflows but missing from `.env.example` (CLEAN-03 scope):

| Secret | Used By Workflow | Currently in .env.example |
|--------|-----------------|--------------------------|
| META_PAGE_ID | launch-campaigns.yml | No |
| PPSPY_COOKIES_JSON | daily-scrape.yml | No |
| META_INSTAGRAM_ACCOUNT_ID | launch-campaigns.yml | No |
| ENSEMBLEDATA_TOKEN | daily-scrape.yml | No |
| PINTEREST_APPS_SCRIPT_URL | daily-pinterest.yml | No |
| MAKE_WEBHOOK_URL | daily-products.yml | No |

These 6 must be added to `.env.example` with placeholder values (empty string or descriptive comment).

## Open Questions

1. **MAKE_WEBHOOK_URL — is it still active?**
   - What we know: Referenced in `daily-products.yml` as a GitHub Actions secret and as a hardcoded fallback in `taobao-to-shopify.ts` (`|| "https://hook.eu1.make.com/..."`)
   - What's unclear: The root CLAUDE.md lists `ZAPIER_WEBHOOK_URL` for Shopify but `daily-products.yml` uses `MAKE_WEBHOOK_URL` (Make.com, not Zapier). It's unclear if both are active or if one replaced the other.
   - Recommendation: Leave existing behavior intact for this phase. Document both in `.env.example`. Flag for user confirmation before Phase 4 work.

2. **Which pipiads file is canonical?**
   - What we know: `pipiads_research_v4.py` (154KB) is the largest and most recent (Mar 15). `pipiads_discover.py` (375KB) is the largest file in the whole project. No workflow references either.
   - What's unclear: Should any pipiads script be kept active (not archived) for manual use in Phase 2?
   - Recommendation: Archive all versioned scripts. The REQUIREMENTS.md lists no active pipiads scraping requirement for Phase 0. If Phase 2 needs pipiads, it can reference the archive.

3. **`bot/` — archive or delete?**
   - What we know: `bot/` is a full Python competitor intelligence package never invoked by workflows.
   - What's unclear: Was it explicitly replaced by `scout/`? Or is it a parallel approach?
   - Recommendation: Move to `archive/bot/`. The planner should not delete it permanently without user confirmation.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — all files read from disk, no inference
- `.github/workflows/*.yml` — verified which scripts each workflow invokes
- `decarba-remixer/CLAUDE.md` — authoritative notes on the decarba-remixer architecture
- `decarba-remixer/package.json`, root `requirements.txt` — verified dependency state
- All active `.py` and `.ts` script files — import and env var patterns verified directly

### Secondary (MEDIUM confidence)
- Approximate version pins for requirements.txt — based on CLAUDE.md recommended stack section and PyPI knowledge. Planner MUST verify exact current stable versions via `pip index versions` before writing them.

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Dead directories/files (CLEAN-01, CLEAN-04): HIGH — verified by directory listing and workflow grep
- Env var gaps (CLEAN-02): HIGH — verified by reading every active script's env var usage pattern
- Dependency gaps (CLEAN-03): HIGH for missing packages, MEDIUM for exact version pins (need live PyPI check)
- Architecture patterns: HIGH — all findings from direct file inspection

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable codebase — no fast-moving dependencies in scope)
