"""Analyze competitor websites using Playwright + Oxylabs proxy."""
import asyncio
import logging
import re
from playwright.async_api import async_playwright, Page

from bot.config import RATE_LIMIT_DELAY
from bot.proxy import launch_browser, new_page
from bot.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


async def analyze_websites(competitors: list[dict]) -> list[dict]:
    """Visit each competitor's website and extract key data."""
    async with async_playwright() as p:
        browser = await launch_browser(p, headless=True, use_proxy=False)
        page = await new_page(browser)

        for i, comp in enumerate(competitors):
            logger.info(f"Analyzing website [{i+1}/{len(competitors)}]: {comp.get('website', 'N/A')}")
            if not comp.get("website"):
                comp["website_analysis"] = {"error": "No website URL"}
                continue

            analysis = await _analyze_single_site(page, comp["website"])
            comp["website_analysis"] = analysis
            await page.wait_for_timeout(RATE_LIMIT_DELAY * 1000)

        await browser.close()

    return competitors


async def _analyze_single_site(page: Page, url: str) -> dict:
    """Extract data from a single competitor website."""
    analysis = {
        "accessible": False,
        "title": "",
        "description": "",
        "hero_messaging": "",
        "product_categories": [],
        "price_range": "",
        "prices_found": [],
        "trust_signals": [],
        "scarcity_signals": [],
        "offer_signals": [],
        "social_proof": [],
        "visual_aesthetic_cues": [],
        "navigation_items": [],
        "has_reviews": False,
        "has_size_guide": False,
        "has_about_page": False,
        "shipping_info": "",
        "return_policy_visible": False,
        "email_capture": False,
        "errors": [],
    }

    try:
        response = await page.goto(url, timeout=REQUEST_TIMEOUT, wait_until="domcontentloaded")
        if not response:
            analysis["errors"].append("No response")
            return analysis

        analysis["accessible"] = response.ok
        await page.wait_for_timeout(3000)

        data = await page.evaluate(
            r"""() => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? el.innerText.trim().substring(0, 500) : '';
                };
                const getMeta = (name) => {
                    const el = document.querySelector('meta[name="' + name + '"], meta[property="' + name + '"]');
                    return el ? el.content : '';
                };

                const navItems = Array.from(document.querySelectorAll('nav a, header a, .menu a, [role="navigation"] a'))
                    .map(a => a.innerText.trim())
                    .filter(t => t.length > 1 && t.length < 40);

                const priceEls = document.querySelectorAll(
                    '[class*="price"], [class*="Price"], [data-price], .money, .product-price'
                );
                const prices = Array.from(priceEls)
                    .map(el => el.innerText.trim())
                    .filter(t => /[\$\u20ac\u00a3]\s*\d+/.test(t) || /\d+[.,]\d{2}/.test(t));

                const bodyText = document.body.innerText.toLowerCase();
                const trustSignals = [];
                const scarcitySignals = [];
                const offerSignals = [];

                if (bodyText.includes('free shipping')) trustSignals.push('Free shipping mentioned');
                if (bodyText.includes('free return')) trustSignals.push('Free returns mentioned');
                if (bodyText.includes('money back') || bodyText.includes('guarantee')) trustSignals.push('Guarantee/money-back');
                if (bodyText.includes('review') || bodyText.includes('rating')) trustSignals.push('Reviews/ratings visible');
                if (bodyText.includes('secure') || bodyText.includes('ssl')) trustSignals.push('Security signals');
                if (bodyText.includes('tracking')) trustSignals.push('Order tracking mentioned');

                if (bodyText.includes('limited')) scarcitySignals.push('Limited mentioned');
                if (bodyText.includes('sold out') || bodyText.includes('uitverkocht')) scarcitySignals.push('Sold out items');
                if (bodyText.includes('no restock') || bodyText.includes('never restock')) scarcitySignals.push('No restock policy');
                if (bodyText.includes('last chance')) scarcitySignals.push('Last chance messaging');
                if (bodyText.includes('only') && bodyText.includes('left')) scarcitySignals.push('Stock counter');
                if (bodyText.includes('drop')) scarcitySignals.push('Drop model');
                if (bodyText.includes('archive')) scarcitySignals.push('Archive concept');
                if (bodyText.includes('exclusive')) scarcitySignals.push('Exclusive mentioned');

                if (bodyText.includes('bundle') || bodyText.includes('save')) offerSignals.push('Bundle/save offer');
                if (bodyText.includes('discount') || bodyText.includes('% off')) offerSignals.push('Discount offer');
                if (bodyText.includes('subscribe') || bodyText.includes('newsletter')) offerSignals.push('Email subscribe');
                if (bodyText.includes('early access')) offerSignals.push('Early access offer');

                const hasEmailCapture = !!document.querySelector(
                    'input[type="email"], form[action*="subscribe"], .klaviyo, .newsletter, [class*="popup"]'
                );

                const hasSizeGuide = bodyText.includes('size guide') || bodyText.includes('size chart')
                    || bodyText.includes('fit guide');

                const hasAbout = navItems.some(n => {
                    const nl = n.toLowerCase();
                    return nl.includes('about') || nl.includes('story') || nl.includes('over ons');
                });

                return {
                    title: document.title,
                    description: getMeta('description') || getMeta('og:description'),
                    hero: getText('h1') || getText('.hero h2') || getText('[class*="hero"]'),
                    navItems: [...new Set(navItems)].slice(0, 15),
                    prices: [...new Set(prices)].slice(0, 20),
                    trustSignals,
                    scarcitySignals,
                    offerSignals,
                    hasEmailCapture,
                    hasSizeGuide,
                    hasAbout,
                    hasReviews: bodyText.includes('review') || !!document.querySelector('[class*="review"], [class*="Review"], .yotpo, .stamped, .judge-me, .loox'),
                };
            }"""
        )

        analysis["title"] = data.get("title", "")
        analysis["description"] = data.get("description", "")
        analysis["hero_messaging"] = data.get("hero", "")
        analysis["navigation_items"] = data.get("navItems", [])
        analysis["prices_found"] = data.get("prices", [])
        analysis["trust_signals"] = data.get("trustSignals", [])
        analysis["scarcity_signals"] = data.get("scarcitySignals", [])
        analysis["offer_signals"] = data.get("offerSignals", [])
        analysis["has_reviews"] = data.get("hasReviews", False)
        analysis["has_size_guide"] = data.get("hasSizeGuide", False)
        analysis["has_about_page"] = data.get("hasAbout", False)
        analysis["email_capture"] = data.get("hasEmailCapture", False)

        if data.get("prices"):
            nums = []
            for p in data["prices"]:
                found = re.findall(r'[\d]+[.,]?\d*', p.replace(",", "."))
                for n in found:
                    try:
                        val = float(n)
                        if 5 < val < 1000:
                            nums.append(val)
                    except ValueError:
                        pass
            if nums:
                analysis["price_range"] = f"${min(nums):.0f} - ${max(nums):.0f}"

        categories = []
        category_keywords = ["hoodie", "tee", "shirt", "pants", "jacket", "crew", "sweater",
                            "jogger", "cargo", "cap", "hat", "accessori", "shoe", "sneaker",
                            "collection", "new", "drop", "archive"]
        for nav in data.get("navItems", []):
            nav_lower = nav.lower()
            for kw in category_keywords:
                if kw in nav_lower:
                    categories.append(nav)
                    break
        analysis["product_categories"] = categories

    except Exception as e:
        analysis["errors"].append(str(e))
        logger.error(f"  Failed to analyze {url}: {e}")

    return analysis
