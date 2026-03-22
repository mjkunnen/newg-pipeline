"""Fetch competitor ad data from Meta Ad Library via the official API."""
import asyncio
import logging
import re
from collections import Counter
from datetime import datetime

import aiohttp

from bot.config import (
    META_ACCESS_TOKEN,
    META_AD_ARCHIVE_URL,
    META_API_FIELDS,
    META_DEFAULT_AD_LIMIT,
    RATE_LIMIT_DELAY,
)

logger = logging.getLogger(__name__)

# Theme detection keywords
THEME_PATTERNS = {
    "scarcity/exclusivity": ["limited", "exclusive", "sold out", "only", "last chance", "don't miss", "few left", "running out"],
    "quality focus": ["quality", "premium", "heavyweight", "handmade", "crafted", "built to last", "durable", "gsm"],
    "discount/sale": ["sale", "% off", "discount", "save", "deal", "clearance", "reduced"],
    "new drop/collection": ["new", "drop", "collection", "just landed", "just dropped", "releasing", "launch"],
    "free shipping": ["free shipping", "free delivery", "shipped free"],
    "social proof": ["best seller", "trending", "sold out fast", "everyone", "thousands", "reviews", "rated", "loved by"],
    "lifestyle/identity": ["wear the", "be the", "join", "lifestyle", "movement", "culture", "represent", "identity"],
    "urgency": ["hurry", "now", "today only", "ends", "last day", "final", "closing", "before it's gone"],
    "community/culture": ["community", "culture", "belong", "crew", "family", "together", "movement"],
    "sustainability": ["sustainable", "eco", "organic", "recycled", "planet", "conscious", "ethical"],
    "comfort/fit": ["comfort", "soft", "cozy", "relaxed", "oversized", "perfect fit", "everyday"],
    "behind-the-scenes": ["behind", "making of", "process", "design", "studio", "handmade", "our story"],
}

# CTA detection patterns
CTA_PATTERNS = [
    r"shop now",
    r"buy now",
    r"get yours",
    r"order now",
    r"cop now",
    r"grab yours",
    r"link in bio",
    r"tap to shop",
    r"swipe up",
    r"check it out",
    r"discover more",
    r"explore now",
    r"don'?t miss out",
    r"sign up",
    r"join (?:the|our)",
    r"learn more",
    r"see more",
    r"visit (?:our |the )?(?:site|store|shop)",
    r"available now",
    r"claim yours",
]


async def check_ad_library(
    competitors: list[dict],
    token: str = None,
    country: str = "ALL",
    limit: int = None,
) -> list[dict]:
    """Fetch Meta Ad Library data for each competitor via the official API.

    Drop-in replacement for the old Playwright-based scraper. Returns the same
    competitor list with 'meta_ads' populated (backward-compatible structure
    plus new rich fields).
    """
    token = token or META_ACCESS_TOKEN
    limit = limit or META_DEFAULT_AD_LIMIT

    if not token:
        logger.error("META_ACCESS_TOKEN not set. Skipping ad library checks.")
        for comp in competitors:
            comp["meta_ads"] = _empty_meta_ads("No API token configured")
        return competitors

    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Validate token first
        if not await _validate_token(session, token):
            for comp in competitors:
                comp["meta_ads"] = _empty_meta_ads("Invalid or expired API token")
            return competitors

        for i, comp in enumerate(competitors):
            brand_name = comp["name"].split("(")[0].strip()
            logger.info(f"Meta Ad Library API [{i+1}/{len(competitors)}]: {brand_name}")

            ad_data = await _fetch_brand_ads(session, brand_name, token, country, limit)
            comp["meta_ads"] = ad_data

            if i < len(competitors) - 1:
                await asyncio.sleep(RATE_LIMIT_DELAY)

    return competitors


async def _validate_token(session: aiohttp.ClientSession, token: str) -> bool:
    """Quick token validation with a minimal API call."""
    try:
        resp = await _fetch_page(session, META_AD_ARCHIVE_URL, {
            "access_token": token,
            "search_terms": "test",
            "ad_reached_countries": '["US"]',
            "ad_active_status": "active",
            "limit": 1,
            "fields": "page_name",
        })
        if "error" in resp:
            logger.error(f"Token validation failed: {resp['error'].get('message', resp['error'])}")
            return False
        return True
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return False


