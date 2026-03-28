"""
NEWGARMENTS — TikTok Creator Finder v5
========================================
Slideshow detectie via TikTok's interne API response.
Intercepteert netwerk requests om post-data te lezen.
100% accurate: checkt image_post_info per post.
"""

import asyncio
import json
import random
import sys
import io
import re
from datetime import datetime
from playwright.async_api import async_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ─── CONFIG ────────────────────────────────────────────────────────────────────

HASHTAGS = [
    "streetwearstyle",
    "streetwearbrand",
    "streetwearfashion",
    "tiktokfashion",
    "tiktokstreetwear",
    "baggyfit",
    "baggyjeans",
    "baggyclothes",
    "oversizedfit",
    "oversizedstreetwear",
    "streetweararchive",
    "archivefashion",
    "clothingbrand",
    "streetweardrops",
    "heavyweighttee",
    "newdrop",
    "fashiontiktok",
    "streetwearinspo",
    "outfitinspo",
]

MAX_ACCOUNTS_PER_HASHTAG = 20
MIN_SLIDESHOW_RATIO = 0.30
MIN_FOLLOWERS = 1000
WESTERN_ONLY = True  # Filter voor UK/US/EU accounts
LOGIN_WAIT = 60
# Proxy configuratie — Oxylabs residential proxy aanbevolen
# Oxylabs formaat: "http://customer-USERNAME:PASSWORD@pr.oxylabs.io:7777"
# Laat leeg voor geen proxy
PROXY = ""
OUTPUT_FILE = f"newgarments_creators_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

# ─── HELPERS ───────────────────────────────────────────────────────────────────

async def human_delay(min_s=1.0, max_s=2.5):
    await asyncio.sleep(random.uniform(min_s, max_s))

def is_western_account(username, bio):
    """Filter out non-Western (ID, SEA, Arabic, CJK) accounts based on bio & username."""
    bio_lower = (bio or "").lower()
    username_lower = username.lower()

    # Indonesian / SEA keywords in bio
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

    # Username ending with .id or containing "indo"
    if username_lower.endswith(".id") or "indonesia" in username_lower:
        return False

    # Check for non-Latin heavy text in bio (CJK, Arabic, Thai, etc.)
    if bio:
        non_latin = sum(1 for c in bio if ord(c) > 0x024F and not (0x2000 <= ord(c) <= 0x27FF) and not (0xFE00 <= ord(c) <= 0xFEFF) and not (0x1F000 <= ord(c) <= 0x1FAFF))
        latin = sum(1 for c in bio if c.isascii() and c.isalpha())
        # If more than 40% non-Latin chars and few Latin chars, likely non-Western
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

async def safe_goto(page, url, timeout=30000):
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
            await asyncio.sleep(random.uniform(0.5, 1.0))
        except:
            break

# ─── API INTERCEPTOR ─────────────────────────────────────────────────────────

class PostDataCollector:
    """
    Intercepteert TikTok API responses om post metadata te vangen.
    Kijkt naar /api/post/item_list en SIGI_STATE in de HTML.
    """
    def __init__(self):
        self.posts = []  # lijst van post dicts
        self.raw_items = []

    def reset(self):
        self.posts = []
        self.raw_items = []

    async def intercept_response(self, response):
        """Callback voor page.on('response')"""
        url = response.url
        try:
            # Methode 1: API endpoint voor user posts
            if "/api/post/item_list" in url or "/api/item_list" in url:
                data = await response.json()
                items = data.get("itemList", data.get("items", []))
                self.raw_items.extend(items)

            # Methode 2: Alternatieve API endpoints
            elif "/api/recommend/item_list" in url:
                data = await response.json()
                items = data.get("itemList", [])
                self.raw_items.extend(items)
        except:
            pass

    def analyze_posts(self):
        """Verwerk raw items naar slideshow/video classificatie"""
        self.posts = []
        for item in self.raw_items:
            post = {
                "id": item.get("id", ""),
                "is_slideshow": False,
                "views": 0,
                "likes": 0,
                "comments": 0,
            }

            # Slideshow detectie: image_post_info aanwezig = slideshow
            if item.get("imagePost") or item.get("image_post_info"):
                post["is_slideshow"] = True
            elif item.get("photo_images") or item.get("photoImages"):
                post["is_slideshow"] = True

            # Stats
            stats = item.get("stats", {})
            post["views"] = stats.get("playCount", 0)
            post["likes"] = stats.get("diggCount", 0)
            post["comments"] = stats.get("commentCount", 0)

            self.posts.append(post)

        return self.posts


