"""
NEWGARMENTS — Competitor Page Finder v2
========================================
Finds TikTok accounts that are 90%+ slideshows with product images,
collages, and Pinterest-style content with text overlays.
No minimum follower count.

Uses persistent browser profile + manual-first approach to avoid captchas.
"""

import asyncio
import json
import random
import sys
import io
import re
import os
import subprocess
import time
from datetime import datetime
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# ─── CONFIG ────────────────────────────────────────────────────────────────────

HASHTAGS = [
    "streetwearbrand",
    "streetweardrops",
    "clothingbrand",
    "streetwearstyle",
    "streetwearfashion",
    "heavyweighthoodie",
    "heavyweighttee",
    "oversizedstreetwear",
    "oversizedhoodie",
    "baggyjeans",
    "baggyfit",
    "flaredjeans",
    "archivefashion",
    "streetweararchive",
    "undergroundstreetwear",
    "newstreetwear",
    "streetweareurope",
    "tiktokstreetwear",
    "tiktokfashion",
    "fashiontiktok",
    "streetwearinspo",
    "outfitinspo",
    "streetwearlookbook",
    "newdrop",
    "limiteddrops",
]

MAX_ACCOUNTS_PER_HASHTAG = 25
MIN_SLIDESHOW_RATIO = 0.90
MIN_FOLLOWERS = 0
WESTERN_ONLY = True
OUTPUT_FILE = f"competitor_pages_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiktok_profile")
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CDP_PORT = 9222

# Already-researched accounts to skip
SKIP_ACCOUNTS = {
    "newgarmentsclo", "fiveleafsclo", "fiveleafs",
    "visionair.store", "representclo", "brokenplanetmarket",
    "brokenplanet", "corteiz", "trapstar", "colebuxton",
    "pegador", "unknownlondon", "coldculture",
    "vicinityclo", "divinbydivin", "thesupermade", "scuffers",
}

# ─── HELPERS ───────────────────────────────────────────────────────────────────

async def human_delay(min_s=2.0, max_s=4.0):
    await asyncio.sleep(random.uniform(min_s, max_s))

def is_western_account(username, bio):
    bio_lower = (bio or "").lower()
    username_lower = username.lower()
    sea_keywords = [
        "jakarta", "jkt", "bandung", "surabaya", "indonesia", "indo",
        "shopee", "tokopedia", "cod ", "ongkir", "gratis ongkir",
        "promo ", "diskon", "murah", "harga", "rupiah", "rp ", "rp.",
        "beli", "jual", "toko", "olshop", "ready stock", "pre order",
        "pengiriman", "kirim", "sidoarjo", "semarang", "yogyakarta",
        "malang", "medan", "makassar", "bali", "tangerang", "bekasi",
        "depok", "bogor", "palembang", "kota", "provinsi",
        "malaysia", "kuala lumpur", "sabah", "thai", "bangkok",
        "vietnam", "pinoy", "manila", "cebu", "philippines",
        ".id", "busana", "baju", "celana", "kaos",
    ]
    for kw in sea_keywords:
        if kw in bio_lower:
            return False
    if username_lower.endswith(".id") or "indonesia" in username_lower:
        return False
    if bio:
        non_latin = sum(1 for c in bio if ord(c) > 0x024F and not (0x2000 <= ord(c) <= 0x27FF) and not (0xFE00 <= ord(c) <= 0xFEFF) and not (0x1F000 <= ord(c) <= 0x1FAFF))
        latin = sum(1 for c in bio if c.isascii() and c.isalpha())
        total_chars = non_latin + latin
        if total_chars > 3 and non_latin / total_chars > 0.4:
            return False
    return True

def parse_count(text):
    if not text:
        return 0
    text = text.strip().upper().replace(",", "")
    try:
        if "K" in text:
            return int(float(text.replace("K", "")) * 1_000)
        elif "M" in text:
            return int(float(text.replace("M", "")) * 1_000_000)
        else:
            return int(text)
    except:
        return 0

async def safe_goto(page, url, timeout=45000):
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return True
        except:
            if attempt < 2:
                await asyncio.sleep(3)
    return False

