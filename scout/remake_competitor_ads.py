"""
Remake competitor ads with NEWGARMENTS products using fal.ai Nano Banana 2 Edit.

Takes the best-performing Revivo Avenue static ads and swaps the clothing
with NEWGARMENTS products while keeping the same pose/model/background.
"""
import os
import sys
import json
import base64
import time
import requests
from pathlib import Path
from datetime import datetime

# Paths
BASE = Path(__file__).parent.parent
PRODUCT_REFS = BASE / "content-library" / "product-refs"
COMPETITOR_ADS = BASE / "scout" / "output" / "competitor_ads"
OUTPUT = BASE / "scout" / "output" / "remakes" / datetime.now().strftime("%Y-%m-%d")
OUTPUT.mkdir(parents=True, exist_ok=True)

# Load env
from dotenv import load_dotenv
load_dotenv(BASE / ".env")

FAL_KEY = os.environ.get("FAL_KEY")
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"


def image_to_data_url(path):
    """Convert image file to base64 data URL for fal.ai."""
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def poll_fal_result(queue_response, headers):
    """Poll fal.ai queue for completed result."""
    status_url = queue_response["status_url"]
    result_url = queue_response["response_url"]

    for _ in range(60):  # max 5 min
        time.sleep(5)
        status_resp = requests.get(status_url, headers=headers, timeout=15)
        status_data = status_resp.json()
        if status_data.get("status") == "COMPLETED":
            result_resp = requests.get(result_url, headers=headers, timeout=15)
            return result_resp.json()
        elif status_data.get("status") in ("FAILED", "CANCELLED"):
            print(f"  FAILED: {status_data}")
            return None
    print("  TIMED OUT")
    return None


