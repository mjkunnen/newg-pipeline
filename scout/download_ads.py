"""Download competitor ad images from Facebook CDN."""
import urllib.request
import ssl
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "output", "competitor_ads")
os.makedirs(OUT_DIR, exist_ok=True)

# Revivo Avenue static ad images (all proven winners, running since Jan 31 2026)
ADS = [
    ("revivo_ad1_model_green.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/641164914_2157309888347309_7894080590538257722_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=111&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=SgT1oecGTVcQ7kNvwFo7qOk&_nc_oc=AdryH37vqTCOtjwjuTYS9cWWOz-XLVHERHYHkR9_YWwo4VMjEE5Q6x1jjHEn81VdkKk&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfwZ70k6yNN3ToIUTBXsR-Oq0G2H9HNIIwTaDvf-CtphBw&oe=69C5C517"),
    ("revivo_ad2_shirtless_jeans.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/623422648_1825255844851771_1586320224814786976_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=100&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=2pVsdNlbcy0Q7kNvwGgMDXl&_nc_oc=Adp9O4sSMmK1P6ZkGpbMDscIGZp4LdyE4putuG9c-vrNknV5lhWUuxAk3RUOGQNMDqM&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfxXRXDZ6wMynOlkuzwSNfFixBsLQAKJPHyvslp8QEoAUA&oe=69C5CF34"),
    ("revivo_ad3_double_dark.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/624760107_1419439609818875_1103235535802873843_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=111&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=TMVwHUqsWfsQ7kNvwGyyJDp&_nc_oc=AdpWm0STx3_ALG5MnQMtJ7YANTPMODRRrKDQereqgPqY7Lf_RCRVMwtGSC9J7Zcjndo&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfyTddHGR06gYtF16ZzBA_ET_9o8zQIopq6N9BzqSN0lsA&oe=69C5982B"),
    ("revivo_ad4_dark_outfit.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/623438807_872340728886860_6800940631696092026_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=108&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=cntOn-qOIrwQ7kNvwGEFksy&_nc_oc=Adp5Gchupb6KhdE8xb9OaVzVfQRzi4IMALtWJEgp8_4mW1D3BhdLbEjBWefHyEuwjrc&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfxtdtbonsWnVjnkraOPAtgPPGxYkUZLC1BJ-GA8XDNJaQ&oe=69C5C4A4"),
    ("revivo_ad5_vanity_jacket.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/638202473_1400927317898630_7464071730097737869_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=110&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=Sn4xNviCHAYQ7kNvwGaejYB&_nc_oc=AdoBhsJeIrRmbRIzjXNAfBCd5MqT6jnNujxBct9OSCl_WnomDJfAQUcJ0GmXnZKXf98&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfyG6JCN_23hQdRmqDkaYO7LWVl-E7Ul0GdUYefl5kdf8w&oe=69C5B5BD"),
    ("revivo_ad6_widelegs_v2.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/623380973_1640488567387825_1341962013688429533_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=102&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=flIaOvwc3j0Q7kNvwHzKTGv&_nc_oc=Adoc4AjAJioUfedXwBT2Gbn6daLrmG2r8Mx2vW9NWOO1wlSpOssLdjlHimeZyHgDOq4&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_Afz5i_-4bIFPsL-3BMNqX4dO-ihz3zoFCKo8lC63Iru4bA&oe=69C5B11C"),
    ("revivo_ad7_model_v3.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/623919337_2071081250356605_3377556752148573354_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=111&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=DKnNH2uE8KsQ7kNvwG3UnIR&_nc_oc=Adrr78oMVESVuQdyGfy6ORL787R7N0AMJy3D7UR-sTWhfOR4nZln1PayDgkvzWEuJAA&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_AfwmycP5U-JB9V5YFnRLhbJz0xNJ684Rhesjrr0GjypKkw&oe=69C5A5F4"),
    ("revivo_ad8_bestsellers.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/622852414_1932191874359379_5750079282941818811_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=110&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=4N_GJwAV6GoQ7kNvwF149h7&_nc_oc=AdqqynxCFoKK8jOJj5-urBmIYBI9AlAnd6U6i-dg1zGiktwRbnIjEd0Rmqia3jFyi_U&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_Afwu22CyEH44Z3u4W7jMQo7Y9TmwtzTfYmVRXNU5JaXlqg&oe=69C5ACB8"),
    ("revivo_ad9_cap.jpg", "https://scontent.fdps8-1.fna.fbcdn.net/v/t39.35426-6/655612535_1652084619554048_403851039403170533_n.jpg?stp=dst-jpg_s600x600_tt6&_nc_cat=105&ccb=1-7&_nc_sid=c53f8f&_nc_ohc=r88baZ_2zmwQ7kNvwGVs3i8&_nc_oc=Adqg3BRUcD-ELPg-VC2t-umeHBe3sv4zeb7w_AeNlD_Qmt2CYGr4JNOlMueHiH4_0d0&_nc_zt=14&_nc_ht=scontent.fdps8-1.fna&_nc_gid=1pTXvuaxbgwiOiuIfSgfNg&_nc_ss=7a30f&oh=00_Afxu0g1_fcBcmNXOpbmkAf93AyB_1e73--UzV6jRjuBP3Q&oe=69C5A581"),
]

ctx = ssl.create_default_context()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://www.facebook.com/",
}

for name, url in ADS:
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

print(f"\nDone! Files saved to {OUT_DIR}")
