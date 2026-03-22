"""
Standalone Meta Ad Library analyzer for NEWGARMENTS competitor research.

Runs ad-only analysis independently, without the full 10-step pipeline.

Usage:
    python -m bot.ad_analyzer --brands "Corteiz,Trapstar,Represent Clo"
    python -m bot.ad_analyzer --use-seeds --country NL --limit 30
    python -m bot.ad_analyzer --input competitor_pages_latest.json
"""
import asyncio
import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config import OUTPUT_DIR, SEED_COMPETITORS, META_ACCESS_TOKEN
from bot.research.ad_library import check_ad_library
from bot.analysis.ad_comparison import compare_ad_strategies
from bot.reporting.swipe_file import generate_swipe_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(OUTPUT_DIR, "ad_analyzer.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("bot.ad_analyzer")


async def run_ad_analysis(
    brands: list[dict],
    country: str = "ALL",
    limit: int = 50,
    output_dir: str = None,
):
    """Run ad-only analysis pipeline."""
    output_dir = output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Starting ad analysis for {len(brands)} brands (country={country}, limit={limit})")

    # 1. Fetch ads
    logger.info("=" * 60)
    logger.info("STEP 1: Fetching ads from Meta Ad Library API")
    logger.info("=" * 60)
    brands = await check_ad_library(brands, country=country, limit=limit)

    with_ads = sum(1 for b in brands if b.get("meta_ads", {}).get("has_active_ads"))
    logger.info(f"Found ads for {with_ads}/{len(brands)} brands")

    # 2. Compare
    logger.info("=" * 60)
    logger.info("STEP 2: Comparing ad strategies")
    logger.info("=" * 60)
    comparison = compare_ad_strategies(brands)

    # Save comparison JSON
    comparison_path = os.path.join(output_dir, "ad_comparison.json")
    with open(comparison_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Ad comparison: {comparison_path}")

    # 3. Swipe file
    logger.info("=" * 60)
    logger.info("STEP 3: Generating swipe file")
    logger.info("=" * 60)
    swipe_path = generate_swipe_file(brands, output_dir)
    logger.info(f"Swipe file: {swipe_path}")

    # 4. Raw ad data export
    raw_path = os.path.join(output_dir, "ad_raw_data.json")
    raw_data = []
    for b in brands:
        meta = b.get("meta_ads", {})
        if meta.get("has_active_ads"):
            raw_data.append({
                "brand": b["name"],
                "ad_count": meta["approximate_ad_count"],
                "themes": meta["observed_themes"],
                "summary": meta.get("summary", {}),
                "ads": meta.get("ads", []),
            })
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Raw ad data: {raw_path}")

    # Summary
    logger.info("=" * 60)
    logger.info("COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Output directory: {output_dir}")
    logger.info("Files generated:")
    logger.info("  - ad_comparison.json")
    logger.info("  - ad_swipe_file.md")
    logger.info("  - ad_swipe_file.json")
    logger.info("  - ad_raw_data.json")

    # Print summary
    print("\n" + "=" * 60)
    print("AD ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Brands analyzed: {len(brands)}")
    print(f"Brands with ads: {with_ads}")
    total_ads = comparison.get("total_ads_analyzed", 0)
    print(f"Total ads found: {total_ads}")
    print()

    if comparison.get("insights"):
        print("KEY INSIGHTS:")
        for insight in comparison["insights"]:
            print(f"  - {insight}")
        print()

    print(f"Full results in: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="NEWGARMENTS Ad Library Analyzer - Standalone ad comparison tool"
    )
    parser.add_argument(
        "--brands", type=str,
        help="Comma-separated brand names (e.g. 'Corteiz,Trapstar,Represent Clo')"
    )
    parser.add_argument(
        "--use-seeds", action="store_true",
        help="Use all seed competitors from config"
    )
    parser.add_argument(
        "--input", type=str,
        help="Path to JSON file with brand list (each entry needs at least a 'name' key)"
    )
    parser.add_argument(
        "--country", type=str, default="ALL",
        help="Country code filter (default: ALL). E.g. NL, US, GB"
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Max ads to fetch per brand (default: 50)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: bot/output/)"
    )
    args = parser.parse_args()

    if args.brands:
        brands = [{"name": b.strip()} for b in args.brands.split(",")]
    elif args.use_seeds:
        brands = [dict(s) for s in SEED_COMPETITORS]  # copy to avoid mutating config
    elif args.input:
        with open(args.input, encoding="utf-8") as f:
            brands = json.load(f)
            if isinstance(brands, dict):
                brands = brands.get("competitors", brands.get("brands", []))
    else:
        parser.error("Provide --brands, --use-seeds, or --input")

    if not brands:
        parser.error("No brands to analyze")

    print(f"Analyzing {len(brands)} brands...")
    asyncio.run(run_ad_analysis(brands, args.country, args.limit, args.output_dir))


if __name__ == "__main__":
    main()
