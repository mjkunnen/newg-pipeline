"""
PiPiAds Automated Research v2 - FIXED
Fixes: Country selection (readonly input), Sort by Ad Spend, Last Seen filter,
       DOM scraping (targets actual ad cards), API interception patterns.
"""
import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

SCREENSHOTS = Path(__file__).parent / "pipiads_screenshots"
SCREENSHOTS.mkdir(exist_ok=True)
DATA_DIR = Path(__file__).parent / "pipiads_data"
DATA_DIR.mkdir(exist_ok=True)
COOKIES = DATA_DIR / "pipiads_cookies.json"

KEYWORDS = [
    "streetwear",
    "oversized hoodie",
    "heavyweight hoodie",
    "streetwear brand",
    "baggy jeans",
    "archive fashion",
    "oversized tee",
    "streetwear drop",
    "limited drop clothing",
    "mens streetwear",
]

# Countries to select (as shown in the PiPiAds checkbox list)
COUNTRIES = ["United States", "United Kingdom", "Germany", "Netherlands", "France"]

# Store ALL intercepted network data
api_responses = []
all_ad_data = []


async def intercept_all_responses(response):
    """Capture ALL API responses to find ad data endpoints."""
    url = response.url
    try:
        if response.status == 200 and "pipiads" in url:
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = await response.json()
                    # Log the endpoint for debugging
                    api_responses.append({
                        "url": url,
                        "keys": list(body.keys()) if isinstance(body, dict) else "list",
                        "size": len(json.dumps(body, default=str)),
                    })
                    # Try to extract ads
                    ads = find_ads_deep(body)
                    if ads:
                        all_ad_data.extend(ads)
                        print(f"  [API] +{len(ads)} ads from {url.split('/')[-1][:50]}")
                except:
                    pass
    except:
        pass


def find_ads_deep(data, depth=0):
    """Recursively search for ad-like objects in any nested structure."""
    if depth > 5:
        return []
    ads = []
    if isinstance(data, dict):
        # Check if this dict itself looks like an ad
        if is_ad_object(data):
            ads.append(data)
            return ads
        # Search all values
        for key, val in data.items():
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and is_ad_object(item):
                        ads.append(item)
                if not ads:
                    for item in val:
                        if isinstance(item, dict):
                            ads.extend(find_ads_deep(item, depth + 1))
            elif isinstance(val, dict):
                ads.extend(find_ads_deep(val, depth + 1))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if is_ad_object(item):
                    ads.append(item)
                else:
                    ads.extend(find_ads_deep(item, depth + 1))
    return ads


def is_ad_object(d):
    """Check if dict looks like an ad with metrics."""
    ad_keys = {"impression", "impressions", "like", "likes", "comment", "comments",
               "share", "shares", "ad_text", "caption", "text", "advertiser",
               "nick_name", "advertiser_name", "ad_id", "id", "creative_id",
               "video_url", "video", "thumbnail", "cover", "cover_url",
               "landing_page", "landing_url", "cost", "spend", "ad_spend",
               "days", "days_running", "run_days", "duration", "cta", "country",
               "total_like", "total_comment", "total_share", "digg_count"}
    matches = sum(1 for k in d.keys() if k.lower() in ad_keys or any(s in k.lower() for s in ["impress", "like", "share", "spend", "video", "cover", "land"]))
    return matches >= 3


async def screenshot(page, name):
    path = SCREENSHOTS / f"v2_{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    print(f"  [SCREENSHOT] v2_{name}.png")


