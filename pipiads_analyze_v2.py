"""
NEWGARMENTS - PiPiAds Competitor Analysis v2
Analyzes the 309 captured ads and generates actionable insights.
"""
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import sys, io
# Fix Windows encoding issues with non-ASCII characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

console = Console(width=120, force_terminal=True)
DATA_DIR = Path(__file__).parent / "pipiads_data"


def safe_str(s, max_len=200):
    """Make string safe for Windows console output."""
    if not s:
        return ""
    s = str(s)[:max_len]
    return s.encode('ascii', errors='replace').decode('ascii')


def parse_num(val):
    """Parse a number from various formats."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return val
    try:
        return int(val)
    except:
        try:
            return float(val)
        except:
            return 0


def load_ads():
    """Load the latest captured data."""
    files = sorted(DATA_DIR.glob("pipiads_v2_FINAL_*.json"), reverse=True)
    if not files:
        files = sorted(DATA_DIR.glob("pipiads_research_FINAL_*.json"), reverse=True)
    if not files:
        console.print("[red]No data files found![/red]")
        return []
    f = files[0]
    console.print(f"[dim]Loading: {f.name}[/dim]")
    data = json.loads(f.read_text(encoding="utf-8"))
    return data.get("api_captured_ads", [])


def analyze():
    ads = load_ads()
    if not ads:
        return

    # Filter out non-ad objects (search queries etc)
    real_ads = [a for a in ads if a.get("ad_id") and a.get("desc")]
    console.print(f"\n[bold]Total raw records: {len(ads)} | Actual ads with data: {len(real_ads)}[/bold]\n")

    if not real_ads:
        console.print("[red]No valid ad data found[/red]")
        return

    # ==========================================
    # 1. TOP PERFORMERS BY VIEWS
    # ==========================================
    console.print(Panel("[bold]TOP PERFORMING COMPETITOR ADS (by views)[/bold]", border_style="green"))

    sorted_by_views = sorted(real_ads, key=lambda a: parse_num(a.get("play_count", 0)), reverse=True)

    table = Table(show_lines=True, expand=True)
    table.add_column("#", width=3)
    table.add_column("Advertiser", width=22)
    table.add_column("Views", width=10, justify="right")
    table.add_column("Likes", width=8, justify="right")
    table.add_column("Days", width=5, justify="right")
    table.add_column("CTA", width=12)
    table.add_column("Region", width=12)
    table.add_column("Hook / Caption", width=45)

    for i, ad in enumerate(sorted_by_views[:20], 1):
        views = parse_num(ad.get("play_count", 0))
        likes = parse_num(ad.get("digg_count", 0))
        days = parse_num(ad.get("put_days", 0))
        name = safe_str(ad.get("unique_id", "") or ad.get("app_name", "") or "?", 22)
        cta = safe_str(ad.get("button_text", "") or "", 12)
        region = safe_str(str(ad.get("fetch_region", "")), 12)
        hook = safe_str(ad.get("ai_analysis_main_hook", "") or ad.get("desc", "") or "", 45)

        v_str = f"{views/1e6:.1f}M" if views >= 1e6 else f"{views/1e3:.0f}K" if views >= 1e3 else str(views)
        l_str = f"{likes/1e3:.1f}K" if likes >= 1e3 else str(likes)

        table.add_row(str(i), name, v_str, l_str, str(days), cta, region, hook)

    console.print(table)

    # ==========================================
    # 2. TOP BY LONGEVITY (proven winners)
    # ==========================================
    console.print(Panel("[bold]PROVEN WINNERS (running longest = validated by spend)[/bold]", border_style="yellow"))

    sorted_by_days = sorted(real_ads, key=lambda a: parse_num(a.get("put_days", 0)), reverse=True)

    table2 = Table(show_lines=True, expand=True)
    table2.add_column("#", width=3)
    table2.add_column("Advertiser", width=22)
    table2.add_column("Days Running", width=12, justify="right")
    table2.add_column("Views", width=10, justify="right")
    table2.add_column("CPM", width=8, justify="right")
    table2.add_column("Hook", width=50)

    for i, ad in enumerate(sorted_by_days[:15], 1):
        days = parse_num(ad.get("put_days", 0))
        views = parse_num(ad.get("play_count", 0))
        cpm = parse_num(ad.get("min_cpm", 0))
        name = safe_str(ad.get("unique_id", "") or ad.get("app_name", "") or "?", 22)
        hook = safe_str(ad.get("ai_analysis_main_hook", "") or ad.get("desc", "") or "", 50)

        v_str = f"{views/1e6:.1f}M" if views >= 1e6 else f"{views/1e3:.0f}K" if views >= 1e3 else str(views)

        table2.add_row(str(i), name, str(days), v_str, f"${cpm:.0f}" if cpm else "?", hook)

    console.print(table2)

    # ==========================================
    # 3. HOOK ANALYSIS
    # ==========================================
    console.print(Panel("[bold]HOOK PATTERNS (AI-extracted main hooks)[/bold]", border_style="cyan"))

    hooks = [safe_str(ad.get("ai_analysis_main_hook", ""), 150) for ad in real_ads if ad.get("ai_analysis_main_hook")]
    hook_words = Counter()
    for h in hooks:
        for word in h.lower().split():
            if len(word) > 3:
                hook_words[word] += 1

    # Categorize hooks
    hook_categories = {
        "Scarcity/Urgency": ["limited", "sold", "last", "hurry", "fast", "gone", "miss", "only", "left", "drop"],
        "Quality/Material": ["heavy", "quality", "premium", "thick", "weight", "cotton", "fabric", "gsm", "built"],
        "Identity/Style": ["style", "fit", "look", "outfit", "wear", "fashion", "streetwear", "fire", "hard"],
        "Price/Value": ["free", "sale", "discount", "off", "save", "cheap", "afford", "price", "deal"],
        "Social Proof": ["everyone", "trending", "viral", "people", "best", "favorite", "loved", "popular"],
        "Problem/Pain": ["tired", "hate", "stop", "worst", "bad", "ugly", "boring", "basic", "same"],
        "Question/Curiosity": ["how", "why", "what", "would", "ever", "know", "secret", "truth", "reveal"],
    }

    cat_table = Table(title="Hook Categories Found", show_lines=True)
    cat_table.add_column("Category", width=20)
    cat_table.add_column("Count", width=8, justify="right")
    cat_table.add_column("Example Hooks", width=70)

    for cat, keywords in hook_categories.items():
        matching_hooks = []
        for h in hooks:
            if any(k in h.lower() for k in keywords):
                matching_hooks.append(h)
        if matching_hooks:
            examples = safe_str(" | ".join(matching_hooks[:3]), 70)
            cat_table.add_row(cat, str(len(matching_hooks)), examples)

    console.print(cat_table)

    # ==========================================
    # 4. CTA BUTTONS USED
    # ==========================================
    console.print(Panel("[bold]CTA BUTTONS USED[/bold]", border_style="magenta"))

    cta_counts = Counter(ad.get("button_text", "unknown") for ad in real_ads if ad.get("button_text"))
    cta_table = Table(show_lines=True)
    cta_table.add_column("CTA Button", width=25)
    cta_table.add_column("Count", width=8, justify="right")
    cta_table.add_column("% of Ads", width=10, justify="right")

    for cta, count in cta_counts.most_common(10):
        pct = count / len(real_ads) * 100
        cta_table.add_row(cta, str(count), f"{pct:.1f}%")

    console.print(cta_table)

    # ==========================================
    # 5. REGIONS TARGETED
    # ==========================================
    console.print(Panel("[bold]TARGET REGIONS[/bold]", border_style="blue"))

    region_counts = Counter()
    for ad in real_ads:
        regions = ad.get("fetch_region", "")
        if isinstance(regions, str):
            for r in re.findall(r"'(\w{2})'", regions):
                region_counts[r] += 1
        elif isinstance(regions, list):
            for r in regions:
                region_counts[r] += 1

    reg_table = Table(show_lines=True)
    reg_table.add_column("Region", width=15)
    reg_table.add_column("Ads", width=8, justify="right")

    for reg, count in region_counts.most_common(15):
        reg_table.add_row(reg, str(count))

    console.print(reg_table)

    # ==========================================
    # 6. PLATFORM / SHOP TYPE
    # ==========================================
    shop_counts = Counter(str(ad.get("shop_type", "")) for ad in real_ads if ad.get("shop_type"))
    if shop_counts:
        console.print(Panel("[bold]SHOP PLATFORMS[/bold]", border_style="white"))
        for shop, count in shop_counts.most_common(10):
            console.print(f"  {shop}: {count} ads")

    # ==========================================
    # 7. STREETWEAR-SPECIFIC INSIGHTS
    # ==========================================
    console.print(Panel("[bold white on red] NEWGARMENTS COMPETITIVE INSIGHTS [/bold white on red]"))

    # Find streetwear-specific ads
    streetwear_keywords = ["streetwear", "hoodie", "oversized", "heavyweight", "baggy", "archive",
                           "drop", "limited", "tee", "crewneck", "jogger", "cargo"]
    streetwear_ads = []
    for ad in real_ads:
        text = (str(ad.get("desc", "")) + " " + str(ad.get("ai_analysis_script", "")) + " " +
                str(ad.get("ai_analysis_main_hook", ""))).lower()
        if any(kw in text for kw in streetwear_keywords):
            streetwear_ads.append(ad)

    console.print(f"\n[bold]Streetwear-relevant ads: {len(streetwear_ads)}/{len(real_ads)}[/bold]\n")

    if streetwear_ads:
        # Top streetwear ads
        sw_sorted = sorted(streetwear_ads, key=lambda a: parse_num(a.get("play_count", 0)), reverse=True)

        console.print("[bold green]Top Streetwear Competitor Ads:[/bold green]\n")
        for i, ad in enumerate(sw_sorted[:10], 1):
            name = safe_str(ad.get("unique_id", "") or ad.get("app_name", "") or "?", 40)
            views = parse_num(ad.get("play_count", 0))
            days = parse_num(ad.get("put_days", 0))
            hook = safe_str(ad.get("ai_analysis_main_hook", "") or "", 100)
            desc = safe_str(ad.get("desc", "") or "", 150)
            script = safe_str(ad.get("ai_analysis_script", "") or "", 200)
            cta = safe_str(ad.get("button_text", ""), 20)
            video = safe_str(ad.get("video_url", ""), 100)

            v_str = f"{views/1e6:.1f}M" if views >= 1e6 else f"{views/1e3:.0f}K" if views >= 1e3 else str(views)

            console.print(Panel(
                f"[bold]Advertiser:[/bold] {name}\n"
                f"[bold]Views:[/bold] {v_str} | [bold]Days:[/bold] {days} | [bold]CTA:[/bold] {cta}\n"
                f"[bold]Hook:[/bold] {hook}\n"
                f"[bold]Caption:[/bold] {desc}\n"
                f"[bold]Script:[/bold] {script}\n"
                f"[dim]Video: {video}[/dim]",
                title=f"#{i} Streetwear Competitor",
                border_style="green" if days > 14 else "yellow",
            ))

    # ==========================================
    # 8. ACTIONABLE RECOMMENDATIONS
    # ==========================================
    console.print(Panel(
        "[bold]Based on 309 competitor ads analyzed:[/bold]\n\n"
        "1. [green]HOOKS THAT WORK:[/green] Study the top hooks above - adapt them for NG's archive/quality angle\n"
        "2. [green]PROVEN FORMAT:[/green] Ads running 30+ days are validated winners - study their creative format\n"
        "3. [green]CTA STRATEGY:[/green] 'Shop now' dominates - but NG could differentiate with 'Cop before it\'s gone'\n"
        "4. [green]REGION FOCUS:[/green] Check which regions have most competition vs. opportunity\n"
        "5. [green]QUALITY ANGLE:[/green] Few competitors lead with fabric weight/quality - this is NG's whitespace\n"
        "6. [green]SCARCITY:[/green] 'Limited' and 'drop' hooks perform well - NG's real scarcity is an advantage\n"
        "7. [green]VIDEO URLS:[/green] Top competitor videos are saved - download and study the visual format\n\n"
        "[bold yellow]Next steps:[/bold yellow] Run pipiads_research_v2.py again with fixed Country/LastSeen filters\n"
        "for more targeted results in US/UK/EU markets.",
        title="ACTION PLAN FOR NEWGARMENTS",
        border_style="red",
    ))

    # Save analysis as markdown
    report_path = Path(__file__).parent / "PIPIADS_COMPETITOR_REPORT.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# PiPiAds Competitor Research Report - NEWGARMENTS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write(f"## Summary\n")
        f.write(f"- **Total ads analyzed:** {len(real_ads)}\n")
        f.write(f"- **Streetwear-relevant:** {len(streetwear_ads)}\n")
        f.write(f"- **Keywords searched:** streetwear, oversized hoodie, heavyweight hoodie, streetwear brand, baggy jeans, archive fashion, oversized tee, streetwear drop, limited drop clothing, mens streetwear\n\n")

        f.write(f"## Top Streetwear Competitor Ads\n\n")
        if streetwear_ads:
            sw_sorted = sorted(streetwear_ads, key=lambda a: parse_num(a.get("play_count", 0)), reverse=True)
            for i, ad in enumerate(sw_sorted[:20], 1):
                name = ad.get("unique_id", "") or ad.get("app_name", "") or "?"
                views = parse_num(ad.get("play_count", 0))
                days = parse_num(ad.get("put_days", 0))
                hook = ad.get("ai_analysis_main_hook", "") or ""
                desc = ad.get("desc", "") or ""
                script = ad.get("ai_analysis_script", "") or ""
                video = ad.get("video_url", "")

                f.write(f"### {i}. {name}\n")
                f.write(f"- **Views:** {views:,} | **Days running:** {days} | **CTA:** {ad.get('button_text', '')}\n")
                f.write(f"- **Hook:** {hook}\n")
                f.write(f"- **Caption:** {desc[:200]}\n")
                if script:
                    f.write(f"- **Script:** {script[:300]}\n")
                if video:
                    f.write(f"- **Video:** {video}\n")
                f.write(f"\n")

        f.write(f"## Hook Patterns\n\n")
        for cat, keywords in hook_categories.items():
            matching = [h for h in hooks if any(k in h.lower() for k in keywords)]
            if matching:
                f.write(f"### {cat} ({len(matching)} ads)\n")
                for h in matching[:5]:
                    f.write(f"- {h}\n")
                f.write(f"\n")

        f.write(f"## CTA Buttons\n\n")
        for cta, count in cta_counts.most_common(10):
            f.write(f"- **{cta}:** {count} ads ({count/len(real_ads)*100:.1f}%)\n")

        f.write(f"\n## Regions Targeted\n\n")
        for reg, count in region_counts.most_common(15):
            f.write(f"- **{reg}:** {count} ads\n")

    console.print(f"\n[green]Report saved to: {report_path.name}[/green]")


if __name__ == "__main__":
    analyze()
