import requests
import time
import os
import json

FAL_KEY = "995ba237-b123-4a7f-b582-74024c92c132:3d3350082ae43c0431a00910ed3abf29"
QUEUE_URL = "https://queue.fal.run/fal-ai/nano-banana-2/edit"
HEADERS = {
    "Authorization": f"Key {FAL_KEY}",
    "Content-Type": "application/json"
}

# Product reference URLs (Shopify CDN)
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

# 6 outfit combos
OUTFITS = [
    ("checkered-zipper-gray", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-dark-green", "graphic-lining-jeans", "ocean-stars-sneaker"),
    ("checkered-zipper-black", "embroidered-striped-jeans", "ocean-stars-sneaker"),
    ("zip-hoodie-y2k-pink", "graphic-lining-jeans", "fur-graphic-sneakers"),
    ("zip-hoodie-y2k-black", "embroidered-striped-jeans", "fur-graphic-sneakers"),
    ("checkered-zipper-red", "graphic-lining-jeans", "ocean-stars-sneaker"),
]

# All 25 pins
PINS = [
    {"id": "1003176885764220462", "url": "https://i.pinimg.com/1200x/c3/b9/a9/c3b9a9c69a58852d860aaa74d760e5a0.jpg"},
    {"id": "1003176885764220460", "url": "https://i.pinimg.com/1200x/4f/6e/87/4f6e8723cdbaedfcdaa447f8f5d85b9f.jpg"},
    {"id": "1003176885764214600", "url": "https://i.pinimg.com/1200x/87/fc/c0/87fcc015e1945fee0fd59f95204f1002.jpg"},
    {"id": "1003176885764214595", "url": "https://i.pinimg.com/1200x/fa/5e/a0/fa5ea061f93cfbcdce95aad75f53645e.jpg"},
    {"id": "1003176885764214592", "url": "https://i.pinimg.com/1200x/1e/f7/30/1ef7301ed81fde4f701a56b88be41102.jpg"},
    {"id": "1003176885764214588", "url": "https://i.pinimg.com/1200x/8e/f0/37/8ef037526b2be29d4a108c9b044f8755.jpg"},
    {"id": "1003176885764178368", "url": "https://i.pinimg.com/1200x/52/36/13/52361308c838947eb7d07064d25d4330.jpg"},
    {"id": "1003176885764178366", "url": "https://i.pinimg.com/1200x/cd/c9/fd/cdc9fda3ab4d1806f43d44762e6fd8c7.jpg"},
    {"id": "1003176885764178360", "url": "https://i.pinimg.com/1200x/2a/ff/72/2aff7270a3d6c18e405fc887f91ffd02.jpg"},
    {"id": "1003176885764178348", "url": "https://i.pinimg.com/1200x/c9/63/dd/c963dd3293bb741485ef65e0b9c0203a.jpg"},
    {"id": "1003176885764146583", "url": "https://i.pinimg.com/1200x/9a/f3/99/9af399be6b980cddfd0c8dc4b4bdf865.jpg"},
    {"id": "1003176885764146576", "url": "https://i.pinimg.com/1200x/73/05/0f/73050f291677a1c901467add7864ffc5.jpg"},
    {"id": "1003176885764146571", "url": "https://i.pinimg.com/1200x/a8/ce/dc/a8cedc9018cc0808f436574485a89e30.jpg"},
    {"id": "1003176885764146567", "url": "https://i.pinimg.com/1200x/56/90/b3/5690b3c8036e2e12fe665b9e147acfc9.jpg"},
    {"id": "1003176885764146558", "url": "https://i.pinimg.com/1200x/3b/21/68/3b21682488c815564f6a45567b0c2756.jpg"},
    {"id": "1003176885764146542", "url": "https://i.pinimg.com/1200x/77/87/ac/7787ac29a8ccaa82153595da044e3015.jpg"},
    {"id": "1003176885764111404", "url": "https://i.pinimg.com/1200x/2a/92/74/2a92740f3a3013967b56a970f2b71e02.jpg"},
    {"id": "1003176885764109960", "url": "https://i.pinimg.com/1200x/07/cb/83/07cb837cd9324d583b7ec8ef36dcd76e.jpg"},
    {"id": "1003176885764109794", "url": "https://i.pinimg.com/1200x/ff/2a/23/ff2a2327760cc855125dbca3a2977490.jpg"},
    {"id": "1003176885764109778", "url": "https://i.pinimg.com/1200x/07/a2/5f/07a25f60200f1ce9a9b4ba4789a56701.jpg"},
    {"id": "1003176885764106014", "url": "https://i.pinimg.com/1200x/a6/f1/5d/a6f15de777ba041e11f62c6d60daaf7f.jpg"},
    {"id": "1003176885764105989", "url": "https://i.pinimg.com/1200x/7d/e8/91/7de8919c66ff7d3f2ad908f7dea4afb1.jpg"},
    {"id": "1003176885764105969", "url": "https://i.pinimg.com/1200x/22/04/44/2204447b2fe751501126193df1f3a399.jpg"},
    {"id": "1003176885764105507", "url": "https://i.pinimg.com/1200x/53/fb/8b/53fb8bd2078344348cc392ad7c80aa13.jpg"},
    {"id": "1003176885764103210", "url": "https://i.pinimg.com/1200x/3d/ec/0e/3dec0ee565698c66a1fad3ebb344b66d.jpg"},
]

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

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

def submit_job(pin_url, top_url, bottom_url, shoes_url, prompt):
    payload = {
        "prompt": prompt,
        "image_urls": [pin_url, top_url, bottom_url, shoes_url]
    }
    resp = requests.post(QUEUE_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data.get("request_id")

def poll_result(request_id, max_wait=300):
    status_url = f"{QUEUE_URL}/requests/{request_id}/status"
    result_url = f"{QUEUE_URL}/requests/{request_id}"
    start = time.time()
    while time.time() - start < max_wait:
        resp = requests.get(status_url, headers=HEADERS)
        resp.raise_for_status()
        status = resp.json()
        if status.get("status") == "COMPLETED":
            result = requests.get(result_url, headers=HEADERS)
            result.raise_for_status()
            return result.json()
        elif status.get("status") in ("FAILED", "CANCELLED"):
            print(f"  Job {request_id} failed: {status}")
            return None
        time.sleep(5)
    print(f"  Job {request_id} timed out")
    return None

def download_image(url, filepath):
    resp = requests.get(url)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        f.write(resp.content)

def main():
    results = []
    # Submit all jobs first (batch), then poll
    jobs = []
    for i, pin in enumerate(PINS):
        outfit = OUTFITS[i % len(OUTFITS)]
        top_id, bottom_id, shoes_id = outfit
        top_url = TOPS[top_id]
        bottom_url = BOTTOMS[bottom_id]
        shoes_url = SHOES[shoes_id]
        prompt = build_prompt(top_id, bottom_id, shoes_id)

        print(f"[{i+1}/25] Submitting pin {pin['id']} with outfit: {top_id} + {bottom_id} + {shoes_id}")
        try:
            request_id = submit_job(pin["url"], top_url, bottom_url, shoes_url, prompt)
            print(f"  -> Request ID: {request_id}")
            jobs.append({
                "pin_id": pin["id"],
                "request_id": request_id,
                "outfit": f"{top_id}__{bottom_id}__{shoes_id}",
                "index": i
            })
        except Exception as e:
            print(f"  -> FAILED to submit: {e}")

        # Small delay between submissions to avoid rate limiting
        time.sleep(0.5)

    print(f"\nSubmitted {len(jobs)} jobs. Now polling for results...\n")

    # Poll all jobs
    for job in jobs:
        print(f"Polling pin {job['pin_id']} (request {job['request_id']})...")
        result = poll_result(job["request_id"])
        if result and "images" in result and len(result["images"]) > 0:
            img_url = result["images"][0].get("url")
            if img_url:
                filename = f"remake_{job['pin_id']}_{job['outfit']}.png"
                filepath = os.path.join(OUTPUT_DIR, filename)
                download_image(img_url, filepath)
                print(f"  -> Saved: {filename}")
                results.append({"pin_id": job["pin_id"], "file": filename, "url": img_url})
            else:
                print(f"  -> No image URL in result")
        else:
            print(f"  -> No result")

    # Save manifest
    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone! {len(results)}/{len(PINS)} remakes generated.")

if __name__ == "__main__":
    main()