async def apply_filters(page):
    """Apply all filters step by step with screenshots."""

    # ==============================
    # 1. TikTok platform
    # ==============================
    print("\n[1/6] Selecting TikTok platform...")
    try:
        tiktok_btn = page.locator('li, span, div').filter(has_text=re.compile(r"^TikTok$")).first
        await tiktok_btn.click()
        await page.wait_for_timeout(800)
        print("  [OK] TikTok selected")
    except Exception as e:
        print(f"  [INFO] TikTok may already be active: {e}")

    # ==============================
    # 2. Dropshipping type
    # ==============================
    print("\n[2/6] Selecting Dropshipping...")
    try:
        drop_btn = page.locator('li, span, div').filter(has_text=re.compile(r"^Dropshipping$")).first
        await drop_btn.click()
        await page.wait_for_timeout(800)
        print("  [OK] Dropshipping selected")
    except:
        print("  [INFO] Dropshipping may already be active")

    await screenshot(page, "step1_platform")

    # ==============================
    # 3. Ecom Platform = Shopify
    # ==============================
    print("\n[3/6] Setting Ecom Platform = Shopify...")
    try:
        # The Shopify option is in the Category row - click the Ecom Platform dropdown
        ecom_dropdown = page.locator('.select-item.select-search').first
        await ecom_dropdown.click()
        await page.wait_for_timeout(800)

        # Now click Shopify from the visible options
        shopify_opt = page.locator('li, .el-select-dropdown__item, span').filter(has_text=re.compile(r"^Shopify$")).first
        await shopify_opt.click()
        await page.wait_for_timeout(500)

        # Click Apply button if there is one
        apply_btn = page.locator('button, div, span').filter(has_text=re.compile(r"^Apply$")).first
        try:
            await apply_btn.click(timeout=2000)
        except:
            pass

        print("  [OK] Shopify selected")
    except Exception as e:
        print(f"  [WARN] Shopify: {e}")

    await page.wait_for_timeout(500)
    await screenshot(page, "step2_shopify")

    # ==============================
    # 4. Last Seen = pick date range
    # ==============================
    print("\n[4/6] Setting Last Seen filter...")
    try:
        # Click on the "Last seen" text/area to open that specific date picker
        last_seen_label = page.locator('text="Last seen"').first
        await last_seen_label.click()
        await page.wait_for_timeout(1000)
        await screenshot(page, "step3_lastseen_clicked")

        # Now we should see a date picker. Let's look for date inputs that are visible
        # The Last Seen area should now have an active picker
        # Try setting dates via the visible range inputs
        date_15_ago = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        date_today = datetime.now().strftime("%Y-%m-%d")

        # Find visible el-range-input elements
        range_inputs = page.locator('.el-range-input:visible')
        count = await range_inputs.count()
        print(f"  Found {count} visible date range inputs")

        if count >= 2:
            start_input = range_inputs.nth(0)
            end_input = range_inputs.nth(1)

            await start_input.click(click_count=3)
            await page.keyboard.type(date_15_ago)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(300)
            await end_input.click(click_count=3)
            await page.keyboard.type(date_today)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")
            print(f"  [OK] Last Seen: {date_15_ago} to {date_today}")
        else:
            # Fallback: try to use the quick buttons near "Last seen" row
            # Look for "Last 7 days" or "Last 30 days" in the Started row
            print("  [WARN] No visible date inputs, using Last 7 days button")
            try:
                last7 = page.locator('li, span, div').filter(has_text=re.compile(r"^Last 7 days$")).first
                await last7.click()
                print("  [OK] Selected Last 7 days (fallback)")
            except:
                pass

    except Exception as e:
        print(f"  [WARN] Last seen filter: {e}")

    await page.wait_for_timeout(500)
    await screenshot(page, "step3_lastseen_set")

    # ==============================
    # 5. Countries = US, UK, DE, NL, FR
    # ==============================
    print("\n[5/6] Setting Countries...")
    try:
        # The country dropdown is readonly - we need to click the container to open it
        # Find it by the "Country/Region" text or placeholder
        country_container = page.locator('.select-item.select-search').filter(
            has=page.locator('[placeholder="Country/Region"]')
        ).first

        # If that doesn't work, try clicking the input's parent
        try:
            await country_container.click()
        except:
            # Alternative: click the dropdown div directly
            country_input = page.locator('[placeholder="Country/Region"]')
            await country_input.click()

        await page.wait_for_timeout(1000)
        await screenshot(page, "step4_country_opened")

        # Now we should see a dropdown with checkboxes
        # The screenshot showed: United States, Japan, Australia, Canada, UAE, Vietnam, Philippines, Korea
        # We need to search/scroll to find our countries

        for country in COUNTRIES:
            try:
                # Look for a search input in the dropdown to type country name
                # The dropdown might have a search field
                search_in_dropdown = page.locator('.el-select-dropdown .el-input__inner:visible, .select-search input:visible, .popper-search input:visible')
                search_count = await search_in_dropdown.count()

                if search_count > 0:
                    # Type to search
                    await search_in_dropdown.first.fill(country)
                    await page.wait_for_timeout(500)

                # Click the checkbox/option for this country
                country_option = page.locator('li, label, .el-checkbox, .option-item, span').filter(
                    has_text=re.compile(re.escape(country))
                ).first
                await country_option.click(timeout=3000)
                print(f"  [OK] Selected: {country}")
                await page.wait_for_timeout(400)

                # Clear search if we typed
                if search_count > 0:
                    await search_in_dropdown.first.fill("")
                    await page.wait_for_timeout(300)

            except Exception as e:
                print(f"  [WARN] Could not select {country}: {str(e)[:80]}")

        # Click Apply if available
        try:
            apply_btn = page.locator('.select-item:visible button, .select-item:visible .btn-apply, .select-item:visible div').filter(
                has_text=re.compile(r"^Apply$")
            ).first
            await apply_btn.click(timeout=2000)
            print("  [OK] Clicked Apply")
        except:
            # Click outside to close dropdown
            await page.locator('.search-bar-container').first.click()

    except Exception as e:
        print(f"  [WARN] Country filter error: {str(e)[:100]}")

    await page.wait_for_timeout(500)
    await screenshot(page, "step4_countries_set")

    # ==============================
    # 6. Sort by Ad Spend
    # ==============================
    print("\n[6/6] Setting Sort = Ad Spend...")
    try:
        # The sort dropdown shows "Sort by: Last seen" - find and click it
        sort_trigger = page.locator('.el-select-sort, [class*="select-sort"]').first
        await sort_trigger.click()
        await page.wait_for_timeout(1000)
        await screenshot(page, "step5_sort_opened")

        # Now find "Ad Spend" option in the dropdown that appeared
        # Use force:true since the element was found but marked not visible
        spend_option = page.locator('.el-select-dropdown__item, .el-select-dropdown li').filter(
            has_text=re.compile(r"Spend", re.IGNORECASE)
        ).first

        # Try with force click since element exists but may be in a hidden dropdown layer
        await spend_option.click(force=True, timeout=5000)
        print("  [OK] Sort by Ad Spend selected")

    except Exception as e:
        print(f"  [WARN] Sort: {str(e)[:100]}")
        # Try alternative: use evaluate to click
        try:
            result = await page.evaluate("""() => {
                const items = document.querySelectorAll('.el-select-dropdown__item');
                for (const item of items) {
                    if (item.textContent.includes('Spend')) {
                        item.click();
                        return 'clicked: ' + item.textContent.trim();
                    }
                }
                // List all sort options for debugging
                const all = [];
                items.forEach(i => all.push(i.textContent.trim()));
                return 'options: ' + all.join(' | ');
            }""")
            print(f"  [JS] {result}")
        except Exception as e2:
            print(f"  [FAIL] Sort JS fallback: {e2}")

    await page.wait_for_timeout(500)
    await screenshot(page, "step5_sort_set")