async def scroll_page(page, rounds=4, distance=600):
    for _ in range(rounds):
        try:
            await page.evaluate(f"window.scrollBy(0, {distance})")
            await asyncio.sleep(random.uniform(0.8, 1.5))
        except:
            break

async def wait_for_captcha(page, label=""):
    """Check for captcha and wait indefinitely until user solves it."""
    try:
        captcha = await page.query_selector('[class*="captcha"], [class*="Captcha"], [id*="captcha"]')
        body_text = ""
        try:
            body_text = await page.inner_text("body")
        except:
            pass

        has_captcha = captcha or "verify" in body_text.lower()[:500]

        if not has_captcha:
            return True

        print(f"\n   >>> CAPTCHA{' on ' + label if label else ''}! Solve it in the browser...", end="", flush=True)

        # Wait up to 120 seconds for user to solve
        for i in range(24):
            await asyncio.sleep(5)
            print(".", end="", flush=True)
            try:
                # Check if captcha is gone
                captcha = await page.query_selector('[class*="captcha"], [class*="Captcha"], [id*="captcha"]')
                if not captcha:
                    # Also verify page has content now
                    links = await page.query_selector_all('a[href*="/@"]')
                    body = await page.inner_text("body")
                    if len(links) > 1 or len(body) > 500:
                        print(" SOLVED!")
                        await asyncio.sleep(2)
                        return True
            except:
                pass

        print(" TIMEOUT (120s)")
        return False
    except:
        return True


# ─── API INTERCEPTOR ─────────────────────────────────────────────────────────

class PostDataCollector:
    def __init__(self):
        self.posts = []
        self.raw_items = []

    def reset(self):
        self.posts = []
        self.raw_items = []

    async def intercept_response(self, response):
        url = response.url
        try:
            if "/api/post/item_list" in url or "/api/item_list" in url:
                data = await response.json()
                items = data.get("itemList", data.get("items", []))
                self.raw_items.extend(items)
            elif "/api/recommend/item_list" in url:
                data = await response.json()
                items = data.get("itemList", [])
                self.raw_items.extend(items)
        except:
            pass

    def analyze_posts(self):
        self.posts = []
        for item in self.raw_items:
            post = {
                "id": item.get("id", ""),
                "is_slideshow": False,
                "views": 0,
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "saves": 0,
            }
            if item.get("imagePost") or item.get("image_post_info"):
                post["is_slideshow"] = True
            elif item.get("photo_images") or item.get("photoImages"):
                post["is_slideshow"] = True

            stats = item.get("stats", {})
            post["views"] = stats.get("playCount", 0)
            post["likes"] = stats.get("diggCount", 0)
            post["comments"] = stats.get("commentCount", 0)
            post["shares"] = stats.get("shareCount", 0)
            post["saves"] = stats.get("collectCount", 0)
            self.posts.append(post)
        return self.posts


async def extract_sigi_state(page):
    posts_data = []
    try:
        sigi = await page.evaluate("""() => {
            if (window.SIGI_STATE) return JSON.stringify(window.SIGI_STATE);
            if (window.__UNIVERSAL_DATA_FOR_REHYDRATION__)
                return JSON.stringify(window.__UNIVERSAL_DATA_FOR_REHYDRATION__);
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                const text = s.textContent || '';
                if (text.includes('ItemModule') || text.includes('imagePost')) {
                    const match = text.match(/\\{.*ItemModule.*\\}/s);
                    if (match) return match[0];
                }
            }
            return null;
        }""")
        if not sigi:
            return posts_data
        data = json.loads(sigi)
        item_module = None
        if "ItemModule" in data:
            item_module = data["ItemModule"]
        elif "default" in data:
            scope = data["default"]
            if isinstance(scope, dict):
                for key, val in scope.items():
                    if isinstance(val, dict) and "itemList" in val:
                        for item in val["itemList"]:
                            is_slide = bool(item.get("imagePost") or item.get("image_post_info"))
                            posts_data.append({
                                "id": item.get("id", ""),
                                "is_slideshow": is_slide,
                                "views": item.get("stats", {}).get("playCount", 0),
                                "likes": item.get("stats", {}).get("diggCount", 0),
                            })
        if item_module and isinstance(item_module, dict):
            for post_id, item in item_module.items():
                is_slide = bool(item.get("imagePost") or item.get("image_post_info"))
                stats = item.get("stats", {})
                posts_data.append({
                    "id": post_id,
                    "is_slideshow": is_slide,
                    "views": stats.get("playCount", 0),
                    "likes": stats.get("diggCount", 0),
                })
    except:
        pass
    return posts_data


