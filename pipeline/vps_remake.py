"""
VPS Auto-Remake Pipeline — standalone script for daily cron on Hetzner VPS.

Fetches new Pinterest pins, checks Google Sheet for already-processed ones,
remakes with NEWGARMENTS outfits via fal.ai edit endpoint, uploads to Drive,
and logs results in the Sheet.

Usage:
    python pipeline/vps_remake.py              # normal run
    python pipeline/vps_remake.py --dry-run    # list new pins without generating
    python pipeline/vps_remake.py --max 5      # limit to 5 pins per run
"""
import os
import re
import sys
import json
import time
import logging
import argparse
import tempfile
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Load .env from repo root
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

FAL_KEY = os.getenv("FAL_KEY")
PINTEREST_TOKEN = os.getenv("PINTEREST_ACCESS_TOKEN")
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
FAL_HEADERS = {
    "Authorization": f"Key {FAL_KEY}",
    "Content-Type": "application/json",
}

# IDs
BOARD_ID = "1003176954437607618"
SHEET_ID = "1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY"
DRIVE_FOLDER_ID = "1crvIaZtrMmuXslneAkX_q4rgcb1J5-FU"
SERVICE_ACCOUNT_FILE = BASE_DIR / "credentials" / "service-account.json"

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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "logs" / "daily-remake.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("vps_remake")


# ---------------------------------------------------------------------------
# Google auth
# ---------------------------------------------------------------------------

def get_google_credentials():
    from google.oauth2.service_account import Credentials
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    return Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=scopes)


# ---------------------------------------------------------------------------
# Pinterest
# ---------------------------------------------------------------------------

def fetch_board_pins_api(board_id):
    """Fetch pins via Pinterest API v5 (requires PINTEREST_ACCESS_TOKEN)."""
    if not PINTEREST_TOKEN:
        return None
    url = f"https://api.pinterest.com/v5/boards/{board_id}/pins"
    headers = {"Authorization": f"Bearer {PINTEREST_TOKEN}"}
    pins = []
    bookmark = None

    while True:
        params = {"page_size": 25}
        if bookmark:
            params["bookmark"] = bookmark
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            log.warning(f"Pinterest API returned {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        for item in data.get("items", []):
            image_url = None
            media = item.get("media", {})
            images = media.get("images", {})
            for size in ("1200x", "originals", "600x"):
                if size in images:
                    image_url = images[size].get("url")
                    break
            if not image_url:
                continue
            pins.append({
                "pin_id": item["id"],
                "image_url": image_url,
            })
        bookmark = data.get("bookmark")
        if not bookmark:
            break

    log.info(f"Pinterest API: fetched {len(pins)} pins")
    return pins


def fetch_board_pins_scrape(board_id):
    """Fallback: scrape Pinterest board page for pin image URLs."""
    board_url = f"https://www.pinterest.com/pin/{board_id}/"
    # Try the board feed URL
    feed_url = f"https://www.pinterest.com/resource/BoardFeedResource/get/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # Simple approach: fetch board page and extract pinimg URLs
    try:
        r = requests.get(f"https://www.pinterest.com/newgarmentsclo/inspo-board/", headers=headers, timeout=15)
        urls = re.findall(r'https://i\.pinimg\.com/(?:originals|1200x|736x)/[a-f0-9/]+\.(?:jpg|png|webp)', r.text)
        seen = set()
        pins = []
        for url in urls:
            url_norm = re.sub(r'/(?:originals|736x)/', '/1200x/', url)
            if url_norm in seen:
                continue
            seen.add(url_norm)
            hash_part = url_norm.split("/1200x/")[1].replace("/", "").split(".")[0]
            pins.append({"pin_id": hash_part[:20], "image_url": url_norm})
        log.info(f"Scrape: found {len(pins)} pins")
        return pins
    except Exception as e:
        log.error(f"Scrape failed: {e}")
        return []


def fetch_board_pins():
    """Fetch pins — try API first, fall back to scrape."""
    pins = fetch_board_pins_api(BOARD_ID)
    if pins is not None:
        return pins
    log.info("No Pinterest API token, falling back to scrape")
    return fetch_board_pins_scrape(BOARD_ID)


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

def get_processed_pin_ids(creds):
    """Read all pin_id values from column G of the tracking sheet."""
    import gspread
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).sheet1
    # pin_id is in column G (per Zapier reverse mapping)
    col_values = sheet.col_values(7)  # column G = 7
    pin_ids = set(v.strip() for v in col_values if v.strip())
    log.info(f"Sheet: {len(pin_ids)} processed pin IDs found")
    return pin_ids