async def extract_sigi_state(page):
    """
    Extraheert SIGI_STATE uit de pagina — TikTok's server-side rendered data.
    Bevat alle post-info inclusief of het een slideshow is.
    """
    posts_data = []
    try:
        # TikTok slaat initial data op in window.__UNIVERSAL_DATA_FOR_REHYDRATION__
        # of in een <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"> tag
        # of SIGI_STATE
        sigi = await page.evaluate("""() => {
            // Methode 1: SIGI_STATE
            if (window.SIGI_STATE) return JSON.stringify(window.SIGI_STATE);
            // Methode 2: __UNIVERSAL_DATA_FOR_REHYDRATION__
            if (window.__UNIVERSAL_DATA_FOR_REHYDRATION__)
                return JSON.stringify(window.__UNIVERSAL_DATA_FOR_REHYDRATION__);
            // Methode 3: Zoek in script tags
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                const text = s.textContent || '';
                if (text.includes('ItemModule') || text.includes('imagePost')) {
                    // Probeer JSON te parsen
                    const match = text.match(/\\{.*ItemModule.*\\}/s);
                    if (match) return match[0];
                }
            }
            return null;
        }""")

        if not sigi:
            return posts_data

        data = json.loads(sigi)

        # Zoek posts in de data structuur
        # SIGI_STATE heeft ItemModule met post IDs als keys
        item_module = None

        if "ItemModule" in data:
            item_module = data["ItemModule"]
        elif "default" in data:
            scope = data["default"]
            if isinstance(scope, dict):
                # Zoek in webapp.video-detail of webapp.user-detail
                for key, val in scope.items():
                    if isinstance(val, dict):
                        if "itemList" in val:
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

    except Exception as e:
        pass  # Silently fail — we have fallback

    return posts_data


async def detect_slideshows_combined(page, collector):
    """
    Combineert alle detectiemethoden:
    1. SIGI_STATE / __UNIVERSAL_DATA__ (server-side data)
    2. API response interceptor
    3. Fallback: URL /photo/ vs /video/ check
    """
    all_posts = []

    # Methode 1: SIGI_STATE
    sigi_posts = await extract_sigi_state(page)
    if sigi_posts:
        all_posts.extend(sigi_posts)

    # Methode 2: Intercepted API data
    if collector.raw_items:
        api_posts = collector.analyze_posts()
        # Merge (dedup op ID)
        existing_ids = {p["id"] for p in all_posts}
        for p in api_posts:
            if p["id"] not in existing_ids:
                all_posts.append(p)

    # Methode 3: Fallback — check href attributen
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

    # Tel
    slideshow_count = sum(1 for p in all_posts if p.get("is_slideshow"))
    video_count = sum(1 for p in all_posts if not p.get("is_slideshow"))
    total = len(all_posts)

    # Views uit posts
    views = [p["views"] for p in all_posts if p.get("views", 0) > 0]

    return slideshow_count, video_count, total, views


# ─── HASHTAG SCRAPER ──────────────────────────────────────────────────────────

async def scrape_hashtag(page, hashtag, max_accounts):
    print(f"\n[ZOEK] #{hashtag}")
    accounts = []

    if not await safe_goto(page, f"https://www.tiktok.com/tag/{hashtag}"):
        print(f"   FOUT: laadde niet")
        return accounts

    await asyncio.sleep(random.uniform(3, 5))

    # Check voor captcha op hashtag pagina
    try:
        body_text = await page.inner_text("body")
        if "slider" in body_text.lower() or "puzzle" in body_text.lower():
            print(f"   CAPTCHA! Los op in de browser...", end=" ", flush=True)
            for _ in range(12):  # max 60s wachten
                await asyncio.sleep(5)
                links_check = await page.query_selector_all('a[href*="/@"]')
                if len(links_check) > 2:
                    print("OK!")
                    break
            else:
                print("timeout")
    except:
        pass

    await scroll_page(page, rounds=6, distance=800)

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
        print(f"   FOUT: {e}")

    # Debug: als geen accounts gevonden, screenshot maken
    if not accounts:
        try:
            await page.screenshot(path=f"debug_hashtag_{hashtag}.png")
            print(f"   DEBUG: screenshot opgeslagen als debug_hashtag_{hashtag}.png")
            # Check page URL om te zien of we geredirect zijn
            print(f"   DEBUG: huidige URL = {page.url}")
        except:
            pass

    print(f"   -> {len(accounts)} accounts")
    return accounts

