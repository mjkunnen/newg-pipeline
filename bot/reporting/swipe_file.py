"""Generate an organized swipe file of competitor ad inspiration."""
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_swipe_file(competitors: list[dict], output_dir: str) -> str:
    """Generate an organized 'swipe file' of competitor ad inspiration.

    Produces both a Markdown file (human-readable) and a JSON companion
    (programmatic use / dashboard).

    Returns:
        Path to the generated markdown file.
    """
    with_ads = [c for c in competitors if c.get("meta_ads", {}).get("has_active_ads")]

    if not with_ads:
        logger.info("No competitor ads found. Swipe file will be empty.")
        md_path = os.path.join(output_dir, "ad_swipe_file.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Ad Swipe File\n\nNo competitor ads found.\n")
        return md_path

    # Collect all material
    hooks_by_theme = _collect_hooks_by_theme(with_ads)
    ads_by_theme = _categorize_by_theme(with_ads)
    ctas = _collect_ctas(with_ads)
    snapshots = _collect_snapshots(with_ads)
    frameworks = _extract_copy_frameworks(with_ads)

    # Write Markdown
    md_path = os.path.join(output_dir, "ad_swipe_file.md")
    _write_markdown(md_path, with_ads, hooks_by_theme, ads_by_theme, ctas, snapshots, frameworks)

    # Write JSON companion
    json_path = os.path.join(output_dir, "ad_swipe_file.json")
    json_data = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_brands": len(with_ads),
        "total_ads": sum(c["meta_ads"]["approximate_ad_count"] for c in with_ads),
        "hooks_by_theme": hooks_by_theme,
        "ads_by_theme": {
            theme: [{"body": a["body"][:500], "brand": a["brand"]} for a in ads]
            for theme, ads in ads_by_theme.items()
        },
        "ctas": ctas,
        "snapshots": snapshots,
        "frameworks": frameworks,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Swipe file saved: {md_path} + {json_path}")
    return md_path


def _collect_hooks_by_theme(brands: list[dict]) -> dict[str, list[dict]]:
    """Collect opening hooks organized by detected theme."""
    from bot.research.ad_library import THEME_PATTERNS

    hooks_by_theme = defaultdict(list)

    for comp in brands:
        hooks = comp.get("meta_ads", {}).get("summary", {}).get("hooks", [])
        for hook in hooks:
            hook_lower = hook.lower()
            matched_theme = "general"
            for theme, keywords in THEME_PATTERNS.items():
                if any(kw in hook_lower for kw in keywords):
                    matched_theme = theme
                    break
            hooks_by_theme[matched_theme].append({
                "hook": hook,
                "brand": comp["name"],
            })

    return dict(hooks_by_theme)


def _categorize_by_theme(brands: list[dict]) -> dict[str, list[dict]]:
    """Sort full ad copy into theme buckets."""
    from bot.research.ad_library import THEME_PATTERNS

    by_theme = defaultdict(list)

    for comp in brands:
        ads = comp.get("meta_ads", {}).get("ads", [])
        for ad in ads:
            body = ad.get("creative_body", "")
            if not body or len(body) < 20:
                continue

            body_lower = body.lower()
            matched_theme = "general"
            for theme, keywords in THEME_PATTERNS.items():
                if any(kw in body_lower for kw in keywords):
                    matched_theme = theme
                    break

            by_theme[matched_theme].append({
                "body": body,
                "brand": comp["name"],
                "platforms": ad.get("publisher_platforms", []),
                "snapshot_url": ad.get("snapshot_url", ""),
            })

    return dict(by_theme)


def _collect_ctas(brands: list[dict]) -> list[dict]:
    """Collect CTAs with frequency and brand attribution."""
    cta_data = defaultdict(lambda: {"count": 0, "brands": set()})

    for comp in brands:
        ctas = comp.get("meta_ads", {}).get("summary", {}).get("ctas", [])
        for cta in ctas:
            key = cta.lower()
            cta_data[key]["count"] += 1
            cta_data[key]["brands"].add(comp["name"])
            cta_data[key]["display"] = cta

    result = [
        {"cta": v["display"], "count": v["count"], "brands": sorted(v["brands"])}
        for v in sorted(cta_data.values(), key=lambda x: x["count"], reverse=True)
    ]
    return result


