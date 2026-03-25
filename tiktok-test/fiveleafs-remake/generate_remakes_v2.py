"""Generate 8 remakes with accurate product descriptions."""
import fal_client
import requests
import base64
from pathlib import Path
import time
import os

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
if not os.getenv("FAL_KEY"):
    raise RuntimeError("FAL_KEY not set – add it to .env")

BASE = Path(__file__).parent
SOURCES = BASE / "pinterest_sources"
PRODUCT_REFS = BASE.parent.parent / "content-library" / "product-refs"
OUTPUT = BASE / "remakes_new"
OUTPUT.mkdir(exist_ok=True)

def image_to_data_url(path):
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    mime = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
    b64 = base64.b64encode(data).decode()
    return f"data:{mime};base64,{b64}"

# Accurate product descriptions based on actual product images
COMBOS = [
    ("source1.jpg", "checkered-zipper-gray.png",
     "The man is wearing a gray zip-up hoodie with blue and yellow plaid flannel lining visible on the inside, silver zipper, oversized fit, hood up or down. Keep exact same male person, pose, mirror, room, phone."),
    
    ("source2.jpg", "zip-hoodie-y2k-dark-green.png",
     "The man is wearing a dark green suede-textured oversized zip hoodie with graffiti-style embroidered text on the chest, silver zipper, hood. Keep exact same male person sitting pose, mirror, cap, room."),
    
    ("source3.jpg", "checkered-zipper-black.png",
     "The man is wearing a black zip-up hoodie with yellow and white plaid flannel lining visible on the inside, silver zipper, oversized cropped fit, hood. Keep exact same male person, pose, mirror, room, phone."),
    
    ("source4.jpg", "zip-hoodie-y2k-black.png",
     "The man is wearing a black suede-textured oversized zip hoodie with graffiti-style embroidered text on the chest, silver zipper, hood. Keep exact same male person, beanie, pose, mirror, bedroom, phone."),
    
    ("source5.jpg", "zip-hoodie-y2k-pink.png",
     "The man is wearing a pink suede-textured oversized zip hoodie with graffiti-style embroidered text on the chest, silver zipper, hood. Keep exact same male person, side profile pose, mirror, room, phone, tattoos."),
    
    ("source6.jpg", "checkered-zipper-red.png",
     "The man is wearing a red and black checkered plaid zip-up hoodie with flannel lining visible, silver zipper, oversized fit, hood. Keep exact same male person, pose, mirror, room, phone."),
    
    ("source7.jpg", "zip-hoodie-y2k-dark-green.png",
     "The man is wearing a dark green suede-textured oversized zip hoodie with graffiti-style embroidered text on the chest, silver zipper, hood. Keep exact same male person, pose, mirror, room, phone."),
    
    ("source8.jpg", "checkered-zipper-gray.png",
     "The man is wearing a gray zip-up hoodie with blue and yellow plaid flannel lining visible on the inside, silver zipper, oversized fit, hood. Keep exact same male person, pose, elevator mirror, phone, bag."),
]

for i, (source, product, prompt) in enumerate(COMBOS, 1):
    source_path = SOURCES / source
    product_path = PRODUCT_REFS / product
    
    if not source_path.exists():
        print(f"  SKIP {source} - not found")
        continue
    
    print(f"\n[{i}/8] {source} + {product}")
    
    source_url = image_to_data_url(source_path)
    product_url = image_to_data_url(product_path)

    try:
        result = fal_client.subscribe(
            "fal-ai/nano-banana-2",
            arguments={
                "prompt": prompt,
                "image_url": source_url,
                "reference_image_url": product_url,
                "seed": 100 + i,
                "num_inference_steps": 35,
            },
        )
        
        if result and "images" in result and len(result["images"]) > 0:
            img_url = result["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            out_path = OUTPUT / f"remake_{i}.png"
            out_path.write_bytes(img_data)
            print(f"  OK: {len(img_data)} bytes")
        else:
            print(f"  ERROR: No images in result")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    time.sleep(1)

print(f"\nDone! All remakes in: {OUTPUT}")
