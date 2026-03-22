"""
PiPiAds Competitor Ad Monitor for NEWGARMENTS
----------------------------------------------
Launches PiPiAds in a browser, lets you login, then monitors
competitor ads and gives real-time feedback in the terminal.

Usage:  python pipiads_monitor.py
Keys:   Press Enter in terminal to refresh analysis
        Type 'q' + Enter to quit
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.markdown import Markdown

console = Console()

# --- Config ---
SEARCH_KEYWORDS = [
    "streetwear",
    "hoodie",
    "oversized hoodie",
    "heavyweight hoodie",
    "streetwear brand",
    "baggy jeans",
    "archive fashion",
    "oversized tee",
    "streetwear drop",
]

DATA_DIR = Path(__file__).parent / "pipiads_data"
DATA_DIR.mkdir(exist_ok=True)

# Store intercepted ads
captured_ads = []
captured_responses = []


def analyze_ad(ad: dict) -> dict:
    """Analyze a single ad and return feedback."""
    feedback = []
    score = 0

    # --- Hook / caption analysis ---
    caption = ad.get("caption", "") or ad.get("ad_text", "") or ""
    caption_lower = caption.lower()

    # Check for hooks we care about
    strong_hooks = ["limited", "sold out", "never restock", "last chance", "drop", "exclusive"]
    weak_hooks = ["shop now", "link in bio", "check out", "buy now"]

    hook_matches = [h for h in strong_hooks if h in caption_lower]
    weak_matches = [h for h in weak_hooks if h in caption_lower]

    if hook_matches:
        feedback.append(f"[green]STRONG hooks: {', '.join(hook_matches)}[/green]")
        score += len(hook_matches) * 15
    if weak_matches:
        feedback.append(f"[yellow]Generic CTAs: {', '.join(weak_matches)}[/yellow]")
        score += len(weak_matches) * 5

    # Emotional triggers
    emotion_words = ["fear", "miss", "regret", "confidence", "identity", "rare", "grail", "fire"]
    emotion_hits = [w for w in emotion_words if w in caption_lower]
    if emotion_hits:
        feedback.append(f"[cyan]Emotion triggers: {', '.join(emotion_hits)}[/cyan]")
        score += len(emotion_hits) * 10

    # --- Performance metrics ---
    impressions = ad.get("impression", 0) or ad.get("impressions", 0) or 0
    likes = ad.get("like", 0) or ad.get("likes", 0) or 0
    comments = ad.get("comment", 0) or ad.get("comments", 0) or 0
    shares = ad.get("share", 0) or ad.get("shares", 0) or 0
    days_running = ad.get("days", 0) or ad.get("days_running", 0) or 0

    if impressions > 1_000_000:
        feedback.append(f"[bold green]VIRAL: {impressions/1e6:.1f}M impressions[/bold green]")
        score += 30
    elif impressions > 100_000:
        feedback.append(f"[green]Strong reach: {impressions/1e3:.0f}K impressions[/green]")
        score += 20

    # Engagement rate
    if impressions > 0:
        eng_rate = (likes + comments + shares) / impressions * 100
        if eng_rate > 5:
            feedback.append(f"[bold green]HIGH engagement: {eng_rate:.1f}%[/bold green]")
            score += 25
        elif eng_rate > 2:
            feedback.append(f"[green]Good engagement: {eng_rate:.1f}%[/green]")
            score += 15
        elif eng_rate < 0.5:
            feedback.append(f"[red]Low engagement: {eng_rate:.2f}%[/red]")

    # Longevity
    if days_running > 30:
        feedback.append(f"[green]Running {days_running} days = proven winner[/green]")
        score += 20
    elif days_running > 14:
        feedback.append(f"[yellow]Running {days_running} days = testing phase passed[/yellow]")
        score += 10

    # --- Relevance to NEWGARMENTS ---
    ng_keywords = ["heavyweight", "oversized", "archive", "limited", "no restock",
                    "streetwear", "hoodie", "baggy", "drop", "capsule"]
    relevance = [k for k in ng_keywords if k in caption_lower]
    if relevance:
        feedback.append(f"[magenta]Relevant to NG: {', '.join(relevance)}[/magenta]")
        score += len(relevance) * 5

    # --- Actionable takeaways ---
    if not feedback:
        feedback.append("[dim]No strong signals found[/dim]")

    return {
        "score": min(score, 100),
        "feedback": feedback,
        "caption_preview": caption[:120] + "..." if len(caption) > 120 else caption,
    }


def newgarments_feedback(ad: dict, analysis: dict) -> list[str]:
    """Generate NEWGARMENTS-specific creative feedback."""
    tips = []
    caption = (ad.get("caption", "") or ad.get("ad_text", "") or "").lower()

    if analysis["score"] >= 60:
        tips.append("STEAL THIS ANGLE - adapt the hook for NG's archive positioning")

    if "free shipping" in caption:
        tips.append("They're using free shipping as CTA - NG could counter with 'no restock' urgency instead")

    if any(w in caption for w in ["gildan", "blank", "cheap"]):
        tips.append("Competitor acknowledging quality concerns - NG can attack this directly")

    impressions = ad.get("impression", 0) or ad.get("impressions", 0) or 0
    days = ad.get("days", 0) or ad.get("days_running", 0) or 0
    if impressions > 500_000 and days > 20:
        tips.append("PROVEN WINNER - study the visual format, not just the copy")

    if any(w in caption for w in ["slide", "carousel", "slideshow"]):
        tips.append("Slideshow/carousel format detected - matches your TikTok slideshow strategy")

    return tips


def display_dashboard(ads: list):
    """Render the analysis dashboard."""
    console.clear()
    console.print(Panel(
        "[bold white on blue] NEWGARMENTS - PiPiAds Competitor Monitor [/bold white on blue]",
        subtitle=f"[dim]{len(ads)} ads captured | {datetime.now().strftime('%H:%M:%S')}[/dim]"
    ))

    if not ads:
        console.print("\n[yellow]No ads captured yet. Browse PiPiAds in the browser to capture data.[/yellow]")
        console.print("[dim]The script intercepts API responses as you search and scroll.[/dim]\n")
        console.print("[bold]Suggested searches for NEWGARMENTS competitors:[/bold]")
        for kw in SEARCH_KEYWORDS:
            console.print(f"  > {kw}")
        return

    # Sort by score
    scored = []
    for ad in ads:
        analysis = analyze_ad(ad)
        ng_tips = newgarments_feedback(ad, analysis)
        scored.append((ad, analysis, ng_tips))
    scored.sort(key=lambda x: x[1]["score"], reverse=True)

    # Top performers table
    table = Table(title="Top Competitor Ads", show_lines=True, expand=True)
    table.add_column("#", width=3, style="dim")
    table.add_column("Advertiser", width=18)
    table.add_column("Caption Preview", width=40)
    table.add_column("Impressions", width=12, justify="right")
    table.add_column("Eng %", width=8, justify="right")
    table.add_column("Days", width=6, justify="right")
    table.add_column("Score", width=7, justify="right")

    for i, (ad, analysis, _) in enumerate(scored[:15], 1):
        advertiser = ad.get("advertiser", "") or ad.get("advertiser_name", "") or ad.get("nick_name", "") or "Unknown"
        impressions = ad.get("impression", 0) or ad.get("impressions", 0) or 0
        likes = ad.get("like", 0) or ad.get("likes", 0) or 0
        comments = ad.get("comment", 0) or ad.get("comments", 0) or 0
        shares = ad.get("share", 0) or ad.get("shares", 0) or 0
        days = ad.get("days", 0) or ad.get("days_running", 0) or 0
        eng = f"{(likes+comments+shares)/impressions*100:.1f}%" if impressions > 0 else "N/A"

        imp_str = f"{impressions/1e6:.1f}M" if impressions >= 1e6 else f"{impressions/1e3:.0f}K" if impressions >= 1e3 else str(impressions)

        score_color = "green" if analysis["score"] >= 60 else "yellow" if analysis["score"] >= 30 else "red"
        table.add_row(
            str(i),
            advertiser[:18],
            analysis["caption_preview"][:40],
            imp_str,
            eng,
            str(days),
            f"[{score_color}]{analysis['score']}[/{score_color}]"
        )

    console.print(table)

    # Detailed feedback for top 5
    console.print("\n[bold]Detailed Analysis - Top 5:[/bold]\n")
    for i, (ad, analysis, ng_tips) in enumerate(scored[:5], 1):
        advertiser = ad.get("advertiser", "") or ad.get("advertiser_name", "") or ad.get("nick_name", "") or "Unknown"
        panel_content = []

        panel_content.append(f"[bold]Caption:[/bold] {analysis['caption_preview']}")
        panel_content.append("")

        for fb in analysis["feedback"]:
            panel_content.append(f"  {fb}")

        if ng_tips:
            panel_content.append("")
            panel_content.append("[bold magenta]NEWGARMENTS Tips:[/bold magenta]")
            for tip in ng_tips:
                panel_content.append(f"  [magenta]> {tip}[/magenta]")

        score = analysis["score"]
        border = "green" if score >= 60 else "yellow" if score >= 30 else "red"
        console.print(Panel(
            "\n".join(panel_content),
            title=f"[bold]#{i} {advertiser} | Score: {score}/100[/bold]",
            border_style=border,
        ))

    # Summary insights
    avg_score = sum(s[1]["score"] for s in scored) / len(scored) if scored else 0
    high_performers = sum(1 for s in scored if s[1]["score"] >= 60)

    console.print(Panel(
        f"[bold]Avg score:[/bold] {avg_score:.0f}/100 | "
        f"[bold]High performers (60+):[/bold] {high_performers}/{len(scored)} | "
        f"[bold]Total captured:[/bold] {len(ads)}",
        title="Summary",
        border_style="blue"
    ))


def save_captured_data(ads: list):
    """Save captured ads to JSON."""
    if not ads:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filepath = DATA_DIR / f"pipiads_capture_{ts}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(ads, f, indent=2, ensure_ascii=False, default=str)
    console.print(f"[dim]Saved {len(ads)} ads to {filepath.name}[/dim]")


async def handle_response(response):
    """Intercept API responses from PiPiAds."""
    url = response.url
    try:
        # Look for API calls that return ad data
        if any(pattern in url for pattern in [
            "/api/", "/ad/search", "/ad/list", "/search",
            "adSearch", "ad_search", "getAd", "get_ad",
            "/v1/", "/v2/", "query", "explore",
        ]):
            if response.status == 200:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "application" in content_type:
                    try:
                        body = await response.json()
                    except Exception:
                        return

                    ads_found = extract_ads_from_response(body, url)
                    if ads_found:
                        new_count = 0
                        existing_ids = {ad.get("id") or ad.get("ad_id") or id(ad) for ad in captured_ads}
                        for ad in ads_found:
                            ad_id = ad.get("id") or ad.get("ad_id")
                            if ad_id and ad_id not in existing_ids:
                                captured_ads.append(ad)
                                new_count += 1
                                existing_ids.add(ad_id)
                            elif not ad_id:
                                captured_ads.append(ad)
                                new_count += 1

                        if new_count > 0:
                            console.print(f"[green]+ {new_count} new ads captured (total: {len(captured_ads)})[/green]")
    except Exception as e:
        pass  # Silent fail on non-relevant responses


def extract_ads_from_response(data, url: str) -> list:
    """Try to extract ad objects from various API response formats."""
    ads = []

    if isinstance(data, dict):
        # Common patterns: data.list, data.ads, data.items, data.records
        for key in ["list", "ads", "items", "records", "data", "results", "ad_list"]:
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict) and looks_like_ad(item):
                        ads.append(item)
                if ads:
                    return ads

        # Nested: data.data.list etc.
        if "data" in data and isinstance(data["data"], dict):
            return extract_ads_from_response(data["data"], url)

        # Check if the dict itself is an ad
        if looks_like_ad(data):
            ads.append(data)

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and looks_like_ad(item):
                ads.append(item)

    return ads


def looks_like_ad(item: dict) -> bool:
    """Heuristic: does this dict look like an ad object?"""
    ad_signals = [
        "impression", "impressions", "like", "likes", "comment", "comments",
        "share", "shares", "ad_text", "caption", "advertiser", "nick_name",
        "advertiser_name", "ad_id", "creative", "days", "days_running",
        "video_url", "thumbnail", "cover", "landing_page", "cta",
        "ad_title", "cost", "spend",
    ]
    matches = sum(1 for s in ad_signals if s in item)
    return matches >= 3


async def main():
    console.print(Panel(
        "[bold]NEWGARMENTS - PiPiAds Competitor Monitor[/bold]\n\n"
        "1. A browser will open to pipiads.com\n"
        "2. Log in with your account\n"
        "3. Search for competitor ads - the script captures data automatically\n"
        "4. Come back to this terminal for real-time analysis\n\n"
        "[dim]Controls: Press Enter to refresh dashboard | 's' to save | 'q' to quit[/dim]",
        border_style="blue",
    ))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport=None,
            no_viewport=True,
        )

        # Try to load saved session cookies
        cookie_file = DATA_DIR / "pipiads_cookies.json"
        if cookie_file.exists():
            try:
                cookies = json.loads(cookie_file.read_text())
                await context.add_cookies(cookies)
                console.print("[green]Loaded saved session cookies[/green]")
            except Exception:
                pass

        page = await context.new_page()

        # Intercept all responses
        page.on("response", handle_response)

        # Navigate to PiPiAds
        await page.goto("https://www.pipiads.com/ad-search", wait_until="domcontentloaded")
        console.print("[green]Browser opened. Please log in if needed, then start searching![/green]\n")

        # Wait for login
        console.print("[yellow]Waiting for you to log in and start browsing...[/yellow]")
        console.print("[dim]The script automatically captures ad data from API responses as you browse.[/dim]\n")

        # Monitor loop
        try:
            while True:
                # Check for user input (non-blocking on Windows)
                display_dashboard(captured_ads)

                console.print("\n[dim]Commands: [Enter] refresh | [s] save data | [q] quit[/dim]")

                # Wait a bit then auto-refresh, or respond to input
                try:
                    # Use asyncio to wait for either timeout or page events
                    await asyncio.sleep(15)

                    # Save cookies periodically
                    try:
                        cookies = await context.cookies()
                        cookie_file.write_text(json.dumps(cookies, default=str))
                    except Exception:
                        pass

                except KeyboardInterrupt:
                    break

        except KeyboardInterrupt:
            pass

        # Save on exit
        console.print("\n[yellow]Shutting down...[/yellow]")
        save_captured_data(captured_ads)

        # Save cookies for next session
        try:
            cookies = await context.cookies()
            cookie_file.write_text(json.dumps(cookies, default=str))
            console.print("[green]Session cookies saved for next time[/green]")
        except Exception:
            pass

        await browser.close()

    console.print("[bold green]Done! Check pipiads_data/ for saved captures.[/bold green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Saving data...[/yellow]")
        save_captured_data(captured_ads)
