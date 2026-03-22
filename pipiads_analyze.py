"""
PiPiAds Capture Analyzer - Offline analysis of saved captures.
Usage: python pipiads_analyze.py
"""

import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
DATA_DIR = Path(__file__).parent / "pipiads_data"


def load_all_captures() -> list:
    """Load all captured ad data."""
    all_ads = []
    seen_ids = set()
    for f in sorted(DATA_DIR.glob("pipiads_capture_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for ad in data:
                ad_id = ad.get("id") or ad.get("ad_id")
                if ad_id and ad_id not in seen_ids:
                    all_ads.append(ad)
                    seen_ids.add(ad_id)
                elif not ad_id:
                    all_ads.append(ad)
        except Exception as e:
            console.print(f"[red]Error loading {f.name}: {e}[/red]")
    return all_ads


def analyze_for_newgarments(ads: list):
    """Generate NEWGARMENTS-specific competitive insights."""
    if not ads:
        console.print("[yellow]No captured data found. Run pipiads_monitor.py first.[/yellow]")
        return

    console.print(Panel(
        f"[bold]NEWGARMENTS Competitive Analysis[/bold]\n"
        f"Analyzing {len(ads)} competitor ads",
        border_style="blue"
    ))

    # Collect patterns
    hooks_used = {}
    top_performers = []
    formats = {"slideshow": 0, "video": 0, "image": 0}
    cta_types = {}
    all_captions = []

    for ad in ads:
        caption = (ad.get("caption", "") or ad.get("ad_text", "") or "").lower()
        all_captions.append(caption)

        impressions = ad.get("impression", 0) or ad.get("impressions", 0) or 0
        likes = ad.get("like", 0) or ad.get("likes", 0) or 0
        days = ad.get("days", 0) or ad.get("days_running", 0) or 0

        # Track hooks
        hook_patterns = {
            "scarcity": ["limited", "sold out", "last chance", "selling fast", "almost gone"],
            "urgency": ["now", "today only", "ends", "hurry", "don't miss"],
            "quality": ["heavyweight", "premium", "quality", "thick", "heavy"],
            "identity": ["stand out", "different", "unique", "not like", "real ones"],
            "social proof": ["everyone", "trending", "viral", "seen on", "as worn"],
            "price": ["sale", "discount", "off", "save", "free shipping"],
        }
        for category, words in hook_patterns.items():
            if any(w in caption for w in words):
                hooks_used[category] = hooks_used.get(category, 0) + 1

        # CTA tracking
        cta = ad.get("cta", "") or ad.get("call_to_action", "") or ""
        if cta:
            cta_types[cta] = cta_types.get(cta, 0) + 1

        # Top performers
        if impressions > 100_000 and days > 7:
            eng_rate = (likes / impressions * 100) if impressions > 0 else 0
            top_performers.append({
                "ad": ad,
                "impressions": impressions,
                "engagement": eng_rate,
                "days": days,
            })

    # --- Display insights ---

    # Hook patterns
    if hooks_used:
        table = Table(title="Hook Patterns Used by Competitors", show_lines=True)
        table.add_column("Hook Type", width=20)
        table.add_column("Count", width=10, justify="right")
        table.add_column("NG Opportunity", width=50)

        ng_opportunities = {
            "scarcity": "Your NO RESTOCK positioning is authentic - lean into it harder than competitors faking it",
            "urgency": "Use real drop dates + 'once it's gone' messaging backed by actual limited inventory",
            "quality": "Your heavyweight construction is your edge - show GSM weight, fabric closeups",
            "identity": "Archive-coded positioning already nails this - emphasize 'worn by the ones who know'",
            "social proof": "Use UGC from real customers, not influencer placements",
            "price": "Don't compete on price - compete on value/rarity. Avoid discounts.",
        }

        for hook, count in sorted(hooks_used.items(), key=lambda x: x[1], reverse=True):
            table.add_row(hook.title(), str(count), ng_opportunities.get(hook, ""))
        console.print(table)

    # Top performers
    top_performers.sort(key=lambda x: x["impressions"], reverse=True)
    if top_performers:
        console.print(f"\n[bold]Top {min(10, len(top_performers))} Proven Winners:[/bold]")
        table = Table(show_lines=True)
        table.add_column("#", width=3)
        table.add_column("Advertiser", width=20)
        table.add_column("Impressions", width=14, justify="right")
        table.add_column("Eng %", width=8, justify="right")
        table.add_column("Days", width=6, justify="right")
        table.add_column("Caption", width=50)

        for i, tp in enumerate(top_performers[:10], 1):
            ad = tp["ad"]
            name = ad.get("advertiser", "") or ad.get("advertiser_name", "") or ad.get("nick_name", "") or "?"
            caption = (ad.get("caption", "") or ad.get("ad_text", "") or "")[:50]
            imp = f"{tp['impressions']/1e6:.1f}M" if tp["impressions"] >= 1e6 else f"{tp['impressions']/1e3:.0f}K"
            table.add_row(str(i), name[:20], imp, f"{tp['engagement']:.1f}%", str(tp["days"]), caption)
        console.print(table)

    # Actionable summary
    console.print(Panel(
        "[bold]Key Takeaways for NEWGARMENTS:[/bold]\n\n"
        "1. Study the top performers' VISUAL FORMAT (not just copy)\n"
        "2. Your authentic scarcity is a competitive advantage - make it undeniable\n"
        "3. Heavyweight quality proof (close-up fabric shots, weight tests) differentiates\n"
        "4. Archive aesthetic + 'gone forever' urgency = your strongest angle\n"
        "5. Avoid discount/sale hooks - they cheapen the archive positioning",
        border_style="green",
        title="Action Items"
    ))


if __name__ == "__main__":
    ads = load_all_captures()
    analyze_for_newgarments(ads)
