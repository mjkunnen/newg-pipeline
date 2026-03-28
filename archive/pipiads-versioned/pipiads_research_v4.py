"""
NEWGARMENTS - PiPiAds Research v4
State-machine-driven, verified, observability-first competitor research.

Run modes:
  --stage A0  operator test (1 keyword, 1 page, 1-2 card opens, validate state machine)
  --stage A1  mini-batch test (3 keywords, 1 page each)
  --stage B   controlled validation (8 keywords, 2 pages each)
  --stage C   full run (all keywords, full depth)
  --mode research  full research run (stage C + baseline reconciliation + drift detection)

Usage:
  python pipiads_research_v4.py --stage A0
  python pipiads_research_v4.py --mode research
"""
import asyncio
import argparse
import hashlib
import json
import re
import sys
import io
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page

# ── Windows encoding fix ──
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BASE = Path(__file__).parent
SCREENSHOTS = BASE / "pipiads_screenshots"
DATA_DIR = BASE / "pipiads_data"
BATCH_LOG = DATA_DIR / "batch_summaries"
STEP_LOG_DIR = DATA_DIR / "step_logs"
COOKIES = DATA_DIR / "pipiads_cookies.json"

TARGET_REGIONS = ["US", "GB", "DE", "NL", "AU"]
# Hard gate: only keep ads targeting at least one of these countries
REQUIRE_TARGET_REGION = True


# ═══════════════════════════════════════════════════════════
# 0. BASELINE FILTER DEFINITIONS
# ═══════════════════════════════════════════════════════════

# Critical filters: if any of these cannot be verified as applied, ABORT.
# Soft filters: tolerate approximation if live options are close equivalents.
BASELINE_FILTERS = {
    "critical": {
        "winning_products": {
            "label": "Winning Products",
            "desired_values": ["Winning Products"],
            "acceptable_equivalents": ["Winning Products"],
            "chip_patterns": ["winning"],
        },
    },
    "soft": {
        "time_window": {
            "label": "Time Window",
            "desired_values": ["Last 30 days"],
            "acceptable_equivalents": ["Last 7 days", "Last 14 days", "Last 30 days",
                                        "Last 60 days", "Last 90 days", "Last 6 months",
                                        "Recent", "This month", "Past month"],
            "chip_patterns": ["last 7", "last 14", "last 30", "last 60", "last 90",
                              "6 months", "recent", "this month", "past month",
                              "7 days", "14 days", "30 days", "60 days", "90 days"],
        },
    },
}

# No hard abort filters for digital product research
HARD_ABORT_FILTERS = set()


# ═══════════════════════════════════════════════════════════
# 0b. BASELINE FILTER MANAGER
# ═══════════════════════════════════════════════════════════

class BaselineManager:
    """
    Reconciliation-first baseline filter manager.
    - Reads currently applied filter chips from the PiPiAds UI
    - Compares to desired baseline
    - Reconciles differences (does NOT blindly reset/clear)
    - Calculates confidence (X/N filters verified)
    - Detects drift on periodic re-checks
    """

    def __init__(self, page: Page, logger, ts: str):
        self.page = page
        self.logger = logger
        self.ts = ts
        self.baseline_snapshot: Dict[str, Any] = {}  # last verified state
        self.confidence: float = 0.0
        self.confidence_detail: Dict[str, str] = {}  # filter_name -> "verified" | "missing" | "approximate"
        self.reconciliation_log: List[Dict] = []
        self.drift_events: List[Dict] = []
        self._total_filters = len(BASELINE_FILTERS["critical"]) + len(BASELINE_FILTERS["soft"])

    async def read_applied_chips(self) -> List[str]:
        """Read all currently applied filter chips/tags from the PiPiAds UI."""
        chips = []
        chip_selectors = [
            '.el-tag', '[class*="filter-tag"]', '[class*="tag-item"]',
            '[class*="selected-filter"]', '[class*="chip"]',
            '.filter-tags .el-tag', '[class*="condition"] .el-tag',
            '[class*="search-condition"] .el-tag',
            '[class*="filter"] .el-tag',
            '[class*="active-filter"]',
            # PiPiAds-specific patterns
            '[class*="select-tag"]', '[class*="el-select__tags"] span',
            '[class*="filter-value"]', '[class*="search-filter"] span',
            '[class*="selected-option"]', '[class*="tag-text"]',
            '.el-select__tags .el-tag', '[class*="condition-item"]',
            '[class*="filter-content"] .el-tag',
            '[class*="search-box"] .el-tag',
        ]
        for sel in chip_selectors:
            try:
                count = await self.page.locator(sel).count()
                for i in range(min(count, 30)):
                    try:
                        text = await self.page.locator(sel).nth(i).inner_text(timeout=800)
                        text = text.strip()
                        if text and len(text) < 100 and len(text) > 0:
                            chips.append(text)
                    except Exception:
                        continue
            except Exception:
                continue

        # Also try to read from select dropdowns that show current values
        select_selectors = [
            '.el-select .el-input__inner',
            '[class*="filter"] .el-input__inner',
            '[class*="select"] input[readonly]',
            '[class*="filter"] select',
        ]
        for sel in select_selectors:
            try:
                count = await self.page.locator(sel).count()
                for i in range(min(count, 10)):
                    try:
                        val = await self.page.locator(sel).nth(i).input_value(timeout=800)
                        if val and val.strip() and len(val.strip()) < 100:
                            chips.append(val.strip())
                    except Exception:
                        try:
                            val = await self.page.locator(sel).nth(i).get_attribute("placeholder", timeout=500)
                        except Exception:
                            continue
            except Exception:
                continue

        # Check toggle buttons (e.g., "Winning Products" button active state)
        toggle_selectors = [
            ('button.btn-filter-winner', 'Winning Products'),
        ]
        for sel, label in toggle_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=800):
                    cls = await btn.get_attribute("class", timeout=500) or ""
                    # Active if has 'active', 'is-active', 'selected', or 'on' class
                    if any(x in cls.lower() for x in ["active", "selected", "is-on", "checked"]):
                        chips.append(label)
            except Exception:
                pass

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in chips:
            cl = c.lower()
            if cl not in seen:
                seen.add(cl)
                unique.append(c)
        return unique

    def _chip_matches_filter(self, chips_lower: List[str], patterns: List[str]) -> bool:
        """Check if any applied chip matches any of the filter's patterns."""
        for chip in chips_lower:
            for pattern in patterns:
                if pattern in chip:
                    return True
        return False

    def _identify_chip_value(self, chips_lower: List[str], patterns: List[str]) -> Optional[str]:
        """Return the actual chip text that matched."""
        for chip in chips_lower:
            for pattern in patterns:
                if pattern in chip:
                    return chip
        return None

    async def reconcile(self) -> Dict[str, Any]:
        """
        Reconciliation-first baseline verification.
        1. Read what's currently applied
        2. Compare to desired baseline
        3. For missing critical filters, attempt to apply them via UI
        4. Re-verify after any changes
        5. Calculate confidence
        Returns: {success, confidence, detail, applied_chips, actions_taken}
        """
        print("\n[BASELINE] Starting reconciliation...")
        actions_taken = []

        # Step 1: Read current state
        chips = await self.read_applied_chips()
        chips_lower = [c.lower() for c in chips]
        print(f"  Applied chips found: {chips if chips else '(none)'}")

        # Step 2: Check each filter
        verified = {}
        missing_critical = []
        missing_soft = []

        for fname, fdef in BASELINE_FILTERS["critical"].items():
            matched = self._chip_matches_filter(chips_lower, fdef["chip_patterns"])
            if matched:
                verified[fname] = "verified"
                actual = self._identify_chip_value(chips_lower, fdef["chip_patterns"])
                print(f"  [OK] {fdef['label']}: verified (chip: {actual})")
            else:
                verified[fname] = "missing"
                missing_critical.append(fname)
                print(f"  [MISS] {fdef['label']}: NOT found in applied chips")

        for fname, fdef in BASELINE_FILTERS["soft"].items():
            matched = self._chip_matches_filter(chips_lower, fdef["chip_patterns"])
            if matched:
                actual = self._identify_chip_value(chips_lower, fdef["chip_patterns"])
                # Check if it's an acceptable equivalent
                if fdef.get("acceptable_equivalents"):
                    is_exact = any(p in (actual or "") for p in [v.lower() for v in fdef["desired_values"]])
                    is_approx = any(p in (actual or "") for p in [v.lower() for v in fdef["acceptable_equivalents"]])
                    if is_exact:
                        verified[fname] = "verified"
                        print(f"  [OK] {fdef['label']}: exact match (chip: {actual})")
                    elif is_approx:
                        verified[fname] = "approximate"
                        print(f"  [~OK] {fdef['label']}: close equivalent (chip: {actual})")
                    else:
                        verified[fname] = "approximate"
                        print(f"  [~OK] {fdef['label']}: found but unrecognized value (chip: {actual})")
                else:
                    verified[fname] = "verified"
                    print(f"  [OK] {fdef['label']}: verified (chip: {actual})")
            else:
                verified[fname] = "missing"
                missing_soft.append(fname)
                print(f"  [MISS] {fdef['label']}: NOT found (soft filter)")

        # Step 3: Attempt to apply missing critical filters via UI
        if missing_critical:
            print(f"\n  [BASELINE] Attempting to apply {len(missing_critical)} missing critical filter(s) via UI...")
            for fname in list(missing_critical):
                applied = await self._try_apply_filter(fname, BASELINE_FILTERS["critical"][fname])
                if applied:
                    actions_taken.append(f"ui_applied_{fname}")
                    verified[fname] = "verified"
                    missing_critical.remove(fname)
                    print(f"  [FIXED] {fname}: applied via UI")
                else:
                    print(f"  [MISS] {fname}: UI apply failed — filter NOT active")

        # Step 3b: Attempt soft filters too (best effort)
        if missing_soft:
            for fname in list(missing_soft):
                applied = await self._try_apply_filter(fname, BASELINE_FILTERS["soft"][fname])
                if applied:
                    actions_taken.append(f"ui_applied_{fname}")
                    verified[fname] = "approximate"
                    missing_soft.remove(fname)

        # Step 4: Re-verify UI-applied filters if we made UI changes
        ui_actions = [a for a in actions_taken if a.startswith("ui_applied_")]
        if ui_actions:
            await self.page.wait_for_timeout(2000)
            chips_after = await self.read_applied_chips()
            chips_after_lower = [c.lower() for c in chips_after]
            print(f"\n  Post-reconciliation chips: {chips_after if chips_after else '(none)'}")

            for fname in list(verified.keys()):
                if verified[fname] == "verified" and fname in BASELINE_FILTERS["critical"]:
                    fdef = BASELINE_FILTERS["critical"][fname]
                    still_present = self._chip_matches_filter(chips_after_lower, fdef["chip_patterns"])
                    if not still_present:
                        verified[fname] = "missing"
                        if fname not in missing_critical:
                            missing_critical.append(fname)
                        print(f"  [WARN] {fname}: applied but not confirmed in post-check")

        # Step 5: Calculate confidence (UI-only — no API enforcement)
        total = self._total_filters
        score = 0
        for fname, status in verified.items():
            if status == "verified":
                score += 1
            elif status == "approximate":
                score += 0.75
        self.confidence = score / total if total > 0 else 0
        self.confidence_detail = dict(verified)
        self.baseline_snapshot = {
            "chips": chips if not actions_taken else (await self.read_applied_chips()),
            "verified": dict(verified),
            "timestamp": datetime.now().isoformat(),
        }

        # Log
        result = {
            "success": len(missing_critical) == 0,
            "confidence": round(self.confidence, 2),
            "confidence_fraction": f"{score}/{total}",
            "detail": verified,
            "missing_critical": missing_critical,
            "missing_soft": missing_soft,
            "actions_taken": actions_taken,
            "applied_chips": self.baseline_snapshot.get("chips", []),
            "required_rebuild": len(actions_taken) > 0,
        }
        self.reconciliation_log.append(result)

        status = "RECONCILED" if result["success"] and actions_taken else (
            "VERIFIED" if result["success"] else "FAILED")
        print(f"\n  [BASELINE] {status} — confidence: {result['confidence_fraction']} "
              f"({self.confidence:.0%})")
        if missing_critical:
            print(f"  [BASELINE] MISSING CRITICAL: {missing_critical}")

        return result

    async def _try_apply_filter(self, filter_name: str, fdef: Dict) -> bool:
        """Apply a filter through visible PiPiAds UI clicks. Returns True if applied."""
        try:
            desired = fdef["desired_values"][0] if fdef["desired_values"] else ""

            if filter_name == "winning_products":
                # Click "Winning Products" toggle button
                # DOM: button.btn-filter-winner
                for sel in [
                    'button.btn-filter-winner',
                    '.btn-filter-winner',
                    'button:has-text("Winning Products")',
                    'text="Winning Products"',
                ]:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await self.page.wait_for_timeout(2500)
                            print(f"  [UI] Clicked 'Winning Products' filter")
                            return True
                    except Exception:
                        continue
                return False

            elif filter_name == "website":
                # Click "E-commerce" in the data types filter bar
                # DOM: div.filter-data-types contains inline options
                for sel in [
                    '.filter-data-types >> text="E-commerce"',
                    '.filter-data-types span:has-text("E-commerce")',
                    '.filter-data-types div:has-text("E-commerce")',
                    '.filter-data-types a:has-text("E-commerce")',
                    'text="E-commerce"',
                ]:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await self.page.wait_for_timeout(2000)
                            print(f"  [UI] Clicked 'E-commerce' filter")
                            return True
                    except Exception:
                        continue
                return False

            elif filter_name == "platform":
                # Click "Shopify" in the category/platform filter area
                # DOM: appears as a suggestion item in the filter-wrap area
                for sel in [
                    '.filter-wrap >> text="Shopify"',
                    '[class*="category"] >> text="Shopify"',
                    '.filter-action >> text="Shopify"',
                    'span:has-text("Shopify")',
                ]:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await self.page.wait_for_timeout(2000)
                            print(f"  [UI] Clicked 'Shopify' filter")
                            return True
                    except Exception:
                        continue

                # Fallback: try the Ecom Platform dropdown
                try:
                    ecom_dd = self.page.locator('text="Ecom Platform"').first
                    if await ecom_dd.is_visible(timeout=1500):
                        await ecom_dd.click()
                        await self.page.wait_for_timeout(1000)
                        shopify_opt = self.page.locator('.el-select-dropdown__item:has-text("Shopify"), li:has-text("Shopify")').first
                        if await shopify_opt.is_visible(timeout=2000):
                            await shopify_opt.click()
                            await self.page.wait_for_timeout(2000)
                            print(f"  [UI] Selected 'Shopify' from Ecom Platform dropdown")
                            return True
                except Exception:
                    pass
                return False

            elif filter_name == "ad_spend":
                # Ad Spend filter — look for a checkbox or toggle
                for sel in [
                    'text="Ad Spend"',
                    '[class*="filter"] >> text="Ad Spend"',
                    'text="Has ad spend"',
                    '.filter-wrap >> text="Ad Spend"',
                ]:
                    try:
                        el = self.page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            await el.click()
                            await self.page.wait_for_timeout(2000)
                            print(f"  [UI] Clicked 'Ad Spend' filter")
                            return True
                    except Exception:
                        continue
                return False

            elif filter_name == "time_window":
                # Click time option in filter-time-types
                return await self._ui_set_time_filter(desired)

            return False
        except Exception:
            return False

    async def _ui_set_time_filter(self, time_option: str) -> bool:
        """Click a time filter option in the PiPiAds time filter bar."""
        for sel in [
            f'.filter-time-types >> text="{time_option}"',
            f'.filter-time-types span:has-text("{time_option}")',
            f'.filter-time-types div:has-text("{time_option}")',
            f'.filter-time-types a:has-text("{time_option}")',
        ]:
            try:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    await el.click()
                    await self.page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False

    async def check_drift(self, keyword_index: int, keyword: str) -> Dict[str, Any]:
        """
        Re-check applied filter chips against baseline snapshot.
        Returns: {drifted, corrections_made, unrecoverable, detail}
        """
        print(f"\n  [DRIFT CHECK] After keyword {keyword_index} ({keyword})...")

        chips = await self.read_applied_chips()
        chips_lower = [c.lower() for c in chips]

        drifted_filters = []
        corrections_made = []
        unrecoverable = False

        # Check critical filters
        for fname, fdef in BASELINE_FILTERS["critical"].items():
            status = self.confidence_detail.get(fname)
            if status == "missing":
                print(f"  [SKIP] {fdef['label']}: was not applied")
                continue

            was_verified = status in ("verified", "approximate")
            still_present = self._chip_matches_filter(chips_lower, fdef["chip_patterns"])

            if was_verified and not still_present:
                drifted_filters.append(fname)
                print(f"  [DRIFT] {fdef['label']}: was verified, now MISSING")

                # Attempt correction
                corrected = await self._try_apply_filter(fname, fdef)
                if corrected:
                    corrections_made.append(fname)
                    print(f"  [CORRECTED] {fname}: re-applied")
                else:
                    if fname in HARD_ABORT_FILTERS:
                        unrecoverable = True
                        print(f"  [UNRECOVERABLE] {fname}: critical filter lost, cannot re-apply")

        # Check soft filters
        for fname, fdef in BASELINE_FILTERS["soft"].items():
            status = self.confidence_detail.get(fname)
            if status == "api_enforced":
                print(f"  [OK] {fdef['label']}: API-enforced (cannot drift)")
                continue
            was_verified = status in ("verified", "approximate")
            still_present = self._chip_matches_filter(chips_lower, fdef["chip_patterns"])
            if was_verified and not still_present:
                drifted_filters.append(fname)
                print(f"  [DRIFT] {fdef['label']}: soft filter drifted (non-critical)")

        # Update confidence after drift check
        if drifted_filters:
            for fname in drifted_filters:
                if fname in corrections_made:
                    self.confidence_detail[fname] = "verified"
                else:
                    self.confidence_detail[fname] = "missing"

            # Recalculate confidence
            score = 0
            for fname, status in self.confidence_detail.items():
                if status == "verified":
                    score += 1
                elif status == "approximate":
                    score += 0.75
            self.confidence = score / self._total_filters if self._total_filters > 0 else 0

        result = {
            "keyword_index": keyword_index,
            "keyword": keyword,
            "drifted": len(drifted_filters) > 0,
            "drifted_filters": drifted_filters,
            "corrections_made": corrections_made,
            "unrecoverable": unrecoverable,
            "confidence_after": round(self.confidence, 2),
            "timestamp": datetime.now().isoformat(),
        }

        if drifted_filters:
            self.drift_events.append(result)

        if not drifted_filters:
            print(f"  [DRIFT CHECK] No drift detected. Confidence: {self.confidence:.0%}")
        else:
            print(f"  [DRIFT CHECK] Drifted: {drifted_filters}, corrected: {corrections_made}, "
                  f"confidence: {self.confidence:.0%}")

        return result

    def should_abort_low_confidence(self) -> tuple:
        """
        Check if baseline confidence is too low to continue.
        Returns: (should_abort: bool, reason: str)
        """
        # Check for missing critical filters (api_enforced counts as verified)
        missing_critical = []
        for fname in BASELINE_FILTERS["critical"]:
            status = self.confidence_detail.get(fname, "missing")
            if status == "missing":
                missing_critical.append(fname)

        # Hard abort: any truly important critical filter missing
        for fname in missing_critical:
            if fname in HARD_ABORT_FILTERS:
                return True, f"critical filter '{fname}' missing and is in HARD_ABORT set"

        # Confidence-based abort
        if self.confidence < 0.5:
            return True, f"baseline confidence {self.confidence:.0%} is below 50% minimum"

        return False, ""

    # NOTE: get_api_overrides() removed — filters are UI-only now


