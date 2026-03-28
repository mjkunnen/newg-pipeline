# Phase 4: Launch Hardening - Discussion Log

> **Audit trail only.**

**Date:** 2026-03-28
**Phase:** 04-launch-hardening
**Areas discussed:** Postgres read integration, Dry-run mode, System User token
**Mode:** --auto

---

## Postgres Read Integration

| Option | Description | Selected |
|--------|-------------|----------|
| New fromPostgres.ts entrypoint | Reads content API, reuses meta.ts, Sheets as fallback | ✓ |
| Modify fromSheet.ts to read both | Single file, more complex | |
| Replace fromSheet.ts entirely | No fallback during transition | |

**User's choice:** [auto] New entrypoint — clean separation, Sheets fallback preserved

## Dry-Run Mode

| Option | Description | Selected |
|--------|-------------|----------|
| CLI --dry-run flag + dryRun param in meta.ts | Validates everything, skips Meta API calls | ✓ |
| Separate dry-run script | Duplicates logic | |
| Environment variable DRY_RUN=true | Less explicit, easy to forget | |

**User's choice:** [auto] CLI flag — explicit, workflow_dispatch input for manual triggers

## System User Token

| Option | Description | Selected |
|--------|-------------|----------|
| Documentation + startup check | No code change for token, add validation log | ✓ |
| Enforce System User in code | Reject personal tokens at startup | |
| No change | Just document externally | |

**User's choice:** [auto] Doc + startup check — warns but doesn't block

## Claude's Discretion

- Slack notification on successful launch, mock response structure, archive legacy Python launcher

## Deferred Ideas

- Advantage+ campaigns, budget management, launch scheduling, A/B testing