async def scrape_ad_cards(page):
    """Scrape actual ad cards from the results grid."""
    ads = await page.evaluate(r"""() => {
        const ads = [];

        // PiPiAds ad cards are in a grid - look for the data-view or card containers
        // From the screenshot: each card has an image, metrics row (impressions, likes, comments, shares),
        // date range, caption text, advertiser info, and action buttons

        // Try common card container selectors
        const cardSelectors = [
            '.ad-card-item',
            '.data-view-list .card-item',
            '.card-list .card-item',
            '.ad-list .item',
            '.waterfall-item',
            '.ad-card',
            '[class*="card-item"]',
            '[class*="ad-item"]',
            '[class*="waterfall"]',
        ];

        let cards = [];
        for (const sel of cardSelectors) {
            cards = document.querySelectorAll(sel);
            if (cards.length > 0) break;
        }

        // If still nothing, find the main content area with multiple children that contain numbers
        if (cards.length === 0) {
            const allDivs = document.querySelectorAll('div');
            for (const div of allDivs) {
                const children = div.children;
                if (children.length >= 4 && children.length <= 50) {
                    let hasMetrics = 0;
                    for (const child of children) {
                        const text = child.textContent || '';
                        if (/\d+[.,]?\d*[KMB]?\s/.test(text) && text.length > 30 && text.length < 2000) {
                            hasMetrics++;
                        }
                    }
                    if (hasMetrics >= 3) {
                        cards = children;
                        break;
                    }
                }
            }
        }

        for (const card of cards) {
            const text = (card.textContent || '').trim();
            if (text.length < 30) continue;

            const ad = {};

            // Get all text content
            ad.raw_text = text.substring(0, 800);

            // Extract numbers with labels
            // Pattern: number followed by metric name, or metric icon + number
            const numPattern = /([\d,.]+[KMB]?)\s*/g;
            const numbers = [];
            let match;
            while ((match = numPattern.exec(text)) !== null) {
                numbers.push(match[1]);
            }
            ad.numbers = numbers;

            // Look for date ranges (e.g., "Mar 5, 2026 Nov 12, 2025")
            const datePattern = /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}/g;
            ad.dates = (text.match(datePattern) || []);

            // Alt date pattern: 2026-01-15
            const isoDatePattern = /\d{4}-\d{2}-\d{2}/g;
            const isoDates = text.match(isoDatePattern) || [];
            if (isoDates.length > 0) ad.iso_dates = isoDates;

            // Get links
            const links = card.querySelectorAll('a[href]');
            ad.links = [];
            for (const link of links) {
                ad.links.push({
                    text: (link.textContent || '').trim().substring(0, 100),
                    href: link.href,
                });
            }

            // Get image sources (thumbnails/covers)
            const imgs = card.querySelectorAll('img');
            ad.images = [];
            for (const img of imgs) {
                if (img.src && !img.src.includes('data:')) {
                    ad.images.push(img.src);
                }
            }

            // Try to identify specific fields by position or class
            // Look for spans/divs with specific metric-like content
            const spans = card.querySelectorAll('span, div, p');
            const metrics = [];
            for (const span of spans) {
                const st = (span.textContent || '').trim();
                // Look for patterns like "597.3K" or "3.5K" or "284"
                if (/^[\d,.]+[KMB]?$/.test(st) && st.length <= 10) {
                    metrics.push(st);
                }
                // Look for caption-like text (longer text without just numbers)
                if (st.length > 20 && st.length < 300 && !/^\d/.test(st)) {
                    if (!ad.caption || st.length > ad.caption.length) {
                        ad.caption = st;
                    }
                }
            }
            ad.metrics = metrics;

            // Get advertiser name - usually a short text near an avatar image
            const smallTexts = [];
            for (const span of spans) {
                const st = (span.textContent || '').trim();
                if (st.length > 2 && st.length < 40 && !(/^[\d,.]+[KMB]?$/.test(st))) {
                    smallTexts.push(st);
                }
            }
            ad.small_texts = smallTexts.slice(0, 10);

            ads.push(ad);
        }

        // Also return debug info
        return {
            ads: ads,
            debug: {
                total_divs: document.querySelectorAll('div').length,
                card_selector_used: cards.length > 0 ? (cards[0]?.className || 'array') : 'none',
                card_count: cards.length,
            }
        };
    }""")
    return ads


