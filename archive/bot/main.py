"""
NEWGARMENTS Intelligence Bot - Main Orchestrator

Reads brand/audience documents, discovers competitors, analyzes their
web presence and ad activity, scores them by relevance, and exports
organized research results.

Usage:
    python -m bot.main [--skip-search] [--skip-ads] [--max-queries N]
"""
import asyncio
import argparse
import logging
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import DOCS_DIR, DOC_FILES, OUTPUT_DIR
from bot.ingest.files import read_all_docs
from bot.analysis.audience_profile import build_audience_profile, save_audience_profile
from bot.analysis.brand_profile import build_brand_profile, save_brand_profile
from bot.analysis.niche_map import build_niche_map, save_niche_map
from bot.discovery.competitors import discover_competitors_google, merge_with_seeds
from bot.discovery.social_search import enrich_social_profiles
from bot.research.websites import analyze_websites
from bot.research.ad_library import check_ad_library
from bot.analysis.ad_comparison import compare_ad_strategies
from bot.reporting.swipe_file import generate_swipe_file
from bot.scoring.competitor_score import score_competitors
from bot.reporting.exporters import (
    export_competitor_list_csv,
    export_competitor_analysis_json,
    export_research_report_md,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(OUTPUT_DIR, "bot.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("bot.main")


async def run(skip_search: bool = False, skip_ads: bool = False, max_queries: int = None):
    """Main execution pipeline."""

    # ── Step 1: Ingest documents ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1: Ingesting brand & audience documents")
    logger.info("=" * 60)
    docs = read_all_docs(DOCS_DIR, DOC_FILES)
    logger.info(f"Loaded {len(docs)} documents")

    # ── Step 2: Build audience profile ────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2: Building audience profile")
    logger.info("=" * 60)
    audience = build_audience_profile(docs)
    save_audience_profile(audience, os.path.join(OUTPUT_DIR, "audience_profile.json"))

    # ── Step 3: Build brand profile ───────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 3: Building brand profile")
    logger.info("=" * 60)
    brand = build_brand_profile(docs)
    save_brand_profile(brand, os.path.join(OUTPUT_DIR, "brand_profile.json"))

    # ── Step 4: Build niche map ───────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4: Building niche map")
    logger.info("=" * 60)
    niche = build_niche_map(audience, brand)
    save_niche_map(niche, os.path.join(OUTPUT_DIR, "niche_map.json"))

    # ── Step 5: Discover competitors ──────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 5: Discovering competitors")
    logger.info("=" * 60)
    if skip_search:
        logger.info("Skipping Google search (--skip-search). Using seeds only.")
        discovered = []
    else:
        discovered = await discover_competitors_google(max_queries=max_queries)

    competitors = merge_with_seeds(discovered)
    logger.info(f"Total competitors to analyze: {len(competitors)}")

    # ── Step 6: Enrich social profiles ────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 6: Enriching social media profiles")
    logger.info("=" * 60)
    competitors = await enrich_social_profiles(competitors)

    # ── Step 7: Analyze websites ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 7: Analyzing competitor websites")
    logger.info("=" * 60)
    competitors = await analyze_websites(competitors)

    # ── Step 8: Check Meta Ad Library ─────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 8: Checking Meta Ad Library")
    logger.info("=" * 60)
    if skip_ads:
        logger.info("Skipping Meta Ad Library (--skip-ads)")
        for comp in competitors:
            comp["meta_ads"] = {"has_active_ads": False, "errors": ["skipped"]}
    else:
        competitors = await check_ad_library(competitors)

    # ── Step 8b: Ad comparison & swipe file ───────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 8b: Analyzing ad strategies and generating swipe file")
    logger.info("=" * 60)
    ad_comparison = compare_ad_strategies(competitors)
    swipe_path = generate_swipe_file(competitors, OUTPUT_DIR)
    logger.info(f"Swipe file: {swipe_path}")

    # ── Step 9: Score competitors ─────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 9: Scoring competitors by relevance")
    logger.info("=" * 60)
    competitors = score_competitors(competitors, audience, brand)

    # ── Step 10: Export results ───────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 10: Exporting results")
    logger.info("=" * 60)

    export_competitor_list_csv(
        competitors, os.path.join(OUTPUT_DIR, "competitor_list.csv")
    )
    export_competitor_analysis_json(
        competitors, os.path.join(OUTPUT_DIR, "competitor_analysis.json")
    )
    export_research_report_md(
        competitors, audience, brand, niche,
        os.path.join(OUTPUT_DIR, "research_report.md"),
        ad_comparison=ad_comparison,
    )

    # Summary
    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("Files generated:")
    logger.info("  - audience_profile.json")
    logger.info("  - brand_profile.json")
    logger.info("  - niche_map.json")
    logger.info("  - competitor_list.csv")
    logger.info("  - competitor_analysis.json")
    logger.info("  - research_report.md")
    logger.info("  - ad_swipe_file.md")
    logger.info("  - ad_swipe_file.json")
    logger.info("  - bot.log")

    # Print top 5
    print("\n" + "=" * 60)
    print("TOP COMPETITORS BY RELEVANCE")
    print("=" * 60)
    for i, comp in enumerate(competitors[:10]):
        ads = "ADS" if comp.get("meta_ads", {}).get("has_active_ads") else "    "
        ig = f"@{comp['instagram']}" if comp.get("instagram") else ""
        print(f"  {i+1:2d}. [{comp.get('relevance_score', 0):4.1f}] {comp['name']:<30s} {ads}  {ig}")

    print(f"\nFull results in: {OUTPUT_DIR}")


def main():
    parser = argparse.ArgumentParser(description="NEWGARMENTS Competitor Intelligence Bot")
    parser.add_argument("--skip-search", action="store_true", help="Skip Google search, use seed competitors only")
    parser.add_argument("--skip-ads", action="store_true", help="Skip Meta Ad Library checks")
    parser.add_argument("--max-queries", type=int, default=None, help="Limit number of Google search queries")
    args = parser.parse_args()

    asyncio.run(run(
        skip_search=args.skip_search,
        skip_ads=args.skip_ads,
        max_queries=args.max_queries,
    ))


if __name__ == "__main__":
    main()
