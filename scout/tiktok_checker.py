"""
TikTok Carousel Checker & Remake Pipeline.

Scrapes TikTok, selects top carousels, remakes slides with fal.ai.
Outputs a JSON manifest — Claude Code handles Drive upload + Sheets logging via Zapier MCP.

Env vars needed (.env):
  FAL_KEY, APIFY_TOKEN

Usage:
    python scout/tiktok_checker.py              # normal run (top 3 carousels)
    python scout/tiktok_checker.py --dry-run    # list candidates without generating
    python scout/tiktok_checker.py --max-posts 1  # limit carousels to process
"""
import os
import sys
import json
import base64
import time
import ssl
import logging
import argparse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

FAL_KEY = os.getenv("FAL_KEY")
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
FAL_HEADERS = {
    "Authorization": f"Key {FAL_KEY}",
    "Content-Type": "application/json",
}

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
if not APIFY_TOKEN:
    raise RuntimeError("APIFY_TOKEN not set – add it to .env")
APIFY_ACTOR_ID = "GdWCkxBtKWOsKjdch"  # clockworks/tiktok-scraper

# Output manifest — Claude Code reads this to upload via Zapier MCP
MANIFEST_FILE = BASE_DIR / "scout" / "output" / "tiktok_manifest.json"

TIKTOK_ACCOUNTS = [
    "fiveleafsclo",
    "thefitscene",
    "azeliasolo",
    "nfits_18",
    "aightfits_clo",
    "fupgun",
    "copenhagenlove1",
    "strhvn2",
    "thebrand4u",
    "outfits.nstra",
    "outfitinspostreet",
    "away.fl",
    "havenfit",
]

# Shopify CDN product reference URLs
TOPS = {
    "checkered-zipper-gray": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/4_ccc56236-97bc-457b-bfd8-d8e354edc3cb.png?v=1766218170",
    "zip-hoodie-y2k-dark-green": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/10_99446fbd-db7b-4093-8981-b3360f12641e.png?v=1765308631",
    "checkered-zipper-black": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/6_19932bda-c124-420e-9b59-6419d31dcbc3.png?v=1771230227",
    "zip-hoodie-y2k-pink": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/13_ef5d7cd1-a2e4-46f7-af14-6303035cc042.png?v=1765308631",
    "zip-hoodie-y2k-black": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/9_36290722-5acb-4006-91d5-7fe7d57de6d3.png?v=1765308631",
    "checkered-zipper-red": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/3_538de051-5bc7-45b9-8bf3-185392b8d99c.png?v=1771230227",
}
BOTTOMS = {
    "embroidered-striped-jeans": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/7_b624fd29-7a4b-4f12-877f-d85ed21952c3.png?v=1765388598",
    "graphic-lining-jeans": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/Untitleddesign_98_6efaadd8-c42c-42a4-9182-4735de182451.png?v=1768054930",
}
SHOES = {
    "fur-graphic-sneakers": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/sneaker-fourrure-7147771.webp?v=1771060651",
    "ocean-stars-sneaker": "https://cdn.shopify.com/s/files/1/0948/8973/8617/files/3_ef25b74a-2f1f-4c14-b8ee-dfa89eed2ef4.jpg?v=1763046283",
}