# ─── PROFIEL SCRAPER ─────────────────────────────────────────────────────────

async def scrape_profile(page, context, username, collector):
    print(f" @{username}", end="", flush=True)

    profile = {
        "username": username,
        "url": f"https://www.tiktok.com/@{username}",
        "followers": 0, "following": 0, "likes": 0,
        "bio": "", "bio_link": "",
        "avg_views": 0,
        "slideshow_posts": 0, "video_posts": 0,
        "total_checked": 0, "slideshow_ratio": 0.0,
        "format": "", "detection_method": "",
        "scraped_at": datetime.now().isoformat(),
    }

    # Reset collector voor deze user
    collector.reset()

    if not await safe_goto(page, f"https://www.tiktok.com/@{username}"):
        print(f" -> timeout")
        return "timeout"

    await asyncio.sleep(random.uniform(2, 4))

    # Followers
    try:
        el = await page.query_selector('[data-e2e="followers-count"]')
        if el:
            profile["followers"] = parse_count(await el.inner_text())
    except:
        pass

    if profile["followers"] < MIN_FOLLOWERS:
        print(f" -> SKIP (<{MIN_FOLLOWERS})")
        return None

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

    # Western market filter — skip non-Western accounts early
    if WESTERN_ONLY and not is_western_account(username, profile["bio"]):
        print(f" -> SKIP (non-Western)")
        return None

    # Bio link
    try:
        link_el = await page.query_selector('[data-e2e="user-link"] a, a[href*="link.tiktok"], [data-e2e="user-bio-link"] a')
        if link_el:
            profile["bio_link"] = (await link_el.get_attribute("href") or await link_el.inner_text() or "").strip()
        if not profile["bio_link"]:
            # Fallback: extract URL from bio text
            import re as _re
            url_match = _re.search(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,})(?:/\S*)?', profile["bio"])
            if url_match:
                profile["bio_link"] = url_match.group(0)
    except:
        pass

    # Scroll om posts te laden + API calls te triggeren
    await scroll_page(page, rounds=4, distance=600)
    await asyncio.sleep(1)

    # ── SLIDESHOW DETECTIE (alle methoden) ───────────────────────
    slide_count, vid_count, total, post_views = await detect_slideshows_combined(page, collector)

    profile["slideshow_posts"] = slide_count
    profile["video_posts"] = vid_count
    profile["total_checked"] = total

    # Detectie methode loggen
    if collector.raw_items:
        profile["detection_method"] = "api_intercept"
    else:
        profile["detection_method"] = "sigi_state_or_url"

    # Views
    if post_views:
        profile["avg_views"] = int(sum(post_views) / len(post_views))
    else:
        # Fallback: lees van pagina
        try:
            view_els = await page.query_selector_all('[data-e2e="video-views"]')
            views = []
            for el in view_els[:8]:
                v = parse_count(await el.inner_text())
                if v > 0:
                    views.append(v)
            if views:
                profile["avg_views"] = int(sum(views) / len(views))
        except:
            pass

    if total > 0:
        profile["slideshow_ratio"] = round(slide_count / total, 2)

    # Format label
    if total == 0:
        print(f" -> SKIP (geen posts)")
        return None
    elif profile["slideshow_ratio"] >= 0.8:
        profile["format"] = "slideshow-only"
    elif profile["slideshow_ratio"] >= 0.5:
        profile["format"] = "slideshow-heavy"
    elif profile["slideshow_ratio"] >= MIN_SLIDESHOW_RATIO:
        profile["format"] = "slideshow-mix"
    else:
        profile["format"] = "video-dominant"

    # Filter
    if slide_count == 0:
        print(f" -> SKIP (0/{total} slides) [{profile['detection_method']}]")
        return None

    if profile["slideshow_ratio"] < MIN_SLIDESHOW_RATIO:
        print(f" -> SKIP ({slide_count}/{total}={profile['slideshow_ratio']*100:.0f}%) [{profile['detection_method']}]")
        return None

    print(f" -> OK! {slide_count}/{total} slides ({profile['slideshow_ratio']*100:.0f}%) | {profile['followers']:,} flw [{profile['detection_method']}]")
    return profile