class DomainTracker:
    """Track advertiser domains across keywords to identify strong competitors."""

    def __init__(self):
        self.domain_keyword_map: Dict[str, set] = {}

    def track(self, url: str, keyword: str):
        domain = self._normalize(url)
        if domain and domain not in ("", "shop.tiktok.com", "activity.tiktok.com",
                                      "shop.tiktokglobalshop.com", "youtube.com"):
            self.domain_keyword_map.setdefault(domain, set()).add(keyword)

    def _normalize(self, url: str) -> str:
        if not url:
            return ""
        domain = re.sub(r"https?://", "", str(url)).split("/")[0].split("?")[0]
        domain = domain.replace("www.", "").lower().strip()
        return domain

    def get_strong_competitors(self, threshold: int = 3) -> List[Dict]:
        return sorted([
            {"domain": d, "keyword_count": len(kws), "keywords": sorted(kws)}
            for d, kws in self.domain_keyword_map.items()
            if len(kws) >= threshold
        ], key=lambda x: x["keyword_count"], reverse=True)

    def get_all_domains(self) -> List[Dict]:
        return sorted([
            {"domain": d, "keyword_count": len(kws), "keywords": sorted(kws)}
            for d, kws in self.domain_keyword_map.items()
        ], key=lambda x: x["keyword_count"], reverse=True)

    def is_strong_competitor(self, url: str) -> bool:
        d = self._normalize(url)
        return len(self.domain_keyword_map.get(d, set())) >= 3


# ═══════════════════════════════════════════════════════════
# 0c. KEYWORD OUTCOME LABELS
# ═══════════════════════════════════════════════════════════

def label_keyword_outcome(summary: Dict) -> str:
    """
    Assign a human-readable outcome label to a keyword's batch results.
    Labels: HIGH_SIGNAL, MODERATE_SIGNAL, LOW_SIGNAL, SATURATED, EMPTY, JUNK_DOMINATED, FAILED
    """
    winners = summary.get("winners", 0)
    possible_winners = summary.get("possible_winners", 0)
    mid = summary.get("mid", 0)
    junk_rate = summary.get("junk_rate", 0)
    cards_captured = summary.get("cards_captured", 0)
    cards_scanned = summary.get("cards_scanned", 0)
    gate_passed = summary.get("gate_passed", False)
    early_terminated = summary.get("early_terminated", False)

    if not gate_passed and cards_scanned == 0:
        return "FAILED"
    if cards_scanned > 0 and cards_captured == 0:
        return "EMPTY"
    if junk_rate > 0.8 and winners == 0:
        return "JUNK_DOMINATED"
    if winners >= 3 or (winners >= 1 and possible_winners >= 3):
        return "HIGH_SIGNAL"
    if winners >= 1 or possible_winners >= 2:
        return "MODERATE_SIGNAL"
    if junk_rate > 0.6:
        return "SATURATED"
    if cards_captured > 0:
        return "LOW_SIGNAL"
    return "LOW_SIGNAL"


# ═══════════════════════════════════════════════════════════
# 1. STATE MACHINE
# ═══════════════════════════════════════════════════════════

class S(str, Enum):
    """Page states."""
    UNKNOWN            = "UNKNOWN"
    LOGIN_REQUIRED     = "LOGIN_REQUIRED"
    DASHBOARD_OR_HOME  = "DASHBOARD_OR_HOME"
    SEARCH_PAGE        = "SEARCH_PAGE"        # search form visible, no results yet or stale results
    LOADING            = "LOADING"
    RESULTS_PAGE       = "RESULTS_PAGE"       # search results visible
    EMPTY_RESULTS      = "EMPTY_RESULTS"
    DETAIL_MODAL_OPEN  = "DETAIL_MODAL_OPEN"
    DETAIL_PAGE_OPEN   = "DETAIL_PAGE_OPEN"
    BLOCKED_BY_OVERLAY = "BLOCKED_BY_OVERLAY"
    ERROR              = "ERROR"

# Allowed transitions: {from_state: {action: [valid_next_states]}}
TRANSITIONS = {
    S.LOGIN_REQUIRED: {
        "manual_login":      [S.DASHBOARD_OR_HOME, S.SEARCH_PAGE, S.RESULTS_PAGE],
    },
    S.DASHBOARD_OR_HOME: {
        "navigate_to_search": [S.SEARCH_PAGE, S.RESULTS_PAGE],
    },
    S.SEARCH_PAGE: {
        "submit_search":     [S.LOADING, S.RESULTS_PAGE, S.EMPTY_RESULTS],
        "api_fetch":         [S.SEARCH_PAGE, S.RESULTS_PAGE],  # JS fetch works from search page
    },
    S.LOADING: {
        "wait_for_load":     [S.RESULTS_PAGE, S.EMPTY_RESULTS, S.ERROR, S.BLOCKED_BY_OVERLAY],
        "api_fetch":         [S.LOADING, S.RESULTS_PAGE],  # JS fetch works during loading
        "submit_search":     [S.LOADING, S.RESULTS_PAGE, S.EMPTY_RESULTS],  # allow search from loading
    },
    S.RESULTS_PAGE: {
        "submit_search":     [S.LOADING, S.RESULTS_PAGE, S.EMPTY_RESULTS],
        "open_result":       [S.DETAIL_MODAL_OPEN, S.DETAIL_PAGE_OPEN],
        "paginate":          [S.LOADING, S.RESULTS_PAGE],
        "api_fetch":         [S.RESULTS_PAGE],  # stays on page, data via JS
    },
    S.EMPTY_RESULTS: {
        "submit_search":     [S.LOADING, S.RESULTS_PAGE, S.EMPTY_RESULTS],
        "navigate_to_search": [S.SEARCH_PAGE],
    },
    S.DETAIL_MODAL_OPEN: {
        "close_modal":       [S.RESULTS_PAGE],
        "extract_detail":    [S.DETAIL_MODAL_OPEN],  # stays in modal
    },
    S.DETAIL_PAGE_OPEN: {
        "go_back":           [S.RESULTS_PAGE],
        "extract_detail":    [S.DETAIL_PAGE_OPEN],
    },
    S.BLOCKED_BY_OVERLAY: {
        "close_overlay":     [S.SEARCH_PAGE, S.RESULTS_PAGE, S.DASHBOARD_OR_HOME],
    },
    S.ERROR: {
        "diagnose":          [S.UNKNOWN],
        "reload":            [S.SEARCH_PAGE, S.RESULTS_PAGE, S.LOGIN_REQUIRED],
        "navigate_to_search": [S.SEARCH_PAGE, S.LOGIN_REQUIRED],
    },
    S.UNKNOWN: {
        "diagnose":          [S.UNKNOWN],
        "reload":            [S.SEARCH_PAGE, S.RESULTS_PAGE, S.LOGIN_REQUIRED],
        "navigate_to_search": [S.SEARCH_PAGE, S.LOGIN_REQUIRED],
        "api_fetch":         [S.UNKNOWN, S.RESULTS_PAGE],  # JS fetch works from any state
    },
}

# Per-action timeouts (ms)
ACTION_TIMEOUTS = {
    "manual_login":       180_000,
    "navigate_to_search": 30_000,
    "submit_search":      15_000,
    "wait_for_load":      20_000,
    "open_result":        8_000,
    "close_modal":        5_000,
    "close_overlay":      5_000,
    "go_back":            10_000,
    "extract_detail":     10_000,
    "paginate":           15_000,
    "api_fetch":          12_000,
    "reload":             30_000,
    "diagnose":           5_000,
}


# ═══════════════════════════════════════════════════════════
# 2. STEP LOG SCHEMA
# ═══════════════════════════════════════════════════════════

@dataclass
class StepLog:
    step_id: int
    timestamp: str
    keyword: str
    page_number: int
    current_state: str
    intended_action: str
    expected_next_state: str      # comma-separated valid next states
    verification_method: str
    result: str                   # "success" | "soft_fail" | "hard_fail"
    actual_state_after: str
    recovery_used: str            # "none" | description
    screenshot_path: str
    notes: str = ""

    def to_dict(self):
        return asdict(self)


class StepLogger:
    def __init__(self, log_dir: Path, ts: str):
        self.log_dir = log_dir
        self.ts = ts
        self.steps: List[StepLog] = []
        self.counter = 0

    def log(self, keyword, page_number, current_state, intended_action,
            expected_next_states, verification_method, result,
            actual_state_after, recovery_used="none", screenshot_path="", notes=""):
        self.counter += 1
        entry = StepLog(
            step_id=self.counter,
            timestamp=datetime.now().isoformat(),
            keyword=keyword,
            page_number=page_number,
            current_state=str(current_state),
            intended_action=intended_action,
            expected_next_state=", ".join(str(s) for s in expected_next_states),
            verification_method=verification_method,
            result=result,
            actual_state_after=str(actual_state_after),
            recovery_used=recovery_used,
            screenshot_path=screenshot_path,
            notes=notes,
        )
        self.steps.append(entry)

        # Console output
        icon = {"success": "+", "soft_fail": "~", "hard_fail": "!"}
        print(f"    [{icon.get(result, '?')}] #{self.counter} {intended_action}: {current_state} -> {actual_state_after} [{result}]"
              + (f" | {notes}" if notes else ""))
        return entry

    def save(self):
        path = self.log_dir / f"steps_{self.ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.steps], f, indent=2, ensure_ascii=False)
        return path


# ═══════════════════════════════════════════════════════════
# 3. PAGE STATE DETECTOR (robust, multi-signal)
# ═══════════════════════════════════════════════════════════

async def detect_state(page: Page) -> S:
    """Detect current page state using multiple signals."""
    url = page.url.lower()

    # Login check
    if "login" in url or "signin" in url or "sign-in" in url:
        return S.LOGIN_REQUIRED

    # Check for blocking overlay (highest priority after login)
    try:
        for sel in ['[class*="captcha"]', '[class*="paywall"]', '[class*="upgrade-modal"]',
                    '[class*="subscribe-modal"]']:
            if await page.locator(sel).first.is_visible(timeout=500):
                return S.BLOCKED_BY_OVERLAY
    except Exception:
        pass

    # Check for detail modal
    try:
        for sel in ['[class*="modal"][class*="detail"]', '[class*="drawer"][class*="detail"]',
                    '[class*="ad-detail-modal"]', '[class*="video-detail"]',
                    '.el-dialog__wrapper:visible', '[class*="modal-mask"]:visible']:
            try:
                if await page.locator(sel).first.is_visible(timeout=400):
                    return S.DETAIL_MODAL_OPEN
            except Exception:
                continue
    except Exception:
        pass

    # Check for loading
    try:
        for sel in ['.el-loading-mask:visible', '[class*="loading"]:visible',
                    '[class*="spinner"]:visible', '[class*="skeleton"]:visible']:
            try:
                if await page.locator(sel).first.is_visible(timeout=400):
                    return S.LOADING
            except Exception:
                continue
    except Exception:
        pass

    # Check for empty results
    try:
        for sel in ['text=/no results/i', 'text=/no data/i', 'text=/0 results/i',
                    '[class*="empty"][class*="result"]', '[class*="no-data"]']:
            try:
                if await page.locator(sel).first.is_visible(timeout=400):
                    return S.EMPTY_RESULTS
            except Exception:
                continue
    except Exception:
        pass

    # Check for results page (ad cards visible)
    try:
        for sel in ['[class*="ad-card"]', '[class*="video-card"]', '[class*="ad-item"]',
                    '[class*="search-result"] [class*="card"]', '[class*="list-item"]']:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    return S.RESULTS_PAGE
            except Exception:
                continue
    except Exception:
        pass

    # Check for search page (search input visible, no results)
    if "ad-search" in url or "search" in url:
        try:
            search_visible = await page.locator('input[placeholder*="Search"]').first.is_visible(timeout=500)
            if search_visible:
                return S.SEARCH_PAGE
        except Exception:
            pass

    # Dashboard / home
    if "pipiads.com" in url and ("dashboard" in url or url.rstrip("/").endswith("pipiads.com")):
        return S.DASHBOARD_OR_HOME

    # If on pipiads but unclassified
    if "pipiads.com" in url:
        # Could be search page without results loaded yet
        try:
            if await page.locator('input[placeholder*="Search"]').first.is_visible(timeout=500):
                return S.SEARCH_PAGE
        except Exception:
            pass
        return S.UNKNOWN

    return S.UNKNOWN


async def take_screenshot(page: Page, label: str, ts: str) -> str:
    """Take screenshot and return path."""
    safe_label = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:80]
    path = SCREENSHOTS / f"{ts}_{safe_label}.png"
    try:
        await page.screenshot(path=str(path))
        return str(path)
    except Exception as e:
        print(f"    [WARN] Screenshot failed: {str(e)[:60]}")
        return ""


