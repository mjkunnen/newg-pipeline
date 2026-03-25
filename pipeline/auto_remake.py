"""
Auto-remake pipeline:
1. Scrape Pinterest board for pins
2. Check Google Sheet for already-processed pins
3. Download new pin images
4. Generate remakes with NEWGARMENTS outfits via fal.ai
5. Upload to Google Drive
6. Update sheet with status

Usage: python auto_remake.py <pinterest_board_url>
"""
import os
import sys
import json
import base64
import time
import random
import requests
from pathlib import Path
from datetime import datetime

# Setup paths
BASE = Path(__file__).parent.parent
PIPELINE = Path(__file__).parent
PRODUCT_REFS = BASE / "content-library" / "product-refs"
OUTPUT = PIPELINE / "output" / datetime.now().strftime("%Y-%m-%d") / "remakes"
OUTPUT.mkdir(parents=True, exist_ok=True)

# Config
SHEET_ID = "1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY"
DRIVE_FOLDER = "1BsWTXQT8lQDwUjqo4Suelo3Gy7lKQro5"
FAL_KEY = os.environ.get("FAL_KEY")
if not FAL_KEY:
    raise RuntimeError("FAL_KEY not set – add it to .env")

# Products to cycle through for remakes
PRODUCTS = [
    {"file": "checkered-zipper-gray.png", "desc": "gray zip-up hoodie with blue and yellow plaid flannel lining, silver zipper, oversized fit"},
    {"file": "zip-hoodie-y2k-dark-green.png", "desc": "dark green suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper"},
    {"file": "checkered-zipper-black.png", "desc": "black zip-up hoodie with yellow and white plaid flannel lining, silver zipper, oversized cropped fit"},
    {"file": "zip-hoodie-y2k-black.png", "desc": "black suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper"},
    {"file": "zip-hoodie-y2k-pink.png", "desc": "pink suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper"},
    {"file": "checkered-zipper-red.png", "desc": "red and black checkered plaid zip-up hoodie with flannel lining, silver zipper, oversized fit"},
]