# ─── SCORING ──────────────────────────────────────────────────────────────────

def score_account(p):
    score = 0
    notes = []
    flw = p.get("followers", 0)
    avg = p.get("avg_views", 0)
    bio = p.get("bio", "").lower()
    sr = p.get("slideshow_ratio", 0)

    if flw > 0 and avg > 0:
        ratio = avg / flw
        if ratio >= 0.3:
            score += 3; notes.append(f"Engagement {ratio:.1f}x")
        elif ratio >= 0.1:
            score += 2; notes.append(f"Engagement {ratio:.1f}x")
        elif ratio >= 0.05:
            score += 1; notes.append(f"Engagement {ratio:.2f}x")

    if sr >= 0.8:
        score += 2; notes.append("Slideshow-only")
    elif sr >= 0.5:
        score += 1; notes.append("Slideshow-heavy")

    if 5_000 <= flw <= 100_000:
        score += 2; notes.append(f"Micro ({flw:,})")
    elif 100_000 < flw <= 500_000:
        score += 1; notes.append(f"Mid-tier ({flw:,})")

    # Positive: product/store/brand signals
    for kw in ["archive", "streetwear", "store", "shop", "brand", "clothing",
               "drop", "showcase", "baggy", "oversized", "heavyweight",
               "worldwide shipping", "dm for promo", "collab", "fashion"]:
        if kw in bio:
            score += 1; notes.append(f"Bio: '{kw}'"); break

    # Negative: fast fashion, personal, or irrelevant
    for kw in ["shein", "amazon", "aliexpress", "fast fashion", "dropship", "asos",
               "y2k", "anime", "kpop", "makeup", "skincare", "cooking"]:
        if kw in bio:
            score -= 3; notes.append(f"RED FLAG: '{kw}'"); break

    return max(0, score), notes

