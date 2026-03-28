"""Side-by-side comparison of competitor ad strategies."""
import logging
from collections import Counter, defaultdict
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


def compare_ad_strategies(competitors: list[dict]) -> dict:
    """Build a side-by-side comparison of competitor ad strategies.

    Args:
        competitors: List with populated meta_ads keys.
    Returns:
        Dict with comparison tables, matrices, patterns, and insights.
    """
    # Filter to competitors with ad data
    with_ads = [c for c in competitors if c.get("meta_ads", {}).get("has_active_ads")]

    if not with_ads:
        return _empty_comparison()

    comparison_table = _build_comparison_table(with_ads)
    theme_matrix = _build_theme_matrix(with_ads)
    platform_matrix = _build_platform_matrix(with_ads)
    hook_patterns = _detect_hook_patterns(with_ads)
    cta_patterns = _build_cta_patterns(with_ads)
    spend_ranking = _build_spend_ranking(with_ads)

    result = {
        "comparison_table": comparison_table,
        "theme_matrix": theme_matrix,
        "platform_matrix": platform_matrix,
        "hook_patterns": hook_patterns,
        "cta_patterns": cta_patterns,
        "spend_ranking": spend_ranking,
        "total_brands_with_ads": len(with_ads),
        "total_ads_analyzed": sum(
            c.get("meta_ads", {}).get("approximate_ad_count", 0) for c in with_ads
        ),
        "insights": [],
    }

    result["insights"] = _generate_insights(result, len(competitors))

    logger.info(
        f"Ad comparison complete: {len(with_ads)} brands with ads, "
        f"{result['total_ads_analyzed']} total ads analyzed"
    )
    return result


def _build_comparison_table(brands: list[dict]) -> list[dict]:
    """Build the main comparison table rows."""
    rows = []
    for comp in brands:
        meta = comp.get("meta_ads", {})
        summary = meta.get("summary", {})
        spend = summary.get("spend_range")

        rows.append({
            "brand": comp["name"],
            "ad_count": meta.get("approximate_ad_count", 0),
            "platforms": summary.get("platforms_used", []),
            "spend_range": f"{spend['currency']} {spend['min']}-{spend['max']}" if spend else "N/A",
            "impressions_range": (
                f"{summary['impressions_range']['min']:,}-{summary['impressions_range']['max']:,}"
                if summary.get("impressions_range") else "N/A"
            ),
            "top_themes": meta.get("observed_themes", [])[:3],
            "top_hooks": summary.get("hooks", [])[:3],
            "avg_lifespan_days": summary.get("avg_ad_lifespan_days"),
            "creative_diversity": summary.get("creative_diversity", 0),
        })

    rows.sort(key=lambda r: r["ad_count"], reverse=True)
    return rows


def _build_theme_matrix(brands: list[dict]) -> dict[str, list[str]]:
    """Map each theme to the brands that use it."""
    matrix = defaultdict(list)
    for comp in brands:
        themes = comp.get("meta_ads", {}).get("observed_themes", [])
        for theme in themes:
            matrix[theme].append(comp["name"])
    # Sort by popularity
    return dict(sorted(matrix.items(), key=lambda x: len(x[1]), reverse=True))


def _build_platform_matrix(brands: list[dict]) -> dict[str, list[str]]:
    """Map each platform to the brands advertising on it."""
    matrix = defaultdict(list)
    for comp in brands:
        platforms = comp.get("meta_ads", {}).get("summary", {}).get("platforms_used", [])
        for platform in platforms:
            matrix[platform].append(comp["name"])
    return dict(sorted(matrix.items(), key=lambda x: len(x[1]), reverse=True))


def _detect_hook_patterns(brands: list[dict]) -> list[dict]:
    """Cluster similar hooks across competitors to find common patterns."""
    all_hooks = []
    for comp in brands:
        hooks = comp.get("meta_ads", {}).get("summary", {}).get("hooks", [])
        for hook in hooks:
            all_hooks.append({"text": hook, "brand": comp["name"]})

    if not all_hooks:
        return []

    # Simple clustering by string similarity
    clusters = []
    used = set()

    for i, hook_a in enumerate(all_hooks):
        if i in used:
            continue
        cluster = {
            "pattern": hook_a["text"],
            "brands": [hook_a["brand"]],
            "examples": [hook_a["text"]],
        }
        used.add(i)

        for j, hook_b in enumerate(all_hooks):
            if j in used or j == i:
                continue
            similarity = SequenceMatcher(
                None, hook_a["text"].lower(), hook_b["text"].lower()
            ).ratio()
            if similarity > 0.5:
                cluster["brands"].append(hook_b["brand"])
                cluster["examples"].append(hook_b["text"])
                used.add(j)

        # Only keep clusters with 2+ brands or interesting single hooks
        if len(set(cluster["brands"])) >= 2 or len(cluster["examples"][0]) > 30:
            cluster["brands"] = list(set(cluster["brands"]))
            clusters.append(cluster)

    clusters.sort(key=lambda c: len(c["brands"]), reverse=True)
    return clusters[:15]


