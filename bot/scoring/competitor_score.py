"""Score competitors by relevance to NEWGARMENTS audience and brand."""
import logging

from bot.config import SCORING_WEIGHTS

logger = logging.getLogger(__name__)

# Keywords that signal high relevance to NEWGARMENTS audience
AUDIENCE_KEYWORDS = [
    "gen z", "streetwear", "hoodie", "limited", "drop", "archive",
    "exclusive", "premium", "heavyweight", "underground", "urban",
    "youth", "young", "street", "culture", "capsule",
]

AESTHETIC_KEYWORDS = [
    "archive", "vintage", "oversized", "boxy", "heavyweight",
    "minimal", "clean", "dark", "muted", "earth tone",
    "techwear", "gorpcore", "y2k", "grunge",
]

MESSAGING_KEYWORDS = [
    "limited", "no restock", "exclusive", "one-time", "sold out",
    "quality", "premium", "built", "heavy", "real", "authentic",
    "trust", "transparent", "community", "culture", "original",
]


def score_competitors(competitors: list[dict], audience: dict, brand: dict) -> list[dict]:
    """Score each competitor on relevance to NEWGARMENTS."""
    for comp in competitors:
        scores = {}

        # 1. Audience overlap (based on keywords in site content)
        scores["audience_overlap"] = _score_keyword_match(comp, AUDIENCE_KEYWORDS)

        # 2. Aesthetic similarity
        scores["aesthetic_similarity"] = _score_keyword_match(comp, AESTHETIC_KEYWORDS)

        # 3. Messaging similarity
        scores["messaging_similarity"] = _score_messaging(comp)

        # 4. Offer similarity
        scores["offer_similarity"] = _score_offer(comp)

        # 5. Platform presence
        scores["platform_presence"] = _score_platform_presence(comp)

        # 6. Ad activity
        scores["ad_activity"] = _score_ad_activity(comp)

        # 7. Website quality
        scores["website_quality"] = _score_website_quality(comp)

        # 8. Confidence level
        scores["confidence_level"] = _score_confidence(comp)

        # Calculate weighted total
        total = sum(
            scores[key] * SCORING_WEIGHTS[key]
            for key in SCORING_WEIGHTS
        )

        comp["scores"] = scores
        comp["relevance_score"] = round(total, 2)

        logger.debug(f"{comp['name']}: {total:.2f} ({scores})")

    # Sort by score descending
    competitors.sort(key=lambda c: c.get("relevance_score", 0), reverse=True)

    logger.info(f"Scored {len(competitors)} competitors. Top: {competitors[0]['name'] if competitors else 'N/A'} ({competitors[0].get('relevance_score', 0) if competitors else 0})")
    return competitors


def _score_keyword_match(comp: dict, keywords: list[str]) -> float:
    """Score 0-10 based on keyword matches in all text fields."""
    text = _get_all_text(comp).lower()
    if not text:
        return 2.0  # Baseline for seeds with no website data

    matches = sum(1 for kw in keywords if kw.lower() in text)
    ratio = matches / len(keywords)
    return min(10.0, round(ratio * 15, 1))  # Scale up slightly, cap at 10


def _score_messaging(comp: dict) -> float:
    """Score messaging alignment with NEWGARMENTS positioning."""
    wa = comp.get("website_analysis", {})
    text = _get_all_text(comp).lower()

    score = 2.0  # baseline

    # Check for key messaging signals
    scarcity = wa.get("scarcity_signals", [])
    if scarcity:
        score += min(3.0, len(scarcity) * 0.75)

    # Check messaging keywords in hero/description
    hero = wa.get("hero_messaging", "").lower()
    desc = wa.get("description", "").lower()
    combined = hero + " " + desc

    for kw in MESSAGING_KEYWORDS:
        if kw in combined:
            score += 0.4

    return min(10.0, round(score, 1))


