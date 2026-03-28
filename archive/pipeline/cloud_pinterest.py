"""
Cloud Pinterest Remake Pipeline — runs in GitHub Actions, no local auth needed.

Reads processed pins from public Google Sheet CSV.
Writes new remakes via Google Apps Script POST (uploads image to Drive + adds row).
Fetches Pinterest pins via Playwright (headless browser scrolls board).
Remakes with fal.ai Nano Banana 2 edit endpoint.

Usage:
    python pipeline/cloud_pinterest.py              # normal run
    python pipeline/cloud_pinterest.py --dry-run    # list new pins without generating
    python pipeline/cloud_pinterest.py --max 5      # limit to 5 pins per run
"""
import os
import re
import sys
import csv
import io
import time
import logging
import argparse
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


def _require(key: str) -> str:
    """Raise at startup if a required env var is missing. Never silent."""
    val = os.getenv(key)
    if not val:
        raise RuntimeError(
            f"Required env var {key!r} is not set. "
            "Add it to .env (local) or GitHub Actions secrets (CI)."
        )
    return val


FAL_KEY = _require("FAL_KEY")
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
FAL_HEADERS = {
    "Authorization": f"Key {FAL_KEY}",
    "Content-Type": "application/json",
}

# IDs
BOARD_ID = "1003176954437607618"
SHEET_ID = "1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Blad1"

# Apps Script URL — deploy the pinterest_apps_script.gs and paste URL here
APPS_SCRIPT_URL = _require("PINTEREST_APPS_SCRIPT_URL")

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

