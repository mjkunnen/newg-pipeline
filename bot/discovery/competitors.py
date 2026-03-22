"""Discover competitors via Google search using Playwright + Oxylabs proxy."""
import asyncio
import logging
import re
from urllib.parse import urlparse
from playwright.async_api import async_playwright

from bot.config import SEARCH_QUERIES, SEED_COMPETITORS, RATE_LIMIT_DELAY
from bot.proxy import launch_browser, new_page, PROXY_TIMEOUT, PROXY_WAIT

logger = logging.getLogger(__name__)

# Domains to exclude (not competitor brands)
EXCLUDE_DOMAINS = {
    "google.com", "youtube.com", "wikipedia.org", "reddit.com",
    "tiktok.com", "instagram.com", "facebook.com", "twitter.com",
    "x.com", "pinterest.com", "amazon.com", "ebay.com",
    "trustpilot.com", "depop.com", "grailed.com", "stockx.com",
    "goat.com", "vinted.com", "shein.com", "asos.com",
    "zara.com", "hm.com", "nike.com", "adidas.com",
    "fashionunited.com", "wgsn.com", "rawshot.ai",
    "nordstrom.com", "jcpenney.com", "walmart.com",
    "independenttradingco.com", "vstees.com", "outrankbrand.com",
    "medium.com", "forbes.com", "gq.com", "highsnobiety.com",
    "hypebeast.com", "complex.com", "ssense.com",
}

# Major brands to exclude (too big / mainstream)
EXCLUDE_BRANDS = {
    "supreme", "nike", "adidas", "jordan", "bape", "off-white",
    "stussy", "palace", "carhartt", "stone island", "balenciaga",
    "gucci", "louis vuitton", "vlone", "thrasher", "vans",
    "fear of god", "essentials", "yeezy",
}


async def discover_competitors_google(max_queries: int = None) -> list[dict]:
    """Search Google for potential competitors via Oxylabs proxy."""
    queries = SEARCH_QUERIES[:max_queries] if max_queries else SEARCH_QUERIES
    all_results = []
    seen_domains = set()

    async with async_playwright() as p:
        browser = await launch_browser(p, headless=False)
        page = await new_page(browser)

        for i, query in enumerate(queries):
            logger.info(f"Searching [{i+1}/{len(queries)}]: {query}")
            try:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=en&gl=us&num=15"
                await page.goto(search_url, timeout=PROXY_TIMEOUT, wait_until="domcontentloaded")
                await page.wait_for_timeout(PROXY_WAIT)

                results = await page.evaluate(
                    """() => {
                        const items = [];
                        document.querySelectorAll('div.g').forEach(el => {
                            const link = el.querySelector('a[href^="http"]');
                            const h3 = el.querySelector('h3');
                            const snippet = el.querySelector('.VwiC3b, [data-sncf], .IsZvec');
                            if (link && h3) {
                                items.push({
                                    url: link.href,
                                    title: h3.innerText,
                                    snippet: snippet ? snippet.innerText : '',
                                });
                            }
                        });
                        if (items.length === 0) {
                            document.querySelectorAll('h3').forEach(h3 => {
                                const a = h3.closest('a');
                                if (a && a.href && a.href.startsWith('http') && !a.href.includes('google.com')) {
                                    items.push({url: a.href, title: h3.innerText, snippet: ''});
                                }
                            });
                        }
                        return items;
                    }"""
                )

                for r in results:
                    try:
                        domain = urlparse(r["url"]).netloc.replace("www.", "")
                    except Exception:
                        continue
                    if domain in seen_domains:
                        continue
                    if any(exc in domain for exc in EXCLUDE_DOMAINS):
                        continue
                    if any(brand in r.get("title", "").lower() for brand in EXCLUDE_BRANDS):
                        continue

                    seen_domains.add(domain)
                    all_results.append({
                        "name": _extract_brand_name(r.get("title", ""), domain),
                        "website": r["url"],
                        "domain": domain,
                        "title": r.get("title", ""),
                        "snippet": r.get("snippet", ""),
                        "source": "google_search",
                        "query": query,
                        "instagram": "",
                        "tiktok": "",
                    })

                logger.info(f"  Found {len(results)} results, {len(all_results)} unique brands total")

            except Exception as e:
                logger.error(f"  Search failed: {e}")

            if i < len(queries) - 1:
                await page.wait_for_timeout(RATE_LIMIT_DELAY * 1000)

        await browser.close()

    return all_results


def _extract_brand_name(title: str, domain: str) -> str:
    """Try to extract a clean brand name from the page title."""
    name = title.split("|")[0].split("-")[0].split("–")[0].split("—")[0]
    name = name.strip()
    if len(name) > 40 or not name:
        name = domain.split(".")[0].title()
    return name


def merge_with_seeds(discovered: list[dict]) -> list[dict]:
    """Merge discovered competitors with seed competitors from documents."""
    merged = []
    seen_domains = set()

    for seed in SEED_COMPETITORS:
        domain = urlparse(seed["website"]).netloc.replace("www.", "")
        seen_domains.add(domain)
        merged.append({
            "name": seed["name"],
            "website": seed["website"],
            "domain": domain,
            "title": "",
            "snippet": "",
            "source": seed["source"],
            "query": "",
            "instagram": seed.get("instagram", ""),
            "tiktok": seed.get("tiktok", ""),
        })

    for comp in discovered:
        if comp["domain"] not in seen_domains:
            seen_domains.add(comp["domain"])
            merged.append(comp)

    logger.info(f"Total competitors after merge: {len(merged)} ({len(SEED_COMPETITORS)} seeds + {len(merged) - len(SEED_COMPETITORS)} discovered)")
    return merged
