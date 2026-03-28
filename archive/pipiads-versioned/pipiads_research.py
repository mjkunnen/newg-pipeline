"""
PiPiAds Automated Competitor Research for NEWGARMENTS
- Applies filters: Shopify, Last 15 days, US/UK/DE/NL/FR, Sort by Ad Spent
- Searches multiple streetwear keywords
- Screenshots each step for verification
- Scrapes ad data and saves results
"""
import asyncio
import json
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
    "baggy jeans streetwear",
    "archive fashion",
    "oversized tee",
    "streetwear drop",
    "limited drop clothing",
    "mens streetwear",
]

COUNTRIES = ["United States", "United Kingdom", "Germany", "Netherlands", "France"]

all_captured_ads = []
api_ad_data = []


def on_response_factory(storage_list):
    """Create a response handler that stores API ad data."""
    async def handle(response):
        url = response.url
        try:
            if any(p in url for p in ["/api/", "/ad/", "/search", "/v1/", "/v2/", "adSearch", "query"]):
                if response.status == 200:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        extract_ads(body, storage_list)
        except:
            pass
    return handle


def extract_ads(data, storage):
    """Recursively extract ad-like objects."""
    if isinstance(data, dict):
        for key in ["list", "ads", "items", "records", "data", "results"]:
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict) and is_ad(item):
                        storage.append(item)
                return
        if "data" in data and isinstance(data["data"], dict):
            extract_ads(data["data"], storage)
        elif is_ad(data):
            storage.append(data)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and is_ad(item):
                storage.append(item)


def is_ad(d):
    signals = ["impression", "impressions", "like", "likes", "ad_text", "caption",
               "advertiser", "nick_name", "ad_id", "creative", "days", "video_url",
               "thumbnail", "cover", "landing_page", "cost", "spend", "ad_title"]
    return sum(1 for s in signals if s in d) >= 3


async def screenshot(page, name):
    path = SCREENSHOTS / f"{name}.png"
    await page.screenshot(path=str(path), full_page=False)
    print(f"  [SCREENSHOT] {name}.png")
    return path


async def safe_click(page, selector, description="element", timeout=5000):
    """Try to click an element, return True if successful."""
    try:
        el = page.locator(selector).first
        await el.wait_for(state="visible", timeout=timeout)
        await el.click()
        print(f"  [OK] Clicked: {description}")
        await page.wait_for_timeout(800)
        return True
    except Exception as e:
        print(f"  [WARN] Could not click {description}: {e}")
        return False


async def select_ecom_platform_shopify(page):
    """Select Shopify in the Ecom Platform filter."""
    print("\n[FILTER] Setting Ecom Platform = Shopify...")

    # Click the Ecom Platform dropdown
    ecom_input = page.locator('input[placeholder="Ecom Platform"]')
    await ecom_input.click()
    await page.wait_for_timeout(1000)
    await screenshot(page, "filter_ecom_opened")

    # Click Shopify option
    shopify = page.locator('text=Shopify').first
    try:
        await shopify.wait_for(state="visible", timeout=3000)
        await shopify.click()
        print("  [OK] Selected Shopify")
        await page.wait_for_timeout(500)
    except:
        # Try alternative: look for the option in dropdown
        options = page.locator('.select-item .select-search li, .el-select-dropdown__item')
        count = await options.count()
        for i in range(count):
            text = await options.nth(i).text_content()
            if text and "shopify" in text.lower().strip():
                await options.nth(i).click()
                print(f"  [OK] Selected Shopify (alt method)")
                break
        await page.wait_for_timeout(500)

    await screenshot(page, "filter_ecom_shopify_selected")


