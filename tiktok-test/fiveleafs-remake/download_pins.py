"""Download Pinterest pin images for remake source material."""
import requests
from pathlib import Path

# Pin image URLs extracted from Pinterest (high-res pinimg.com)
# Replace 736x with originals for max quality
PIN_IMAGES = {
    "pin1": "https://i.pinimg.com/736x/4c/13/60/4c1360a3b53ee48c8eed2638ca3618d4.jpg",  # cream cargo + jordan 4
    "pin3": "https://i.pinimg.com/736x/a2/a6/6b/a2a66b017c925f7dd1f03791d951c7fe.jpg",  # baggy jeans shacket
}

# Need to get more pins - let me use originals URL pattern
PINS_TO_FETCH = [
    "https://www.pinterest.com/pin/281615782940095163/",
    "https://www.pinterest.com/pin/606086062386274584/",
    "https://www.pinterest.com/pin/873698396461820119/",
    "https://www.pinterest.com/pin/723812971380651587/",
    "https://www.pinterest.com/pin/3729612235366964/",
    "https://www.pinterest.com/pin/59813501296686701/",
    "https://www.pinterest.com/pin/774124928539707/",
]

OUTPUT = Path(__file__).parent / "pinterest_sources"

for name, url in PIN_IMAGES.items():
    # Get higher res
    url_hq = url.replace("/736x/", "/originals/")
    print(f"Downloading {name}...")
    try:
        r = requests.get(url_hq, timeout=15)
        if r.status_code != 200:
            r = requests.get(url, timeout=15)
        ext = "jpg"
        (OUTPUT / f"{name}.{ext}").write_bytes(r.content)
        print(f"  Saved {name}.{ext} ({len(r.content)} bytes)")
    except Exception as e:
        print(f"  Error: {e}")

print("Done with direct URLs. Need Playwright for remaining pins.")
