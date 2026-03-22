"""
Daily Discovery — Automated subscription brand scouting.

This module is designed to be called by Claude via the command center.
It provides the scraping instructions as a prompt that Claude executes
via Playwright MCP, since Playwright runs through Claude's MCP tools.

Usage (called by Claude):
    1. Claude reads this file for the scraping workflow
    2. Claude executes the Playwright steps via MCP
    3. Claude calls parse_and_save() with the scraped data

Direct usage for testing:
    from scout.daily_discovery import get_scraping_prompt, parse_and_save
"""

import json
import random
from datetime import datetime
from pathlib import Path

from scout.config import (
    AD_LIBRARY_SEARCH_TERMS,
    SEARCH_QUERIES,
    TARGET_COUNTRIES,
    EXCLUDED_NICHES,
)
from scout.ad_library_scraper import parse_scraped_results, save_opportunities

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "scout" / "output"


def get_todays_search_terms(num_terms=3):
    """Get search terms for today (rotates daily)."""
    day_of_year = datetime.now().timetuple().tm_yday
    random.seed(day_of_year)

    # Pick from both lists
    ad_terms = random.sample(AD_LIBRARY_SEARCH_TERMS, min(2, len(AD_LIBRARY_SEARCH_TERMS)))
    niche_terms = random.sample(SEARCH_QUERIES, min(2, len(SEARCH_QUERIES)))

    return ad_terms + niche_terms


def get_scraping_prompt():
    """
    Generate the prompt that Claude should execute via Playwright MCP.
    This is the instruction set for the browser automation.
    """
    search_terms = get_todays_search_terms()
    countries = random.sample(TARGET_COUNTRIES, min(3, len(TARGET_COUNTRIES)))
    excluded = ", ".join(EXCLUDED_NICHES[:10])

    prompt = f"""AUTOMATED SCOUT: Subscription Brand Discovery

TASK: Search Meta Ad Library for subscription-based brands. Extract advertiser data for analysis.

SEARCH TERMS (do each one):
{json.dumps(search_terms, indent=2)}

COUNTRIES TO CHECK: {', '.join(countries)}

STEPS FOR EACH SEARCH TERM:
1. Navigate to https://www.facebook.com/ads/library
2. Set country filter to one of: {', '.join(countries)}
3. Select "All ads" category
4. Enter the search term in the search box
5. Wait for results to load
6. For each ad result visible (up to 20 per search):
   a. Extract: Advertiser name, ad text/copy, landing page URL
   b. Note: start date (look for "Started running on..." text)
   c. Note: media type (image, video, carousel)
   d. Check if the ad mentions subscription/monthly/box/membership
7. Scroll down to load more results if available
8. Move to next search term

EXCLUDE these niches (skip ads containing these words):
{excluded}

FOCUS ON: Niche subscription products that are NOT supplements, skincare, or health.
WINNING SIGNALS: Ads running 30+ days, brands with multiple active ads, clear subscription offer.

AFTER SCRAPING, save results by calling the parse function with this format:
Each ad should be a dict with keys:
- advertiser_name: str
- ad_text: str (the ad copy/body text)
- landing_url: str (the destination URL)
- start_date: str (e.g., "Mar 1, 2026")
- media_type: str ("image", "video", or "carousel")

Save the raw results as JSON to: {OUTPUT_DIR}/raw_scrape_{datetime.now().strftime('%Y%m%d')}.json
Then I will parse and score them.
"""
    return prompt


def parse_and_save(raw_results):
    """
    Parse raw scraped data and save scored opportunities.

    Args:
        raw_results: List of ad dicts from Playwright scraping

    Returns:
        Path to saved opportunities file
    """
    opportunities = parse_scraped_results(raw_results)

    today = datetime.now().strftime("%Y%m%d")
    filename = f"opportunities_{today}.json"
    output_path = save_opportunities(opportunities, filename)

    # Print summary
    print(f"\n{'='*50}")
    print(f"SCOUT RESULTS — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*50}")
    print(f"Total opportunities found: {len(opportunities)}")
    if opportunities:
        print(f"\nTop 5 opportunities:")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"  {i}. {opp['name']} (score: {opp['score']})")
            print(f"     Website: {opp.get('website', 'N/A')}")
            print(f"     Active ads: {opp['num_ads']}, longest running: {opp['max_ad_age_days']} days")
            print()
    else:
        print("No subscription brand opportunities found in this scan.")

    return output_path


def get_website_research_prompt(opportunities_file):
    """
    Generate prompt for deep-diving into top opportunities' websites.
    Called after initial ad library scan.
    """
    with open(opportunities_file) as f:
        data = json.load(f)

    top = data.get("opportunities", [])[:5]
    if not top:
        return "No opportunities to research."

    websites = []
    for opp in top:
        if opp.get("website"):
            websites.append({
                "brand": opp["name"],
                "website": opp["website"],
                "score": opp["score"],
            })

    prompt = f"""AUTOMATED SCOUT PHASE 2: Website Deep Dive

Research the top subscription brand opportunities found in the ad library scan.

BRANDS TO RESEARCH:
{json.dumps(websites, indent=2)}

FOR EACH WEBSITE:
1. Navigate to the website
2. Find their subscription/membership offering:
   - What products are in the subscription?
   - What's the price point? (monthly cost)
   - What's the value proposition? (why subscribe?)
   - What subscription frequency options? (weekly/monthly/quarterly)
3. Analyze the landing page:
   - What's the hero message?
   - What social proof do they show? (reviews, customer count, media mentions)
   - What's the CTA?
4. Check their product catalog:
   - How many products do they sell?
   - What's the average price?
   - Are products unique/niche or generic?
5. Check for reviews/trust signals:
   - Trustpilot, Google reviews, on-site reviews
   - How many reviews?
   - Average rating?

Save the research as JSON to: {OUTPUT_DIR}/website_research_{datetime.now().strftime('%Y%m%d')}.json

Each brand should have:
- brand_name, website, subscription_price, subscription_description
- value_proposition, target_audience, product_count
- trust_signals (reviews count, rating)
- cloneability_notes (how easy to replicate this model)
"""
    return prompt


if __name__ == "__main__":
    # Print today's scraping prompt
    print(get_scraping_prompt())
