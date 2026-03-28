"""Search for competitor presence on social platforms via Oxylabs proxy."""
import asyncio
import logging
import re
from playwright.async_api import async_playwright, Page

from bot.config import RATE_LIMIT_DELAY
from bot.proxy import launch_browser, new_page
from bot.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


async def enrich_social_profiles(competitors: list[dict]) -> list[dict]:
    """For each competitor, try to find/verify Instagram and TikTok profiles."""
    async with async_playwright() as p:
        browser = await launch_browser(p, headless=True, use_proxy=False)
        page = await new_page(browser)

        for i, comp in enumerate(competitors):
            logger.info(f"Enriching social [{i+1}/{len(competitors)}]: {comp['name']}")

            if not comp.get("instagram"):
                comp["instagram"] = await _find_instagram_from_site(page, comp["website"])

            if not comp.get("tiktok"):
                comp["tiktok"] = await _find_tiktok_from_site(page, comp["website"])

            if not comp.get("instagram") or not comp.get("tiktok"):
                brand_clean = comp["name"].split("(")[0].strip()
                social = await _search_social_handles(page, brand_clean)
                if not comp.get("instagram") and social.get("instagram"):
                    comp["instagram"] = social["instagram"]
                if not comp.get("tiktok") and social.get("tiktok"):
                    comp["tiktok"] = social["tiktok"]

            await page.wait_for_timeout(RATE_LIMIT_DELAY * 1000)

        await browser.close()

    return competitors


async def _find_instagram_from_site(page: Page, url: str) -> str:
    """Visit a website and look for Instagram links."""
    try:
        await page.goto(url, timeout=REQUEST_TIMEOUT, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        ig_links = await page.evaluate(
            """() => {
                const links = document.querySelectorAll('a[href*="instagram.com"]');
                return Array.from(links).map(l => l.href);
            }"""
        )

        for link in ig_links:
            match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', link)
            if match:
                handle = match.group(1)
                if handle not in ("p", "reel", "stories", "explore"):
                    return handle
    except Exception as e:
        logger.debug(f"Failed to check {url} for Instagram: {e}")
    return ""


async def _find_tiktok_from_site(page: Page, url: str) -> str:
    """Look for TikTok links on the page (assumes page is already loaded)."""
    try:
        tt_links = await page.evaluate(
            """() => {
                const links = document.querySelectorAll('a[href*="tiktok.com"]');
                return Array.from(links).map(l => l.href);
            }"""
        )

        for link in tt_links:
            match = re.search(r'tiktok\.com/@([a-zA-Z0-9_.]+)', link)
            if match:
                return match.group(1)
    except Exception as e:
        logger.debug(f"Failed to check for TikTok: {e}")
    return ""


async def _search_social_handles(page: Page, brand_name: str) -> dict:
    """Search Google for brand social media profiles."""
    result = {"instagram": "", "tiktok": ""}
    try:
        query = f"{brand_name} streetwear instagram tiktok"
        await page.goto(
            f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en",
            timeout=REQUEST_TIMEOUT,
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(2000)

        content = await page.content()

        ig_matches = re.findall(r'instagram\.com/([a-zA-Z0-9_.]{3,30})', content)
        for handle in ig_matches:
            if handle not in ("p", "reel", "stories", "explore", "accounts"):
                result["instagram"] = handle
                break

        tt_matches = re.findall(r'tiktok\.com/@([a-zA-Z0-9_.]{3,30})', content)
        for handle in tt_matches:
            result["tiktok"] = handle
            break

    except Exception as e:
        logger.debug(f"Social search failed for {brand_name}: {e}")

    return result
