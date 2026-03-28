---
phase: 02
slug: discovery-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (ESM-native, matches codebase's NodeNext/import.meta usage) |
| **Config file** | Wave 0 gap — `decarba-remixer/vitest.config.ts` needs creation |
| **Quick run command** | `cd decarba-remixer && npx vitest run --reporter=dot` |
| **Full suite command** | `cd decarba-remixer && npx vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd decarba-remixer && npx vitest run --reporter=dot`
- **After every plan wave:** Run `cd decarba-remixer && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-W0-01 | W0 | 0 | — | setup | `cd decarba-remixer && npx vitest run` | ❌ W0 | ⬜ pending |
| 02-01-01 | 01 | 1 | DISC-01 | integration | `npx vitest run src/scraper/__tests__/dedup.test.ts` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | DISC-02 | unit | `npx vitest run src/scraper/__tests__/tiktok-filter.test.ts` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | DISC-03 | unit | `npx vitest run src/scraper/__tests__/pinterest-dedup.test.ts` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | DISC-05, SRC-04 | unit | `npx vitest run src/scraper/__tests__/config.test.ts` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | SRC-01 | unit | `npx vitest run src/scraper/__tests__/tiktok.test.ts` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 2 | SRC-02 | unit | `npx vitest run src/scraper/__tests__/pinterest.test.ts` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 2 | SRC-03 | unit | `npx vitest run src/scraper/__tests__/meta.test.ts` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 3 | DISC-04 | manual | n/a — requires GitHub Actions environment | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `decarba-remixer/vitest.config.ts` — vitest config for Node.js ESM environment
- [ ] `decarba-remixer/package.json` — add `vitest` to devDependencies; add `"test": "vitest run"` script
- [ ] `decarba-remixer/src/scraper/__tests__/dedup.test.ts` — dedup integration stubs
- [ ] `decarba-remixer/src/scraper/__tests__/tiktok-filter.test.ts` — engagement rate filter stubs
- [ ] `decarba-remixer/src/scraper/__tests__/pinterest-dedup.test.ts` — Pinterest Postgres dedup stubs
- [ ] `decarba-remixer/src/scraper/__tests__/config.test.ts` — config loader stubs
- [ ] `decarba-remixer/src/scraper/__tests__/tiktok.test.ts` — TikTok scraper stubs
- [ ] `decarba-remixer/src/scraper/__tests__/pinterest.test.ts` — Pinterest scraper stubs
- [ ] `decarba-remixer/src/scraper/__tests__/meta.test.ts` — Meta Ad Library stubs
- [ ] `decarba-remixer/src/scraper/__tests__/ppspy-config.test.ts` — PPSpy config stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Slack alert on workflow failure | DISC-04 | Requires GitHub Actions runner + SLACK_WEBHOOK_URL secret | 1. Push code change 2. Trigger workflow 3. Verify Slack message arrives within 5 minutes |
| Meta Ad Library Apify actor returns expected fields | SRC-03 | Requires live Apify token + API call | 1. Run actor manually via Apify console 2. Verify output has adArchiveID, images, videos fields |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