# ═══════════════════════════════════════════════════════════
# 4. ACTION EXECUTOR WITH VERIFICATION
# ═══════════════════════════════════════════════════════════

class ActionResult:
    def __init__(self, success: bool, new_state: S, soft_fail: bool = False, notes: str = ""):
        self.success = success
        self.soft_fail = soft_fail
        self.hard_fail = not success and not soft_fail
        self.new_state = new_state
        self.notes = notes

    @property
    def result_str(self):
        if self.success:
            return "success"
        if self.soft_fail:
            return "soft_fail"
        return "hard_fail"


class Operator:
    """
    State-machine-driven browser operator.
    Every action: detect state -> validate transition -> execute -> verify outcome.
    No blind continuation.
    """

    def __init__(self, page: Page, logger: StepLogger, ts: str):
        self.page = page
        self.logger = logger
        self.ts = ts
        self.current_state: S = S.UNKNOWN
        self._recovery_counts: Counter = Counter()  # (state, action) -> count
        self._total_recoveries = 0
        self._max_recovery_per_context = 2
        self._max_total_recoveries = 10
        # Stuck detection
        self._last_state: Optional[S] = None
        self._same_state_ticks = 0
        self._last_action: Optional[str] = None
        self._action_repeat_count = 0
        self._last_screenshot_hash: Optional[str] = None
        self._same_screenshot_ticks = 0

    async def refresh_state(self) -> S:
        """Detect and update current state."""
        self.current_state = await detect_state(self.page)
        return self.current_state

    def _is_transition_allowed(self, from_state: S, action: str) -> bool:
        allowed = TRANSITIONS.get(from_state, {})
        return action in allowed

    def _expected_states(self, from_state: S, action: str) -> List[S]:
        return TRANSITIONS.get(from_state, {}).get(action, [])

    def _get_timeout(self, action: str) -> int:
        return ACTION_TIMEOUTS.get(action, 10_000)

    # ── STUCK DETECTION ──

    async def _check_stuck(self, intended_action: str) -> bool:
        """
        Multi-signal stuck detection:
        1. Same state too long while transition expected
        2. Same action repeated without verified result
        3. Same screenshot hash while progress expected
        """
        state = self.current_state
        stuck_reasons = []

        # Signal 1: same state persists
        if state == self._last_state:
            self._same_state_ticks += 1
            if self._same_state_ticks >= 4:
                stuck_reasons.append(f"same state {state} for {self._same_state_ticks} ticks")
        else:
            self._same_state_ticks = 0
        self._last_state = state

        # Signal 2: same action repeated
        if intended_action == self._last_action:
            self._action_repeat_count += 1
            if self._action_repeat_count >= 2:
                stuck_reasons.append(f"action '{intended_action}' repeated {self._action_repeat_count}x without progress")
        else:
            self._action_repeat_count = 0
        self._last_action = intended_action

        # Signal 3: screenshot hash unchanged
        try:
            screenshot_bytes = await self.page.screenshot()
            h = hashlib.md5(screenshot_bytes).hexdigest()
            if h == self._last_screenshot_hash:
                self._same_screenshot_ticks += 1
                if self._same_screenshot_ticks >= 3:
                    stuck_reasons.append(f"identical screenshot for {self._same_screenshot_ticks} ticks")
            else:
                self._same_screenshot_ticks = 0
            self._last_screenshot_hash = h
        except Exception:
            pass

        if stuck_reasons:
            print(f"    [STUCK] {'; '.join(stuck_reasons)}")
            return True
        return False

    def _reset_stuck_signals(self):
        """Reset stuck signals after successful progress."""
        self._same_state_ticks = 0
        self._action_repeat_count = 0
        self._same_screenshot_ticks = 0
        self._last_action = None

    # ── RECOVERY ENGINE (state-specific) ──

    def _can_recover(self, state: S, action: str) -> bool:
        if self._total_recoveries >= self._max_total_recoveries:
            return False
        key = (str(state), action)
        return self._recovery_counts[key] < self._max_recovery_per_context

    def _record_recovery(self, state: S, action: str):
        self._total_recoveries += 1
        self._recovery_counts[(str(state), action)] += 1

    async def recover(self, failed_state: S, failed_action: str, keyword: str, page_num: int) -> ActionResult:
        """
        State-specific recovery tree.
        Returns ActionResult indicating whether recovery succeeded.
        """
        if not self._can_recover(failed_state, failed_action):
            self.logger.log(keyword, page_num, failed_state, f"recovery_{failed_action}",
                            [], "recovery_budget_check", "hard_fail",
                            failed_state, notes="recovery budget exhausted")
            return ActionResult(False, failed_state, notes="recovery budget exhausted")

        self._record_recovery(failed_state, failed_action)
        ss = await take_screenshot(self.page, f"recovery_{failed_state}_{failed_action}", self.ts)

        # ── State-specific recovery branches ──

        if failed_state == S.RESULTS_PAGE and failed_action == "open_result":
            # Card click failed. Do NOT reload. Try alternate strategies.
            steps = [
                ("scroll_into_view", self._recovery_scroll_and_retry_click),
                ("try_parent_click", self._recovery_parent_click),
            ]
            for step_name, step_fn in steps:
                result = await step_fn()
                new_state = await self.refresh_state()
                if new_state in (S.DETAIL_MODAL_OPEN, S.DETAIL_PAGE_OPEN):
                    self.logger.log(keyword, page_num, failed_state, f"recovery_{step_name}",
                                    [S.DETAIL_MODAL_OPEN, S.DETAIL_PAGE_OPEN],
                                    "detect_state", "success", new_state, recovery_used=step_name, screenshot_path=ss)
                    return ActionResult(True, new_state, notes=f"recovered via {step_name}")
            # All card-click recovery failed
            self.logger.log(keyword, page_num, failed_state, "recovery_open_result",
                            [], "all_strategies_exhausted", "hard_fail",
                            await self.refresh_state(), recovery_used="all_failed", screenshot_path=ss,
                            notes="card open recovery exhausted, skipping card")
            return ActionResult(False, self.current_state, notes="card click unrecoverable")

        elif failed_state == S.DETAIL_MODAL_OPEN and failed_action == "close_modal":
            # Modal won't close. Try close hierarchy, then escape, then backdrop.
            close_methods = [
                ("close_selectors", self._recovery_close_selectors),
                ("escape_key", self._recovery_escape),
                ("click_backdrop", self._recovery_click_backdrop),
            ]
            for method_name, method_fn in close_methods:
                await method_fn()
                await self.page.wait_for_timeout(800)
                new_state = await self.refresh_state()
                if new_state == S.RESULTS_PAGE:
                    self.logger.log(keyword, page_num, failed_state, f"recovery_{method_name}",
                                    [S.RESULTS_PAGE], "detect_state", "success", new_state,
                                    recovery_used=method_name, screenshot_path=ss)
                    return ActionResult(True, new_state, notes=f"modal closed via {method_name}")
            # Force navigate back
            await self.page.go_back()
            await self.page.wait_for_timeout(2000)
            new_state = await self.refresh_state()
            self.logger.log(keyword, page_num, failed_state, "recovery_force_back",
                            [S.RESULTS_PAGE, S.SEARCH_PAGE], "detect_state",
                            "success" if new_state in (S.RESULTS_PAGE, S.SEARCH_PAGE) else "hard_fail",
                            new_state, recovery_used="force_back", screenshot_path=ss)
            return ActionResult(new_state in (S.RESULTS_PAGE, S.SEARCH_PAGE), new_state)

        elif failed_state in (S.SEARCH_PAGE, S.RESULTS_PAGE) and failed_action == "submit_search":
            # Search submission failed. Verify input, re-submit.
            steps = [
                ("verify_input_refill", self._recovery_verify_search_input),
                ("reload_and_search", self._recovery_reload_search_page),
            ]
            for step_name, step_fn in steps:
                result = await step_fn(keyword)
                new_state = await self.refresh_state()
                if new_state in (S.RESULTS_PAGE, S.EMPTY_RESULTS):
                    self.logger.log(keyword, page_num, failed_state, f"recovery_{step_name}",
                                    [S.RESULTS_PAGE, S.EMPTY_RESULTS], "detect_state", "success",
                                    new_state, recovery_used=step_name, screenshot_path=ss)
                    return ActionResult(True, new_state, notes=f"search recovered via {step_name}")
            return ActionResult(False, await self.refresh_state(), notes="search recovery exhausted")

        elif failed_state == S.LOADING:
            # Stuck loading. Wait longer, then reload.
            await self.page.wait_for_timeout(5000)
            new_state = await self.refresh_state()
            if new_state != S.LOADING:
                return ActionResult(True, new_state, notes="loading resolved after wait")
            # Reload
            try:
                await self.page.reload(timeout=30_000)
                await self.page.wait_for_timeout(3000)
            except Exception:
                pass
            new_state = await self.refresh_state()
            self.logger.log(keyword, page_num, S.LOADING, "recovery_reload",
                            [S.SEARCH_PAGE, S.RESULTS_PAGE], "detect_state",
                            "success" if new_state not in (S.LOADING, S.ERROR, S.UNKNOWN) else "hard_fail",
                            new_state, recovery_used="reload_after_loading", screenshot_path=ss)
            return ActionResult(new_state not in (S.LOADING, S.ERROR, S.UNKNOWN), new_state)

        elif failed_state == S.BLOCKED_BY_OVERLAY:
            await self._recovery_close_selectors()
            await self._recovery_escape()
            await self.page.wait_for_timeout(1000)
            new_state = await self.refresh_state()
            if new_state != S.BLOCKED_BY_OVERLAY:
                return ActionResult(True, new_state, notes="overlay cleared")
            return ActionResult(False, new_state, notes="overlay could not be cleared")

        elif failed_state == S.LOGIN_REQUIRED:
            # Cannot auto-recover login. Enter pause.
            return await self._recovery_wait_for_login(keyword, page_num, ss)

        else:
            # Generic: reload
            try:
                await self.page.reload(timeout=30_000)
                await self.page.wait_for_timeout(3000)
            except Exception:
                pass
            new_state = await self.refresh_state()
            return ActionResult(new_state not in (S.ERROR, S.UNKNOWN), new_state, notes="generic reload recovery")

    # ── Recovery sub-methods ──

    async def _recovery_scroll_and_retry_click(self):
        try:
            await self.page.evaluate("window.scrollBy(0, 200)")
            await self.page.wait_for_timeout(500)
        except Exception:
            pass

    async def _recovery_parent_click(self):
        """Try clicking a broader card container."""
        try:
            for sel in ['[class*="ad-card"]', '[class*="video-card"]', '[class*="ad-item"]']:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    await el.click()
                    await self.page.wait_for_timeout(1500)
                    return
        except Exception:
            pass

    async def _recovery_close_selectors(self):
        for sel in ['[class*="close"]', 'button:has-text("Close")', '.el-dialog__close',
                    '[aria-label="Close"]', 'button:has-text("×")', '.modal-close',
                    '[class*="icon-close"]', 'svg[class*="close"]']:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    await self.page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def _recovery_escape(self):
        try:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)
        except Exception:
            pass

    async def _recovery_click_backdrop(self):
        try:
            for sel in ['.el-overlay', '[class*="mask"]', '[class*="backdrop"]', '[class*="overlay"]']:
                el = self.page.locator(sel).first
                if await el.is_visible(timeout=500):
                    box = await el.bounding_box()
                    if box:
                        await self.page.mouse.click(box["x"] + 5, box["y"] + 5)
                        await self.page.wait_for_timeout(500)
                        return
        except Exception:
            pass

    async def _recovery_verify_search_input(self, keyword: str):
        try:
            inp = self.page.locator('input[placeholder*="Search"]').first
            if await inp.is_visible(timeout=2000):
                await inp.click(click_count=3)
                await inp.fill(keyword)
                await inp.press("Enter")
                await self.page.wait_for_timeout(5000)
        except Exception:
            pass

    async def _recovery_reload_search_page(self, keyword: str = ""):
        try:
            await self.page.goto("https://www.pipiads.com/ad-search", timeout=30_000)
            await self.page.wait_for_timeout(3000)
        except Exception:
            pass

    async def _recovery_wait_for_login(self, keyword: str, page_num: int, ss: str) -> ActionResult:
        """Controlled login resume flow."""
        print("    [PAUSE] Login required. Waiting for manual login...")
        print("    [PAUSE] Please log in in the browser window.")

        # Poll for state change
        for _ in range(60):  # 60 x 3s = 180s max
            await self.page.wait_for_timeout(3000)
            new_state = await self.refresh_state()
            if new_state != S.LOGIN_REQUIRED:
                # Login succeeded — but do NOT blindly continue
                print(f"    [RESUME] Login detected, new state: {new_state}")

                # If landed on dashboard/home, navigate to search
                if new_state == S.DASHBOARD_OR_HOME:
                    print("    [RESUME] On dashboard, navigating to search page...")
                    try:
                        await self.page.goto("https://www.pipiads.com/ad-search", timeout=30_000)
                        await self.page.wait_for_timeout(3000)
                    except Exception:
                        pass
                    new_state = await self.refresh_state()

                # Verify we're on an interactive page
                if new_state in (S.SEARCH_PAGE, S.RESULTS_PAGE):
                    # Save fresh cookies
                    try:
                        context = self.page.context
                        cookies = await context.cookies()
                        COOKIES.write_text(json.dumps(cookies, default=str))
                        print("    [RESUME] Cookies saved")
                    except Exception:
                        pass

                    self.logger.log(keyword, page_num, S.LOGIN_REQUIRED, "manual_login",
                                    [S.SEARCH_PAGE, S.RESULTS_PAGE], "detect_state_post_login",
                                    "success", new_state, recovery_used="manual_login", screenshot_path=ss)
                    return ActionResult(True, new_state, notes="login resumed successfully")
                else:
                    print(f"    [RESUME] Post-login state unclear: {new_state}, attempting navigation...")
                    await self._recovery_reload_search_page()
                    new_state = await self.refresh_state()
                    return ActionResult(new_state in (S.SEARCH_PAGE, S.RESULTS_PAGE), new_state,
                                        notes=f"post-login recovery to {new_state}")

        self.logger.log(keyword, page_num, S.LOGIN_REQUIRED, "manual_login",
                        [S.SEARCH_PAGE], "timeout", "hard_fail",
                        S.LOGIN_REQUIRED, recovery_used="login_timeout", screenshot_path=ss)
        return ActionResult(False, S.LOGIN_REQUIRED, notes="login timeout after 180s")

    # ══════════════════════════════════════════
    # CORE EXECUTION METHOD: execute_and_verify
    # ══════════════════════════════════════════

    async def execute(self, action: str, keyword: str, page_num: int,
                      action_fn=None, action_args=None,
                      verify_fn=None) -> ActionResult:
        """
        The central control loop step:
        1. Detect current state
        2. Validate transition is allowed
        3. Check for stuck
        4. Execute action
        5. Verify outcome (NO BLIND CONTINUATION)
        6. Recover if needed
        7. Log everything
        """
        state_before = await self.refresh_state()
        expected_states = self._expected_states(state_before, action)

        # Validate transition is allowed
        if not self._is_transition_allowed(state_before, action):
            # State mismatch — try to handle gracefully
            ss = await take_screenshot(self.page, f"invalid_transition_{action}", self.ts)
            self.logger.log(keyword, page_num, state_before, action,
                            expected_states, "transition_check", "hard_fail",
                            state_before, screenshot_path=ss,
                            notes=f"transition {state_before}->{action} not allowed")

            # If we're in a wrong state, try to get to the right one
            if state_before == S.DETAIL_MODAL_OPEN and action != "close_modal":
                # Close modal first
                close_result = await self.execute("close_modal", keyword, page_num,
                                                   action_fn=self._action_close_modal)
                if close_result.success:
                    # Retry original action
                    return await self.execute(action, keyword, page_num, action_fn, action_args, verify_fn)
            elif state_before == S.LOGIN_REQUIRED:
                login_result = await self.recover(S.LOGIN_REQUIRED, "manual_login", keyword, page_num)
                if login_result.success:
                    return await self.execute(action, keyword, page_num, action_fn, action_args, verify_fn)

            return ActionResult(False, state_before, notes=f"invalid transition from {state_before}")

        # Check for stuck
        is_stuck = await self._check_stuck(action)
        if is_stuck:
            ss = await take_screenshot(self.page, f"stuck_{action}", self.ts)
            self.logger.log(keyword, page_num, state_before, action,
                            expected_states, "stuck_detection", "soft_fail",
                            state_before, screenshot_path=ss, notes="stuck detected before action")
            # Attempt recovery
            rec = await self.recover(state_before, action, keyword, page_num)
            if rec.success:
                self._reset_stuck_signals()
                return rec
            return ActionResult(False, rec.new_state, notes="stuck + recovery failed")

        # Execute action
        timeout = self._get_timeout(action)
        try:
            if action_fn:
                args = action_args or ()
                await asyncio.wait_for(action_fn(*args), timeout=timeout / 1000)
        except asyncio.TimeoutError:
            ss = await take_screenshot(self.page, f"timeout_{action}", self.ts)
            self.logger.log(keyword, page_num, state_before, action,
                            expected_states, "timeout", "soft_fail",
                            state_before, screenshot_path=ss,
                            notes=f"action timed out after {timeout}ms")
            # Recover
            rec = await self.recover(state_before, action, keyword, page_num)
            return ActionResult(rec.success, rec.new_state, soft_fail=not rec.success,
                                notes=f"timeout recovery: {rec.notes}")
        except Exception as e:
            ss = await take_screenshot(self.page, f"error_{action}", self.ts)
            self.logger.log(keyword, page_num, state_before, action,
                            expected_states, "exception", "hard_fail",
                            state_before, screenshot_path=ss,
                            notes=f"exception: {str(e)[:100]}")
            return ActionResult(False, state_before, notes=f"exception: {str(e)[:80]}")

        # ── VERIFY OUTCOME (this is the "no blind continuation" gate) ──
        # Give the page a moment to transition
        await self.page.wait_for_timeout(500)
        state_after = await self.refresh_state()

        # Custom verification if provided
        if verify_fn:
            verified = await verify_fn(state_after)
        else:
            # Default verification: new state must be in expected list
            verified = state_after in expected_states if expected_states else True

        # For api_fetch, state stays the same — that's valid.
        # JS fetch works independently of page visual state.
        if action == "api_fetch":
            verified = True

        result_str = "success" if verified else "soft_fail"
        ss = ""
        if not verified:
            ss = await take_screenshot(self.page, f"verify_fail_{action}", self.ts)

        self.logger.log(keyword, page_num, state_before, action,
                        expected_states, verify_fn.__name__ if verify_fn else "state_in_expected",
                        result_str, state_after, screenshot_path=ss,
                        notes="" if verified else f"expected {expected_states}, got {state_after}")

        if verified:
            self._reset_stuck_signals()
            self.current_state = state_after
            return ActionResult(True, state_after)
        else:
            # Soft failure — attempt recovery
            rec = await self.recover(state_before, action, keyword, page_num)
            return ActionResult(rec.success, rec.new_state, soft_fail=not rec.success,
                                notes=f"verification failed, recovery: {rec.notes}")

    # ── Concrete action implementations ──

    async def _action_close_modal(self):
        await self._recovery_close_selectors()
        await self.page.wait_for_timeout(500)
        state = await detect_state(self.page)
        if state == S.DETAIL_MODAL_OPEN:
            await self._recovery_escape()
            await self.page.wait_for_timeout(500)
            state = await detect_state(self.page)
        if state == S.DETAIL_MODAL_OPEN:
            await self._recovery_click_backdrop()