async def search_keyword(page, keyword, idx):
    """Search a keyword and scrape results."""
    kw_safe = keyword.replace(" ", "_")
    print(f"\n{'='*60}")
    print(f"[SEARCH {idx}/{len(KEYWORDS)}] '{keyword}'")
    print(f"{'='*60}")

    # Clear search and type new keyword
    search_input = page.locator('input[placeholder*="Search by any ad keyword"]')
    await search_input.click(click_count=3)
    await page.wait_for_timeout(200)
    await search_input.fill("")
    await page.wait_for_timeout(200)
    await search_input.fill(keyword)
    await page.wait_for_timeout(300)

    # Click search
    api_count_before = len(all_ad_data)
    search_btn = page.locator('button.btn-search, .search-btn button').first
    await search_btn.click()
    print("  Searching...")

    # Wait for results
    await page.wait_for_timeout(6000)
    await screenshot(page, f"search_{idx}_{kw_safe}")

    # Scroll to load more
    for i in range(4):
        await page.evaluate("window.scrollBy(0, 600)")
        await page.wait_for_timeout(1500)

    await screenshot(page, f"search_{idx}_{kw_safe}_scrolled")

    # Scrape DOM
    result = await scrape_ad_cards(page)
    dom_ads = result.get("ads", []) if isinstance(result, dict) else []
    debug = result.get("debug", {}) if isinstance(result, dict) else {}
    api_new = len(all_ad_data) - api_count_before

    print(f"  [RESULT] API: +{api_new} | DOM: {len(dom_ads)} cards | Debug: {debug}")

    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)

    return {
        "keyword": keyword,
        "dom_ads": dom_ads,
        "api_new": api_new,
        "debug": debug,
        "timestamp": datetime.now().isoformat(),
    }