async def select_last_seen_15_days(page):
    """Set Last Seen to approximately last 15 days."""
    print("\n[FILTER] Setting Last Seen = Last 15 days...")

    # Click the Last seen date picker
    last_seen_input = page.locator('input[placeholder="Last seen"]')
    await last_seen_input.click()
    await page.wait_for_timeout(1000)
    await screenshot(page, "filter_lastseen_opened")

    # Try clicking "Last 30 days" as closest option, or set custom date
    # First check for quick filter buttons
    last30 = page.locator('text="Last 30 days"')
    last7 = page.locator('text="Last 7 days"')

    # Check if there are quick buttons visible
    try:
        # Look for the time filter row with quick options
        time_row = page.locator('.filter-time-types, .filter-item')
        buttons = time_row.locator('li, span, div').filter(has_text="Last")
        count = await buttons.count()
        print(f"  Found {count} time filter options")
        for i in range(count):
            text = (await buttons.nth(i).text_content()).strip()
            if text:
                print(f"    - {text}")
    except:
        pass

    # Try to use the date range picker for custom 15 days
    try:
        # Calculate 15 days ago
        end_date = datetime.now()
        start_date = end_date - timedelta(days=15)

        # Look for date range picker - it's an el-range input
        # Try clicking it to open the calendar
        date_container = page.locator('.select-item-date').nth(1)  # Second date picker (Last seen)
        await date_container.click()
        await page.wait_for_timeout(1000)
        await screenshot(page, "filter_lastseen_calendar")

        # Type the date range
        inputs = page.locator('.el-date-range-picker input.el-range-input, .el-range-input')
        input_count = await inputs.count()
        print(f"  Found {input_count} date range inputs")

        if input_count >= 4:  # There are Creation Date and Last Seen inputs
            # Last seen start (3rd input = index 2)
            start_input = inputs.nth(2)
            end_input = inputs.nth(3)
        elif input_count >= 2:
            start_input = inputs.nth(0)
            end_input = inputs.nth(1)
        else:
            raise Exception("Date inputs not found")

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        await start_input.click(click_count=3)
        await start_input.fill(start_str)
        await page.wait_for_timeout(300)
        await end_input.click(click_count=3)
        await end_input.fill(end_str)
        await page.wait_for_timeout(300)
        await page.keyboard.press("Enter")
        print(f"  [OK] Set Last Seen: {start_str} to {end_str}")

    except Exception as e:
        print(f"  [WARN] Custom date failed ({e}), trying Last 30 days button...")
        # Fallback: click Last 30 days from the quick filter bar
        try:
            await page.locator('.filter-time-types').locator('text="Last 30 days"').click()
            print("  [OK] Selected Last 30 days (fallback)")
        except:
            print("  [FAIL] Could not set date filter")

    await page.wait_for_timeout(500)
    await screenshot(page, "filter_lastseen_set")


async def select_countries(page):
    """Select US, UK, Germany, Netherlands, France."""
    print("\n[FILTER] Setting Countries = US, UK, DE, NL, FR...")

    country_input = page.locator('input[placeholder="Country/Region"]')
    await country_input.click()
    await page.wait_for_timeout(1000)
    await screenshot(page, "filter_country_opened")

    for country in COUNTRIES:
        try:
            await country_input.fill("")
            await page.wait_for_timeout(300)
            await country_input.fill(country)
            await page.wait_for_timeout(800)

            # Find and click the matching option
            option = page.locator(f'.el-select-dropdown__item, li, .option-item').filter(has_text=country).first
            await option.wait_for(state="visible", timeout=3000)
            await option.click()
            print(f"  [OK] Selected: {country}")
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"  [WARN] Could not select {country}: {e}")
            # Try clicking away and retrying
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
            await country_input.click()
            await page.wait_for_timeout(500)

    await screenshot(page, "filter_countries_set")


async def set_sort_by_ad_spent(page):
    """Set sort to Ad Spent."""
    print("\n[FILTER] Setting Sort = Ad Spent...")

    # Click the sort dropdown
    sort_el = page.locator('.el-select-sort, .select-type').first
    await sort_el.click()
    await page.wait_for_timeout(1000)
    await screenshot(page, "filter_sort_opened")

    # Find the ad spent option
    try:
        # Look for the option in dropdown
        spent_option = page.locator('.el-select-dropdown__item, .el-select-dropdown li').filter(has_text="Spent")
        if await spent_option.count() > 0:
            await spent_option.first.click()
            print("  [OK] Selected Sort by: Ad Spent")
        else:
            # Try other text variations
            for text in ["Ad Spent", "Spend", "Cost", "Budget", "Total Spend", "Estimated Spend"]:
                opt = page.locator(f'.el-select-dropdown__item').filter(has_text=text)
                if await opt.count() > 0:
                    await opt.first.click()
                    print(f"  [OK] Selected Sort by: {text}")
                    break
    except Exception as e:
        print(f"  [WARN] Could not set sort: {e}")

    await page.wait_for_timeout(500)
    await screenshot(page, "filter_sort_set")