async def detect_slideshows_combined(page, collector):
    all_posts = []
    sigi_posts = await extract_sigi_state(page)
    if sigi_posts:
        all_posts.extend(sigi_posts)

    if collector.raw_items:
        api_posts = collector.analyze_posts()
        existing_ids = {p["id"] for p in all_posts}
        for p in api_posts:
            if p["id"] not in existing_ids:
                all_posts.append(p)

    if not all_posts:
        try:
            await scroll_page(page, rounds=3, distance=500)
            links = await page.query_selector_all('a[href*="/photo/"], a[href*="/video/"]')
            seen = set()
            for link in links:
                href = await link.get_attribute("href") or ""
                if "/photo/" in href:
                    pid = href.split("/photo/")[-1].split("?")[0]
                    if pid not in seen:
                        seen.add(pid)
                        all_posts.append({"id": pid, "is_slideshow": True, "views": 0})
                elif "/video/" in href:
                    pid = href.split("/video/")[-1].split("?")[0]
                    if pid not in seen:
                        seen.add(pid)
                        all_posts.append({"id": pid, "is_slideshow": False, "views": 0})
        except:
            pass

    slideshow_count = sum(1 for p in all_posts if p.get("is_slideshow"))
    video_count = sum(1 for p in all_posts if not p.get("is_slideshow"))
    total = len(all_posts)
    views = [p["views"] for p in all_posts if p.get("views", 0) > 0]
    slideshow_views = [p["views"] for p in all_posts if p.get("is_slideshow") and p.get("views", 0) > 0]
    max_slideshow_views = max(slideshow_views) if slideshow_views else 0

    return slideshow_count, video_count, total, views, max_slideshow_views


# ─── HASHTAG SCRAPER ──────────────────────────────────────────────────────────

async def scrape_hashtag(page, hashtag, max_accounts):
    print(f"\n[SEARCH] #{hashtag}")
    accounts = []

    if not await safe_goto(page, f"https://www.tiktok.com/tag/{hashtag}"):
        print(f"   ERROR: failed to load")
        return accounts

    await asyncio.sleep(random.uniform(3, 5))

    # Check and wait for captcha
    await wait_for_captcha(page, f"#{hashtag}")

    await scroll_page(page, rounds=8, distance=800)

    try:
        all_links = await page.query_selector_all('a')
        seen = set()
        for link in all_links:
            href = await link.get_attribute("href") or ""
            if "/@" in href:
                parts = href.split("/@")
                if len(parts) > 1:
                    username = parts[1].split("/")[0].split("?")[0].strip()
                    if username and username not in seen and len(username) > 1:
                        seen.add(username)
                        accounts.append(username)
            if len(accounts) >= max_accounts:
                break
    except Exception as e:
        print(f"   ERROR: {e}")

    if not accounts:
        try:
            await page.screenshot(path=f"debug_competitor_{hashtag}.png")
            print(f"   DEBUG: screenshot saved, URL = {page.url}")
        except:
            pass

    print(f"   -> {len(accounts)} accounts found")
    return accounts


# ─── PROFILE SCRAPER ─────────────────────────────────────────────────────────