def remake_ad(source_path, product_refs, prompt, output_name):
    """Remake a single ad using fal.ai Nano Banana 2 Edit.

    Args:
        source_path: Path to the competitor ad image
        product_refs: List of (path, description) tuples for reference products
        prompt: Edit prompt
        output_name: Output filename
    """
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    # Build image_urls: first is the source ad, rest are product references
    image_urls = [image_to_data_url(source_path)]
    for ref_path, _ in product_refs:
        image_urls.append(image_to_data_url(ref_path))

    print(f"  Sending to fal.ai ({len(image_urls)} images)...")

    payload = {
        "prompt": prompt,
        "image_urls": image_urls,
    }

    resp = requests.post(FAL_EDIT_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        result = poll_fal_result(result, headers)
        if not result:
            return None

    images = result.get("images", [])
    if not images:
        print(f"  No images in response: {json.dumps(result)[:200]}")
        return None

    img_url = images[0].get("url")
    if not img_url:
        return None

    # Download result
    img_data = requests.get(img_url, timeout=30).content
    output_path = OUTPUT / output_name
    output_path.write_bytes(img_data)
    print(f"  Saved: {output_path} ({len(img_data)/1024:.1f} KB)")
    return output_path


# Define the remakes: which competitor ad + which NEWGARMENTS products
REMAKES = [
    {
        "name": "remake_jeans_hoodie_gray",
        "source": "revivo_ad2_shirtless_jeans.jpg",
        "products": [
            ("checkered-zipper-gray.png", "gray zip-up hoodie with blue and yellow plaid flannel lining"),
            ("embroidered-striped-jeans.png", "black and white embroidered striped baggy jeans"),
        ],
        "prompt": (
            "Image 1 is the source photo. Keep the exact same person, pose, background, lighting, and camera angle. "
            "CHANGE the outfit: dress the model in the clothing shown in the reference images. "
            "Image 2 shows the top: a gray zip-up hoodie with plaid flannel lining, oversized fit. "
            "Image 3 shows the pants: black and white embroidered striped baggy jeans. "
            "Replace the current outfit with EXACTLY these items. The clothing should look natural and photorealistic on the person. "
            "Streetwear editorial photo style."
        ),
    },
    {
        "name": "remake_jeans_hoodie_green",
        "source": "revivo_ad2_shirtless_jeans.jpg",
        "products": [
            ("zip-hoodie-y2k-dark-green.png", "dark green suede-textured oversized zip hoodie"),
            ("graphic-lining-jeans.png", "graphic lining baggy jeans"),
        ],
        "prompt": (
            "Image 1 is the source photo. Keep the exact same person, pose, background, lighting, and camera angle. "
            "CHANGE the outfit: dress the model in the clothing shown in the reference images. "
            "Image 2 shows the top: a dark green suede-textured oversized zip hoodie with graffiti embroidery. "
            "Image 3 shows the pants: graphic lining baggy jeans with artistic details. "
            "Replace the current outfit with EXACTLY these items. The clothing should look natural and photorealistic. "
            "Streetwear editorial photo style."
        ),
    },
    {
        "name": "remake_jacket_hoodie_black",
        "source": "revivo_ad3_double_dark.jpg",
        "products": [
            ("zip-hoodie-y2k-black.png", "black suede-textured oversized zip hoodie"),
        ],
        "prompt": (
            "Image 1 is the source photo. Keep the exact same person, pose, background, lighting, and camera angle. "
            "CHANGE the jacket/outerwear: replace it with the black oversized zip hoodie shown in Image 2. "
            "The hoodie has a suede texture and graffiti-style embroidered text on the chest. "
            "Keep the same styling mood but with this hoodie. Photorealistic, streetwear editorial."
        ),
    },
    {
        "name": "remake_jacket_vanity_pink",
        "source": "revivo_ad5_vanity_jacket.jpg",
        "products": [
            ("zip-hoodie-y2k-pink.png", "pink suede-textured oversized zip hoodie"),
        ],
        "prompt": (
            "Image 1 is the source photo. Keep the exact same person, pose, background, lighting, and camera angle. "
            "CHANGE the jacket: replace it with the pink oversized zip hoodie shown in Image 2. "
            "The hoodie has a suede texture and graffiti-style embroidered text on the chest, silver zipper. "
            "Keep the same styling mood but with this hoodie. Photorealistic, streetwear editorial."
        ),
    },
    {
        "name": "remake_model_green_outfit",
        "source": "revivo_ad1_model_green.jpg",
        "products": [
            ("checkered-zipper-red.png", "red and black checkered plaid zip-up hoodie"),
            ("embroidered-striped-jeans.png", "black and white embroidered striped baggy jeans"),
        ],
        "prompt": (
            "Image 1 is the source photo. Keep the exact same person, pose, background, lighting, and camera angle. "
            "CHANGE the outfit: dress the model in the clothing shown in the reference images. "
            "Image 2 shows the top: a red and black checkered plaid zip-up hoodie with flannel lining, oversized fit. "
            "Image 3 shows the pants: black and white embroidered striped baggy jeans. "
            "Replace the current outfit with EXACTLY these items. Photorealistic, streetwear editorial."
        ),
    },
]


def main():
    if not FAL_KEY:
        print("ERROR: FAL_KEY not set in environment or .env")
        sys.exit(1)

    print("=" * 60)
    print("NEWGARMENTS — Competitor Ad Remake Pipeline")
    print(f"Source: Revivo Avenue (Meta Ad Library)")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Output: {OUTPUT}")
    print("=" * 60)

    results = []
    for i, remake in enumerate(REMAKES):
        print(f"\n--- Remake {i+1}/{len(REMAKES)}: {remake['name']} ---")
        print(f"  Source: {remake['source']}")

        source_path = COMPETITOR_ADS / remake["source"]
        if not source_path.exists():
            print(f"  ERROR: Source not found: {source_path}")
            continue

        product_refs = []
        for ref_file, ref_desc in remake["products"]:
            ref_path = PRODUCT_REFS / ref_file
            if not ref_path.exists():
                print(f"  WARNING: Product ref not found: {ref_path}")
                continue
            product_refs.append((str(ref_path), ref_desc))

        if not product_refs:
            print("  ERROR: No product references found")
            continue

        output_name = f"{remake['name']}.png"
        result = remake_ad(str(source_path), product_refs, remake["prompt"], output_name)

        if result:
            results.append({
                "name": remake["name"],
                "source": remake["source"],
                "output": str(result),
                "products": [r[0] for _, r in enumerate(remake["products"])],
            })

        # Small delay between API calls
        if i < len(REMAKES) - 1:
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"Done! {len(results)}/{len(REMAKES)} remakes generated")
    print(f"Output: {OUTPUT}")
    print("=" * 60)

    # Save manifest
    manifest = OUTPUT / "manifest.json"
    manifest.write_text(json.dumps(results, indent=2))
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
