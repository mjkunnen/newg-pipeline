"""
Remake new pins from the ADS NEWGARMENTS Pinterest board.
Pin 9-14 are outfit photos that need to be remade with NEWGARMENTS products.
"""
import os
import sys
import base64
import random
import requests
from pathlib import Path
from PIL import Image

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
if not os.getenv("FAL_KEY"):
    raise RuntimeError("FAL_KEY not set – add it to .env")
import fal_client

BASE = Path(__file__).parent
PINS = BASE / "board_pins_new"
OUTPUT = BASE / "board_remakes_new"
OUTPUT.mkdir(exist_ok=True)
PRODUCT_REFS = Path(__file__).parent.parent.parent / "content-library" / "product-refs"


def image_to_data_url(path):
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def generate_remake(source_path, product_file, product_desc, output_path):
    source_url = image_to_data_url(source_path)
    product_path = PRODUCT_REFS / product_file
    product_url = image_to_data_url(product_path)

    prompt = f"""The person is wearing a {product_desc}.
Keep the exact same person, face, skin tone, hairstyle, pose, background, mirror, phone, and angle.
Only change the top/hoodie/jacket to match the reference product image exactly.
Photorealistic, natural lighting, streetwear style."""

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

            # Crop to right panel if multi-panel
            img = Image.open(output_path)
            w, h = img.size
            if w > h * 1.2:
                panels = round(w / h)
                panel_w = w // panels
                crop = img.crop((w - panel_w, 0, w, h))
                crop.save(output_path, quality=95)

            print(f"  OK: {output_path.name} ({crop.size if w > h * 1.2 else img.size})")
            return output_path
        else:
            print(f"  FAIL: No images in result")
            return None
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


# Only outfit pins (9-14), paired with different NEWGARMENTS products
remakes = [
    # pin9: LV sweater mirror selfie -> gray checkered zipper
    ("pin9.jpg", "checkered-zipper-gray.png",
     "gray zip-up hoodie with blue and yellow plaid flannel lining visible at the collar and zipper area, silver zipper, oversized fit"),

    # pin10: Black graphic hoodie -> black Y2K zip hoodie
    ("pin10.jpg", "zip-hoodie-y2k-black.png",
     "black suede-textured oversized zip hoodie with colorful graffiti-style embroidered text on the chest reading street-style words, silver zipper, open over white tee"),

    # pin11: Black D sweater -> black checkered zipper
    ("pin11.jpg", "checkered-zipper-black.png",
     "black zip-up hoodie with yellow and white plaid flannel lining visible at collar, silver zipper, oversized cropped fit"),

    # pin12: Black cardigan full body -> dark green Y2K
    ("pin12.jpg", "zip-hoodie-y2k-dark-green.png",
     "dark green suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper, open over white tee"),

    # pin13: Brown pattern sweater arch mirror -> pink Y2K
    ("pin13.jpg", "zip-hoodie-y2k-pink.png",
     "pink suede-textured oversized zip hoodie with graffiti-style embroidered text on chest, silver zipper"),

    # pin14: Burgundy tracksuit editorial -> red checkered
    ("pin14.jpg", "checkered-zipper-red.png",
     "red and black buffalo plaid checkered zip-up hoodie with flannel lining, silver zipper, oversized fit"),
]

print(f"Generating {len(remakes)} remakes from new board pins...\n")

for i, (pin_file, product_file, product_desc) in enumerate(remakes):
    pin_num = 9 + i
    print(f"[{i+1}/{len(remakes)}] pin{pin_num} -> {product_file}")
    source = PINS / pin_file
    output = OUTPUT / f"remake_{pin_num}.png"

    if not source.exists():
        print(f"  SKIP: {source} not found")
        continue

    generate_remake(source, product_file, product_desc, output)
    print()

print(f"\nDone! Remakes saved to: {OUTPUT}")