async def scrape_profile(page, username, collector):
    print(f" @{username}", end="", flush=True)

    profile = {
        "username": username,
        "url": f"https://www.tiktok.com/@{username}",
        "followers": 0, "following": 0, "likes": 0,
        "bio": "", "bio_link": "",
        "avg_views": 0, "max_views": 0,
        "slideshow_posts": 0, "video_posts": 0,
        "total_checked": 0, "slideshow_ratio": 0.0,
        "format": "", "detection_method": "",
        "scraped_at": datetime.now().isoformat(),
    }

    collector.reset()

    if not await safe_goto(page, f"https://www.tiktok.com/@{username}"):
        print(f" -> timeout")
        return "timeout"

    await asyncio.sleep(random.uniform(2.5, 4.5))

    # Captcha check on profile
    await wait_for_captcha(page, f"@{username}")

    # Followers
    try:
        el = await page.query_selector('[data-e2e="followers-count"]')
        if el:
            profile["followers"] = parse_count(await el.inner_text())
    except:
        pass

    # Likes & Following
    for field, sel in [("likes", "likes-count"), ("following", "following-count")]:
        try:
            el = await page.query_selector(f'[data-e2e="{sel}"]')
            if el:
                profile[field] = parse_count(await el.inner_text())
        except:
            pass

    # Bio
    try:
        el = await page.query_selector('[data-e2e="user-bio"]')
        if el:
            profile["bio"] = (await el.inner_text()).strip()
    except:
        pass

    # Western filter
    if WESTERN_ONLY and not is_western_account(username, profile["bio"]):
        print(f" -> SKIP (non-Western)")
        return None

    # Bio link
    try:
        link_el = await page.query_selector('[data-e2e="user-link"] a, a[href*="link.tiktok"], [data-e2e="user-bio-link"] a')
        if link_el:
            profile["bio_link"] = (await link_el.get_attribute("href") or await link_el.inner_text() or "").strip()
        if not profile["bio_link"]:
            url_match = re.search(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,})(?:/\S*)?', profile["bio"])
            if url_match:
                profile["bio_link"] = url_match.group(0)
    except:
        pass

    # Scroll to load posts
    await scroll_page(page, rounds=5, distance=600)
    await asyncio.sleep(1.5)

    # Slideshow detection
    slide_count, vid_count, total, post_views, max_slide_views = await detect_slideshows_combined(page, collector)

    profile["slideshow_posts"] = slide_count
    profile["video_posts"] = vid_count
    profile["total_checked"] = total
    profile["max_views"] = max_slide_views

    if collector.raw_items:
        profile["detection_method"] = "api_intercept"
    else:
        profile["detection_method"] = "sigi_state_or_url"

    # Views
    if post_views:
        profile["avg_views"] = int(sum(post_views) / len(post_views))
    else:
        try:
            view_els = await page.query_selector_all('[data-e2e="video-views"]')
            views = []
            for el in view_els[:10]:
                v = parse_count(await el.inner_text())
                if v > 0:
                    views.append(v)
            if views:
                profile["avg_views"] = int(sum(views) / len(views))
                profile["max_views"] = max(max(views), profile["max_views"])
        except:
            pass

    if total > 0:
        profile["slideshow_ratio"] = round(slide_count / total, 2)

    # Format label & filter
    if total == 0:
        print(f" -> SKIP (no posts)")
        return None
    elif total < 3:
        print(f" -> SKIP (only {total} posts)")
        return None
    elif profile["slideshow_ratio"] < MIN_SLIDESHOW_RATIO:
        print(f" -> SKIP ({slide_count}/{total}={profile['slideshow_ratio']*100:.0f}% < 90%)")
        return None

    profile["format"] = "slideshow-only"
    print(f" -> MATCH! {slide_count}/{total} slides ({profile['slideshow_ratio']*100:.0f}%) | {profile['followers']:,} flw | max {profile['max_views']:,} views [{profile['detection_method']}]")
    return profile


# ─── SCORING ──────────────────────────────────────────────────────────────────

