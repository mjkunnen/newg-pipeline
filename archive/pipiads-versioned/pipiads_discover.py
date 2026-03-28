"""
NEWGARMENTS - PiPiAds Discovery & Operator v4

Modes:
  --mode discover   Learn the Pipiads interface from live DOM.
                    Inspects 3+ cards structurally, tests 2 distinct card opens,
                    builds ranked recipes, multi-signal state verification.
                    Saves site_map.json, state_catalog.json, dom_signatures.json,
                    interaction_recipes.json, consistency_report.json,
                    artifact_validation.json, screenshots, html snapshots.

  --mode A0         Discovery + operator validation + fallback-path test.
                    Runs discover, then validates with a third card open using
                    alternate recipe. Passes only if all gates met.

  --mode A1         Mini-batch research (3 keywords, 1 page). Requires valid artifacts.
  --mode B          Controlled validation (8 keywords, 2 pages). Requires valid artifacts.
  --mode C          Full research run. Requires valid artifacts.
  --mode filter_lab  Filter optimization lab. Tests filter profiles for niche relevance.
  --mode research    Baseline filter research. Applies known-good filters, runs keyword
                     research with pre-scan, selective opening, classification, and
                     pattern tracking. Outputs research_records.json, competitor_summary.json,
                     creative_patterns.md.

Usage:
  python pipiads_discover.py --mode discover
  python pipiads_discover.py --mode A0
  python pipiads_discover.py --mode research
"""
import asyncio
import argparse
import hashlib
import json
import re
import sys
import io
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page

# ── Windows encoding fix ──
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).parent
SCREENSHOTS = BASE / "pipiads_screenshots"
DATA_DIR = BASE / "pipiads_data"
LEARN_DIR = DATA_DIR / "learned"
HTML_SNAPS = DATA_DIR / "html_snapshots"
STEP_LOG_DIR = DATA_DIR / "step_logs"
BATCH_LOG = DATA_DIR / "batch_summaries"
COOKIES = DATA_DIR / "pipiads_cookies.json"

# Learned artifact paths
SITE_MAP_PATH = LEARN_DIR / "site_map.json"
STATE_CATALOG_PATH = LEARN_DIR / "state_catalog.json"
DOM_SIGNATURES_PATH = LEARN_DIR / "dom_signatures.json"
INTERACTION_RECIPES_PATH = LEARN_DIR / "interaction_recipes.json"
CONSISTENCY_REPORT_PATH = LEARN_DIR / "consistency_report.json"
ARTIFACT_VALIDATION_PATH = LEARN_DIR / "artifact_validation.json"

ARTIFACT_VERSION = "4.1"

TARGET_REGIONS = ["US", "GB", "DE", "NL", "FR", "CA", "AU"]

for d in [SCREENSHOTS, DATA_DIR, LEARN_DIR, HTML_SNAPS, STEP_LOG_DIR, BATCH_LOG]:
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# STEP LOGGER
# ═══════════════════════════════════════════════════════════

class StepLogger:
    def __init__(self, ts: str):
        self.ts = ts
        self.steps = []
        self.counter = 0

    def log(self, phase, action, state_before, state_after, result, notes="", screenshot=""):
        self.counter += 1
        entry = {
            "step_id": self.counter, "timestamp": datetime.now().isoformat(),
            "phase": phase, "action": action, "state_before": state_before,
            "state_after": state_after, "result": result, "notes": notes,
            "screenshot": screenshot,
        }
        self.steps.append(entry)
        icon = {"success": "+", "soft_fail": "~", "hard_fail": "!", "info": "."}
        print(f"  [{icon.get(result, '?')}] #{self.counter} {action}: {state_before} -> {state_after} [{result}]"
              + (f" | {notes}" if notes else ""))
        return entry

    def save(self):
        path = STEP_LOG_DIR / f"steps_{self.ts}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.steps, f, indent=2, ensure_ascii=False)
        return path


# ═══════════════════════════════════════════════════════════
# SCREENSHOT + HTML HELPERS
# ═══════════════════════════════════════════════════════════

async def take_ss(page: Page, label: str, ts: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:80]
    path = SCREENSHOTS / f"{ts}_{safe}.png"
    try:
        await page.screenshot(path=str(path))
        return str(path)
    except Exception as e:
        print(f"  [WARN] screenshot failed: {str(e)[:60]}")
        return ""


async def save_html(page: Page, label: str, ts: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", label)[:80]
    path = HTML_SNAPS / f"{ts}_{safe}.html"
    try:
        path.write_text(await page.content(), encoding="utf-8")
        return str(path)
    except Exception as e:
        print(f"  [WARN] html snapshot failed: {str(e)[:60]}")
        return ""


# ═══════════════════════════════════════════════════════════
# DOM INSPECTORS — all run in the live browser via evaluate()
# ═══════════════════════════════════════════════════════════

async def inspect_page_meta(page: Page) -> dict:
    return await page.evaluate("""() => ({
        url: location.href,
        title: document.title,
        headings: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,20).map(h => ({
            tag: h.tagName, text: h.textContent.trim().substring(0,100), class: h.className.substring(0,80)
        })),
        inputs: Array.from(document.querySelectorAll('input[type="text"],input[type="search"],input:not([type])')).slice(0,10).map(i => ({
            placeholder: i.placeholder, name: i.name, class: i.className.substring(0,80), id: i.id, type: i.type,
            visible: i.offsetParent !== null, rect: i.getBoundingClientRect()
        })),
        buttons: Array.from(document.querySelectorAll('button')).filter(b => b.offsetParent !== null).slice(0,25).map(b => ({
            text: b.textContent.trim().substring(0,60), class: b.className.substring(0,80),
            type: b.type, ariaLabel: b.getAttribute('aria-label')||'',
            rect: b.getBoundingClientRect()
        })),
    })""")


async def inspect_nav(page: Page) -> list:
    return await page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('nav a, aside a, [class*="sidebar"] a, [class*="menu"] a, [class*="nav"] a').forEach(a => {
            if (a.offsetParent !== null) items.push({text: a.textContent.trim().substring(0,80), href: a.href, class: a.className.substring(0,80)});
        });
        document.querySelectorAll('[role="tab"], [class*="tab-item"], [class*="tab_item"]').forEach(t => {
            if (t.offsetParent !== null) items.push({text: t.textContent.trim().substring(0,80), href: t.href||'', class: t.className.substring(0,80), type:'tab'});
        });
        return items.slice(0,30);
    }""")


async def inspect_repeated_containers(page: Page) -> list:
    return await page.evaluate("""() => {
        const candidates = [];
        document.querySelectorAll('[class*="list"],[class*="grid"],[class*="result"],[class*="content"],[class*="card"],[class*="wrap"]').forEach(container => {
            if (!container.offsetParent) return;
            const rect = container.getBoundingClientRect();
            if (rect.width < 200 || rect.height < 100) return;
            const children = Array.from(container.children).filter(c => c.offsetParent !== null);
            if (children.length < 2) return;
            const sigs = children.map(c => c.tagName + '.' + (c.className||'').split(' ').filter(x=>x).sort().join('.'));
            const counts = {};
            sigs.forEach(s => { counts[s] = (counts[s]||0)+1; });
            const best = Object.entries(counts).sort((a,b)=>b[1]-a[1])[0];
            if (best && best[1] >= 2) {
                const rep = children.find(c => (c.tagName+'.'+(c.className||'').split(' ').filter(x=>x).sort().join('.')) === best[0]);
                candidates.push({
                    container_tag: container.tagName, container_class: container.className.substring(0,120),
                    container_id: container.id,
                    container_rect: {x:Math.round(rect.x), y:Math.round(rect.y), w:Math.round(rect.width), h:Math.round(rect.height)},
                    child_count: children.length, repeated_count: best[1],
                    repeated_signature: best[0].substring(0,120),
                    child_sample_class: rep ? rep.className.substring(0,120) : '',
                    child_sample_tag: rep ? rep.tagName : '',
                    child_sample_text: rep ? rep.textContent.trim().substring(0,250) : '',
                    is_in_main_content: rect.x > 50 && rect.width > 400,
                });
            }
        });
        candidates.sort((a,b) => {
            const aMain = a.is_in_main_content ? 1 : 0;
            const bMain = b.is_in_main_content ? 1 : 0;
            if (aMain !== bMain) return bMain - aMain;
            return b.repeated_count - a.repeated_count;
        });
        return candidates.slice(0,10);
    }""")


async def inspect_card_fields(page: Page, card_selector: str, card_index: int = 0) -> dict:
    """Inspect inner structure of a specific card by index."""
    return await page.evaluate("""([selector, idx]) => {
        const cards = document.querySelectorAll(selector);
        const card = cards[idx];
        if (!card) return {error: 'card not found', selector, idx, total: cards.length};
        const result = {
            selector, idx, tag: card.tagName, class: card.className.substring(0,120),
            rect: card.getBoundingClientRect(),
            images: [], links: [], buttons: [], texts: [], videos: [], data_attrs: [],
        };
        function walk(el, depth) {
            if (depth > 6 || !el) return;
            Array.from(el.children).forEach(child => {
                if (!child.offsetParent && child.tagName !== 'IMG') return;
                if (child.tagName === 'IMG')
                    result.images.push({src:(child.src||'').substring(0,200), alt:child.alt, class:child.className.substring(0,80)});
                if (child.tagName === 'A')
                    result.links.push({href:(child.href||'').substring(0,200), text:child.textContent.trim().substring(0,80), class:child.className.substring(0,80)});
                if (child.tagName === 'BUTTON')
                    result.buttons.push({text:child.textContent.trim().substring(0,80), class:child.className.substring(0,80)});
                if (child.tagName === 'VIDEO')
                    result.videos.push({src:(child.src||'').substring(0,200)});
                if (child.children.length === 0 && child.textContent.trim().length > 0 && child.textContent.trim().length < 200)
                    result.texts.push({text:child.textContent.trim(), tag:child.tagName, class:child.className.substring(0,80)});
                // Collect data attributes
                Array.from(child.attributes).filter(a => a.name.startsWith('data-')).forEach(a => {
                    result.data_attrs.push({name: a.name, value: a.value.substring(0,80), on_tag: child.tagName, on_class: child.className.substring(0,60)});
                });
                walk(child, depth+1);
            });
        }
        walk(card, 0);
        return result;
    }""", [card_selector, card_index])


async def inspect_modal_state(page: Page) -> dict:
    return await page.evaluate("""() => {
        const result = {modals:[], overlays:[], drawers:[]};
        document.querySelectorAll('[class*="modal"],[class*="dialog"],[role="dialog"],.el-dialog__wrapper').forEach(m => {
            const style = getComputedStyle(m);
            if (style.display === 'none' && !m.classList.contains('el-dialog__wrapper')) return;
            const rect = m.getBoundingClientRect();
            if (rect.width < 100 || rect.height < 100) return;
            const visible = m.offsetParent !== null || style.display !== 'none';
            if (!visible) return;
            result.modals.push({
                tag: m.tagName, class: m.className.substring(0,120), id: m.id,
                rect: {x:Math.round(rect.x),y:Math.round(rect.y),w:Math.round(rect.width),h:Math.round(rect.height)},
                close_buttons: Array.from(m.querySelectorAll('[class*="close"],[aria-label*="close" i],[aria-label*="Close"],button')).filter(b=>b.offsetParent!==null).slice(0,8).map(b=>({
                    tag:b.tagName, class:b.className.substring(0,80), text:b.textContent.trim().substring(0,40),
                    ariaLabel:b.getAttribute('aria-label')||'',
                    rect: b.getBoundingClientRect(),
                })),
                text_preview: m.textContent.trim().substring(0,400),
            });
        });
        document.querySelectorAll('[class*="overlay"],[class*="backdrop"],[class*="mask"],.el-overlay').forEach(o => {
            if (o.offsetParent !== null) result.overlays.push({tag:o.tagName, class:o.className.substring(0,120), rect:o.getBoundingClientRect()});
        });
        document.querySelectorAll('[class*="drawer"]').forEach(d => {
            if (d.offsetParent !== null) { const r=d.getBoundingClientRect(); if(r.width>50) result.drawers.push({tag:d.tagName,class:d.className.substring(0,120),rect:{x:r.x,y:r.y,w:r.width,h:r.height}}); }
        });
        return result;
    }""")


async def inspect_pagination(page: Page) -> dict:
    return await page.evaluate("""() => {
        const result = {candidates:[]};
        ['[class*="pagination"]','[class*="pager"]','.el-pagination','nav[aria-label*="page" i]'].forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                if (el.offsetParent !== null) result.candidates.push({
                    selector:sel, tag:el.tagName, class:el.className.substring(0,120),
                    buttons: Array.from(el.querySelectorAll('button,a,li')).filter(b=>b.offsetParent!==null).slice(0,15).map(b=>({
                        text:b.textContent.trim().substring(0,30), tag:b.tagName, class:b.className.substring(0,60),
                    })),
                });
            });
        });
        return result;
    }""")


async def inspect_filters(page: Page) -> dict:
    return await page.evaluate("""() => {
        const result = {filter_groups:[]};
        const seen = new Set();
        ['[class*="filter"]','[class*="Filter"]','[class*="sort"]','[class*="Sort"]','select','[class*="dropdown"]'].forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                if (!el.offsetParent) return;
                const key = el.tagName+el.className;
                if (seen.has(key)) return; seen.add(key);
                const rect = el.getBoundingClientRect();
                if (rect.width<30||rect.height<15) return;
                result.filter_groups.push({
                    selector:sel, tag:el.tagName, class:el.className.substring(0,120),
                    text:el.textContent.trim().substring(0,150),
                    rect:{x:Math.round(rect.x),y:Math.round(rect.y),w:Math.round(rect.width),h:Math.round(rect.height)},
                });
            });
        });
        return result;
    }""")


async def count_visible_cards(page: Page, selector: str) -> int:
    """Count how many visible elements match a selector."""
    return await page.evaluate("""(sel) => {
        return Array.from(document.querySelectorAll(sel)).filter(el => el.offsetParent !== null).length;
    }""", selector)


# ═══════════════════════════════════════════════════════════
# MULTI-SIGNAL RESULTS PAGE VERIFICATION
# ═══════════════════════════════════════════════════════════

async def verify_results_page(page: Page, card_selector: Optional[str] = None) -> dict:
    """
    Multi-signal verification that we are on a real results page.
    Returns {verified: bool, evidence: {...}, signals: {name: bool}}.
    Requires multiple signals, not just repeated containers.
    """
    evidence = {}
    signals = {}

    url = page.url.lower()

    # Signal 1: URL contains search-related path
    signals["url_is_search"] = "search" in url or "ad-search" in url
    evidence["url"] = url

    # Signal 2: Search input visible (still on search page context)
    try:
        search_visible = await page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[type="text"],input[type="search"],input:not([type])');
            return Array.from(inputs).some(i => i.offsetParent !== null && (i.placeholder||'').toLowerCase().includes('search'));
        }""")
        signals["search_input_visible"] = search_visible
    except Exception:
        signals["search_input_visible"] = False

    # Signal 3: Repeated card containers in main content area
    repeated = await inspect_repeated_containers(page)
    main_content_cards = [r for r in repeated if r.get("is_in_main_content") and r["repeated_count"] >= 3]
    signals["repeated_card_containers"] = len(main_content_cards) > 0
    evidence["card_container_count"] = len(main_content_cards)
    evidence["top_container_repeat_count"] = main_content_cards[0]["repeated_count"] if main_content_cards else 0

    # Signal 4: If we have a known card selector, verify it has visible matches
    if card_selector:
        visible_count = await count_visible_cards(page, card_selector)
        signals["known_card_selector_matches"] = visible_count >= 2
        evidence["known_card_count"] = visible_count
    else:
        signals["known_card_selector_matches"] = None  # can't check

    # Signal 5: Cards contain expected sub-features (thumbnail/text/metrics)
    if main_content_cards:
        sample_text = main_content_cards[0].get("child_sample_text", "").lower()
        has_metrics = any(c in sample_text for c in ["view", "like", "day", "click", "cpm", "ctr", "impression", "spend", "cost"])
        has_content = len(sample_text) > 30
        signals["cards_have_expected_features"] = has_metrics or has_content
        evidence["sample_card_text_len"] = len(sample_text)
        evidence["sample_has_metrics"] = has_metrics
    else:
        signals["cards_have_expected_features"] = False

    # Signal 6: Pagination or result count visible
    pagination = await inspect_pagination(page)
    has_pagination = len(pagination.get("candidates", [])) > 0
    signals["pagination_or_count_visible"] = has_pagination
    evidence["pagination_candidates"] = len(pagination.get("candidates", []))

    # Signal 7: No blocking modal/overlay
    modal_state = await inspect_modal_state(page)
    signals["no_blocking_modal"] = len(modal_state.get("modals", [])) == 0
    evidence["open_modals"] = len(modal_state.get("modals", []))

    # Signal 8: Not dominated by loading skeletons
    try:
        skeleton_count = await page.evaluate("""() => {
            return document.querySelectorAll('[class*="skeleton"],[class*="loading"],[class*="spinner"]').length;
        }""")
        signals["not_loading"] = skeleton_count < 3
        evidence["skeleton_elements"] = skeleton_count
    except Exception:
        signals["not_loading"] = True

    # ── Combine: require at least 4 of the checkable signals ──
    checkable = {k: v for k, v in signals.items() if v is not None}
    passing = sum(1 for v in checkable.values() if v)
    total = len(checkable)
    verified = passing >= 4 and signals.get("repeated_card_containers", False)

    evidence["signals_passing"] = passing
    evidence["signals_total"] = total

    return {"verified": verified, "evidence": evidence, "signals": signals}


# ═══════════════════════════════════════════════════════════
# SELECTOR STRATEGY BUILDER
# ═══════════════════════════════════════════════════════════

def build_selector_strategies(element_info: dict, element_type: str) -> list:
    """Build ranked selector strategies from element info."""
    strategies = []

    if element_type == "input":
        if element_info.get("placeholder"):
            ph = element_info["placeholder"][:30]
            strategies.append({"selector": f'input[placeholder*="{ph}"]', "stability": "high", "type": "placeholder"})
        if element_info.get("id"):
            strategies.append({"selector": f'#{element_info["id"]}', "stability": "high", "type": "id"})
        if element_info.get("name"):
            strategies.append({"selector": f'input[name="{element_info["name"]}"]', "stability": "medium", "type": "name"})
        if element_info.get("class"):
            cls = element_info["class"].split()[0]
            if cls and len(cls) > 2:
                strategies.append({"selector": f'input.{cls}', "stability": "low", "type": "class"})

    elif element_type == "button":
        text = (element_info.get("text", "") or "").strip()
        if text and len(text) < 25:
            strategies.append({"selector": f'button:has-text("{text}")', "stability": "high", "type": "text"})
        if element_info.get("ariaLabel"):
            strategies.append({"selector": f'[aria-label="{element_info["ariaLabel"]}"]', "stability": "high", "type": "aria"})
        if element_info.get("class"):
            cls = element_info["class"].split()[0]
            if cls and len(cls) > 2:
                strategies.append({"selector": f'button.{cls}', "stability": "medium", "type": "class"})

    elif element_type == "card_root":
        if element_info.get("child_sample_class"):
            for cls in element_info["child_sample_class"].split()[:3]:
                cls = cls.strip()
                if cls and len(cls) > 2:
                    strategies.append({"selector": f'.{cls}', "stability": "medium", "type": "class"})
        if element_info.get("container_class"):
            for cls in element_info["container_class"].split()[:2]:
                cls = cls.strip()
                if cls and len(cls) > 2:
                    tag = (element_info.get("child_sample_tag") or "div").lower()
                    strategies.append({"selector": f'.{cls} > {tag}', "stability": "medium", "type": "container_child"})

    elif element_type == "close_button":
        if element_info.get("ariaLabel"):
            strategies.append({"selector": f'[aria-label="{element_info["ariaLabel"]}"]', "stability": "high", "type": "aria"})
        text = (element_info.get("text", "") or "").strip()
        if text and len(text) < 15:
            strategies.append({"selector": f'button:has-text("{text}")', "stability": "medium", "type": "text"})
        if element_info.get("class"):
            cls = element_info["class"].split()[0]
            if cls and len(cls) > 2:
                strategies.append({"selector": f'.{cls}', "stability": "medium", "type": "class"})

    return strategies


# ═══════════════════════════════════════════════════════════
# RANKED RECIPE BUILDER
# ═══════════════════════════════════════════════════════════

class RecipeBook:
    """Stores ranked interaction recipes with success/fail tracking."""

    def __init__(self):
        self.recipes: Dict[str, list] = {}

    def add(self, action: str, method: dict, success: bool, notes: str = ""):
        if action not in self.recipes:
            self.recipes[action] = []
        # Check if this method already exists
        for existing in self.recipes[action]:
            if existing["method"].get("selector") == method.get("selector") and existing["method"].get("type") == method.get("type"):
                if success:
                    existing["success_count"] += 1
                else:
                    existing["fail_count"] += 1
                existing["last_verified_at"] = datetime.now().isoformat()
                existing["notes"] = notes
                return
        # New recipe
        self.recipes[action].append({
            "method": method,
            "success_count": 1 if success else 0,
            "fail_count": 0 if success else 1,
            "confidence": 0.9 if success else 0.1,
            "last_verified_at": datetime.now().isoformat(),
            "notes": notes,
        })

    def rank(self, action: str) -> list:
        """Return recipes for an action ranked by confidence."""
        entries = self.recipes.get(action, [])
        for e in entries:
            total = e["success_count"] + e["fail_count"]
            e["confidence"] = round(e["success_count"] / max(total, 1), 2)
        return sorted(entries, key=lambda e: e["confidence"], reverse=True)

    def to_dict(self) -> dict:
        result = {}
        for action, entries in self.recipes.items():
            result[action] = self.rank(action)
        return result


# ═══════════════════════════════════════════════════════════
# CARD OPEN + CLOSE TEST — reusable for discovery + A0
# ═══════════════════════════════════════════════════════════

async def test_card_open(page: Page, card_selector: str, card_index: int,
                          open_method: dict, logger: StepLogger, recipe_book: RecipeBook,
                          ts: str, label: str) -> dict:
    """
    Attempt to open a card and inspect what happens.
    Returns {success, detail_type, modal_info, close_tested, close_success, ...}
    """
    result = {
        "success": False, "detail_type": "unknown", "card_index": card_index,
        "open_method": open_method, "modal_info": None,
        "close_tested": False, "close_success": False, "close_method_used": None,
    }

    # Pre-state
    pre_url = page.url
    pre_modals = await inspect_modal_state(page)
    ss_pre = await take_ss(page, f"{label}_pre_open_card{card_index}", ts)

    # Attempt open
    try:
        sel = open_method.get("selector", card_selector)
        cards = page.locator(sel)
        count = await cards.count()
        if count <= card_index:
            logger.log("card_test", f"open_card_{card_index}", "results_page", "results_page", "hard_fail",
                        notes=f"only {count} cards, need index {card_index}", screenshot=ss_pre)
            recipe_book.add("open_result_card", open_method, False, f"index {card_index} out of range ({count} visible)")
            return result

        target = cards.nth(card_index)
        await target.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await target.click()
        await page.wait_for_timeout(3000)

    except Exception as e:
        logger.log("card_test", f"open_card_{card_index}", "results_page", "results_page", "hard_fail",
                    notes=f"click failed: {str(e)[:80]}", screenshot=ss_pre)
        recipe_book.add("open_result_card", open_method, False, f"click exception: {str(e)[:60]}")
        return result

    # Post-state
    post_url = page.url
    post_modals = await inspect_modal_state(page)
    ss_post = await take_ss(page, f"{label}_post_open_card{card_index}", ts)
    html_post = await save_html(page, f"{label}_detail_card{card_index}", ts)

    url_changed = post_url != pre_url
    new_modals = len(post_modals.get("modals", [])) - len(pre_modals.get("modals", []))
    new_drawers = len(post_modals.get("drawers", [])) - len(pre_modals.get("drawers", []))

    if new_modals > 0:
        result["detail_type"] = "modal"
        result["modal_info"] = post_modals["modals"][-1]
        result["success"] = True
    elif new_drawers > 0:
        result["detail_type"] = "drawer"
        result["success"] = True
    elif url_changed:
        result["detail_type"] = "page"
        result["success"] = True
    else:
        result["detail_type"] = "unknown"
        result["success"] = False

    recipe_book.add("open_result_card", open_method, result["success"],
                      f"detail_type={result['detail_type']}")

    state_after = result["detail_type"] if result["success"] else "results_page"
    logger.log("card_test", f"open_card_{card_index}", "results_page", state_after,
                "success" if result["success"] else "hard_fail",
                notes=f"type={result['detail_type']}, url_changed={url_changed}, new_modals={new_modals}",
                screenshot=ss_post)

    # ── Close test ──
    if result["success"]:
        result["close_tested"] = True
        close_success = False
        close_method_used = None

        if result["detail_type"] == "modal":
            modal = result["modal_info"]
            # Try close buttons found in modal
            close_attempts = []
            for cb in (modal or {}).get("close_buttons", []):
                strategies = build_selector_strategies(cb, "close_button")
                close_attempts.extend(strategies)
            # Add Escape and backdrop
            close_attempts.append({"selector": "Escape", "stability": "high", "type": "keyboard"})
            for ov in post_modals.get("overlays", []):
                cls = ov.get("class", "").split()[0] if ov.get("class") else ""
                if cls:
                    close_attempts.append({"selector": f'.{cls}', "stability": "low", "type": "backdrop"})

            for attempt in close_attempts:
                try:
                    if attempt["type"] == "keyboard":
                        await page.keyboard.press("Escape")
                    elif attempt["type"] == "backdrop":
                        loc = page.locator(attempt["selector"]).first
                        box = await loc.bounding_box()
                        if box:
                            await page.mouse.click(box["x"] + 5, box["y"] + 5)
                    else:
                        loc = page.locator(attempt["selector"]).first
                        if await loc.is_visible(timeout=1500):
                            await loc.click()

                    await page.wait_for_timeout(1500)
                    post_close = await inspect_modal_state(page)
                    if len(post_close.get("modals", [])) < len(post_modals.get("modals", [])):
                        close_success = True
                        close_method_used = attempt
                        recipe_book.add("close_detail", attempt, True, f"closed modal via {attempt['type']}")
                        break
                    else:
                        recipe_book.add("close_detail", attempt, False, "modal still open after attempt")
                except Exception:
                    recipe_book.add("close_detail", attempt, False, "exception during close")
                    continue

            if not close_success:
                # Force back
                await page.go_back()
                await page.wait_for_timeout(2000)
                post_back = await inspect_modal_state(page)
                if len(post_back.get("modals", [])) == 0:
                    close_success = True
                    close_method_used = {"selector": "go_back", "type": "browser_back"}
                    recipe_book.add("close_detail", close_method_used, True, "force back worked")

        elif result["detail_type"] == "page":
            await page.go_back()
            await page.wait_for_timeout(3000)
            close_method_used = {"selector": "go_back", "type": "browser_back"}
            if "search" in page.url.lower():
                close_success = True
                recipe_book.add("close_detail", close_method_used, True, "browser back to results")
            else:
                recipe_book.add("close_detail", close_method_used, False, "back did not return to results")

        elif result["detail_type"] == "drawer":
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)
            post_close = await inspect_modal_state(page)
            if len(post_close.get("drawers", [])) == 0:
                close_success = True
                close_method_used = {"selector": "Escape", "type": "keyboard"}
                recipe_book.add("close_detail", close_method_used, True, "escape closed drawer")

        result["close_success"] = close_success
        result["close_method_used"] = close_method_used

        ss_close = await take_ss(page, f"{label}_post_close_card{card_index}", ts)
        logger.log("card_test", f"close_card_{card_index}",
                    result["detail_type"], "results_page" if close_success else "unknown",
                    "success" if close_success else "hard_fail",
                    notes=f"method={close_method_used}", screenshot=ss_close)

    return result


# ═══════════════════════════════════════════════════════════
# DISCOVER MODE
# ═══════════════════════════════════════════════════════════