def _build_cta_patterns(brands: list[dict]) -> list[dict]:
    """Aggregate CTAs across brands."""
    cta_brands = defaultdict(list)
    for comp in brands:
        ctas = comp.get("meta_ads", {}).get("summary", {}).get("ctas", [])
        for cta in ctas:
            cta_brands[cta.lower()].append(comp["name"])

    patterns = [
        {"cta": cta, "brands": list(set(brand_list)), "count": len(brand_list)}
        for cta, brand_list in cta_brands.items()
    ]
    patterns.sort(key=lambda p: p["count"], reverse=True)
    return patterns


def _build_spend_ranking(brands: list[dict]) -> list[dict]:
    """Rank brands by estimated ad spend."""
    ranking = []
    for comp in brands:
        spend = comp.get("meta_ads", {}).get("summary", {}).get("spend_range")
        if spend:
            ranking.append({
                "brand": comp["name"],
                "estimated_max_spend": spend["max"],
                "currency": spend["currency"],
                "display": f"{spend['currency']} {spend['min']}-{spend['max']}",
            })

    ranking.sort(key=lambda r: r["estimated_max_spend"], reverse=True)
    return ranking


def _generate_insights(comparison: dict, total_competitors: int) -> list[str]:
    """Auto-generate actionable insights from the comparison data."""
    insights = []
    total_with_ads = comparison["total_brands_with_ads"]

    # Ad adoption rate
    pct = round(total_with_ads / total_competitors * 100) if total_competitors else 0
    insights.append(
        f"{total_with_ads}/{total_competitors} competitors ({pct}%) are running active Meta ads."
    )

    # Platform insights
    platform_matrix = comparison.get("platform_matrix", {})
    if platform_matrix:
        top_platform = max(platform_matrix.items(), key=lambda x: len(x[1]))
        insights.append(
            f"Most popular ad platform: {top_platform[0]} ({len(top_platform[1])} brands). "
            f"Consider prioritizing this channel."
        )
        if "instagram" in platform_matrix and "facebook" in platform_matrix:
            both = set(platform_matrix.get("instagram", [])) & set(platform_matrix.get("facebook", []))
            if both:
                insights.append(
                    f"{len(both)} brands advertise on both Facebook and Instagram: {', '.join(list(both)[:5])}."
                )

    # Theme insights
    theme_matrix = comparison.get("theme_matrix", {})
    if theme_matrix:
        top_themes = list(theme_matrix.items())[:3]
        for theme, brands in top_themes:
            insights.append(
                f"Theme '{theme}' is used by {len(brands)} brands: {', '.join(brands[:4])}."
            )

    # Spend insights
    spend_ranking = comparison.get("spend_ranking", [])
    if spend_ranking:
        top_spender = spend_ranking[0]
        insights.append(
            f"Highest estimated spend: {top_spender['brand']} at {top_spender['display']}."
        )

    # Hook patterns
    hook_patterns = comparison.get("hook_patterns", [])
    if hook_patterns:
        multi_brand = [h for h in hook_patterns if len(h["brands"]) >= 2]
        if multi_brand:
            insights.append(
                f"Found {len(multi_brand)} hook patterns used by multiple brands. "
                f"These are proven approaches worth adapting."
            )

    # Creative diversity
    table = comparison.get("comparison_table", [])
    high_diversity = [r for r in table if r.get("creative_diversity", 0) > 0.7]
    low_diversity = [r for r in table if 0 < r.get("creative_diversity", 0) < 0.3]
    if high_diversity:
        insights.append(
            f"Brands with highly diverse ad creatives: {', '.join(r['brand'] for r in high_diversity[:3])}. "
            f"They test many different angles."
        )
    if low_diversity:
        insights.append(
            f"Brands running repetitive creatives: {', '.join(r['brand'] for r in low_diversity[:3])}. "
            f"They've likely found a winning formula they're scaling."
        )

    return insights


def _empty_comparison() -> dict:
    """Return empty comparison structure."""
    return {
        "comparison_table": [],
        "theme_matrix": {},
        "platform_matrix": {},
        "hook_patterns": [],
        "cta_patterns": [],
        "spend_ranking": [],
        "total_brands_with_ads": 0,
        "total_ads_analyzed": 0,
        "insights": ["No competitors with active Meta ads found."],
    }