OUTFITS = [
    ("checkered-zipper-gray", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-dark-green", "graphic-lining-jeans", "ocean-stars-sneaker"),
    ("checkered-zipper-black", "embroidered-striped-jeans", "ocean-stars-sneaker"),
    ("zip-hoodie-y2k-pink", "graphic-lining-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-black", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("checkered-zipper-red", "graphic-lining-jeans", "ocean-stars-sneaker"),
]

TIKTOK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.tiktok.com/",
}

# Logging
(BASE_DIR / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "logs" / "tiktok-checker.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("tiktok_checker")


# ---------------------------------------------------------------------------
# Apify: TikTok scraping (cloud API)
# ---------------------------------------------------------------------------

def fetch_all_posts(accounts, results_per_page=20):
    """Scrape posts from all TikTok accounts via Apify clockworks/tiktok-scraper."""
    profile_urls = [f"https://www.tiktok.com/@{a}" for a in accounts]

    log.info(f"Starting Apify run for {len(accounts)} accounts...")
    run_input = {
        "profiles": profile_urls,
        "resultsPerPage": results_per_page,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }

    url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs?token={APIFY_TOKEN}"
    resp = requests.post(url, json=run_input, timeout=30)
    resp.raise_for_status()
    run_data = resp.json()["data"]
    run_id = run_data["id"]
    dataset_id = run_data["defaultDatasetId"]
    log.info(f"Apify run started: {run_id}")

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    for attempt in range(120):  # max 10 min
        time.sleep(5)
        status = requests.get(status_url, timeout=15).json()["data"]["status"]
        if status == "SUCCEEDED":
            log.info(f"Apify run completed after {(attempt+1)*5}s")
            break
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            log.error(f"Apify run failed: {status}")
            return []
    else:
        log.error("Apify run timed out after 10 minutes")
        return []

    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json"
    items = requests.get(items_url, timeout=60).json()
    log.info(f"Fetched {len(items)} total posts from Apify")
    return items


def select_top_carousels(posts, processed_ids, max_age_days=7, top_n=3):
    """Filter to new carousel posts from last N days, sorted by views."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cutoff_ts = cutoff.timestamp()

    candidates = []
    for post in posts:
        if not post.get("isSlideshow"):
            continue
        slides = post.get("slideshowImageLinks", [])
        if not slides:
            continue
        create_time = post.get("createTime", 0)
        if create_time < cutoff_ts:
            continue
        post_id = str(post.get("id", ""))
        if post_id in processed_ids:
            continue

        username = post.get("authorMeta", {}).get("name", "unknown")
        candidates.append({
            "post_id": post_id,
            "username": username,
            "play_count": post.get("playCount", 0),
            "create_time": create_time,
            "create_date": post.get("createTimeISO", ""),
            "web_url": post.get("webVideoUrl", ""),
            "text": post.get("text", "")[:100],
            "num_slides": len(slides),
            "slides": slides,
        })

    candidates.sort(key=lambda x: x["play_count"], reverse=True)
    selected = candidates[:top_n]

    log.info(f"Found {len(candidates)} carousel candidates, selected top {len(selected)}")
    for i, c in enumerate(selected):
        log.info(f"  #{i+1}: @{c['username']} — {c['play_count']:,} views — {c['num_slides']} slides — {c['post_id']}")

    return selected


# ---------------------------------------------------------------------------
# Download slides
# ---------------------------------------------------------------------------

def download_slides(carousel, output_dir):
    """Download all slide images from a carousel post."""
    post_dir = output_dir / f"{carousel['username']}_{carousel['post_id']}"
    post_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, slide in enumerate(carousel["slides"]):
        url = slide.get("downloadLink") or slide.get("tiktokLink")
        if not url:
            continue

        filename = f"slide_{i+1}.jpg"
        filepath = post_dir / filename

        try:
            req = urllib.request.Request(url, headers=TIKTOK_HEADERS)
            ctx = ssl.create_default_context()
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
            data = resp.read()
            filepath.write_bytes(data)
            log.info(f"  Downloaded {filename} ({len(data)/1024:.1f} KB)")
            paths.append(filepath)
        except Exception as e:
            log.warning(f"  Failed to download slide {i+1}: {e}")

    return paths


# ---------------------------------------------------------------------------
# fal.ai remake (cloud API)
# ---------------------------------------------------------------------------

def image_to_data_url(path):
    """Convert local image to base64 data URL."""
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def build_prompt(top_name, bottom_name, shoes_name):
    return (
        f"Image 1 is the source photo. CRITICAL: Maintain the EXACT same layout, format, and composition. "
        f"If it's a flat lay (clothing laid out on a surface), keep it as a flat lay — replace each clothing item "
        f"in the SAME position, SAME size, SAME proportions. Do NOT change a flat lay into a model photo. "
        f"If it's a model photo, keep the same person, face, skin tone, pose, background, and lighting. "
        f"ONLY change the clothing items: "
        f"Image 2 is the top: a {top_name.replace('-', ' ')} zip hoodie, "
        f"with a plain white t-shirt underneath, visible at the chest/neckline. "
        f"Image 3 is the bottom: {bottom_name.replace('-', ' ')}. "
        f"Image 4 is the footwear: {shoes_name.replace('-', ' ')}. "
        f"PROPORTIONS ARE CRITICAL: The shoes must be realistically sized — small relative to the clothing, "
        f"as they would appear in real life. The hoodie should be the largest item. "
        f"Items must NOT overlap each other — keep clear spacing between each piece. "
        f"Match the exact scale and positioning of items from the original image."
    )


def submit_to_fal(source_data_url, top_url, bottom_url, shoes_url, prompt):
    """Submit edit job to fal.ai queue."""
    payload = {
        "prompt": prompt,
        "image_urls": [source_data_url, top_url, bottom_url, shoes_url],
        "image_size": {"width": 1080, "height": 1920},
    }
    resp = requests.post(FAL_EDIT_URL, headers=FAL_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    log.info(f"  Submitted to fal.ai — request_id: {data.get('request_id', 'unknown')}")
    return data


def poll_fal_result(queue_response):
    """Poll fal.ai queue for completed result."""
    status_url = queue_response["status_url"]
    response_url = queue_response["response_url"]

    for attempt in range(60):  # max 5 min
        time.sleep(5)
        try:
            resp = requests.get(status_url, headers=FAL_HEADERS, timeout=15)
            status_data = resp.json()
        except Exception as e:
            log.warning(f"  Poll attempt {attempt+1} error: {e}")
            continue

        status = status_data.get("status")
        if status == "COMPLETED":
            result = requests.get(response_url, headers=FAL_HEADERS, timeout=15)
            return result.json()
        elif status in ("FAILED", "CANCELLED"):
            log.error(f"  fal.ai job failed: {status_data}")
            return None

    log.error("  fal.ai job timed out after 5 minutes")
    return None


def remake_slide(slide_path, outfit_index, output_path):
    """Remake a single slide with a NEWGARMENTS outfit."""
    outfit = OUTFITS[outfit_index % len(OUTFITS)]
    top_id, bottom_id, shoes_id = outfit
    outfit_label = f"{top_id} + {bottom_id} + {shoes_id}"

    log.info(f"  Outfit: {outfit_label}")

    source_url = image_to_data_url(slide_path)
    prompt = build_prompt(top_id, bottom_id, shoes_id)

    queue_resp = submit_to_fal(source_url, TOPS[top_id], BOTTOMS[bottom_id], SHOES[shoes_id], prompt)
    result = poll_fal_result(queue_resp)

    if not result:
        return None, outfit_label

    images = result.get("images", [])
    if not images or not images[0].get("url"):
        log.error("  No image URL in result")
        return None, outfit_label

    img_url = images[0]["url"]
    img_data = requests.get(img_url, timeout=30).content
    output_path.write_bytes(img_data)
    log.info(f"  Saved remake: {output_path.name} ({len(img_data)/1024:.1f} KB)")
    return output_path, outfit_label


# ---------------------------------------------------------------------------
# Local tracking (processed post IDs — always runs as backup)
# ---------------------------------------------------------------------------

PROCESSED_FILE = BASE_DIR / "scout" / "processed_tiktok.json"


def get_local_processed():
    if PROCESSED_FILE.exists():
        return set(json.loads(PROCESSED_FILE.read_text()))
    return set()


def save_local_processed(post_id):
    processed = get_local_processed()
    processed.add(post_id)
    PROCESSED_FILE.write_text(json.dumps(sorted(processed), indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NEWGARMENTS TikTok carousel checker & remake pipeline")
    parser.add_argument("--dry-run", action="store_true", help="List top carousels without generating")
    parser.add_argument("--max-posts", type=int, default=3, help="Max carousels to process (default: 3)")
    parser.add_argument("--max-age-days", type=int, default=7, help="Only consider posts from last N days (default: 7)")
    parser.add_argument("--results-per-page", type=int, default=20, help="Posts to fetch per account (default: 20)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("NEWGARMENTS — TikTok Carousel Checker & Remake")
    log.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info(f"Accounts: {len(TIKTOK_ACCOUNTS)}")
    log.info("=" * 60)

    if not FAL_KEY:
        log.error("FAL_KEY not set in .env")
        sys.exit(1)

    # Step 1: Get processed IDs
    processed_ids = get_local_processed()

    # Step 2: Fetch posts from all accounts via Apify
    all_posts = fetch_all_posts(TIKTOK_ACCOUNTS, results_per_page=args.results_per_page)
    if not all_posts:
        log.info("No posts fetched")
        sys.exit(0)

    # Step 3: Select top carousels
    carousels = select_top_carousels(all_posts, processed_ids,
                                      max_age_days=args.max_age_days, top_n=args.max_posts)
    if not carousels:
        log.info("No new carousels to process")
        sys.exit(0)

    if args.dry_run:
        log.info("DRY RUN — would process these carousels:")
        for i, c in enumerate(carousels):
            log.info(f"  [{i+1}] @{c['username']} — {c['play_count']:,} views — {c['num_slides']} slides — {c['post_id']}")
            log.info(f"       {c['web_url']}")
            log.info(f"       {c['text']}")
        sys.exit(0)

    # Step 4: Process each carousel
    # Output dirs — persistent so Claude Code can read the files for upload
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_base = BASE_DIR / "scout" / "output" / "tiktok_carousels" / date_str
    download_dir = output_base / "slides"
    remake_dir = output_base / "remakes"
    download_dir.mkdir(parents=True, exist_ok=True)
    remake_dir.mkdir(parents=True, exist_ok=True)

    outfit_counter = 0
    manifest_entries = []

    for ci, carousel in enumerate(carousels):
        log.info(f"\n{'='*60}")
        log.info(f"Carousel {ci+1}/{len(carousels)}: @{carousel['username']} — {carousel['play_count']:,} views")
        log.info(f"Post: {carousel['web_url']}")
        log.info(f"Slides: {carousel['num_slides']}")

        # Download slides
        slide_paths = download_slides(carousel, download_dir)
        if not slide_paths:
            log.error("No slides downloaded, skipping")
            continue

        # Slide 1 = silhouette/intro — include in manifest as-is (no edit, just upload)
        if slide_paths:
            slide1_name = f"tiktok_{carousel['username']}_{carousel['post_id']}_slide1_original.jpg"
            manifest_entries.append({
                "file_path": str(slide_paths[0]),
                "filename": slide1_name,
                "username": carousel["username"],
                "post_id": carousel["post_id"],
                "post_url": carousel["web_url"],
                "view_count": carousel["play_count"],
                "num_slides": carousel["num_slides"],
                "slide_num": 1,
                "outfit": "original (silhouette)",
                "date_processed": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
            log.info(f"\n--- Slide 1/{len(slide_paths)} — original silhouette (no edit, will upload as-is) ---")

        # Remake slides 2+ with NEWGARMENTS outfits
        for si, slide_path in enumerate(slide_paths):
            if si == 0:
                continue
            log.info(f"\n--- Slide {si+1}/{len(slide_paths)} ---")
            output_name = f"tiktok_{carousel['username']}_{carousel['post_id']}_slide{si+1}_remake.png"
            output_path = remake_dir / output_name

            result_path, outfit_label = remake_slide(slide_path, outfit_counter, output_path)
            outfit_counter += 1

            if result_path:
                manifest_entries.append({
                    "file_path": str(result_path),
                    "filename": output_name,
                    "username": carousel["username"],
                    "post_id": carousel["post_id"],
                    "post_url": carousel["web_url"],
                    "view_count": carousel["play_count"],
                    "num_slides": carousel["num_slides"],
                    "slide_num": si + 1,
                    "outfit": outfit_label,
                    "date_processed": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

            if si < len(slide_paths) - 1:
                time.sleep(2)

        # Track locally
        save_local_processed(carousel["post_id"])

        if ci < len(carousels) - 1:
            time.sleep(2)

    # Write manifest for Claude Code to read
    manifest = {
        "date": date_str,
        "carousels_processed": len(carousels),
        "remakes_completed": len(manifest_entries),
        "remake_dir": str(remake_dir),
        "entries": manifest_entries,
    }
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
    log.info(f"\n{'='*60}")
    log.info(f"Done! {len(manifest_entries)} slides remade from {len(carousels)} carousels")
    log.info(f"Manifest: {MANIFEST_FILE}")
    log.info(f"Remakes: {remake_dir}")
    log.info("=" * 60)

    # Print manifest path for Claude Code to pick up
    print(f"MANIFEST:{MANIFEST_FILE}")

    sys.exit(0 if manifest_entries else 1)


if __name__ == "__main__":
    main()
