---
phase: 0
slug: codebase-consolidation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 0 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash scripts + grep verification (no test framework needed for cleanup phase) |
| **Config file** | none |
| **Quick run command** | `bash -c 'ls pipiads_research_v{1,2,3}.py 2>/dev/null && echo FAIL || echo PASS'` |
| **Full suite command** | `bash .planning/phases/00-codebase-consolidation/verify.sh` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick verification commands
- **After every plan wave:** Run full verification
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 00-01-01 | 01 | 1 | CLEAN-01 | grep | `ls pipiads_research_v{1,2,3}.py 2>/dev/null \|\| echo CLEAN` | ✅ | ⬜ pending |
| 00-01-02 | 01 | 1 | CLEAN-04 | grep | `test -d clone && echo FAIL \|\| echo CLEAN` | ✅ | ⬜ pending |
| 00-02-01 | 02 | 1 | CLEAN-02 | grep | `grep -l 'raise.*missing' decarba-remixer/src/scraper/ppspy.ts` | ❌ W0 | ⬜ pending |
| 00-03-01 | 03 | 1 | CLEAN-03 | grep | `grep 'playwright' requirements.txt` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements — no test framework install needed.
- Verification is via file presence/absence checks and grep commands.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GitHub Actions runs with correct scripts | CLEAN-01 | Requires pushing and triggering workflow | Push to branch, verify workflow output references canonical script |
| Startup validation catches missing env vars | CLEAN-02 | Requires running script without vars | Unset a required env var, run script, verify error message |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
