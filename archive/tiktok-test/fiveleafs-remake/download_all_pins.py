import requests
from pathlib import Path

OUTPUT = Path(__file__).parent / "pinterest_sources"
OUTPUT.mkdir(exist_ok=True)

# All collected pin images - upgrade to originals for max quality
PINS = {
    "source1": "https://i.pinimg.com/736x/4c/13/60/4c1360a3b53ee48c8eed2638ca3618d4.jpg",  # cream cargo jordan 4
    "source2": "https://i.pinimg.com/736x/94/60/84/946084697639ef542dc934319180a28a.jpg",  # street fashion men
    "source3": "https://i.pinimg.com/736x/64/41/df/6441df1b0ec8d6c6031676c1fbee4d82.jpg",  # steeziest fit
    "source4": "https://i.pinimg.com/736x/5a/7b/f1/5a7bf198d43f00594141a34df78d0525.jpg",  # black outfit oversized
    "source5": "https://i.pinimg.com/736x/d1/96/d0/d196d0b4181596dbb6af5cce69d89d0c.jpg",  # senpooo streetwear
    "source6": "https://i.pinimg.com/736x/e8/53/a2/e853a2a9e17a286f62a606bfa0349535.jpg",  # male comfy spring
    # From search results - upgrade 236x to 736x
    "source7": "https://i.pinimg.com/736x/4f/9b/15/4f9b15336fa7a8ced9d908cfff12e705.jpg",  # search result 1
    "source8": "https://i.pinimg.com/736x/b5/ca/e7/b5cae71bcab1fd0ed7e8a3f7e4551b57.jpg",  # search result 2
}

for name, url in PINS.items():
    # Try originals first
    url_hq = url.replace("/736x/", "/originals/")
    print(f"Downloading {name}...")
    try:
        r = requests.get(url_hq, timeout=15)
        if r.status_code != 200 or len(r.content) < 5000:
            r = requests.get(url, timeout=15)
        (OUTPUT / f"{name}.jpg").write_bytes(r.content)
        print(f"  OK: {len(r.content)} bytes")
    except Exception as e:
        print(f"  Error: {e}")

print("\nAll sources downloaded!")