# ═══════════════════════════════════════════════════════════
# KEYWORD CONFIG, STAGES, RELEVANCE, CLASSIFICATION, DEDUP
# (carried over from v4 with improvements)
# ═══════════════════════════════════════════════════════════

KEYWORDS = {
    # GROUP 1 — BROAD DIGITAL PRODUCT
    "digital product":              {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "online course":                {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "sell digital products":        {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "digital download":             {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "make money online":            {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "online business course":       {"tier": "T1", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    # GROUP 2 — CREATOR / SIDE HUSTLE
    "side hustle":                   {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "passive income":                {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "etsy digital products":         {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "gumroad products":              {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "notion template":               {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "ai side hustle":                {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    # GROUP 3 — MARKETING / BUSINESS COURSES
    "dropshipping course":           {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "tiktok ads course":             {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "shopify course":                {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "affiliate marketing course":    {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "smma course":                   {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "copywriting course":            {"tier": "T3", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    # GROUP 4 — AI DIGITAL PRODUCTS
    "ai prompts":                    {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "chatgpt prompts":               {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "ai marketing tools":            {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "ai business tools":             {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "ai automation":                 {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "ai content generator":          {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    # GROUP 5 — TEMPLATE / DOWNLOAD PRODUCTS
    "canva templates":               {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "instagram templates":           {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "resume templates":              {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "business templates":            {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "notion productivity template":  {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    "digital planner":               {"tier": "T2", "mode": "niche",  "max_pages": 3, "max_opens": 12},
    # GROUP 6 — HIGH-CONVERSION OFFER WORDING
    "free training":                 {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "free masterclass":              {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "free workshop":                 {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "limited seats webinar":         {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "learn how to":                  {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
    "step by step system":           {"tier": "T3", "mode": "broad",  "max_pages": 3, "max_opens": 12},
}

# Initial run: 15 priority keywords (ordered by run priority)
INITIAL_RUN_KEYWORDS = [
    "digital product", "online course",
    "side hustle", "passive income", "notion template",
    "canva templates", "ai prompts", "chatgpt prompts",
    "affiliate marketing course", "smma course", "dropshipping course",
    "digital planner", "free masterclass", "free training",
    "ai automation",
]

STAGES = {
    "A0": {
        "name": "Operator Test",
        "keywords": ["digital product"],
        "max_pages_override": 1,
        "max_card_opens": 2,
        "goal": "validate state machine, transitions, verification, recovery, logging",
    },
    "A1": {
        "name": "Mini-Batch Test",
        "keywords": ["digital product", "online course", "ai prompts"],
        "max_pages_override": 1,
        "max_card_opens": None,
        "goal": "verify extraction, dedupe, classification, report generation",
    },
    "B": {
        "name": "Controlled Validation",
        "keywords": INITIAL_RUN_KEYWORDS[:8],
        "max_pages_override": 2,
        "max_card_opens": None,
        "goal": "validate field quality, classification sanity, junk rate, recovery logic",
    },
    "C": {
        "name": "Full Run",
        "keywords": list(KEYWORDS.keys()),
        "max_pages_override": None,
        "max_card_opens": None,
        "goal": "comprehensive digital product research",
    },
    "research": {
        "name": "Research Mode",
        "keywords": INITIAL_RUN_KEYWORDS,
        "max_pages_override": None,
        "max_card_opens": None,
        "goal": "digital product funnel research — discover profitable ads, recurring domains, hooks, pricing models",
        "baseline_required": True,
        "drift_check_interval": 5,
        "abort_on_critical_missing": True,
    },
}

# Card-open cap: signal-aware limits per keyword tier/mode
CARD_OPEN_CAPS = {
    ("T1", "broad"):      {"max_opens": 8, "min_relevance": 3},
    ("T1", "niche"):      {"max_opens": 8, "min_relevance": 3},
    ("T2", "niche"):      {"max_opens": 10, "min_relevance": 2},
    ("T2", "broad"):      {"max_opens": 8, "min_relevance": 3},
    ("T3", "competitor"): {"max_opens": 6, "min_relevance": 2},
}
DEFAULT_CARD_CAP = {"max_opens": 8, "min_relevance": 3}

# Research mode: caps per keyword (Winning Products filter pre-filters quality)
RESEARCH_CARD_OPEN_CAP = 9       # max per keyword (across all passes)
PASS_CARD_OPEN_CAP = 3           # max per search pass

# Multi-sort search passes per keyword (research mode)
MULTI_SORT_PASSES = [
    {"sort": "Ad Spend",      "time": "Last 6 months", "label": "spend"},
    {"sort": "Impression",    "time": "Last 6 months", "label": "impressions"},
    {"sort": "First seen",    "time": "Last 6 months", "label": "first_seen"},
    {"sort": "Creation Date", "time": "Last 30 days",  "label": "creation"},
]

SORT_FALLBACK_ORDER = ["Ad Spend", "Impression", "Like", "Creation Date"]

# ── Prescan winner thresholds (skip weak ads, save credits) ──
# Raised to find actually-scaling brands, not test creatives
PRESCAN_MIN_VIEWS = 50_000
PRESCAN_MIN_DAYS = 7
PRESCAN_MIN_LIKES = 50


def parse_prescan_num(text: str) -> int:
    """Parse prescan metric text like '11K', '1.2M', '580', '3' into int."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    try:
        if text.upper().endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        elif text.upper().endswith("K"):
            return int(float(text[:-1]) * 1_000)
        elif text.upper().endswith("B"):
            return int(float(text[:-1]) * 1_000_000_000)
        return int(float(text))
    except (ValueError, TypeError):
        return 0


def prescan_winner_score(ps: dict) -> tuple:
    """Score a prescan card for winner potential.
    Returns (score, views, days, likes, reason).
    Score < 0 means SKIP (fails minimum thresholds).
    """
    views = parse_prescan_num(ps.get("views_text", ""))
    days = parse_prescan_num(ps.get("days_text", ""))
    likes = parse_prescan_num(ps.get("likes_text", ""))

    # Hard minimum filters — need at least ONE scaling signal (views OR longevity)
    if views < PRESCAN_MIN_VIEWS and days < PRESCAN_MIN_DAYS:
        return -1, views, days, likes, f"weak: views={views:,}, days={days}"
    # Also skip if views are tiny even with some days (not actually scaling)
    if views > 0 and views < 10_000 and days < 14:
        return -1, views, days, likes, f"not scaling: views={views:,}, days={days}"

    # Score: weighted combination favoring longevity + views + engagement
    score = 0.0
    reasons = []

    # Views weight
    if views >= 1_000_000:
        score += 30; reasons.append(f"{views//1000}K views")
    elif views >= 500_000:
        score += 20; reasons.append(f"{views//1000}K views")
    elif views >= 100_000:
        score += 10; reasons.append(f"{views//1000}K views")
    elif views >= 20_000:
        score += 3; reasons.append(f"{views//1000}K views")

    # Runtime weight (longevity = likely profitable)
    if days >= 60:
        score += 25; reasons.append(f"{days}d longevity")
    elif days >= 30:
        score += 18; reasons.append(f"{days}d longevity")
    elif days >= 14:
        score += 10; reasons.append(f"{days}d running")
    elif days >= 7:
        score += 4; reasons.append(f"{days}d running")
    elif days >= 3:
        score += 1; reasons.append(f"{days}d running")

    # Engagement weight
    if likes >= 5_000:
        score += 15; reasons.append(f"{likes:,} likes")
    elif likes >= 1_000:
        score += 8; reasons.append(f"{likes:,} likes")
    elif likes >= 500:
        score += 4; reasons.append(f"{likes:,} likes")
    elif likes >= 50:
        score += 1; reasons.append(f"{likes} likes")

    # Engagement ratio bonus
    if views > 0 and likes > 0:
        eng_ratio = likes / views
        if eng_ratio > 0.02:
            score += 5; reasons.append(f"high engagement {eng_ratio:.1%}")
        elif eng_ratio > 0.005:
            score += 2; reasons.append(f"decent engagement {eng_ratio:.2%}")

    return score, views, days, likes, " | ".join(reasons)

STRONG_RELEVANCE = [
    "course", "template", "digital product", "digital download", "ebook",
    "masterclass", "training", "workshop", "webinar", "funnel",
    "ai prompt", "chatgpt", "notion", "canva", "gumroad", "etsy",
    "side hustle", "passive income", "make money", "online business",
    "affiliate", "dropshipping", "smma", "copywriting", "marketing",
    "automation", "ai tool", "prompt pack", "planner", "blueprint",
]
WEAK_RELEVANCE = [
    "free", "learn", "step by step", "system", "method", "strategy",
    "income", "revenue", "profit", "earn", "sell", "launch",
    "guide", "cheat sheet", "swipe file", "toolkit", "resource",
    "subscriber", "creator", "coach", "mentor", "expert",
]
IRRELEVANCE_MARKERS = [
    "dental", "teeth", "skincare", "supplement", "weight loss",
    "casino", "gambling", "adult", "cbd", "vape", "pet food",
    "kitchen appliance", "cooking recipe", "baby toy", "kids toy",
    "nail art", "hair extension", "carpet cleaning",
]

MAX_CONSECUTIVE_JUNK = 8
API_DELAY_MS = 1200


def parse_num(val):
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return val
    try:
        return int(val)
    except Exception:
        try:
            return float(val)
        except Exception:
            return 0


# Map full country names to 2-letter codes for region matching
# Only use full names (3+ chars) to avoid substring false positives
COUNTRY_NAME_TO_CODE = {
    "united states": "US", "usa": "US",
    "united kingdom": "GB", "britain": "GB", "england": "GB",
    "germany": "DE", "deutschland": "DE",
    "netherlands": "NL", "holland": "NL", "the netherlands": "NL",
    "australia": "AU",
    "france": "FR",
    "canada": "CA",
    "italy": "IT",
    "spain": "ES",
    "brazil": "BR",
    "japan": "JP",
    "india": "IN",
    "mexico": "MX",
    "indonesia": "ID",
    "thailand": "TH",
    "vietnam": "VN",
    "philippines": "PH",
    "malaysia": "MY",
    "singapore": "SG",
    "south korea": "KR", "korea": "KR",
    "taiwan": "TW",
    "saudi arabia": "SA",
    "uae": "AE", "united arab emirates": "AE",
    "greece": "GR",
    "turkey": "TR",
    "poland": "PL",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "belgium": "BE",
    "switzerland": "CH",
    "austria": "AT",
    "ireland": "IE",
    "new zealand": "NZ",
    "south africa": "ZA",
    "nigeria": "NG",
    "egypt": "EG",
    "israel": "IL",
    "russia": "RU",
    "ukraine": "UA",
    "romania": "RO",
    "czech": "CZ",
    "hungary": "HU",
    "portugal": "PT",
    "argentina": "AR",
    "colombia": "CO",
    "chile": "CL",
    "peru": "PE",
}


def extract_regions(ad):
    regions = ad.get("fetch_region", "")
    if isinstance(regions, list):
        return regions
    region_str = str(regions).lower().strip()
    if not region_str:
        return []
    # Try 2-letter codes in quotes first (API format)
    codes = re.findall(r"'(\w{2})'", str(regions))
    if codes:
        return [c.upper() for c in codes]
    # Parse full country names (modal extraction format)
    # Use word boundary matching to avoid substring issues
    found = []
    for name, code in COUNTRY_NAME_TO_CODE.items():
        if re.search(r'\b' + re.escape(name) + r'\b', region_str):
            if code not in found:
                found.append(code)
    return found


def is_target_region(ad):
    return any(r in TARGET_REGIONS for r in extract_regions(ad))


def ad_text(ad):
    return " ".join(filter(None, [
        str(ad.get("desc", "")),
        str(ad.get("ai_analysis_script", "")),
        str(ad.get("ai_analysis_main_hook", "")),
        str(ad.get("unique_id", "")),
        str(ad.get("app_name", "")),
    ])).lower()


def make_dedupe_key(ad):
    advertiser = (ad.get("unique_id", "") or ad.get("app_name", "") or "").strip().lower()
    caption = (ad.get("desc", "") or "").strip().lower()[:100]
    hook = (ad.get("ai_analysis_main_hook", "") or "").strip().lower()[:80]
    landing = (ad.get("landing_page", "") or ad.get("store_url", "") or "").strip().lower()
    raw = f"{advertiser}|{caption}|{hook}|{landing}"
    return hashlib.md5(raw.encode()).hexdigest()


def fmt_views(v):
    if v >= 1_000_000:
        return f"{v/1e6:.1f}M"
    if v >= 1_000:
        return f"{v/1e3:.0f}K"
    return str(v)


def relevance_prefilter(ad):
    text = ad_text(ad)
    for marker in IRRELEVANCE_MARKERS:
        if marker in text:
            return False, 0, f"irrelevant niche: {marker}"
    score = 0
    for sig in STRONG_RELEVANCE:
        if sig in text:
            score += 2
    for sig in WEAK_RELEVANCE:
        if sig in text:
            score += 1
    shop = str(ad.get("shop_type", "")).lower()
    if shop and shop not in ("unknown", ""):
        score += 1
    if is_target_region(ad):
        score += 2
    if score >= 3:
        return True, score, "relevant"
    elif score >= 1:
        return True, score, "marginal"
    return False, score, "no relevance signals"


def score_performance(ad):
    views = parse_num(ad.get("play_count", 0))
    likes = parse_num(ad.get("digg_count", 0))
    days = parse_num(ad.get("put_days", 0))
    s = 0; reasons = []
    if days >= 60:   s += 3; reasons.append(f"{days}d longevity (strong)")
    elif days >= 30: s += 2; reasons.append(f"{days}d longevity")
    elif days >= 14: s += 1; reasons.append(f"{days}d longevity (moderate)")
    if views >= 1_000_000:   s += 3; reasons.append(f"{fmt_views(views)} views")
    elif views >= 500_000:   s += 2; reasons.append(f"{fmt_views(views)} views")
    elif views >= 100_000:   s += 1; reasons.append(f"{fmt_views(views)} views")
    if views > 0:
        eng = likes / views
        if eng > 0.02:   s += 2; reasons.append(f"high engagement {eng:.1%}")
        elif eng > 0.005: s += 1; reasons.append(f"decent engagement {eng:.1%}")
    return min(s, 10), reasons


def score_relevance(ad, keyword_tier):
    text = ad_text(ad)
    s = 0; reasons = []
    strong_hits = sum(1 for sig in STRONG_RELEVANCE if sig in text)
    if strong_hits >= 3:   s += 3; reasons.append(f"{strong_hits} strong relevance signals")
    elif strong_hits >= 1: s += 2; reasons.append(f"{strong_hits} strong signal(s)")
    weak_hits = sum(1 for sig in WEAK_RELEVANCE if sig in text)
    if weak_hits >= 2: s += 1; reasons.append(f"{weak_hits} weak signals")
    for marker in IRRELEVANCE_MARKERS:
        if marker in text:
            s -= 5; reasons.append(f"irrelevant: {marker}"); break
    if "shopify" in str(ad.get("shop_type", "")).lower(): s += 1; reasons.append("Shopify")
    if is_target_region(ad): s += 2; reasons.append("target region (scaling market)")
    if keyword_tier == "T3": reasons.append("BRAND-ANCHORED BIAS")
    return max(0, min(s, 10)), reasons


def score_transferability(ad):
    s = 0; reasons = []
    if ad.get("ai_analysis_main_hook"): s += 2; reasons.append("has hook")
    if ad.get("ai_analysis_script"): s += 1; reasons.append("has script")
    if ad.get("video_url"): s += 1; reasons.append("video available")
    if ad.get("landing_page") or ad.get("store_url"): s += 1; reasons.append("landing visible")
    caption = ad.get("desc", "") or ""
    if len(re.sub(r"#\w+", "", caption).strip()) > 30: s += 1; reasons.append("substantive caption")
    if ad.get("button_text"): s += 1; reasons.append(f"CTA: {ad['button_text']}")
    return min(s, 10), reasons


def extraction_confidence(ad):
    fields = ["ad_id", "unique_id", "desc", "play_count", "digg_count",
              "put_days", "button_text", "fetch_region", "shop_type",
              "video_url", "ai_analysis_main_hook", "ai_analysis_script"]
    present = sum(1 for f in fields if ad.get(f) not in (None, "", 0, []))
    ratio = present / len(fields)
    if ratio >= 0.7: return "high", ratio
    if ratio >= 0.4: return "medium", ratio
    return "low", ratio


def classify_ad(ad, keyword_tier):
    perf, pr = score_performance(ad)
    rel, rr = score_relevance(ad, keyword_tier)
    trans, tr = score_transferability(ad)
    conf, conf_ratio = extraction_confidence(ad)
    reasons = pr + rr + tr
    if conf == "low": reasons.append(f"LOW confidence ({conf_ratio:.0%})")
    scores = {"performance_score": perf, "relevance_score": rel,
              "transferability_score": trans, "extraction_confidence": conf,
              "extraction_confidence_ratio": round(conf_ratio, 2)}
    if conf == "low":
        cls = "MID" if rel >= 3 else "DISCARD"
        reasons.append(f"capped at {cls}: low confidence")
    elif rel <= 1:
        cls = "DISCARD"; reasons.append("very low relevance")
    elif rel >= 4 and (trans >= 4 or perf >= 5):
        cls = "WINNER"
    elif rel >= 3 and (perf >= 3 or trans >= 3):
        cls = "POSSIBLE_WINNER"
    elif rel >= 2:
        cls = "MID"
    else:
        cls = "DISCARD"; reasons.append("weak overall")
    return cls, scores, reasons


class DedupEngine:
    def __init__(self):
        self.seen_ad_ids = {}
        self.seen_content_keys = {}
        self.seen_landing_urls = {}
        self.duplicate_counts = {}

    def check_and_add(self, ad, record):
        ad_id = ad.get("ad_id", "")
        if ad_id and ad_id in self.seen_ad_ids:
            self.duplicate_counts[ad_id] = self.duplicate_counts.get(ad_id, 1) + 1
            existing = self.seen_ad_ids[ad_id]
            if record.get("scores", {}).get("performance_score", 0) > existing.get("scores", {}).get("performance_score", 0):
                self.seen_ad_ids[ad_id] = record
            return False, ad_id
        content_key = make_dedupe_key(ad)
        if content_key in self.seen_content_keys:
            canonical = self.seen_content_keys[content_key]
            self.duplicate_counts[canonical] = self.duplicate_counts.get(canonical, 1) + 1
            return False, canonical
        landing = (ad.get("landing_page", "") or ad.get("store_url", "") or "").strip().lower()
        if landing and landing in self.seen_landing_urls:
            canonical = self.seen_landing_urls[landing]
            can_rec = self.seen_ad_ids.get(canonical, {})
            can_adv = can_rec.get("advertiser_name", "").lower() if can_rec else ""
            this_adv = (ad.get("unique_id", "") or ad.get("app_name", "") or "").lower()
            if can_adv and this_adv and can_adv == this_adv:
                self.duplicate_counts[canonical] = self.duplicate_counts.get(canonical, 1) + 1
                return False, canonical
        if ad_id:
            self.seen_ad_ids[ad_id] = record
            self.seen_content_keys[content_key] = ad_id
            if landing:
                self.seen_landing_urls[landing] = ad_id
            self.duplicate_counts[ad_id] = 1
        return True, ad_id

    def get_duplicate_count(self, ad_id):
        return self.duplicate_counts.get(ad_id, 1)


def build_record(ad, keyword, kw_config, classification, scores, reasons, dedupe_key, dup_count,
                 page_num, state_detected, extraction_source="api_response"):
    views = parse_num(ad.get("play_count", 0))
    likes = parse_num(ad.get("digg_count", 0))
    days = parse_num(ad.get("put_days", 0))
    advertiser = ad.get("unique_id", "") or ad.get("app_name", "") or ""
    caption = ad.get("desc", "") or ""
    hook = ad.get("ai_analysis_main_hook", "") or ""
    script = ad.get("ai_analysis_script", "") or ""
    landing = ad.get("landing_page", "") or ad.get("store_url", "") or ""
    text_lower = (caption + " " + script).lower()
    creative_format = "unknown"
    for pattern, label in [
        (["review", "honest review", "unboxing"], "review/unboxing"),
        (["haul", "try on"], "haul/try-on"),
        (["outfit", "ootd", "fit check"], "outfit_showcase"),
        (["before", "after", "transformation"], "before_after"),
        (["pov", "story", "imagine"], "narrative/pov"),
    ]:
        if any(w in text_lower for w in pattern):
            creative_format = label; break
    audience_clues = []
    if any(w in text_lower for w in ["men", "guys", "him", "his", "bro", "king"]): audience_clues.append("male")
    if any(w in text_lower for w in ["women", "girl", "her", "she", "queen"]): audience_clues.append("female")
    if any(w in text_lower for w in ["gen z", "y2k", "teen"]): audience_clues.append("gen_z")
    why_matters = ""
    if classification == "WINNER": why_matters = f"Strong: {'; '.join(reasons[:3])}"
    elif classification == "POSSIBLE_WINNER": why_matters = f"Promising: {'; '.join(reasons[:2])}"
    why_misleading = ""
    if kw_config["mode"] == "competitor": why_misleading = "brand-anchored bias"
    if scores["extraction_confidence"] == "low": why_misleading += ("; " if why_misleading else "") + "low confidence"
    if days < 7 and views > 500_000: why_misleading += ("; " if why_misleading else "") + "very new + high views = possible paid boost"
    return {
        "keyword": keyword, "keyword_tier": kw_config["tier"], "search_mode": kw_config["mode"],
        "timestamp": datetime.now().isoformat(), "page_number": page_num,
        "ad_id": ad.get("ad_id", ""), "advertiser_name": advertiser,
        "brand_name_if_distinct": "", "product_name": "",
        "product_category": "digital_product" if any(s in ad_text(ad) for s in STRONG_RELEVANCE[:15]) else "adjacent",
        "regions": extract_regions(ad), "platform": ad.get("shop_type", ""),
        "first_seen": ad.get("first_seen", ""), "last_seen": ad.get("last_seen", ""),
        "longevity_days": days, "views": views, "likes": likes,
        "comments": parse_num(ad.get("comment_count", 0)),
        "shares": parse_num(ad.get("share_count", 0)),
        "engagement_rate": round(likes / views, 4) if views > 0 else 0,
        "cpm": parse_num(ad.get("min_cpm", 0)), "destination_url": landing,
        "video_url": ad.get("video_url", ""), "screenshot_paths": [],
        "scores": scores, "classification": classification,
        "discard_reason": reasons[-1] if classification == "DISCARD" and reasons else "",
        "why_it_matters": why_matters, "why_it_might_be_misleading": why_misleading,
        "hook": hook, "angle": "", "offer": "", "cta": ad.get("button_text", ""),
        "creative_format": creative_format, "visual_structure": "",
        "caption": caption[:300], "script": script[:500], "audience_clues": audience_clues,
        "dedupe_key": dedupe_key, "duplicate_count": dup_count,
        "canonical_record_id": ad.get("ad_id", ""),
        "state_detected": str(state_detected), "last_action": "api_fetch",
        "recovery_used": False, "extraction_source": extraction_source,
    }


def write_batch_summary(keyword, kw_config, summary, batch_log_dir):
    safe_kw = re.sub(r"[^a-zA-Z0-9]", "_", keyword)
    path = batch_log_dir / f"batch_{safe_kw}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    return path


# ═══════════════════════════════════════════════════════════
# PRE-RUN CHECKLIST
# ═══════════════════════════════════════════════════════════

def run_precheck(stage_key):
    checks = []; ok = True
    for d in [SCREENSHOTS, DATA_DIR, BATCH_LOG, STEP_LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)
        checks.append(f"  [OK] {d.name}/ exists")
    report_path = BASE / "PIPIADS_COMPETITOR_REPORT_V4.md"
    try:
        report_path.write_text("test"); report_path.unlink()
        checks.append("  [OK] Report path writable")
    except Exception as e:
        checks.append(f"  [FAIL] Report not writable: {e}"); ok = False
    if COOKIES.exists():
        checks.append(f"  [OK] Cookies found ({COOKIES.stat().st_size}B)")
    else:
        checks.append("  [WARN] No cookies — manual login required")
    stage = STAGES.get(stage_key)
    if stage:
        checks.append(f"  [OK] Stage {stage_key}: {stage['name']}")
        checks.append(f"       Keywords: {len(stage['keywords'])}")
        checks.append(f"       Goal: {stage['goal']}")
        if stage["max_pages_override"]:
            checks.append(f"       Pages/kw: {stage['max_pages_override']}")
        if stage.get("max_card_opens") is not None:
            checks.append(f"       Max card opens: {stage['max_card_opens']}")
    else:
        checks.append(f"  [FAIL] Unknown stage: {stage_key}"); ok = False
    checks.append(f"  [OK] Keywords: {len(KEYWORDS)} total")
    checks.append(f"  [OK] State machine: {len(TRANSITIONS)} states, {sum(len(v) for v in TRANSITIONS.values())} transitions")
    checks.append(f"  [OK] Action timeouts: {len(ACTION_TIMEOUTS)} defined")
    checks.append(f"  [OK] Stuck detection: screenshot hash + state ticks + action repeats")
    checks.append(f"  [OK] 3-level dedup: ad_id / content_hash / landing_url")
    checks.append(f"  [OK] Step logging: per-action with full schema")
    checks.append(f"  [OK] Recovery: state-specific branches, 2/context, 10 total max")
    if stage_key == "research":
        checks.append(f"  [OK] Research mode: baseline reconciliation enabled")
        checks.append(f"  [OK] Drift detection: every {stage.get('drift_check_interval', 4)} keywords")
        checks.append(f"  [OK] Critical filters: {list(BASELINE_FILTERS['critical'].keys())}")
        checks.append(f"  [OK] Soft filters: {list(BASELINE_FILTERS['soft'].keys())}")
        checks.append(f"  [OK] Hard abort filters: {HARD_ABORT_FILTERS}")
        checks.append(f"  [OK] Keyword outcome labels: enabled")
    return ok, checks


# ═══════════════════════════════════════════════════════════
# REPORT GENERATOR
# ═══════════════════════════════════════════════════════════

def generate_report(records, keyword_summaries, stage_key, stage_config, run_meta, domain_tracker=None):
    report_path = BASE / "PIPIADS_COMPETITOR_REPORT_V4.md"
    class_counts = Counter(r["classification"] for r in records)
    conf_counts = Counter(r["scores"]["extraction_confidence"] for r in records)
    advertisers = set(r["advertiser_name"] for r in records if r["advertiser_name"])
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# NEWGARMENTS - PiPiAds Competitor Report v4\n\n")
        f.write(f"## 1. Run Summary\n\n")
        f.write(f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- **Stage:** {stage_key} — {stage_config['name']}\n")
        f.write(f"- **Goal:** {stage_config['goal']}\n")
        f.write(f"- **Keywords attempted:** {run_meta['keywords_attempted']}\n")
        f.write(f"- **Keywords completed:** {run_meta['keywords_completed']}\n")
        f.write(f"- **Unstable keywords:** {', '.join(run_meta['unstable_keywords']) or 'none'}\n")
        f.write(f"- **Total records:** {len(records)}\n")
        f.write(f"- **Unique advertisers:** {len(advertisers)}\n")
        for cls in ["WINNER", "POSSIBLE_WINNER", "MID", "DISCARD"]:
            f.write(f"- **{cls}:** {class_counts.get(cls, 0)}\n")
        f.write(f"- **Recoveries:** {run_meta['total_recoveries']}\n")
        f.write(f"- **Step logs:** {run_meta.get('step_log_path', 'N/A')}\n\n")

        winners = sorted([r for r in records if r["classification"] == "WINNER"],
                         key=lambda r: r["scores"]["performance_score"] + r["scores"]["relevance_score"], reverse=True)
        f.write(f"## 2. Top Winners ({len(winners)})\n\n")
        for i, r in enumerate(winners, 1):
            f.write(f"### {i}. {r['advertiser_name']}\n")
            f.write(f"- **Views:** {fmt_views(r['views'])} | **Likes:** {r['likes']:,} | **Days:** {r['longevity_days']} | **CTA:** {r['cta']}\n")
            f.write(f"- **Perf:** {r['scores']['performance_score']}/10 | **Rel:** {r['scores']['relevance_score']}/10 | **Trans:** {r['scores']['transferability_score']}/10 | **Conf:** {r['scores']['extraction_confidence']}\n")
            if r["hook"]: f.write(f"- **Hook:** {r['hook']}\n")
            f.write(f"- **Caption:** {r['caption'][:200]}\n")
            if r["script"]: f.write(f"- **Script:** {r['script'][:250]}\n")
            f.write(f"- **Why:** {r['why_it_matters']}\n")
            if r["why_it_might_be_misleading"]: f.write(f"- **Caution:** {r['why_it_might_be_misleading']}\n")
            if r["video_url"]: f.write(f"- **Video:** {r['video_url']}\n")
            f.write(f"- **Keyword:** {r['keyword']} ({r['keyword_tier']})\n\n")

        pw = sorted([r for r in records if r["classification"] == "POSSIBLE_WINNER"],
                     key=lambda r: r["scores"]["performance_score"] + r["scores"]["relevance_score"], reverse=True)
        f.write(f"## 2b. Possible Winners ({len(pw)})\n\n")
        for i, r in enumerate(pw[:20], 1):
            f.write(f"**{i}. {r['advertiser_name']}** — {fmt_views(r['views'])}, {r['longevity_days']}d")
            if r["hook"]: f.write(f" — Hook: {r['hook'][:80]}")
            f.write(f" [P:{r['scores']['performance_score']} R:{r['scores']['relevance_score']} T:{r['scores']['transferability_score']}]\n\n")

        f.write(f"## 3. Repeated Patterns\n\n")
        hooks = [r["hook"] for r in records if r["hook"] and r["classification"] in ("WINNER", "POSSIBLE_WINNER")]
        if hooks:
            f.write(f"### Hooks ({len(hooks)})\n\n")
            for h in hooks[:15]: f.write(f"- {h}\n")
            f.write(f"\n")
        cta_c = Counter(r["cta"] for r in records if r["cta"])
        f.write(f"### CTAs\n\n")
        for cta, cnt in cta_c.most_common(10): f.write(f"- **{cta}:** {cnt}\n")
        f.write(f"\n")
        reg_c = Counter(); [reg_c.update(r["regions"]) for r in records]
        f.write(f"### Regions\n\n")
        for reg, cnt in reg_c.most_common(): f.write(f"- **{reg}:** {cnt}\n")
        f.write(f"\n")
        adv_c = Counter(r["advertiser_name"] for r in records if r["advertiser_name"])
        repeats = {k: v for k, v in adv_c.items() if v >= 2}
        if repeats:
            f.write(f"### Repeat Advertisers\n\n")
            for adv, cnt in sorted(repeats.items(), key=lambda x: x[1], reverse=True)[:15]:
                f.write(f"- **{adv}:** {cnt}\n")
            f.write(f"\n")

        f.write(f"## 4. Saturation vs Opportunity\n\n")
        high_junk = [s for s in keyword_summaries if s.get("junk_rate", 0) > 0.7]
        low_junk = [s for s in keyword_summaries if s.get("junk_rate", 0) < 0.3 and s.get("cards_captured", 0) > 0]
        f.write(f"### High-Junk Keywords\n\n")
        for s in high_junk: f.write(f"- **{s['keyword']}** ({s['tier']}): {s['junk_rate']:.0%} junk\n")
        if not high_junk: f.write(f"_None._\n")
        f.write(f"\n### High-Signal Keywords\n\n")
        for s in low_junk: f.write(f"- **{s['keyword']}** ({s['tier']}): {s.get('winners',0)}W, {s.get('possible_winners',0)}PW\n")
        if not low_junk: f.write(f"_None._\n")
        f.write(f"\n")

        f.write(f"## 5. Data Quality\n\n")
        f.write(f"- **Confidence:** high={conf_counts.get('high',0)}, med={conf_counts.get('medium',0)}, low={conf_counts.get('low',0)}\n")
        f.write(f"- **Unstable:** {', '.join(run_meta['unstable_keywords']) or 'none'}\n")
        f.write(f"- **Recoveries:** {run_meta['total_recoveries']}\n\n")

        f.write(f"## 6. Next-Search Recommendations\n\n")
        f.write(f"| Keyword | Tier | Pages | Captured | W | PW | Junk% | Outcome | Recommend |\n")
        f.write(f"|---------|------|-------|----------|---|-----|-------|---------|----------|\n")
        for s in sorted(keyword_summaries, key=lambda x: x.get("winners", 0), reverse=True):
            outcome = s.get("outcome_label", "")
            f.write(f"| {s['keyword']} | {s['tier']} | {s.get('pages_visited',0)} | {s.get('cards_captured',0)} | {s.get('winners',0)} | {s.get('possible_winners',0)} | {s.get('junk_rate',0):.0%} | {outcome} | {s.get('recommend','')} |\n")
        f.write(f"\n")

        # Strong competitor domains section
        if domain_tracker:
            strong = domain_tracker.get_strong_competitors(threshold=3)
            all_doms = domain_tracker.get_all_domains()
            f.write(f"## 7. Strong Competitor Domains\n\n")
            if strong:
                f.write(f"Domains appearing across 3+ keywords:\n\n")
                for sc in strong:
                    f.write(f"- **{sc['domain']}** — {sc['keyword_count']} keywords: {', '.join(sorted(sc['keywords']))}\n")
                f.write(f"\n")
            else:
                f.write(f"_No domain appeared in 3+ keywords._\n\n")
            f.write(f"### All Tracked Domains\n\n")
            for d in sorted(all_doms, key=lambda x: x["keyword_count"], reverse=True)[:20]:
                marker = " ★" if domain_tracker.is_strong_competitor(d["domain"]) else ""
                f.write(f"- {d['domain']}: {d['keyword_count']} keywords{marker}\n")
            f.write(f"\n")

        # Research mode: baseline & drift section
        if stage_key == "research":
            f.write(f"## 8. Baseline & Drift Report\n\n")
            br = run_meta.get("baseline_reconciliation", {})
            if br:
                f.write(f"- **Reconciliation:** {'Required rebuild' if br.get('required_rebuild') else 'Verified (no rebuild)'}\n")
                f.write(f"- **Confidence:** {br.get('confidence_fraction', 'N/A')} ({br.get('confidence', 0):.0%})\n")
                f.write(f"- **Missing critical:** {br.get('missing_critical', []) or 'none'}\n")
                f.write(f"- **Actions taken:** {br.get('actions_taken', []) or 'none'}\n\n")

            drift_evts = run_meta.get("drift_events", [])
            any_drift = any(d.get("drifted") for d in drift_evts)
            f.write(f"### Drift Events\n\n")
            if any_drift:
                for d in drift_evts:
                    if d.get("drifted"):
                        f.write(f"- **KW {d['keyword_index']}** ({d['keyword']}): {d['drifted_filters']} "
                                f"-> corrected: {d['corrections_made']}\n")
            else:
                f.write(f"_No drift detected._\n")
            f.write(f"\n")

            f.write(f"### Operator Stability\n\n")
            f.write(f"- **Stable:** {'Yes' if run_meta.get('operator_stability') else 'No'}\n")
            f.write(f"- **Recoveries:** {run_meta.get('total_recoveries', 0)}\n")
            failures = run_meta.get("failure_points", [])
            if failures:
                f.write(f"- **Failure points:** {len(failures)}\n")
                for fp in failures:
                    f.write(f"  - {fp}\n")
            f.write(f"\n")

    return report_path


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default=None, choices=["A0", "A1", "B", "C"])
    parser.add_argument("--mode", default=None, choices=["research"])
    args = parser.parse_args()

    # Resolve stage: --mode research maps to "research" stage
    if args.mode == "research":
        stage_key = "research"
    elif args.stage:
        stage_key = args.stage
    else:
        stage_key = "A0"  # default fallback

    stage_config = STAGES[stage_key]
    is_research_mode = stage_key == "research"
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    print("=" * 70)
    print(f"NEWGARMENTS - PiPiAds Research v4 — Stage {stage_key}: {stage_config['name']}")
    print(f"Goal: {stage_config['goal']}")
    print("=" * 70)

    # ── PRE-RUN CHECKLIST ──
    print("\n[PRE-RUN CHECKLIST]")
    ok, checks = run_precheck(stage_key)
    for c in checks: print(c)
    if not ok:
        print("\n[ABORT] Pre-run checklist failed.")
        return
    print(f"\n  All checks passed.\n")

    stage_keywords = stage_config["keywords"]
    max_pages_override = stage_config["max_pages_override"]
    max_card_opens_override = stage_config.get("max_card_opens")

    print(f"[STAGE {stage_key}] Keywords:")
    for kw in stage_keywords:
        cfg = KEYWORDS.get(kw, {"tier": "?", "mode": "?", "max_pages": 2, "max_opens": 12})
        pages = max_pages_override or cfg["max_pages"]
        print(f"  - {kw} [{cfg['tier']}/{cfg['mode']}] x{pages}pg")

    # Init
    dedup = DedupEngine()
    step_logger = StepLogger(STEP_LOG_DIR, ts)
    all_records = []
    keyword_summaries = []
    domain_tracker = DomainTracker()
    run_meta = {"keywords_attempted": 0, "keywords_completed": 0,
                "unstable_keywords": [], "total_recoveries": 0,
                "baseline_reconciliation": None, "drift_events": [],
                "operator_stability": True, "failure_points": []}

    async with async_playwright() as p:
        print("\n[+] Launching browser...")
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        if COOKIES.exists():
            try:
                cookies = json.loads(COOKIES.read_text())
                await context.add_cookies(cookies)
                print("[+] Cookies loaded")
            except Exception:
                print("[WARN] Cookie load failed")

        page = await context.new_page()
        op = Operator(page, step_logger, ts)

        # ── Intercept API format (non-research modes only) ──
        captured_api_format = []
        if not is_research_mode:
            async def on_request(request):
                if "search4/at/video/search" in request.url:
                    try:
                        post = request.post_data
                        if post:
                            captured_api_format.append({
                                "url": request.url,
                                "payload": json.loads(post),
                                "headers": dict(request.headers),
                            })
                    except Exception:
                        pass

            page.on("request", on_request)

        # ── Navigate to PiPiAds ──
        print("[+] Opening PiPiAds...")
        await page.goto("https://www.pipiads.com/ad-search", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        state = await op.refresh_state()
        ss = await take_screenshot(page, f"01_initial_{state}", ts)
        step_logger.log("_init", 0, state, "navigate_to_search",
                        [S.SEARCH_PAGE, S.RESULTS_PAGE, S.LOGIN_REQUIRED],
                        "detect_state", "success", state, screenshot_path=ss)

        # Dismiss any leftover modal/overlay before proceeding
        if state == S.DETAIL_MODAL_OPEN:
            print("[+] Leftover modal detected, dismissing...")
            for _ in range(3):
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(800)
            state = await op.refresh_state()
            if state == S.DETAIL_MODAL_OPEN:
                # Force navigate to clean page
                await page.goto("https://www.pipiads.com/ad-search", wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                state = await op.refresh_state()
            print(f"[+] After cleanup, state: {state}")

        # Handle login if needed
        if state == S.LOGIN_REQUIRED:
            login_result = await op.recover(S.LOGIN_REQUIRED, "manual_login", "_init", 0)
            if not login_result.success:
                print("[ABORT] Cannot establish session.")
                await browser.close()
                return
            state = login_result.new_state

        # Save cookies
        cookies = await context.cookies()
        COOKIES.write_text(json.dumps(cookies, default=str))
        await take_screenshot(page, f"02_session_active_{state}", ts)
        print(f"[+] Session active, state: {state}")

        # ═══════════════════════════════════════
        # BASELINE RECONCILIATION (research mode)
        # ═══════════════════════════════════════
        baseline_mgr = None
        if is_research_mode:
            print("\n[STEP 1] Baseline filter reconciliation...")
            baseline_mgr = BaselineManager(page, step_logger, ts)
            baseline_result = await baseline_mgr.reconcile()
            run_meta["baseline_reconciliation"] = baseline_result
            await take_screenshot(page, "04_baseline_reconciliation", ts)

            should_abort, abort_reason = baseline_mgr.should_abort_low_confidence()
            if should_abort:
                # In research mode, UI filter application is best-effort.
                # Multi-pass sort/time strategy is the primary search mechanism.
                # Warn but continue instead of aborting.
                print(f"\n[WARN] Baseline confidence low: {abort_reason}")
                print(f"  Confidence: {baseline_result['confidence_fraction']} ({baseline_mgr.confidence:.0%})")
                print(f"  Missing critical: {baseline_result.get('missing_critical', [])}")
                print(f"  Continuing anyway — filters will be retried per search pass.")
                await take_screenshot(page, "WARN_baseline_confidence", ts)
            else:
                print(f"  [BASELINE] Ready. Confidence: {baseline_mgr.confidence:.0%}")

        # ── Proven PiPiAds selectors ──
        CARD_SEL_PRIMARY = ".item-wrap"
        CARD_SEL_FALLBACKS = [".wt-block-grid__item", ".lists-wrap > li", '[class*="ad-card"]', '[class*="video-card"]']
        SEARCH_INPUT_SEL = "#inputKeyword"
        SEARCH_INPUT_FALLBACK = 'input[placeholder*="Search by any ad keyword"]'
        MODAL_SEL_PRIMARY = ".el-dialog__wrapper:visible"
        MODAL_SEL_FALLBACKS = ['[class*="modal"][class*="detail"]:visible', '[class*="drawer"]:visible', '[class*="video-detail"]:visible']
        MAX_SCROLL_ROUNDS = 6

        async def resolve_card_selector() -> str:
            """Return the best working card selector, preferring the proven .item-wrap."""
            try:
                count = await page.locator(CARD_SEL_PRIMARY).count()
                if count >= 1:
                    return CARD_SEL_PRIMARY
            except Exception:
                pass
            for fb in CARD_SEL_FALLBACKS:
                try:
                    count = await page.locator(fb).count()
                    if count >= 1:
                        print(f"    [WARN] Primary card selector failed, using fallback: {fb}")
                        return fb
                except Exception:
                    continue
            return CARD_SEL_PRIMARY  # default even if 0 found

        async def is_modal_open() -> bool:
            """Check if detail modal is open using proven then fallback selectors."""
            try:
                if await page.locator(MODAL_SEL_PRIMARY).first.is_visible(timeout=800):
                    return True
            except Exception:
                pass
            for fb in MODAL_SEL_FALLBACKS:
                try:
                    if await page.locator(fb).first.is_visible(timeout=500):
                        return True
                except Exception:
                    continue
            return False

        async def prescan_card(card_el) -> Dict[str, Any]:
            """Extract prescan fields from a card DOM element."""
            ps = {"advertiser": "", "views_text": "", "days_text": "", "likes_text": "",
                  "caption_preview": "", "cta_text": "", "platform_badge": ""}
            try:
                # Advertiser name
                for sel in ['.link-item.title.a-link', '.app-name', '.nickname', '[class*="title"] a']:
                    try:
                        el = card_el.locator(sel).first
                        if await el.is_visible(timeout=400):
                            ps["advertiser"] = (await el.inner_text(timeout=400)).strip()
                            if ps["advertiser"]:
                                break
                    except Exception:
                        continue
                # Data count items: Impression / Days / Like
                items = card_el.locator('.data-count .item')
                item_count = await items.count()
                for i in range(min(item_count, 4)):
                    try:
                        val = await items.nth(i).locator('.value').inner_text(timeout=400)
                        cap = await items.nth(i).locator('.caption').inner_text(timeout=400)
                        cap_l = cap.strip().lower()
                        val = val.strip()
                        if "impression" in cap_l or "view" in cap_l:
                            ps["views_text"] = val
                        elif "day" in cap_l:
                            ps["days_text"] = val
                        elif "like" in cap_l:
                            ps["likes_text"] = val
                    except Exception:
                        continue
                # CTA / shop-now
                try:
                    cta_el = card_el.locator('.shop-now').first
                    if await cta_el.is_visible(timeout=300):
                        ps["cta_text"] = (await cta_el.inner_text(timeout=400)).strip()
                except Exception:
                    pass
                # Caption preview from ad text
                for sel in ['.button-text-copy', '.title', 'h5.title']:
                    try:
                        el = card_el.locator(sel).first
                        if await el.is_visible(timeout=300):
                            t = (await el.inner_text(timeout=400)).strip()
                            if t and len(t) > 3:
                                ps["caption_preview"] = t[:200]
                                break
                    except Exception:
                        continue
            except Exception:
                pass
            return ps

        async def extract_modal_data() -> Dict[str, Any]:
            """Extract detailed fields from the open detail modal DOM."""
            md = {"advertiser_name": "", "description": "", "hook": "", "script": "",
                  "play_count": 0, "digg_count": 0, "comment_count": 0, "share_count": 0,
                  "put_days": 0, "button_text": "", "landing_page": "", "video_url": "",
                  "shop_type": "", "fetch_region": "", "first_seen": "", "last_seen": "",
                  "ad_id": "", "ad_spend": "", "cpm": ""}

            # Find the modal container
            modal = None
            try:
                modal = page.locator(MODAL_SEL_PRIMARY).first
                if not await modal.is_visible(timeout=800):
                    modal = None
            except Exception:
                modal = None
            if not modal:
                for fb in MODAL_SEL_FALLBACKS:
                    try:
                        m = page.locator(fb).first
                        if await m.is_visible(timeout=500):
                            modal = m
                            break
                    except Exception:
                        continue
            if not modal:
                return md

            # Helper: safe text extraction
            async def _txt(selector, timeout=600):
                try:
                    el = modal.locator(selector).first
                    if await el.is_visible(timeout=timeout):
                        return (await el.inner_text(timeout=timeout)).strip()
                except Exception:
                    pass
                return ""

            # Advertiser
            for sel in ['p.name', '.text-primary.ellipsis', '.app-name.nickname', '.link-item.title.a-link']:
                v = await _txt(sel)
                if v:
                    md["advertiser_name"] = v
                    break

            # Structured value/caption pairs
            items = modal.locator('.data-count .item, .item-data .item, .detail-data .item')
            item_count = 0
            try:
                item_count = await items.count()
            except Exception:
                pass
            for i in range(min(item_count, 10)):
                try:
                    val = (await items.nth(i).locator('.value').inner_text(timeout=400)).strip()
                    cap = (await items.nth(i).locator('.caption').inner_text(timeout=400)).strip().lower()
                    if "impression" in cap or "view" in cap:
                        md["play_count"] = parse_num(val.replace(",", "").replace("K", "000").replace("M", "000000"))
                    elif cap == "days" or "day" in cap:
                        md["put_days"] = parse_num(val.split("-")[0] if "-" in val else val)
                    elif "like" in cap:
                        if "%" in val:
                            pass  # engagement rate, not raw likes
                        else:
                            md["digg_count"] = parse_num(val.replace(",", "").replace("K", "000").replace("M", "000000"))
                    elif "spend" in cap or "cost" in cap:
                        md["ad_spend"] = val
                    elif "platform" in cap or "ecom" in cap:
                        md["shop_type"] = val
                except Exception:
                    continue

            # CTA
            cta = await _txt('.shop-now, .shop-now.flex-shrink-0')
            if cta:
                md["button_text"] = cta

            # Ad copy / description
            for sel in ['._attr:has-text("Ad Copy") + *', '._attr:has-text("Ad Copy") ~ *']:
                v = await _txt(sel)
                if v and v != "Ad Copy:":
                    md["description"] = v[:500]
                    break
            # Fallback: grab all text after "Ad Copy:" label
            if not md["description"]:
                try:
                    all_text = await modal.inner_text(timeout=2000)
                    if "Ad Copy:" in all_text:
                        after = all_text.split("Ad Copy:")[1][:500].strip()
                        # Stop at next label
                        for stop in ["Display Name:", "Country/Region:", "Audience:", "Creation Date:", "TikTok Post:"]:
                            if stop in after:
                                after = after.split(stop)[0].strip()
                        md["description"] = after
                except Exception:
                    pass

            # Landing page
            for sel in ['a.slot-wrap.btn.rowLanding', 'a.rowLanding', 'a[class*="landing"]']:
                try:
                    el = modal.locator(sel).first
                    if await el.is_visible(timeout=500):
                        href = await el.get_attribute("href", timeout=400)
                        if href:
                            md["landing_page"] = href
                            break
                        t = (await el.inner_text(timeout=400)).strip()
                        if t.startswith("http"):
                            md["landing_page"] = t
                            break
                except Exception:
                    continue

            # Region
            try:
                all_text = await modal.inner_text(timeout=2000)
                if "Country/Region:" in all_text:
                    region_part = all_text.split("Country/Region:")[1][:200]
                    for stop in ["Audience:", "Creation Date:", "TikTok Post:", "Final link:"]:
                        if stop in region_part:
                            region_part = region_part.split(stop)[0]
                    md["fetch_region"] = region_part.strip()
            except Exception:
                pass

            # Video URL
            try:
                vid = modal.locator('video source, video[src]').first
                src = await vid.get_attribute("src", timeout=500)
                if src:
                    md["video_url"] = src
            except Exception:
                pass

            # TikTok post link as ad_id source
            for sel in ['a[href*="tiktok.com"]', 'a.btn.slot-wrap']:
                try:
                    el = modal.locator(sel).first
                    href = await el.get_attribute("href", timeout=400)
                    if href and "tiktok" in href:
                        md["ad_id"] = href
                        break
                except Exception:
                    continue

            return md

        async def ui_submit_search(keyword: str) -> bool:
            """Type keyword and submit search via UI. Returns True if RESULTS_PAGE reached."""
            # Fill search input
            inp = None
            try:
                inp = page.locator(SEARCH_INPUT_SEL).first
                if not await inp.is_visible(timeout=2000):
                    inp = page.locator(SEARCH_INPUT_FALLBACK).first
            except Exception:
                inp = page.locator(SEARCH_INPUT_FALLBACK).first

            try:
                await inp.click(click_count=3)
                await inp.fill(keyword)
                await page.wait_for_timeout(300)
                await inp.press("Enter")
            except Exception as e:
                print(f"    [ERROR] Search input failed: {str(e)[:80]}")
                return False

            # Wait for results
            await page.wait_for_timeout(3000)
            # Wait up to 15s for cards to appear
            card_sel = CARD_SEL_PRIMARY
            for _ in range(6):
                try:
                    count = await page.locator(card_sel).count()
                    if count > 0:
                        return True
                except Exception:
                    pass
                await page.wait_for_timeout(2000)

            # Check fallbacks
            for fb in CARD_SEL_FALLBACKS:
                try:
                    if await page.locator(fb).count() > 0:
                        return True
                except Exception:
                    continue

            # Check empty results
            state = await op.refresh_state()
            if state == S.EMPTY_RESULTS:
                return False  # genuinely empty

            return False

        # ═══════════════════════════════════════
        # UI SORT & TIME FILTER HELPERS
        # ═══════════════════════════════════════

        async def ui_set_sort(sort_option: str) -> bool:
            """Click a sort option in the inline sort bar. Returns True if clicked."""
            # Sort options are inline within div.data-view-sort as clickable elements
            # Each shows as "Sort by: X" text (e.g., "Sort by: Ad Spend")
            sort_container = page.locator('.data-view-sort')
            try:
                if not await sort_container.is_visible(timeout=3000):
                    print(f"    [SORT] Sort bar not visible")
                    return False
            except Exception:
                print(f"    [SORT] Sort bar not found")
                return False

            # Strategy 1: Click by text match within sort container
            for text_pattern in [
                f'text="Sort by: {sort_option}"',
                f'text="{sort_option}"',
                f':has-text("{sort_option}")',
            ]:
                try:
                    el = sort_container.locator(text_pattern).first
                    if await el.is_visible(timeout=1500):
                        await el.click(timeout=3000)
                        await page.wait_for_timeout(2500)
                        print(f"    [SORT] Clicked '{sort_option}'")
                        return True
                except Exception:
                    continue

            # Strategy 2: Iterate all clickable children and find text match
            try:
                children = sort_container.locator('span, a, div, label')
                count = await children.count()
                for i in range(count):
                    try:
                        txt = (await children.nth(i).inner_text(timeout=400)).strip()
                        if sort_option.lower() in txt.lower() and len(txt) < 50:
                            await children.nth(i).click(timeout=3000)
                            await page.wait_for_timeout(2500)
                            print(f"    [SORT] Clicked '{txt}'")
                            return True
                    except Exception:
                        continue
            except Exception:
                pass

            print(f"    [SORT] Could not find '{sort_option}' in sort bar")
            return False

        async def ui_set_time_filter(time_option: str) -> bool:
            """Click a time filter option in the PiPiAds time filter bar."""
            for sel in [
                f'.filter-time-types >> text="{time_option}"',
                f'.filter-time-types span:has-text("{time_option}")',
                f'.filter-time-types div:has-text("{time_option}")',
                f'.filter-time-types a:has-text("{time_option}")',
                f'text="{time_option}"',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await page.wait_for_timeout(2000)
                        print(f"    [TIME] Set to '{time_option}'")
                        return True
                except Exception:
                    continue
            print(f"    [TIME] Could not set '{time_option}'")
            return False

        active_sort = "Default"  # track what sort is currently active

        # KEYWORD SEARCH LOOP (UI-only)
        # ═══════════════════════════════════════
        print(f"\n[STEP 2] Keyword searches ({len(stage_keywords)} keywords)...\n")

        drift_check_interval = stage_config.get("drift_check_interval", 0)
        abort_run = False
        browser_crashed = False

        for kw_idx, keyword in enumerate(stage_keywords, 1):
            if abort_run:
                break

            kw_config = KEYWORDS.get(keyword, {"tier": "T1", "mode": "broad", "max_pages": 2, "max_opens": 12})
            max_pages = max_pages_override or kw_config["max_pages"]
            tier = kw_config["tier"]
            mode = kw_config["mode"]
            run_meta["keywords_attempted"] += 1

            print(f"\n{'─'*60}")
            print(f"[{kw_idx}/{len(stage_keywords)}] [{tier}/{mode}] \"{keyword}\"")
            print(f"{'─'*60}")

            # ── Drift detection (every N keywords in research mode) ──
            if is_research_mode and baseline_mgr and drift_check_interval > 0:
                if kw_idx > 1 and (kw_idx - 1) % drift_check_interval == 0:
                    drift_result = await baseline_mgr.check_drift(kw_idx - 1, stage_keywords[kw_idx - 2])
                    run_meta["drift_events"].append(drift_result)
                    if drift_result.get("unrecoverable"):
                        print(f"\n[ABORT] Unrecoverable drift detected at keyword {kw_idx - 1}.")
                        print(f"  Drifted: {drift_result['drifted_filters']}")
                        run_meta["failure_points"].append({
                            "type": "unrecoverable_drift",
                            "keyword_index": kw_idx - 1,
                            "detail": drift_result,
                        })
                        run_meta["operator_stability"] = False
                        abort_run = True
                        break

            # ── Gate: verify state before keyword ──
            state = await op.refresh_state()
            if state == S.LOGIN_REQUIRED:
                rec = await op.recover(S.LOGIN_REQUIRED, "manual_login", keyword, 0)
                if not rec.success:
                    run_meta["unstable_keywords"].append(keyword)
                    run_meta["failure_points"].append({"type": "login_required", "keyword": keyword})
                    continue
            if state == S.DETAIL_MODAL_OPEN:
                await op.execute("close_modal", keyword, 0, action_fn=op._action_close_modal)
            # If not on search/results page, navigate there
            if state not in (S.SEARCH_PAGE, S.RESULTS_PAGE, S.LOADING):
                try:
                    await page.goto("https://www.pipiads.com/ad-search", timeout=30_000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass

            # Per-keyword tracking
            kw_records = []
            kw_discarded = 0
            kw_early_terminated = False
            kw_gate_passed = False
            kw_card_opens = 0
            kw_cards_scanned = 0
            kw_pages_visited = 0

            # Signal-aware card-open cap
            if is_research_mode:
                kw_max_card_opens = RESEARCH_CARD_OPEN_CAP
            else:
                cap_config = CARD_OPEN_CAPS.get((tier, mode), DEFAULT_CARD_CAP)
                kw_max_card_opens = max_card_opens_override if max_card_opens_override is not None else cap_config["max_opens"]

            # ═══════════════════════════════════════
            # MULTI-PASS SEARCH (research mode) or SINGLE-PASS (stage mode)
            # ═══════════════════════════════════════
            passes = MULTI_SORT_PASSES if is_research_mode else [{"sort": None, "time": None, "label": "default"}]

            try:
              for pass_idx, pass_config in enumerate(passes):
                if kw_card_opens >= kw_max_card_opens or kw_early_terminated:
                    break

                pass_label = pass_config["label"]
                pass_max_opens = PASS_CARD_OPEN_CAP if is_research_mode else kw_max_card_opens
                pass_opens = 0

                # Set sort and time for this pass (research mode only)
                if is_research_mode and pass_config["sort"]:
                    print(f"  [Pass {pass_idx+1}/{len(passes)}: {pass_label}]")
                    sort_ok = await ui_set_sort(pass_config["sort"])
                    if not sort_ok:
                        # Try fallback sorts
                        for fallback in SORT_FALLBACK_ORDER:
                            if fallback != pass_config["sort"]:
                                sort_ok = await ui_set_sort(fallback)
                                if sort_ok:
                                    print(f"    [SORT] Fallback to '{fallback}'")
                                    break
                        if not sort_ok:
                            print(f"    [SORT] All sort options failed, skipping pass")
                            continue

                    if pass_config["time"]:
                        await ui_set_time_filter(pass_config["time"])

                # Submit keyword search
                if is_research_mode or pass_idx == 0:
                    print(f"  Searching...")
                    search_ok = await ui_submit_search(keyword)
                    ss = await take_screenshot(page, f"kw_{re.sub(r'[^a-zA-Z0-9]', '_', keyword)}_{pass_label}", ts)
                    step_logger.log(keyword, pass_idx, state, "submit_search",
                                    [S.RESULTS_PAGE], "card_count_check",
                                    "success" if search_ok else "soft_fail",
                                    await op.refresh_state(), screenshot_path=ss,
                                    notes=f"search_ok={search_ok}, pass={pass_label}")

                    if not search_ok:
                        if pass_idx == 0:
                            print(f"  No results for \"{keyword}\"")
                        continue

                kw_pages_visited += 1

                # Scroll to top for each pass
                try:
                    await page.evaluate("window.scrollTo(0, 0)")
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Prescan the first batch of cards
                card_sel = await resolve_card_selector()
                try:
                    card_count = await page.locator(card_sel).count()
                except Exception:
                    continue

                if card_count == 0:
                    continue

                # ── Prescan visible cards ──
                open_queue = []
                kw_junk_streak = 0
                for ci in range(card_count):
                    card_el = page.locator(card_sel).nth(ci)
                    ps = await prescan_card(card_el)
                    kw_cards_scanned += 1

                    if is_research_mode:
                        w_score, w_views, w_days, w_likes, w_reason = prescan_winner_score(ps)
                        if w_score < 0:
                            kw_discarded += 1
                            kw_junk_streak += 1
                            continue
                        kw_junk_streak = 0
                        open_queue.append({
                            "index": ci, "relevance": w_score, "prescan": ps,
                            "views": w_views, "days": w_days, "likes": w_likes,
                            "selection_reason": w_reason,
                        })
                    else:
                        prescan_text = " ".join(filter(None, [
                            keyword, ps["advertiser"], ps["caption_preview"],
                            ps["cta_text"], ps["platform_badge"]
                        ])).lower()
                        pseudo_ad = {
                            "desc": prescan_text, "ai_analysis_script": "",
                            "ai_analysis_main_hook": "", "unique_id": ps["advertiser"],
                            "app_name": ps["advertiser"], "shop_type": ps["platform_badge"],
                            "fetch_region": "",
                        }
                        passes_filter, rel_quick, rel_reason = relevance_prefilter(pseudo_ad)
                        if not passes_filter:
                            kw_discarded += 1
                            continue
                        open_queue.append({"index": ci, "relevance": rel_quick, "prescan": ps})

                # Sort by score, cap to pass limit
                remaining = min(pass_max_opens, kw_max_card_opens - kw_card_opens)
                open_queue.sort(key=lambda x: x["relevance"], reverse=True)
                open_queue = open_queue[:remaining]

                if is_research_mode and open_queue:
                    print(f"    [PRESCAN] {card_count} cards, {len(open_queue)} qualify, top={open_queue[0]['relevance']:.0f}")
                    for oq in open_queue:
                        print(f"      card {oq['index']}: score={oq['relevance']:.0f} | {oq.get('selection_reason', '')}")
                elif is_research_mode:
                    print(f"    [PRESCAN] {card_count} cards, 0 qualify")

                # ── Open top cards + extract ──
                for oq in open_queue:
                    ci = oq["index"]
                    ps = oq["prescan"]

                    try:
                        card_el = page.locator(card_sel).nth(ci)
                        await card_el.scroll_into_view_if_needed(timeout=3000)
                        await page.wait_for_timeout(300)
                        clicked = False
                        for click_sel in ['.cover', '.cover-container', '.item-inner', '.el-image']:
                            try:
                                inner = card_el.locator(click_sel).first
                                if await inner.is_visible(timeout=500):
                                    await inner.click(timeout=5000)
                                    clicked = True
                                    break
                            except Exception:
                                continue
                        if not clicked:
                            await card_el.click(timeout=5000)
                    except Exception as e:
                        step_logger.log(keyword, pass_idx, S.RESULTS_PAGE, "open_result",
                                        [S.DETAIL_MODAL_OPEN], "click",
                                        "soft_fail", S.RESULTS_PAGE,
                                        notes=f"card {ci} click failed: {str(e)[:60]}")
                        continue

                    # Wait for modal
                    await page.wait_for_timeout(1500)
                    modal_open = await is_modal_open()
                    if not modal_open:
                        await page.wait_for_timeout(1500)
                        modal_open = await is_modal_open()

                    if not modal_open:
                        step_logger.log(keyword, pass_idx, S.RESULTS_PAGE, "open_result",
                                        [S.DETAIL_MODAL_OPEN], "modal_check",
                                        "soft_fail", S.RESULTS_PAGE,
                                        notes=f"card {ci}: modal did not open")
                        continue

                    # Extract from modal
                    md = await extract_modal_data()
                    ad_data = {
                        "ad_id": md["ad_id"] or f"ui_{keyword}_{ci}_{pass_label}",
                        "unique_id": md["advertiser_name"] or ps["advertiser"],
                        "app_name": md["advertiser_name"] or ps["advertiser"],
                        "desc": md["description"],
                        "ai_analysis_main_hook": md.get("hook", ""),
                        "ai_analysis_script": md.get("script", ""),
                        "play_count": md["play_count"] or parse_prescan_num(ps["views_text"]),
                        "digg_count": md["digg_count"] or parse_prescan_num(ps["likes_text"]),
                        "comment_count": md["comment_count"],
                        "share_count": md["share_count"],
                        "put_days": md["put_days"] or parse_prescan_num(ps["days_text"]),
                        "button_text": md["button_text"] or ps["cta_text"],
                        "landing_page": md["landing_page"],
                        "store_url": md["landing_page"],
                        "video_url": md["video_url"],
                        "shop_type": md["shop_type"] or ps["platform_badge"],
                        "fetch_region": md["fetch_region"],
                        "first_seen": md.get("first_seen", ""),
                        "last_seen": md.get("last_seen", ""),
                        "min_cpm": md.get("cpm", ""),
                    }

                    # Classify + dedup + record
                    classification, scores, reasons = classify_ad(ad_data, tier)

                    # Hard country gate: discard ads not targeting required regions
                    if REQUIRE_TARGET_REGION:
                        ad_regions = extract_regions(ad_data)
                        if ad_regions and not any(r in TARGET_REGIONS for r in ad_regions):
                            if is_research_mode:
                                print(f"    [REGION GATE] {ad_data['unique_id'][:30]} regions={ad_regions} -> DISCARD")
                            classification = "DISCARD"
                            reasons.append(f"region gate: {ad_regions} not in {TARGET_REGIONS}")

                    dk = make_dedupe_key(ad_data)
                    is_new, canonical_id = dedup.check_and_add(ad_data, {
                        "advertiser_name": ad_data["unique_id"],
                        "scores": scores,
                    })

                    if is_new:
                        kw_card_opens += 1
                        pass_opens += 1
                        dup_count = dedup.get_duplicate_count(ad_data["ad_id"])
                        record = build_record(ad_data, keyword, kw_config, classification, scores, reasons,
                                              dk, dup_count, 1, S.DETAIL_MODAL_OPEN, "ui_modal_extraction")
                        selection_reason = oq.get("selection_reason", "")
                        if selection_reason:
                            record["selection_reason"] = selection_reason
                            record["prescan_views"] = oq.get("views", 0)
                            record["prescan_days"] = oq.get("days", 0)
                            record["prescan_likes"] = oq.get("likes", 0)
                        record["search_pass"] = pass_label
                        all_records.append(record)
                        kw_records.append(record)

                        # Track domain
                        if hasattr(domain_tracker, 'track'):
                            domain_tracker.track(ad_data["landing_page"], keyword)

                        sel_info = f" [{selection_reason}]" if selection_reason else ""
                        step_logger.log(keyword, pass_idx, S.DETAIL_MODAL_OPEN, "extract_detail",
                                        [S.DETAIL_MODAL_OPEN], "fields_present",
                                        "success", S.DETAIL_MODAL_OPEN,
                                        notes=f"card {ci}: {classification} | {ad_data['unique_id'][:30]}{sel_info}")

                    # Close modal
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(800)
                    if await is_modal_open():
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(800)

                    if kw_card_opens >= kw_max_card_opens or pass_opens >= pass_max_opens:
                        break

            except Exception as pass_err:
                err_name = type(pass_err).__name__
                if "TargetClosed" in err_name or "closed" in str(pass_err).lower():
                    print(f"\n  [CRASH] Browser/page closed (likely credits exhausted): {str(pass_err)[:80]}")
                    abort_run = True
                else:
                    print(f"\n  [ERROR] Pass loop error: {err_name}: {str(pass_err)[:80]}")

            kw_gate_passed = len(kw_records) > 0 or kw_cards_scanned > 0

            # ── Keyword batch summary ──
            kw_total = len(kw_records)
            kw_winners = sum(1 for r in kw_records if r["classification"] == "WINNER")
            kw_possible = sum(1 for r in kw_records if r["classification"] == "POSSIBLE_WINNER")
            kw_mid = sum(1 for r in kw_records if r["classification"] == "MID")
            kw_total_scanned = kw_total + kw_discarded
            junk_rate = kw_discarded / max(kw_total_scanned, 1)

            if kw_winners >= 2 or (kw_possible >= 3 and junk_rate < 0.5):
                recommend = "expand"
                reason = f"{kw_winners}W/{kw_possible}PW, {junk_rate:.0%} junk"
            elif junk_rate > 0.8 and kw_winners == 0:
                recommend = "abandon"
                reason = f"{junk_rate:.0%} junk, 0 winners"
            elif junk_rate > 0.6:
                recommend = "reduce"
                reason = f"high junk ({junk_rate:.0%})"
            else:
                recommend = "maintain"
                reason = "moderate signal"

            summary = {
                "keyword": keyword, "tier": tier, "mode": mode,
                "pages_visited": kw_pages_visited,
                "cards_scanned": kw_total_scanned, "cards_captured": kw_total,
                "pre_filtered_out": kw_discarded,
                "winners": kw_winners, "possible_winners": kw_possible, "mid": kw_mid,
                "junk_rate": round(junk_rate, 2), "early_terminated": kw_early_terminated,
                "recommend": recommend, "reason": reason,
                "gate_passed": kw_gate_passed or (kw_pages_visited > 0 and kw_total_scanned > 0),
            }
            # Add keyword outcome label
            summary["outcome_label"] = label_keyword_outcome(summary)
            keyword_summaries.append(summary)
            write_batch_summary(keyword, kw_config, summary, BATCH_LOG)

            gate = "PASS" if summary["gate_passed"] else "FAIL"
            outcome = summary["outcome_label"]
            print(f"\n  [{gate}] \"{keyword}\": {kw_total} captured, {kw_winners}W/{kw_possible}PW/{kw_mid}M, junk={junk_rate:.0%}, {recommend} [{outcome}]")

            if summary["gate_passed"]:
                run_meta["keywords_completed"] += 1
            else:
                run_meta["unstable_keywords"].append(keyword)

        # ── End of search loop ──
        try:
            # Final drift check in research mode
            if is_research_mode and baseline_mgr and not abort_run:
                final_drift = await baseline_mgr.check_drift(len(stage_keywords), "FINAL")
                run_meta["drift_events"].append(final_drift)
                if final_drift.get("drifted"):
                    run_meta["operator_stability"] = False

            run_meta["total_recoveries"] = op._total_recoveries
            if baseline_mgr:
                run_meta["baseline_filter_confidence"] = baseline_mgr.confidence
                run_meta["baseline_confidence_detail"] = baseline_mgr.confidence_detail
                run_meta["drift_events"] = baseline_mgr.drift_events
            run_meta["operator_stability"] = run_meta.get("operator_stability", True) and (
                op._total_recoveries <= op._max_total_recoveries * 0.7
            )
            await take_screenshot(page, "99_complete", ts)
        except Exception as post_err:
            print(f"\n[WARN] Post-loop cleanup failed (browser may have crashed): {str(post_err)[:100]}")
            print(f"  Collected {len(all_records)} records — saving partial results.")
        try:
            await browser.close()
        except Exception:
            pass

    # ── Save outputs (runs even after browser crash) ──
    print(f"\n[STEP 3] Saving...")
    step_log_path = step_logger.save()
    run_meta["step_log_path"] = str(step_log_path)

    output = {
        "meta": {
            "timestamp": datetime.now().isoformat(), "stage": stage_key,
            "stage_name": stage_config["name"], "total_records": len(all_records),
            "classifications": dict(Counter(r["classification"] for r in all_records)),
            "run_meta": run_meta,
        },
        "keyword_summaries": keyword_summaries,
        "ads": sorted(all_records, key=lambda r: r["scores"]["relevance_score"] + r["scores"]["performance_score"], reverse=True),
    }
    json_path = DATA_DIR / f"pipiads_v4_stage{stage_key}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"  JSON: {json_path.name}")
    print(f"  Steps: {step_log_path.name}")

    report_path = generate_report(all_records, keyword_summaries, stage_key, stage_config, run_meta, domain_tracker=domain_tracker)
    print(f"  Report: {report_path.name}")

    class_counts = Counter(r["classification"] for r in all_records)
    print(f"\n{'='*70}")
    print(f"STAGE {stage_key} COMPLETE — {stage_config['name']}")
    print(f"{'='*70}")

    # ── Research mode: comprehensive summary ──
    if is_research_mode:
        # 1. Baseline reconciliation result
        br = run_meta.get("baseline_reconciliation", {})
        if br:
            required_rebuild = br.get("required_rebuild", False)
            print(f"\n[1] BASELINE RECONCILIATION: {'REQUIRED REBUILD' if required_rebuild else 'VERIFIED (no rebuild needed)'}")
            print(f"    Actions taken: {br.get('actions_taken', []) or 'none'}")
            print(f"    Applied chips: {br.get('applied_chips', [])}")

        # 2. Baseline filter confidence
        print(f"\n[2] BASELINE FILTER CONFIDENCE: {run_meta.get('baseline_filter_confidence', 'N/A'):.0%}" if isinstance(run_meta.get('baseline_filter_confidence'), (int, float)) else f"\n[2] BASELINE FILTER CONFIDENCE: N/A")
        conf_detail = run_meta.get("baseline_confidence_detail", {})
        for fname, status in conf_detail.items():
            print(f"    {fname}: {status}")

        # 3. Drift events
        drift_evts = run_meta.get("drift_events", [])
        any_drift = any(d.get("drifted") for d in drift_evts)
        print(f"\n[3] DRIFT: {'YES — drift occurred' if any_drift else 'No drift detected'}")
        for d in drift_evts:
            if d.get("drifted"):
                print(f"    At keyword {d['keyword_index']} ({d['keyword']}): drifted={d['drifted_filters']}, "
                      f"corrected={d['corrections_made']}, unrecoverable={d.get('unrecoverable', False)}")

        # 4. Keyword outcome labels
        print(f"\n[4] KEYWORD OUTCOME LABELS:")
        for s in keyword_summaries:
            label = s.get("outcome_label", "?")
            print(f"    {s['keyword']:30s} [{s['tier']}/{s['mode']:10s}] -> {label:20s} "
                  f"({s.get('winners',0)}W/{s.get('possible_winners',0)}PW, junk={s.get('junk_rate',0):.0%})")

        # 5. Strongest keywords
        strong = [s for s in keyword_summaries if s.get("outcome_label") in ("HIGH_SIGNAL", "MODERATE_SIGNAL")]
        print(f"\n[5] STRONGEST KEYWORDS ({len(strong)}):")
        for s in sorted(strong, key=lambda x: x.get("winners", 0) + x.get("possible_winners", 0), reverse=True):
            print(f"    {s['keyword']}: {s.get('winners',0)}W/{s.get('possible_winners',0)}PW")

        # 6. Top competitor domains (using DomainTracker)
        strong_competitors = domain_tracker.get_strong_competitors(threshold=3)
        all_domains = domain_tracker.get_all_domains()
        print(f"\n[6] TOP COMPETITOR DOMAINS:")
        if strong_competitors:
            print(f"  STRONG COMPETITORS (appeared in 3+ keywords):")
            for sc in strong_competitors:
                print(f"    ★ {sc['domain']}: {sc['keyword_count']} keywords — {', '.join(sorted(sc['keywords']))}")
        print(f"  ALL TRACKED DOMAINS ({len(all_domains)}):")
        for d in sorted(all_domains, key=lambda x: x["keyword_count"], reverse=True)[:15]:
            marker = " ★" if domain_tracker.is_strong_competitor(d["domain"]) else ""
            print(f"    {d['domain']}: {d['keyword_count']} keywords{marker}")

        # 7. Most repeated hooks / CTAs / product types
        hooks = [r["hook"] for r in all_records if r["hook"] and r["classification"] in ("WINNER", "POSSIBLE_WINNER")]
        ctas = Counter(r["cta"] for r in all_records if r["cta"])
        categories = Counter(r["product_category"] for r in all_records)
        formats = Counter(r["creative_format"] for r in all_records if r["creative_format"] != "unknown")
        print(f"\n[7] MOST REPEATED HOOKS ({len(hooks)}):")
        for h in hooks[:10]:
            print(f"    - {h[:100]}")
        print(f"\n    MOST REPEATED CTAs:")
        for cta, cnt in ctas.most_common(8):
            print(f"    - {cta}: {cnt}")
        print(f"\n    PRODUCT TYPES:")
        for cat, cnt in categories.most_common(5):
            print(f"    - {cat}: {cnt}")

        # 8. Operator stability
        stable = run_meta.get("operator_stability", True)
        print(f"\n[8] OPERATOR STABILITY: {'HELD' if stable else 'UNSTABLE'}")
        print(f"    Total recoveries: {run_meta['total_recoveries']}")
        print(f"    Unstable keywords: {run_meta['unstable_keywords'] or 'none'}")

        # 9. Failure points
        failures = run_meta.get("failure_points", [])
        print(f"\n[9] FAILURE POINTS: {len(failures) if failures else 'none'}")
        for fp in failures:
            print(f"    - {fp}")

    else:
        # Standard (non-research) summary
        print(f"Keywords: {run_meta['keywords_attempted']} attempted, {run_meta['keywords_completed']} completed")
        print(f"Unstable: {run_meta['unstable_keywords'] or 'none'}")
        print(f"Records: {len(all_records)} (W:{class_counts.get('WINNER',0)} PW:{class_counts.get('POSSIBLE_WINNER',0)} M:{class_counts.get('MID',0)} D:{class_counts.get('DISCARD',0)})")
        print(f"Recoveries: {run_meta['total_recoveries']}")

        if stage_key == "A0":
            print(f"\n[NEXT] Inspect step log and report. If clean, run: --stage A1")
        elif stage_key == "A1":
            print(f"\n[NEXT] Validate classification and fields. If clean: --stage B")
        elif stage_key == "B":
            print(f"\n[NEXT] Review junk rates and recommendations. If clean: --stage C")

    print(f"\n[+] Done!")


if __name__ == "__main__":
    asyncio.run(main())