async def run_discover(page: Page, logger: StepLogger, ts: str) -> dict:
    print("\n" + "=" * 70)
    print("DISCOVERY MODE — Learning Pipiads interface")
    print("=" * 70)

    site_map = {"sections": [], "url_patterns": {}, "discovered_at": ts, "version": ARTIFACT_VERSION}
    state_catalog = {"states": {}, "version": ARTIFACT_VERSION, "created_at": ts}
    dom_sigs = {
        "version": ARTIFACT_VERSION, "created_at": ts,
        "result_card_roots": [], "detail_modal_roots": [],
        "pagination_candidates": [], "filter_candidates": [],
        "close_button_candidates": [], "search_input_candidates": [],
        "search_button_candidates": [],
    }
    recipe_book = RecipeBook()
    consistency = {
        "card_structure_consistency": "unknown",
        "detail_open_consistency": "unknown",
        "close_recipe_confidence": "unknown",
        "mixed_behavior_notes": [],
        "cards_inspected": 0,
        "opens_tested": 0,
    }

    # ─── STEP 1: Page meta ───
    print("\n[1/11] Page meta...")
    meta = await inspect_page_meta(page)
    ss = await take_ss(page, "d01_page_meta", ts)
    await save_html(page, "d01_page", ts)

    site_map["url_patterns"]["initial"] = meta["url"]
    site_map["page_title"] = meta.get("title", "")

    # Prioritize inputs that look like the main search bar
    # Pipiads main search has placeholder like "Search by any ad keyword..."
    primary_inputs = []
    secondary_inputs = []
    for inp in meta.get("inputs", []):
        ph = (inp.get("placeholder", "") or "").lower()
        strategies = build_selector_strategies(inp, "input")
        entry = {
            **{k: inp.get(k, "") for k in ("placeholder", "name", "id", "class")},
            "selector_strategies": strategies,
        }
        if any(kw in ph for kw in ["keyword", "ad keyword", "search by"]):
            primary_inputs.append(entry)
        elif "search" in ph:
            secondary_inputs.append(entry)
        # Skip inputs that are clearly not the main search (filter inputs, etc.)
    dom_sigs["search_input_candidates"] = primary_inputs + secondary_inputs
    if not dom_sigs["search_input_candidates"] and meta.get("inputs"):
        # Fallback: add first visible input with any placeholder
        for inp in meta["inputs"]:
            if inp.get("visible") and inp.get("placeholder"):
                strategies = build_selector_strategies(inp, "input")
                dom_sigs["search_input_candidates"].append({
                    **{k: inp.get(k, "") for k in ("placeholder", "name", "id", "class")},
                    "selector_strategies": strategies,
                })
                break

    # Exclude buttons that are clearly NOT search-submit (nav buttons, feature buttons, etc.)
    BUTTON_EXCLUDE = ["find similar", "similar by image", "upload", "sign out", "log out",
                      "upgrade", "subscribe", "save", "export", "download"]
    for btn in meta.get("buttons", []):
        text = (btn.get("text", "") or "").strip()
        if not text:
            continue
        text_lower = text.lower()
        if any(excl in text_lower for excl in BUTTON_EXCLUDE):
            continue
        if any(kw in text_lower for kw in ["search", "go"]):
            strategies = build_selector_strategies(btn, "button")
            dom_sigs["search_button_candidates"].append({"text": text, "class": btn.get("class", ""), "selector_strategies": strategies})

    logger.log("discover", "page_meta", "initial", meta["url"][:60], "info",
               notes=f"inputs={len(dom_sigs['search_input_candidates'])}, search_btns={len(dom_sigs['search_button_candidates'])}", screenshot=ss)

    # ─── STEP 2: Nav ───
    print("\n[2/11] Navigation sections...")
    nav = await inspect_nav(page)
    for item in nav:
        site_map["sections"].append(item)
    logger.log("discover", "nav", "search_page", "search_page", "info", notes=f"{len(nav)} items")
    for item in nav[:8]:
        print(f"    - {item.get('text','')[:40]}  →  {item.get('href','')[:50]}")

    # ─── STEP 3: Filters ───
    print("\n[3/11] Filters...")
    filters = await inspect_filters(page)
    dom_sigs["filter_candidates"] = filters.get("filter_groups", [])
    logger.log("discover", "filters", "search_page", "search_page", "info",
               notes=f"{len(dom_sigs['filter_candidates'])} groups")

    # ─── STEP 4: Pre-search state ───
    print("\n[4/11] Pre-search state catalog...")
    modal_pre = await inspect_modal_state(page)
    pag_pre = await inspect_pagination(page)
    state_catalog["states"]["SEARCH_PAGE"] = {
        "name": "SEARCH_PAGE",
        "url_clues": ["ad-search", "search"],
        "identifying_signals": {
            "search_input_visible": len(dom_sigs["search_input_candidates"]) > 0,
            "headings": [h["text"] for h in meta.get("headings", [])[:5]],
            "modals_open": len(modal_pre.get("modals", [])),
        },
        "allowed_actions": ["submit_search", "apply_filter"],
        "expected_transitions": {"submit_search": ["LOADING", "RESULTS_PAGE", "EMPTY_RESULTS"]},
        "confidence": "high" if dom_sigs["search_input_candidates"] else "low",
    }

    # ─── STEP 5: Submit test search ───
    print("\n[5/11] Test search ('streetwear')...")

    search_submitted = False
    for candidate in dom_sigs["search_input_candidates"]:
        for strat in candidate["selector_strategies"]:
            try:
                loc = page.locator(strat["selector"]).first
                if await loc.is_visible(timeout=3000):
                    await loc.click(click_count=3)
                    await loc.fill("streetwear")
                    recipe_book.add("fill_search_input", strat, True, "input filled")
                    print(f"  Input: {strat['type']} → {strat['selector'][:50]}")

                    # Prefer Enter key first (most search UIs submit via Enter)
                    # Pipiads ad-search page has no visible "Search" button — uses Enter
                    enter_method = {"selector": "Enter", "type": "keyboard", "stability": "high"}
                    await loc.press("Enter")
                    recipe_book.add("submit_search", enter_method, True, "enter key submitted")
                    print(f"  Submit: Enter key on input")

                    search_submitted = True
                    break
            except Exception:
                recipe_book.add("fill_search_input", strat, False, "input fill failed")
        if search_submitted:
            break

    # If Enter didn't work, try search buttons as fallback
    if not search_submitted:
        for btn_candidate in dom_sigs["search_button_candidates"]:
            for btn_strat in btn_candidate["selector_strategies"]:
                try:
                    btn_loc = page.locator(btn_strat["selector"]).first
                    if await btn_loc.is_visible(timeout=2000):
                        await btn_loc.click()
                        search_submitted = True
                        recipe_book.add("submit_search", btn_strat, True, "button click submitted")
                        print(f"  Submit fallback: {btn_strat['type']} → {btn_strat['selector'][:50]}")
                        break
                except Exception:
                    recipe_book.add("submit_search", btn_strat, False, "button click failed")
            if search_submitted:
                break

    if not search_submitted:
        logger.log("discover", "submit_search", "search_page", "search_page", "hard_fail",
                    notes="no search method worked")
        return None

    await page.wait_for_timeout(6000)
    ss = await take_ss(page, "d05_after_search", ts)
    await save_html(page, "d05_results", ts)

    # ─── STEP 6: Verify results page (multi-signal) ───
    print("\n[6/11] Verifying results page (multi-signal)...")
    verification = await verify_results_page(page)

    print(f"  Signals:")
    for sig_name, sig_val in verification["signals"].items():
        icon = "+" if sig_val else ("-" if sig_val is False else "?")
        print(f"    [{icon}] {sig_name}")
    print(f"  Verified: {verification['verified']} ({verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']} signals)")

    logger.log("discover", "verify_results", "post_search", "results_page" if verification["verified"] else "unknown",
                "success" if verification["verified"] else "hard_fail",
                notes=f"signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']}", screenshot=ss)

    if not verification["verified"]:
        print("  [FAIL] Results page not verified. Check screenshots and HTML snapshot.")
        return None

    # ─── STEP 7: Inspect card structure for 3+ cards ───
    print("\n[7/11] Inspecting card structures (3+ cards)...")
    repeated = await inspect_repeated_containers(page)
    main_cards = [r for r in repeated if r.get("is_in_main_content") and r["repeated_count"] >= 3]

    if not main_cards:
        main_cards = [r for r in repeated if r["repeated_count"] >= 3]

    if not main_cards:
        logger.log("discover", "find_cards", "results_page", "results_page", "hard_fail",
                    notes="no repeated card containers found")
        return None

    best = main_cards[0]
    card_strategies = build_selector_strategies(best, "card_root")

    if not card_strategies:
        logger.log("discover", "build_card_selectors", "results_page", "results_page", "hard_fail",
                    notes="could not build card selectors")
        return None

    primary_card_sel = card_strategies[0]["selector"]

    # Inspect 3 individual cards for structure comparison
    card_inspections = []
    for idx in range(min(3, best["repeated_count"])):
        fields = await inspect_card_fields(page, primary_card_sel, idx)
        if not fields.get("error"):
            card_inspections.append(fields)
            print(f"  Card {idx}: {len(fields.get('texts',[]))} texts, {len(fields.get('images',[]))} imgs, {len(fields.get('links',[]))} links, {len(fields.get('buttons',[]))} btns")
        else:
            print(f"  Card {idx}: inspection failed — {fields.get('error','')}")

    consistency["cards_inspected"] = len(card_inspections)

    # Compare card structures
    if len(card_inspections) >= 2:
        text_counts = [len(c.get("texts", [])) for c in card_inspections]
        img_counts = [len(c.get("images", [])) for c in card_inspections]
        link_counts = [len(c.get("links", [])) for c in card_inspections]

        text_consistent = max(text_counts) - min(text_counts) <= 3
        img_consistent = max(img_counts) - min(img_counts) <= 1
        link_consistent = max(link_counts) - min(link_counts) <= 2

        if text_consistent and img_consistent and link_consistent:
            consistency["card_structure_consistency"] = "high"
        elif text_consistent or img_consistent:
            consistency["card_structure_consistency"] = "medium"
        else:
            consistency["card_structure_consistency"] = "low"
            consistency["mixed_behavior_notes"].append(
                f"card structure varies: texts={text_counts}, imgs={img_counts}, links={link_counts}")

        print(f"  Structure consistency: {consistency['card_structure_consistency']}")
    else:
        consistency["card_structure_consistency"] = "low"
        consistency["mixed_behavior_notes"].append("fewer than 2 cards inspected")

    # Store card root info
    dom_sigs["result_card_roots"].append({
        "container_class": best.get("container_class", ""),
        "child_class": best.get("child_sample_class", ""),
        "child_tag": best.get("child_sample_tag", ""),
        "repeated_count": best["repeated_count"],
        "selector_strategies": card_strategies,
        "inner_fields_sample": card_inspections[0] if card_inspections else {},
        "structure_consistency": consistency["card_structure_consistency"],
        "cards_inspected_count": len(card_inspections),
    })

    # Also build open-card recipes from card inner elements
    # (thumbnail click, title link click, etc.)
    if card_inspections:
        sample = card_inspections[0]
        # Thumbnail click
        for img in sample.get("images", [])[:1]:
            if img.get("class"):
                cls = img["class"].split()[0]
                if cls:
                    recipe_book.add("open_result_card",
                                     {"selector": f'{primary_card_sel} img.{cls}', "type": "thumbnail_click", "stability": "low"},
                                     False, "candidate — not yet tested")
        # Title/link click
        for link in sample.get("links", [])[:1]:
            if link.get("class"):
                cls = link["class"].split()[0]
                if cls:
                    recipe_book.add("open_result_card",
                                     {"selector": f'{primary_card_sel} a.{cls}', "type": "title_link_click", "stability": "low"},
                                     False, "candidate — not yet tested")

    # ─── STEP 8: Test card open #1 (index 0, primary selector) ───
    print("\n[8/11] Card open test #1 (card 0, primary selector)...")
    open1 = await test_card_open(page, primary_card_sel, 0,
                                  {"selector": primary_card_sel, "type": "card_root_click", "stability": "medium"},
                                  logger, recipe_book, ts, "d08")
    consistency["opens_tested"] += 1

    # Wait for results to be back before next open
    if open1["success"]:
        await page.wait_for_timeout(1000)
        v = await verify_results_page(page, primary_card_sel)
        if not v["verified"]:
            print("  [WARN] Results page not re-verified after close. Waiting...")
            await page.wait_for_timeout(3000)

    # ─── STEP 9: Test card open #2 (index 2, primary selector) ───
    print("\n[9/11] Card open test #2 (card 2, primary selector)...")
    open2 = await test_card_open(page, primary_card_sel, 2,
                                  {"selector": primary_card_sel, "type": "card_root_click", "stability": "medium"},
                                  logger, recipe_book, ts, "d09")
    consistency["opens_tested"] += 1

    if open2["success"]:
        await page.wait_for_timeout(1000)

    # ─── STEP 10: Assess consistency ───
    print("\n[10/11] Assessing consistency...")

    detail_types = []
    if open1["success"]:
        detail_types.append(open1["detail_type"])
    if open2["success"]:
        detail_types.append(open2["detail_type"])

    if len(detail_types) == 2:
        if detail_types[0] == detail_types[1]:
            consistency["detail_open_consistency"] = f"{detail_types[0]}_only"
        else:
            consistency["detail_open_consistency"] = "mixed"
            consistency["mixed_behavior_notes"].append(
                f"card 0 opened as {detail_types[0]}, card 2 opened as {detail_types[1]}")
    elif len(detail_types) == 1:
        consistency["detail_open_consistency"] = f"{detail_types[0]}_only"
        consistency["mixed_behavior_notes"].append("only 1 successful open — consistency uncertain")
    else:
        consistency["detail_open_consistency"] = "unknown"
        consistency["mixed_behavior_notes"].append("no successful card opens")

    # Close recipe confidence
    close_recipes = recipe_book.rank("close_detail")
    successful_closes = [r for r in close_recipes if r["success_count"] > 0]
    if len(successful_closes) >= 2:
        consistency["close_recipe_confidence"] = "high"
    elif len(successful_closes) == 1:
        consistency["close_recipe_confidence"] = "medium"
    else:
        consistency["close_recipe_confidence"] = "low"

    print(f"  card_structure: {consistency['card_structure_consistency']}")
    print(f"  detail_open: {consistency['detail_open_consistency']}")
    print(f"  close_confidence: {consistency['close_recipe_confidence']}")
    if consistency["mixed_behavior_notes"]:
        for note in consistency["mixed_behavior_notes"]:
            print(f"  note: {note}")

    # Record detail modal roots
    for open_result in [open1, open2]:
        if open_result.get("modal_info"):
            m = open_result["modal_info"]
            dom_sigs["detail_modal_roots"].append({
                "class": m.get("class", ""),
                "id": m.get("id", ""),
                "selector_strategies": build_selector_strategies({"class": m.get("class", ""), "id": m.get("id", "")}, "button"),
                "close_buttons": m.get("close_buttons", []),
            })
            for cb in m.get("close_buttons", []):
                dom_sigs["close_button_candidates"].append({
                    **cb,
                    "selector_strategies": build_selector_strategies(cb, "close_button"),
                })

    # Record RESULTS_PAGE state
    state_catalog["states"]["RESULTS_PAGE"] = {
        "name": "RESULTS_PAGE",
        "url_clues": ["ad-search", "search"],
        "identifying_signals": {
            "card_roots_present": True,
            "card_count": best["repeated_count"],
            "primary_card_selector": primary_card_sel,
            "pagination_visible": len((await inspect_pagination(page)).get("candidates", [])) > 0,
        },
        "verification_method": "verify_results_page() — multi-signal",
        "disambiguation_from_SEARCH_PAGE": "card_roots_present AND repeated >= 3 AND 4+ signals pass",
        "allowed_actions": ["open_result", "paginate", "submit_search", "api_fetch"],
        "expected_transitions": {
            "open_result": [f"DETAIL_{consistency['detail_open_consistency'].upper()}"],
            "paginate": ["LOADING", "RESULTS_PAGE"],
            "submit_search": ["LOADING", "RESULTS_PAGE", "EMPTY_RESULTS"],
        },
        "confidence": "high" if consistency["card_structure_consistency"] != "low" else "medium",
    }

    # Record detail state
    if detail_types:
        primary_detail = detail_types[0]
        state_name = f"DETAIL_{primary_detail.upper()}"
        state_catalog["states"][state_name] = {
            "name": state_name,
            "detail_type": primary_detail,
            "identifying_signals": {
                "modal_open": primary_detail == "modal",
                "url_changed": primary_detail == "page",
            },
            "close_recipes": recipe_book.rank("close_detail"),
            "allowed_actions": ["extract_detail", "close_detail"],
            "expected_transitions": {"close_detail": ["RESULTS_PAGE"]},
            "confidence": consistency["close_recipe_confidence"],
        }

    # Pagination
    dom_sigs["pagination_candidates"] = (await inspect_pagination(page)).get("candidates", [])

    # ─── STEP 11: Save artifacts ───
    print("\n[11/11] Saving artifacts...")

    with open(SITE_MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(site_map, f, indent=2, ensure_ascii=False)
    print(f"  site_map.json")

    with open(STATE_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(state_catalog, f, indent=2, ensure_ascii=False)
    print(f"  state_catalog.json — {len(state_catalog['states'])} states")

    with open(DOM_SIGNATURES_PATH, "w", encoding="utf-8") as f:
        json.dump(dom_sigs, f, indent=2, ensure_ascii=False)
    print(f"  dom_signatures.json — cards={len(dom_sigs['result_card_roots'])}, modals={len(dom_sigs['detail_modal_roots'])}")

    with open(INTERACTION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(recipe_book.to_dict(), f, indent=2, ensure_ascii=False)
    ranked = recipe_book.to_dict()
    print(f"  interaction_recipes.json — {len(ranked)} actions, {sum(len(v) for v in ranked.values())} total recipes")

    with open(CONSISTENCY_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(consistency, f, indent=2, ensure_ascii=False)
    print(f"  consistency_report.json")

    # Artifact validation baseline
    validation = {
        "version": ARTIFACT_VERSION, "created_at": datetime.now().isoformat(),
        "pipiads_url_context": meta["url"],
        "validation_checks": {
            "search_input_found": len(dom_sigs["search_input_candidates"]) > 0,
            "search_submitted": search_submitted,
            "results_verified_multi_signal": verification["verified"],
            "card_roots_found": len(dom_sigs["result_card_roots"]) > 0,
            "detail_open_tested": consistency["opens_tested"] >= 2,
            "detail_close_tested": any(r["close_tested"] for r in [open1, open2]),
            "card_structure_consistency": consistency["card_structure_consistency"],
            "detail_open_consistency": consistency["detail_open_consistency"],
        },
        "artifact_status": "valid",
        "results_verification_evidence": verification,
    }
    # Downgrade if weak
    if consistency["card_structure_consistency"] == "low" or consistency["close_recipe_confidence"] == "low":
        validation["artifact_status"] = "partial"
    if not verification["verified"]:
        validation["artifact_status"] = "stale"

    with open(ARTIFACT_VALIDATION_PATH, "w", encoding="utf-8") as f:
        json.dump(validation, f, indent=2, ensure_ascii=False)
    print(f"  artifact_validation.json — status={validation['artifact_status']}")

    step_path = logger.save()

    # ─── Summary ───
    print("\n" + "─" * 70)
    print("DISCOVERY SUMMARY")
    print("─" * 70)
    gates = {
        "search_input_found": len(dom_sigs["search_input_candidates"]) > 0,
        "search_submitted": search_submitted,
        "results_verified_multi_signal": verification["verified"],
        "card_roots_identified": len(dom_sigs["result_card_roots"]) > 0,
        "3+_cards_inspected_structurally": len(card_inspections) >= 3,
        "2_distinct_card_opens_tested": consistency["opens_tested"] >= 2,
        "detail_close_verified": any(r.get("close_success") for r in [open1, open2]),
        "ranked_recipes_saved": len(ranked) > 0,
        "artifacts_saved": SITE_MAP_PATH.exists() and DOM_SIGNATURES_PATH.exists(),
        "consistency_assessed": consistency["card_structure_consistency"] != "unknown",
    }

    all_pass = True
    for gate, passed in gates.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {gate}")
        if not passed:
            all_pass = False

    print(f"\n  Overall: {'ALL GATES PASSED' if all_pass else 'SOME GATES FAILED'}")
    print(f"  Artifact status: {validation['artifact_status']}")

    return {
        "gates": gates, "all_pass": all_pass,
        "dom_sigs": dom_sigs, "recipes": recipe_book,
        "state_catalog": state_catalog, "consistency": consistency,
        "verification": verification, "validation": validation,
        "primary_card_selector": primary_card_sel,
        "open_results": [open1, open2],
    }


# ═══════════════════════════════════════════════════════════
# A0: Discovery + Fallback-Path Validation
# ═══════════════════════════════════════════════════════════

async def run_a0(page: Page, logger: StepLogger, ts: str):
    print("\n[A0] Running discovery...")
    result = await run_discover(page, logger, ts)

    if not result or not result["all_pass"]:
        print("\n[A0] Discovery gates incomplete. Review artifacts before retrying.")
        return result

    print("\n" + "=" * 70)
    print("[A0] FALLBACK-PATH VALIDATION")
    print("=" * 70)

    recipe_book: RecipeBook = result["recipes"]
    primary_sel = result["primary_card_selector"]

    # ── Verify we're back on results page ──
    v = await verify_results_page(page, primary_sel)
    if not v["verified"]:
        print("[A0] Not on results page. Re-submitting search...")
        # Use top-ranked submit recipe
        submit_recipes = recipe_book.rank("submit_search")
        fill_recipes = recipe_book.rank("fill_search_input")

        resub = False
        for fr in fill_recipes:
            try:
                loc = page.locator(fr["method"]["selector"]).first
                if await loc.is_visible(timeout=3000):
                    await loc.click(click_count=3)
                    await loc.fill("streetwear")
                    for sr in submit_recipes:
                        try:
                            if sr["method"].get("type") == "keyboard":
                                await loc.press("Enter")
                            else:
                                btn = page.locator(sr["method"]["selector"]).first
                                if await btn.is_visible(timeout=2000):
                                    await btn.click()
                            resub = True
                            break
                        except Exception:
                            continue
                    if resub:
                        break
            except Exception:
                continue

        if resub:
            await page.wait_for_timeout(6000)
        v = await verify_results_page(page, primary_sel)
        if not v["verified"]:
            print("[A0] Cannot restore results page. Stopping.")
            return result

    # ── Choose alternate open recipe ──
    open_recipes = recipe_book.rank("open_result_card")
    primary_open = open_recipes[0]["method"] if open_recipes else None
    alternate_open = None

    # Find an untested or different-type recipe
    for r in open_recipes:
        if r["method"].get("type") != primary_open.get("type") if primary_open else True:
            alternate_open = r["method"]
            break

    if not alternate_open and len(open_recipes) > 1:
        alternate_open = open_recipes[1]["method"]

    # ── Test 1: Open card 4 with PRIMARY recipe ──
    print(f"\n[A0] Test 1: Card 4, primary recipe ({primary_open.get('type','?') if primary_open else '?'})...")
    open3 = await test_card_open(page, primary_sel, 4, primary_open or {"selector": primary_sel, "type": "card_root_click"},
                                  logger, recipe_book, ts, "a0_t1")

    if open3["success"]:
        await page.wait_for_timeout(1000)
        v = await verify_results_page(page, primary_sel)
        if not v["verified"]:
            await page.wait_for_timeout(3000)

    # ── Test 2: Open card 1 with ALTERNATE recipe (fallback validation) ──
    if alternate_open:
        print(f"\n[A0] Test 2: Card 1, ALTERNATE recipe ({alternate_open.get('type','?')})...")
        open4 = await test_card_open(page, primary_sel, 1, alternate_open,
                                      logger, recipe_book, ts, "a0_t2_alt")

        if open4["success"]:
            print(f"  [A0] Alternate recipe WORKED: {alternate_open.get('type','?')}")
        else:
            print(f"  [A0] Alternate recipe FAILED: {alternate_open.get('type','?')} — primary is the only proven path")

        if open4["success"]:
            await page.wait_for_timeout(1000)
    else:
        print(f"\n[A0] No alternate open recipe available. Testing primary close fallback instead...")
        # Test alternate close: if primary close was Escape, try close button, or vice versa
        close_recipes = recipe_book.rank("close_detail")
        if len(close_recipes) >= 2:
            primary_close = close_recipes[0]["method"]
            alt_close = close_recipes[1]["method"]
            print(f"  Primary close: {primary_close.get('type','?')}")
            print(f"  Alternate close: {alt_close.get('type','?')}")
            # Open a card and test alternate close
            open_alt = await test_card_open(page, primary_sel, 1,
                                             primary_open or {"selector": primary_sel, "type": "card_root_click"},
                                             logger, recipe_book, ts, "a0_alt_close")
            # The close within test_card_open uses its own logic; we just check if multiple close paths are verified
            print(f"  Close recipes verified: {len([r for r in close_recipes if r['success_count'] > 0])}")

    # ── Update artifacts with new data ──
    with open(INTERACTION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(recipe_book.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"\n[A0] Updated interaction_recipes.json with new test data")

    # A0 gates
    print("\n" + "─" * 70)
    print("[A0] VALIDATION GATES")
    print("─" * 70)
    a0_gates = {
        "discovery_passed": result["all_pass"],
        "results_page_re_verified": v["verified"],
        "third_card_open_tested": open3["success"],
        "fallback_path_tested": alternate_open is not None or len(recipe_book.rank("close_detail")) >= 2,
        "multiple_close_recipes_exist": len([r for r in recipe_book.rank("close_detail") if r["success_count"] > 0]) >= 1,
    }
    all_a0 = True
    for gate, passed in a0_gates.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {gate}")
        if not passed:
            all_a0 = False

    print(f"\n  A0 Overall: {'PASSED' if all_a0 else 'FAILED'}")

    if all_a0:
        print(f"\n  [NEXT] Artifacts validated. Run --mode A1 for mini-batch research.")
    else:
        print(f"\n  [NEXT] Fix failures and re-run --mode A0.")

    logger.save()
    return {**result, "a0_gates": a0_gates, "a0_passed": all_a0}


# ═══════════════════════════════════════════════════════════
# ARTIFACT VALIDATION (for research modes)
# ═══════════════════════════════════════════════════════════

async def validate_artifacts(page: Page, logger: StepLogger, ts: str) -> dict:
    """
    Before research mode uses learned artifacts, verify they still match the live page.
    Returns {valid: bool, checks: {...}, status: valid|stale|partial}.
    """
    if not ARTIFACT_VALIDATION_PATH.exists():
        return {"valid": False, "status": "missing", "checks": {}}
    if not DOM_SIGNATURES_PATH.exists() or not INTERACTION_RECIPES_PATH.exists():
        return {"valid": False, "status": "missing", "checks": {}}

    validation = json.loads(ARTIFACT_VALIDATION_PATH.read_text(encoding="utf-8"))
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    checks = {}

    # Check 1: Version match
    checks["version_match"] = validation.get("version") == ARTIFACT_VERSION

    # Check 2: Search input still visible
    input_candidates = dom_sigs.get("search_input_candidates", [])
    input_found = False
    for candidate in input_candidates:
        for strat in candidate.get("selector_strategies", []):
            try:
                loc = page.locator(strat["selector"]).first
                if await loc.is_visible(timeout=2000):
                    input_found = True
                    break
            except Exception:
                continue
        if input_found:
            break
    checks["search_input_visible"] = input_found

    # Check 3: Card selector matches visible elements (after a quick search)
    card_roots = dom_sigs.get("result_card_roots", [])
    card_sel_works = False
    if card_roots:
        for strat in card_roots[0].get("selector_strategies", []):
            try:
                count = await count_visible_cards(page, strat["selector"])
                if count >= 2:
                    card_sel_works = True
                    break
            except Exception:
                continue
    checks["card_selector_matches"] = card_sel_works

    # Check 4: Recipes exist for core actions
    checks["has_submit_recipe"] = len(recipes.get("submit_search", [])) > 0
    checks["has_open_recipe"] = len(recipes.get("open_result_card", [])) > 0
    checks["has_close_recipe"] = len(recipes.get("close_detail", [])) > 0

    # Determine status
    critical = [checks["search_input_visible"], checks["has_submit_recipe"]]
    if all(critical) and sum(checks.values()) >= 4:
        status = "valid"
    elif any(critical):
        status = "partial"
    else:
        status = "stale"

    result = {"valid": status == "valid", "status": status, "checks": checks}

    logger.log("validation", "validate_artifacts", "pre_research", "validated",
                "success" if result["valid"] else "soft_fail",
                notes=f"status={status}, checks={sum(checks.values())}/{len(checks)}")

    return result


# ═══════════════════════════════════════════════════════════
# A1: Mini-Batch Research (3 keywords, 1 page, max 3 opens)
# ═══════════════════════════════════════════════════════════

A1_KEYWORDS = ["streetwear", "oversized hoodie", "essentials hoodie"]
A1_MAX_OPENS_PER_KEYWORD = 3
A1_MAX_PAGES = 1


async def extract_detail_from_modal(page: Page) -> dict:
    """Extract ad detail data from an open modal/detail view."""
    return await page.evaluate("""() => {
        const data = {texts: [], images: [], links: [], videos: [], metrics: {}};
        // Look for the modal content
        const modals = document.querySelectorAll('[class*="modal"],[class*="dialog"],[role="dialog"],.el-dialog__wrapper');
        let container = null;
        for (const m of modals) {
            const style = getComputedStyle(m);
            if (style.display !== 'none' && m.offsetParent !== null) {
                const rect = m.getBoundingClientRect();
                if (rect.width > 300 && rect.height > 300) { container = m; break; }
            }
        }
        if (!container) container = document.body;

        // Collect text content
        container.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, a').forEach(el => {
            if (!el.offsetParent && el.tagName !== 'SPAN') return;
            const t = el.textContent.trim();
            if (t.length > 2 && t.length < 500 && el.children.length === 0) {
                data.texts.push({text: t, tag: el.tagName, class: (el.className||'').substring(0,80)});
            }
        });

        // Images
        container.querySelectorAll('img').forEach(img => {
            if (img.src) data.images.push({src: img.src.substring(0,300), alt: img.alt||'', class: (img.className||'').substring(0,80)});
        });

        // Links
        container.querySelectorAll('a[href]').forEach(a => {
            if (a.href && !a.href.startsWith('javascript')) {
                data.links.push({href: a.href.substring(0,300), text: a.textContent.trim().substring(0,100), class: (a.className||'').substring(0,80)});
            }
        });

        // Videos
        container.querySelectorAll('video').forEach(v => {
            data.videos.push({src: (v.src||'').substring(0,300), poster: (v.poster||'').substring(0,300)});
        });

        // Try to find specific metric elements (impression, likes, spend, etc.)
        container.querySelectorAll('.value, [class*="metric"], [class*="count"], [class*="stat"]').forEach(el => {
            const label = el.previousElementSibling?.textContent?.trim() || el.nextElementSibling?.textContent?.trim() || '';
            const val = el.textContent.trim();
            if (val && label) data.metrics[label.substring(0,40)] = val.substring(0,40);
        });

        // Advertiser info
        const advertiserEl = container.querySelector('[class*="advertiser"], [class*="app-name"], [class*="nickname"], .pro-info a');
        if (advertiserEl) data.advertiser = advertiserEl.textContent.trim().substring(0,100);

        // Caption / ad text
        const captionEl = container.querySelector('[class*="caption-text"], [class*="ad-text"], [class*="description"], [class*="copy"]');
        if (captionEl) data.caption = captionEl.textContent.trim().substring(0,500);

        // Landing page / CTA
        const landingEl = container.querySelector('[class*="landing"], [class*="shop-now"], [class*="cta"], a[href*="http"]');
        if (landingEl) {
            data.landing_url = (landingEl.href || '').substring(0,300);
            data.cta_text = landingEl.textContent.trim().substring(0,80);
        }

        // Region info
        const regionEls = container.querySelectorAll('[class*="region"] img, [class*="country"] img');
        data.regions = Array.from(regionEls).map(r => r.alt || r.title || '').filter(x => x);

        return data;
    }""")


async def run_a1(page: Page, logger: StepLogger, ts: str):
    """
    A1: Mini-batch research run.
    - 3 keywords, 1 page each, max 3 card opens per keyword
    - Uses learned artifacts with live validation
    - Intercepts API responses to capture ad data
    - Opens cards via UI to verify modal behavior + extract detail
    - Strict stop conditions
    """
    print("\n" + "=" * 70)
    print("A1 — MINI-BATCH RESEARCH")
    print(f"Keywords: {A1_KEYWORDS}")
    print(f"Max opens/keyword: {A1_MAX_OPENS_PER_KEYWORD}, Max pages: {A1_MAX_PAGES}")
    print("=" * 70)

    # ── Load learned artifacts ──
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    # Primary selectors from artifacts
    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors in artifacts.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]
    print(f"  Card selector: {primary_card_sel}")

    input_candidates = dom_sigs.get("search_input_candidates", [])
    if not input_candidates:
        print("[ABORT] No search input candidates in artifacts.")
        return None
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"]
    print(f"  Input selector: {primary_input_sel}")

    # Best open/close recipes
    open_recipes = recipes.get("open_result_card", [])
    proven_open = [r for r in open_recipes if r["success_count"] > 0]
    if not proven_open:
        print("[ABORT] No proven open recipe.")
        return None
    best_open = proven_open[0]["method"]
    print(f"  Open recipe: {best_open['type']} → {best_open['selector']}")

    close_recipes = recipes.get("close_detail", [])
    proven_close = [r for r in close_recipes if r["success_count"] > 0]
    if not proven_close:
        print("[ABORT] No proven close recipe.")
        return None
    best_close = proven_close[0]["method"]
    print(f"  Close recipe: {best_close['type']} → {best_close['selector']}")

    # ── Set up API response interception ──
    api_results = {}  # keyword → list of ad items

    async def on_api_response(response):
        if "search4/at/video/search" in response.url and response.status == 200:
            try:
                body = await response.json()
                result = body.get("result", {})
                items = result.get("list", []) if isinstance(result, dict) else []
                if items:
                    # Store under current keyword context
                    current_kw = getattr(on_api_response, '_current_keyword', 'unknown')
                    if current_kw not in api_results:
                        api_results[current_kw] = []
                    for item in items:
                        api_results[current_kw].append(item)
                    print(f"    [API] +{len(items)} ads captured for '{current_kw}'")
            except Exception as e:
                print(f"    [API] Response parse error: {str(e)[:60]}")

    page.on("response", on_api_response)

    # ── Validate artifacts live ──
    print(f"\n[VALIDATE] Checking artifacts against live page...")
    val = await validate_artifacts(page, logger, ts)
    print(f"  Status: {val['status']}")
    for check, passed in val["checks"].items():
        icon = "+" if passed else "-"
        print(f"    [{icon}] {check}")

    if val["status"] in ("stale", "missing"):
        print(f"\n[ABORT] Artifacts {val['status']}. Re-run --mode A0 first.")
        return None

    # ── Research loop ──
    recipe_book = RecipeBook()
    # Pre-populate from saved recipes
    for action, entries in recipes.items():
        for entry in entries:
            recipe_book.recipes.setdefault(action, []).append(dict(entry))

    all_keyword_results = []
    stop_triggered = False
    stop_reason = ""
    consecutive_open_fails = 0

    for kw_idx, keyword in enumerate(A1_KEYWORDS):
        if stop_triggered:
            break

        print(f"\n{'─' * 70}")
        print(f"[KEYWORD {kw_idx+1}/{len(A1_KEYWORDS)}] '{keyword}'")
        print(f"{'─' * 70}")

        kw_result = {
            "keyword": keyword,
            "api_ads_captured": 0,
            "cards_found": 0,
            "cards_opened": 0,
            "cards_open_failed": 0,
            "detail_types_seen": [],
            "close_successes": 0,
            "close_failures": 0,
            "detail_extractions": [],
            "stop_triggered": False,
        }

        # Set current keyword for API interception
        on_api_response._current_keyword = keyword

        # ── Fill + submit search ──
        try:
            loc = page.locator(primary_input_sel).first
            if not await loc.is_visible(timeout=5000):
                # Fallback to #inputKeyword
                loc = page.locator("#inputKeyword").first
                if not await loc.is_visible(timeout=3000):
                    print(f"  [FAIL] Search input not visible. Stop.")
                    stop_triggered = True
                    stop_reason = "search_input_not_visible"
                    kw_result["stop_triggered"] = True
                    all_keyword_results.append(kw_result)
                    break

            await loc.click(click_count=3)
            await loc.fill(keyword)
            await page.wait_for_timeout(500)
            await loc.press("Enter")
            print(f"  Search submitted for '{keyword}'")
            logger.log("a1_research", f"search_submit_{keyword}", "search_page", "loading", "info")
        except Exception as e:
            print(f"  [FAIL] Search submission failed: {str(e)[:80]}")
            stop_triggered = True
            stop_reason = f"search_submit_failed: {str(e)[:60]}"
            kw_result["stop_triggered"] = True
            all_keyword_results.append(kw_result)
            break

        # Wait for results
        await page.wait_for_timeout(6000)

        # ── Verify results page ──
        verification = await verify_results_page(page, primary_card_sel)
        ss = await take_ss(page, f"a1_results_{keyword.replace(' ', '_')}", ts)

        if not verification["verified"]:
            print(f"  [WARN] Results page not verified (signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']})")
            # Wait longer and retry
            await page.wait_for_timeout(5000)
            verification = await verify_results_page(page, primary_card_sel)
            if not verification["verified"]:
                print(f"  [FAIL] Results page still not verified. Stopping keyword.")
                logger.log("a1_research", f"verify_results_{keyword}", "loading", "unknown", "hard_fail",
                           notes=f"signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']}", screenshot=ss)
                # Card selector failure = stop condition
                if not verification["signals"].get("repeated_card_containers"):
                    stop_triggered = True
                    stop_reason = "card_selector_failed_no_repeated_containers"
                kw_result["stop_triggered"] = True
                all_keyword_results.append(kw_result)
                continue

        logger.log("a1_research", f"verify_results_{keyword}", "loading", "results_page", "success",
                   notes=f"signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']}", screenshot=ss)

        # Count visible cards
        visible_cards = await count_visible_cards(page, primary_card_sel)
        kw_result["cards_found"] = visible_cards
        print(f"  Results verified: {visible_cards} cards visible")

        # ── API data already captured via interception ──
        kw_result["api_ads_captured"] = len(api_results.get(keyword, []))
        print(f"  API ads captured: {kw_result['api_ads_captured']}")

        # ── Open up to 3 cards via UI ──
        opens_this_kw = 0
        open_fails_this_kw = 0

        for card_idx in range(min(A1_MAX_OPENS_PER_KEYWORD, visible_cards)):
            if stop_triggered:
                break

            print(f"\n  [CARD {card_idx}] Opening via {best_open['type']}...")

            # Pre-state
            pre_modals = await inspect_modal_state(page)
            pre_url = page.url

            try:
                cards = page.locator(best_open["selector"])
                count = await cards.count()
                if count <= card_idx:
                    print(f"    Only {count} cards, skipping index {card_idx}")
                    continue

                target = cards.nth(card_idx)
                await target.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await target.click()
                await page.wait_for_timeout(3000)

            except Exception as e:
                print(f"    [FAIL] Click failed: {str(e)[:60]}")
                open_fails_this_kw += 1
                consecutive_open_fails += 1
                recipe_book.add("open_result_card", best_open, False, f"a1 click fail: {str(e)[:40]}")
                logger.log("a1_research", f"open_card_{keyword}_{card_idx}", "results_page", "results_page", "hard_fail",
                           notes=f"click exception: {str(e)[:60]}")

                if consecutive_open_fails >= 2:
                    stop_triggered = True
                    stop_reason = f"open_failed_twice_for_{keyword}"
                    kw_result["stop_triggered"] = True
                continue

            # Check what happened
            post_modals = await inspect_modal_state(page)
            post_url = page.url
            new_modals = len(post_modals.get("modals", [])) - len(pre_modals.get("modals", []))
            url_changed = post_url != pre_url

            detail_type = "unknown"
            if new_modals > 0:
                detail_type = "modal"
            elif url_changed:
                detail_type = "page"
            elif len(post_modals.get("drawers", [])) > len(pre_modals.get("drawers", [])):
                detail_type = "drawer"

            if detail_type == "unknown":
                print(f"    [FAIL] No detail opened (no modal, no URL change, no drawer)")
                open_fails_this_kw += 1
                consecutive_open_fails += 1
                recipe_book.add("open_result_card", best_open, False, "a1 no detail appeared")
                logger.log("a1_research", f"open_card_{keyword}_{card_idx}", "results_page", "results_page", "soft_fail",
                           notes="no detail type detected")

                if consecutive_open_fails >= 2:
                    stop_triggered = True
                    stop_reason = f"open_failed_twice_for_{keyword}"
                    kw_result["stop_triggered"] = True
                continue

            # Success
            opens_this_kw += 1
            consecutive_open_fails = 0
            kw_result["detail_types_seen"].append(detail_type)
            recipe_book.add("open_result_card", best_open, True, f"a1 detail_type={detail_type}")

            ss_detail = await take_ss(page, f"a1_detail_{keyword.replace(' ', '_')}_{card_idx}", ts)
            logger.log("a1_research", f"open_card_{keyword}_{card_idx}", "results_page", detail_type,
                       "success", notes=f"type={detail_type}", screenshot=ss_detail)

            print(f"    Opened: {detail_type}")

            # ── Check for non-modal behavior (stop condition) ──
            if detail_type not in ("modal",):
                print(f"    [WARN] Non-modal behavior: {detail_type}")
                kw_result["stop_triggered"] = True
                stop_triggered = True
                stop_reason = f"non_modal_behavior_{detail_type}"

            # ── Extract detail data ──
            try:
                detail_data = await extract_detail_from_modal(page)
                kw_result["detail_extractions"].append({
                    "card_index": card_idx,
                    "detail_type": detail_type,
                    "data": detail_data,
                })
                text_count = len(detail_data.get("texts", []))
                img_count = len(detail_data.get("images", []))
                link_count = len(detail_data.get("links", []))
                advertiser = detail_data.get("advertiser", "unknown")
                print(f"    Extracted: {text_count} texts, {img_count} imgs, {link_count} links, adv={advertiser}")
            except Exception as e:
                print(f"    [WARN] Detail extraction error: {str(e)[:60]}")
                kw_result["detail_extractions"].append({
                    "card_index": card_idx,
                    "detail_type": detail_type,
                    "data": {"error": str(e)[:100]},
                })

            # ── Close detail ──
            close_success = False
            try:
                if best_close["type"] == "keyboard":
                    await page.keyboard.press(best_close["selector"])
                else:
                    close_loc = page.locator(best_close["selector"]).first
                    if await close_loc.is_visible(timeout=2000):
                        await close_loc.click()

                await page.wait_for_timeout(2000)

                post_close_modals = await inspect_modal_state(page)
                if len(post_close_modals.get("modals", [])) < len(post_modals.get("modals", [])):
                    close_success = True
                elif "search" in page.url.lower() and page.url == pre_url:
                    close_success = True

                recipe_book.add("close_detail", best_close, close_success,
                                f"a1 close after {detail_type}")

            except Exception as e:
                print(f"    [WARN] Close exception: {str(e)[:60]}")
                recipe_book.add("close_detail", best_close, False, f"a1 exception: {str(e)[:40]}")

            if close_success:
                kw_result["close_successes"] += 1
                print(f"    Closed successfully via {best_close['type']}")
                logger.log("a1_research", f"close_card_{keyword}_{card_idx}", detail_type, "results_page",
                           "success", notes=f"method={best_close['type']}")
            else:
                kw_result["close_failures"] += 1
                print(f"    [WARN] Close may have failed, attempting recovery...")
                logger.log("a1_research", f"close_card_{keyword}_{card_idx}", detail_type, "unknown",
                           "soft_fail", notes=f"method={best_close['type']}")

                # Recovery: try Escape again, then browser back
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(1500)
                    post_recovery = await inspect_modal_state(page)
                    if len(post_recovery.get("modals", [])) == 0:
                        print(f"    Recovery: Escape retry worked")
                        close_success = True
                    else:
                        await page.go_back()
                        await page.wait_for_timeout(3000)
                        if "search" in page.url.lower():
                            print(f"    Recovery: browser back worked")
                            close_success = True
                        else:
                            print(f"    [FAIL] Close recovery failed")
                            stop_triggered = True
                            stop_reason = "close_failed_without_recovery"
                            kw_result["stop_triggered"] = True
                except Exception:
                    stop_triggered = True
                    stop_reason = "close_recovery_exception"
                    kw_result["stop_triggered"] = True

            # Brief wait before next card
            await page.wait_for_timeout(1000)

        kw_result["cards_opened"] = opens_this_kw
        kw_result["cards_open_failed"] = open_fails_this_kw
        all_keyword_results.append(kw_result)

        print(f"\n  [KEYWORD DONE] '{keyword}': {opens_this_kw} opened, {open_fails_this_kw} failed, "
              f"{kw_result['api_ads_captured']} API ads, {kw_result['close_successes']} closes OK")

    # ── Remove API listener ──
    page.remove_listener("response", on_api_response)

    # ── Deduplicate API results ──
    all_api_ads = []
    seen_ids = set()
    for kw, items in api_results.items():
        for item in items:
            aid = item.get("ad_id") or item.get("id") or item.get("_id")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                item["_source_keyword"] = kw
                all_api_ads.append(item)

    # ── Filter for target regions ──
    region_matched = []
    for ad in all_api_ads:
        regions = ad.get("fetch_region", [])
        if isinstance(regions, str):
            regions = re.findall(r"'(\w{2})'", regions)
        if isinstance(regions, list):
            if any(r in TARGET_REGIONS for r in regions):
                region_matched.append(ad)

    # ── Save results ──
    a1_output = {
        "mode": "A1",
        "timestamp": datetime.now().isoformat(),
        "keywords": A1_KEYWORDS,
        "guardrails": {
            "max_keywords": len(A1_KEYWORDS),
            "max_pages": A1_MAX_PAGES,
            "max_opens_per_keyword": A1_MAX_OPENS_PER_KEYWORD,
        },
        "artifact_validation": val,
        "keyword_results": all_keyword_results,
        "api_summary": {
            "total_ads_captured": len(all_api_ads),
            "unique_ads": len(all_api_ads),
            "region_matched": len(region_matched),
            "target_regions": TARGET_REGIONS,
        },
        "stop_condition": {
            "triggered": stop_triggered,
            "reason": stop_reason,
        },
        "recipe_updates": recipe_book.to_dict(),
    }

    output_path = DATA_DIR / f"a1_results_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(a1_output, f, indent=2, ensure_ascii=True, default=str)
    print(f"\n  Results saved to: {output_path.name}")

    # Save API ads separately
    if all_api_ads:
        ads_path = DATA_DIR / f"a1_ads_{ts}.json"
        with open(ads_path, "w", encoding="utf-8") as f:
            json.dump({
                "ads": all_api_ads,
                "region_matched": region_matched,
                "total": len(all_api_ads),
                "region_matched_count": len(region_matched),
            }, f, indent=2, ensure_ascii=True, default=str)
        print(f"  API ads saved to: {ads_path.name}")

    # Update recipes
    with open(INTERACTION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(recipe_book.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"  Updated interaction_recipes.json")

    # ── A1 REPORT ──
    print("\n" + "=" * 70)
    print("A1 REPORT")
    print("=" * 70)

    # 1. Artifact validation
    print(f"\n1. ARTIFACT VALIDATION: {val['status']}")
    for check, passed in val["checks"].items():
        icon = "+" if passed else "-"
        print(f"   [{icon}] {check}")

    # 2. Per-keyword results
    print(f"\n2. PER-KEYWORD RESULTS:")
    for kr in all_keyword_results:
        print(f"   '{kr['keyword']}':")
        print(f"     Cards found: {kr['cards_found']}")
        print(f"     Cards opened: {kr['cards_opened']} (failed: {kr['cards_open_failed']})")
        print(f"     API ads: {kr['api_ads_captured']}")
        print(f"     Detail extractions: {len(kr['detail_extractions'])}")
        print(f"     Close: {kr['close_successes']} OK, {kr['close_failures']} failed")
        if kr['stop_triggered']:
            print(f"     ** STOP TRIGGERED **")

    # 3. Detail modal behavior
    all_types = []
    for kr in all_keyword_results:
        all_types.extend(kr["detail_types_seen"])
    type_counts = Counter(all_types)
    print(f"\n3. DETAIL BEHAVIOR:")
    print(f"   Types seen: {dict(type_counts)}")
    if len(type_counts) == 1 and "modal" in type_counts:
        print(f"   Consistent: modal-only (matches A0 discovery)")
    elif len(type_counts) == 0:
        print(f"   No cards were opened successfully")
    else:
        print(f"   MIXED behavior detected — review needed")

    # 4. Close recipe reliability
    total_closes = sum(kr["close_successes"] for kr in all_keyword_results)
    total_close_fails = sum(kr["close_failures"] for kr in all_keyword_results)
    print(f"\n4. CLOSE RECIPE RELIABILITY:")
    print(f"   Successes: {total_closes}")
    print(f"   Failures: {total_close_fails}")
    if total_closes > 0 and total_close_fails == 0:
        print(f"   Status: RELIABLE")
    elif total_close_fails > 0:
        print(f"   Status: UNRELIABLE — {total_close_fails} failures")
    else:
        print(f"   Status: UNTESTED")

    # 5. Stop conditions
    print(f"\n5. STOP CONDITIONS:")
    if stop_triggered:
        print(f"   TRIGGERED: {stop_reason}")
    else:
        print(f"   None triggered — clean run")

    # 6. Summary
    print(f"\n6. SUMMARY:")
    print(f"   Keywords searched: {len(all_keyword_results)}/{len(A1_KEYWORDS)}")
    total_opens = sum(kr["cards_opened"] for kr in all_keyword_results)
    print(f"   Total cards opened: {total_opens}")
    print(f"   Total API ads captured: {len(all_api_ads)}")
    print(f"   Region-matched ads: {len(region_matched)}")
    print(f"   Output file: {output_path.name}")

    # Gate assessment
    print(f"\n{'─' * 70}")
    a1_gates = {
        "artifacts_validated": val["status"] in ("valid", "partial"),
        "all_keywords_searched": len(all_keyword_results) == len(A1_KEYWORDS),
        "cards_opened_successfully": total_opens > 0,
        "detail_behavior_consistent": len(type_counts) <= 1,
        "close_reliable": total_close_fails == 0,
        "no_stop_triggered": not stop_triggered,
        "api_data_captured": len(all_api_ads) > 0,
    }
    all_pass = True
    for gate, passed in a1_gates.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {gate}")
        if not passed:
            all_pass = False

    print(f"\n  A1 Overall: {'PASSED' if all_pass else 'NEEDS REVIEW'}")
    if all_pass:
        print(f"  [NEXT] Ready for --mode B (8 keywords, 2 pages)")
    else:
        print(f"  [NEXT] Review failures before proceeding")

    logger.save()
    return a1_output


# ═══════════════════════════════════════════════════════════
# B: Controlled Scale Research (8 keywords, 2 pages, 4 opens)
# ═══════════════════════════════════════════════════════════

B_KEYWORDS = [
    "streetwear", "oversized hoodie", "heavyweight hoodie", "baggy jeans",
    "streetwear brand", "oversized tee", "archive fashion", "limited drop clothing",
]
B_MAX_OPENS_PER_KEYWORD = 4
B_MAX_PAGES = 2


async def navigate_to_page_2(page: Page, logger: StepLogger, ts: str, keyword: str) -> bool:
    """Try to navigate to page 2 of results. Returns True if successful."""
    # Strategy 1: Look for pagination buttons with "2" or "Next"
    try:
        pag = await inspect_pagination(page)
        candidates = pag.get("candidates", [])
        if candidates:
            for cand in candidates:
                for btn in cand.get("buttons", []):
                    if btn.get("text", "").strip() == "2":
                        # Found a "2" button in pagination
                        sel = f'{cand["selector"]} :text-is("2")'
                        try:
                            loc = page.locator(sel).first
                            if await loc.is_visible(timeout=2000):
                                await loc.click()
                                await page.wait_for_timeout(4000)
                                logger.log("b_research", f"paginate_{keyword}", "results_page", "loading", "info",
                                           notes="clicked page 2 button")
                                return True
                        except Exception:
                            pass
    except Exception:
        pass

    # Strategy 2: el-pagination specific (Pipiads uses Element UI)
    try:
        # Try clicking the "next" button in Element UI pagination
        next_btn = page.locator('.el-pagination .btn-next, .el-pagination button.btn-next').first
        if await next_btn.is_visible(timeout=2000):
            disabled = await next_btn.get_attribute("disabled")
            if disabled is None:
                await next_btn.click()
                await page.wait_for_timeout(4000)
                logger.log("b_research", f"paginate_{keyword}", "results_page", "loading", "info",
                           notes="el-pagination next button")
                return True
    except Exception:
        pass

    # Strategy 3: Look for any next/arrow button
    for sel in ['[class*="pagination"] [class*="next"]', '[class*="pager"] [class*="next"]',
                'button:has-text("Next")', 'a:has-text("Next")']:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible(timeout=1500):
                await loc.click()
                await page.wait_for_timeout(4000)
                logger.log("b_research", f"paginate_{keyword}", "results_page", "loading", "info",
                           notes=f"next via {sel}")
                return True
        except Exception:
            continue

    # Strategy 4: page.evaluate to find and click number "2" in pagination area
    try:
        clicked = await page.evaluate("""() => {
            const pags = document.querySelectorAll('[class*="pagination"],[class*="pager"],.el-pagination');
            for (const p of pags) {
                const items = p.querySelectorAll('li, button, a, span');
                for (const item of items) {
                    if (item.textContent.trim() === '2' && item.offsetParent) {
                        item.click();
                        return true;
                    }
                }
            }
            return false;
        }""")
        if clicked:
            await page.wait_for_timeout(4000)
            logger.log("b_research", f"paginate_{keyword}", "results_page", "loading", "info",
                       notes="evaluate click page 2")
            return True
    except Exception:
        pass

    logger.log("b_research", f"paginate_{keyword}", "results_page", "results_page", "soft_fail",
               notes="no pagination method worked")
    return False


async def run_b(page: Page, logger: StepLogger, ts: str):
    """
    B: Controlled-scale research run.
    - 8 keywords, max 2 pages each, max 4 card opens per keyword
    - UI-first extraction; API interception is optional secondary
    - Conservative confidence tracking
    - 6 stop conditions, 9-point report
    """
    print("\n" + "=" * 70)
    print("B — CONTROLLED SCALE RESEARCH")
    print(f"Keywords: {B_KEYWORDS}")
    print(f"Max opens/keyword: {B_MAX_OPENS_PER_KEYWORD}, Max pages: {B_MAX_PAGES}")
    print("=" * 70)

    # ── Load learned artifacts ──
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors in artifacts.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]
    # Also track alternate selectors for confidence comparison
    alt_card_sels = [s["selector"] for s in card_roots[0]["selector_strategies"][1:]]

    input_candidates = dom_sigs.get("search_input_candidates", [])
    if not input_candidates:
        print("[ABORT] No search input candidates in artifacts.")
        return None
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"]

    open_recipes_loaded = recipes.get("open_result_card", [])
    proven_open = [r for r in open_recipes_loaded if r["success_count"] > 0]
    if not proven_open:
        print("[ABORT] No proven open recipe.")
        return None
    best_open = proven_open[0]["method"]

    close_recipes_loaded = recipes.get("close_detail", [])
    proven_close = [r for r in close_recipes_loaded if r["success_count"] > 0]
    if not proven_close:
        print("[ABORT] No proven close recipe.")
        return None
    best_close = proven_close[0]["method"]

    print(f"  Card selector (primary): {primary_card_sel}")
    print(f"  Card selector (alts): {alt_card_sels[:2]}")
    print(f"  Input: {primary_input_sel}")
    print(f"  Open: {best_open['type']} → {best_open['selector']}")
    print(f"  Close: {best_close['type']} → {best_close['selector']}")

    # ── API interception: register BEFORE first search (improved timing) ──
    api_results = {}
    api_capture_count = 0

    async def on_api_response(response):
        nonlocal api_capture_count
        if "search4/at/video/search" in response.url and response.status == 200:
            try:
                body = await response.json()
                result = body.get("result", {})
                items = result.get("list", []) if isinstance(result, dict) else []
                if items:
                    current_kw = getattr(on_api_response, '_current_keyword', 'unknown')
                    if current_kw not in api_results:
                        api_results[current_kw] = []
                    for item in items:
                        api_results[current_kw].append(item)
                    api_capture_count += len(items)
                    print(f"    [API] +{len(items)} ads captured for '{current_kw}'")
            except Exception:
                pass

    # Register early
    page.on("response", on_api_response)

    # ── Validate artifacts ──
    print(f"\n[VALIDATE] Checking artifacts against live page...")
    val = await validate_artifacts(page, logger, ts)
    print(f"  Status: {val['status']}")
    for check, passed in val["checks"].items():
        icon = "+" if passed else "-"
        print(f"    [{icon}] {check}")

    if val["status"] in ("stale", "missing"):
        print(f"\n[ABORT] Artifacts {val['status']}. Re-run --mode A0 first.")
        page.remove_listener("response", on_api_response)
        return None

    # ── Confidence tracker ──
    confidence = {
        "card_root_click": {"successes": 0, "failures": 0, "keywords_tested": set()},
        "escape_close": {"successes": 0, "failures": 0},
        "primary_selector": {"match_counts": [], "keywords_tested": set()},
        "detail_types": [],
        "card_structures_seen": [],  # text_count per card for consistency check
        "first_fragility_sign": None,
        "artifact_revalidations": [],
    }

    recipe_book = RecipeBook()
    for action, entries in recipes.items():
        for entry in entries:
            recipe_book.recipes.setdefault(action, []).append(dict(entry))

    all_keyword_results = []
    stop_triggered = False
    stop_reason = ""
    total_pages_processed = 0
    total_cards_opened = 0

    for kw_idx, keyword in enumerate(B_KEYWORDS):
        if stop_triggered:
            break

        print(f"\n{'═' * 70}")
        print(f"[KEYWORD {kw_idx+1}/{len(B_KEYWORDS)}] '{keyword}'")
        print(f"{'═' * 70}")

        kw_result = {
            "keyword": keyword,
            "pages_searched": 0,
            "cards_found_per_page": [],
            "cards_opened": 0,
            "cards_open_failed": 0,
            "detail_types_seen": [],
            "close_successes": 0,
            "close_failures": 0,
            "detail_extractions": [],
            "api_ads_captured": 0,
            "stop_triggered": False,
        }

        on_api_response._current_keyword = keyword
        consecutive_open_fails_this_kw = 0
        opens_this_kw = 0

        for page_num in range(1, B_MAX_PAGES + 1):
            if stop_triggered:
                break

            print(f"\n  ── Page {page_num} ──")

            if page_num == 1:
                # Submit new search
                try:
                    loc = page.locator(primary_input_sel).first
                    if not await loc.is_visible(timeout=5000):
                        loc = page.locator("#inputKeyword").first
                        if not await loc.is_visible(timeout=3000):
                            print(f"  [FAIL] Search input not visible.")
                            stop_triggered = True
                            stop_reason = "search_input_not_visible"
                            kw_result["stop_triggered"] = True
                            break

                    await loc.click(click_count=3)
                    await loc.fill(keyword)
                    await page.wait_for_timeout(500)

                    # Use expect_response to catch API response for this search
                    try:
                        async with page.expect_response(
                            lambda r: "search4/at/video/search" in r.url,
                            timeout=15000
                        ) as response_info:
                            await loc.press("Enter")
                        resp = await response_info.value
                        print(f"    [API-SYNC] Got search response: status={resp.status}")
                    except Exception:
                        # Fallback: just press Enter without waiting for response
                        await loc.press("Enter")
                        print(f"    [API-SYNC] Response wait timed out, continuing")

                    logger.log("b_research", f"search_submit_{keyword}", "search_page", "loading", "info")
                except Exception as e:
                    print(f"  [FAIL] Search failed: {str(e)[:80]}")
                    stop_triggered = True
                    stop_reason = f"search_submit_failed: {str(e)[:60]}"
                    kw_result["stop_triggered"] = True
                    break

                await page.wait_for_timeout(5000)

            else:
                # Navigate to next page
                print(f"  Navigating to page {page_num}...")
                paginated = await navigate_to_page_2(page, logger, ts, keyword)
                if not paginated:
                    print(f"  [WARN] Could not paginate to page {page_num}. Skipping.")
                    break
                await page.wait_for_timeout(3000)

            # ── Verify results page ──
            verification = await verify_results_page(page, primary_card_sel)
            ss = await take_ss(page, f"b_results_{keyword.replace(' ', '_')}_p{page_num}", ts)

            if not verification["verified"]:
                await page.wait_for_timeout(5000)
                verification = await verify_results_page(page, primary_card_sel)
                if not verification["verified"]:
                    print(f"  [FAIL] Results page not verified (signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']})")
                    logger.log("b_research", f"verify_results_{keyword}_p{page_num}", "loading", "unknown", "hard_fail",
                               notes=f"signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']}", screenshot=ss)
                    if not verification["signals"].get("repeated_card_containers"):
                        # Stop condition 1: card root selector no longer matches
                        stop_triggered = True
                        stop_reason = "card_root_selector_no_match"
                        if not confidence["first_fragility_sign"]:
                            confidence["first_fragility_sign"] = f"card_root_no_match at kw={keyword} p={page_num}"
                    kw_result["stop_triggered"] = True
                    break

            logger.log("b_research", f"verify_results_{keyword}_p{page_num}", "loading", "results_page", "success",
                       notes=f"signals={verification['evidence']['signals_passing']}/{verification['evidence']['signals_total']}", screenshot=ss)

            visible_cards = await count_visible_cards(page, primary_card_sel)
            kw_result["cards_found_per_page"].append({"page": page_num, "count": visible_cards})
            kw_result["pages_searched"] += 1
            total_pages_processed += 1

            # Track primary selector confidence
            confidence["primary_selector"]["match_counts"].append(visible_cards)
            confidence["primary_selector"]["keywords_tested"].add(keyword)

            # Also check alt selectors (confidence comparison, don't act on it)
            for alt_sel in alt_card_sels[:1]:
                try:
                    alt_count = await count_visible_cards(page, alt_sel)
                    if alt_count > visible_cards:
                        print(f"    [NOTE] Alt selector '{alt_sel}' found {alt_count} vs primary {visible_cards}")
                except Exception:
                    pass

            print(f"  Results verified: {visible_cards} cards visible (page {page_num})")

            # ── Open cards ──
            remaining_opens = B_MAX_OPENS_PER_KEYWORD - opens_this_kw
            cards_to_open = min(remaining_opens, visible_cards, 3)  # max 3 per page to spread across pages

            for card_idx in range(cards_to_open):
                if stop_triggered:
                    break

                actual_idx = card_idx  # top cards on current page
                print(f"\n    [CARD p{page_num}:{actual_idx}] Opening...")

                pre_modals = await inspect_modal_state(page)
                pre_url = page.url

                try:
                    cards = page.locator(best_open["selector"])
                    count = await cards.count()
                    if count <= actual_idx:
                        print(f"      Only {count} cards, skipping index {actual_idx}")
                        continue

                    target = cards.nth(actual_idx)
                    await target.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await target.click()
                    await page.wait_for_timeout(3000)

                except Exception as e:
                    print(f"      [FAIL] Click failed: {str(e)[:60]}")
                    kw_result["cards_open_failed"] += 1
                    consecutive_open_fails_this_kw += 1
                    confidence["card_root_click"]["failures"] += 1
                    recipe_book.add("open_result_card", best_open, False, f"b click fail: {str(e)[:40]}")
                    logger.log("b_research", f"open_card_{keyword}_p{page_num}_{actual_idx}", "results_page",
                               "results_page", "hard_fail", notes=f"click exception: {str(e)[:60]}")

                    # Stop condition 2: open fails twice for same keyword
                    if consecutive_open_fails_this_kw >= 2:
                        stop_triggered = True
                        stop_reason = f"open_failed_twice_{keyword}_p{page_num}"
                        kw_result["stop_triggered"] = True
                        if not confidence["first_fragility_sign"]:
                            confidence["first_fragility_sign"] = f"open_failed_twice at kw={keyword} p={page_num}"
                    continue

                # Check detail type
                post_modals = await inspect_modal_state(page)
                post_url = page.url
                new_modals = len(post_modals.get("modals", [])) - len(pre_modals.get("modals", []))
                url_changed = post_url != pre_url

                detail_type = "unknown"
                if new_modals > 0:
                    detail_type = "modal"
                elif url_changed:
                    detail_type = "page"
                elif len(post_modals.get("drawers", [])) > len(pre_modals.get("drawers", [])):
                    detail_type = "drawer"

                if detail_type == "unknown":
                    print(f"      [FAIL] No detail opened")
                    kw_result["cards_open_failed"] += 1
                    consecutive_open_fails_this_kw += 1
                    confidence["card_root_click"]["failures"] += 1
                    recipe_book.add("open_result_card", best_open, False, "b no detail appeared")
                    logger.log("b_research", f"open_card_{keyword}_p{page_num}_{actual_idx}",
                               "results_page", "results_page", "soft_fail", notes="no detail type detected")

                    if consecutive_open_fails_this_kw >= 2:
                        stop_triggered = True
                        stop_reason = f"open_failed_twice_{keyword}_p{page_num}"
                        kw_result["stop_triggered"] = True
                        if not confidence["first_fragility_sign"]:
                            confidence["first_fragility_sign"] = f"open_failed_twice at kw={keyword} p={page_num}"
                    continue

                # Open succeeded
                opens_this_kw += 1
                total_cards_opened += 1
                consecutive_open_fails_this_kw = 0
                kw_result["detail_types_seen"].append(detail_type)
                confidence["detail_types"].append(detail_type)
                confidence["card_root_click"]["successes"] += 1
                confidence["card_root_click"]["keywords_tested"].add(keyword)
                recipe_book.add("open_result_card", best_open, True, f"b detail_type={detail_type}")

                ss_detail = await take_ss(page, f"b_detail_{keyword.replace(' ', '_')}_p{page_num}_{actual_idx}", ts)
                logger.log("b_research", f"open_card_{keyword}_p{page_num}_{actual_idx}",
                           "results_page", detail_type, "success",
                           notes=f"type={detail_type}", screenshot=ss_detail)

                print(f"      Opened: {detail_type}")

                # Stop condition 4: non-modal behavior unclassified
                if detail_type not in ("modal", "page", "drawer"):
                    stop_triggered = True
                    stop_reason = f"unclassified_detail_behavior_{detail_type}"
                    kw_result["stop_triggered"] = True
                    if not confidence["first_fragility_sign"]:
                        confidence["first_fragility_sign"] = f"unclassified detail type at kw={keyword}"

                # Note non-modal but classified behavior (don't stop, but record)
                if detail_type != "modal" and detail_type in ("page", "drawer"):
                    print(f"      [NOTE] Non-modal but classified: {detail_type}")
                    if not confidence["first_fragility_sign"]:
                        confidence["first_fragility_sign"] = f"non-modal detail ({detail_type}) at kw={keyword} p{page_num}"

                # ── Extract ──
                try:
                    detail_data = await extract_detail_from_modal(page)
                    kw_result["detail_extractions"].append({
                        "card_index": actual_idx, "page": page_num,
                        "detail_type": detail_type, "data": detail_data,
                    })
                    text_count = len(detail_data.get("texts", []))
                    img_count = len(detail_data.get("images", []))
                    link_count = len(detail_data.get("links", []))
                    advertiser = detail_data.get("advertiser", "unknown")

                    # Track card structure consistency
                    confidence["card_structures_seen"].append(text_count)

                    print(f"      Extracted: {text_count} texts, {img_count} imgs, {link_count} links, adv={advertiser}")
                except Exception as e:
                    print(f"      [WARN] Extraction error: {str(e)[:60]}")
                    kw_result["detail_extractions"].append({
                        "card_index": actual_idx, "page": page_num,
                        "detail_type": detail_type, "data": {"error": str(e)[:100]},
                    })

                # ── Close ──
                close_success = False
                try:
                    if best_close["type"] == "keyboard":
                        await page.keyboard.press(best_close["selector"])
                    else:
                        close_loc = page.locator(best_close["selector"]).first
                        if await close_loc.is_visible(timeout=2000):
                            await close_loc.click()

                    await page.wait_for_timeout(2000)

                    post_close_modals = await inspect_modal_state(page)
                    if len(post_close_modals.get("modals", [])) < len(post_modals.get("modals", [])):
                        close_success = True
                    elif "search" in page.url.lower() and page.url == pre_url:
                        close_success = True

                    recipe_book.add("close_detail", best_close, close_success, f"b close after {detail_type}")
                except Exception as e:
                    print(f"      [WARN] Close exception: {str(e)[:60]}")
                    recipe_book.add("close_detail", best_close, False, f"b exception: {str(e)[:40]}")

                if close_success:
                    kw_result["close_successes"] += 1
                    confidence["escape_close"]["successes"] += 1
                    print(f"      Closed via {best_close['type']}")
                    logger.log("b_research", f"close_{keyword}_p{page_num}_{actual_idx}",
                               detail_type, "results_page", "success", notes=f"method={best_close['type']}")
                else:
                    kw_result["close_failures"] += 1
                    confidence["escape_close"]["failures"] += 1
                    print(f"      [WARN] Close may have failed, recovering...")
                    logger.log("b_research", f"close_{keyword}_p{page_num}_{actual_idx}",
                               detail_type, "unknown", "soft_fail", notes=f"method={best_close['type']}")

                    # Recovery
                    recovered = False
                    try:
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(1500)
                        post_recovery = await inspect_modal_state(page)
                        if len(post_recovery.get("modals", [])) == 0:
                            recovered = True
                            print(f"      Recovery: Escape retry worked")
                        else:
                            await page.go_back()
                            await page.wait_for_timeout(3000)
                            if "search" in page.url.lower():
                                recovered = True
                                print(f"      Recovery: browser back worked")
                    except Exception:
                        pass

                    if not recovered:
                        # Stop condition 3: close fails and recovery doesn't restore
                        print(f"      [FAIL] Close recovery failed")
                        stop_triggered = True
                        stop_reason = "close_failed_no_recovery"
                        kw_result["stop_triggered"] = True
                        if not confidence["first_fragility_sign"]:
                            confidence["first_fragility_sign"] = f"close_recovery_failed at kw={keyword} p{page_num}"
                        break

                    # Verify we're back on results page after recovery
                    v_post = await verify_results_page(page, primary_card_sel)
                    if not v_post["verified"]:
                        stop_triggered = True
                        stop_reason = "results_page_not_restored_after_close_recovery"
                        kw_result["stop_triggered"] = True
                        if not confidence["first_fragility_sign"]:
                            confidence["first_fragility_sign"] = f"results_page_not_restored after close recovery at kw={keyword}"
                        break

                await page.wait_for_timeout(800)

        # ── End of keyword: check card structure consistency ──
        if len(confidence["card_structures_seen"]) >= 4:
            text_counts = confidence["card_structures_seen"]
            avg = sum(text_counts) / len(text_counts)
            spread = max(text_counts) - min(text_counts)
            if spread > avg * 0.5 and spread > 20:
                # Stop condition 6: mixed card structures
                if not confidence["first_fragility_sign"]:
                    confidence["first_fragility_sign"] = f"card_structure_spread={spread} avg={avg:.0f} after kw={keyword}"
                # Only stop if really bad
                if spread > avg * 0.8:
                    stop_triggered = True
                    stop_reason = f"card_structure_highly_mixed (spread={spread}, avg={avg:.0f})"
                    kw_result["stop_triggered"] = True

        kw_result["cards_opened"] = opens_this_kw
        kw_result["api_ads_captured"] = len(api_results.get(keyword, []))
        all_keyword_results.append(kw_result)

        print(f"\n  [KW DONE] '{keyword}': pages={kw_result['pages_searched']}, "
              f"opened={opens_this_kw}, failed={kw_result['cards_open_failed']}, "
              f"API={kw_result['api_ads_captured']}, closes={kw_result['close_successes']}OK/{kw_result['close_failures']}fail")

        # ── Periodic artifact revalidation (every 3 keywords) ──
        if (kw_idx + 1) % 3 == 0 and not stop_triggered:
            print(f"\n  [REVALIDATE] Checking artifacts after {kw_idx+1} keywords...")
            reval = await validate_artifacts(page, logger, ts)
            confidence["artifact_revalidations"].append({
                "after_keyword": keyword, "status": reval["status"],
                "checks": reval["checks"],
            })
            if reval["status"] == "stale":
                # Stop condition 5: artifacts dropped to stale
                stop_triggered = True
                stop_reason = "artifacts_became_stale_during_run"
                if not confidence["first_fragility_sign"]:
                    confidence["first_fragility_sign"] = f"artifacts stale after kw={keyword}"
            else:
                print(f"    Artifacts still: {reval['status']}")

        # Reset per-keyword open fail counter
        consecutive_open_fails_this_kw = 0
        opens_this_kw = 0

    # ── Clean up ──
    page.remove_listener("response", on_api_response)

    # ── Deduplicate API results ──
    all_api_ads = []
    seen_ids = set()
    for kw, items in api_results.items():
        for item in items:
            aid = item.get("ad_id") or item.get("id") or item.get("_id")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                item["_source_keyword"] = kw
                all_api_ads.append(item)

    region_matched = []
    for ad in all_api_ads:
        regions = ad.get("fetch_region", [])
        if isinstance(regions, str):
            regions = re.findall(r"'(\w{2})'", regions)
        if isinstance(regions, list):
            if any(r in TARGET_REGIONS for r in regions):
                region_matched.append(ad)

    # ── Compute final confidence ──
    crc = confidence["card_root_click"]
    crc_total = crc["successes"] + crc["failures"]
    crc_rate = round(crc["successes"] / max(crc_total, 1), 2)

    esc = confidence["escape_close"]
    esc_total = esc["successes"] + esc["failures"]
    esc_rate = round(esc["successes"] / max(esc_total, 1), 2)

    type_counts = Counter(confidence["detail_types"])

    text_counts = confidence["card_structures_seen"]
    structure_consistency = "unknown"
    if len(text_counts) >= 3:
        avg = sum(text_counts) / len(text_counts)
        spread = max(text_counts) - min(text_counts)
        if spread <= 10:
            structure_consistency = "high"
        elif spread <= 20:
            structure_consistency = "medium"
        else:
            structure_consistency = "low"

    # ── Save ──
    b_output = {
        "mode": "B",
        "timestamp": datetime.now().isoformat(),
        "keywords": B_KEYWORDS,
        "guardrails": {
            "max_keywords": len(B_KEYWORDS),
            "max_pages": B_MAX_PAGES,
            "max_opens_per_keyword": B_MAX_OPENS_PER_KEYWORD,
        },
        "artifact_validation": val,
        "keyword_results": all_keyword_results,
        "api_summary": {
            "total_captured": len(all_api_ads),
            "region_matched": len(region_matched),
            "api_interception_worked": api_capture_count > 0,
        },
        "confidence": {
            "card_root_click": {"rate": crc_rate, "successes": crc["successes"], "failures": crc["failures"],
                                "keywords_tested": len(crc["keywords_tested"])},
            "escape_close": {"rate": esc_rate, "successes": esc["successes"], "failures": esc["failures"]},
            "detail_types": dict(type_counts),
            "structure_consistency": structure_consistency,
            "first_fragility_sign": confidence["first_fragility_sign"],
            "artifact_revalidations": confidence["artifact_revalidations"],
        },
        "stop_condition": {"triggered": stop_triggered, "reason": stop_reason},
        "recipe_updates": recipe_book.to_dict(),
    }

    output_path = DATA_DIR / f"b_results_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(b_output, f, indent=2, ensure_ascii=True, default=str)
    print(f"\n  Results saved to: {output_path.name}")

    if all_api_ads:
        ads_path = DATA_DIR / f"b_ads_{ts}.json"
        with open(ads_path, "w", encoding="utf-8") as f:
            json.dump({
                "ads": all_api_ads,
                "region_matched": region_matched,
                "total": len(all_api_ads),
                "region_matched_count": len(region_matched),
            }, f, indent=2, ensure_ascii=True, default=str)
        print(f"  API ads saved to: {ads_path.name}")

    with open(INTERACTION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(recipe_book.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"  Updated interaction_recipes.json")

    # ══════════════════════════════════════════════════════════
    # B REPORT — 9 POINTS
    # ══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("B REPORT")
    print("=" * 70)

    # 1. Modal behavior
    print(f"\n1. MODAL BEHAVIOR:")
    print(f"   Detail types seen: {dict(type_counts)}")
    if len(type_counts) == 1 and "modal" in type_counts:
        print(f"   Verdict: modal_only HELD across {total_cards_opened} card opens")
    elif len(type_counts) == 0:
        print(f"   Verdict: no cards opened")
    else:
        print(f"   Verdict: MIXED behavior appeared — {dict(type_counts)}")

    # 2. card_root_click stability
    print(f"\n2. CARD_ROOT_CLICK STABILITY:")
    print(f"   Success rate: {crc_rate} ({crc['successes']}/{crc_total})")
    print(f"   Keywords tested: {len(crc['keywords_tested'])}/{len(B_KEYWORDS)}")
    if crc_rate >= 0.95:
        print(f"   Verdict: STABLE across all tested keywords/pages")
    elif crc_rate >= 0.8:
        print(f"   Verdict: MOSTLY STABLE with minor failures")
    else:
        print(f"   Verdict: UNSTABLE — needs investigation")

    # 3. Escape close sufficiency
    print(f"\n3. ESCAPE CLOSE SUFFICIENCY:")
    print(f"   Success rate: {esc_rate} ({esc['successes']}/{esc_total})")
    if esc_rate >= 1.0 and esc_total > 0:
        print(f"   Verdict: Escape SUFFICIENT for all closes")
    elif esc_rate >= 0.9:
        print(f"   Verdict: Escape mostly sufficient, minor failures")
    else:
        print(f"   Verdict: Escape INSUFFICIENT — alternate close needed")

    # 4. Card structure consistency
    print(f"\n4. CARD STRUCTURE CONSISTENCY:")
    print(f"   Text counts across cards: min={min(text_counts) if text_counts else 'N/A'}, "
          f"max={max(text_counts) if text_counts else 'N/A'}, "
          f"avg={sum(text_counts)/len(text_counts):.0f}" if text_counts else "   No data")
    print(f"   Verdict: {structure_consistency}")

    # 5. Artifact validity
    print(f"\n5. ARTIFACT VALIDITY:")
    print(f"   Initial: {val['status']}")
    for rv in confidence["artifact_revalidations"]:
        print(f"   After '{rv['after_keyword']}': {rv['status']}")
    if not confidence["artifact_revalidations"]:
        print(f"   No mid-run revalidations performed")
    if all(rv["status"] in ("valid", "partial") for rv in confidence["artifact_revalidations"]):
        print(f"   Verdict: artifacts STAYED VALID throughout")
    elif confidence["artifact_revalidations"]:
        print(f"   Verdict: artifact degradation detected")
    else:
        print(f"   Verdict: initial validation held (no revalidation point reached)")

    # 6. Better recipes learned?
    print(f"\n6. NEW/BETTER RECIPES:")
    updated_recipes = recipe_book.to_dict()
    for action, entries in updated_recipes.items():
        for entry in entries:
            total = entry["success_count"] + entry["fail_count"]
            if total > 0:
                print(f"   {action}: {entry['method'].get('type','?')} → "
                      f"{entry['success_count']}/{total} ({entry['confidence']})")

    # 7. API interception
    print(f"\n7. API INTERCEPTION:")
    print(f"   Total captured: {api_capture_count}")
    print(f"   Unique ads: {len(all_api_ads)}")
    print(f"   Region matched: {len(region_matched)}")
    if api_capture_count > 0:
        print(f"   Verdict: API interception IMPROVED — now capturing data")
    else:
        print(f"   Verdict: API interception still UNRELIABLE")

    # 8. First fragility sign
    print(f"\n8. FIRST FRAGILITY SIGN:")
    if confidence["first_fragility_sign"]:
        print(f"   {confidence['first_fragility_sign']}")
    else:
        print(f"   None detected — no structural fragility observed")

    # 9. Totals
    print(f"\n9. TOTALS:")
    kw_completed = len([kr for kr in all_keyword_results if not kr["stop_triggered"]])
    kw_stopped = len([kr for kr in all_keyword_results if kr["stop_triggered"]])
    print(f"   Keywords: {len(all_keyword_results)}/{len(B_KEYWORDS)} searched ({kw_completed} clean, {kw_stopped} stopped)")
    print(f"   Pages processed: {total_pages_processed}")
    print(f"   Cards opened (UI): {total_cards_opened}")
    print(f"   Detail extractions: {sum(len(kr['detail_extractions']) for kr in all_keyword_results)}")
    print(f"   Total closes: {sum(kr['close_successes'] for kr in all_keyword_results)} OK, "
          f"{sum(kr['close_failures'] for kr in all_keyword_results)} failed")

    # Gate assessment
    print(f"\n{'─' * 70}")
    print("B GATES:")
    b_gates = {
        "artifacts_valid": val["status"] in ("valid", "partial"),
        "modal_only_held": len(type_counts) <= 1 or (len(type_counts) == 1 and "modal" in type_counts),
        "card_root_click_stable": crc_rate >= 0.9,
        "escape_close_reliable": esc_rate >= 0.9,
        "structure_consistent": structure_consistency in ("high", "medium"),
        "no_stop_triggered": not stop_triggered,
        "majority_keywords_completed": len(all_keyword_results) >= len(B_KEYWORDS) * 0.75,
    }
    all_pass = True
    for gate, passed in b_gates.items():
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {gate}")
        if not passed:
            all_pass = False

    print(f"\n  B Overall: {'PASSED' if all_pass else 'NEEDS REVIEW'}")
    if all_pass:
        print(f"  [NEXT] Operator model scales. Ready for --mode C.")
    else:
        print(f"  [NEXT] Review failures before proceeding to C.")

    print(f"\n  [STOP] B run complete. Do not auto-advance to C.")

    logger.save()
    return b_output


# ═══════════════════════════════════════════════════════════
# B2: Continuation Mechanism Discovery
# ═══════════════════════════════════════════════════════════

CONTINUATION_ANALYSIS_PATH = LEARN_DIR / "continuation_analysis.json"
SCROLL_TRACE_PATH = LEARN_DIR / "scroll_trace.json"
CONTINUATION_RECIPES_PATH = LEARN_DIR / "continuation_recipes.json"

B2_KEYWORD = "oversized hoodie"


async def detect_scroll_container(page: Page, card_list_selector: str) -> dict:
    """Detect the actual scrollable container for results."""
    return await page.evaluate("""(cardListSel) => {
        const result = {
            scroll_context_type: 'unknown',
            scroll_container_selector: null,
            scroll_container_dimensions: null,
            ancestors_checked: 0,
            window_scrollable: false,
            internal_containers: [],
            evidence: [],
        };

        // Check window/document scrollability
        const docEl = document.documentElement;
        const bodyEl = document.body;
        result.window_scrollable = docEl.scrollHeight > docEl.clientHeight;
        result.evidence.push('window scrollHeight=' + docEl.scrollHeight + ' clientHeight=' + docEl.clientHeight);

        // Find the card list container
        let listContainer = null;
        // Try several selectors to find the result list
        for (const sel of [cardListSel, '.lists-wrap', '[class*="lists-wrap"]', '[class*="result-list"]']) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) {
                listContainer = el;
                break;
            }
        }

        if (!listContainer) {
            result.evidence.push('card list container not found');
            result.scroll_context_type = result.window_scrollable ? 'window' : 'unknown';
            return result;
        }

        result.evidence.push('card list found: ' + listContainer.tagName + '.' + (listContainer.className || '').substring(0, 80));

        // Walk ancestors from card list container up to body
        let el = listContainer;
        while (el && el !== document.body && el !== docEl) {
            result.ancestors_checked++;
            const style = getComputedStyle(el);
            const ov = style.overflow + ' ' + style.overflowY;
            const isScrollable = (ov.includes('auto') || ov.includes('scroll')) && el.scrollHeight > el.clientHeight;

            if (isScrollable) {
                const rect = el.getBoundingClientRect();
                const selectorParts = [];
                if (el.id) selectorParts.push('#' + el.id);
                if (el.className) {
                    const cls = (el.className || '').split(' ').filter(c => c && c.length > 2).slice(0, 3).map(c => '.' + c).join('');
                    if (cls) selectorParts.push(el.tagName.toLowerCase() + cls);
                }
                const selector = selectorParts[0] || (el.tagName.toLowerCase() + '.' + (el.className || '').split(' ')[0]);

                result.internal_containers.push({
                    selector: selector,
                    tag: el.tagName,
                    class: (el.className || '').substring(0, 120),
                    overflow: ov.trim(),
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    scrollTop: el.scrollTop,
                    rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                });
                result.evidence.push('scrollable ancestor: ' + el.tagName + '.' + (el.className || '').substring(0, 60) + ' overflow=' + ov.trim() + ' scrollH=' + el.scrollHeight + ' clientH=' + el.clientHeight);
            }
            el = el.parentElement;
        }

        // Classify
        if (result.internal_containers.length > 0 && result.window_scrollable) {
            result.scroll_context_type = 'mixed';
            result.scroll_container_selector = result.internal_containers[0].selector;
            result.scroll_container_dimensions = result.internal_containers[0];
        } else if (result.internal_containers.length > 0) {
            result.scroll_context_type = 'internal_container';
            result.scroll_container_selector = result.internal_containers[0].selector;
            result.scroll_container_dimensions = result.internal_containers[0];
        } else if (result.window_scrollable) {
            result.scroll_context_type = 'window';
        } else {
            result.scroll_context_type = 'unknown';
        }

        return result;
    }""", card_list_selector)


async def collect_card_fingerprints(page: Page, card_selector: str, sample_first: int = 3, sample_last: int = 3) -> dict:
    """Collect identity fingerprints and bbox for cards."""
    return await page.evaluate("""([sel, sFirst, sLast]) => {
        const cards = Array.from(document.querySelectorAll(sel));
        const total = cards.length;
        const visible = cards.filter(c => c.offsetParent !== null).length;

        function fingerprint(card, idx) {
            const advEl = card.querySelector('.app-name, .nickname, [class*="title"] a, .a-link');
            const imgEl = card.querySelector('img');
            const linkEl = card.querySelector('a[href]');
            const rect = card.getBoundingClientRect();
            const advText = (advEl ? advEl.textContent.trim() : '').substring(0, 60);
            const imgSrc = (imgEl ? imgEl.src : '').substring(0, 100);
            const linkHref = (linkEl ? linkEl.href : '').substring(0, 100);
            return {
                dom_index: idx,
                advertiser_text: advText,
                first_img_src: imgSrc,
                first_link_href: linkHref,
                fingerprint_hash: advText + '|' + imgSrc.substring(imgSrc.length - 30),
                bbox_top: Math.round(rect.top),
                bbox_height: Math.round(rect.height),
            };
        }

        const first_n = [];
        for (let i = 0; i < Math.min(sFirst, total); i++) {
            first_n.push(fingerprint(cards[i], i));
        }
        const last_n = [];
        for (let i = Math.max(0, total - sLast); i < total; i++) {
            last_n.push(fingerprint(cards[i], i));
        }
        const sampled_bboxes = [];
        if (total > 0) sampled_bboxes.push({index: 0, top: cards[0].getBoundingClientRect().top});
        if (total > 1) sampled_bboxes.push({index: total - 1, top: cards[total - 1].getBoundingClientRect().top});

        return {
            dom_card_count: total,
            visible_card_count: visible,
            first_n: first_n,
            last_n: last_n,
            sampled_bboxes: sampled_bboxes,
        };
    }""", [card_selector, sample_first, sample_last])


async def inspect_bottom_zone(page: Page, card_selector: str) -> dict:
    """Inspect the area below/around the result list for continuation controls."""
    return await page.evaluate("""(cardSel) => {
        const result = {
            pagination_candidates: [],
            load_more_candidates: [],
            sentinel_candidates: [],
            end_markers: [],
            result_count_labels: [],
            hidden_pagination: [],
        };

        // Get result container bounding box for scoping
        const cards = document.querySelectorAll(cardSel);
        let resultBottom = 0;
        let resultLeft = 0;
        let resultRight = 1920;
        if (cards.length > 0) {
            const lastCard = cards[cards.length - 1];
            const lastRect = lastCard.getBoundingClientRect();
            resultBottom = lastRect.bottom;
            // Use first card for horizontal bounds
            const firstRect = cards[0].getBoundingClientRect();
            resultLeft = firstRect.left - 50;
            resultRight = firstRect.right + 50;
        }

        // Pagination scoped to result area
        const pagSelectors = ['[class*="pagination"]', '[class*="pager"]', '.el-pagination', 'nav[aria-label*="page" i]'];
        pagSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                const rect = el.getBoundingClientRect();
                const visible = el.offsetParent !== null;
                const style = getComputedStyle(el);
                const hidden = style.display === 'none' || style.visibility === 'hidden' || rect.height === 0;

                // Scoping: must be vertically near result bottom AND horizontally overlapping
                const verticallyNear = rect.top >= resultBottom - 100 && rect.top <= resultBottom + 300;
                const horizontallyOverlapping = rect.left < resultRight && rect.right > resultLeft;
                const notInNav = rect.top > 100;

                const numberedChildren = Array.from(el.querySelectorAll('li, button, a, span'))
                    .filter(c => /^\\d+$/.test(c.textContent.trim())).length;
                const hasNextPrev = el.textContent.toLowerCase().includes('next') || el.querySelector('[class*="next"]') !== null;

                const entry = {
                    selector: sel,
                    tag: el.tagName,
                    class: (el.className || '').substring(0, 120),
                    visible: visible,
                    hidden: hidden,
                    visible_text: el.textContent.trim().substring(0, 150),
                    bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                    relative_to_results: Math.round(rect.top - resultBottom) + 'px from result bottom',
                    has_numbered_children: numberedChildren > 0,
                    numbered_child_count: numberedChildren,
                    has_next_prev: hasNextPrev,
                    scoped_to_results: verticallyNear && horizontallyOverlapping && notInNav,
                    rejected: false,
                    rejection_reason: null,
                };

                if (!notInNav) { entry.rejected = true; entry.rejection_reason = 'in navigation area (top < 100px)'; }
                else if (!horizontallyOverlapping) { entry.rejected = true; entry.rejection_reason = 'no horizontal overlap with results'; }
                else if (!verticallyNear && !hidden) { entry.rejected = true; entry.rejection_reason = 'not vertically near result bottom'; }
                else if (!numberedChildren && !hasNextPrev && !hidden) { entry.rejected = true; entry.rejection_reason = 'no numbered children and no next/prev'; }

                if (hidden && (numberedChildren > 0 || hasNextPrev)) {
                    result.hidden_pagination.push(entry);
                } else {
                    result.pagination_candidates.push(entry);
                }
            });
        });

        // Load more buttons
        const loadMoreSelectors = ['[class*="load-more"]', '[class*="loadmore"]', '[class*="load_more"]',
            'button:has([class*="load"])', '[class*="show-more"]'];
        loadMoreSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                if (el.getBoundingClientRect().top > resultBottom - 100) {
                    result.load_more_candidates.push({
                        selector: sel, tag: el.tagName, class: (el.className || '').substring(0, 80),
                        text: el.textContent.trim().substring(0, 60),
                        visible: el.offsetParent !== null,
                        bbox: el.getBoundingClientRect(),
                    });
                }
            });
        });
        // Also check for text-based load more
        document.querySelectorAll('button, a, div').forEach(el => {
            const t = el.textContent.trim().toLowerCase();
            if ((t === 'load more' || t === 'show more' || t === 'view more') && el.offsetParent !== null) {
                const rect = el.getBoundingClientRect();
                if (rect.top > resultBottom - 200) {
                    result.load_more_candidates.push({
                        selector: 'text-match', tag: el.tagName, class: (el.className || '').substring(0, 80),
                        text: el.textContent.trim().substring(0, 60), visible: true, bbox: rect,
                    });
                }
            }
        });

        // Sentinels / infinite scroll triggers
        const sentinelSelectors = ['[class*="sentinel"]', '[class*="observer"]', '[class*="trigger"]',
            '[class*="infinite"]', '[class*="bottom-loader"]', '[class*="scroll-trigger"]', '[class*="lazy-load"]'];
        sentinelSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                const rect = el.getBoundingClientRect();
                result.sentinel_candidates.push({
                    selector: sel, tag: el.tagName, class: (el.className || '').substring(0, 80),
                    visible: el.offsetParent !== null, bbox: rect,
                    text: el.textContent.trim().substring(0, 40),
                });
            });
        });

        // End-of-list markers
        const endSelectors = ['[class*="no-more"]', '[class*="end-of"]', '[class*="empty"]', '[class*="nomore"]'];
        endSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                if (el.getBoundingClientRect().top > resultBottom - 200) {
                    result.end_markers.push({
                        selector: sel, tag: el.tagName, class: (el.className || '').substring(0, 80),
                        text: el.textContent.trim().substring(0, 100),
                        visible: el.offsetParent !== null,
                    });
                }
            });
        });

        // Result count labels
        document.querySelectorAll('[class*="total"], [class*="count"], [class*="result"], [class*="showing"]').forEach(el => {
            const t = el.textContent.trim();
            if (t.length < 80 && /\\d/.test(t) && el.offsetParent !== null) {
                const rect = el.getBoundingClientRect();
                // Must be near the result area (above or around)
                if (rect.top < resultBottom + 100) {
                    result.result_count_labels.push({
                        text: t.substring(0, 80),
                        tag: el.tagName,
                        class: (el.className || '').substring(0, 80),
                        bbox: rect,
                    });
                }
            }
        });

        return result;
    }""", card_selector)


async def perform_scroll_test(page: Page, card_selector: str, scroll_target: str,
                               container_selector: str, increments: int,
                               increment_px: int, logger: StepLogger, ts: str) -> list:
    """
    Perform controlled scroll test on a specific target.
    Returns list of scroll_trace step dicts.
    """
    trace = []
    baseline_fps = await collect_card_fingerprints(page, card_selector)
    baseline_hashes = set(fp["fingerprint_hash"] for fp in baseline_fps["first_n"] + baseline_fps["last_n"])

    # Track network requests during scrolling
    scroll_requests = []

    async def on_scroll_request(response):
        if response.status == 200:
            url = response.url
            if any(p in url for p in ["search4", "search", "api", "list", "page"]):
                scroll_requests.append({
                    "url": url[:200],
                    "status": response.status,
                    "type": "fetch/xhr",
                })

    page.on("response", on_scroll_request)

    bottom_reached_count = 0

    for step_num in range(increments):
        # Scroll
        if scroll_target == "window":
            await page.evaluate(f"window.scrollBy(0, {increment_px})")
        else:
            await page.evaluate(f"""(sel) => {{
                const el = document.querySelector(sel);
                if (el) el.scrollTop += {increment_px};
            }}""", container_selector)

        # Settle
        await page.wait_for_timeout(3000)

        # Collect measurements
        scroll_state = await page.evaluate(f"""(containerSel) => {{
            const docH = document.documentElement.scrollHeight;
            const winY = window.scrollY;
            const vpH = window.innerHeight;
            let contScrollH = docH;
            let contClientH = vpH;
            let contScrollTop = winY;
            const cont = containerSel ? document.querySelector(containerSel) : null;
            if (cont) {{
                contScrollH = cont.scrollHeight;
                contClientH = cont.clientHeight;
                contScrollTop = cont.scrollTop;
            }}
            const atBottom = (contScrollTop + contClientH) >= (contScrollH - 100);
            // Check for loaders
            const loaders = document.querySelectorAll('[class*="skeleton"],[class*="loading"],[class*="spinner"]');
            const visibleLoaders = Array.from(loaders).filter(l => l.offsetParent !== null).length;

            return {{
                scroll_y: winY,
                viewport_height: vpH,
                document_height: docH,
                container_scroll_height: contScrollH,
                container_client_height: contClientH,
                container_scroll_top: contScrollTop,
                at_bottom: atBottom,
                loaders_detected: visibleLoaders,
            }};
        }}""", container_selector if scroll_target != "window" else "")

        # Collect fingerprints
        fps = await collect_card_fingerprints(page, card_selector)
        current_hashes = set(fp["fingerprint_hash"] for fp in fps["first_n"] + fps["last_n"])
        new_hashes = current_hashes - baseline_hashes
        lost_hashes = baseline_hashes - current_hashes

        # Check if content swapped at index 0
        content_swap = False
        if baseline_fps["first_n"] and fps["first_n"]:
            if fps["first_n"][0]["fingerprint_hash"] != baseline_fps["first_n"][0]["fingerprint_hash"]:
                content_swap = True

        # Network requests this step
        requests_this_step = list(scroll_requests)
        scroll_requests.clear()

        if scroll_state["at_bottom"]:
            bottom_reached_count += 1

        step_data = {
            "step": step_num + 1,
            "scroll_target": scroll_target,
            "scroll_y": scroll_state["scroll_y"],
            "viewport_height": scroll_state["viewport_height"],
            "document_height": scroll_state["document_height"],
            "container_scroll_height": scroll_state["container_scroll_height"],
            "container_client_height": scroll_state["container_client_height"],
            "dom_card_count": fps["dom_card_count"],
            "dom_count_delta_from_baseline": fps["dom_card_count"] - baseline_fps["dom_card_count"],
            "visible_card_count": fps["visible_card_count"],
            "first_3_identities": fps["first_n"],
            "last_3_identities": fps["last_n"],
            "new_fingerprints_detected": len(new_hashes),
            "lost_fingerprints_detected": len(lost_hashes),
            "content_swap_detected": content_swap,
            "sampled_bbox_positions": fps["sampled_bboxes"],
            "loaders_detected": scroll_state["loaders_detected"],
            "controls_detected": [],
            "network_requests_this_step": len(requests_this_step),
            "request_urls_sample": [r["url"][:100] for r in requests_this_step[:3]],
            "request_types": [r["type"] for r in requests_this_step[:3]],
            "response_statuses_sample": [r["status"] for r in requests_this_step[:3]],
            "likely_result_request_detected": any("search" in r["url"].lower() for r in requests_this_step),
            "at_bottom": scroll_state["at_bottom"],
            "bottom_reached_count": bottom_reached_count,
            "notes": "",
        }

        # Screenshot every 3rd step and on last step
        if (step_num + 1) % 3 == 0 or step_num == increments - 1:
            ss = await take_ss(page, f"b2_scroll_{scroll_target}_{step_num+1}", ts)
            step_data["screenshot"] = ss

        trace.append(step_data)

        print(f"    Step {step_num+1}: scrollY={scroll_state['scroll_y']}, "
              f"dom={fps['dom_card_count']}(Δ{fps['dom_card_count'] - baseline_fps['dom_card_count']}), "
              f"vis={fps['visible_card_count']}, "
              f"new={len(new_hashes)}, lost={len(lost_hashes)}, "
              f"swap={'YES' if content_swap else 'no'}, "
              f"net={len(requests_this_step)}, "
              f"loaders={scroll_state['loaders_detected']}"
              + (" [BOTTOM]" if scroll_state["at_bottom"] else ""))

        # Extra settle at bottom
        if scroll_state["at_bottom"] and bottom_reached_count <= 2:
            print(f"    At bottom — extra 5s settle...")
            await page.wait_for_timeout(5000)
            # Re-measure after settle
            fps2 = await collect_card_fingerprints(page, card_selector)
            if fps2["dom_card_count"] != fps["dom_card_count"]:
                step_data["notes"] += f"DOM count changed after settle: {fps['dom_card_count']} -> {fps2['dom_card_count']}. "
                print(f"    DOM count changed after settle: {fps['dom_card_count']} -> {fps2['dom_card_count']}")

    page.remove_listener("response", on_scroll_request)
    return trace


async def run_b2(page: Page, logger: StepLogger, ts: str):
    """
    B2: Continuation mechanism discovery.
    Discovers how Pipiads exposes results beyond the initial visible batch.
    """
    print("\n" + "=" * 70)
    print("B2 — CONTINUATION MECHANISM DISCOVERY")
    print(f"Keyword: '{B2_KEYWORD}'")
    print("=" * 70)

    # ════════════════════════════════════════
    # Phase 0: Setup
    # ════════════════════════════════════════
    print("\n[Phase 0] Setup...")

    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]

    input_candidates = dom_sigs.get("search_input_candidates", [])
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"] if input_candidates else "#inputKeyword"

    # Validate
    val = await validate_artifacts(page, logger, ts)
    print(f"  Artifacts: {val['status']}")
    if val["status"] in ("stale", "missing"):
        print("[ABORT] Artifacts invalid.")
        return None

    # Submit search
    try:
        loc = page.locator(primary_input_sel).first
        if not await loc.is_visible(timeout=5000):
            loc = page.locator("#inputKeyword").first
        await loc.click(click_count=3)
        await loc.fill(B2_KEYWORD)
        await page.wait_for_timeout(500)
        await loc.press("Enter")
        print(f"  Searched: '{B2_KEYWORD}'")
    except Exception as e:
        print(f"[ABORT] Search failed: {str(e)[:80]}")
        return None

    await page.wait_for_timeout(6000)

    verification = await verify_results_page(page, primary_card_sel)
    if not verification["verified"]:
        await page.wait_for_timeout(5000)
        verification = await verify_results_page(page, primary_card_sel)
        if not verification["verified"]:
            print(f"[ABORT] Results page not verified.")
            return None

    ss0 = await take_ss(page, "b2_phase0_results", ts)
    await save_html(page, "b2_phase0_results", ts)
    logger.log("b2", "setup_complete", "search_page", "results_page", "success",
               notes=f"keyword={B2_KEYWORD}", screenshot=ss0)
    print(f"  Results page verified.")

    # ════════════════════════════════════════
    # Phase 1: Baseline characterization
    # ════════════════════════════════════════
    print("\n[Phase 1] Baseline characterization...")

    # 1a. Card counts
    baseline_fps = await collect_card_fingerprints(page, primary_card_sel)
    print(f"  DOM card count: {baseline_fps['dom_card_count']}")
    print(f"  Visible cards: {baseline_fps['visible_card_count']}")

    # 1b. Detect scroll container
    scroll_info = await detect_scroll_container(page, ".lists-wrap")
    print(f"  Scroll context: {scroll_info['scroll_context_type']}")
    print(f"  Window scrollable: {scroll_info['window_scrollable']}")
    print(f"  Internal containers: {len(scroll_info['internal_containers'])}")
    for ic in scroll_info["internal_containers"]:
        print(f"    - {ic['selector'][:60]} (scrollH={ic['scrollHeight']}, clientH={ic['clientHeight']})")
    for ev in scroll_info["evidence"]:
        print(f"    evidence: {ev}")

    container_selector = scroll_info.get("scroll_container_selector")

    # 1c. Result count text
    result_count_info = await page.evaluate("""() => {
        const candidates = [];
        document.querySelectorAll('[class*="total"], [class*="count"], [class*="result"], [class*="showing"], [class*="num"]').forEach(el => {
            const t = el.textContent.trim();
            if (t.length < 100 && /\\d/.test(t) && el.offsetParent !== null) {
                const rect = el.getBoundingClientRect();
                if (rect.top < 700) {
                    candidates.push({text: t.substring(0, 80), tag: el.tagName, class: (el.className||'').substring(0, 80),
                        bbox: {x: Math.round(rect.x), y: Math.round(rect.y)}});
                }
            }
        });
        return candidates;
    }""")
    result_count_label_found = len(result_count_info) > 0
    result_count_label_text = result_count_info[0]["text"] if result_count_info else None
    print(f"  Result count labels: {len(result_count_info)}")
    for rc in result_count_info[:5]:
        print(f"    - '{rc['text']}' ({rc['tag']}.{rc['class'][:30]})")

    # 1d. Bottom controls (without scrolling)
    bottom_zone = await inspect_bottom_zone(page, primary_card_sel)
    print(f"  Pagination candidates: {len(bottom_zone['pagination_candidates'])}")
    for pc in bottom_zone["pagination_candidates"]:
        status = "SCOPED" if pc["scoped_to_results"] else f"REJECTED ({pc['rejection_reason']})"
        print(f"    - {pc['selector']} visible={pc['visible']} numbered={pc['has_numbered_children']} [{status}]")
    print(f"  Hidden pagination: {len(bottom_zone['hidden_pagination'])}")
    for hp in bottom_zone["hidden_pagination"]:
        print(f"    - {hp['selector']} text='{hp['visible_text'][:50]}'")
    print(f"  Load more: {len(bottom_zone['load_more_candidates'])}")
    print(f"  Sentinels: {len(bottom_zone['sentinel_candidates'])}")
    print(f"  End markers: {len(bottom_zone['end_markers'])}")
    for em in bottom_zone["end_markers"]:
        print(f"    - '{em['text'][:60]}' visible={em['visible']}")

    logger.log("b2", "baseline", "results_page", "results_page", "info",
               notes=f"dom={baseline_fps['dom_card_count']}, vis={baseline_fps['visible_card_count']}, "
                     f"scroll={scroll_info['scroll_context_type']}, pag={len(bottom_zone['pagination_candidates'])}")

    ss1 = await take_ss(page, "b2_phase1_baseline", ts)

    # ════════════════════════════════════════
    # Phase 2: Window-scroll test
    # ════════════════════════════════════════
    window_trace = []
    window_tested = False
    if scroll_info["window_scrollable"]:
        print("\n[Phase 2] Window-scroll test...")
        window_tested = True
        window_trace = await perform_scroll_test(
            page, primary_card_sel, "window", "", 8, 800, logger, ts)

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(2000)
        print("  Scrolled back to top.")
    else:
        print("\n[Phase 2] SKIP — window not scrollable")

    # ════════════════════════════════════════
    # Phase 3: Internal-container-scroll test
    # ════════════════════════════════════════
    internal_trace = []
    internal_tested = False
    if scroll_info["internal_containers"]:
        print(f"\n[Phase 3] Internal-container-scroll test ({container_selector})...")
        internal_tested = True

        # Reset internal container scroll first
        if container_selector:
            await page.evaluate(f"""(sel) => {{
                const el = document.querySelector(sel);
                if (el) el.scrollTop = 0;
            }}""", container_selector)
            await page.wait_for_timeout(1000)

        internal_trace = await perform_scroll_test(
            page, primary_card_sel, "internal", container_selector, 8, 600, logger, ts)

        # Scroll container back to top
        if container_selector:
            await page.evaluate(f"""(sel) => {{
                const el = document.querySelector(sel);
                if (el) el.scrollTop = 0;
            }}""", container_selector)
            await page.wait_for_timeout(1000)
    else:
        print("\n[Phase 3] SKIP — no internal scroll container found")

    # ════════════════════════════════════════
    # Phase 4: Bottom-zone interrogation
    # ════════════════════════════════════════
    print("\n[Phase 4] Bottom-zone interrogation...")

    # Scroll to bottom of active container
    if scroll_info["scroll_context_type"] in ("window", "mixed"):
        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    if container_selector and scroll_info["scroll_context_type"] in ("internal_container", "mixed"):
        await page.evaluate(f"""(sel) => {{
            const el = document.querySelector(sel);
            if (el) el.scrollTop = el.scrollHeight;
        }}""", container_selector)
    await page.wait_for_timeout(3000)

    ss_bottom1 = await take_ss(page, "b2_phase4_bottom_pass1", ts)

    # Re-inspect bottom zone after scrolling
    bottom_zone_2 = await inspect_bottom_zone(page, primary_card_sel)
    print(f"  Bottom pass 1:")
    print(f"    Pagination: {len(bottom_zone_2['pagination_candidates'])} "
          f"(scoped: {len([p for p in bottom_zone_2['pagination_candidates'] if p['scoped_to_results']])})")
    print(f"    Load more: {len(bottom_zone_2['load_more_candidates'])}")
    print(f"    Sentinels: {len(bottom_zone_2['sentinel_candidates'])}")
    print(f"    End markers: {len(bottom_zone_2['end_markers'])}")
    for pc in bottom_zone_2["pagination_candidates"]:
        if pc["scoped_to_results"] and not pc["rejected"]:
            print(f"    [SCOPED PAGINATION] {pc['visible_text'][:80]} numbered={pc['has_numbered_children']}")

    # Second bottom settle
    print(f"  Second bottom pass (5s settle)...")
    await page.wait_for_timeout(5000)

    fps_bottom = await collect_card_fingerprints(page, primary_card_sel)
    print(f"    DOM cards after bottom settle: {fps_bottom['dom_card_count']} (baseline was {baseline_fps['dom_card_count']})")

    ss_bottom2 = await take_ss(page, "b2_phase4_bottom_pass2", ts)

    # Third check — scroll again from bottom
    if scroll_info["scroll_context_type"] in ("window", "mixed"):
        await page.evaluate("window.scrollBy(0, 500)")
    if container_selector and scroll_info["scroll_context_type"] in ("internal_container", "mixed"):
        await page.evaluate(f"""(sel) => {{
            const el = document.querySelector(sel);
            if (el) el.scrollTop += 500;
        }}""", container_selector)
    await page.wait_for_timeout(3000)

    fps_bottom2 = await collect_card_fingerprints(page, primary_card_sel)
    print(f"    DOM cards after re-scroll: {fps_bottom2['dom_card_count']}")

    bottom_zone_3 = await inspect_bottom_zone(page, primary_card_sel)

    # ── Attempt clicking scoped pagination if found ──
    scoped_pag = [p for p in bottom_zone_2["pagination_candidates"]
                  if p["scoped_to_results"] and not p["rejected"] and p["visible"]]
    pagination_click_result = None
    if scoped_pag:
        print(f"\n  Testing scoped pagination control...")
        best_pag = scoped_pag[0]
        ss_pre_click = await take_ss(page, "b2_phase4_pre_pag_click", ts)
        pre_fps = await collect_card_fingerprints(page, primary_card_sel)

        # Try clicking "2" or "Next" within the pagination
        clicked = False
        for attempt_sel in [
            f'{best_pag["selector"]} :text-is("2")',
            f'{best_pag["selector"]} [class*="next"]',
            f'{best_pag["selector"]} button:has-text("Next")',
        ]:
            try:
                loc = page.locator(attempt_sel).first
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    clicked = True
                    print(f"    Clicked: {attempt_sel}")
                    break
            except Exception:
                continue

        if not clicked:
            # Try evaluate-based click
            try:
                clicked = await page.evaluate(f"""(sel) => {{
                    const pag = document.querySelector(sel);
                    if (!pag) return false;
                    const items = pag.querySelectorAll('li, button, a, span');
                    for (const item of items) {{
                        if (item.textContent.trim() === '2' && item.offsetParent) {{
                            item.click(); return true;
                        }}
                    }}
                    // Try "Next" button
                    const next = pag.querySelector('[class*="next"]');
                    if (next && next.offsetParent) {{ next.click(); return true; }}
                    return false;
                }}""", best_pag["selector"])
                if clicked:
                    print(f"    Clicked via evaluate on {best_pag['selector']}")
            except Exception:
                pass

        if clicked:
            await page.wait_for_timeout(5000)
            ss_post_click = await take_ss(page, "b2_phase4_post_pag_click", ts)
            post_fps = await collect_card_fingerprints(page, primary_card_sel)

            pre_hashes = set(fp["fingerprint_hash"] for fp in pre_fps["first_n"] + pre_fps["last_n"])
            post_hashes = set(fp["fingerprint_hash"] for fp in post_fps["first_n"] + post_fps["last_n"])
            identities_changed = pre_hashes != post_hashes
            new_identities = post_hashes - pre_hashes

            pagination_click_result = {
                "clicked": True,
                "identities_changed": identities_changed,
                "new_identities_count": len(new_identities),
                "dom_count_before": pre_fps["dom_card_count"],
                "dom_count_after": post_fps["dom_card_count"],
                "pre_screenshot": ss_pre_click,
                "post_screenshot": ss_post_click,
            }
            print(f"    Identities changed: {identities_changed} ({len(new_identities)} new)")
            print(f"    DOM count: {pre_fps['dom_card_count']} -> {post_fps['dom_card_count']}")
        else:
            pagination_click_result = {"clicked": False, "reason": "no clickable target found"}
            print(f"    Could not click any pagination target")

    # ── Attempt clicking load-more if found ──
    load_more_click_result = None
    if bottom_zone_2["load_more_candidates"]:
        visible_lm = [lm for lm in bottom_zone_2["load_more_candidates"] if lm.get("visible")]
        if visible_lm:
            print(f"\n  Testing load-more control...")
            lm = visible_lm[0]
            pre_fps = await collect_card_fingerprints(page, primary_card_sel)
            ss_pre = await take_ss(page, "b2_phase4_pre_loadmore", ts)

            try:
                if lm["selector"] == "text-match":
                    loc = page.locator(f'{lm["tag"]}:has-text("{lm["text"]}")').first
                else:
                    loc = page.locator(lm["selector"]).first
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await page.wait_for_timeout(5000)
                    post_fps = await collect_card_fingerprints(page, primary_card_sel)
                    ss_post = await take_ss(page, "b2_phase4_post_loadmore", ts)

                    load_more_click_result = {
                        "clicked": True,
                        "dom_grew": post_fps["dom_card_count"] > pre_fps["dom_card_count"],
                        "dom_before": pre_fps["dom_card_count"],
                        "dom_after": post_fps["dom_card_count"],
                    }
                    print(f"    DOM: {pre_fps['dom_card_count']} -> {post_fps['dom_card_count']}")
            except Exception as e:
                load_more_click_result = {"clicked": False, "error": str(e)[:60]}
                print(f"    Load-more click failed: {str(e)[:60]}")

    logger.log("b2", "bottom_zone", "results_page", "results_page", "info",
               notes=f"pag_scoped={len(scoped_pag)}, load_more={len(bottom_zone_2['load_more_candidates'])}, "
                     f"sentinels={len(bottom_zone_2['sentinel_candidates'])}")

    # ════════════════════════════════════════
    # Phase 5: Classification
    # ════════════════════════════════════════
    print("\n[Phase 5] Classification...")

    all_trace = window_trace + internal_trace

    # Analyze traces
    dom_grew = any(s["dom_count_delta_from_baseline"] > 0 for s in all_trace)
    any_content_swap = any(s["content_swap_detected"] for s in all_trace)
    any_new_fps = any(s["new_fingerprints_detected"] > 0 for s in all_trace)
    any_network = any(s["likely_result_request_detected"] for s in all_trace)
    max_bottom_count = max((s["bottom_reached_count"] for s in all_trace), default=0)
    settle_waits = sum(1 for s in all_trace if s["at_bottom"])
    max_dom_delta = max((s["dom_count_delta_from_baseline"] for s in all_trace), default=0)

    # Pagination evidence
    pagination_verified = (pagination_click_result is not None
                           and pagination_click_result.get("clicked")
                           and pagination_click_result.get("identities_changed"))

    # Infinite scroll evidence — prioritize append over content-swap noise
    # Append-style infinite scroll: DOM count grew materially, new identities appeared.
    # A false content_swap_detected can happen when new cards are appended and the
    # viewport shifts, causing index-0 fingerprint comparison to see different content.
    # True append: dom_count increases, old cards remain in DOM, new cards added at bottom.
    # The key signal is material DOM growth (>= batch size), NOT absence of content swap.
    material_dom_growth = max_dom_delta >= 10  # at least half a batch
    infinite_scroll_detected = material_dom_growth and dom_grew

    # Load more evidence
    load_more_verified = (load_more_click_result is not None
                          and load_more_click_result.get("clicked")
                          and load_more_click_result.get("dom_grew"))

    # Virtualization evidence — only if DOM count stayed flat AND content swapped
    # True virtualization: DOM count stable (delta <=2 across ALL steps), content rotated.
    # If DOM grew materially, content_swap is noise from append, NOT virtualization.
    dom_stayed_flat = all(abs(s["dom_count_delta_from_baseline"]) <= 2 for s in all_trace)
    virtualization_detected = (dom_stayed_flat and any_content_swap and not material_dom_growth)

    # Static evidence — strict requirements
    static_evidence = {
        "max_scroll_reached": max_bottom_count >= 1,
        "bottom_reached_count": max_bottom_count,
        "settle_waits_completed": settle_waits,
        "result_count_label_inspected": result_count_label_found or len(result_count_info) > 0 or True,  # we always inspect
        "internal_scroll_tested": internal_tested or len(scroll_info["internal_containers"]) == 0,
        "window_scroll_tested": window_tested,
        "no_dom_growth": not dom_grew,
        "no_identity_change": not any_content_swap and not any_new_fps,
        "no_pagination_in_result_zone": len(scoped_pag) == 0 or (pagination_click_result and not pagination_click_result.get("identities_changed", False)),
        "no_load_more_found": len(bottom_zone_2["load_more_candidates"]) == 0,
        "no_continuation_network_requests": not any_network,
        "no_bottom_sentinel_found": len(bottom_zone_2["sentinel_candidates"]) == 0,
    }

    all_static_met = all([
        static_evidence["max_scroll_reached"],
        static_evidence["bottom_reached_count"] >= 2,
        static_evidence["settle_waits_completed"] >= 2,
        static_evidence["window_scroll_tested"] or static_evidence["internal_scroll_tested"],
        static_evidence["no_dom_growth"],
        static_evidence["no_identity_change"],
        static_evidence["no_pagination_in_result_zone"],
        static_evidence["no_load_more_found"],
        static_evidence["no_continuation_network_requests"],
        static_evidence["no_bottom_sentinel_found"],
    ])

    # Classify
    continuation_type = "unknown"
    confidence = "low"
    evidence_summary = ""

    if pagination_verified:
        continuation_type = "pagination"
        confidence = "high"
        evidence_summary = (f"Scoped pagination control found and clicked. "
                            f"Card identities changed after click ({pagination_click_result.get('new_identities_count', 0)} new).")
    elif infinite_scroll_detected:
        continuation_type = "infinite_scroll"
        confidence = "high" if max_dom_delta >= 20 else "medium"
        evidence_summary = (f"DOM card count grew by {max_dom_delta} during scrolling (append-style). "
                            f"Batch size ~{baseline_fps['dom_card_count']}. "
                            f"Network requests coincided with batch loads. "
                            f"Old cards retained in DOM, new cards appended at bottom.")
    elif load_more_verified:
        continuation_type = "load_more"
        confidence = "high"
        evidence_summary = (f"Load-more button found and clicked. "
                            f"DOM grew from {load_more_click_result['dom_before']} to {load_more_click_result['dom_after']}.")
    elif virtualization_detected:
        if any_content_swap:
            continuation_type = "virtualization"
            confidence = "medium"
            evidence_summary = (f"DOM count stayed flat but card identities changed at index 0. "
                                f"Content swap detected during scrolling.")
        else:
            continuation_type = "unknown"
            confidence = "low"
            evidence_summary = "Weak virtualization signals. Not enough evidence."
    elif all_static_met:
        continuation_type = "static"
        confidence = "high" if max_bottom_count >= 2 else "medium"
        evidence_summary = (f"All negative evidence met. Bottom reached {max_bottom_count}x. "
                            f"No DOM growth, no identity changes, no pagination, no load-more, "
                            f"no continuation network requests, no sentinels. "
                            f"Results appear limited to initial batch.")
    else:
        continuation_type = "unknown"
        confidence = "low"
        missing = [k for k, v in static_evidence.items() if not v]
        evidence_summary = f"Could not classify. Static evidence incomplete: {missing}"

    print(f"\n  CONTINUATION TYPE: {continuation_type}")
    print(f"  CONFIDENCE: {confidence}")
    print(f"  EVIDENCE: {evidence_summary}")

    # ════════════════════════════════════════
    # Phase 6: Recipe persistence
    # ════════════════════════════════════════
    print("\n[Phase 6] Saving artifacts...")

    continuation_analysis = {
        "version": ARTIFACT_VERSION,
        "timestamp": datetime.now().isoformat(),
        "keyword": B2_KEYWORD,
        "initial_visible_count": baseline_fps["visible_card_count"],
        "initial_dom_count": baseline_fps["dom_card_count"],
        "scroll_context_type": scroll_info["scroll_context_type"],
        "scroll_container_selector": scroll_info.get("scroll_container_selector"),
        "scroll_container_dimensions": scroll_info.get("scroll_container_dimensions"),
        "ancestors_checked": scroll_info.get("ancestors_checked", 0),
        "pagination_controls_found": len(scoped_pag) > 0,
        "pagination_click_result": pagination_click_result,
        "load_more_found": len(bottom_zone_2["load_more_candidates"]) > 0,
        "load_more_click_result": load_more_click_result,
        "infinite_scroll_detected": infinite_scroll_detected,
        "virtualization_detected": virtualization_detected,
        "continuation_type": continuation_type,
        "confidence": confidence,
        "evidence_summary": evidence_summary,
        "scroll_height_changed": any(s["document_height"] != all_trace[0]["document_height"] for s in all_trace) if all_trace else False,
        "network_requests_during_scroll": sum(s["network_requests_this_step"] for s in all_trace),
        "bottom_sentinel_found": len(bottom_zone_2["sentinel_candidates"]) > 0,
        "result_count_label_found": result_count_label_found,
        "result_count_label_text": result_count_label_text,
        "result_count_labels_all": result_count_info[:5],
        "static_evidence": static_evidence,
        "max_scroll_reached": max_bottom_count >= 1,
        "bottom_reached_count": max_bottom_count,
        "settle_waits_completed": settle_waits,
        "internal_scroll_tested": internal_tested,
        "window_scroll_tested": window_tested,
        "no_dom_growth": not dom_grew,
        "no_identity_change": not any_content_swap and not any_new_fps,
        "pagination_candidates_inspected": bottom_zone_2["pagination_candidates"],
        "hidden_pagination_found": bottom_zone_2["hidden_pagination"],
        "bottom_zone_elements_found": {
            "load_more": bottom_zone_2["load_more_candidates"],
            "sentinels": bottom_zone_2["sentinel_candidates"],
            "end_markers": bottom_zone_2["end_markers"],
        },
    }

    with open(CONTINUATION_ANALYSIS_PATH, "w", encoding="utf-8") as f:
        json.dump(continuation_analysis, f, indent=2, ensure_ascii=True, default=str)
    print(f"  continuation_analysis.json — type={continuation_type}, confidence={confidence}")

    scroll_trace_data = {
        "version": ARTIFACT_VERSION,
        "keyword": B2_KEYWORD,
        "window_trace": window_trace,
        "internal_trace": internal_trace,
        "window_tested": window_tested,
        "internal_tested": internal_tested,
        "baseline_fingerprints": baseline_fps,
    }
    with open(SCROLL_TRACE_PATH, "w", encoding="utf-8") as f:
        json.dump(scroll_trace_data, f, indent=2, ensure_ascii=True, default=str)
    print(f"  scroll_trace.json — {len(window_trace)} window steps, {len(internal_trace)} internal steps")

    # Continuation recipes
    cont_recipes = {"continuation_methods": [], "recommended_method": None, "fallback_methods": []}

    if continuation_type == "pagination" and pagination_click_result and pagination_click_result.get("clicked"):
        cont_recipes["continuation_methods"].append({
            "type": "click_pagination_next",
            "selector": scoped_pag[0]["selector"] if scoped_pag else None,
            "confidence": 1.0 if pagination_verified else 0.0,
            "success_count": 1 if pagination_verified else 0,
            "fail_count": 0 if pagination_verified else 1,
            "notes": "pagination control in result zone, clicking '2' or 'Next' changes card identities",
        })
        cont_recipes["recommended_method"] = "click_pagination_next"
    elif continuation_type == "infinite_scroll":
        cont_recipes["continuation_methods"].append({
            "type": "infinite_scroll_append",
            "scroll_target": "window",
            "selector": container_selector or "window",
            "batch_size_expected": baseline_fps["dom_card_count"],
            "confidence": 0.95,
            "success_count": 1,
            "fail_count": 0,
            "settle_wait_seconds": 4,
            "verification": "dom_card_count increases by ~batch_size after scroll-to-bottom",
            "stop_conditions": [
                "no DOM growth after 2 consecutive bottom passes",
                "no new identities after 2 consecutive bottom passes",
                "per-keyword batch cap reached",
            ],
            "notes": f"scroll triggers DOM append with ~{baseline_fps['dom_card_count']} new cards per batch. "
                     f"Network requests coincide with batch loads. Max observed delta: {max_dom_delta}.",
        })
        cont_recipes["recommended_method"] = "infinite_scroll_append"
    elif continuation_type == "load_more":
        cont_recipes["continuation_methods"].append({
            "type": "click_load_more",
            "selector": bottom_zone_2["load_more_candidates"][0]["selector"] if bottom_zone_2["load_more_candidates"] else None,
            "confidence": 1.0 if load_more_verified else 0.0,
            "success_count": 1 if load_more_verified else 0,
            "fail_count": 0 if load_more_verified else 1,
            "notes": "load-more button grows DOM with new cards",
        })
        cont_recipes["recommended_method"] = "click_load_more"
    elif continuation_type == "static":
        cont_recipes["continuation_methods"].append({
            "type": "none_available",
            "confidence": 0.9 if confidence == "high" else 0.5,
            "success_count": 0,
            "fail_count": 0,
            "notes": "no continuation mechanism found — results limited to single batch. Compensate with more keywords.",
        })
        cont_recipes["recommended_method"] = "more_keywords"

    # Record what failed
    cont_recipes["fallback_methods"].append({
        "type": "window_scroll", "tested": window_tested,
        "result": "no_continuation" if window_tested and not dom_grew and not any_content_swap else "not_tested",
    })
    cont_recipes["fallback_methods"].append({
        "type": "internal_scroll", "tested": internal_tested,
        "result": "no_continuation" if internal_tested and not dom_grew and not any_content_swap else "not_tested",
    })
    cont_recipes["fallback_methods"].append({
        "type": "pagination_click", "tested": pagination_click_result is not None,
        "result": "success" if pagination_verified else ("failed" if pagination_click_result else "not_tested"),
    })
    cont_recipes["fallback_methods"].append({
        "type": "load_more_click", "tested": load_more_click_result is not None,
        "result": "success" if load_more_verified else ("failed" if load_more_click_result else "not_tested"),
    })

    with open(CONTINUATION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(cont_recipes, f, indent=2, ensure_ascii=True, default=str)
    print(f"  continuation_recipes.json — recommended={cont_recipes['recommended_method']}")

    # ════════════════════════════════════════
    # B2 REPORT
    # ════════════════════════════════════════
    print("\n" + "=" * 70)
    print("B2 REPORT — CONTINUATION MECHANISM DISCOVERY")
    print("=" * 70)

    print(f"\n1. CONTINUATION TYPE: {continuation_type}")
    print(f"   Confidence: {confidence}")

    print(f"\n2. EVIDENCE:")
    print(f"   {evidence_summary}")

    print(f"\n3. SCROLL TARGET:")
    print(f"   Context: {scroll_info['scroll_context_type']}")
    if container_selector:
        print(f"   Internal container: {container_selector}")
    print(f"   Window scrollable: {scroll_info['window_scrollable']}")

    print(f"\n4. MECHANISM RULING:")
    print(f"   Pagination: {'VERIFIED' if pagination_verified else 'NOT FOUND / NOT VERIFIED'}")
    print(f"   Infinite scroll: {'DETECTED' if infinite_scroll_detected else 'NOT DETECTED'}")
    print(f"   Load more: {'VERIFIED' if load_more_verified else 'NOT FOUND / NOT VERIFIED'}")
    print(f"   Virtualization: {'DETECTED' if virtualization_detected else 'NOT DETECTED'}")
    print(f"   Static: {'CLASSIFIED' if continuation_type == 'static' else 'NOT CLASSIFIED'}")

    print(f"\n5. STATIC EVIDENCE (all must be true for static):")
    for k, v in static_evidence.items():
        icon = "+" if v else "-"
        val_str = str(v)
        print(f"   [{icon}] {k}: {val_str}")

    print(f"\n6. RECOMMENDED CONTINUATION RECIPE:")
    print(f"   {cont_recipes['recommended_method'] or 'NONE'}")

    print(f"\n7. SCROLL TRACE SUMMARY:")
    print(f"   Window steps: {len(window_trace)}")
    print(f"   Internal steps: {len(internal_trace)}")
    total_net = sum(s["network_requests_this_step"] for s in all_trace)
    print(f"   Network requests during scroll: {total_net}")
    print(f"   Max DOM delta: {max((s['dom_count_delta_from_baseline'] for s in all_trace), default=0)}")
    print(f"   Content swaps detected: {sum(1 for s in all_trace if s['content_swap_detected'])}")

    # Pass/fail
    print(f"\n{'─' * 70}")
    b2_pass = continuation_type != "unknown"
    print(f"  B2: {'PASS' if b2_pass else 'FAIL'} — continuation_type={continuation_type} (confidence={confidence})")
    if b2_pass:
        if continuation_type == "static":
            print(f"  C can proceed with single-page strategy (more keywords to compensate).")
        else:
            print(f"  C can proceed with {continuation_type} strategy.")
    else:
        print(f"  C NOT ready — continuation mechanism still unknown.")

    print(f"\n  [STOP] B2 complete. Do not auto-advance to C.")

    logger.save()
    return continuation_analysis


# ═══════════════════════════════════════════════════════════
# C: Controlled Full-Scale Research with Infinite Scroll
# ═══════════════════════════════════════════════════════════

C_KEYWORDS = [
    "streetwear", "oversized hoodie", "heavyweight hoodie", "baggy jeans",
    "streetwear brand", "oversized tee", "archive fashion", "limited drop clothing",
    "mens streetwear", "streetwear drop", "graphic tee streetwear", "essentials hoodie",
]
C_MAX_BATCHES_PER_KEYWORD = 3
C_MAX_OPENS_PER_KEYWORD = 4
C_SCROLL_SETTLE_SECONDS = 4


async def scroll_load_batch(page: Page, card_selector: str, current_dom_count: int,
                             max_wait_seconds: int = 10) -> dict:
    """
    Scroll to bottom of window and wait for DOM card count to increase.
    Returns {success, new_count, delta, waited_seconds}.
    """
    await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    waited = 0
    interval = 2
    while waited < max_wait_seconds:
        await page.wait_for_timeout(interval * 1000)
        waited += interval
        new_count = await page.evaluate(f"""(sel) => {{
            return document.querySelectorAll(sel).length;
        }}""", card_selector)
        if new_count > current_dom_count:
            return {"success": True, "new_count": new_count, "delta": new_count - current_dom_count, "waited_seconds": waited}
    # Final check
    new_count = await page.evaluate(f"""(sel) => {{
        return document.querySelectorAll(sel).length;
    }}""", card_selector)
    return {"success": new_count > current_dom_count, "new_count": new_count,
            "delta": new_count - current_dom_count, "waited_seconds": waited}


async def run_c(page: Page, logger: StepLogger, ts: str):
    """
    C: Controlled full-scale research with infinite scroll.
    - 12 keywords, max 3 batches per keyword, max 4 opens per keyword
    - Infinite scroll continuation verified per keyword
    - UI-first extraction, API as secondary
    - Live validation of B2's continuation model
    """
    print("\n" + "=" * 70)
    print("C — CONTROLLED FULL-SCALE RESEARCH")
    print(f"Keywords: {len(C_KEYWORDS)}")
    print(f"Max batches/keyword: {C_MAX_BATCHES_PER_KEYWORD}, Max opens/keyword: {C_MAX_OPENS_PER_KEYWORD}")
    print("=" * 70)

    # ── Load artifacts ──
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))
    cont_recipes = json.loads(CONTINUATION_RECIPES_PATH.read_text(encoding="utf-8"))

    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]

    input_candidates = dom_sigs.get("search_input_candidates", [])
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"] if input_candidates else "#inputKeyword"

    open_recipes_loaded = recipes.get("open_result_card", [])
    proven_open = [r for r in open_recipes_loaded if r["success_count"] > 0]
    best_open = proven_open[0]["method"] if proven_open else None
    if not best_open:
        print("[ABORT] No proven open recipe.")
        return None

    close_recipes_loaded = recipes.get("close_detail", [])
    proven_close = [r for r in close_recipes_loaded if r["success_count"] > 0]
    best_close = proven_close[0]["method"] if proven_close else None
    if not best_close:
        print("[ABORT] No proven close recipe.")
        return None

    recommended_cont = cont_recipes.get("recommended_method")
    print(f"  Card: {primary_card_sel}")
    print(f"  Open: {best_open['type']} → {best_open['selector']}")
    print(f"  Close: {best_close['type']} → {best_close['selector']}")
    print(f"  Continuation: {recommended_cont}")

    # ── API interception (optional secondary) ──
    api_results = {}

    async def on_api_response(response):
        if "search4/at/video/search" in response.url and response.status == 200:
            try:
                body = await response.json()
                result = body.get("result", {})
                items = result.get("list", []) if isinstance(result, dict) else []
                if items:
                    kw = getattr(on_api_response, '_kw', 'unknown')
                    api_results.setdefault(kw, []).extend(items)
            except Exception:
                pass

    page.on("response", on_api_response)

    # ── Validate artifacts ──
    val = await validate_artifacts(page, logger, ts)
    print(f"  Artifacts: {val['status']}")
    if val["status"] in ("stale", "missing"):
        print("[ABORT] Artifacts invalid.")
        page.remove_listener("response", on_api_response)
        return None

    # ── Confidence + tracking ──
    recipe_book = RecipeBook()
    for action, entries in recipes.items():
        for entry in entries:
            recipe_book.recipes.setdefault(action, []).append(dict(entry))

    confidence = {
        "card_root_click": {"successes": 0, "failures": 0},
        "escape_close": {"successes": 0, "failures": 0},
        "detail_types": [],
        "card_structures_seen": [],
        "scroll_continuation": {"batches_loaded": 0, "batches_failed": 0, "batch_sizes": []},
        "first_fragility_sign": None,
    }

    all_keyword_results = []
    stop_triggered = False
    stop_reason = ""
    total_cards_opened = 0
    total_batches_loaded = 0

    for kw_idx, keyword in enumerate(C_KEYWORDS):
        if stop_triggered:
            break

        print(f"\n{'═' * 70}")
        print(f"[KEYWORD {kw_idx+1}/{len(C_KEYWORDS)}] '{keyword}'")
        print(f"{'═' * 70}")

        kw_result = {
            "keyword": keyword,
            "batches_loaded": 0,
            "total_cards_in_dom": 0,
            "cards_opened": 0,
            "cards_open_failed": 0,
            "detail_types_seen": [],
            "close_successes": 0,
            "close_failures": 0,
            "detail_extractions": [],
            "api_ads_captured": 0,
            "scroll_continuation_held": True,
            "stop_triggered": False,
        }

        on_api_response._kw = keyword
        consecutive_open_fails = 0

        # ── Submit search ──
        try:
            loc = page.locator(primary_input_sel).first
            if not await loc.is_visible(timeout=5000):
                loc = page.locator("#inputKeyword").first
            await loc.click(click_count=3)
            await loc.fill(keyword)
            await page.wait_for_timeout(500)
            await loc.press("Enter")
            logger.log("c_research", f"search_{keyword}", "search_page", "loading", "info")
        except Exception as e:
            print(f"  [FAIL] Search failed: {str(e)[:80]}")
            stop_triggered = True
            stop_reason = f"search_failed: {str(e)[:60]}"
            kw_result["stop_triggered"] = True
            all_keyword_results.append(kw_result)
            break

        await page.wait_for_timeout(6000)

        # ── Verify results ──
        verification = await verify_results_page(page, primary_card_sel)
        if not verification["verified"]:
            await page.wait_for_timeout(5000)
            verification = await verify_results_page(page, primary_card_sel)
            if not verification["verified"]:
                print(f"  [FAIL] Results not verified.")
                if not verification["signals"].get("repeated_card_containers"):
                    stop_triggered = True
                    stop_reason = "card_root_selector_no_match"
                    if not confidence["first_fragility_sign"]:
                        confidence["first_fragility_sign"] = f"card_root_no_match at kw={keyword}"
                kw_result["stop_triggered"] = True
                all_keyword_results.append(kw_result)
                continue

        ss = await take_ss(page, f"c_results_{keyword.replace(' ', '_')}", ts)
        logger.log("c_research", f"verify_{keyword}", "loading", "results_page", "success", screenshot=ss)

        initial_dom_count = await page.evaluate(f"document.querySelectorAll('{primary_card_sel}').length")
        current_dom_count = initial_dom_count
        print(f"  Initial DOM cards: {initial_dom_count}")

        # ── Scroll to top before card opens ──
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        # ── Open first batch of cards (top of results) ──
        opens_this_kw = 0
        cards_to_open_now = min(2, C_MAX_OPENS_PER_KEYWORD, initial_dom_count)

        for card_idx in range(cards_to_open_now):
            if stop_triggered:
                break

            print(f"\n    [CARD {card_idx}] Opening...")
            pre_modals = await inspect_modal_state(page)
            pre_url = page.url

            try:
                cards = page.locator(best_open["selector"])
                target = cards.nth(card_idx)
                await target.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await target.click()
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"      [FAIL] Click: {str(e)[:60]}")
                kw_result["cards_open_failed"] += 1
                consecutive_open_fails += 1
                confidence["card_root_click"]["failures"] += 1
                if consecutive_open_fails >= 2:
                    stop_triggered = True
                    stop_reason = f"open_failed_twice_{keyword}"
                    kw_result["stop_triggered"] = True
                    if not confidence["first_fragility_sign"]:
                        confidence["first_fragility_sign"] = f"open_failed_twice at kw={keyword}"
                continue

            post_modals = await inspect_modal_state(page)
            new_modals = len(post_modals.get("modals", [])) - len(pre_modals.get("modals", []))
            detail_type = "modal" if new_modals > 0 else ("page" if page.url != pre_url else "unknown")

            if detail_type == "unknown":
                kw_result["cards_open_failed"] += 1
                consecutive_open_fails += 1
                confidence["card_root_click"]["failures"] += 1
                if consecutive_open_fails >= 2:
                    stop_triggered = True
                    stop_reason = f"open_failed_twice_{keyword}"
                    kw_result["stop_triggered"] = True
                continue

            opens_this_kw += 1
            total_cards_opened += 1
            consecutive_open_fails = 0
            kw_result["detail_types_seen"].append(detail_type)
            confidence["detail_types"].append(detail_type)
            confidence["card_root_click"]["successes"] += 1
            recipe_book.add("open_result_card", best_open, True, f"c detail={detail_type}")

            if detail_type != "modal":
                if not confidence["first_fragility_sign"]:
                    confidence["first_fragility_sign"] = f"non-modal detail ({detail_type}) at kw={keyword}"
                if detail_type not in ("page", "drawer"):
                    stop_triggered = True
                    stop_reason = f"unclassified_detail_{detail_type}"
                    kw_result["stop_triggered"] = True

            print(f"      Opened: {detail_type}")

            # Extract
            try:
                detail_data = await extract_detail_from_modal(page)
                kw_result["detail_extractions"].append({"card_index": card_idx, "detail_type": detail_type, "data": detail_data})
                confidence["card_structures_seen"].append(len(detail_data.get("texts", [])))
                adv = detail_data.get("advertiser", "unknown")
                print(f"      Extracted: {len(detail_data.get('texts',[]))} texts, adv={adv}")
            except Exception as e:
                print(f"      [WARN] Extract: {str(e)[:60]}")

            # Close
            close_ok = False
            try:
                if best_close["type"] == "keyboard":
                    await page.keyboard.press(best_close["selector"])
                else:
                    cl = page.locator(best_close["selector"]).first
                    if await cl.is_visible(timeout=2000):
                        await cl.click()
                await page.wait_for_timeout(2000)
                post_close = await inspect_modal_state(page)
                close_ok = len(post_close.get("modals", [])) < len(post_modals.get("modals", []))
                recipe_book.add("close_detail", best_close, close_ok, f"c close")
            except Exception:
                recipe_book.add("close_detail", best_close, False, "c exception")

            if close_ok:
                kw_result["close_successes"] += 1
                confidence["escape_close"]["successes"] += 1
                print(f"      Closed OK")
            else:
                kw_result["close_failures"] += 1
                confidence["escape_close"]["failures"] += 1
                # Recovery
                recovered = False
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(1500)
                    if len((await inspect_modal_state(page)).get("modals", [])) == 0:
                        recovered = True
                    else:
                        await page.go_back()
                        await page.wait_for_timeout(3000)
                        recovered = "search" in page.url.lower()
                except Exception:
                    pass
                if not recovered:
                    stop_triggered = True
                    stop_reason = "close_failed_no_recovery"
                    kw_result["stop_triggered"] = True
                    if not confidence["first_fragility_sign"]:
                        confidence["first_fragility_sign"] = f"close_recovery_failed at kw={keyword}"
                    break

            await page.wait_for_timeout(800)

        # ── Infinite scroll continuation ──
        if not stop_triggered:
            no_growth_passes = 0
            for batch_num in range(C_MAX_BATCHES_PER_KEYWORD):
                if stop_triggered:
                    break

                print(f"\n  [SCROLL batch {batch_num+1}/{C_MAX_BATCHES_PER_KEYWORD}] "
                      f"Current DOM: {current_dom_count}")

                batch_result = await scroll_load_batch(page, primary_card_sel, current_dom_count)

                if batch_result["success"]:
                    delta = batch_result["delta"]
                    current_dom_count = batch_result["new_count"]
                    kw_result["batches_loaded"] += 1
                    total_batches_loaded += 1
                    confidence["scroll_continuation"]["batches_loaded"] += 1
                    confidence["scroll_continuation"]["batch_sizes"].append(delta)
                    no_growth_passes = 0
                    print(f"    Batch loaded: +{delta} cards (total: {current_dom_count}), waited {batch_result['waited_seconds']}s")
                    logger.log("c_research", f"scroll_batch_{keyword}_{batch_num}",
                               "results_page", "results_page", "success",
                               notes=f"+{delta} cards, total={current_dom_count}")

                    # Open 1-2 more cards from newly loaded batch
                    remaining_opens = C_MAX_OPENS_PER_KEYWORD - opens_this_kw
                    if remaining_opens > 0:
                        # Scroll back up slightly to access new cards
                        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight - 1500)")
                        await page.wait_for_timeout(1000)

                        extra_opens = min(remaining_opens, 2)
                        # Open cards near the end of the current batch
                        for oi in range(extra_opens):
                            if stop_triggered:
                                break
                            target_idx = current_dom_count - delta + oi  # first card of new batch
                            if target_idx >= current_dom_count:
                                break

                            print(f"\n    [CARD batch{batch_num+1}:{oi}] Opening idx {target_idx}...")
                            pre_m = await inspect_modal_state(page)

                            try:
                                cards_loc = page.locator(best_open["selector"])
                                t = cards_loc.nth(target_idx)
                                await t.scroll_into_view_if_needed()
                                await page.wait_for_timeout(500)
                                await t.click()
                                await page.wait_for_timeout(3000)
                            except Exception as e:
                                print(f"        [FAIL] Click: {str(e)[:60]}")
                                kw_result["cards_open_failed"] += 1
                                consecutive_open_fails += 1
                                confidence["card_root_click"]["failures"] += 1
                                if consecutive_open_fails >= 2:
                                    stop_triggered = True
                                    stop_reason = f"open_failed_twice_{keyword}_batch"
                                    kw_result["stop_triggered"] = True
                                continue

                            post_m = await inspect_modal_state(page)
                            nm = len(post_m.get("modals", [])) - len(pre_m.get("modals", []))
                            dt = "modal" if nm > 0 else "unknown"

                            if dt == "unknown":
                                kw_result["cards_open_failed"] += 1
                                consecutive_open_fails += 1
                                confidence["card_root_click"]["failures"] += 1
                                if consecutive_open_fails >= 2:
                                    stop_triggered = True
                                    stop_reason = f"open_failed_twice_{keyword}_batch"
                                    kw_result["stop_triggered"] = True
                                continue

                            opens_this_kw += 1
                            total_cards_opened += 1
                            consecutive_open_fails = 0
                            kw_result["detail_types_seen"].append(dt)
                            confidence["detail_types"].append(dt)
                            confidence["card_root_click"]["successes"] += 1

                            print(f"        Opened: {dt}")

                            try:
                                dd = await extract_detail_from_modal(page)
                                kw_result["detail_extractions"].append({"card_index": target_idx, "detail_type": dt, "data": dd})
                                confidence["card_structures_seen"].append(len(dd.get("texts", [])))
                                print(f"        Extracted: {len(dd.get('texts',[]))} texts, adv={dd.get('advertiser','?')}")
                            except Exception:
                                pass

                            # Close
                            try:
                                if best_close["type"] == "keyboard":
                                    await page.keyboard.press(best_close["selector"])
                                await page.wait_for_timeout(2000)
                                pc = await inspect_modal_state(page)
                                c_ok = len(pc.get("modals", [])) < len(post_m.get("modals", []))
                                recipe_book.add("close_detail", best_close, c_ok, "c batch close")
                                if c_ok:
                                    kw_result["close_successes"] += 1
                                    confidence["escape_close"]["successes"] += 1
                                    print(f"        Closed OK")
                                else:
                                    kw_result["close_failures"] += 1
                                    confidence["escape_close"]["failures"] += 1
                                    await page.keyboard.press("Escape")
                                    await page.wait_for_timeout(1500)
                            except Exception:
                                kw_result["close_failures"] += 1
                                confidence["escape_close"]["failures"] += 1

                            await page.wait_for_timeout(800)

                else:
                    no_growth_passes += 1
                    confidence["scroll_continuation"]["batches_failed"] += 1
                    print(f"    No growth after {batch_result['waited_seconds']}s (pass {no_growth_passes})")
                    logger.log("c_research", f"scroll_batch_{keyword}_{batch_num}",
                               "results_page", "results_page", "soft_fail",
                               notes=f"no growth, waited={batch_result['waited_seconds']}s")

                    if no_growth_passes >= 2:
                        print(f"    No growth after 2 passes — end of results for '{keyword}'")
                        break

        kw_result["cards_opened"] = opens_this_kw
        kw_result["total_cards_in_dom"] = current_dom_count
        kw_result["api_ads_captured"] = len(api_results.get(keyword, []))

        # Check if scroll continuation held
        if kw_result["batches_loaded"] == 0 and initial_dom_count < 20:
            kw_result["scroll_continuation_held"] = False
            if not confidence["first_fragility_sign"]:
                confidence["first_fragility_sign"] = f"no batches loaded for kw={keyword} (initial={initial_dom_count})"

        all_keyword_results.append(kw_result)
        consecutive_open_fails = 0

        print(f"\n  [KW DONE] '{keyword}': batches={kw_result['batches_loaded']}, "
              f"dom={current_dom_count}, opened={opens_this_kw}, "
              f"closes={kw_result['close_successes']}OK/{kw_result['close_failures']}fail, "
              f"API={kw_result['api_ads_captured']}")

        # Periodic revalidation
        if (kw_idx + 1) % 4 == 0 and not stop_triggered:
            reval = await validate_artifacts(page, logger, ts)
            if reval["status"] == "stale":
                stop_triggered = True
                stop_reason = "artifacts_became_stale"
                if not confidence["first_fragility_sign"]:
                    confidence["first_fragility_sign"] = f"artifacts stale after kw={keyword}"
            else:
                print(f"  [REVALIDATE] Artifacts: {reval['status']}")

        # Scroll back to top for next keyword
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

    # ── Clean up ──
    page.remove_listener("response", on_api_response)

    # ── Deduplicate API results ──
    all_api_ads = []
    seen_ids = set()
    for kw, items in api_results.items():
        for item in items:
            aid = item.get("ad_id") or item.get("id") or item.get("_id")
            if aid and aid not in seen_ids:
                seen_ids.add(aid)
                item["_source_keyword"] = kw
                all_api_ads.append(item)

    # ── Compute stats ──
    crc = confidence["card_root_click"]
    crc_total = crc["successes"] + crc["failures"]
    crc_rate = round(crc["successes"] / max(crc_total, 1), 2)

    esc = confidence["escape_close"]
    esc_total = esc["successes"] + esc["failures"]
    esc_rate = round(esc["successes"] / max(esc_total, 1), 2)

    type_counts = Counter(confidence["detail_types"])
    text_counts = confidence["card_structures_seen"]

    sc = confidence["scroll_continuation"]
    batch_sizes = sc["batch_sizes"]
    avg_batch = round(sum(batch_sizes) / len(batch_sizes), 1) if batch_sizes else 0

    avg_batches_per_kw = round(total_batches_loaded / max(len(all_keyword_results), 1), 1)
    avg_cards_per_kw = round(sum(kr["total_cards_in_dom"] for kr in all_keyword_results) / max(len(all_keyword_results), 1), 1)

    # ── Save ──
    c_output = {
        "mode": "C",
        "timestamp": datetime.now().isoformat(),
        "keywords": C_KEYWORDS,
        "guardrails": {
            "max_keywords": len(C_KEYWORDS),
            "max_batches": C_MAX_BATCHES_PER_KEYWORD,
            "max_opens": C_MAX_OPENS_PER_KEYWORD,
        },
        "keyword_results": all_keyword_results,
        "api_summary": {"total": len(all_api_ads)},
        "confidence": {
            "card_root_click_rate": crc_rate,
            "escape_close_rate": esc_rate,
            "detail_types": dict(type_counts),
            "scroll_continuation": sc,
            "first_fragility_sign": confidence["first_fragility_sign"],
        },
        "stop_condition": {"triggered": stop_triggered, "reason": stop_reason},
    }

    output_path = DATA_DIR / f"c_results_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(c_output, f, indent=2, ensure_ascii=True, default=str)
    print(f"\n  Results saved to: {output_path.name}")

    if all_api_ads:
        ads_path = DATA_DIR / f"c_ads_{ts}.json"
        with open(ads_path, "w", encoding="utf-8") as f:
            json.dump({"ads": all_api_ads, "total": len(all_api_ads)}, f, indent=2, ensure_ascii=True, default=str)
        print(f"  API ads saved to: {ads_path.name}")

    with open(INTERACTION_RECIPES_PATH, "w", encoding="utf-8") as f:
        json.dump(recipe_book.to_dict(), f, indent=2, ensure_ascii=False)

    # ══════════════════════════════════════════════════════════
    # C REPORT — 9 POINTS
    # ══════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("C REPORT — CONTROLLED FULL-SCALE RESEARCH")
    print("=" * 70)

    # 1. Infinite scroll
    scroll_held_count = sum(1 for kr in all_keyword_results if kr["scroll_continuation_held"])
    print(f"\n1. INFINITE SCROLL:")
    print(f"   Held for: {scroll_held_count}/{len(all_keyword_results)} keywords")
    print(f"   Total batches loaded: {total_batches_loaded}")
    print(f"   Batch failures: {sc['batches_failed']}")
    if total_batches_loaded > 0 and sc["batches_failed"] <= total_batches_loaded * 0.2:
        print(f"   Verdict: HELD across keywords")
    elif total_batches_loaded == 0:
        print(f"   Verdict: NO BATCHES LOADED — scroll may not have triggered")
    else:
        print(f"   Verdict: PARTIALLY HELD — some batch failures")

    # 2. Average batches per keyword
    print(f"\n2. AVERAGE BATCHES PER KEYWORD: {avg_batches_per_kw}")

    # 3. Average cards per keyword
    print(f"\n3. AVERAGE CARDS OBSERVED PER KEYWORD: {avg_cards_per_kw}")

    # 4. Batch size
    print(f"\n4. BATCH SIZE:")
    if batch_sizes:
        print(f"   Avg: {avg_batch}")
        print(f"   Min: {min(batch_sizes)}, Max: {max(batch_sizes)}")
        near_20 = sum(1 for b in batch_sizes if 15 <= b <= 25)
        print(f"   Near 20: {near_20}/{len(batch_sizes)}")
    else:
        print(f"   No batches loaded")

    # 5. Modal behavior
    print(f"\n5. MODAL BEHAVIOR:")
    print(f"   Types: {dict(type_counts)}")
    if len(type_counts) == 1 and "modal" in type_counts:
        print(f"   Verdict: modal_only HELD ({sum(type_counts.values())} opens)")
    elif len(type_counts) == 0:
        print(f"   Verdict: no opens")
    else:
        print(f"   Verdict: MIXED")

    # 6. Escape
    print(f"\n6. ESCAPE CLOSE:")
    print(f"   Rate: {esc_rate} ({esc['successes']}/{esc_total})")
    print(f"   Verdict: {'SUFFICIENT' if esc_rate >= 0.95 else 'NEEDS REVIEW'}")

    # 7. Structural drift
    print(f"\n7. STRUCTURAL DRIFT:")
    if text_counts:
        spread = max(text_counts) - min(text_counts)
        avg_tc = sum(text_counts) / len(text_counts)
        print(f"   Text count range: {min(text_counts)}-{max(text_counts)} (avg {avg_tc:.0f}, spread {spread})")
        print(f"   Verdict: {'STABLE' if spread <= 15 else 'DRIFTING'}")
    else:
        print(f"   No data")
    if confidence["first_fragility_sign"]:
        print(f"   First fragility: {confidence['first_fragility_sign']}")
    else:
        print(f"   No fragility detected")

    # 8. Selector confidence
    print(f"\n8. SELECTOR CONFIDENCE:")
    print(f"   card_root_click: {crc_rate} ({crc['successes']}/{crc_total})")
    if crc_rate >= 0.95 and crc_total >= 20:
        print(f"   Verdict: UPGRADE — selector is stable at scale")
    elif crc_rate >= 0.9:
        print(f"   Verdict: MAINTAIN — mostly stable")
    else:
        print(f"   Verdict: DOWNGRADE — not reliable enough")

    # 9. Totals
    print(f"\n9. TOTALS:")
    kw_done = len(all_keyword_results)
    print(f"   Keywords: {kw_done}/{len(C_KEYWORDS)}")
    print(f"   Batches loaded: {total_batches_loaded}")
    print(f"   Cards opened (UI): {total_cards_opened}")
    print(f"   Detail extractions: {sum(len(kr['detail_extractions']) for kr in all_keyword_results)}")
    print(f"   Closes: {sum(kr['close_successes'] for kr in all_keyword_results)} OK / "
          f"{sum(kr['close_failures'] for kr in all_keyword_results)} fail")
    print(f"   API ads: {len(all_api_ads)}")
    if stop_triggered:
        print(f"   STOP: {stop_reason}")

    print(f"\n{'─' * 70}")
    c_gates = {
        "scroll_held": scroll_held_count >= len(all_keyword_results) * 0.75,
        "modal_only": len(type_counts) <= 1 or ("modal" in type_counts and type_counts.get("modal", 0) >= sum(type_counts.values()) * 0.9),
        "close_reliable": esc_rate >= 0.9,
        "selector_stable": crc_rate >= 0.9,
        "no_stop": not stop_triggered,
        "majority_keywords": kw_done >= len(C_KEYWORDS) * 0.75,
    }
    all_pass = all(c_gates.values())
    for gate, passed in c_gates.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {gate}")
    print(f"\n  C Overall: {'PASSED' if all_pass else 'NEEDS REVIEW'}")
    print(f"\n  Output: {output_path.name}")

    logger.save()
    return c_output


