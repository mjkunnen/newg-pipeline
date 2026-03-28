"""
Proper remake workflow using the EDIT endpoint with full outfits (top + bottom + shoes).
Uses pipeline/generate_image.py functions correctly.
"""
import os
import sys
import json
import base64
import time
import requests
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Load env
load_dotenv(Path(__file__).parent.parent.parent / ".env")
FAL_KEY = os.getenv("FAL_KEY")

BASE = Path(__file__).parent
PINS_OLD = BASE / "board_pins"
PINS_NEW = BASE / "board_pins_new"
OUTPUT = BASE / "board_remakes_proper"
OUTPUT.mkdir(exist_ok=True)
PRODUCT_REFS = Path(__file__).parent.parent.parent / "content-library" / "product-refs"
CATALOG_PATH = Path(__file__).parent.parent.parent / "config" / "clothing-catalog.json"

FAL_EDIT_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"


def encode_image(path):
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def poll_fal_result(queue_response, headers):
    status_url = queue_response["status_url"]
    result_url = queue_response["response_url"]
    for _ in range(60):
        time.sleep(5)
        status = requests.get(status_url, headers=headers, timeout=15).json()
        if status.get("status") == "COMPLETED":
            return requests.get(result_url, headers=headers, timeout=15).json()
        elif status.get("status") in ("FAILED", "CANCELLED"):
            print(f"  FAILED: {status}")
            return None
    print("  TIMEOUT")
    return None


def remake_with_outfit(source_path, top_ref, bottom_ref, shoes_ref, output_path, outfit_label):
    """
    Correct workflow:
    - image_urls[0] = Pinterest source image (keep person/pose/bg)
    - image_urls[1] = top product reference
    - image_urls[2] = bottom product reference
    - image_urls[3] = shoes product reference
    - Prompt tells model which image is which
    """
    headers = {
        "Authorization": f"Key {FAL_KEY}",
        "Content-Type": "application/json",
    }

    image_urls = [encode_image(source_path)]

    ref_parts = []
    if top_ref and Path(top_ref).exists():
        image_urls.append(encode_image(top_ref))
        ref_parts.append(f"Image {len(image_urls)} shows the top/hoodie")
    if bottom_ref and Path(bottom_ref).exists():
        image_urls.append(encode_image(bottom_ref))
        ref_parts.append(f"Image {len(image_urls)} shows the jeans/bottom")
    if shoes_ref and Path(shoes_ref).exists():
        image_urls.append(encode_image(shoes_ref))
        ref_parts.append(f"Image {len(image_urls)} shows the shoes/sneakers")

    ref_text = ". ".join(ref_parts)

    prompt = (
        f"Image 1 is the source photo. Keep everything in Image 1 exactly the same — "
        f"same person, same face, same skin tone, same hairstyle, same pose, same background, "
        f"same lighting, same camera angle, same composition. "
        f"ONLY change the clothing/outfit. "
        f"{ref_text}. "
        f"Replace the outfit on the person in Image 1 with EXACTLY these product items "
        f"as shown in the reference images. The person is wearing a plain white t-shirt underneath "
        f"the zip hoodie, visible at the chest/neckline. Match the colors, patterns, textures, and details "
        f"of each product precisely. The outfit should look natural and photorealistic on the person."
    )

    print(f"  Sending {len(image_urls)} images (1 source + {len(image_urls)-1} product refs)")

    payload = {
        "prompt": prompt,
        "image_urls": image_urls,
    }

    try:
        resp = requests.post(FAL_EDIT_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if result.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
            result = poll_fal_result(result, headers)
            if not result:
                return None

        images = result.get("images", [])
        if images:
            img_url = images[0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            output_path.write_bytes(img_data)
            print(f"  OK: {output_path.name}")
            return output_path
        else:
            print(f"  No images in result")
            return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


# Load catalog
catalog = json.loads(CATALOG_PATH.read_text())
products = catalog["collections"]["691713999225"]["products"]

# Organize by category
tops = {p["id"]: p for p in products if p["category"] == "tops"}
bottoms = {p["id"]: p for p in products if p["category"] == "bottoms"}
footwear = {p["id"]: p for p in products if p["category"] == "footwear"}

print(f"Catalog: {len(tops)} tops, {len(bottoms)} bottoms, {len(footwear)} shoes\n")

# Define outfit combos to generate (subset — not all 24)
# Each outfit = (top_id, bottom_id, shoes_id)
OUTFITS = [
    ("checkered-zipper-gray", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-dark-green", "graphic-lining-jeans", "ocean-stars-sneaker"),
    ("checkered-zipper-black", "embroidered-striped-jeans", "ocean-stars-sneaker"),
    ("zip-hoodie-y2k-pink", "graphic-lining-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-black", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("checkered-zipper-red", "graphic-lining-jeans", "ocean-stars-sneaker"),
]

def get_ref_path(product_id):
    for ext in ("png", "jpg", "jpeg", "webp"):
        p = PRODUCT_REFS / f"{product_id}.{ext}"
        if p.exists():
            return str(p)
    return None

# Find all outfit pin images (from both old and new batches)
all_pins = []
for d in [PINS_OLD, PINS_NEW]:
    if d.exists():
        for f in sorted(d.glob("pin*.jpg")):
            all_pins.append(f)

# Filter: only use outfit photos (pins 1-14), not competitor ads (15-23)
outfit_pins = [p for p in all_pins if int(p.stem.replace("pin", "")) <= 14]
print(f"Found {len(outfit_pins)} outfit pins to remake\n")

# Generate: each pin × one outfit combo (cycling through outfits)
for i, pin_path in enumerate(outfit_pins):
    pin_num = pin_path.stem.replace("pin", "")
    outfit_idx = i % len(OUTFITS)
    top_id, bottom_id, shoes_id = OUTFITS[outfit_idx]

    label = f"{tops[top_id]['name']} + {bottoms[bottom_id]['name']} + {footwear[shoes_id]['name']}"
    print(f"[{i+1}/{len(outfit_pins)}] Pin {pin_num} -> {label}")

    top_ref = get_ref_path(top_id)
    bottom_ref = get_ref_path(bottom_id)
    shoes_ref = get_ref_path(shoes_id)

    output_name = f"remake_pin{pin_num}_{top_id}.png"
    output_path = OUTPUT / output_name

    remake_with_outfit(pin_path, top_ref, bottom_ref, shoes_ref, output_path, label)
    print()

print(f"\nAll remakes saved to: {OUTPUT}")