def append_to_sheet(creds, pin_id, pin_url, outfit_combo, status, drive_file_id="", drive_filename=""):
    """Append a row to the tracking sheet.

    Columns (A-G, but Zapier maps in reverse):
    G=pin_id, F=pin_url, E=outfit_combo, D=status, C=date_processed, B=drive_file_id, A=drive_filename
    """
    import gspread
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).sheet1
    row = [
        drive_filename,                             # A
        drive_file_id,                              # B
        datetime.now().strftime("%Y-%m-%d %H:%M"),  # C
        status,                                     # D
        outfit_combo,                               # E
        pin_url,                                    # F
        pin_id,                                     # G
    ]
    sheet.append_row(row, value_input_option="RAW")
    log.info(f"Sheet: appended row for pin {pin_id} — {status}")


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
    """Submit edit job to fal.ai queue. Returns full queue response."""
    payload = {
        "prompt": prompt,
        "image_urls": [pin_image_url, top_url, bottom_url, shoes_url],
    }
    resp = requests.post(FAL_EDIT_URL, headers=FAL_HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    log.info(f"Submitted to fal.ai — request_id: {data.get('request_id', 'unknown')}")
    return data


def poll_fal_result(queue_response):
    """Poll using status_url and response_url from queue response.

    CRITICAL: Uses the URLs exactly as returned by the queue endpoint.
    Pattern from pipeline/generate_image.py:_poll_fal_result.
    """
    status_url = queue_response["status_url"]
    response_url = queue_response["response_url"]

    for attempt in range(60):  # max 5 minutes
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
# Google Drive
# ---------------------------------------------------------------------------

def upload_to_drive(creds, local_path, filename, folder_id):
    """Upload file to Google Drive folder. Returns file ID."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    service = build("drive", "v3", credentials=creds)

    # Create today's subfolder if needed
    today = datetime.now().strftime("%Y-%m-%d")
    query = f"name='{today}' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces="drive", fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        subfolder_id = files[0]["id"]
    else:
        meta = {
            "name": today,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [folder_id],
        }
        folder = service.files().create(body=meta, fields="id").execute()
        subfolder_id = folder["id"]
        log.info(f"Drive: created subfolder {today}")

    file_meta = {"name": filename, "parents": [subfolder_id]}
    media = MediaFileUpload(str(local_path), mimetype="image/png")
    uploaded = service.files().create(body=file_meta, media_body=media, fields="id").execute()
    file_id = uploaded["id"]
    log.info(f"Drive: uploaded {filename} -> {file_id}")
    return file_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NEWGARMENTS daily Pinterest remake pipeline")
    parser.add_argument("--dry-run", action="store_true", help="List new pins without generating")
    parser.add_argument("--max", type=int, default=10, help="Max pins to process per run (default: 10)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("NEWGARMENTS VPS Auto-Remake Pipeline")
    log.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log.info("=" * 60)

    # Validate
    if not FAL_KEY:
        log.error("FAL_KEY not set in .env")
        sys.exit(1)
    if not SERVICE_ACCOUNT_FILE.exists():
        log.error(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        sys.exit(1)

    # Step 1: Google auth
    creds = get_google_credentials()

    # Step 2: Fetch pins from board
    all_pins = fetch_board_pins()
    log.info(f"Found {len(all_pins)} total pins on board")

    if not all_pins:
        log.info("No pins found on board")
        sys.exit(0)

    # Step 3: Check what's already done
    processed = get_processed_pin_ids(creds)

    # Step 4: Filter new pins
    new_pins = [p for p in all_pins if p["pin_id"] not in processed]
    log.info(f"{len(new_pins)} new pins to process")

    if not new_pins:
        log.info("All pins already processed!")
        sys.exit(0)

    if args.dry_run:
        log.info("DRY RUN — would process these pins:")
        for i, pin in enumerate(new_pins[:args.max]):
            outfit = OUTFITS[i % len(OUTFITS)]
            log.info(f"  [{i+1}] pin_id={pin['pin_id']} outfit={' + '.join(outfit)}")
        sys.exit(0)

    # Step 5: Process each new pin
    new_pins = new_pins[:args.max]
    success_count = 0
    tmpdir = Path(tempfile.mkdtemp(prefix="newg_remake_"))

    for i, pin in enumerate(new_pins):
        outfit = OUTFITS[i % len(OUTFITS)]
        top_id, bottom_id, shoes_id = outfit
        outfit_label = f"{top_id} + {bottom_id} + {shoes_id}"

        log.info(f"\n--- [{i+1}/{len(new_pins)}] Pin {pin['pin_id']} ---")
        log.info(f"Outfit: {outfit_label}")

        try:
            # Build prompt and submit
            prompt = build_prompt(top_id, bottom_id, shoes_id)
            queue_resp = submit_to_fal(
                pin["image_url"],
                TOPS[top_id],
                BOTTOMS[bottom_id],
                SHOES[shoes_id],
                prompt,
            )

            # Poll for result
            result = poll_fal_result(queue_resp)
            if not result:
                append_to_sheet(creds, pin["pin_id"], pin["image_url"], outfit_label, "failed")
                continue

            images = result.get("images", [])
            if not images or not images[0].get("url"):
                log.error("No image URL in result")
                append_to_sheet(creds, pin["pin_id"], pin["image_url"], outfit_label, "failed")
                continue

            # Download result
            img_url = images[0]["url"]
            filename = f"remake_{pin['pin_id']}_{top_id}.png"
            local_path = tmpdir / filename
            img_data = requests.get(img_url, timeout=30).content
            local_path.write_bytes(img_data)
            log.info(f"Downloaded remake: {filename} ({len(img_data)} bytes)")

            # Upload to Drive
            drive_file_id = upload_to_drive(creds, local_path, filename, DRIVE_FOLDER_ID)

            # Update Sheet
            append_to_sheet(creds, pin["pin_id"], pin["image_url"], outfit_label, "done", drive_file_id, filename)
            success_count += 1

        except Exception as e:
            log.error(f"Error processing pin {pin['pin_id']}: {e}")
            try:
                append_to_sheet(creds, pin["pin_id"], pin["image_url"], outfit_label, "failed")
            except Exception:
                pass

        # Small delay between jobs
        time.sleep(1)

    log.info(f"\n{'=' * 60}")
    log.info(f"Done! {success_count}/{len(new_pins)} remakes generated")
    log.info("=" * 60)

    sys.exit(0 if success_count > 0 else 1)


if __name__ == "__main__":
    main()