def _collect_snapshots(brands: list[dict]) -> dict[str, list[str]]:
    """Collect ad snapshot URLs organized by brand."""
    snapshots = {}
    for comp in brands:
        urls = []
        for ad in comp.get("meta_ads", {}).get("ads", []):
            url = ad.get("snapshot_url", "")
            if url:
                urls.append(url)
        if urls:
            snapshots[comp["name"]] = urls
    return snapshots


def _extract_copy_frameworks(brands: list[dict]) -> list[dict]:
    """Detect common copywriting structures in ad texts."""
    frameworks = []
    all_texts = []

    for comp in brands:
        for ad in comp.get("meta_ads", {}).get("ads", []):
            body = ad.get("creative_body", "")
            if body and len(body) > 50:
                all_texts.append({"text": body, "brand": comp["name"]})

    if not all_texts:
        return frameworks

    # Detect common structures
    question_opener = [t for t in all_texts if t["text"].strip().startswith(("?", "Who", "What", "Why", "How", "When", "Where", "Do you", "Are you", "Have you", "Want", "Looking", "Tired"))]
    if question_opener:
        frameworks.append({
            "name": "Question Hook",
            "description": "Opens with a question to engage the reader and create curiosity",
            "count": len(question_opener),
            "examples": [t["text"][:150] for t in question_opener[:3]],
            "brands": list(set(t["brand"] for t in question_opener)),
        })

    emoji_heavy = [t for t in all_texts if len(re.findall(r'[\U0001F300-\U0001F9FF]', t["text"])) >= 3]
    if emoji_heavy:
        frameworks.append({
            "name": "Emoji-Rich Copy",
            "description": "Uses multiple emojis to break up text and add visual interest",
            "count": len(emoji_heavy),
            "examples": [t["text"][:150] for t in emoji_heavy[:3]],
            "brands": list(set(t["brand"] for t in emoji_heavy)),
        })

    short_punchy = [t for t in all_texts if len(t["text"]) < 100 and any(c in t["text"] for c in "!.")]
    if short_punchy:
        frameworks.append({
            "name": "Short & Punchy",
            "description": "Brief, impactful copy under 100 characters with strong punctuation",
            "count": len(short_punchy),
            "examples": [t["text"][:150] for t in short_punchy[:3]],
            "brands": list(set(t["brand"] for t in short_punchy)),
        })

    list_format = [t for t in all_texts if t["text"].count("\n") >= 3 or t["text"].count("•") >= 2 or t["text"].count("✓") >= 2 or t["text"].count("-") >= 3]
    if list_format:
        frameworks.append({
            "name": "List/Bullet Format",
            "description": "Uses bullet points or line breaks to highlight features/benefits",
            "count": len(list_format),
            "examples": [t["text"][:200] for t in list_format[:3]],
            "brands": list(set(t["brand"] for t in list_format)),
        })

    storytelling = [t for t in all_texts if len(t["text"]) > 300]
    if storytelling:
        frameworks.append({
            "name": "Long-Form Storytelling",
            "description": "Extended copy that tells a story or builds a narrative (300+ chars)",
            "count": len(storytelling),
            "examples": [t["text"][:200] + "..." for t in storytelling[:3]],
            "brands": list(set(t["brand"] for t in storytelling)),
        })

    frameworks.sort(key=lambda f: f["count"], reverse=True)
    return frameworks