async def _fetch_brand_ads(
    session: aiohttp.ClientSession,
    brand_name: str,
    token: str,
    country: str = "ALL",
    limit: int = 50,
) -> dict:
    """Query the ads_archive endpoint for a single brand with pagination."""
    all_ads = []
    params = {
        "access_token": token,
        "search_terms": brand_name,
        "ad_reached_countries": f'["{country}"]' if country != "ALL" else '["US","GB","NL","DE","AU","CA","FR"]',
        "ad_active_status": "active",
        "ad_type": "all",
        "limit": min(limit, 25),  # API page size
        "fields": ",".join(META_API_FIELDS),
    }

    try:
        next_url = None
        while len(all_ads) < limit:
            if next_url:
                resp = await _fetch_page(session, next_url, {})
            else:
                resp = await _fetch_page(session, META_AD_ARCHIVE_URL, params)

            if "error" in resp:
                error_msg = resp["error"].get("message", str(resp["error"]))
                logger.warning(f"  API error for {brand_name}: {error_msg}")
                if not all_ads:
                    return _empty_meta_ads(error_msg)
                break

            data = resp.get("data", [])
            if not data:
                break

            all_ads.extend(data)

            # Check for next page
            paging = resp.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break

            await asyncio.sleep(RATE_LIMIT_DELAY)

        all_ads = all_ads[:limit]
        return _parse_ad_response(all_ads, brand_name)

    except Exception as e:
        logger.error(f"  Failed to fetch ads for {brand_name}: {e}")
        return _empty_meta_ads(str(e))