async def scrape_visible_ads(page) -> list:
    """Scrape ad cards visible on the page."""
    ads = await page.evaluate("""() => {
        const ads = [];
        // Try multiple possible selectors for ad cards
        const cardSelectors = [
            '.ad-card', '.card-item', '.ad-item', '.result-item',
            '.video-card', '[class*="ad-card"]', '[class*="card-item"]',
            '.data-list-item', '.list-item', '.ad-list-item',
            '.data-view-list > div', '.main-content-list > div'
        ];

        let cards = [];
        for (const sel of cardSelectors) {
            const found = document.querySelectorAll(sel);
            if (found.length > 0) {
                cards = found;
                break;
            }
        }

        // If no cards found, try getting all major content blocks
        if (cards.length === 0) {
            // Look for the main results container
            const containers = document.querySelectorAll('[class*="list"], [class*="result"], [class*="content"]');
            for (const c of containers) {
                if (c.children.length > 3 && c.children.length < 100) {
                    cards = c.children;
                    break;
                }
            }
        }

        for (const card of cards) {
            const text = card.textContent || '';
            if (text.length < 20) continue;

            // Extract data from the card
            const ad = {
                full_text: text.substring(0, 500),
                // Try to find specific data points
                advertiser: '',
                impressions_text: '',
                likes_text: '',
                comments_text: '',
                shares_text: '',
                days_text: '',
                caption: '',
                landing_url: '',
            };

            // Look for links
            const links = card.querySelectorAll('a[href]');
            for (const link of links) {
                const href = link.href;
                if (href && !href.includes('pipiads')) {
                    ad.landing_url = href;
                }
                const linkText = link.textContent.trim();
                if (linkText.length > 5 && linkText.length < 50) {
                    ad.advertiser = ad.advertiser || linkText;
                }
            }

            // Look for numbers (impressions, likes etc.)
            const nums = text.match(/[\d,.]+[KMB]?\s*(impression|like|comment|share|day)/gi) || [];
            for (const n of nums) {
                const lower = n.toLowerCase();
                if (lower.includes('impression')) ad.impressions_text = n.trim();
                else if (lower.includes('like')) ad.likes_text = n.trim();
                else if (lower.includes('comment')) ad.comments_text = n.trim();
                else if (lower.includes('share')) ad.shares_text = n.trim();
                else if (lower.includes('day')) ad.days_text = n.trim();
            }

            // Get image/video thumbnail
            const img = card.querySelector('img');
            if (img) ad.thumbnail = img.src;

            ads.push(ad);
        }
        return ads;
    }""")
    return ads


async def search_keyword(page, keyword, keyword_index):
    """Search for a keyword and scrape results."""
    print(f"\n{'='*60}")
    print(f"[SEARCH {keyword_index}] Searching: '{keyword}'")
    print(f"{'='*60}")

    # Clear and type keyword
    search_input = page.locator('input[placeholder*="Search by any ad keyword"]')
    await search_input.click(click_count=3)
    await page.wait_for_timeout(300)
    await search_input.fill(keyword)
    await page.wait_for_timeout(500)

    # Click search button
    search_btn = page.locator('button.btn-search').first
    await search_btn.click()
    print(f"  [OK] Search submitted for: {keyword}")

    # Wait for results to load
    await page.wait_for_timeout(5000)
    await screenshot(page, f"search_{keyword_index}_{keyword.replace(' ', '_')}_results")

    # Check API intercepted data
    pre_count = len(api_ad_data)

    # Scroll down to load more results
    for scroll_i in range(3):
        await page.evaluate("window.scrollBy(0, 800)")
        await page.wait_for_timeout(2000)

    await screenshot(page, f"search_{keyword_index}_{keyword.replace(' ', '_')}_scrolled")

    # Also scrape DOM
    dom_ads = await scrape_visible_ads(page)
    api_new = len(api_ad_data) - pre_count

    print(f"  [DATA] API captured: {api_new} new ads | DOM scraped: {len(dom_ads)} cards")

    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(500)

    return {
        "keyword": keyword,
        "api_ads_captured": api_new,
        "dom_ads": dom_ads,
        "timestamp": datetime.now().isoformat(),
    }