def _write_markdown(
    path: str,
    brands: list[dict],
    hooks_by_theme: dict,
    ads_by_theme: dict,
    ctas: list[dict],
    snapshots: dict,
    frameworks: list[dict],
):
    """Write the swipe file markdown."""
    L = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_ads = sum(c["meta_ads"]["approximate_ad_count"] for c in brands)

    L.append("# NEWGARMENTS Ad Swipe File")
    L.append(f"Generated: {now}")
    L.append(f"\n**{len(brands)} brands** with active ads | **{total_ads} ads** analyzed\n")

    L.append("---\n")

    # 1. Hooks by theme
    L.append("## 1. Opening Hooks\n")
    L.append("The first line of an ad determines whether someone stops scrolling. "
             "These are the hooks your competitors use, organized by theme.\n")

    for theme, hook_list in hooks_by_theme.items():
        L.append(f"### {theme.replace('/', ' / ').title()}")
        for item in hook_list[:8]:
            L.append(f"- \"{item['hook']}\" — *{item['brand']}*")
        L.append("")

    # 2. Full ad copy by theme
    L.append("---\n")
    L.append("## 2. Full Ad Copy Examples\n")

    for theme, ad_list in ads_by_theme.items():
        L.append(f"### {theme.replace('/', ' / ').title()} ({len(ad_list)} ads)")
        for ad in ad_list[:5]:
            body_preview = ad["body"][:300].replace("\n", " ").strip()
            platforms = ", ".join(ad["platforms"]) if ad["platforms"] else "unknown"
            L.append(f"\n**{ad['brand']}** ({platforms}):")
            L.append(f"> {body_preview}")
            L.append("")
        L.append("")

    # 3. CTAs
    L.append("---\n")
    L.append("## 3. Calls to Action\n")
    L.append("| CTA | Used by | Brands |")
    L.append("|-----|---------|--------|")
    for cta in ctas[:15]:
        brand_str = ", ".join(cta["brands"][:4])
        if len(cta["brands"]) > 4:
            brand_str += f" +{len(cta['brands']) - 4} more"
        L.append(f"| {cta['cta']} | {cta['count']} brands | {brand_str} |")
    L.append("")

    # 4. Copy frameworks
    L.append("---\n")
    L.append("## 4. Copy Frameworks Detected\n")
    for fw in frameworks:
        L.append(f"### {fw['name']} ({fw['count']} ads)")
        L.append(f"*{fw['description']}*\n")
        L.append(f"Used by: {', '.join(fw['brands'][:5])}\n")
        L.append("Examples:")
        for ex in fw["examples"]:
            L.append(f"> {ex.replace(chr(10), ' ')}")
            L.append("")
        L.append("")

    # 5. Creative snapshot URLs
    L.append("---\n")
    L.append("## 5. Ad Creative Snapshots (Visual Review)\n")
    L.append("Click these links to view the actual ad creatives on Facebook.\n")
    for brand_name, urls in snapshots.items():
        L.append(f"### {brand_name} ({len(urls)} creatives)")
        for i, url in enumerate(urls[:10], 1):
            L.append(f"{i}. [{brand_name} Ad #{i}]({url})")
        if len(urls) > 10:
            L.append(f"*...and {len(urls) - 10} more*")
        L.append("")

    # 6. NEWGARMENTS adaptation notes
    L.append("---\n")
    L.append("## 6. NEWGARMENTS Adaptation Notes\n")
    L.append("Key takeaways for adapting these patterns to the NEWGARMENTS brand voice:\n")

    if "scarcity/exclusivity" in hooks_by_theme:
        L.append("### Scarcity Hooks")
        L.append("- Multiple competitors use scarcity language effectively. NEWGARMENTS should lean into "
                 "the 'no restock' promise with hooks like \"Once it's gone, it's gone\" or \"This drop won't return.\"")
        L.append("")

    if "quality focus" in hooks_by_theme:
        L.append("### Quality Hooks")
        L.append("- Quality messaging resonates in this niche. Lead with specific details: "
                 "\"500GSM heavyweight French terry\" is stronger than generic \"premium quality.\"")
        L.append("")

    if "lifestyle/identity" in hooks_by_theme or "community/culture" in hooks_by_theme:
        L.append("### Identity/Culture Hooks")
        L.append("- The strongest performing competitors tie their brand to an identity. "
                 "\"Wear the identity\" is a good start — amplify it by showing what that identity looks like.")
        L.append("")

    if frameworks:
        top_fw = frameworks[0]
        L.append(f"### Most Common Framework: {top_fw['name']}")
        L.append(f"- {top_fw['count']} ads use this approach. Consider testing this format "
                 f"for NEWGARMENTS ads alongside your current creative strategy.")
        L.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
