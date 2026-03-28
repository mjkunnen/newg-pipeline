---
phase: 03
slug: dashboard-unification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (ad-command-center) |
| **Config file** | `ad-command-center/tests/conftest.py` |
| **Quick run command** | `cd ad-command-center && pytest tests/ -x -q` |
| **Full suite command** | `cd ad-command-center && pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd ad-command-center && pytest tests/ -x -q`
- **After every plan wave:** Run `cd ad-command-center && pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-W0-01 | W0 | 0 | DASH-04, DASH-05 | unit | `pytest tests/ -x -q` | Wave 0 | pending |
| 03-01-01 | 01 | 1 | DASH-04 | unit | `pytest tests/test_content_items.py -k drive_link` | Wave 0 | pending |
| 03-01-02 | 01 | 1 | DASH-05 | unit | `pytest tests/test_content_health.py -x` | Wave 0 | pending |
| 03-02-01 | 02 | 2 | DASH-01, DASH-02 | manual | Browser: open dashboard, verify content cards render | N/A | pending |
| 03-02-02 | 02 | 2 | DASH-03 | manual | Browser: click card, verify preview/download works | N/A | pending |
| 03-02-03 | 02 | 2 | DASH-04 | manual | Browser: paste Drive link, verify status updates | N/A | pending |
| 03-03-01 | 03 | 3 | DASH-01 | structural | `grep -c "npm run dashboard" .github/workflows/daily-scrape.yml` returns 0 | N/A | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `ad-command-center/tests/test_content_health.py` — covers DASH-05 health endpoint
- [ ] New test cases in `tests/test_content_items.py` — covers DASH-04 (drive_link), DASH-02 (status filter)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Content discovery cards render correctly | DASH-01, DASH-02 | Visual/browser UI | Open dashboard, verify cards show with correct data |
| Creative preview/download works | DASH-03 | Browser interaction | Click content card, verify modal shows creative |
| Drive link submission updates status | DASH-04 | Browser interaction | Paste Drive URL, verify status changes to queued |
| Health panel shows source status | DASH-05 | Visual/browser UI | Check health section shows 4 source cards |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