def image_to_data_url(path):
    """Convert image file to data URL for fal.ai."""
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    mime = {"png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def scrape_pinterest_board(board_url):
    """Extract pin image URLs from a Pinterest board using requests + API."""
    # Try Pinterest RSS/API approach first
    print(f"\nScraping board: {board_url}")

    # Extract board path from URL
    # e.g., https://www.pinterest.com/username/boardname/
    parts = board_url.rstrip("/").split("/")
    username = parts[-2] if len(parts) >= 2 else parts[-1]
    boardname = parts[-1]

    # Try fetching board page and extracting pin data
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    pins = []
    try:
        r = requests.get(board_url, headers=headers, timeout=15)
        # Extract pinimg URLs from page source
        import re
        pin_urls = re.findall(r'https://i\.pinimg\.com/(?:originals|736x)/[a-f0-9/]+\.(?:jpg|png|webp)', r.text)
        # Deduplicate and filter
        seen = set()
        for url in pin_urls:
            # Normalize to 736x for consistency
            url_norm = url.replace("/originals/", "/736x/")
            if url_norm not in seen:
                seen.add(url_norm)
                # Extract a pseudo pin_id from the image hash
                hash_part = url_norm.split("/736x/")[1].replace("/", "").replace(".jpg", "").replace(".png", "")
                pins.append({
                    "pin_id": hash_part[:20],
                    "image_url": url_norm,
                    "description": f"Pin from {boardname}",
                })
        print(f"  Found {len(pins)} pins via page scrape")
    except Exception as e:
        print(f"  Error scraping: {e}")

    return pins


def get_processed_pins():
    """Get list of already-processed pin IDs from Google Sheet."""
    # This will be called via Zapier MCP in the Claude Code context
    # For standalone use, we track locally
    processed_file = PIPELINE / "processed_pins.json"
    if processed_file.exists():
        return json.loads(processed_file.read_text())
    return []


def save_processed_pin(pin_id):
    """Mark a pin as processed."""
    processed_file = PIPELINE / "processed_pins.json"
    processed = get_processed_pins()
    if pin_id not in processed:
        processed.append(pin_id)
        processed_file.write_text(json.dumps(processed, indent=2))


def download_pin_image(pin, output_dir):
    """Download a pin's image."""
    url = pin["image_url"]
    # Try originals first for higher quality
    url_hq = url.replace("/736x/", "/originals/")

    try:
        r = requests.get(url_hq, timeout=15)
        if r.status_code != 200 or len(r.content) < 5000:
            r = requests.get(url, timeout=15)

        ext = "jpg"
        filepath = output_dir / f"{pin['pin_id']}.{ext}"
        filepath.write_bytes(r.content)
        print(f"  Downloaded: {filepath.name} ({len(r.content)} bytes)")
        return filepath
    except Exception as e:
        print(f"  Download error: {e}")
        return None


def generate_remake(source_path, product, output_path):
    """Generate a remake using fal.ai Nano Banana 2."""
    import fal_client

    os.environ["FAL_KEY"] = FAL_KEY

    source_url = image_to_data_url(source_path)
    product_path = PRODUCT_REFS / product["file"]
    product_url = image_to_data_url(product_path)

    prompt = f"""The person is wearing a {product['desc']}.
Keep the exact same person, pose, background, mirror, phone, and angle.
Only change the top/jacket/hoodie to match the reference product image.
Photorealistic, natural lighting, streetwear style mirror selfie."""

    try:
        result = fal_client.subscribe(
            "fal-ai/nano-banana-2",
            arguments={
                "prompt": prompt,
                "image_url": source_url,
                "reference_image_url": product_url,
                "seed": random.randint(1, 9999),
                "num_inference_steps": 35,
            },
        )

        if result and "images" in result and len(result["images"]) > 0:
            img_url = result["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            output_path.write_bytes(img_data)

            # If multi-panel, crop to right panel
            from PIL import Image
            img = Image.open(output_path)
            w, h = img.size
            if w > h * 1.2:
                panels = round(w / h)
                panel_w = w // panels
                crop = img.crop((w - panel_w, 0, w, h))
                crop.save(output_path, quality=95)

            print(f"  Remake generated: {output_path.name}")
            return output_path
        else:
            print(f"  No images in result")
            return None
    except Exception as e:
        print(f"  Generation error: {e}")
        return None


def upload_to_temp(filepath):
    """Upload file to 0x0.st for Zapier access."""
    try:
        with open(filepath, "rb") as f:
            r = requests.post("https://0x0.st", files={"file": f}, timeout=30)
        if r.status_code == 200:
            return r.text.strip()
    except:
        pass
    return None


def process_board(board_url, max_pins=10):
    """Main pipeline: scrape → filter → download → remake → upload."""
    print("=" * 60)
    print("NEWGARMENTS Auto-Remake Pipeline")
    print(f"Board: {board_url}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Step 1: Scrape pins from board
    pins = scrape_pinterest_board(board_url)
    if not pins:
        print("No pins found!")
        return []

    # Step 2: Filter out already-processed pins
    processed = get_processed_pins()
    new_pins = [p for p in pins if p["pin_id"] not in processed]
    print(f"\n{len(new_pins)} new pins to process (out of {len(pins)} total)")

    if not new_pins:
        print("All pins already processed!")
        return []

    # Limit
    new_pins = new_pins[:max_pins]

    # Step 3: Download + Remake each pin
    results = []
    source_dir = OUTPUT / "sources"
    remake_dir = OUTPUT / "generated"
    source_dir.mkdir(parents=True, exist_ok=True)
    remake_dir.mkdir(parents=True, exist_ok=True)

    for i, pin in enumerate(new_pins):
        print(f"\n--- Pin {i+1}/{len(new_pins)}: {pin['pin_id'][:15]}... ---")

        # Download source
        source_path = download_pin_image(pin, source_dir)
        if not source_path:
            continue

        # Pick a product (cycle through collection)
        product = PRODUCTS[i % len(PRODUCTS)]
        print(f"  Outfit: {product['file']}")

        # Generate remake
        remake_path = remake_dir / f"remake_{pin['pin_id'][:15]}_{product['file'].replace('.png','')}.png"
        result = generate_remake(source_path, product, remake_path)

        if result:
            results.append({
                "pin_id": pin["pin_id"],
                "source": str(source_path),
                "remake": str(remake_path),
                "product": product["file"],
            })
            save_processed_pin(pin["pin_id"])

        time.sleep(1)

    print(f"\n{'=' * 60}")
    print(f"Done! {len(results)} remakes generated")
    print(f"Output: {OUTPUT}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_remake.py <pinterest_board_url>")
        print("Example: python auto_remake.py https://www.pinterest.com/username/boardname/")
        sys.exit(1)

    board_url = sys.argv[1]
    results = process_board(board_url)

    if results:
        # Save manifest
        manifest_path = OUTPUT / "manifest.json"
        manifest_path.write_text(json.dumps(results, indent=2))
        print(f"\nManifest saved: {manifest_path}")