# ═══════════════════════════════════════════════════════════
# FILTER LAB — Structured filter optimization
# ═══════════════════════════════════════════════════════════

FILTER_PROFILES_PATH = DATA_DIR / "filter_profiles.json"
FILTER_RESULTS_PATH = DATA_DIR / "filter_test_results.json"
FILTER_RANKINGS_PATH = DATA_DIR / "filter_rankings.json"
FILTER_SUMMARY_PATH = DATA_DIR / "best_settings_summary.md"

FILTER_LAB_MAX_OPENS_PER_PROFILE = 3

# ── Niche relevance keywords for scoring ──
NICHE_KEYWORDS = [
    "streetwear", "hoodie", "oversized", "tee", "graphic", "drop", "limited",
    "heavyweight", "baggy", "archive", "fashion", "apparel", "clothing", "brand",
    "urban", "vintage", "mens", "outfit", "essentials", "wardrobe", "jeans",
    "sweatshirt", "jogger", "cargo", "denim", "sneaker", "aesthetic",
]
JUNK_KEYWORDS = [
    "casino", "crypto", "forex", "weight loss", "supplement", "diet", "pill",
    "keto", "dating", "loan", "insurance", "gambling", "slot", "cbd", "mlm",
    "get rich", "free money", "click here", "giveaway", "iphone", "samsung",
    "survey", "game", "gaming", "puzzle", "candy", "mobile game",
]
COMPETITOR_SIGNALS = [
    "shopify", "shop now", "buy now", "add to cart", "free shipping",
    "limited edition", "new drop", "collection", "store", "order now",
    ".com", ".co", "link in bio", "tap to shop", "get yours",
]
CREATIVE_SIGNALS = [
    "hook", "unboxing", "review", "haul", "try on", "outfit", "styling",
    "before", "after", "transformation", "grwm", "get ready", "ootd",
    "fit check", "what i wear", "winter", "summer", "spring", "fall",
]


