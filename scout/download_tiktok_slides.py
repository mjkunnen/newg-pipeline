"""Download TikTok slide images."""
import urllib.request
import ssl
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "output", "fiveleafs_slides")
os.makedirs(OUT_DIR, exist_ok=True)

SLIDES = [
    ("slide1.jpg", "https://p16-pu-sign-no.tiktokcdn-eu.com/tos-no1a-i-photomode-no/87e50e24a10d4529a0b16bbbbc3101e6~tplv-photomode-image.jpeg?dr=14555&x-expires=1774357200&x-signature=b6XfCGf%2BJDmTTFZXfR0CDIwYwow%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=sg1&ftpl=1"),
    ("slide2.jpg", "https://p16-pu-sign-no.tiktokcdn-eu.com/tos-no1a-i-photomode-no/3fc589fd641141edb164adad0e2fe1a9~tplv-photomode-image.jpeg?dr=14555&x-expires=1774357200&x-signature=KNgXYE%2Bp9Xh5F76HMMcuqVyKJb0%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=sg1&ftpl=1"),
    ("slide3.jpg", "https://p16-pu-sign-no.tiktokcdn-eu.com/tos-no1a-i-photomode-no/fa21414f14b141299ef3546a62da2d58~tplv-photomode-image.jpeg?dr=14555&x-expires=1774357200&x-signature=NmUY8iQQf75QKyRMKuOz5%2BkBf9g%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=sg1&ftpl=1"),
    ("slide4.jpg", "https://p16-pu-sign-no.tiktokcdn-eu.com/tos-no1a-i-photomode-no/fd4ca61a64fb470ba2bc59c15bd3b53d~tplv-photomode-image.jpeg?dr=14555&x-expires=1774357200&x-signature=o7eSfsloYbZw7XNZwA4hv19Qg4w%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=sg1&ftpl=1"),
    ("slide5.jpg", "https://p16-pu-sign-no.tiktokcdn-eu.com/tos-no1a-i-photomode-no/7e8835f13e804e88be062b46581a22bc~tplv-photomode-image.jpeg?dr=14555&x-expires=1774357200&x-signature=PLFOGDfeVJPkm1kLyocZJFocaDM%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=9b759fb9&idc=sg1&ftpl=1"),
]

ctx = ssl.create_default_context()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.tiktok.com/",
}

for name, url in SLIDES:
    out_path = os.path.join(OUT_DIR, name)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, context=ctx)
        data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"OK: {name} ({len(data)/1024:.1f} KB)")
    except Exception as e:
        print(f"FAIL: {name} - {e}")
