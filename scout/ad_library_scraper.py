"""
Meta Ad Library scraper via Playwright.

Scrapes facebook.com/ads/library for subscription brand ads.
Extracts: advertiser name, ad text, landing page URL, start date, media type.
Detects winning signals (long-running ads, multiple creatives).
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "scout" / "output"


def calculate_ad_age_days(start_date_str):
    """Calculate how many days an ad has been running."""
    try:
        # Meta Ad Library shows dates like "Started running on Mar 1, 2026"
        # We'll parse various formats
        for fmt in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                start = datetime.strptime(start_date_str.strip(), fmt)
                return (datetime.now() - start).days
            except ValueError:
                continue
        return 0
    except Exception:
        return 0


def is_excluded(text, excluded_terms):
    """Check if text contains any excluded niche terms."""
    text_lower = text.lower()
    return any(term in text_lower for term in excluded_terms)


def has_subscription_signal(text, keywords):
    """Check if text contains subscription-related keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def extract_domain(url):
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def score_opportunity(brand_data):
    """Score a brand opportunity (0-100) based on winning signals."""
    score = 0

    # Ad longevity (max 30 points)
    max_age = max((ad.get("age_days", 0) for ad in brand_data.get("ads", [])), default=0)
    if max_age >= 90:
        score += 30
    elif max_age >= 60:
        score += 25
    elif max_age >= 30:
        score += 20
    elif max_age >= 14:
        score += 10

    # Number of active ads (max 25 points)
    num_ads = len(brand_data.get("ads", []))
    if num_ads >= 10:
        score += 25
    elif num_ads >= 5:
        score += 20
    elif num_ads >= 3:
        score += 15
    elif num_ads >= 2:
        score += 10

    # Subscription signals in ad copy (max 20 points)
    sub_signals = sum(1 for ad in brand_data.get("ads", [])
                      if ad.get("has_subscription_signal", False))
    if sub_signals >= 3:
        score += 20
    elif sub_signals >= 1:
        score += 15

    # Has a clear landing page / website (max 10 points)
    if brand_data.get("website"):
        score += 10

    # Niche uniqueness bonus (max 15 points) — not a mega brand
    name = brand_data.get("name", "").lower()
    mega_brands = ["amazon", "walmart", "target", "costco", "nike", "adidas"]
    if not any(b in name for b in mega_brands):
        score += 15

    return min(score, 100)


def parse_scraped_results(raw_results):
    """
    Parse raw scraped ad data into structured brand opportunities.

    Args:
        raw_results: List of dicts with keys:
            - advertiser_name, ad_text, landing_url, start_date, media_type

    Returns:
        List of brand opportunity dicts, scored and sorted.
    """
    from scout.config import EXCLUDED_NICHES, WINNING_SIGNALS

    # Group ads by advertiser
    brands = {}
    for ad in raw_results:
        name = ad.get("advertiser_name", "Unknown")
        if name not in brands:
            brands[name] = {
                "name": name,
                "website": None,
                "ads": [],
                "niches_detected": [],
            }

        # Check exclusions
        ad_text = ad.get("ad_text", "")
        if is_excluded(ad_text, EXCLUDED_NICHES):
            continue
        if is_excluded(name, EXCLUDED_NICHES):
            continue

        age_days = calculate_ad_age_days(ad.get("start_date", ""))
        has_sub = has_subscription_signal(
            ad_text, WINNING_SIGNALS["subscription_keywords"]
        )

        landing_url = ad.get("landing_url", "")
        if landing_url and not brands[name]["website"]:
            brands[name]["website"] = extract_domain(landing_url)

        brands[name]["ads"].append({
            "text": ad_text[:500],
            "landing_url": landing_url,
            "start_date": ad.get("start_date", ""),
            "age_days": age_days,
            "media_type": ad.get("media_type", "unknown"),
            "has_subscription_signal": has_sub,
        })

    # Score and filter
    opportunities = []
    for brand_data in brands.values():
        if not brand_data["ads"]:
            continue

        brand_data["score"] = score_opportunity(brand_data)
        brand_data["num_ads"] = len(brand_data["ads"])
        brand_data["max_ad_age_days"] = max(
            (ad["age_days"] for ad in brand_data["ads"]), default=0
        )
        brand_data["has_subscription"] = any(
            ad["has_subscription_signal"] for ad in brand_data["ads"]
        )

        # Only include brands with subscription signals
        if brand_data["has_subscription"]:
            opportunities.append(brand_data)

    # Sort by score descending
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    return opportunities


def save_opportunities(opportunities, filename="opportunities.json"):
    """Save opportunities to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(opportunities)} opportunities to {output_path}")
    return output_path