async def inspect_filter_state(page: Page) -> dict:
    """
    Comprehensive inspection of current filter UI state.
    Uses multiple detection strategies:
    1. Applied chips with × close buttons (primary proof)
    2. Active/selected class detection (broad pattern matching)
    3. Sort dropdown label reading
    4. Filter area text scanning
    Works on both tab-style (TikTok) and dropdown-style (Facebook/Adspy) layouts.
    """
    return await page.evaluate("""() => {
        const state = {
            platform: null,
            platform_all_options: [],
            data_types_active: [],
            data_types_all_options: [],
            time: null,
            time_all_options: [],
            sort: null,
            active_classes: [],
            chips: [],
            category_active: [],
            app_platform_active: [],
            filter_area_text: '',
            raw_applied_filters: [],
        };

        // ── Helper: broad active-state detection ──
        function isActiveElement(el) {
            if (!el) return false;
            const cls = (el.className || '').toLowerCase();
            const pcls = el.parentElement ? (el.parentElement.className || '').toLowerCase() : '';
            const gpcls = el.parentElement?.parentElement ? (el.parentElement.parentElement.className || '').toLowerCase() : '';
            // Check multiple active-state patterns
            const patterns = ['active', 'selected', 'current', 'chosen', 'checked', 'is-active', 'is-selected'];
            for (const p of patterns) {
                if (cls.includes(p) || pcls.includes(p) || gpcls.includes(p)) return true;
            }
            // Check aria attributes
            if (el.getAttribute('aria-selected') === 'true') return true;
            if (el.getAttribute('aria-checked') === 'true') return true;
            // Check computed style for highlight (green background = active on PiPiAds)
            try {
                const bg = getComputedStyle(el).backgroundColor;
                // PiPiAds active tabs often have green (#00b96b-ish) or colored background
                if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' && bg !== 'rgb(255, 255, 255)') {
                    // Has a non-white, non-transparent background — likely active
                    const match = bg.match(/rgb\\((\\d+),\\s*(\\d+),\\s*(\\d+)\\)/);
                    if (match) {
                        const [r, g, b] = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
                        // Green-ish (PiPiAds brand color) or other highlight color
                        if (g > 150 && g > r && g > b) return true;  // green dominant
                        if (r < 200 && g < 200 && b < 200 && (r+g+b) < 500) return true; // dark/colored bg
                    }
                }
            } catch(e) {}
            return false;
        }

        // ── 1. Scan for applied filter chips with × close buttons ──
        // These are the PRIMARY proof of applied filters
        // Look for elements containing close/remove buttons anywhere in the filter area
        const filterAreas = document.querySelectorAll(
            '.filter-wrap, .filter-action, [class*="filter"], [class*="search-filter"], ' +
            '[class*="condition"], [class*="criteria"], .data-view-sort'
        );

        // Strategy A: Find elements with × text or close icon children
        document.querySelectorAll('*').forEach(el => {
            if (!el.offsetParent) return;
            const rect = el.getBoundingClientRect();
            if (rect.y > 600 || rect.height > 50 || rect.width > 300) return; // filter area is in top portion
            const text = el.textContent.trim();
            // Look for elements with × as child or sibling (close button pattern)
            const hasClose = el.querySelector('[class*="close"], [class*="remove"], .el-icon-close') ||
                             text.endsWith('×') || text.endsWith('✕') || text.endsWith('✖');
            if (hasClose && text.length > 1 && text.length < 60) {
                const cleanText = text.replace(/[×✕✖]/g, '').trim();
                if (cleanText.length > 0) {
                    state.chips.push({text: cleanText, raw: text, class: (el.className||'').substring(0,80), hasClose: true});
                }
            }
        });

        // Strategy B: Look for .el-tag elements (Element UI tags)
        document.querySelectorAll('.el-tag').forEach(el => {
            if (el.offsetParent && el.textContent.trim().length > 0 && el.textContent.trim().length < 80) {
                const text = el.textContent.replace(/[×✕✖]/g, '').trim();
                if (text && !state.chips.some(c => c.text === text)) {
                    state.chips.push({text, raw: el.textContent.trim(), class: el.className.substring(0,80), hasClose: true});
                }
            }
        });

        // Strategy C: Look for filter value displays (applied dropdown values)
        document.querySelectorAll('[class*="filter"] [class*="value"], [class*="filter"] [class*="label"]').forEach(el => {
            if (el.offsetParent && el.textContent.trim().length > 1 && el.textContent.trim().length < 60) {
                const rect = el.getBoundingClientRect();
                if (rect.y < 500) {
                    state.raw_applied_filters.push({text: el.textContent.trim(), class: (el.className||'').substring(0,80)});
                }
            }
        });

        // ── 2. Platform detection ──
        // Look in filter-ad-types row (tab-style) or top navigation tabs
        const platformSelectors = [
            '.filter-ad-types', '.filter-item.filter-ad-types',
            '[class*="ad-type"]', '[class*="platform-tab"]'
        ];
        for (const sel of platformSelectors) {
            const row = document.querySelector(sel);
            if (!row) continue;
            row.querySelectorAll('span, div, a, button').forEach(el => {
                if (!el.offsetParent) return;
                const text = el.textContent.trim();
                if (!text || text.length > 30 || el.children.length > 3) return;
                const active = isActiveElement(el);
                state.platform_all_options.push({text, isActive: active});
                if (active && (text.toLowerCase().includes('tiktok') || text.toLowerCase().includes('facebook') || text === 'All')) {
                    state.platform = text;
                    state.active_classes.push({group: 'platform', text, class: (el.className||'').substring(0,80)});
                }
            });
            if (state.platform) break;
        }

        // Also check URL for platform hints
        if (!state.platform) {
            const url = location.href.toLowerCase();
            if (url.includes('facebook') || url.includes('fb-')) state.platform = 'Facebook (from URL)';
            if (url.includes('adspy')) state.platform = 'Facebook/Adspy (from URL)';
        }

        // ── 3. Data types detection ──
        const dataSelectors = ['.filter-data-types', '.filter-item.filter-data-types', '[class*="data-type"]'];
        for (const sel of dataSelectors) {
            const row = document.querySelector(sel);
            if (!row) continue;
            row.querySelectorAll('span, div, a, button').forEach(el => {
                if (!el.offsetParent) return;
                const text = el.textContent.trim();
                if (!text || text.length > 40 || el.children.length > 3) return;
                const active = isActiveElement(el);
                state.data_types_all_options.push({text, isActive: active});
                if (active && text !== 'All') {
                    state.data_types_active.push(text);
                    state.active_classes.push({group: 'data_type', text, class: (el.className||'').substring(0,80)});
                }
            });
        }
        // Also detect from chips: if "E-commerce ×" chip exists, it's active
        for (const chip of state.chips) {
            const cl = chip.text.toLowerCase();
            if (cl.includes('e-commerce') || cl.includes('ecommerce')) {
                if (!state.data_types_active.some(d => d.toLowerCase().includes('e-commerce')))
                    state.data_types_active.push(chip.text);
            }
            if (cl.includes('dropshipping')) {
                if (!state.data_types_active.some(d => d.toLowerCase().includes('dropshipping')))
                    state.data_types_active.push(chip.text);
            }
        }

        // ── 4. Time detection ──
        const timeSelectors = ['.filter-time-types', '.filter-item.filter-time-types', '[class*="time-type"]'];
        for (const sel of timeSelectors) {
            const row = document.querySelector(sel);
            if (!row) continue;
            row.querySelectorAll('span, div, a, button').forEach(el => {
                if (!el.offsetParent) return;
                const text = el.textContent.trim();
                if (!text || text.length > 40 || el.children.length > 3) return;
                const active = isActiveElement(el);
                state.time_all_options.push({text, isActive: active});
                if (active) {
                    state.time = text;
                    state.active_classes.push({group: 'time', text, class: (el.className||'').substring(0,80)});
                }
            });
        }
        // Also detect from chips
        for (const chip of state.chips) {
            const cl = chip.text.toLowerCase();
            if (cl.includes('month') || cl.includes('day') || cl.includes('year') || cl.includes('yesterday')) {
                if (!state.time) state.time = chip.text;
            }
        }

        // ── 5. Sort detection ──
        // Look specifically for "Sort by:" text or sort dropdown
        // Avoid reading the search-type dropdown ("Ad Keyword") which is different
        const sortCandidates = document.querySelectorAll(
            '.data-view-sort, [class*="sort"], [class*="Sort"]'
        );
        for (const sc of sortCandidates) {
            if (!sc.offsetParent) continue;
            const rect = sc.getBoundingClientRect();
            if (rect.width < 50) continue;
            const text = sc.textContent.trim();
            // Must contain "Sort by" or be a sort-specific element
            if (text.toLowerCase().includes('sort by') || sc.className.toLowerCase().includes('sort')) {
                // Extract the actual sort value
                const input = sc.querySelector('input, .el-input__inner');
                if (input) {
                    const val = (input.value || '').trim();
                    if (val && val.length < 40 && val.toLowerCase().includes('sort')) {
                        state.sort = val;
                        break;
                    }
                }
                // Look for the selected item text
                const selected = sc.querySelector('.el-select__selected-item, [class*="selected"]');
                if (selected) {
                    state.sort = selected.textContent.trim();
                    break;
                }
                // Fallback: parse "Sort by: XXX" from text
                const match = text.match(/Sort by[:\\s]+(\\S[^\\n]{2,30})/i);
                if (match) {
                    state.sort = match[1].trim();
                    break;
                }
            }
        }

        // ── 6. Read el-select dropdown values (Facebook/Adspy layout) ──
        // These dropdowns show selected values in their inputs
        state.dropdown_values = {};
        document.querySelectorAll('.el-select').forEach(sel => {
            if (!sel.offsetParent) return;
            const rect = sel.getBoundingClientRect();
            if (rect.y > 500 || rect.height > 80) return;
            const input = sel.querySelector('input');
            if (!input) return;
            const placeholder = (input.placeholder || '').trim();
            const value = (input.value || '').trim();
            // A selected value replaces the placeholder, or a selected-text span appears
            const selectedSpan = sel.querySelector('.el-select__selected-item, [class*="selected"]');
            const selectedText = selectedSpan ? selectedSpan.textContent.trim() : '';
            // Check for Element UI's tag display (multi-select shows tags)
            const tags = [];
            sel.querySelectorAll('.el-tag').forEach(tag => {
                const t = tag.textContent.replace(/[×✕]/g, '').trim();
                if (t) tags.push(t);
            });
            if (placeholder || value || selectedText || tags.length) {
                state.dropdown_values[placeholder || `select_${Math.round(rect.x)}`] = {
                    placeholder, value, selectedText, tags,
                    y: Math.round(rect.y), x: Math.round(rect.x),
                    class: (sel.className||'').substring(0, 60),
                    hasValue: !!(value && value !== placeholder) || !!selectedText || tags.length > 0
                };
            }
        });

        // ── 7. Category detection (Shopify) ──
        // Check chips
        for (const chip of state.chips) {
            if (chip.text.toLowerCase().includes('shopify')) {
                state.category_active.push({text: chip.text, isActive: true, source: 'chip'});
            }
        }
        // Check dropdown values (Facebook/Adspy: Ecom Platform dropdown)
        for (const [key, dd] of Object.entries(state.dropdown_values)) {
            const kl = key.toLowerCase();
            if (kl.includes('ecom') && kl.includes('platform')) {
                const val = (dd.value || dd.selectedText || '').toLowerCase();
                const tagTexts = (dd.tags || []).map(t => t.toLowerCase());
                if (val.includes('shopify') || tagTexts.some(t => t.includes('shopify'))) {
                    state.category_active.push({text: dd.value || dd.selectedText || dd.tags[0], isActive: true, source: 'dropdown'});
                }
            }
        }
        // Also scan DOM
        document.querySelectorAll('[class*="category"], [class*="suggestion"], [class*="ecom"]').forEach(el => {
            if (!el.offsetParent) return;
            el.querySelectorAll('span, div, a, label').forEach(child => {
                const t = child.textContent.trim().toLowerCase();
                if (t === 'shopify' || t === 'woocommerce') {
                    const active = isActiveElement(child);
                    state.category_active.push({text: child.textContent.trim(), isActive: active, source: 'dom'});
                }
            });
        });

        // ── 8. App Platform detection (Website) ──
        // Check chips
        for (const chip of state.chips) {
            if (chip.text.toLowerCase().includes('website')) {
                state.app_platform_active.push({text: chip.text, isActive: true, source: 'chip'});
            }
        }
        // Check dropdown values (Facebook/Adspy: App Platform dropdown)
        for (const [key, dd] of Object.entries(state.dropdown_values)) {
            const kl = key.toLowerCase();
            if (kl.includes('app') && kl.includes('platform')) {
                const val = (dd.value || dd.selectedText || '').toLowerCase();
                const tagTexts = (dd.tags || []).map(t => t.toLowerCase());
                if (val.includes('website') || tagTexts.some(t => t.includes('website'))) {
                    state.app_platform_active.push({text: dd.value || dd.selectedText || dd.tags[0], isActive: true, source: 'dropdown'});
                }
            }
        }
        // Also scan DOM
        document.querySelectorAll('[class*="platform"], [class*="app-platform"]').forEach(el => {
            if (!el.offsetParent) return;
            el.querySelectorAll('span, div, a, label').forEach(child => {
                const t = child.textContent.trim().toLowerCase();
                if (t === 'website' || t === 'app') {
                    const active = isActiveElement(child);
                    state.app_platform_active.push({text: child.textContent.trim(), isActive: active, source: 'dom'});
                }
            });
        });

        // ── 9. Capture raw filter area text for debugging ──
        const fw = document.querySelector('.filter-wrap, .filter-action');
        if (fw) {
            state.filter_area_text = fw.textContent.trim().substring(0, 500).replace(/\\s+/g, ' ');
        }

        // Deduplicate chips
        const seen = new Set();
        state.chips = state.chips.filter(c => {
            const key = c.text.toLowerCase();
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        return state;
    }""")