async def _fetch_page(
    session: aiohttp.ClientSession,
    url: str,
    params: dict,
) -> dict:
    """Make a single API request with retry on 429."""
    max_retries = 3
    backoff = 5

    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params if params else None) as resp:
                if resp.status == 429:
                    wait = backoff * (2 ** attempt)
                    logger.warning(f"  Rate limited (429). Waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                return await resp.json()
        except asyncio.TimeoutError:
            logger.warning(f"  Request timeout (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
            continue
        except Exception as e:
            return {"error": {"message": str(e)}}

    return {"error": {"message": "Max retries exceeded"}}


def _parse_ad_response(raw_ads: list[dict], brand_name: str) -> dict:
    """Transform raw API response into the enriched meta_ads structure."""
    if not raw_ads:
        return _empty_meta_ads()

    # Parse individual ads
    parsed_ads = []
    all_texts = []
    all_platforms = set()
    spend_values = []
    impression_values = []
    lifespans = []
    regions = Counter()
    demographics = Counter()
    languages = set()

    for ad in raw_ads:
        # Creative text
        bodies = ad.get("ad_creative_bodies", [])
        body = bodies[0] if bodies else ""
        if body:
            all_texts.append(body)

        link_titles = ad.get("ad_creative_link_titles", [])
        link_descs = ad.get("ad_creative_link_descriptions", [])
        link_captions = ad.get("ad_creative_link_captions", [])

        # Platforms
        platforms = ad.get("publisher_platforms", [])
        all_platforms.update(platforms)

        # Spend
        spend = ad.get("spend", {})
        if spend and "lower_bound" in spend:
            try:
                spend_values.append(float(spend["upper_bound"]))
            except (ValueError, KeyError):
                pass

        # Impressions
        impressions = ad.get("impressions", {})
        if impressions and "lower_bound" in impressions:
            try:
                impression_values.append(int(impressions["upper_bound"]))
            except (ValueError, KeyError):
                pass

        # Lifespan
        start = ad.get("ad_delivery_start_time", "")
        stop = ad.get("ad_delivery_stop_time", "")
        if start:
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(stop.replace("Z", "+00:00")) if stop else datetime.now(start_dt.tzinfo)
                lifespan = (end_dt - start_dt).days
                if lifespan >= 0:
                    lifespans.append(lifespan)
            except (ValueError, TypeError):
                pass

        # Demographics
        for demo in ad.get("demographic_distribution", []):
            age = demo.get("age", "")
            gender = demo.get("gender", "")
            pct = demo.get("percentage", "")
            if age and gender:
                demographics[f"{age} {gender}"] += float(pct) if pct else 0

        # Regions
        for region in ad.get("delivery_by_region", []):
            name = region.get("region", "")
            pct = region.get("percentage", "")
            if name:
                regions[name] += float(pct) if pct else 0

        # Languages
        for lang in ad.get("languages", []):
            languages.add(lang)

        parsed_ads.append({
            "ad_creation_time": ad.get("ad_creation_time", ""),
            "delivery_start": start,
            "delivery_stop": stop,
            "creative_body": body,
            "creative_link_title": link_titles[0] if link_titles else "",
            "creative_link_description": link_descs[0] if link_descs else "",
            "creative_link_caption": link_captions[0] if link_captions else "",
            "snapshot_url": ad.get("ad_snapshot_url", ""),
            "page_name": ad.get("page_name", ""),
            "page_id": ad.get("page_id", ""),
            "publisher_platforms": platforms,
            "impressions": impressions if impressions else None,
            "spend": spend if spend else None,
            "currency": ad.get("currency", ""),
            "demographic_distribution": ad.get("demographic_distribution"),
            "delivery_by_region": ad.get("delivery_by_region"),
            "languages": ad.get("languages", []),
        })

    # Build summary
    themes = _extract_themes(all_texts)
    hooks = _extract_hooks(all_texts)
    ctas = _extract_ctas(all_texts)

    # Creative diversity: ratio of unique first-50-chars to total
    if all_texts:
        prefixes = set(t[:50].lower().strip() for t in all_texts)
        creative_diversity = round(len(prefixes) / len(all_texts), 2)
    else:
        creative_diversity = 0.0

    top_demographics = [k for k, _ in demographics.most_common(5)]
    top_regions = [k for k, _ in regions.most_common(5)]

    summary = {
        "total_ads": len(parsed_ads),
        "active_ads": len(parsed_ads),  # We only fetch active
        "platforms_used": sorted(all_platforms),
        "spend_range": {
            "min": round(min(spend_values), 2),
            "max": round(max(spend_values), 2),
            "currency": parsed_ads[0].get("currency", "USD") if parsed_ads else "USD",
        } if spend_values else None,
        "impressions_range": {
            "min": min(impression_values),
            "max": max(impression_values),
        } if impression_values else None,
        "avg_ad_lifespan_days": round(sum(lifespans) / len(lifespans), 1) if lifespans else None,
        "top_regions": top_regions,
        "top_demographics": top_demographics,
        "languages": sorted(languages),
        "hooks": hooks[:10],
        "ctas": ctas,
        "creative_diversity": creative_diversity,
    }

    return {
        # Backward-compatible fields
        "has_active_ads": len(parsed_ads) > 0,
        "approximate_ad_count": len(parsed_ads),
        "ad_texts_sample": all_texts[:5],
        "observed_themes": themes,
        "errors": [],
        # New rich fields
        "ads": parsed_ads,
        "summary": summary,
    }


def _empty_meta_ads(error: str = None) -> dict:
    """Return an empty meta_ads structure."""
    return {
        "has_active_ads": False,
        "approximate_ad_count": 0,
        "ad_texts_sample": [],
        "observed_themes": [],
        "errors": [error] if error else [],
        "ads": [],
        "summary": {
            "total_ads": 0,
            "active_ads": 0,
            "platforms_used": [],
            "spend_range": None,
            "impressions_range": None,
            "avg_ad_lifespan_days": None,
            "top_regions": [],
            "top_demographics": [],
            "languages": [],
            "hooks": [],
            "ctas": [],
            "creative_diversity": 0.0,
        },
    }


def _extract_themes(ad_texts: list[str]) -> list[str]:
    """Detect marketing themes from ad copy."""
    if not ad_texts:
        return []

    combined = " ".join(ad_texts).lower()
    found = []
    for theme, keywords in THEME_PATTERNS.items():
        if any(kw in combined for kw in keywords):
            found.append(theme)
    return found


def _extract_hooks(ad_texts: list[str]) -> list[str]:
    """Extract opening hooks (first sentence/phrase) from ad copy."""
    hooks = []
    seen = set()
    for text in ad_texts:
        text = text.strip()
        if not text:
            continue
        # First sentence or first line
        match = re.match(r'^(.+?[.!?])\s', text)
        if match:
            hook = match.group(1).strip()
        else:
            hook = text.split('\n')[0].strip()

        # Clean and deduplicate
        if len(hook) < 10 or len(hook) > 200:
            continue
        hook_lower = hook.lower()
        if hook_lower not in seen:
            seen.add(hook_lower)
            hooks.append(hook)

    return hooks


def _extract_ctas(ad_texts: list[str]) -> list[str]:
    """Extract calls-to-action from ad copy."""
    if not ad_texts:
        return []

    combined = " ".join(ad_texts).lower()
    found = []
    for pattern in CTA_PATTERNS:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        if matches:
            # Capitalize nicely
            cta = matches[0].strip()
            cta = cta[0].upper() + cta[1:] if cta else cta
            if cta not in found:
                found.append(cta)
    return found