# ─── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  NEWGARMENTS — TikTok Creator Finder v5")
    print("  API intercept + SIGI_STATE + URL fallback")
    print("=" * 60)

    all_accounts = {}
    results = []

    async with async_playwright() as p:
        launch_opts = {
            "headless": False,
            "args": ["--start-maximized"],
        }
        if PROXY:
            launch_opts["proxy"] = {"server": PROXY}
            print(f"[PROXY] Verbinden via {PROXY}")

        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.4 Mobile/15E148 Safari/604.1"
            ),
            is_mobile=True,
            has_touch=True,
            device_scale_factor=3,
        )

        # Setup API interceptor
        collector = PostDataCollector()

        page = await context.new_page()
        page.on("response", collector.intercept_response)

        # ── LOGIN ────────────────────────────────────────────────────
        print(f"\n[LOGIN] Log in op TikTok ({LOGIN_WAIT}s)")
        await page.goto("https://www.tiktok.com/login", timeout=60000)
        for i in range(LOGIN_WAIT, 0, -5):
            print(f"   {i}s...", end=" ", flush=True)
            await asyncio.sleep(5)
        print("\n")

        # ── CAPTCHA CHECK ──────────────────────────────────────────────
        # Laad eerste hashtag en wacht tot user captcha oplost
        first_tag = HASHTAGS[0]
        print(f"[CAPTCHA CHECK] Laden van #{first_tag}...")
        await safe_goto(page, f"https://www.tiktok.com/tag/{first_tag}", timeout=30000)
        await asyncio.sleep(3)

        # Check of er een captcha is
        captcha = await page.query_selector('[class*="captcha"], [class*="Captcha"], [id*="captcha"]')
        page_text = await page.inner_text("body") if not captcha else ""
        has_slider = "slider" in page_text.lower() or "puzzle" in page_text.lower() or captcha
        if has_slider:
            print("[CAPTCHA] Captcha gedetecteerd! Los hem handmatig op in de browser.")
            print("   Wacht tot de pagina content toont (30s)...")
            for i in range(30, 0, -5):
                print(f"   {i}s...", end=" ", flush=True)
                await asyncio.sleep(5)
                # Check of captcha weg is
                try:
                    links = await page.query_selector_all('a[href*="/@"]')
                    if len(links) > 2:
                        print("\n   Captcha opgelost!")
                        break
                except:
                    pass
            print()

        # ── HASHTAGS ─────────────────────────────────────────────────
        print("[STAP 1] Hashtags doorzoeken...\n")
        for hashtag in HASHTAGS:
            try:
                usernames = await scrape_hashtag(page, hashtag, MAX_ACCOUNTS_PER_HASHTAG)
                for u in usernames:
                    if u not in all_accounts:
                        all_accounts[u] = True
            except Exception as e:
                print(f"   Crash #{hashtag}: {e}")
                try: await page.close()
                except: pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)
            await human_delay(1.5, 3)

        total = len(all_accounts)
        print(f"\n[STAP 2] {total} unieke accounts — slideshow filter...\n")

        # ── PROFIELEN ────────────────────────────────────────────────
        consecutive_timeouts = 0
        for idx, username in enumerate(list(all_accounts.keys()), 1):
            # Batch pause elke 30 accounts
            if idx > 1 and idx % 30 == 0:
                print(f"\n  [PAUZE] Even wachten na {idx} accounts...")
                await asyncio.sleep(random.uniform(10, 15))

            # Als te veel timeouts, herstart browser pagina
            if consecutive_timeouts >= 5:
                print(f"\n  [HERSTART] Te veel timeouts, nieuwe pagina...")
                try: await page.close()
                except: pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)
                consecutive_timeouts = 0
                await asyncio.sleep(5)

            print(f"  [{idx}/{total}]", end="")
            try:
                profile = await scrape_profile(page, context, username, collector)
                if profile == "timeout":
                    consecutive_timeouts += 1
                elif profile:
                    consecutive_timeouts = 0
                    fit_score, notes = score_account(profile)
                    profile["fit_score"] = fit_score
                    profile["score_notes"] = notes
                    results.append(profile)
                    # Incrementeel opslaan
                    _sorted = sorted(results, key=lambda x: x["fit_score"], reverse=True)
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                        json.dump(_sorted, f, indent=2, ensure_ascii=False)
                else:
                    consecutive_timeouts = 0
            except Exception as e:
                print(f" @{username} -> CRASH: {e}")
                consecutive_timeouts += 1
                try: await page.close()
                except: pass
                page = await context.new_page()
                page.on("response", collector.intercept_response)
            await human_delay(1.0, 2.2)

        try: await browser.close()
        except: pass

    # ── OPSLAAN ──────────────────────────────────────────────────────
    results.sort(key=lambda x: x["fit_score"], reverse=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Ook opslaan als latest
    with open("newgarments_creators_latest.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"  KLAAR! {len(results)} slideshow creators")
    print(f"  (van {total} gescand)")
    print(f"  -> {OUTPUT_FILE}")
    print(f"{'=' * 60}")

    if results:
        print(f"\nTOP {min(15, len(results))}:\n")
        for i, acc in enumerate(results[:15], 1):
            sr = acc['slideshow_ratio'] * 100
            print(f"  {i:2}. @{acc['username']} [{acc['format']}]")
            print(f"      {acc['followers']:,} flw | {acc['avg_views']:,} avg views | {sr:.0f}% slides")
            print(f"      Score: {acc['fit_score']}/8 | {', '.join(acc['score_notes'][:3])}")
            print(f"      Detectie: {acc['detection_method']}")
            if acc['bio'] and acc['bio'] not in ["No bio yet.", ""]:
                print(f"      Bio: {acc['bio'][:80]}")
            print()
    else:
        print("\nGeen slideshow accounts gevonden.")
        print("Check of je was ingelogd en of TikTok niet geblokkeerd is.")


if __name__ == "__main__":
    asyncio.run(main())