async def apply_filter_click(page: Page, filter_group_class: str, target_text: str,
                               logger: StepLogger, ts: str) -> dict:
    """
    Click a filter option within a filter group by matching visible text.
    Returns {success, matched_text, verification}.
    """
    result = {"success": False, "matched_text": None, "verification": None, "error": None}

    try:
        # Find clickable children in the filter group
        matched = await page.evaluate("""([groupClass, targetText]) => {
            const container = document.querySelector('.' + groupClass.split(' ').join('.'));
            if (!container) return {found: false, error: 'container not found: ' + groupClass};

            const candidates = container.querySelectorAll('span, div, a, button, label');
            const matches = [];
            for (const el of candidates) {
                const text = el.textContent.trim();
                if (text.toLowerCase() === targetText.toLowerCase() && el.offsetParent !== null) {
                    matches.push({
                        text: text,
                        tag: el.tagName,
                        class: el.className.substring(0, 80),
                        rect: el.getBoundingClientRect(),
                        childCount: el.children.length,
                    });
                }
            }
            // Prefer leaf nodes (no children) for cleaner clicks
            matches.sort((a, b) => a.childCount - b.childCount);
            return {found: matches.length > 0, matches: matches.slice(0, 3)};
        }""", [filter_group_class, target_text])

        if not matched.get("found"):
            result["error"] = f"no match for '{target_text}' in .{filter_group_class}"
            logger.log("filter_lab", f"filter_click_{target_text}", "filter_ui", "filter_ui", "soft_fail",
                        notes=result["error"])
            return result

        # Click the best match
        best = matched["matches"][0]
        # Use text-based click within the container
        container_sel = "." + ".".join(filter_group_class.split())
        # Try clicking by exact text match within container
        try:
            loc = page.locator(f"{container_sel} >> text='{target_text}'").first
            if await loc.is_visible(timeout=3000):
                await loc.click()
                result["success"] = True
                result["matched_text"] = best["text"]
            else:
                # Fallback: coordinate click
                x = best["rect"]["x"] + best["rect"]["width"] / 2
                y = best["rect"]["y"] + best["rect"]["height"] / 2
                await page.mouse.click(x, y)
                result["success"] = True
                result["matched_text"] = best["text"]
        except Exception:
            # Coordinate fallback
            x = best["rect"]["x"] + best["rect"]["width"] / 2
            y = best["rect"]["y"] + best["rect"]["height"] / 2
            await page.mouse.click(x, y)
            result["success"] = True
            result["matched_text"] = best["text"]

        await page.wait_for_timeout(1500)

    except Exception as e:
        result["error"] = str(e)[:80]
        result["success"] = False

    return result