# 6 outfit combos (cycling)
OUTFITS = [
    ("checkered-zipper-gray", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-dark-green", "graphic-lining-jeans", "ocean-stars-sneaker"),
    ("checkered-zipper-black", "embroidered-striped-jeans", "ocean-stars-sneaker"),
    ("zip-hoodie-y2k-pink", "graphic-lining-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-black", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("checkered-zipper-red", "graphic-lining-jeans", "ocean-stars-sneaker"),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("cloud_pinterest")


# ---------------------------------------------------------------------------
# Google Sheet — read via public CSV
# ---------------------------------------------------------------------------

def get_processed_pin_ids():
    """Read all pin_id AND image URL hashes from Postgres (via PROCESSED_PINS_FILE) and Sheet CSV.
    Returns (set of pin_ids, set of image hashes) for dual dedup.
    Postgres is the primary source (D-07); Sheet provides fallback for IDs not yet migrated."""
    pin_ids = set()
    image_hashes = set()

    # Primary: read Postgres-sourced pin IDs from file written by workflow step
    postgres_file = os.getenv("PROCESSED_PINS_FILE")
    if postgres_file and os.path.exists(postgres_file):
        with open(postgres_file) as f:
            for line in f:
                pid = line.strip()
                if pid:
                    pin_ids.add(pid)
        log.info(f"Postgres: {len(pin_ids)} pre-loaded pin IDs from content API")

    # Fallback: also read from Google Sheet CSV (catches IDs not yet in Postgres)
    try:
        resp = requests.get(SHEET_CSV_URL, timeout=15)
        resp.raise_for_status()
        reader = csv.reader(io.StringIO(resp.text))
        rows = list(reader)
        if len(rows) < 2:
            return pin_ids, image_hashes
        # Find columns by header name
        headers = [h.strip().lower() for h in rows[0]]
        pin_col = 6  # default: column G
        url_col = 5  # default: column F (pin_url)
        for i, h in enumerate(headers):
            if h == "pin_id":
                pin_col = i
            elif h == "pin_url":
                url_col = i
        sheet_pin_count = 0
        for row in rows[1:]:
            if len(row) > pin_col and row[pin_col].strip():
                pin_ids.add(row[pin_col].strip())
                sheet_pin_count += 1
            if len(row) > url_col and row[url_col].strip():
                img_hash = _extract_image_hash(row[url_col].strip())
                if img_hash:
                    image_hashes.add(img_hash)
        log.info(f"Sheet: {sheet_pin_count} pin IDs, {len(image_hashes)} unique image hashes (total dedup set: {len(pin_ids)})")
        return pin_ids, image_hashes
    except Exception as e:
        log.error(f"Failed to read sheet: {e}")
        return pin_ids, image_hashes


def _extract_image_hash(url):
    """Extract the unique image filename hash from a pinimg URL.
    e.g. 'https://i.pinimg.com/originals/ff/2a/23/ff2a2327760cc855125dbca3a2977490.jpg' → 'ff2a2327760cc855125dbca3a2977490'
    """
    match = re.search(r'/([a-f0-9]{32})\.\w+$', url)
    return match.group(1) if match else None


def post_remake_to_sheet(pin_id, pin_url, outfit_combo, status, image_url, filename):
    """POST remake data to Apps Script which uploads to Drive + adds row."""
    if not APPS_SCRIPT_URL:
        log.error("PINTEREST_APPS_SCRIPT_URL not set — cannot write to sheet")
        return None
    try:
        data = {
            "action": "add_remake",
            "pin_id": pin_id,
            "pin_url": pin_url,
            "outfit_combo": outfit_combo,
            "status": status,
            "image_url": image_url or "",
            "filename": filename,
        }
        resp = requests.post(APPS_SCRIPT_URL, data=data, timeout=60, allow_redirects=True)
        if resp.status_code == 200:
            result = resp.json()
            log.info(f"Sheet+Drive: {pin_id} → {result.get('drive_file_id', 'no_id')}")
            return result
        else:
            log.error(f"Apps Script returned {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        log.error(f"Apps Script POST failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Pinterest — Playwright headless browser
# ---------------------------------------------------------------------------

BOARD_URL = "https://www.pinterest.com/MyGarmentsEU/ads-newgarments/"

def fetch_board_pins():
    """Fetch pins from Pinterest board using Playwright (scrolls to load all pins).
    Stops before 'More ideas' section to avoid non-board pins."""
    from playwright.sync_api import sync_playwright

    pins = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page.goto(BOARD_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Get board pin count to avoid "More ideas" section
        board_pin_count = page.evaluate("""() => {
            const match = document.body.innerText.match(/(\\d+)\\s*Pins/i);
            return match ? parseInt(match[1]) : 50;
        }""")
        log.info(f"Board says {board_pin_count} pins")

        prev_count = 0
        stale_rounds = 0

        for scroll_round in range(15):
            # Check for "More ideas" / "More like this" section — hard stop
            has_more_ideas = page.evaluate("""() => {
                const text = document.body.innerText;
                return /More ideas|More like this|Meer idee/i.test(text);
            }""")
            if has_more_ideas and len(pins) > 0:
                log.info(f"Detected 'More ideas' section after {len(pins)} pins — stopping")
                break

            # Collect visible pins each scroll
            visible = page.evaluate("""() => {
                const results = [];
                const links = document.querySelectorAll('a[href*="/pin/"]');
                for (const el of links) {
                    const href = el.getAttribute("href") || "";
                    const match = href.match(/\\/pin\\/(\\d+)/);
                    if (!match) continue;
                    const img = el.querySelector("img");
                    if (!img) continue;
                    const src = img.getAttribute("src") || "";
                    if (!src.includes("pinimg.com")) continue;
                    const imageUrl = src.replace(/\\/(236x|474x|564x|736x)\\//, "/originals/");
                    results.push({pinId: match[1], imageUrl});
                }
                return results;
            }""")

            for v in visible:
                if v["pinId"] not in seen and len(pins) < board_pin_count:
                    seen.add(v["pinId"])
                    pins.append({"pin_id": v["pinId"], "image_url": v["imageUrl"]})

            # Stop once we've collected the board's pin count
            if len(pins) >= board_pin_count:
                log.info(f"Reached board pin count ({board_pin_count}), stopping scroll")
                break

            # Stale scroll detection — no new pins for 2 rounds = stop
            if len(pins) == prev_count:
                stale_rounds += 1
                if stale_rounds >= 2:
                    log.info(f"No new pins for {stale_rounds} scroll rounds — stopping at {len(pins)} pins")
                    break
            else:
                stale_rounds = 0
            prev_count = len(pins)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        browser.close()

    log.info(f"Playwright: fetched {len(pins)} pins from board")
    return pins


# ---------------------------------------------------------------------------
# fal.ai
# ---------------------------------------------------------------------------

def build_prompt(top_name, bottom_name, shoes_name):
    return (
        f"Image 1 is the source photo. Keep the exact same person, face, skin tone, pose, background, and lighting. "
        f"ONLY change the clothing. "
        f"Image 2 is the top: dress the person in this {top_name.replace('-', ' ')} zip hoodie, "
        f"wearing a plain white t-shirt underneath the zip hoodie, visible at the chest/neckline. "
        f"Image 3 is the bottom: dress the person in these {bottom_name.replace('-', ' ')}. "
        f"Image 4 is the footwear: put these {shoes_name.replace('-', ' ')} on the person's feet. "
        f"The overall outfit should look cohesive and natural."
    )


def submit_to_fal(pin_image_url, top_url, bottom_url, shoes_url, prompt):
    payload = {
        "prompt": prompt,
        "image_urls": [pin_image_url, top_url, bottom_url, shoes_url],
        "image_size": {"width": 1080, "height": 1920},
    }
    resp = requests.post(FAL_EDIT_URL, headers=FAL_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    log.info(f"Submitted to fal.ai — request_id: {data.get('request_id', 'unknown')}")
    return data


def poll_fal_result(queue_response):
    status_url = queue_response["status_url"]
    response_url = queue_response["response_url"]

    for attempt in range(60):
        time.sleep(5)
        try:
            resp = requests.get(status_url, headers=FAL_HEADERS, timeout=15)
            status_data = resp.json()
        except Exception as e:
            log.warning(f"Poll attempt {attempt+1} error: {e}")
            continue

        status = status_data.get("status")
        if status == "COMPLETED":
            result = requests.get(response_url, headers=FAL_HEADERS, timeout=15)
            return result.json()
        elif status in ("FAILED", "CANCELLED"):
            log.error(f"fal.ai job failed: {status_data}")
            return None

    log.error("fal.ai job timed out after 5 minutes")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NEWGARMENTS cloud Pinterest remake pipeline")
    parser.add_argument("--dry-run", action="store_true", help="List new pins without generating")
    parser.add_argument("--max", type=int, default=2, help="Max pins to process per run (default: 2)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("NEWGARMENTS Cloud Pinterest Remake Pipeline")
    log.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    # Step 1: Read processed pins from Sheet (public CSV)
    processed_ids, processed_hashes = get_processed_pin_ids()

    # Step 2: Fetch pins from board
    all_pins = fetch_board_pins()
    log.info(f"Found {len(all_pins)} total pins on board")

    if not all_pins:
        log.info("No pins found on board")
        sys.exit(0)

    # Step 3: Filter new pins — dedup by BOTH pin_id AND image URL hash
    new_pins = []
    for p in all_pins:
        if p["pin_id"] in processed_ids:
            continue
        img_hash = _extract_image_hash(p["image_url"])
        if img_hash and img_hash in processed_hashes:
            log.info(f"Skipping pin {p['pin_id']} — same image already remade (hash: {img_hash[:12]}…)")
            continue
        new_pins.append(p)
    log.info(f"{len(new_pins)} new pins to process (after pin_id + image dedup)")

    if not new_pins:
        log.info("All pins already processed!")
        sys.exit(0)

    if args.dry_run:
        log.info("DRY RUN — would process these pins:")
        for i, pin in enumerate(new_pins[:args.max]):
            outfit = OUTFITS[i % len(OUTFITS)]
            log.info(f"  [{i+1}] pin_id={pin['pin_id']} outfit={' + '.join(outfit)}")
        sys.exit(0)

    # Step 4: Process each new pin
    new_pins = new_pins[:args.max]
    success_count = 0

    for i, pin in enumerate(new_pins):
        outfit = OUTFITS[i % len(OUTFITS)]
        top_id, bottom_id, shoes_id = outfit
        outfit_label = f"{top_id} + {bottom_id} + {shoes_id}"

        log.info(f"\n--- [{i+1}/{len(new_pins)}] Pin {pin['pin_id']} ---")
        log.info(f"Outfit: {outfit_label}")

        try:
            prompt = build_prompt(top_id, bottom_id, shoes_id)
            queue_resp = submit_to_fal(
                pin["image_url"],
                TOPS[top_id],
                BOTTOMS[bottom_id],
                SHOES[shoes_id],
                prompt,
            )

            result = poll_fal_result(queue_resp)
            if not result:
                post_remake_to_sheet(pin["pin_id"], pin["image_url"], outfit_label, "failed", "", "")
                continue

            images = result.get("images", [])
            if not images or not images[0].get("url"):
                log.error("No image URL in result")
                post_remake_to_sheet(pin["pin_id"], pin["image_url"], outfit_label, "failed", "", "")
                continue

            img_url = images[0]["url"]
            filename = f"remake_{pin['pin_id']}_{top_id}.png"
            log.info(f"Remake ready: {filename}")

            # POST to Apps Script — it uploads to Drive + adds row
            post_remake_to_sheet(pin["pin_id"], pin["image_url"], outfit_label, "done", img_url, filename)
            success_count += 1

        except Exception as e:
            log.error(f"Error processing pin {pin['pin_id']}: {e}")
            try:
                post_remake_to_sheet(pin["pin_id"], pin["image_url"], outfit_label, "failed", "", "")
            except Exception:
                pass

        time.sleep(1)

    log.info(f"\n{'=' * 60}")
    log.info(f"Done! {success_count}/{len(new_pins)} remakes generated")
    log.info("=" * 60)

    sys.exit(0 if success_count > 0 else 1)


if __name__ == "__main__":
    main()
