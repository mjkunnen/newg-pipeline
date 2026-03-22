"""
NEWGARMENTS Competitor Creative Remake Pipeline — Main Orchestrator

Watches a Pinterest board (via Zapier Google Sheet queue) or accepts manual
TikTok links, analyzes competitor creatives with OpenAI Vision, generates
remakes with Nano Banana 2 (fal.ai) for each product in the catalog, and
delivers everything to Google Drive.

Usage:
    # Process Pinterest queue (from Zapier Google Sheet)
    python -m pipeline.remake_pipeline --source pinterest

    # Process a single TikTok link
    python -m pipeline.remake_pipeline --source tiktok --url "https://tiktok.com/..."

    # Process a single image URL directly (for testing)
    python -m pipeline.remake_pipeline --source direct --url "https://..." --pin-id test123
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.capture import capture_pinterest_pin, capture_tiktok
from pipeline.analyze import analyze_creative
from pipeline.generate_image import generate_for_catalog
from pipeline.deliver import build_delivery_manifest, save_manifest, get_files_for_upload

# Configure logging
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(OUTPUT_DIR / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline.main")

# Paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
CATALOG_PATH = CONFIG_DIR / "clothing-catalog.json"
GEN_CONFIG_PATH = CONFIG_DIR / "generation-config.json"


def load_catalog() -> dict:
    """Load product catalog."""
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_gen_config() -> dict:
    """Load generation config."""
    with open(GEN_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_pipeline_for_source(source_info: dict, catalog: dict) -> dict:
    """Run the full pipeline for a single source creative.

    Steps:
    1. Analyze the source image with OpenAI Vision
    2. Generate remakes with Nano Banana 2 for each product
    3. Build delivery manifest
    4. Return manifest for Drive upload

    Returns the delivery manifest dict.
    """
    today = date.today().isoformat()
    image_path = source_info.get("local_path")

    if not image_path or not Path(image_path).exists():
        logger.error(f"Source image not found: {image_path}")
        return {"error": "Source image not found"}

    # ── Step 1: Analyze ─────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 1: Analyzing source creative with OpenAI Vision")
    logger.info("=" * 60)
    description = source_info.get("description", "")
    creative_brief = analyze_creative(image_path, description)

    # Save the creative brief
    brief_dir = OUTPUT_DIR / today
    brief_dir.mkdir(parents=True, exist_ok=True)
    source_id = source_info.get("pin_id", source_info.get("video_id", "unknown"))
    brief_path = brief_dir / f"creative_brief_{source_id}.json"
    brief_path.write_text(json.dumps(creative_brief, indent=2))
    logger.info(f"Creative brief saved: {brief_path}")

    # ── Step 2: Generate images ─────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 2: Generating remakes with Nano Banana 2")
    logger.info("=" * 60)
    output_base = str(OUTPUT_DIR / today / "generated")
    generated_images = generate_for_catalog(
        creative_brief, catalog, image_path, output_base
    )

    successful = [g for g in generated_images if g["status"] == "success"]
    failed = [g for g in generated_images if g["status"] == "failed"]
    logger.info(f"Generation complete: {len(successful)} success, {len(failed)} failed")

    # ── Step 3: Video generation (only if source was video) ─────────
    generated_videos = None
    if source_info.get("source_type") == "tiktok" and source_info.get("video_path"):
        logger.info("=" * 60)
        logger.info("STEP 3: Generating video versions (source was video)")
        logger.info("=" * 60)
        try:
            from pipeline.generate_video import generate_videos_for_images
            generated_videos = generate_videos_for_images(generated_images)
        except Exception as e:
            logger.warning(f"Video generation skipped: {e}")

    # ── Step 4: Build delivery manifest ─────────────────────────────
    logger.info("=" * 60)
    logger.info("STEP 4: Building delivery manifest")
    logger.info("=" * 60)
    manifest = build_delivery_manifest(
        source_info, creative_brief, generated_images, generated_videos
    )
    manifest_path = save_manifest(manifest, str(OUTPUT_DIR))

    # Log summary
    files = get_files_for_upload(manifest)
    logger.info(f"Ready for Drive upload: {len(files)} files across {len(manifest['collections'])} collections")
    for col, items in manifest["collections"].items():
        logger.info(f"  {col}: {len(items)} variants")

    return manifest


def process_pinterest_pin(image_url: str, pin_id: str, description: str = ""):
    """Process a single Pinterest pin through the full pipeline."""
    logger.info("=" * 60)
    logger.info(f"PROCESSING PINTEREST PIN: {pin_id}")
    logger.info("=" * 60)

    catalog = load_catalog()
    source_info = capture_pinterest_pin(image_url, pin_id, description)
    manifest = run_pipeline_for_source(source_info, catalog)
    return manifest


def process_tiktok(tiktok_url: str):
    """Process a TikTok link through the full pipeline."""
    logger.info("=" * 60)
    logger.info(f"PROCESSING TIKTOK: {tiktok_url}")
    logger.info("=" * 60)

    catalog = load_catalog()
    source_info = capture_tiktok(tiktok_url)
    manifest = run_pipeline_for_source(source_info, catalog)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="NEWGARMENTS Creative Remake Pipeline")
    parser.add_argument("--source", choices=["pinterest", "tiktok", "direct"],
                       required=True, help="Source type")
    parser.add_argument("--url", type=str, help="URL to process (TikTok link or direct image URL)")
    parser.add_argument("--pin-id", type=str, default="test", help="Pin ID (for direct mode)")
    parser.add_argument("--description", type=str, default="", help="Source description")
    args = parser.parse_args()

    if args.source == "pinterest" and not args.url:
        logger.info("Pinterest queue mode — reading from Google Sheet...")
        logger.info("(Use Zapier MCP google_sheets_lookup_spreadsheet_rows to read pending pins)")
        logger.info("For now, use --url to pass a direct image URL with --source direct")
        return

    if args.source == "tiktok":
        if not args.url:
            logger.error("--url required for TikTok source")
            return
        manifest = process_tiktok(args.url)

    elif args.source in ("pinterest", "direct"):
        if not args.url:
            logger.error("--url required")
            return
        manifest = process_pinterest_pin(args.url, args.pin_id, args.description)

    # Print summary
    if manifest and "error" not in manifest:
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
        print(f"Date: {manifest['date']}")
        print(f"Total images: {manifest['total_images']}")
        print(f"Collections: {', '.join(manifest['drive_structure']['collection_folders'])}")
        print(f"\nFiles ready for Google Drive upload.")
        print(f"Use Zapier MCP tools to upload to: {manifest['drive_structure']['root']}/{manifest['date']}/")


if __name__ == "__main__":
    main()