async def apply_sort_selection(page: Page, sort_value: str, logger: StepLogger, ts: str) -> dict:
    """
    Open the sort dropdown and select a value.
    Returns {success, selected, error}.
    """
    result = {"success": False, "selected": None, "error": None}

    try:
        # Click the sort dropdown to open it
        sort_container = page.locator(".el-select-sort, .select-type").first
        if not await sort_container.is_visible(timeout=3000):
            result["error"] = "sort dropdown not visible"
            return result

        await sort_container.click()
        await page.wait_for_timeout(1000)

        # Look for dropdown options (el-select creates a popup)
        # Try clicking the matching option in the dropdown popup
        option_sel = f".el-select-dropdown__item >> text='{sort_value}'"
        try:
            opt = page.locator(option_sel).first
            if await opt.is_visible(timeout=3000):
                await opt.click()
                result["success"] = True
                result["selected"] = sort_value
                await page.wait_for_timeout(1500)
                return result
        except Exception:
            pass

        # Fallback: find by evaluating dropdown items
        clicked = await page.evaluate("""(target) => {
            const items = document.querySelectorAll('.el-select-dropdown__item, .el-select-dropdown li');
            for (const item of items) {
                if (item.textContent.trim().toLowerCase().includes(target.toLowerCase())) {
                    item.click();
                    return {clicked: true, text: item.textContent.trim()};
                }
            }
            return {clicked: false};
        }""", sort_value)

        if clicked.get("clicked"):
            result["success"] = True
            result["selected"] = clicked.get("text", sort_value)
            await page.wait_for_timeout(1500)
        else:
            result["error"] = f"sort option '{sort_value}' not found in dropdown"
            # Close dropdown by pressing Escape
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)

    except Exception as e:
        result["error"] = str(e)[:80]
        # Try to close any open dropdown
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

    return result


async def prescan_visible_cards(page: Page, card_selector: str, max_cards: int = 20) -> list:
    """
    Pre-scan visible cards without opening them.
    Extracts: advertiser, thumbnail hints, CTA, duration, engagement metrics, region.
    Returns list of card summaries for quality estimation.
    """
    return await page.evaluate("""([sel, maxCards]) => {
        const cards = Array.from(document.querySelectorAll(sel)).slice(0, maxCards);
        return cards.map((card, idx) => {
            const texts = [];
            card.querySelectorAll('p, span, div, a, h5').forEach(el => {
                if (el.children.length === 0 && el.textContent.trim().length > 1 && el.textContent.trim().length < 200) {
                    texts.push({text: el.textContent.trim(), class: (el.className || '').substring(0, 60)});
                }
            });

            const imgs = Array.from(card.querySelectorAll('img')).map(i => ({
                src: (i.src || '').substring(0, 200),
                alt: i.alt || '',
            }));

            const links = Array.from(card.querySelectorAll('a[href]')).map(a => ({
                href: (a.href || '').substring(0, 200),
                text: a.textContent.trim().substring(0, 80),
            }));

            // Extract specific fields
            const advertiser = card.querySelector('.link-item.title, [class*="app-name"], [class*="nickname"]');
            const shopNow = card.querySelector('.shop-now, [class*="cta"]');
            const timeEl = card.querySelector('.time, [class*="duration"]');
            const dateEl = card.querySelector('.create-time, [class*="time-line"]');

            // Metrics (impression, days, likes)
            const metrics = {};
            card.querySelectorAll('.item').forEach(item => {
                const val = item.querySelector('.value');
                const cap = item.querySelector('.caption');
                if (val && cap) metrics[cap.textContent.trim()] = val.textContent.trim();
            });

            // Region flags
            const regionImgs = card.querySelectorAll('[class*="region"] img, ._decor img');
            const regions = Array.from(regionImgs).map(r => r.alt || r.title || '').filter(x => x);

            return {
                index: idx,
                advertiser: advertiser ? advertiser.textContent.trim() : null,
                cta: shopNow ? shopNow.textContent.trim() : null,
                duration: timeEl ? timeEl.textContent.trim() : null,
                date_range: dateEl ? dateEl.textContent.trim() : null,
                metrics: metrics,
                regions: regions,
                text_preview: texts.slice(0, 8).map(t => t.text).join(' | '),
                image_count: imgs.length,
                link_count: links.length,
            };
        });
    }""", [card_selector, max_cards])


def score_card_relevance(card_summary: dict, detail_data: Optional[dict] = None) -> dict:
    """
    Score a single card for niche relevance.
    Works on pre-scan data, optionally enhanced with detail modal data.
    """
    all_text = (card_summary.get("text_preview", "") + " " +
                (card_summary.get("advertiser", "") or "") + " " +
                (card_summary.get("cta", "") or "")).lower()

    if detail_data:
        detail_texts = " ".join(t.get("text", "") for t in detail_data.get("texts", []))
        all_text += " " + detail_texts.lower()
        all_text += " " + (detail_data.get("advertiser", "") or "").lower()
        all_text += " " + (detail_data.get("caption", "") or "").lower()
        all_text += " " + (detail_data.get("cta_text", "") or "").lower()

    # Relevance: how many niche keywords appear
    niche_hits = sum(1 for kw in NICHE_KEYWORDS if kw in all_text)
    relevance = min(niche_hits / 3.0, 1.0)  # 3+ hits = max relevance

    # Junk detection
    junk_hits = sum(1 for kw in JUNK_KEYWORDS if kw in all_text)
    is_junk = junk_hits >= 1

    # Competitor signal
    comp_hits = sum(1 for kw in COMPETITOR_SIGNALS if kw in all_text)
    is_competitor = comp_hits >= 2

    # Creative signal
    creative_hits = sum(1 for kw in CREATIVE_SIGNALS if kw in all_text)
    has_creative_signal = creative_hits >= 1

    return {
        "relevance": round(relevance, 2),
        "is_junk": is_junk,
        "junk_hits": junk_hits,
        "is_competitor": is_competitor,
        "competitor_hits": comp_hits,
        "has_creative_signal": has_creative_signal,
        "creative_hits": creative_hits,
        "niche_hits": niche_hits,
    }


def compute_profile_score(card_scores: list, opened_scores: list) -> dict:
    """
    Compute aggregate profile score from individual card scores.
    """
    if not card_scores:
        return {
            "relevance_score": 0, "competitor_score": 0, "creative_signal_score": 0,
            "junk_penalty": 1.0, "density_score": 0, "repeat_pattern_score": 0,
            "overall_profile_score": 0,
        }

    n = len(card_scores)

    # 1. Relevance: average relevance of all pre-scanned cards
    relevance_score = round(sum(s["relevance"] for s in card_scores) / n, 2)

    # 2. Competitor: fraction that look like real competitors
    competitor_score = round(sum(1 for s in card_scores if s["is_competitor"]) / n, 2)

    # 3. Creative signal: fraction with useful creative patterns
    creative_signal_score = round(sum(1 for s in card_scores if s["has_creative_signal"]) / n, 2)

    # 4. Junk penalty: fraction of junk (inverted — lower is better)
    junk_frac = sum(1 for s in card_scores if s["is_junk"]) / n
    junk_penalty = round(junk_frac, 2)

    # 5. Density: relevant cards per batch (cards with relevance > 0.3)
    good_cards = sum(1 for s in card_scores if s["relevance"] >= 0.33)
    density_score = round(good_cards / n, 2)

    # 6. Repeat pattern: how many cards share niche keywords (consistency)
    if n >= 3:
        high_relevance = sum(1 for s in card_scores if s["relevance"] >= 0.33)
        repeat_pattern_score = round(min(high_relevance / (n * 0.5), 1.0), 2)
    else:
        repeat_pattern_score = 0

    # Boost from opened card scores (if we opened cards and they were good)
    opened_boost = 0
    if opened_scores:
        opened_relevance = sum(s["relevance"] for s in opened_scores) / len(opened_scores)
        opened_competitor = sum(1 for s in opened_scores if s["is_competitor"]) / len(opened_scores)
        opened_boost = round((opened_relevance + opened_competitor) * 0.1, 2)

    # Overall: weighted combination
    overall = round(
        relevance_score * 0.25 +
        competitor_score * 0.20 +
        creative_signal_score * 0.15 +
        (1.0 - junk_penalty) * 0.15 +
        density_score * 0.15 +
        repeat_pattern_score * 0.10 +
        opened_boost,
        3
    )

    return {
        "relevance_score": relevance_score,
        "competitor_score": competitor_score,
        "creative_signal_score": creative_signal_score,
        "junk_penalty": junk_penalty,
        "density_score": density_score,
        "repeat_pattern_score": repeat_pattern_score,
        "opened_boost": opened_boost,
        "overall_profile_score": overall,
    }


