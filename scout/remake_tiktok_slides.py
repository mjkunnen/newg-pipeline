"""Remake TikTok slide post outfit photos with NEWGARMENTS products."""
import os
import sys
import json
import base64
import time
import requests
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent
PRODUCT_REFS = BASE / "content-library" / "product-refs"
SLIDES_DIR = BASE / "scout" / "output" / "fiveleafs_slides"
OUTPUT = BASE / "scout" / "output" / "tiktok_remakes" / datetime.now().strftime("%Y-%m-%d")
OUTPUT.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(BASE / ".env")

FAL_KEY = os.environ.get("FAL_KEY")
FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"


def image_to_data_url(path):
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    mime = {"png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    if ext == ".png": mime = "image/png"
    elif ext == ".webp": mime = "image/webp"
    else: mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def poll_fal_result(queue_response, headers):
    status_url = queue_response["status_url"]
    result_url = queue_response["response_url"]
    for _ in range(60):
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


def remake_slide(source_path, product_refs, prompt, output_name):
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }
    image_urls = [image_to_data_url(source_path)]
    for ref_path in product_refs:
        image_urls.append(image_to_data_url(ref_path))

    print(f"  Sending to fal.ai ({len(image_urls)} images)...")
    payload = {"prompt": prompt, "image_urls": image_urls}

    resp = requests.post(FAL_EDIT_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        result = poll_fal_result(result, headers)
        if not result:
            return None

    images = result.get("images", [])
    if not images:
        print(f"  No images in response")
        return None

    img_url = images[0].get("url")
    if not img_url:
        return None

    img_data = requests.get(img_url, timeout=30).content
    output_path = OUTPUT / output_name
    output_path.write_bytes(img_data)
    print(f"  Saved: {output_path} ({len(img_data)/1024:.1f} KB)")
    return output_path


# 4 outfit slides to remake
REMAKES = [
    {
        "name": "slide1_gray_hoodie_jeans",
        "source": "slide1.jpg",
        "products": [
            str(PRODUCT_REFS / "checkered-zipper-gray.png"),
            str(PRODUCT_REFS / "graphic-lining-jeans.png"),
        ],
        "prompt": (
            "Image 1 is the source photo — a mirror selfie of a person wearing a hoodie draped over shoulders, white tee, and light jeans. "
            "Keep the EXACT same person, pose, mirror, phone, room, background, lighting, and camera angle. "
            "ONLY change the clothing: "
            "Image 2 shows the new hoodie: a gray zip-up hoodie with blue and yellow plaid flannel lining, silver zipper — drape it the same way over the shoulders. "
            "Image 3 shows the new pants: graphic lining baggy jeans with artistic details. "
            "Replace the outfit with EXACTLY these items. Keep the text 'Clean Fits Inspo:' overlay. "
            "Photorealistic, natural mirror selfie lighting."
        ),
    },
    {
        "name": "slide2_green_hoodie",
        "source": "slide2.jpg",
        "products": [
            str(PRODUCT_REFS / "zip-hoodie-y2k-dark-green.png"),
            str(PRODUCT_REFS / "embroidered-striped-jeans.png"),
        ],
        "prompt": (
            "Image 1 is the source photo — a mirror selfie of a person wearing a light gray hoodie and jeans in a bathroom. "
            "Keep the EXACT same person, pose, mirror, phone, room, background, lighting, and camera angle. "
            "ONLY change the clothing: "
            "Image 2 shows the new hoodie: a dark green suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper. "
            "Image 3 shows the new pants: black and white embroidered striped baggy jeans. "
            "Replace the outfit with EXACTLY these items. Photorealistic, natural mirror selfie lighting."
        ),
    },
    {
        "name": "slide3_black_hoodie_jeans",
        "source": "slide3.jpg",
        "products": [
            str(PRODUCT_REFS / "zip-hoodie-y2k-black.png"),
            str(PRODUCT_REFS / "graphic-lining-jeans.png"),
        ],
        "prompt": (
            "Image 1 is the source photo — a mirror selfie of a person wearing a black hoodie draped over a white tee, with gray jeans. "
            "Keep the EXACT same person, pose, mirror, phone, room, background, lighting, and camera angle. "
            "ONLY change the clothing: "
            "Image 2 shows the new hoodie: a black suede-textured oversized zip hoodie with graffiti-style embroidered text on chest — drape it the same way over the tee. "
            "Image 3 shows the new pants: graphic lining baggy jeans with artistic details. "
            "Replace the outfit with EXACTLY these items. Photorealistic, natural mirror selfie lighting."
        ),
    },
    {
        "name": "slide4_red_checker_ripped",
        "source": "slide4.jpg",
        "products": [
            str(PRODUCT_REFS / "checkered-zipper-red.png"),
            str(PRODUCT_REFS / "embroidered-striped-jeans.png"),
        ],
        "prompt": (
            "Image 1 is the source photo — a mirror selfie of a person wearing a black zip hoodie over white tee, black ripped jeans, beanie, and sneakers. "
            "Keep the EXACT same person, pose, mirror, phone, room, background, lighting, beanie, and camera angle. "
            "ONLY change the hoodie and jeans: "
            "Image 2 shows the new hoodie: a red and black checkered plaid zip-up hoodie with flannel lining, oversized fit. "
            "Image 3 shows the new pants: black and white embroidered striped baggy jeans. "
            "Replace ONLY the hoodie and jeans with these items. Keep the beanie, white tee underneath, and sneakers the same. "
            "Photorealistic, natural mirror selfie lighting."
        ),
    },
]


def main():
    if not FAL_KEY:
        print("ERROR: FAL_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("NEWGARMENTS — TikTok Slide Remake")
    print(f"Source: @fiveleafsclo slide post")
    print(f"Output: {OUTPUT}")
    print("=" * 60)

    results = []
    for i, remake in enumerate(REMAKES):
        print(f"\n--- Slide {i+1}/{len(REMAKES)}: {remake['name']} ---")
        source_path = SLIDES_DIR / remake["source"]
        if not source_path.exists():
            print(f"  ERROR: Source not found: {source_path}")
            continue

        output_name = f"{remake['name']}.png"
        result = remake_slide(str(source_path), remake["products"], remake["prompt"], output_name)
        if result:
            results.append({"name": remake["name"], "output": str(result)})

        if i < len(REMAKES) - 1:
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print(f"Done! {len(results)}/{len(REMAKES)} slides remade")
    print(f"Output: {OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