def _score_offer(comp: dict) -> float:
    """Score offer structure similarity."""
    wa = comp.get("website_analysis", {})
    score = 2.0

    offer_signals = wa.get("offer_signals", [])
    scarcity_signals = wa.get("scarcity_signals", [])

    if offer_signals:
        score += min(3.0, len(offer_signals) * 1.0)
    if scarcity_signals:
        score += min(3.0, len(scarcity_signals) * 0.5)

    # Price range check (mid-tier is closest to NEWGARMENTS)
    price_range = wa.get("price_range", "")
    if price_range:
        try:
            parts = price_range.replace("$", "").split("-")
            low = float(parts[0].strip())
            high = float(parts[1].strip())
            mid = (low + high) / 2
            # Ideal range: $40-$120
            if 30 <= mid <= 150:
                score += 2.0
            elif 15 <= mid <= 200:
                score += 1.0
        except (ValueError, IndexError):
            pass

    return min(10.0, round(score, 1))


def _score_platform_presence(comp: dict) -> float:
    """Score based on social media presence."""
    score = 0.0

    if comp.get("website"):
        score += 3.0
    if comp.get("instagram"):
        score += 3.0
    if comp.get("tiktok"):
        score += 3.0

    # Bonus for document-mentioned brands (proven relevance)
    if comp.get("source") == "document_mention":
        score += 1.0

    return min(10.0, round(score, 1))


def _score_ad_activity(comp: dict) -> float:
    """Score based on Meta Ad Library activity (enhanced with API data)."""
    meta = comp.get("meta_ads", {})
    if not meta:
        return 2.0

    score = 2.0
    if meta.get("has_active_ads"):
        score += 3.0

        ad_count = meta.get("approximate_ad_count", 0)
        if ad_count > 20:
            score += 1.5
        elif ad_count > 5:
            score += 0.75

        # Platform diversity bonus
        summary = meta.get("summary", {})
        platforms = summary.get("platforms_used", [])
        if len(platforms) >= 3:
            score += 1.0
        elif len(platforms) >= 2:
            score += 0.5

        # Spend signal
        spend = summary.get("spend_range")
        if spend and spend.get("max", 0) > 1000:
            score += 1.0
        elif spend and spend.get("max", 0) > 100:
            score += 0.5

        # Theme bonuses
        themes = meta.get("observed_themes", [])
        if "scarcity/exclusivity" in themes:
            score += 0.5
        if "quality focus" in themes:
            score += 0.5

    return min(10.0, round(score, 1))


def _score_website_quality(comp: dict) -> float:
    """Score website quality signals."""
    wa = comp.get("website_analysis", {})
    if not wa or not wa.get("accessible"):
        return 1.0

    score = 3.0  # Base for accessible site

    if wa.get("has_reviews"):
        score += 1.5
    if wa.get("has_size_guide"):
        score += 1.5
    if wa.get("has_about_page"):
        score += 1.0
    if wa.get("email_capture"):
        score += 0.5
    if wa.get("trust_signals"):
        score += min(2.0, len(wa["trust_signals"]) * 0.5)
    if wa.get("product_categories"):
        score += 0.5

    return min(10.0, round(score, 1))


def _score_confidence(comp: dict) -> float:
    """Meta-score: how confident are we in this competitor's relevance?"""
    score = 2.0

    # Document mentions = high confidence
    if comp.get("source") == "document_mention":
        score += 5.0

    # Has website analysis data
    wa = comp.get("website_analysis", {})
    if wa.get("accessible"):
        score += 1.5

    # Has social profiles
    if comp.get("instagram"):
        score += 0.5
    if comp.get("tiktok"):
        score += 0.5

    # Has ad data
    if comp.get("meta_ads", {}).get("has_active_ads"):
        score += 1.0

    return min(10.0, round(score, 1))


def _get_all_text(comp: dict) -> str:
    """Combine all text fields for keyword matching."""
    parts = [
        comp.get("title", ""),
        comp.get("snippet", ""),
        comp.get("name", ""),
    ]
    wa = comp.get("website_analysis", {})
    if wa:
        parts.extend([
            wa.get("title", ""),
            wa.get("description", ""),
            wa.get("hero_messaging", ""),
            " ".join(wa.get("navigation_items", [])),
            " ".join(wa.get("trust_signals", [])),
            " ".join(wa.get("scarcity_signals", [])),
        ])
    return " ".join(parts)
