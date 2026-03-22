"""Generate 8 remakes using fal.ai - each source gets a different NEWGARMENTS outfit."""
import fal_client
import requests
import base64
from pathlib import Path
import time

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

# 8 source-outfit combinations (each source gets a unique outfit)
COMBOS = [
    ("source1.jpg", "checkered-zipper-gray.png", "gray checkered zipper hoodie with white t-shirt underneath and dark baggy jeans"),
    ("source2.jpg", "zip-hoodie-y2k-dark-green.png", "dark green Y2K zip hoodie with white t-shirt and baggy light blue jeans"),
    ("source3.jpg", "checkered-zipper-black.png", "black checkered zipper hoodie with wide leg pants and white sneakers"),
    ("source4.jpg", "zip-hoodie-y2k-black.png", "black Y2K zip hoodie with dark baggy cargo pants and white sneakers"),
    ("source5.jpg", "zip-hoodie-y2k-pink.png", "pink Y2K zip hoodie with gray baggy sweatpants and white sneakers"),
    ("source6.jpg", "checkered-zipper-red.png", "red checkered zipper hoodie with light blue jeans and black boots"),
    ("source7.jpg", "zip-hoodie-y2k-dark-green.png", "dark green Y2K zip hoodie with gray baggy jeans and green-white sneakers"),
    ("source8.jpg", "checkered-zipper-gray.png", "gray checkered zipper hoodie with tan cargo pants and white sneakers"),
]

for i, (source, product, outfit_desc) in enumerate(COMBOS, 1):
    source_path = SOURCES / source
    product_path = PRODUCT_REFS / product
    
    if not source_path.exists():
        print(f"  SKIP {source} - not found")
        continue
    
    print(f"\n[{i}/8] Generating remake: {source} + {product}")
    
    source_url = image_to_data_url(source_path)
    product_url = image_to_data_url(product_path)
    
    prompt = f"""Replace the person's top/jacket/hoodie with this exact clothing item from the reference image. 
The person should be wearing a {outfit_desc}.
Keep the exact same person, pose, background, mirror, phone, and angle. 
Only change the outfit to match the NEWGARMENTS product shown in the reference image.
Photorealistic mirror selfie, natural lighting, streetwear style."""

    try:
        result = fal_client.subscribe(
            "fal-ai/nano-banana-2",
            arguments={
                "prompt": prompt,
                "image_url": source_url,
                "reference_image_url": product_url,
                "seed": 42 + i,
                "num_inference_steps": 30,
            },
        )
        
        if result and "images" in result and len(result["images"]) > 0:
            img_url = result["images"][0]["url"]
            img_data = requests.get(img_url, timeout=30).content
            out_path = OUTPUT / f"remake_{i}.png"
            out_path.write_bytes(img_data)
            print(f"  OK: {out_path.name} ({len(img_data)} bytes)")
        else:
            print(f"  ERROR: No images in result: {result}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    time.sleep(1)

print(f"\nAll remakes saved to: {OUTPUT}")