def score_account(p):
    score = 0
    notes = []
    flw = p.get("followers", 0)
    avg = p.get("avg_views", 0)
    max_v = p.get("max_views", 0)
    bio = p.get("bio", "").lower()
    sr = p.get("slideshow_ratio", 0)

    if flw > 0 and avg > 0:
        ratio = avg / max(flw, 1)
        if ratio >= 1.0:
            score += 4; notes.append(f"VIRAL {ratio:.1f}x views/flw")
        elif ratio >= 0.3:
            score += 3; notes.append(f"High engagement {ratio:.1f}x")
        elif ratio >= 0.1:
            score += 2; notes.append(f"Good engagement {ratio:.1f}x")
        elif ratio >= 0.05:
            score += 1; notes.append(f"Decent engagement {ratio:.2f}x")

    if flw < 5000 and max_v > 50000:
        score += 3; notes.append(f"Low flw ({flw:,}) but {max_v:,} max views!")
    elif flw < 10000 and max_v > 100000:
        score += 3; notes.append(f"Viral slideshow {max_v:,} views on {flw:,} flw")

    if sr >= 0.95:
        score += 2; notes.append("95%+ slideshows")
    elif sr >= 0.90:
        score += 1; notes.append("90%+ slideshows")

    brand_keywords = ["archive", "streetwear", "store", "shop", "brand", "clothing",
                      "drop", "showcase", "baggy", "oversized", "heavyweight",
                      "worldwide shipping", "fashion", "limited", "premium",
                      "quality", "handmade", "hoodie", "apparel", "wear"]
    for kw in brand_keywords:
        if kw in bio:
            score += 1; notes.append(f"Bio: '{kw}'"); break

    if p.get("bio_link"):
        score += 1; notes.append("Has website link")

    for kw in ["shein", "amazon", "aliexpress", "fast fashion", "dropship",
               "y2k", "anime", "kpop", "makeup", "skincare", "cooking",
               "repost", "fanpage", "meme"]:
        if kw in bio:
            score -= 5; notes.append(f"RED FLAG: '{kw}'"); break

    return max(0, score), notes