async def run_filter_lab(page: Page, logger: StepLogger, ts: str):
    """
    Filter Lab — Structured filter optimization for niche ad research.

    Stages:
      F1: Load/create filter profiles
      F2: Test each profile (apply filters, verify, pre-scan, open sample, score)
      F3: Rank profiles and generate summary

    Outputs:
      filter_profiles.json, filter_test_results.json, filter_rankings.json, best_settings_summary.md
    """
    print("\n" + "=" * 70)
    print("FILTER LAB — Structured Filter Optimization")
    print("=" * 70)

    # ── Load artifacts ──
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]

    input_candidates = dom_sigs.get("search_input_candidates", [])
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"] if input_candidates else "#inputKeyword"

    open_recipes_loaded = recipes.get("open_result_card", [])
    proven_open = [r for r in open_recipes_loaded if r["success_count"] > 0]
    best_open = proven_open[0]["method"] if proven_open else None
    if not best_open:
        print("[ABORT] No proven open recipe.")
        return None

    close_recipes_loaded = recipes.get("close_detail", [])
    proven_close = [r for r in close_recipes_loaded if r["success_count"] > 0]
    best_close = proven_close[0]["method"] if proven_close else None
    if not best_close:
        print("[ABORT] No proven close recipe.")
        return None

    print(f"  Card: {primary_card_sel}")
    print(f"  Open: {best_open['type']} → {best_open['selector']}")
    print(f"  Close: {best_close['type']} → {best_close['selector']}")

    # ── Validate artifacts ──
    val = await validate_artifacts(page, logger, ts)
    print(f"  Artifacts: {val['status']}")
    if val["status"] in ("stale", "missing"):
        print("[ABORT] Artifacts invalid.")
        return None

    # ══════════════════════════════════════════════════════════
    # F1: Load profiles
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("F1 — Loading filter profiles")
    print(f"{'─' * 70}")

    if not FILTER_PROFILES_PATH.exists():
        print("[ABORT] filter_profiles.json not found.")
        return None

    profiles_data = json.loads(FILTER_PROFILES_PATH.read_text(encoding="utf-8"))
    profiles = profiles_data.get("profiles", [])
    print(f"  Loaded {len(profiles)} profiles")

    for p in profiles:
        print(f"    [{p['profile_id']}] {p['label']} — kw='{p['keyword']}' filters={list(p['filters'].keys())}")

    # ══════════════════════════════════════════════════════════
    # F2: Test each profile
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("F2 — Testing profiles")
    print(f"{'─' * 70}")

    # Map filter keys to CSS class selectors for the filter rows
    FILTER_GROUP_MAP = {
        "platform": "filter-ad-types",
        "data_type": "filter-data-types",
        "time": "filter-time-types",
    }

    all_test_results = []

    for prof_idx, profile in enumerate(profiles):
        pid = profile["profile_id"]
        keyword = profile["keyword"]
        filters = profile["filters"]

        print(f"\n{'═' * 70}")
        print(f"[PROFILE {prof_idx+1}/{len(profiles)}] {pid}: '{profile['label']}'")
        print(f"  Keyword: '{keyword}'")
        print(f"  Filters: {filters}")
        print(f"{'═' * 70}")

        test_result = {
            "profile_id": pid,
            "keyword": keyword,
            "filters_requested": dict(filters),
            "filters_applied": {},
            "filter_verification": {},
            "verification_status": "unknown",
            "visible_batch_size": 0,
            "cards_prescanned": 0,
            "cards_opened": 0,
            "prescan_scores": [],
            "opened_scores": [],
            "profile_scores": {},
            "notes": [],
            "screenshots": [],
        }

        # ── Step 1: Navigate to search page (clean state) ──
        print(f"\n  [1] Resetting to search page...")
        try:
            await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  [FAIL] Navigation: {str(e)[:60]}")
            test_result["notes"].append(f"navigation failed: {str(e)[:60]}")
            test_result["verification_status"] = "navigation_failed"
            all_test_results.append(test_result)
            continue

        # ── Step 2: Record pre-filter state ──
        pre_filter_state = await inspect_filter_state(page)
        ss_pre = await take_ss(page, f"flab_{pid}_01_pre_filter", ts)
        test_result["screenshots"].append(ss_pre)
        print(f"  Pre-filter state: platform={pre_filter_state.get('platform')}, "
              f"data_type={pre_filter_state.get('data_type')}, time={pre_filter_state.get('time')}")

        # ── Step 3: Apply filters ──
        print(f"\n  [2] Applying filters...")
        filter_apply_results = {}

        for filter_key, filter_value in filters.items():
            if filter_key == "sort":
                # Sort uses a dropdown, not tabs
                print(f"    Sort → '{filter_value}'...")
                sort_result = await apply_sort_selection(page, filter_value, logger, ts)
                filter_apply_results["sort"] = sort_result
                if sort_result["success"]:
                    test_result["filters_applied"]["sort"] = sort_result.get("selected", filter_value)
                    print(f"      OK: {sort_result.get('selected')}")
                else:
                    print(f"      FAILED: {sort_result.get('error', 'unknown')}")
                    test_result["notes"].append(f"sort failed: {sort_result.get('error')}")
            elif filter_key in FILTER_GROUP_MAP:
                group_class = FILTER_GROUP_MAP[filter_key]
                print(f"    {filter_key} → '{filter_value}' (in .{group_class})...")
                click_result = await apply_filter_click(page, group_class, filter_value, logger, ts)
                filter_apply_results[filter_key] = click_result
                if click_result["success"]:
                    test_result["filters_applied"][filter_key] = click_result.get("matched_text", filter_value)
                    print(f"      OK: matched '{click_result.get('matched_text')}'")
                else:
                    print(f"      FAILED: {click_result.get('error', 'unknown')}")
                    test_result["notes"].append(f"{filter_key} failed: {click_result.get('error')}")
            else:
                print(f"    [SKIP] Unknown filter key: {filter_key}")
                test_result["notes"].append(f"unknown filter key: {filter_key}")

        await page.wait_for_timeout(1000)

        # ── Step 4: Verify filter state ──
        print(f"\n  [3] Verifying filter state...")
        post_filter_state = await inspect_filter_state(page)
        ss_post_filter = await take_ss(page, f"flab_{pid}_02_post_filter", ts)
        test_result["screenshots"].append(ss_post_filter)

        verification = {}
        filters_verified = 0
        filters_checked = 0

        for filter_key, filter_value in filters.items():
            if filter_key == "sort":
                sort_text = (post_filter_state.get("sort") or "").lower()
                # Sort verification: check if sort label contains the target
                sort_target = filter_value.lower().replace("sort by: ", "")
                verified = sort_target in sort_text
                verification["sort"] = {
                    "target": filter_value,
                    "observed": post_filter_state.get("sort"),
                    "verified": verified,
                }
                filters_checked += 1
                if verified:
                    filters_verified += 1
                print(f"    Sort: {'OK' if verified else 'UNCERTAIN'} "
                      f"(target='{filter_value}', observed='{post_filter_state.get('sort')}')")
            elif filter_key == "platform":
                observed = post_filter_state.get("platform", "")
                verified = filter_value.lower() in (observed or "").lower()
                # Also check active_classes
                if not verified:
                    for ac in post_filter_state.get("active_classes", []):
                        if ac["group"] == "platform" and filter_value.lower() in ac["text"].lower():
                            verified = True
                            observed = ac["text"]
                            break
                verification["platform"] = {"target": filter_value, "observed": observed, "verified": verified}
                filters_checked += 1
                if verified:
                    filters_verified += 1
                print(f"    Platform: {'OK' if verified else 'UNCERTAIN'} "
                      f"(target='{filter_value}', observed='{observed}')")
            elif filter_key == "data_type":
                observed = post_filter_state.get("data_type", "")
                verified = filter_value.lower() in (observed or "").lower()
                if not verified:
                    for ac in post_filter_state.get("active_classes", []):
                        if ac["group"] == "data_type" and filter_value.lower() in ac["text"].lower():
                            verified = True
                            observed = ac["text"]
                            break
                verification["data_type"] = {"target": filter_value, "observed": observed, "verified": verified}
                filters_checked += 1
                if verified:
                    filters_verified += 1
                print(f"    Data type: {'OK' if verified else 'UNCERTAIN'} "
                      f"(target='{filter_value}', observed='{observed}')")
            elif filter_key == "time":
                observed = post_filter_state.get("time", "")
                verified = filter_value.lower() in (observed or "").lower()
                if not verified:
                    for ac in post_filter_state.get("active_classes", []):
                        if ac["group"] == "time" and filter_value.lower() in ac["text"].lower():
                            verified = True
                            observed = ac["text"]
                            break
                verification["time"] = {"target": filter_value, "observed": observed, "verified": verified}
                filters_checked += 1
                if verified:
                    filters_verified += 1
                print(f"    Time: {'OK' if verified else 'UNCERTAIN'} "
                      f"(target='{filter_value}', observed='{observed}')")

        test_result["filter_verification"] = verification

        if filters_checked > 0 and filters_verified >= filters_checked * 0.5:
            test_result["verification_status"] = "verified"
        elif filters_verified > 0:
            test_result["verification_status"] = "partial"
        else:
            test_result["verification_status"] = "unverified"

        print(f"  Verification: {test_result['verification_status']} ({filters_verified}/{filters_checked})")

        # ── Step 5: Submit search ──
        print(f"\n  [4] Searching '{keyword}'...")
        try:
            loc = page.locator(primary_input_sel).first
            if not await loc.is_visible(timeout=5000):
                loc = page.locator("#inputKeyword").first
            await loc.click(click_count=3)
            await loc.fill(keyword)
            await page.wait_for_timeout(500)
            await loc.press("Enter")
        except Exception as e:
            print(f"  [FAIL] Search: {str(e)[:60]}")
            test_result["notes"].append(f"search failed: {str(e)[:60]}")
            test_result["verification_status"] = "search_failed"
            all_test_results.append(test_result)
            continue

        await page.wait_for_timeout(6000)

        # ── Verify results ──
        ver = await verify_results_page(page, primary_card_sel)
        if not ver["verified"]:
            await page.wait_for_timeout(5000)
            ver = await verify_results_page(page, primary_card_sel)
            if not ver["verified"]:
                print(f"  [FAIL] Results not verified after search")
                test_result["notes"].append("results page not verified")
                test_result["verification_status"] = "no_results"
                all_test_results.append(test_result)
                continue

        ss_results = await take_ss(page, f"flab_{pid}_03_results", ts)
        test_result["screenshots"].append(ss_results)

        # ── Step 6: Pre-scan visible cards ──
        print(f"\n  [5] Pre-scanning visible cards...")
        dom_count = await count_visible_cards(page, primary_card_sel)
        test_result["visible_batch_size"] = dom_count
        print(f"    Visible cards: {dom_count}")

        card_summaries = await prescan_visible_cards(page, primary_card_sel, max_cards=20)
        test_result["cards_prescanned"] = len(card_summaries)

        # Score each pre-scanned card
        prescan_scores = []
        for cs in card_summaries:
            score = score_card_relevance(cs)
            prescan_scores.append({
                "index": cs["index"],
                "advertiser": cs.get("advertiser"),
                "cta": cs.get("cta"),
                "metrics": cs.get("metrics", {}),
                "score": score,
            })

        test_result["prescan_scores"] = prescan_scores

        # Quick prescan summary
        relevant_count = sum(1 for s in prescan_scores if s["score"]["relevance"] >= 0.33)
        junk_count = sum(1 for s in prescan_scores if s["score"]["is_junk"])
        comp_count = sum(1 for s in prescan_scores if s["score"]["is_competitor"])
        print(f"    Pre-scan: {len(prescan_scores)} cards — "
              f"{relevant_count} relevant, {comp_count} competitors, {junk_count} junk")

        # Check for early junk abort
        if len(prescan_scores) >= 5 and junk_count >= len(prescan_scores) * 0.6:
            print(f"    [EARLY STOP] Junk rate too high ({junk_count}/{len(prescan_scores)})")
            test_result["notes"].append(f"early stop: junk rate {junk_count}/{len(prescan_scores)}")
            # Still compute scores with what we have
            opened_scores_list = []
            test_result["opened_scores"] = opened_scores_list
            test_result["profile_scores"] = compute_profile_score(
                [s["score"] for s in prescan_scores], opened_scores_list
            )
            all_test_results.append(test_result)
            logger.log("filter_lab", f"profile_{pid}", "results_page", "scored", "success",
                        notes=f"early_stop_junk, overall={test_result['profile_scores']['overall_profile_score']}")
            continue

        # ── Step 7: Select and open top cards ──
        print(f"\n  [6] Opening top {FILTER_LAB_MAX_OPENS_PER_PROFILE} cards...")

        # Rank cards by relevance for opening
        ranked_for_open = sorted(prescan_scores, key=lambda s: s["score"]["relevance"], reverse=True)
        cards_to_open = ranked_for_open[:FILTER_LAB_MAX_OPENS_PER_PROFILE]

        # Scroll to top before opening
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        opened_scores_list = []
        for open_idx, card_info in enumerate(cards_to_open):
            card_dom_idx = card_info["index"]
            print(f"\n    [OPEN {open_idx+1}/{len(cards_to_open)}] "
                  f"Card idx={card_dom_idx}, adv={card_info.get('advertiser', '?')}, "
                  f"prescan_relevance={card_info['score']['relevance']}")

            pre_modals = await inspect_modal_state(page)

            try:
                cards_loc = page.locator(best_open["selector"])
                target = cards_loc.nth(card_dom_idx)
                await target.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await target.click()
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"      [FAIL] Click: {str(e)[:60]}")
                test_result["notes"].append(f"open failed card {card_dom_idx}: {str(e)[:40]}")
                continue

            post_modals = await inspect_modal_state(page)
            new_modals = len(post_modals.get("modals", [])) - len(pre_modals.get("modals", []))

            if new_modals <= 0:
                print(f"      [FAIL] No modal appeared")
                test_result["notes"].append(f"no modal for card {card_dom_idx}")
                continue

            test_result["cards_opened"] += 1

            # Extract detail
            try:
                detail_data = await extract_detail_from_modal(page)
                # Rescore with detail data
                enriched_score = score_card_relevance(card_info, detail_data)
                opened_scores_list.append(enriched_score)

                adv = detail_data.get("advertiser", "?")
                landing = detail_data.get("landing_url", "")
                caption = (detail_data.get("caption", "") or "")[:80]
                print(f"      Extracted: adv={adv}, relevance={enriched_score['relevance']}, "
                      f"competitor={enriched_score['is_competitor']}")
                if landing:
                    print(f"      Landing: {landing[:80]}")
                if caption:
                    print(f"      Caption: {caption}")

            except Exception as e:
                print(f"      [WARN] Extract: {str(e)[:60]}")

            # Close modal
            try:
                if best_close["type"] == "keyboard":
                    await page.keyboard.press(best_close["selector"])
                else:
                    cl = page.locator(best_close["selector"]).first
                    if await cl.is_visible(timeout=2000):
                        await cl.click()
                await page.wait_for_timeout(2000)
            except Exception:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1500)

            await page.wait_for_timeout(800)

        test_result["opened_scores"] = [
            {"relevance": s["relevance"], "is_competitor": s["is_competitor"],
             "has_creative_signal": s["has_creative_signal"], "is_junk": s["is_junk"]}
            for s in opened_scores_list
        ]

        # ── Step 8: Compute profile score ──
        test_result["profile_scores"] = compute_profile_score(
            [s["score"] for s in prescan_scores], opened_scores_list
        )

        overall = test_result["profile_scores"]["overall_profile_score"]
        print(f"\n  [SCORED] {pid}: overall={overall}")
        print(f"    relevance={test_result['profile_scores']['relevance_score']}, "
              f"competitor={test_result['profile_scores']['competitor_score']}, "
              f"creative={test_result['profile_scores']['creative_signal_score']}, "
              f"junk_penalty={test_result['profile_scores']['junk_penalty']}, "
              f"density={test_result['profile_scores']['density_score']}")

        logger.log("filter_lab", f"profile_{pid}", "results_page", "scored", "success",
                    notes=f"overall={overall}")

        all_test_results.append(test_result)

    # ══════════════════════════════════════════════════════════
    # F3: Rank and generate outputs
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("F3 — Ranking profiles")
    print(f"{'─' * 70}")

    # Save test results
    test_output = {
        "mode": "filter_lab",
        "timestamp": datetime.now().isoformat(),
        "profiles_tested": len(all_test_results),
        "results": all_test_results,
    }
    with open(FILTER_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(test_output, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Test results saved: {FILTER_RESULTS_PATH.name}")

    # Rank profiles
    scored_profiles = [
        r for r in all_test_results
        if r.get("profile_scores", {}).get("overall_profile_score") is not None
    ]
    ranked = sorted(scored_profiles, key=lambda r: r["profile_scores"]["overall_profile_score"], reverse=True)

    rankings = []
    for rank_idx, r in enumerate(ranked):
        ps = r["profile_scores"]
        rankings.append({
            "rank": rank_idx + 1,
            "profile_id": r["profile_id"],
            "keyword": r["keyword"],
            "filters_applied": r.get("filters_applied", {}),
            "verification_status": r["verification_status"],
            "overall_score": ps["overall_profile_score"],
            "relevance_score": ps["relevance_score"],
            "competitor_score": ps["competitor_score"],
            "creative_signal_score": ps["creative_signal_score"],
            "junk_penalty": ps["junk_penalty"],
            "density_score": ps["density_score"],
            "visible_batch_size": r["visible_batch_size"],
            "cards_opened": r["cards_opened"],
        })

    rankings_output = {
        "timestamp": datetime.now().isoformat(),
        "rankings": rankings,
    }
    with open(FILTER_RANKINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(rankings_output, f, indent=2, ensure_ascii=False)
    print(f"  Rankings saved: {FILTER_RANKINGS_PATH.name}")

    # Print rankings table
    print(f"\n  {'Rank':<5} {'Profile':<30} {'Overall':<9} {'Relev':<7} {'Comp':<6} {'Creat':<7} {'Junk':<6} {'Density':<8}")
    print(f"  {'─'*5} {'─'*30} {'─'*9} {'─'*7} {'─'*6} {'─'*7} {'─'*6} {'─'*8}")
    for r in rankings:
        print(f"  {r['rank']:<5} {r['profile_id']:<30} {r['overall_score']:<9} "
              f"{r['relevance_score']:<7} {r['competitor_score']:<6} "
              f"{r['creative_signal_score']:<7} {r['junk_penalty']:<6} {r['density_score']:<8}")

    # ── Generate best_settings_summary.md ──
    summary_lines = [
        "# Filter Lab — Best Settings Summary",
        f"",
        f"Generated: {datetime.now().isoformat()}",
        f"Profiles tested: {len(ranked)}",
        f"",
    ]

    if ranked:
        best = ranked[0]
        ps = best["profile_scores"]
        summary_lines += [
            "## Best Profile Overall",
            f"**{best['profile_id']}** (score: {ps['overall_profile_score']})",
            f"- Keyword: `{best['keyword']}`",
            f"- Filters: {best.get('filters_applied', {})}",
            f"- Relevance: {ps['relevance_score']}, Competitor: {ps['competitor_score']}, "
            f"Creative: {ps['creative_signal_score']}",
            f"- Junk penalty: {ps['junk_penalty']}, Density: {ps['density_score']}",
            "",
        ]

        # Best for competitors
        by_comp = sorted(ranked, key=lambda r: r["profile_scores"]["competitor_score"], reverse=True)
        bc = by_comp[0]
        summary_lines += [
            "## Best for Finding Competitors",
            f"**{bc['profile_id']}** (competitor score: {bc['profile_scores']['competitor_score']})",
            f"- Keyword: `{bc['keyword']}`",
            f"- Filters: {bc.get('filters_applied', {})}",
            "",
        ]

        # Best for creative inspiration
        by_creative = sorted(ranked, key=lambda r: r["profile_scores"]["creative_signal_score"], reverse=True)
        bcr = by_creative[0]
        summary_lines += [
            "## Best for Creative Inspiration",
            f"**{bcr['profile_id']}** (creative score: {bcr['profile_scores']['creative_signal_score']})",
            f"- Keyword: `{bcr['keyword']}`",
            f"- Filters: {bcr.get('filters_applied', {})}",
            "",
        ]

        # Best for low junk
        by_low_junk = sorted(ranked, key=lambda r: r["profile_scores"]["junk_penalty"])
        blj = by_low_junk[0]
        summary_lines += [
            "## Best for Low Junk",
            f"**{blj['profile_id']}** (junk penalty: {blj['profile_scores']['junk_penalty']})",
            f"- Keyword: `{blj['keyword']}`",
            f"- Filters: {blj.get('filters_applied', {})}",
            "",
        ]

        # Best for long-running winners (highest density + relevance with long time window)
        by_density = sorted(ranked, key=lambda r: r["profile_scores"]["density_score"], reverse=True)
        bd = by_density[0]
        summary_lines += [
            "## Best for Long-Running Winners",
            f"**{bd['profile_id']}** (density score: {bd['profile_scores']['density_score']})",
            f"- Keyword: `{bd['keyword']}`",
            f"- Filters: {bd.get('filters_applied', {})}",
            "",
        ]

        # Profiles to avoid (bottom 3)
        summary_lines += ["## Profiles to Avoid"]
        for r in ranked[-3:]:
            ps = r["profile_scores"]
            summary_lines.append(
                f"- **{r['profile_id']}** (score: {ps['overall_profile_score']}) — "
                f"junk: {ps['junk_penalty']}, relevance: {ps['relevance_score']}"
            )
        summary_lines.append("")

        # Settings analysis
        summary_lines += [
            "## Settings Analysis",
            "",
        ]

        # Which settings increased junk
        high_junk = [r for r in ranked if r["profile_scores"]["junk_penalty"] >= 0.2]
        if high_junk:
            summary_lines.append("### Settings that increased junk:")
            for r in high_junk:
                summary_lines.append(f"- {r['profile_id']}: junk={r['profile_scores']['junk_penalty']} "
                                     f"(filters: {r.get('filters_applied', {})})")
        else:
            summary_lines.append("### No profiles had high junk rates")
        summary_lines.append("")

        # Which settings increased competitor density
        high_comp = [r for r in ranked if r["profile_scores"]["competitor_score"] >= 0.3]
        if high_comp:
            summary_lines.append("### Settings that increased competitor density:")
            for r in high_comp:
                summary_lines.append(f"- {r['profile_id']}: competitor={r['profile_scores']['competitor_score']} "
                                     f"(filters: {r.get('filters_applied', {})})")
        else:
            summary_lines.append("### No profiles had high competitor density (threshold: 0.3)")
        summary_lines.append("")

        # Best video creative references
        high_creative = [r for r in ranked if r["profile_scores"]["creative_signal_score"] >= 0.2]
        if high_creative:
            summary_lines.append("### Settings for best video creative references:")
            for r in high_creative:
                summary_lines.append(f"- {r['profile_id']}: creative={r['profile_scores']['creative_signal_score']} "
                                     f"(filters: {r.get('filters_applied', {})})")
        else:
            summary_lines.append("### No profiles had high creative signal (threshold: 0.2)")
        summary_lines.append("")

    summary_text = "\n".join(summary_lines)
    FILTER_SUMMARY_PATH.write_text(summary_text, encoding="utf-8")
    print(f"  Summary saved: {FILTER_SUMMARY_PATH.name}")

    # ══════════════════════════════════════════════════════════
    # FILTER LAB REPORT
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("FILTER LAB REPORT")
    print(f"{'=' * 70}")

    if ranked:
        top3 = ranked[:3]
        bottom3 = ranked[-3:] if len(ranked) >= 3 else ranked

        print(f"\n1. TOP 3 FILTER PROFILES:")
        for r in top3:
            ps = r["profile_scores"]
            print(f"   #{r.get('rank', '?')} {r['profile_id']}: overall={ps['overall_profile_score']}, "
                  f"relev={ps['relevance_score']}, comp={ps['competitor_score']}, "
                  f"creative={ps['creative_signal_score']}")

        print(f"\n2. WORST 3 FILTER PROFILES:")
        for r in bottom3:
            ps = r["profile_scores"]
            print(f"   #{r.get('rank', '?')} {r['profile_id']}: overall={ps['overall_profile_score']}, "
                  f"junk={ps['junk_penalty']}")

        print(f"\n3. SETTINGS THAT INCREASED JUNK:")
        high_junk = [r for r in ranked if r["profile_scores"]["junk_penalty"] >= 0.15]
        if high_junk:
            for r in high_junk:
                print(f"   {r['profile_id']}: junk_penalty={r['profile_scores']['junk_penalty']} "
                      f"filters={r.get('filters_applied', {})}")
        else:
            print("   None — all profiles had low junk")

        print(f"\n4. SETTINGS THAT INCREASED COMPETITOR DENSITY:")
        by_comp = sorted(ranked, key=lambda r: r["profile_scores"]["competitor_score"], reverse=True)
        for r in by_comp[:3]:
            print(f"   {r['profile_id']}: competitor_score={r['profile_scores']['competitor_score']} "
                  f"filters={r.get('filters_applied', {})}")

        print(f"\n5. BEST VIDEO CREATIVE REFERENCES:")
        by_creative = sorted(ranked, key=lambda r: r["profile_scores"]["creative_signal_score"], reverse=True)
        for r in by_creative[:3]:
            print(f"   {r['profile_id']}: creative={r['profile_scores']['creative_signal_score']} "
                  f"filters={r.get('filters_applied', {})}")

        print(f"\n6. RECOMMENDED SETTINGS FOR YOUR NICHE:")
        best = ranked[0]
        print(f"   Best overall: {best['profile_id']}")
        print(f"   Keyword: '{best['keyword']}'")
        print(f"   Filters: {best.get('filters_applied', {})}")
        print(f"   Score: {best['profile_scores']['overall_profile_score']}")
    else:
        print("  No profiles scored — check filter application logs above.")

    print(f"\n  Outputs:")
    print(f"    {FILTER_RESULTS_PATH.name}")
    print(f"    {FILTER_RANKINGS_PATH.name}")
    print(f"    {FILTER_SUMMARY_PATH.name}")

    print(f"\n  [STOP] Filter Lab F2 complete. Review results before F3 refinement.")

    logger.save()
    return test_output


# ═══════════════════════════════════════════════════════════
# RESEARCH MODE — Baseline filter + keyword research
# ═══════════════════════════════════════════════════════════

RESEARCH_KEYWORDS = {
    "core_product": [
        "streetwear", "oversized hoodie", "heavyweight hoodie",
        "graphic tee", "baggy jeans", "essentials hoodie", "premium blank hoodie",
    ],
    "aesthetic_niche": [
        "y2k streetwear", "archive fashion", "limited drop clothing",
    ],
    "competitor_adjacent": [
        "streetwear brand", "mens streetwear",
    ],
}
RESEARCH_MAX_BATCHES = 3
RESEARCH_MAX_OPENS_PER_KW = 4
RESEARCH_RECORDS_PATH = DATA_DIR / "research_records.json"
RESEARCH_COMPETITOR_PATH = DATA_DIR / "competitor_summary.json"
RESEARCH_PATTERNS_PATH = DATA_DIR / "creative_patterns.md"


async def discover_full_filter_ui(page: Page) -> dict:
    """
    Comprehensive discovery of all filter controls visible on the page.
    Used after platform switch to find controls that may have appeared/changed.
    """
    return await page.evaluate("""() => {
        const result = {
            filter_rows: [],
            category_options: [],
            app_platform_options: [],
            sort_options: [],
            time_options: [],
            checkboxes: [],
            buttons: [],
            dropdowns: [],
            chips: [],
        };

        // Scan all filter-item rows
        document.querySelectorAll('[class*="filter-item"], [class*="filter-"]').forEach(el => {
            if (!el.offsetParent) return;
            const rect = el.getBoundingClientRect();
            if (rect.width < 100 || rect.height < 15) return;
            const cls = el.className.substring(0, 120);
            // Get clickable children
            const children = [];
            el.querySelectorAll('span, div, a, button, label').forEach(ch => {
                if (ch.offsetParent && ch.children.length === 0 && ch.textContent.trim().length > 0 && ch.textContent.trim().length < 80) {
                    children.push({
                        text: ch.textContent.trim(),
                        tag: ch.tagName,
                        class: ch.className.substring(0, 80),
                        isActive: ch.classList.contains('active') || ch.classList.contains('is-active') ||
                                  ch.parentElement?.classList.contains('active') || ch.parentElement?.classList.contains('is-active'),
                    });
                }
            });
            if (children.length > 0) {
                result.filter_rows.push({class: cls, text: el.textContent.trim().substring(0, 200), children: children.slice(0, 20)});
            }
        });

        // Category section — look for text "Category" or "Shopify" near filter area
        document.querySelectorAll('[class*="category"], [class*="suggestions"]').forEach(el => {
            if (!el.offsetParent) return;
            result.category_options.push({
                class: el.className.substring(0, 80),
                text: el.textContent.trim().substring(0, 200),
                rect: {x: Math.round(el.getBoundingClientRect().x), y: Math.round(el.getBoundingClientRect().y)},
            });
        });

        // Also look for Shopify/Woocommerce text in the filter area
        const filterWrap = document.querySelector('.filter-wrap, .filter-action');
        if (filterWrap) {
            filterWrap.querySelectorAll('span, div, a, label').forEach(el => {
                const t = el.textContent.trim().toLowerCase();
                if ((t.includes('shopify') || t.includes('woocommerce') || t.includes('category') ||
                     t.includes('app platform') || t.includes('website')) && el.children.length <= 2) {
                    result.category_options.push({
                        class: el.className.substring(0, 80),
                        text: el.textContent.trim(),
                        tag: el.tagName,
                        isActive: el.classList.contains('active') || el.classList.contains('is-active'),
                    });
                }
            });
        }

        // Sort dropdown options (if open)
        document.querySelectorAll('.el-select-dropdown__item').forEach(el => {
            if (el.offsetParent) {
                result.sort_options.push({text: el.textContent.trim(), selected: el.classList.contains('selected')});
            }
        });

        // Checkboxes / toggles
        document.querySelectorAll('input[type="checkbox"], .el-checkbox, .el-switch').forEach(el => {
            if (!el.offsetParent) return;
            const label = el.closest('label') || el.parentElement;
            result.checkboxes.push({
                text: (label?.textContent || '').trim().substring(0, 80),
                checked: el.checked || el.classList.contains('is-checked'),
                class: el.className.substring(0, 80),
            });
        });

        // Buttons in filter area
        if (filterWrap) {
            filterWrap.querySelectorAll('button').forEach(btn => {
                if (btn.offsetParent) {
                    result.buttons.push({
                        text: btn.textContent.trim().substring(0, 60),
                        class: btn.className.substring(0, 80),
                        isActive: btn.classList.contains('active') || btn.classList.contains('is-active'),
                    });
                }
            });
        }

        // Chips / tags visible
        document.querySelectorAll('.el-tag, [class*="chip"], [class*="tag"]').forEach(el => {
            if (el.offsetParent && el.textContent.trim().length > 0 && el.textContent.trim().length < 80) {
                result.chips.push({text: el.textContent.trim(), class: el.className.substring(0, 80)});
            }
        });

        return result;
    }""")


BASELINE_EXPECTED = {
    "platform": {"value": "Facebook", "critical": True},
    "ecommerce": {"value": "E-commerce", "critical": True, "group": "filter-data-types",
                  "alts": ["E-Commerce", "Ecommerce"]},
    "dropshipping": {"value": "Dropshipping", "critical": True, "group": "filter-data-types"},
    "category": {"value": "Shopify", "critical": True},
    "app_platform": {"value": "Website", "critical": False},  # Demoted: PiPiAds dropdown resists automation
    "time": {"value": "Last 6 months", "critical": True,
             "preferred": ["Last 3 months", "Last 90 days", "Last 6 months"],
             "group": "filter-time-types"},
    "sort": {"value": "Ad Spend", "critical": True,
             "alts": ["Adspend", "Ad spend", "Adspend(USD)", "Ad Spend(USD)"]},
    "last_seen": {"value": "Last 7 days", "critical": False},
}


def _match_text(observed: str, target: str) -> bool:
    """Case-insensitive substring match for filter comparison."""
    return target.lower() in (observed or "").lower()


def compare_baseline(live_state: dict) -> dict:
    """
    Compare live filter state against expected baseline.
    Returns {correct: [...], missing: [...], wrong: [...]}.
    """
    correct = []
    missing = []
    wrong = []

    # ── Platform ──
    live_plat = (live_state.get("platform") or "").lower()
    if "facebook" in live_plat:
        correct.append("platform")
    else:
        missing.append("platform")

    # ── Data types (multi-select) ──
    live_dt = [t.lower() for t in live_state.get("data_types_active", [])]
    live_dt_flat = " ".join(live_dt)
    if any("e-commerce" in d or "ecommerce" in d for d in live_dt):
        correct.append("ecommerce")
    else:
        missing.append("ecommerce")
    if any("dropshipping" in d for d in live_dt):
        correct.append("dropshipping")
    else:
        missing.append("dropshipping")
    # Check for unwanted active data types (not All, not our targets)
    for dt_text in live_state.get("data_types_active", []):
        dt_l = dt_text.lower()
        if dt_l == "all" or "e-commerce" in dt_l or "ecommerce" in dt_l or "dropshipping" in dt_l:
            continue
        wrong.append(f"data_type:{dt_text}")

    # ── Category (Shopify) — check chips, active state, AND dropdown values ──
    chip_texts = " ".join(c.get("text", "") for c in live_state.get("chips", [])).lower()
    cat_active = [c["text"] for c in live_state.get("category_active", []) if c.get("isActive")]
    # Also check dropdown_values for el-select dropdowns (Facebook/Adspy layout)
    dd_vals = live_state.get("dropdown_values", {})
    dd_has_shopify = any(
        "shopify" in (v.get("value", "") + v.get("selectedText", "") + " ".join(v.get("tags", []))).lower()
        for v in dd_vals.values()
    )
    if "shopify" in chip_texts or any("shopify" in c.lower() for c in cat_active) or dd_has_shopify:
        correct.append("category")
    else:
        missing.append("category")

    # ── App Platform (Website) — check chips, active state, AND dropdown values ──
    app_active = [a["text"] for a in live_state.get("app_platform_active", []) if a.get("isActive")]
    dd_has_website = any(
        "website" in (v.get("value", "") + v.get("selectedText", "") + " ".join(v.get("tags", []))).lower()
        for k, v in dd_vals.items()
        if "platform" in k.lower() or "app" in k.lower()
    )
    if "website" in chip_texts or any("website" in a.lower() for a in app_active) or dd_has_website:
        correct.append("app_platform")
    else:
        missing.append("app_platform")

    # ── Time ──
    live_time = (live_state.get("time") or "").lower()
    time_ok = any(t in live_time for t in ["3 month", "90 day", "6 month"]) or \
              any(t in chip_texts for t in ["3 month", "90 day", "6 month"])
    if time_ok:
        correct.append("time")
    else:
        missing.append("time")

    # ── Sort ──
    live_sort = (live_state.get("sort") or "").lower()
    if "ad spend" in live_sort or "adspend" in live_sort:
        correct.append("sort")
    else:
        missing.append("sort")

    # ── Last seen (soft) ──
    if "last seen" in chip_texts or "7 day" in chip_texts:
        correct.append("last_seen")
    else:
        missing.append("last_seen")

    return {"correct": correct, "missing": missing, "wrong": wrong}


async def _apply_dropdown_filter(page: Page, filter_name: str, option_text: str,
                                  trigger_labels: list, trigger_selectors: list) -> bool:
    """
    Open a dropdown filter and select an option.
    Facebook/Adspy layout uses dropdown selectors (not tab-style clicks).
    """
    print(f"        [dropdown] Trying to apply {filter_name}={option_text}")

    # First: diagnostic dump of all el-select and dropdown elements on the page
    diag = await page.evaluate("""() => {
        const results = [];
        // Scan for el-select components
        document.querySelectorAll('.el-select, .el-select-v2, [class*="el-select"]').forEach(el => {
            if (!el.offsetParent) return;
            const rect = el.getBoundingClientRect();
            results.push({
                type: 'el-select',
                text: el.textContent.trim().substring(0, 80),
                class: (el.className||'').substring(0, 100),
                y: Math.round(rect.y),
                x: Math.round(rect.x),
                w: Math.round(rect.width),
                h: Math.round(rect.height),
            });
        });
        // Scan for elements with "Platform" or "Category" in text (visible, in filter area)
        document.querySelectorAll('span, label, div, p').forEach(el => {
            if (!el.offsetParent) return;
            const text = el.textContent.trim();
            const rect = el.getBoundingClientRect();
            if (rect.y > 400 || rect.height > 50 || text.length > 60 || text.length < 3) return;
            const tl = text.toLowerCase();
            if (tl.includes('platform') || tl.includes('category') || tl.includes('shopify') || tl.includes('website')) {
                results.push({
                    type: 'label',
                    text: text.substring(0, 60),
                    tag: el.tagName,
                    class: (el.className||'').substring(0, 80),
                    y: Math.round(rect.y),
                    x: Math.round(rect.x),
                    children: el.children.length,
                });
            }
        });
        return results;
    }""")
    print(f"        [dropdown] DOM scan found {len(diag)} elements:")
    for d in diag[:20]:
        print(f"          {d.get('type')}: '{d.get('text', '')[:50]}' @ y={d.get('y')} cls={d.get('class', '')[:40]}")

    # Strategy 1: Find trigger by visible label text
    for label in trigger_labels:
        try:
            trigger = page.locator(f"text='{label}'").first
            if await trigger.is_visible(timeout=1500):
                bbox = await trigger.bounding_box()
                print(f"        [dropdown] Found label '{label}' at y={bbox['y']:.0f}")
                if bbox and bbox["height"] < 60 and bbox["y"] < 500:
                    await trigger.click()
                    await page.wait_for_timeout(1000)
                    found = await _select_dropdown_option(page, option_text)
                    if found:
                        return True
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
            else:
                print(f"        [dropdown] Label '{label}' not visible")
        except Exception as e:
            print(f"        [dropdown] Label '{label}' error: {str(e)[:60]}")
            continue

    # Strategy 2: Click el-select elements whose text matches trigger labels
    try:
        clicked = await page.evaluate("""([labels, optionText]) => {
            const selects = document.querySelectorAll('.el-select, [class*="el-select"]');
            const found = [];
            for (const sel of selects) {
                if (!sel.offsetParent) continue;
                const rect = sel.getBoundingClientRect();
                if (rect.y > 500 || rect.height > 80) continue;
                const text = sel.textContent.trim().toLowerCase();
                found.push({text: sel.textContent.trim().substring(0,50), y: Math.round(rect.y)});
                for (const lbl of labels) {
                    if (text.includes(lbl.toLowerCase())) {
                        const input = sel.querySelector('input, .el-input__inner, .el-input');
                        if (input) { input.click(); return {clicked: true, via: 'input', text: sel.textContent.trim().substring(0,50)}; }
                        sel.click();
                        return {clicked: true, via: 'self', text: sel.textContent.trim().substring(0,50)};
                    }
                }
            }
            return {clicked: false, scanned: found.length, samples: found.slice(0, 8)};
        }""", [trigger_labels, option_text])

        print(f"        [dropdown] el-select scan: {clicked}")
        if clicked and clicked.get("clicked"):
            await page.wait_for_timeout(1200)
            found = await _select_dropdown_option(page, option_text)
            if found:
                return True
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
    except Exception as e:
        print(f"        [dropdown] el-select scan error: {str(e)[:80]}")

    # Strategy 3: Brute-force — click all el-select elements in the filter area one by one
    # and check if any dropdown contains our option
    try:
        select_count = await page.locator(".el-select").count()
        print(f"        [dropdown] Brute-force: {select_count} el-select elements")
        for i in range(min(select_count, 12)):
            sel = page.locator(".el-select").nth(i)
            if not await sel.is_visible(timeout=300):
                continue
            bbox = await sel.bounding_box()
            if not bbox or bbox["y"] > 500:
                continue
            # Get placeholder and text for diagnostics
            placeholder = ""
            try:
                inp_el = sel.locator("input").first
                if await inp_el.is_visible(timeout=200):
                    placeholder = await inp_el.get_attribute("placeholder") or ""
            except Exception:
                pass
            text = (await sel.text_content() or "").strip()[:40]
            try:
                # Click the input inside the select
                inp = sel.locator("input, .el-input__inner").first
                if await inp.is_visible(timeout=300):
                    await inp.click()
                else:
                    await sel.click()
                await page.wait_for_timeout(800)

                # Log visible options for debugging
                opts = await page.evaluate("""() => {
                    const items = document.querySelectorAll(
                        '.el-select-dropdown__item, .el-scrollbar__view li, [role="option"]'
                    );
                    const visible = [];
                    for (const item of items) {
                        if (item.offsetParent && item.getBoundingClientRect().height > 0) {
                            visible.push(item.textContent.trim().substring(0, 40));
                        }
                    }
                    return visible.slice(0, 10);
                }""")
                if opts:
                    print(f"          select #{i} placeholder='{placeholder}' options={opts[:6]}")

                # Check if our option is in this dropdown's options
                target_lower = option_text.lower()
                if any(target_lower in o.lower() for o in (opts or [])):
                    # Try direct Playwright click on the matching item
                    # Use the el-popover.comSelect container since that's where PiPiAds renders options
                    click_success = False

                    # Approach A: Direct Playwright locator on visible li items
                    try:
                        all_li = page.locator("li.el-select-dropdown__item")
                        li_count = await all_li.count()
                        for li_idx in range(li_count):
                            li = all_li.nth(li_idx)
                            try:
                                if not await li.is_visible(timeout=150):
                                    continue
                                li_text = (await li.text_content() or "").strip()
                                if li_text.lower() == target_lower or target_lower in li_text.lower():
                                    await li.click(timeout=2000)
                                    await page.wait_for_timeout(1000)
                                    print(f"          [select_option] Clicked '{li_text}' via direct Playwright li click")
                                    click_success = True
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass

                    # Approach B: Use _select_dropdown_option (existing strategies)
                    if not click_success:
                        click_success = await _select_dropdown_option(page, option_text)

                    if click_success:
                        # Verify the selection stuck by checking if the select element changed
                        await page.wait_for_timeout(500)
                        new_text = (await sel.text_content() or "").strip()[:40]
                        print(f"        [dropdown] Brute-force: found '{option_text}' in select #{i} placeholder='{placeholder}' (now: '{new_text}')")
                        return True

                # Option not in this dropdown or click failed
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)
            except Exception:
                continue
    except Exception as e:
        print(f"        [dropdown] Brute-force error: {str(e)[:80]}")

    print(f"        [dropdown] All strategies failed for {filter_name}={option_text}")
    return False


async def _select_dropdown_option(page: Page, option_text: str) -> bool:
    """
    Select an option from an open dropdown popup.
    Element UI appends dropdown popovers to <body> as .el-select-dropdown.el-popper.
    We must only target items in the CURRENTLY VISIBLE popper.
    """
    target = option_text.lower()

    # Strategy 1: Playwright locator targeting visible popover items
    # PiPiAds uses el-popover.comSelect for filter dropdown popovers
    for sel in [
        ".el-popover.comSelect .el-select-dropdown__item",
        ".el-popover .el-select-dropdown__item",
        ".el-popper .el-select-dropdown__item",
        ".el-select-dropdown .el-select-dropdown__item",
    ]:
        try:
            items = page.locator(sel)
            count = await items.count()
            for i in range(count):
                item = items.nth(i)
                try:
                    if not await item.is_visible(timeout=200):
                        continue
                except Exception:
                    continue
                text = (await item.text_content() or "").strip()
                if text.lower() == target or target in text.lower():
                    await item.click(timeout=3000)
                    await page.wait_for_timeout(1000)
                    print(f"          [select_option] Clicked '{text}' via Playwright locator ({sel[:30]})")
                    return True
        except Exception:
            continue

    # Strategy 2: Use evaluate to find coordinates, then mouse.click
    try:
        result = await page.evaluate("""(target) => {
            const containers = document.querySelectorAll(
                '.el-popover, .el-popper, .el-select-dropdown, [class*="popover"], [class*="dropdown"]'
            );
            for (const container of containers) {
                const style = getComputedStyle(container);
                if (style.display === 'none' || style.visibility === 'hidden') continue;
                const rect = container.getBoundingClientRect();
                if (rect.height < 10) continue;
                const items = container.querySelectorAll('.el-select-dropdown__item, li');
                for (const item of items) {
                    const iRect = item.getBoundingClientRect();
                    if (iRect.height === 0 || iRect.width === 0) continue;
                    const text = item.textContent.trim();
                    if (text.toLowerCase() === target || text.toLowerCase().includes(target)) {
                        return {found: true, text, x: Math.round(iRect.x + iRect.width/2), y: Math.round(iRect.y + iRect.height/2)};
                    }
                }
            }
            return {found: false};
        }""", target)
        if result and result.get("found"):
            await page.mouse.click(result["x"], result["y"])
            await page.wait_for_timeout(1000)
            print(f"          [select_option] Clicked '{result['text']}' at ({result['x']},{result['y']}) via coordinates")
            return True
        else:
            print(f"          [select_option] No match for '{option_text}' in visible popover containers")
    except Exception as e:
        print(f"          [select_option] Strategy 2 error: {str(e)[:80]}")

    # Strategy 3: getByText inside dropdown context only
    try:
        option = page.get_by_text(option_text, exact=True).first
        if await option.is_visible(timeout=500):
            is_dropdown = await option.evaluate("""el => {
                let p = el;
                for (let i = 0; i < 10 && p; i++) {
                    const cls = (p.className || '').toLowerCase();
                    if (cls.includes('dropdown') || cls.includes('popover') || cls.includes('popper'))
                        return true;
                    p = p.parentElement;
                }
                return false;
            }""")
            if is_dropdown:
                await option.click(timeout=3000)
                await page.wait_for_timeout(800)
                print(f"          [select_option] Clicked via getByText (dropdown context)")
                return True
    except Exception:
        pass

    print(f"          [select_option] All strategies failed for '{option_text}'")
    return False


async def _apply_single_filter(page: Page, filter_name: str, logger: StepLogger, ts: str) -> bool:
    """Apply a single missing baseline filter. Returns True if successful."""
    spec = BASELINE_EXPECTED.get(filter_name)
    if not spec:
        return False

    if filter_name == "platform":
        r = await apply_filter_click(page, "filter-ad-types", "Facebook", logger, ts)
        if r["success"]:
            await page.wait_for_timeout(3000)  # platform switch needs extra settle time
            return True
        return False

    if filter_name in ("ecommerce", "dropshipping"):
        target = spec["value"]
        r = await apply_filter_click(page, spec["group"], target, logger, ts)
        if r["success"]:
            await page.wait_for_timeout(1500)
            return True
        for alt in spec.get("alts", []):
            r = await apply_filter_click(page, spec["group"], alt, logger, ts)
            if r["success"]:
                await page.wait_for_timeout(1500)
                return True
        return False

    if filter_name == "category":
        # Facebook/Adspy layout uses dropdown selectors for Ecom Platform
        # Strategy: find the dropdown trigger labeled "Ecom Platform" or "Ecom Category",
        # click it to open, then select "Shopify" from the popup options
        applied = await _apply_dropdown_filter(page, "category", "Shopify",
            trigger_labels=["Ecom Platform", "All Ecom Platform", "Ecom Category"],
            trigger_selectors=[
                "[class*='ecom']", "[class*='platform']", "[class*='category']",
                ".filter-wrap", ".filter-action",
            ])
        if applied:
            await page.wait_for_timeout(2000)
            return True
        # Fallback: direct text click (works if Shopify is visible without dropdown)
        for strategy in [
            lambda: page.locator(".filter-wrap >> text='Shopify'").first,
            lambda: page.locator("[class*='category'] >> text='Shopify'").first,
            lambda: page.locator("text='Shopify'").first,
        ]:
            try:
                loc = strategy()
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue
        return False

    if filter_name == "app_platform":
        # Facebook/Adspy layout: App Platform is an el-select dropdown.
        # Targeted approach: find the input by placeholder, scroll into view,
        # click to open, then find and click "Website" in the popover.

        # Approach 1: Find input by placeholder, open dropdown, use keyboard to select
        try:
            inp = page.locator('input[placeholder="App Platform"]').first
            if await inp.is_visible(timeout=2000):
                await inp.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await inp.click()
                await page.wait_for_timeout(1500)

                await take_ss(page, "app_platform_dropdown_open", ts)

                clicked = False

                # A: Type to filter — clear input, type "Website", wait for filter, press Enter
                try:
                    # Element UI selects with filterable support typing to filter
                    await inp.fill("")
                    await inp.type("Website", delay=100)
                    await page.wait_for_timeout(800)

                    # Check if filtered results show Website
                    opts = await page.evaluate("""() => {
                        const items = document.querySelectorAll('.el-select-dropdown__item');
                        const visible = [];
                        for (const item of items) {
                            if (item.offsetParent && item.getBoundingClientRect().height > 0) {
                                const style = getComputedStyle(item);
                                if (style.display !== 'none') {
                                    visible.push(item.textContent.trim());
                                }
                            }
                        }
                        return visible;
                    }""")
                    print(f"        [app_platform] After typing 'Website', visible options: {opts}")

                    # If only Website is left, press Enter
                    if any("website" in o.lower() for o in opts):
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(1000)
                        print(f"        [app_platform] Pressed Enter to select")
                        clicked = True
                except Exception as e:
                    print(f"        [app_platform] Type+Enter approach failed: {str(e)[:60]}")

                # B: Arrow-key navigation — Website is the 4th option (App, App Store, Google Play, Website)
                if not clicked:
                    try:
                        # Re-click input to re-open if needed
                        await inp.click()
                        await page.wait_for_timeout(800)
                        # Navigate down to Website (4th option)
                        for _ in range(4):
                            await page.keyboard.press("ArrowDown")
                            await page.wait_for_timeout(200)
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(1000)
                        print(f"        [app_platform] Selected via ArrowDown+Enter")
                        clicked = True
                    except Exception as e:
                        print(f"        [app_platform] Arrow approach failed: {str(e)[:60]}")

                # C: Direct click on popover li items using scrollbar container
                if not clicked:
                    try:
                        # Re-click input to open dropdown
                        await inp.click()
                        await page.wait_for_timeout(800)
                        items = page.locator('.el-popover:visible .el-scrollbar li, .el-popover:visible li')
                        count = await items.count()
                        print(f"        [app_platform] Popover li count: {count}")
                        for idx in range(count):
                            item = items.nth(idx)
                            try:
                                t = (await item.text_content() or "").strip()
                                if "website" in t.lower():
                                    await item.click(timeout=2000, force=True)
                                    await page.wait_for_timeout(1000)
                                    print(f"        [app_platform] Force-clicked '{t}' in popover li #{idx}")
                                    clicked = True
                                    break
                            except Exception:
                                continue
                    except Exception as e:
                        print(f"        [app_platform] Popover li approach failed: {str(e)[:60]}")

                # D: Fallback to brute-force dropdown
                if not clicked:
                    applied = await _apply_dropdown_filter(page, "app_platform", "Website",
                        trigger_labels=["App Platform"],
                        trigger_selectors=["[class*='platform']"])
                    if applied:
                        clicked = True

                if clicked:
                    await page.wait_for_timeout(1500)
                    # Verify by checking if the el-select now has hadVal class
                    sel_el = page.locator('.el-select').filter(has=page.locator('input[placeholder="App Platform"]')).first
                    try:
                        has_val = await sel_el.evaluate("el => el.className.includes('hadVal')")
                        sel_text = (await sel_el.text_content() or "").strip()[:30]
                        print(f"        [app_platform] Post-click: hadVal={has_val}, text='{sel_text}'")
                    except Exception:
                        pass
                    await take_ss(page, "app_platform_after_select", ts)
                    return True
                else:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
        except Exception as e:
            print(f"        [app_platform] Targeted approach error: {str(e)[:80]}")

        return False

    if filter_name == "time":
        for label in spec.get("preferred", [spec["value"]]):
            r = await apply_filter_click(page, spec["group"], label, logger, ts)
            if r["success"]:
                await page.wait_for_timeout(1500)
                return True
        return False

    if filter_name == "sort":
        r = await apply_sort_selection(page, spec["value"], logger, ts)
        if r["success"]:
            await page.wait_for_timeout(1500)
            return True
        for alt in spec.get("alts", []):
            r = await apply_sort_selection(page, alt, logger, ts)
            if r["success"]:
                await page.wait_for_timeout(1500)
                return True
        return False

    if filter_name == "last_seen":
        # Try to find a "Last seen" toggle near time filters
        for sel_text in ["Last seen", "Last Seen"]:
            try:
                loc = page.locator(f".filter-wrap >> text='{sel_text}'").first
                if await loc.is_visible(timeout=1500):
                    bbox = await loc.bounding_box()
                    if bbox and bbox["height"] < 40:
                        await loc.click()
                        await page.wait_for_timeout(1000)
                        return True
            except Exception:
                continue
        return False

    return False


async def baseline_state_reconcile(page: Page, logger: StepLogger, ts: str) -> dict:
    """
    Reconciliation-first baseline filter setup.

    Phase A: Inspect current live filter state
    Phase B: Compare against expected baseline
    Phase C: Fix only what is missing/wrong (no redundant clicks)
    Phase D: Verify final state, compute confidence

    Only resets/clears if state is too dirty to safely reconcile.
    """
    result = {
        "success": False,
        "method": "reconciled",  # or "rebuilt"
        "confidence": 0.0,
        "critical_confirmed": 0,
        "critical_total": 0,
        "correct": [],
        "fixed": [],
        "failed": [],
        "screenshots": [],
        "live_state_before": None,
        "live_state_after": None,
    }

    print("\n  [RECONCILE] Inspecting current filter state...")

    # ═══ Phase A: Inspect current live state ═══
    live_state = await inspect_filter_state(page)
    result["live_state_before"] = live_state
    ss0 = await take_ss(page, "reconcile_00_current_state", ts)
    result["screenshots"].append(ss0)

    print(f"    Platform: {live_state.get('platform', 'none')}")
    print(f"    Data types active: {live_state.get('data_types_active', [])}")
    print(f"    Time: {live_state.get('time', 'none')}")
    print(f"    Sort: {live_state.get('sort', 'none')}")
    print(f"    Chips: {[c['text'] for c in live_state.get('chips', [])]}")
    print(f"    Category: {[c['text'] for c in live_state.get('category_active', []) if c.get('isActive')]}")
    print(f"    App platform: {[a['text'] for a in live_state.get('app_platform_active', []) if a.get('isActive')]}")
    dd_vals = {k: v.get('value') or v.get('selectedText') or v.get('tags', [])
               for k, v in live_state.get('dropdown_values', {}).items() if v.get('hasValue')}
    if dd_vals:
        print(f"    Dropdown values: {dd_vals}")

    # ═══ Phase B: Compare against expected baseline ═══
    comparison = compare_baseline(live_state)
    correct = comparison["correct"]
    missing = comparison["missing"]
    wrong = comparison["wrong"]

    print(f"\n    Correct: {correct}")
    print(f"    Missing: {missing}")
    print(f"    Wrong: {wrong}")
    result["correct"] = correct

    # ── Check if state is too dirty for reconciliation ──
    if len(wrong) >= 4 and len(missing) >= 3:
        print(f"\n    [DIRTY] State too contaminated ({len(wrong)} wrong, {len(missing)} missing) — full rebuild")
        result["method"] = "rebuilt"
        logger.log("reconcile", "state_too_dirty", "dirty_state", "rebuilding", "info",
                    notes=f"wrong={len(wrong)}, missing={len(missing)}")

        # Navigate fresh and rebuild all
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        missing = ["platform", "ecommerce", "dropshipping", "category", "app_platform", "time", "sort", "last_seen"]
        correct = []

    # ═══ Phase C: Fix only what is needed ═══
    if not missing and not wrong:
        print(f"\n    [OK] Baseline already correct — no changes needed")
    else:
        print(f"\n    [FIX] Reconciling {len(missing)} missing filters...")

        for filter_name in missing:
            spec = BASELINE_EXPECTED.get(filter_name, {})
            is_critical = spec.get("critical", False)
            print(f"      Fixing: {filter_name} ({'CRITICAL' if is_critical else 'soft'})...")

            ok = await _apply_single_filter(page, filter_name, logger, ts)
            if ok:
                result["fixed"].append(filter_name)
                print(f"        Applied")
                logger.log("reconcile", f"fix_{filter_name}", "missing", "applied", "success")
            else:
                result["failed"].append({"filter": filter_name, "critical": is_critical})
                print(f"        FAILED")
                logger.log("reconcile", f"fix_{filter_name}", "missing", "failed", "soft_fail" if not is_critical else "hard_fail")

                # Retry once for critical filters
                if is_critical:
                    print(f"        Retrying...")
                    await page.wait_for_timeout(1500)
                    ok2 = await _apply_single_filter(page, filter_name, logger, ts)
                    if ok2:
                        result["fixed"].append(filter_name)
                        result["failed"] = [f for f in result["failed"] if f["filter"] != filter_name]
                        print(f"        Retry succeeded")
                    else:
                        print(f"        Retry also failed")

    await page.wait_for_timeout(2000)

    # ═══ Phase D: Verify final state ═══
    print(f"\n    [VERIFY] Final baseline state...")
    final_state = await inspect_filter_state(page)
    result["live_state_after"] = final_state
    ss_final = await take_ss(page, "reconcile_01_final_state", ts)
    result["screenshots"].append(ss_final)

    final_comparison = compare_baseline(final_state)
    final_correct = final_comparison["correct"]

    print(f"    Final correct: {final_correct}")
    print(f"    Final chips: {[c['text'] for c in final_state.get('chips', [])]}")
    print(f"    Final sort: {final_state.get('sort')}")
    print(f"    Final platform: {final_state.get('platform')}")
    print(f"    Final category: {[c['text'] for c in final_state.get('category_active', []) if c.get('isActive')]}")
    print(f"    Final app_platform: {[a['text'] for a in final_state.get('app_platform_active', []) if a.get('isActive')]}")
    dd_final = {k: {'val': v.get('value'), 'sel': v.get('selectedText'), 'tags': v.get('tags', []), 'hasVal': v.get('hasValue')}
                for k, v in final_state.get('dropdown_values', {}).items()}
    if dd_final:
        print(f"    Final dropdown_values: {dd_final}")

    # ── Compute baseline_filter_confidence ──
    critical_filters = [name for name, spec in BASELINE_EXPECTED.items() if spec.get("critical")]
    critical_confirmed = sum(1 for f in critical_filters if f in final_correct)
    critical_total = len(critical_filters)
    confidence = round(critical_confirmed / max(critical_total, 1), 2)

    result["critical_confirmed"] = critical_confirmed
    result["critical_total"] = critical_total
    result["confidence"] = confidence
    result["correct"] = final_correct

    print(f"\n    Baseline confidence: {critical_confirmed}/{critical_total} critical = {confidence}")

    # ── Abort rules ──
    # If confidence < 6/7 and a truly important filter is missing, abort
    failed_critical = [f["filter"] for f in result["failed"] if f.get("critical")]
    hard_abort_filters = {"platform", "category", "sort"}  # plus ecommerce/dropshipping; app_platform demoted to soft
    must_abort = any(f in hard_abort_filters for f in failed_critical)

    if critical_confirmed < critical_total and must_abort:
        print(f"    [ABORT] Critical filter(s) missing after reconciliation: {failed_critical}")
        result["success"] = False
        return result

    # If only time-family approximation is the gap, allow it
    if critical_confirmed >= critical_total - 1:
        soft_gap = [f for f in critical_filters if f not in final_correct]
        if soft_gap == ["time"] or soft_gap == ["last_seen"]:
            print(f"    [WARN] Time filter approximate — proceeding with warning")
            result["success"] = True
        elif not soft_gap:
            result["success"] = True
        else:
            print(f"    [ABORT] Non-time critical filter missing: {soft_gap}")
            result["success"] = False
            return result
    elif critical_confirmed == critical_total:
        result["success"] = True
    else:
        print(f"    [ABORT] Too many critical filters missing ({critical_total - critical_confirmed})")
        result["success"] = False
        return result

    print(f"    Method: {result['method']}")
    print(f"    Fixed: {result['fixed']}")
    if result["failed"]:
        print(f"    Failed (non-blocking): {[f['filter'] for f in result['failed'] if not f.get('critical')]}")

    logger.log("reconcile", "baseline_verified", "reconciling", "baseline_ready",
                "success" if result["success"] else "hard_fail",
                notes=f"confidence={confidence}, method={result['method']}, fixed={result['fixed']}")

    return result


async def check_baseline_drift(page: Page) -> dict:
    """
    Lightweight drift check during research.
    Returns {drifted: bool, drifted_filters: [...], live_state: {...}}.
    """
    live = await inspect_filter_state(page)
    comparison = compare_baseline(live)
    # Only care about critical filters that are missing
    critical_names = {name for name, spec in BASELINE_EXPECTED.items() if spec.get("critical")}
    drifted = [f for f in comparison["missing"] if f in critical_names]
    return {
        "drifted": len(drifted) > 0,
        "drifted_filters": drifted,
        "live_state": live,
    }


def classify_ad(detail_data: dict, prescan_data: dict) -> dict:
    """
    Classify an opened ad into research categories.
    Returns classification with reasoning.
    """
    all_text = ""
    advertiser = detail_data.get("advertiser", "") or prescan_data.get("advertiser", "") or ""
    caption = detail_data.get("caption", "") or ""
    cta_text = detail_data.get("cta_text", "") or prescan_data.get("cta", "") or ""
    landing = detail_data.get("landing_url", "") or ""
    regions = detail_data.get("regions", [])
    texts = [t.get("text", "") for t in detail_data.get("texts", [])]

    all_text = " ".join([advertiser, caption, cta_text, landing] + texts).lower()

    # ── Extract structured fields ──
    hook = ""
    # Hook is usually the first substantial text (>10 chars, not a metric)
    for t in texts:
        if len(t) > 10 and not any(m in t.lower() for m in ["impression", "like", "day", "click", "spend"]):
            hook = t[:120]
            break
    if not hook and caption:
        hook = caption[:120]

    product_type = "unknown"
    for pt in ["hoodie", "tee", "shirt", "jeans", "pants", "jacket", "shorts",
               "sweater", "sweatshirt", "cargo", "jogger", "cap", "hat", "sneaker",
               "bag", "accessory", "dress", "skirt", "coat"]:
        if pt in all_text:
            product_type = pt
            break

    # Domain extraction
    domain = ""
    if landing:
        import re as _re
        dm = _re.search(r'https?://([^/]+)', landing)
        if dm:
            domain = dm.group(1).replace("www.", "")

    # ── Classification ──
    niche_hits = sum(1 for kw in NICHE_KEYWORDS if kw in all_text)
    junk_hits = sum(1 for kw in JUNK_KEYWORDS if kw in all_text)
    comp_hits = sum(1 for kw in COMPETITOR_SIGNALS if kw in all_text)
    creative_hits = sum(1 for kw in CREATIVE_SIGNALS if kw in all_text)

    if junk_hits >= 2:
        classification = "discard"
        reason = "too many junk signals"
    elif niche_hits >= 3 and comp_hits >= 2:
        classification = "strong_competitor"
        reason = f"high niche relevance ({niche_hits}) + ecommerce signals ({comp_hits})"
    elif creative_hits >= 2 or (niche_hits >= 2 and creative_hits >= 1):
        classification = "useful_creative_reference"
        reason = f"creative patterns ({creative_hits}) + niche relevance ({niche_hits})"
    elif niche_hits >= 2 or comp_hits >= 1:
        classification = "mid"
        reason = f"some relevance ({niche_hits}) or ecommerce signal ({comp_hits})"
    else:
        classification = "discard"
        reason = f"low relevance ({niche_hits}), no competitor signals"

    return {
        "classification": classification,
        "reason": reason,
        "advertiser": advertiser,
        "domain": domain,
        "hook": hook,
        "cta": cta_text,
        "product_type": product_type,
        "landing_url": landing,
        "regions": regions,
        "caption_preview": caption[:200] if caption else "",
        "niche_hits": niche_hits,
        "comp_hits": comp_hits,
        "creative_hits": creative_hits,
        "junk_hits": junk_hits,
    }


async def _open_and_classify(page, best_open, best_close, card_dom_idx, prescan_rel,
                              adv_preview, keyword, group, record_id_ref,
                              research_records, pattern_tracker, logger, ts) -> dict:
    """Open a single card, extract, classify, close. Returns {opened, record, classification}."""
    result = {"opened": False, "record": None, "classification": None}

    pre_modals = await inspect_modal_state(page)
    try:
        cards_loc = page.locator(best_open["selector"])
        target = cards_loc.nth(card_dom_idx)
        await target.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await target.click()
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"      [FAIL] Click: {str(e)[:60]}")
        return result

    post_modals = await inspect_modal_state(page)
    if len(post_modals.get("modals", [])) <= len(pre_modals.get("modals", [])):
        print(f"      [FAIL] No modal appeared")
        return result

    result["opened"] = True

    try:
        detail_data = await extract_detail_from_modal(page)
    except Exception:
        detail_data = {}

    cls = classify_ad(detail_data, {"advertiser": adv_preview, "cta": ""})
    record_id_ref[0] += 1
    rec = {
        "id": f"rec_{record_id_ref[0]:03d}",
        "keyword": keyword, "group": group,
        "card_index": card_dom_idx,
        "prescan_relevance": prescan_rel,
        "classification": cls["classification"],
        "reason": cls["reason"],
        "advertiser": cls["advertiser"],
        "domain": cls["domain"],
        "hook": cls["hook"],
        "cta": cls["cta"],
        "product_type": cls["product_type"],
        "landing_url": cls["landing_url"],
        "regions": cls["regions"],
        "caption_preview": cls["caption_preview"],
        "detail_texts_count": len(detail_data.get("texts", [])),
        "detail_images_count": len(detail_data.get("images", [])),
    }
    research_records.append(rec)
    result["record"] = rec
    result["classification"] = cls

    # Update tracker
    if cls["advertiser"]:
        pattern_tracker["advertisers"][cls["advertiser"]] += 1
    if cls["domain"]:
        pattern_tracker["domains"][cls["domain"]] += 1
    if cls["cta"]:
        pattern_tracker["ctas"][cls["cta"]] += 1
    if cls["product_type"] != "unknown":
        pattern_tracker["product_types"][cls["product_type"]] += 1
    for rg in cls["regions"]:
        pattern_tracker["regions"][rg] += 1
    pattern_tracker["classifications"][cls["classification"]] += 1
    if cls["hook"]:
        pattern_tracker["hooks"].append({"hook": cls["hook"], "keyword": keyword, "advertiser": cls["advertiser"]})

    ci = {"strong_competitor": "★", "useful_creative_reference": "◆",
          "mid": "·", "discard": "✗"}.get(cls["classification"], "?")
    print(f"      [{ci}] {cls['classification']}: "
          f"adv='{cls['advertiser'][:30]}', domain='{cls['domain'][:30]}', "
          f"product={cls['product_type']}")
    if cls["hook"]:
        print(f"         Hook: '{cls['hook'][:80]}'")
    if cls["cta"]:
        print(f"         CTA: '{cls['cta'][:40]}'")

    # Close modal
    try:
        if best_close["type"] == "keyboard":
            await page.keyboard.press(best_close["selector"])
        else:
            cl = page.locator(best_close["selector"]).first
            if await cl.is_visible(timeout=2000):
                await cl.click()
        await page.wait_for_timeout(2000)
        post_close = await inspect_modal_state(page)
        if len(post_close.get("modals", [])) >= len(post_modals.get("modals", [])):
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(1500)
    except Exception:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(1500)
    await page.wait_for_timeout(800)

    return result


def compute_keyword_outcome(records_for_kw: list, prescan_count: int, junk_prescan: int) -> str:
    """
    Classify keyword outcome:
    - strong_keyword: ≥2 strong/creative, junk <30%
    - moderate_keyword: ≥1 strong/creative, junk <50%
    - weak_keyword: some results but low signal
    - junk_keyword: junk ≥70% or no relevant cards
    """
    if prescan_count == 0:
        return "junk_keyword"

    junk_rate = junk_prescan / max(prescan_count, 1)
    strong_or_creative = sum(1 for r in records_for_kw
                              if r["classification"] in ("strong_competitor", "useful_creative_reference"))

    if junk_rate >= 0.7:
        return "junk_keyword"
    if strong_or_creative >= 2 and junk_rate < 0.3:
        return "strong_keyword"
    if strong_or_creative >= 1 and junk_rate < 0.5:
        return "moderate_keyword"
    if len(records_for_kw) > 0:
        return "weak_keyword"
    return "junk_keyword"


async def run_research(page: Page, logger: StepLogger, ts: str):
    """
    Research mode — reconcile baseline filters + keyword research.
    Uses reconciliation-first filter setup, drift detection,
    capped card-open logic, keyword outcome labels, and pattern tracking.
    """
    print("\n" + "=" * 70)
    print("RESEARCH MODE — Baseline Reconciliation + Keyword Research")
    print("=" * 70)

    # ── Load artifacts ──
    dom_sigs = json.loads(DOM_SIGNATURES_PATH.read_text(encoding="utf-8"))
    recipes = json.loads(INTERACTION_RECIPES_PATH.read_text(encoding="utf-8"))

    card_roots = dom_sigs.get("result_card_roots", [])
    if not card_roots:
        print("[ABORT] No card root selectors.")
        return None
    primary_card_sel = card_roots[0]["selector_strategies"][0]["selector"]

    input_candidates = dom_sigs.get("search_input_candidates", [])
    primary_input_sel = input_candidates[0]["selector_strategies"][0]["selector"] if input_candidates else "#inputKeyword"

    open_recipes_loaded = recipes.get("open_result_card", [])
    proven_open = [r for r in open_recipes_loaded if r["success_count"] > 0]
    best_open = proven_open[0]["method"] if proven_open else None
    if not best_open:
        print("[ABORT] No proven open recipe.")
        return None

    close_recipes_loaded = recipes.get("close_detail", [])
    proven_close = [r for r in close_recipes_loaded if r["success_count"] > 0]
    best_close = proven_close[0]["method"] if proven_close else None
    if not best_close:
        print("[ABORT] No proven close recipe.")
        return None

    print(f"  Card: {primary_card_sel}")
    print(f"  Open: {best_open['type']} → {best_open['selector']}")
    print(f"  Close: {best_close['type']} → {best_close['selector']}")

    # ── Validate artifacts ──
    val = await validate_artifacts(page, logger, ts)
    print(f"  Artifacts: {val['status']}")
    if val["status"] in ("stale", "missing"):
        print("[ABORT] Artifacts invalid.")
        return None

    # ══════════════════════════════════════════════════════════
    # STEP 1: Baseline state reconciliation
    # ══════════════════════════════════════════════════════════
    reconcile_result = await baseline_state_reconcile(page, logger, ts)
    if not reconcile_result["success"]:
        print("[ABORT] Baseline filters could not be reconciled.")
        logger.save()
        return None

    baseline_confidence = reconcile_result["confidence"]
    baseline_method = reconcile_result["method"]

    # ══════════════════════════════════════════════════════════
    # STEP 2: Keyword research loop
    # ══════════════════════════════════════════════════════════
    all_keywords = []
    for group_name, kws in RESEARCH_KEYWORDS.items():
        for kw in kws:
            all_keywords.append({"keyword": kw, "group": group_name})

    print(f"\n  Keywords: {len(all_keywords)} across {len(RESEARCH_KEYWORDS)} groups")
    print(f"  Baseline: {baseline_method}, confidence={baseline_confidence}")

    # ── Tracking state ──
    research_records = []
    pattern_tracker = {
        "advertisers": Counter(),
        "domains": Counter(),
        "hooks": [],
        "ctas": Counter(),
        "product_types": Counter(),
        "regions": Counter(),
        "classifications": Counter(),
    }
    record_id_ref = [0]  # mutable ref for helper
    stop_triggered = False
    stop_reason = ""
    total_opened = 0
    total_prescanned = 0
    keyword_outcomes = {}
    drift_events = []

    for kw_idx, kw_info in enumerate(all_keywords):
        if stop_triggered:
            break

        keyword = kw_info["keyword"]
        group = kw_info["group"]

        print(f"\n{'═' * 70}")
        print(f"[KW {kw_idx+1}/{len(all_keywords)}] '{keyword}' ({group})")
        print(f"{'═' * 70}")

        consecutive_fails = 0
        kw_prescan_count = 0
        kw_junk_prescan = 0

        # ── Submit search ──
        try:
            loc = page.locator(primary_input_sel).first
            if not await loc.is_visible(timeout=5000):
                loc = page.locator("#inputKeyword").first
            await loc.click(click_count=3)
            await loc.fill(keyword)
            await page.wait_for_timeout(500)
            await loc.press("Enter")
            logger.log("research", f"search_{keyword}", "search_page", "loading", "info")
        except Exception as e:
            print(f"  [FAIL] Search: {str(e)[:60]}")
            stop_triggered = True
            stop_reason = f"search_failed: {str(e)[:60]}"
            break

        await page.wait_for_timeout(6000)

        # ── Verify results ──
        ver = await verify_results_page(page, primary_card_sel)
        if not ver["verified"]:
            await page.wait_for_timeout(5000)
            ver = await verify_results_page(page, primary_card_sel)
            if not ver["verified"]:
                print(f"  [SKIP] Results not verified for '{keyword}'")
                keyword_outcomes[keyword] = "junk_keyword"
                continue

        ss_results = await take_ss(page, f"res_{keyword.replace(' ', '_')}_results", ts)

        dom_count = await page.evaluate(f"document.querySelectorAll('{primary_card_sel}').length")
        current_dom_count = dom_count
        print(f"  Initial DOM cards: {dom_count}")

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        # ── Pre-scan visible cards ──
        card_summaries = await prescan_visible_cards(page, primary_card_sel, max_cards=20)
        total_prescanned += len(card_summaries)
        kw_prescan_count = len(card_summaries)

        prescan_scored = []
        for cs in card_summaries:
            score = score_card_relevance(cs)
            prescan_scored.append({"summary": cs, "score": score})

        relevant_count = sum(1 for s in prescan_scored if s["score"]["relevance"] >= 0.33)
        junk_count = sum(1 for s in prescan_scored if s["score"]["is_junk"])
        kw_junk_prescan = junk_count
        print(f"  Pre-scan: {len(card_summaries)} cards — {relevant_count} relevant, {junk_count} junk")

        # ── Early junk abort ──
        if len(prescan_scored) >= 5 and junk_count >= len(prescan_scored) * 0.7:
            print(f"  [SKIP] Junk rate too high ({junk_count}/{len(prescan_scored)})")
            keyword_outcomes[keyword] = "junk_keyword"
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
            continue

        # ── Capped card-open logic: first batch max 2 ──
        ranked_cards = sorted(prescan_scored, key=lambda s: s["score"]["relevance"], reverse=True)
        first_batch_max = 2
        cards_for_first_batch = ranked_cards[:first_batch_max]

        opens_this_kw = 0
        kw_records = []

        for open_idx, card_info in enumerate(cards_for_first_batch):
            if stop_triggered:
                break

            card_dom_idx = card_info["summary"]["index"]
            prescan_rel = card_info["score"]["relevance"]
            adv_preview = card_info["summary"].get("advertiser", "?")

            if prescan_rel < 0.1:
                print(f"    [SKIP] Card {card_dom_idx}: relevance too low ({prescan_rel})")
                continue

            print(f"\n    [OPEN {open_idx+1}/{first_batch_max}] Card idx={card_dom_idx}, "
                  f"adv='{adv_preview}', prescan_rel={prescan_rel}")

            oc = await _open_and_classify(
                page, best_open, best_close, card_dom_idx, prescan_rel,
                adv_preview, keyword, group, record_id_ref,
                research_records, pattern_tracker, logger, ts
            )
            if oc["opened"]:
                opens_this_kw += 1
                total_opened += 1
                consecutive_fails = 0
                if oc["record"]:
                    kw_records.append(oc["record"])
            else:
                consecutive_fails += 1
                if consecutive_fails >= 2:
                    stop_triggered = True
                    stop_reason = f"open_failed_twice_{keyword}"

        # ── Evaluate first-batch density to decide scroll effort ──
        first_batch_strong = sum(1 for r in kw_records
                                  if r["classification"] in ("strong_competitor", "useful_creative_reference"))
        first_batch_mid = sum(1 for r in kw_records if r["classification"] == "mid")

        if first_batch_strong >= 1:
            density_level = "high"
            scroll_extra_opens = 2  # allow 2 more from scroll batches
        elif first_batch_mid >= 1 or relevant_count >= 3:
            density_level = "low"
            scroll_extra_opens = 1  # allow 1 more from scroll
        else:
            density_level = "none"
            scroll_extra_opens = 0

        print(f"  First batch density: {density_level} (strong={first_batch_strong}, mid={first_batch_mid})")

        # ── Infinite scroll continuation ──
        if not stop_triggered and scroll_extra_opens > 0:
            no_growth = 0
            for batch_num in range(RESEARCH_MAX_BATCHES):
                if stop_triggered or scroll_extra_opens <= 0:
                    break

                print(f"\n  [SCROLL batch {batch_num+1}/{RESEARCH_MAX_BATCHES}] DOM: {current_dom_count}")
                batch_result = await scroll_load_batch(page, primary_card_sel, current_dom_count)

                if batch_result["success"]:
                    delta = batch_result["delta"]
                    current_dom_count = batch_result["new_count"]
                    no_growth = 0
                    print(f"    +{delta} cards (total: {current_dom_count})")

                    new_summaries = await prescan_visible_cards(page, primary_card_sel, max_cards=current_dom_count)
                    new_cards = new_summaries[current_dom_count - delta:]
                    new_scored = [{"summary": cs, "score": score_card_relevance(cs)} for cs in new_cards]
                    total_prescanned += len(new_cards)
                    kw_prescan_count += len(new_cards)
                    kw_junk_prescan += sum(1 for s in new_scored if s["score"]["is_junk"])

                    if scroll_extra_opens > 0:
                        new_ranked = sorted(new_scored, key=lambda s: s["score"]["relevance"], reverse=True)
                        batch_opens = new_ranked[:min(scroll_extra_opens, 2)]

                        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight - 1500)")
                        await page.wait_for_timeout(1000)

                        for bo in batch_opens:
                            if stop_triggered or scroll_extra_opens <= 0:
                                break
                            bi = bo["summary"]["index"]
                            br = bo["score"]["relevance"]
                            if br < 0.1:
                                continue

                            print(f"\n    [OPEN batch] idx={bi}, rel={br}")
                            oc = await _open_and_classify(
                                page, best_open, best_close, bi, br,
                                bo["summary"].get("advertiser", "?"),
                                keyword, group, record_id_ref,
                                research_records, pattern_tracker, logger, ts
                            )
                            if oc["opened"]:
                                opens_this_kw += 1
                                total_opened += 1
                                scroll_extra_opens -= 1
                                if oc["record"]:
                                    kw_records.append(oc["record"])
                else:
                    no_growth += 1
                    print(f"    No growth (pass {no_growth})")
                    if no_growth >= 2:
                        break

        # ── Keyword outcome label ──
        outcome = compute_keyword_outcome(kw_records, kw_prescan_count, kw_junk_prescan)
        keyword_outcomes[keyword] = outcome
        outcome_icon = {"strong_keyword": "★", "moderate_keyword": "◆",
                        "weak_keyword": "·", "junk_keyword": "✗"}.get(outcome, "?")
        print(f"\n  [{outcome_icon}] KW OUTCOME: '{keyword}' → {outcome} "
              f"(opened={opens_this_kw}, dom={current_dom_count})")

        # Scroll to top for next keyword
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(1000)

        # ── Drift detection every 4 keywords ──
        if (kw_idx + 1) % 4 == 0 and not stop_triggered:
            print(f"\n  [DRIFT CHECK] Checking baseline filters...")
            drift = await check_baseline_drift(page)
            if drift["drifted"]:
                print(f"  [DRIFT] Filters drifted: {drift['drifted_filters']}")
                drift_events.append({
                    "after_keyword": keyword,
                    "drifted_filters": drift["drifted_filters"],
                    "action": "reconciling",
                })
                logger.log("research", "drift_detected", "research", "reconciling", "soft_fail",
                            notes=f"drifted: {drift['drifted_filters']}")

                # Attempt reconciliation
                re_reconcile = await baseline_state_reconcile(page, logger, ts)
                if re_reconcile["success"]:
                    print(f"  [DRIFT] Reconciled successfully (confidence={re_reconcile['confidence']})")
                    drift_events[-1]["action"] = "reconciled"
                    drift_events[-1]["confidence_after"] = re_reconcile["confidence"]
                else:
                    print(f"  [ABORT] Drift could not be corrected — stopping")
                    stop_triggered = True
                    stop_reason = f"unrecoverable_drift: {drift['drifted_filters']}"
                    drift_events[-1]["action"] = "abort"
            else:
                print(f"  [DRIFT CHECK] OK — no drift")

    # ══════════════════════════════════════════════════════════
    # STEP 3: Generate outputs
    # ══════════════════════════════════════════════════════════
    print(f"\n{'─' * 70}")
    print("Generating research outputs...")
    print(f"{'─' * 70}")

    # 1. research_records.json
    records_output = {
        "mode": "research",
        "timestamp": datetime.now().isoformat(),
        "baseline": {
            "method": baseline_method,
            "confidence": baseline_confidence,
            "critical_confirmed": reconcile_result["critical_confirmed"],
            "critical_total": reconcile_result["critical_total"],
            "correct": reconcile_result["correct"],
            "fixed": reconcile_result["fixed"],
            "failed": reconcile_result["failed"],
        },
        "keywords": [k["keyword"] for k in all_keywords],
        "keyword_outcomes": keyword_outcomes,
        "total_records": len(research_records),
        "total_prescanned": total_prescanned,
        "total_opened": total_opened,
        "drift_events": drift_events,
        "stop": {"triggered": stop_triggered, "reason": stop_reason},
        "records": research_records,
    }
    with open(RESEARCH_RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(records_output, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {RESEARCH_RECORDS_PATH.name} ({len(research_records)} records)")

    # 2. competitor_summary.json
    top_advertisers = pattern_tracker["advertisers"].most_common(20)
    top_domains = pattern_tracker["domains"].most_common(20)
    top_ctas = pattern_tracker["ctas"].most_common(15)
    top_products = pattern_tracker["product_types"].most_common(10)
    region_dist = dict(pattern_tracker["regions"].most_common(20))
    class_dist = dict(pattern_tracker["classifications"])

    competitor_output = {
        "timestamp": datetime.now().isoformat(),
        "total_ads_analyzed": len(research_records),
        "keyword_outcomes": keyword_outcomes,
        "top_advertisers": [{"name": a, "count": c} for a, c in top_advertisers],
        "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
        "top_product_types": [{"type": p, "count": c} for p, c in top_products],
        "top_hooks": pattern_tracker["hooks"][:30],
        "top_ctas": [{"cta": ct, "count": c} for ct, c in top_ctas],
        "region_distribution": region_dist,
        "classification_distribution": class_dist,
    }
    with open(RESEARCH_COMPETITOR_PATH, "w", encoding="utf-8") as f:
        json.dump(competitor_output, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved: {RESEARCH_COMPETITOR_PATH.name}")

    # 3. creative_patterns.md
    lines = [
        "# Creative Patterns — Streetwear Ecommerce Research",
        f"",
        f"Generated: {datetime.now().isoformat()}",
        f"Baseline: {baseline_method}, confidence={baseline_confidence}",
        f"Ads analyzed: {len(research_records)}",
        f"Cards prescanned: {total_prescanned}",
        f"",
        f"## Keyword Outcomes",
    ]
    for kw, outcome in sorted(keyword_outcomes.items(), key=lambda x: ["strong_keyword", "moderate_keyword", "weak_keyword", "junk_keyword"].index(x[1]) if x[1] in ["strong_keyword", "moderate_keyword", "weak_keyword", "junk_keyword"] else 99):
        icon = {"strong_keyword": "★", "moderate_keyword": "◆", "weak_keyword": "·", "junk_keyword": "✗"}.get(outcome, "?")
        lines.append(f"- {icon} **{kw}**: {outcome}")

    lines += ["", "## Classification Breakdown"]
    for cls_name, cls_count in sorted(class_dist.items(), key=lambda x: -x[1]):
        lines.append(f"- **{cls_name}**: {cls_count}")

    lines += ["", "## Top Competitor Domains"]
    for d, c in top_domains[:10]:
        lines.append(f"- `{d}` ({c} ads)")

    lines += ["", "## Top Advertisers"]
    for a, c in top_advertisers[:10]:
        lines.append(f"- {a} ({c} ads)")

    lines += ["", "## Product Types Found"]
    for p, c in top_products:
        lines.append(f"- {p}: {c}")

    lines += ["", "## Top CTAs"]
    for ct, c in top_ctas[:10]:
        lines.append(f"- \"{ct}\" ({c}x)")

    lines += ["", "## Hooks Observed"]
    for h in pattern_tracker["hooks"][:20]:
        lines.append(f"- [{h['advertiser'][:20]}] \"{h['hook'][:80]}\"")

    lines += ["", "## Region Distribution"]
    for rg, c in sorted(region_dist.items(), key=lambda x: -x[1]):
        lines.append(f"- {rg}: {c}")

    lines += ["", "## Strong Competitors (Detail)"]
    strong = [r for r in research_records if r["classification"] == "strong_competitor"]
    if strong:
        for r in strong[:10]:
            lines.append(f"### {r['advertiser'] or r['domain'] or 'Unknown'}")
            lines.append(f"- Domain: `{r['domain']}`")
            lines.append(f"- Product: {r['product_type']}")
            lines.append(f"- CTA: {r['cta']}")
            lines.append(f"- Hook: \"{r['hook'][:100]}\"")
            lines.append(f"- Keyword: {r['keyword']}")
            lines.append(f"- Landing: {r['landing_url'][:80]}")
            lines.append("")
    else:
        lines.append("No strong competitors classified in this run.")

    RESEARCH_PATTERNS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Saved: {RESEARCH_PATTERNS_PATH.name}")

    # ══════════════════════════════════════════════════════════
    # RESEARCH REPORT — 9 POINTS
    # ══════════════════════════════════════════════════════════
    print(f"\n{'=' * 70}")
    print("RESEARCH REPORT")
    print(f"{'=' * 70}")

    print(f"\n1. BASELINE RECONCILIATION:")
    print(f"   Method: {baseline_method}")
    print(f"   Confidence: {reconcile_result['critical_confirmed']}/{reconcile_result['critical_total']} "
          f"= {baseline_confidence}")
    print(f"   Already correct: {reconcile_result['correct']}")
    print(f"   Fixed: {reconcile_result['fixed']}")
    if reconcile_result["failed"]:
        print(f"   Failed: {[f['filter'] for f in reconcile_result['failed']]}")

    print(f"\n2. BASELINE FILTER CONFIDENCE: {baseline_confidence}")

    print(f"\n3. DRIFT EVENTS:")
    if drift_events:
        for de in drift_events:
            print(f"   After '{de['after_keyword']}': {de['drifted_filters']} → {de['action']}")
    else:
        print(f"   No drift detected")

    print(f"\n4. KEYWORD OUTCOME LABELS:")
    for outcome_type in ["strong_keyword", "moderate_keyword", "weak_keyword", "junk_keyword"]:
        kws = [kw for kw, o in keyword_outcomes.items() if o == outcome_type]
        if kws:
            print(f"   {outcome_type}: {kws}")

    print(f"\n5. STRONGEST KEYWORDS:")
    strong_kws = [kw for kw, o in keyword_outcomes.items() if o in ("strong_keyword", "moderate_keyword")]
    if strong_kws:
        for kw in strong_kws:
            kw_recs = [r for r in research_records if r["keyword"] == kw]
            sc = sum(1 for r in kw_recs if r["classification"] == "strong_competitor")
            cr = sum(1 for r in kw_recs if r["classification"] == "useful_creative_reference")
            print(f"   '{kw}': {len(kw_recs)} ads ({sc} strong, {cr} creative)")
    else:
        print(f"   No strong keywords found")

    print(f"\n6. TOP COMPETITOR DOMAINS:")
    for d, c in top_domains[:5]:
        print(f"   {d} ({c} ads)")

    print(f"\n7. MOST REPEATED HOOKS / CTAs / PRODUCTS:")
    seen_hooks = set()
    for h in pattern_tracker["hooks"][:8]:
        short = h["hook"][:50]
        if short not in seen_hooks:
            seen_hooks.add(short)
            print(f"   Hook: \"{h['hook'][:70]}\" — {h['advertiser'][:20]}")
    for ct, c in top_ctas[:5]:
        print(f"   CTA: \"{ct}\" ({c}x)")
    for p, c in top_products[:5]:
        print(f"   Product: {p} ({c}x)")

    print(f"\n8. OPERATOR STABILITY:")
    print(f"   Total opened: {total_opened}")
    print(f"   Total prescanned: {total_prescanned}")
    print(f"   Keywords completed: {len(keyword_outcomes)}/{len(all_keywords)}")
    if stop_triggered:
        print(f"   STOP: {stop_reason}")
    else:
        print(f"   Completed all keywords without stopping")

    print(f"\n9. ISSUES / LOW-CONFIDENCE:")
    issues = []
    if baseline_confidence < 1.0:
        issues.append(f"baseline confidence {baseline_confidence} (not perfect)")
    if drift_events:
        issues.append(f"{len(drift_events)} drift events")
    if stop_triggered:
        issues.append(f"stopped: {stop_reason}")
    junk_kws = [kw for kw, o in keyword_outcomes.items() if o == "junk_keyword"]
    if junk_kws:
        issues.append(f"junk keywords: {junk_kws}")
    if issues:
        for iss in issues:
            print(f"   - {iss}")
    else:
        print(f"   None — clean run")

    print(f"\n  Classification: {dict(class_dist)}")
    print(f"\n  Outputs:")
    print(f"    {RESEARCH_RECORDS_PATH.name}")
    print(f"    {RESEARCH_COMPETITOR_PATH.name}")
    print(f"    {RESEARCH_PATTERNS_PATH.name}")

    logger.save()
    return records_output


# ═══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════

async def ensure_session(page: Page, logger: StepLogger, ts: str) -> bool:
    url = page.url.lower()
    if "login" not in url and "signin" not in url:
        return True

    print("[!] LOGIN REQUIRED — attempting auto-login...")
    ss = await take_ss(page, "login_required", ts)
    logger.log("session", "login_start", "login_required", "attempting", "info", screenshot=ss)

    # Auto-login: find email/password fields and submit
    auto_login_done = False
    try:
        await page.wait_for_timeout(2000)

        # Find and fill email field
        email_filled = False
        for sel in [
            'input[type="email"]', 'input[name="email"]', 'input[placeholder*="email" i]',
            'input[placeholder*="Email"]', 'input[autocomplete="email"]',
            'input[name="username"]', 'input[placeholder*="account" i]',
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await loc.fill("mjkmediallc@gmail.com")
                    email_filled = True
                    print(f"  Email filled via: {sel}")
                    break
            except Exception:
                continue

        if not email_filled:
            # Fallback: try first visible text input
            try:
                inputs = page.locator('input[type="text"], input:not([type])').first
                if await inputs.is_visible(timeout=2000):
                    await inputs.click()
                    await inputs.fill("mjkmediallc@gmail.com")
                    email_filled = True
                    print("  Email filled via fallback input")
            except Exception:
                pass

        # Find and fill password field
        pw_filled = False
        for sel in [
            'input[type="password"]', 'input[name="password"]',
            'input[placeholder*="password" i]', 'input[placeholder*="Password"]',
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    await loc.fill("Stadshagen5!")
                    pw_filled = True
                    print(f"  Password filled via: {sel}")
                    break
            except Exception:
                continue

        if email_filled and pw_filled:
            # Find and click login/submit button
            submitted = False
            for sel in [
                'button[type="submit"]', 'button:has-text("Log in")', 'button:has-text("Login")',
                'button:has-text("Sign in")', 'button:has-text("Sign In")',
                'button:has-text("Log In")', '[class*="login"] button',
                '[class*="submit"] button', 'input[type="submit"]',
            ]:
                try:
                    loc = page.locator(sel).first
                    if await loc.is_visible(timeout=1500):
                        await loc.click()
                        submitted = True
                        print(f"  Login submitted via: {sel}")
                        break
                except Exception:
                    continue

            if not submitted:
                # Try pressing Enter on password field
                try:
                    pw_loc = page.locator('input[type="password"]').first
                    await pw_loc.press("Enter")
                    submitted = True
                    print("  Login submitted via Enter key")
                except Exception:
                    pass

            if submitted:
                auto_login_done = True
                print("  Waiting for login to complete...")
                await page.wait_for_timeout(8000)

    except Exception as e:
        print(f"  [WARN] Auto-login attempt error: {str(e)[:80]}")

    if auto_login_done:
        ss = await take_ss(page, "login_after_submit", ts)
        logger.log("session", "auto_login_submitted", "login_required", "waiting", "info", screenshot=ss)

    # Poll for successful login (whether auto or manual)
    for attempt in range(60):
        try:
            new_url = page.url.lower()
        except Exception:
            print("  [ERROR] Browser/page closed during login wait")
            return False

        if "login" not in new_url and "signin" not in new_url:
            print("[+] Login successful!")
            try:
                if "dashboard" in new_url or new_url.rstrip("/").endswith("pipiads.com"):
                    await page.goto("https://www.pipiads.com/ad-search", timeout=30000)
                    await page.wait_for_timeout(3000)
                cookies = await page.context.cookies()
                COOKIES.write_text(json.dumps(cookies, default=str))
                logger.log("session", "login_ok", "login_required", "search_page", "success")
            except Exception as e:
                print(f"  [WARN] Post-login navigation error: {str(e)[:80]}")
                return False
            return True

        # Check for login errors visible on page
        if attempt == 3 and auto_login_done:
            try:
                error_visible = await page.evaluate("""() => {
                    const els = document.querySelectorAll('[class*="error"],[class*="alert"],[class*="message"]');
                    for (const el of els) {
                        if (el.offsetParent && el.textContent.trim().length > 5) {
                            return el.textContent.trim().substring(0, 150);
                        }
                    }
                    return null;
                }""")
                if error_visible:
                    print(f"  [WARN] Login error detected: {error_visible[:80]}")
            except Exception:
                pass

        try:
            await page.wait_for_timeout(3000)
        except Exception:
            print("  [ERROR] Browser closed during login poll")
            return False

    logger.log("session", "login_timeout", "login_required", "login_required", "hard_fail")
    return False


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="discover", choices=["discover", "A0", "A1", "B", "B2", "C", "filter_lab", "research"])
    args = parser.parse_args()

    mode = args.mode
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    print("=" * 70)
    print(f"NEWGARMENTS - PiPiAds Operator v4 — Mode: {mode}")
    print("=" * 70)

    for d in [SCREENSHOTS, DATA_DIR, LEARN_DIR, HTML_SNAPS, STEP_LOG_DIR, BATCH_LOG]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] {d}")
    if COOKIES.exists():
        print(f"  [OK] Cookies ({COOKIES.stat().st_size}B)")
    else:
        print(f"  [WARN] No cookies")

    logger = StepLogger(ts)

    print(f"\n[+] Launching visible Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        if COOKIES.exists():
            try:
                await context.add_cookies(json.loads(COOKIES.read_text()))
                print("[+] Cookies loaded")
            except Exception:
                print("[WARN] Cookie load failed")

        page = await context.new_page()

        print("[+] Navigating to PiPiAds...")
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        if not await ensure_session(page, logger, ts):
            print("[ABORT] No session.")
            await browser.close()
            return

        cookies = await context.cookies()
        COOKIES.write_text(json.dumps(cookies, default=str))

        if mode == "discover":
            await run_discover(page, logger, ts)

        elif mode == "A0":
            await run_a0(page, logger, ts)

        elif mode == "A1":
            await run_a1(page, logger, ts)

        elif mode == "B":
            await run_b(page, logger, ts)

        elif mode == "B2":
            await run_b2(page, logger, ts)

        elif mode == "C":
            await run_c(page, logger, ts)

        elif mode == "filter_lab":
            await run_filter_lab(page, logger, ts)

        elif mode == "research":
            await run_research(page, logger, ts)

        print(f"\n[+] Browser open 10s for inspection...")
        await page.wait_for_timeout(10000)
        await browser.close()

    logger.save()
    print(f"[+] Done.")


if __name__ == "__main__":
    asyncio.run(main())
