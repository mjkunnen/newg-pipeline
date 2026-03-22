"""Export research results to CSV, JSON, and Markdown."""
import csv
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def export_competitor_list_csv(competitors: list[dict], output_path: str):
    """Export competitor list to CSV."""
    fieldnames = [
        "rank", "name", "relevance_score", "website", "instagram", "tiktok",
        "source", "price_range", "has_active_ads", "ad_count", "ad_platforms",
        "ad_spend_range", "ad_themes", "accessible",
        "scarcity_signals", "trust_signals",
        "score_audience_overlap", "score_aesthetic_similarity",
        "score_messaging_similarity", "score_offer_similarity",
        "score_platform_presence", "score_ad_activity",
        "score_website_quality", "score_confidence_level",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, comp in enumerate(competitors):
            scores = comp.get("scores", {})
            wa = comp.get("website_analysis", {})
            meta = comp.get("meta_ads", {})

            summary = meta.get("summary", {})
            spend = summary.get("spend_range")
            writer.writerow({
                "rank": i + 1,
                "name": comp.get("name", ""),
                "relevance_score": comp.get("relevance_score", 0),
                "website": comp.get("website", ""),
                "instagram": comp.get("instagram", ""),
                "tiktok": comp.get("tiktok", ""),
                "source": comp.get("source", ""),
                "price_range": wa.get("price_range", ""),
                "has_active_ads": meta.get("has_active_ads", False),
                "ad_count": meta.get("approximate_ad_count", 0),
                "ad_platforms": "; ".join(summary.get("platforms_used", [])),
                "ad_spend_range": f"{spend['currency']} {spend['min']}-{spend['max']}" if spend else "",
                "ad_themes": "; ".join(meta.get("observed_themes", [])),
                "accessible": wa.get("accessible", False),
                "scarcity_signals": "; ".join(wa.get("scarcity_signals", [])),
                "trust_signals": "; ".join(wa.get("trust_signals", [])),
                "score_audience_overlap": scores.get("audience_overlap", 0),
                "score_aesthetic_similarity": scores.get("aesthetic_similarity", 0),
                "score_messaging_similarity": scores.get("messaging_similarity", 0),
                "score_offer_similarity": scores.get("offer_similarity", 0),
                "score_platform_presence": scores.get("platform_presence", 0),
                "score_ad_activity": scores.get("ad_activity", 0),
                "score_website_quality": scores.get("website_quality", 0),
                "score_confidence_level": scores.get("confidence_level", 0),
            })

    logger.info(f"Competitor list CSV saved to {output_path}")


def export_competitor_analysis_json(competitors: list[dict], output_path: str):
    """Export full competitor analysis to JSON."""
    # Clean up for JSON serialization
    clean = []
    for comp in competitors:
        entry = {
            "rank": competitors.index(comp) + 1,
            "name": comp.get("name", ""),
            "relevance_score": comp.get("relevance_score", 0),
            "website": comp.get("website", ""),
            "instagram": comp.get("instagram", ""),
            "tiktok": comp.get("tiktok", ""),
            "source": comp.get("source", ""),
            "scores": comp.get("scores", {}),
            "website_analysis": comp.get("website_analysis", {}),
            "meta_ads": comp.get("meta_ads", {}),
        }
        clean.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Competitor analysis JSON saved to {output_path}")


def export_research_report_md(competitors: list[dict], audience: dict, brand: dict, niche_map: dict, output_path: str, ad_comparison: dict = None):
    """Export a human-readable research report in Markdown."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# NEWGARMENTS Competitor Research Report")
    lines.append(f"Generated: {now}\n")

    # Summary
    lines.append("## Executive Summary\n")
    lines.append(f"- **Total competitors analyzed:** {len(competitors)}")
    seed_count = sum(1 for c in competitors if c.get("source") == "document_mention")
    lines.append(f"- **From documents:** {seed_count}")
    lines.append(f"- **Discovered via search:** {len(competitors) - seed_count}")
    active_ads = sum(1 for c in competitors if c.get("meta_ads", {}).get("has_active_ads"))
    lines.append(f"- **With active Meta ads:** {active_ads}")
    lines.append("")

    # Top competitors
    lines.append("## Top Competitors by Relevance Score\n")
    lines.append("| Rank | Brand | Score | Website | IG | TikTok | Ads | Price Range |")
    lines.append("|------|-------|-------|---------|-----|--------|-----|-------------|")

    for i, comp in enumerate(competitors[:20]):
        wa = comp.get("website_analysis", {})
        meta = comp.get("meta_ads", {})
        ads = "Yes" if meta.get("has_active_ads") else "No"
        lines.append(
            f"| {i+1} | {comp['name']} | {comp.get('relevance_score', 0)} | "
            f"[link]({comp.get('website', '')}) | "
            f"{comp.get('instagram', '-')} | {comp.get('tiktok', '-')} | "
            f"{ads} | {wa.get('price_range', '-')} |"
        )
    lines.append("")

    # Detailed analysis for top 10
    lines.append("## Detailed Analysis (Top 10)\n")
    for i, comp in enumerate(competitors[:10]):
        wa = comp.get("website_analysis", {})
        meta = comp.get("meta_ads", {})
        scores = comp.get("scores", {})

        lines.append(f"### {i+1}. {comp['name']}")
        lines.append(f"- **Website:** {comp.get('website', 'N/A')}")
        lines.append(f"- **Instagram:** @{comp.get('instagram', 'N/A')}")
        lines.append(f"- **TikTok:** @{comp.get('tiktok', 'N/A')}")
        lines.append(f"- **Relevance Score:** {comp.get('relevance_score', 0)}/10")
        lines.append(f"- **Source:** {comp.get('source', 'N/A')}")
        lines.append(f"- **Price Range:** {wa.get('price_range', 'N/A')}")
        lines.append("")

        if wa.get("hero_messaging"):
            lines.append(f"**Hero Messaging:** \"{wa['hero_messaging'][:200]}\"")
            lines.append("")

        if wa.get("scarcity_signals"):
            lines.append(f"**Scarcity Signals:** {', '.join(wa['scarcity_signals'])}")
        if wa.get("trust_signals"):
            lines.append(f"**Trust Signals:** {', '.join(wa['trust_signals'])}")
        if wa.get("offer_signals"):
            lines.append(f"**Offer Signals:** {', '.join(wa['offer_signals'])}")
        if wa.get("product_categories"):
            lines.append(f"**Product Categories:** {', '.join(wa['product_categories'])}")
        lines.append("")

        if meta.get("has_active_ads"):
            summary = meta.get("summary", {})
            lines.append(f"**Meta Ads:** Active (~{meta.get('approximate_ad_count', '?')} ads)")
            if summary.get("platforms_used"):
                lines.append(f"**Ad Platforms:** {', '.join(summary['platforms_used'])}")
            spend = summary.get("spend_range")
            if spend:
                lines.append(f"**Estimated Spend Range:** {spend['currency']} {spend['min']}-{spend['max']}")
            if meta.get("observed_themes"):
                lines.append(f"**Ad Themes:** {', '.join(meta['observed_themes'])}")
            if summary.get("hooks"):
                lines.append(f"**Top Hooks:** {' | '.join(summary['hooks'][:3])}")
            if summary.get("ctas"):
                lines.append(f"**CTAs Used:** {', '.join(summary['ctas'][:3])}")
            snapshot_count = len([a for a in meta.get("ads", []) if a.get("snapshot_url")])
            if snapshot_count:
                lines.append(f"**Creative Snapshots:** {snapshot_count} available")
        else:
            lines.append("**Meta Ads:** No active ads found")
        lines.append("")

        lines.append("**Score Breakdown:**")
        for key, val in scores.items():
            lines.append(f"  - {key.replace('_', ' ').title()}: {val}/10")
        lines.append("")
        lines.append("---\n")

    # Ad strategy comparison
    if ad_comparison and ad_comparison.get("total_brands_with_ads", 0) > 0:
        lines.append("## Ad Strategy Comparison\n")
        lines.append(f"**{ad_comparison['total_brands_with_ads']} brands** running Meta ads | "
                      f"**{ad_comparison['total_ads_analyzed']} ads** analyzed\n")

        table = ad_comparison.get("comparison_table", [])
        if table:
            lines.append("| Brand | Ads | Platforms | Spend | Top Themes | Diversity |")
            lines.append("|-------|-----|-----------|-------|------------|-----------|")
            for row in table[:15]:
                themes_str = ", ".join(row["top_themes"][:2]) if row["top_themes"] else "-"
                platforms_str = ", ".join(row["platforms"][:3]) if row["platforms"] else "-"
                lines.append(
                    f"| {row['brand']} | {row['ad_count']} | {platforms_str} | "
                    f"{row['spend_range']} | {themes_str} | {row['creative_diversity']:.0%} |"
                )
            lines.append("")

        insights = ad_comparison.get("insights", [])
        if insights:
            lines.append("### Insights\n")
            for insight in insights:
                lines.append(f"- {insight}")
            lines.append("")

    # Market observations
    lines.append("## Key Observations\n")

    # Count common signals
    scarcity_brands = [c["name"] for c in competitors if c.get("website_analysis", {}).get("scarcity_signals")]
    review_brands = [c["name"] for c in competitors if c.get("website_analysis", {}).get("has_reviews")]
    size_guide_brands = [c["name"] for c in competitors if c.get("website_analysis", {}).get("has_size_guide")]

    lines.append(f"- **{len(scarcity_brands)}/{len(competitors)}** competitors use scarcity messaging")
    lines.append(f"- **{len(review_brands)}/{len(competitors)}** have visible reviews on site")
    lines.append(f"- **{len(size_guide_brands)}/{len(competitors)}** have size guides")
    lines.append(f"- **{active_ads}/{len(competitors)}** are running Meta ads")
    lines.append("")

    lines.append("## Data Notes\n")
    lines.append("- All scores are based on observable signals, not fabricated metrics")
    lines.append("- Social follower counts are NOT included (would require authenticated API access)")
    lines.append("- Ad performance data is NOT available (Meta doesn't expose this)")
    lines.append("- Scores are relative comparisons, not absolute quality judgments")
    lines.append("- Instagram/TikTok handles may be approximate if not found on brand website")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Research report saved to {output_path}")