async def main():
    print("=" * 60)
    print("NEWGARMENTS - PiPiAds Research v2 (Fixed)")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        # Load cookies
        if COOKIES.exists():
            try:
                cookies = json.loads(COOKIES.read_text())
                await context.add_cookies(cookies)
                print("[+] Loaded cookies")
            except:
                pass

        page = await context.new_page()
        page.on("response", intercept_all_responses)

        print("[+] Opening PiPiAds...")
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        # Login check
        if "login" in page.url.lower():
            print("[!] LOGIN REQUIRED - log in now...")
            await page.wait_for_url("**/ad-search**", timeout=120000)
            await page.wait_for_timeout(3000)

        # Save cookies
        cookies = await context.cookies()
        COOKIES.write_text(json.dumps(cookies, default=str))
        print("[+] Logged in!")
        await screenshot(page, "start")

        # Apply filters
        await apply_filters(page)

        # Log API endpoints found so far
        print(f"\n[DEBUG] API responses intercepted so far: {len(api_responses)}")
        for resp in api_responses[:10]:
            print(f"  {resp['url'][:80]}  keys={resp.get('keys', '?')}")

        # Save API debug info
        with open(DATA_DIR / "api_debug.json", "w") as f:
            json.dump(api_responses, f, indent=2, default=str)

        # Search all keywords
        all_results = []
        for i, keyword in enumerate(KEYWORDS, 1):
            try:
                result = await search_keyword(page, keyword, i)
                all_results.append(result)
            except Exception as e:
                print(f"  [ERROR] {keyword}: {e}")
                await screenshot(page, f"error_{i}_{keyword.replace(' ', '_')}")
            await page.wait_for_timeout(2000)

        # Final save
        final_path = DATA_DIR / f"pipiads_v2_FINAL_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump({
                "search_results": all_results,
                "api_captured_ads": all_ad_data,
                "api_endpoints_seen": api_responses,
                "total_api_ads": len(all_ad_data),
                "filters": {
                    "platform": "TikTok",
                    "type": "Dropshipping",
                    "ecom": "Shopify",
                    "last_seen": "15 days",
                    "countries": COUNTRIES,
                    "sort": "Ad Spend",
                },
                "keywords": KEYWORDS,
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n{'='*60}")
        print("RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"API ads captured: {len(all_ad_data)}")
        print(f"API endpoints seen: {len(api_responses)}")
        print(f"Searches completed: {len(all_results)}/{len(KEYWORDS)}")
        print(f"Saved to: {final_path.name}")

        # Keep browser open for review
        print("\nBrowser stays open 30s for manual review...")
        await page.wait_for_timeout(30000)
        await browser.close()

    print("[+] Done!")


if __name__ == "__main__":
    asyncio.run(main())