# ─── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 65)
    print("  NEWGARMENTS — Competitor Page Finder v2")
    print("  Target: 90%+ slideshow accounts (product/collage/pinterest)")
    print("  Using YOUR real Chrome browser (no captcha issues)")
    print("=" * 65)

    all_accounts = {}
    results = []

    # ── LAUNCH PLAYWRIGHT CHROMIUM ──────────────────────────────────
    os.makedirs(PROFILE_DIR, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.4 Mobile/15E148 Safari/604.1"
            ),
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
            ignore_default_args=["--enable-automation"],
        )

        collector = PostDataCollector()
        page = context.pages[0] if context.pages else await context.new_page()
        page.on("response", collector.intercept_response)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        print("   Connected to Chrome!")

        # ── LOGIN CHECK ──────────────────────────────────────────────
        print("\n[STEP 0] Opening TikTok — checking login status...")
        await safe_goto(page, "https://www.tiktok.com/foryou", timeout=30000)
        await asyncio.sleep(4)

        is_logged_in = False
        try:
            page_url = page.url
            body = await page.inner_text("body")
            if "/login" not in page_url and ("Following" in body or "For You" in body or "foryou" in page_url):
                is_logged_in = True
                print("   Logged in!")
        except:
            pass

        if not is_logged_in:
            print("\n   ╔══════════════════════════════════════════════════╗")
            print("   ║  NOT LOGGED IN — Please log in to TikTok now    ║")
            print("   ║  The script will wait until you're done.        ║")
            print("   ╚══════════════════════════════════════════════════╝")
            await safe_goto(page, "https://www.tiktok.com/login", timeout=30000)

            for i in range(36):
                await asyncio.sleep(5)
                print(f"   Waiting for login... ({(i+1)*5}s)", end="\r", flush=True)
                try:
                    if "/login" not in page.url:
                        print("\n   Login detected!")
                        await asyncio.sleep(3)
                        break
                except:
                    pass
            print()

        # Load first hashtag
        print("\n[STEP 1] Loading first hashtag page...")
        first_tag = HASHTAGS[0]
        await safe_goto(page, f"https://www.tiktok.com/tag/{first_tag}", timeout=45000)
        await asyncio.sleep(4)

        # Check for captcha (should be rare with real Chrome)
        captcha_ok = await wait_for_captcha(page, f"#{first_tag}")

        if not captcha_ok:
            print("\n   Captcha detected. Solve it in the Chrome window.")
            print("   Waiting 60 more seconds...")
            await asyncio.sleep(60)

        # ── HASHTAGS ─────────────────────────────────────────────────
        print("\n[STEP 2] Searching hashtags for accounts...\n")

        for hashtag in HASHTAGS:
            try:
                usernames = await scrape_hashtag(page, hashtag, MAX_ACCOUNTS_PER_HASHTAG)
                for u in usernames:
                    if u.lower() not in SKIP_ACCOUNTS and u not in all_accounts:
                        all_accounts[u] = True
            except Exception as e:
                print(f"   Crash #{hashtag}: {e}")
                try:
                    await page.close()
                except:
                    pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)

            # Longer delay between hashtags to be less suspicious
            await human_delay(3.0, 6.0)

        total = len(all_accounts)
        print(f"\n[STEP 3] {total} unique accounts — checking for 90%+ slideshow pages...\n")

        # ── PROFILES ────────────────────────────────────────────────
        consecutive_timeouts = 0
        for idx, username in enumerate(list(all_accounts.keys()), 1):
            if idx > 1 and idx % 20 == 0:
                print(f"\n  [PAUSE] Cooling down after {idx} accounts ({len(results)} matches so far)...")
                await asyncio.sleep(random.uniform(15, 25))

            if consecutive_timeouts >= 4:
                print(f"\n  [RESTART] Too many timeouts, new page...")
                try:
                    await page.close()
                except:
                    pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)
                pass
                consecutive_timeouts = 0
                await asyncio.sleep(8)

            print(f"  [{idx}/{total}]", end="")
            try:
                profile = await scrape_profile(page, username, collector)
                if profile == "timeout":
                    consecutive_timeouts += 1
                elif profile:
                    consecutive_timeouts = 0
                    fit_score, notes = score_account(profile)
                    profile["fit_score"] = fit_score
                    profile["score_notes"] = notes
                    results.append(profile)
                    # Save incrementally
                    _sorted = sorted(results, key=lambda x: x["fit_score"], reverse=True)
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(_sorted, f, indent=2, ensure_ascii=False)
                    with open("competitor_pages_latest.json", "w", encoding="utf-8") as f:
                        json.dump(_sorted, f, indent=2, ensure_ascii=False)
                else:
                    consecutive_timeouts = 0
            except Exception as e:
                print(f" @{username} -> CRASH: {e}")
                consecutive_timeouts += 1
                try:
                    await page.close()
                except:
                    pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)
                pass

            # Longer delay between profiles
            await human_delay(2.0, 4.0)

        try:
            await context.close()
        except:
            pass

    # ── FINAL SAVE ──────────────────────────────────────────────────
    results.sort(key=lambda x: x["fit_score"], reverse=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open("competitor_pages_latest.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 65}")
    print(f"  DONE! {len(results)} competitor pages found (90%+ slideshows)")
    print(f"  (scanned {total} accounts)")
    print(f"  -> {OUTPUT_FILE}")
    print(f"{'=' * 65}")

    if results:
        print(f"\nTOP {min(20, len(results))} RESULTS:\n")
        for i, acc in enumerate(results[:20], 1):
            sr = acc['slideshow_ratio'] * 100
            print(f"  {i:2}. @{acc['username']} [{acc['format']}]")
            print(f"      {acc['followers']:,} followers | avg {acc['avg_views']:,} views | max {acc['max_views']:,} views | {sr:.0f}% slides")
            print(f"      Score: {acc['fit_score']}/11 | {', '.join(acc['score_notes'][:4])}")
            if acc['bio'] and acc['bio'] not in ["No bio yet.", ""]:
                print(f"      Bio: {acc['bio'][:100]}")
            if acc['bio_link']:
                print(f"      Link: {acc['bio_link']}")
            print()
    else:
        print("\nNo 90%+ slideshow accounts found.")
        print("Make sure you solved any captchas and were logged in.")


if __name__ == "__main__":
    asyncio.run(main())