async def main():
    print("=" * 60)
    print("NEWGARMENTS - PiPiAds Automated Competitor Research")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )

        # Load cookies
        if COOKIES.exists():
            try:
                cookies = json.loads(COOKIES.read_text())
                await context.add_cookies(cookies)
                print("[+] Loaded saved cookies")
            except:
                pass

        page = await context.new_page()

        # Set up API interception
        page.on("response", on_response_factory(api_ad_data))

        # Navigate
        print("[+] Opening PiPiAds...")
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(2000)

        # Check login
        if "login" in page.url.lower():
            print("[!] LOGIN REQUIRED - please log in...")
            await page.wait_for_url("**/ad-search**", timeout=120000)
            await page.wait_for_timeout(3000)

        # Save cookies
        cookies = await context.cookies()
        COOKIES.write_text(json.dumps(cookies, default=str))

        await screenshot(page, "research_start")
        print("[+] Logged in, starting filter setup...\n")

        # ==========================================
        # STEP 1: Select platform TikTok (should be default)
        # ==========================================
        print("[FILTER] Ensuring TikTok platform is selected...")
        tiktok_tab = page.locator('.filter-ad-types').locator('text="TikTok"').first
        try:
            await tiktok_tab.click()
            print("  [OK] TikTok selected")
        except:
            print("  [INFO] TikTok may already be selected")
        await page.wait_for_timeout(500)

        # ==========================================
        # STEP 2: Select E-commerce / Dropshipping type
        # ==========================================
        print("[FILTER] Selecting Dropshipping ad type...")
        try:
            drop_tab = page.locator('.filter-data-types').locator('text="Dropshipping"').first
            await drop_tab.click()
            print("  [OK] Dropshipping selected")
        except:
            try:
                ecom_tab = page.locator('.filter-data-types').locator('text="E-commerce"').first
                await ecom_tab.click()
                print("  [OK] E-commerce selected")
            except:
                print("  [INFO] Using default ad type")
        await page.wait_for_timeout(500)
        await screenshot(page, "filter_platform_type")

        # ==========================================
        # STEP 3: Ecom Platform = Shopify
        # ==========================================
        await select_ecom_platform_shopify(page)

        # ==========================================
        # STEP 4: Last Seen = 15 days
        # ==========================================
        await select_last_seen_15_days(page)

        # ==========================================
        # STEP 5: Countries
        # ==========================================
        await select_countries(page)

        # ==========================================
        # STEP 6: Sort by Ad Spent
        # ==========================================
        await set_sort_by_ad_spent(page)

        await screenshot(page, "all_filters_applied")
        print("\n[+] All filters applied! Starting keyword searches...\n")

        # ==========================================
        # STEP 7: Search each keyword
        # ==========================================
        all_results = []
        for i, keyword in enumerate(KEYWORDS, 1):
            try:
                result = await search_keyword(page, keyword, i)
                all_results.append(result)

                # Save intermediate results
                save_path = DATA_DIR / f"pipiads_research_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "search_results": all_results,
                        "api_captured_ads": api_ad_data,
                        "total_api_ads": len(api_ad_data),
                        "timestamp": datetime.now().isoformat(),
                    }, f, indent=2, ensure_ascii=False, default=str)

            except Exception as e:
                print(f"  [ERROR] Search failed for '{keyword}': {e}")
                await screenshot(page, f"error_{i}_{keyword.replace(' ', '_')}")

            # Small delay between searches
            await page.wait_for_timeout(2000)

        # ==========================================
        # FINAL: Summary screenshot and save
        # ==========================================
        await screenshot(page, "research_complete")

        # Save final results
        final_path = DATA_DIR / f"pipiads_research_FINAL_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump({
                "search_results": all_results,
                "api_captured_ads": api_ad_data,
                "total_api_ads": len(api_ad_data),
                "filters_used": {
                    "platform": "TikTok",
                    "ecom_platform": "Shopify",
                    "last_seen": "15 days",
                    "countries": COUNTRIES,
                    "sort": "Ad Spent",
                },
                "keywords": KEYWORDS,
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n{'='*60}")
        print(f"RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"Total API-captured ads: {len(api_ad_data)}")
        print(f"Keywords searched: {len(all_results)}/{len(KEYWORDS)}")
        print(f"Results saved to: {final_path.name}")
        print(f"Screenshots in: {SCREENSHOTS}")
        print(f"\nKeeping browser open for 30 seconds for manual review...")

        await page.wait_for_timeout(30000)
        await browser.close()

    print("[+] Done!")


if __name__ == "__main__":
    asyncio.run(main())
