"""
PiPiAds Research v3 — Intercept API requests to learn the payload format,
then replay searches with proper country/date filters via the API directly.
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

TARGET_REGIONS = ["US", "GB", "DE", "NL", "FR"]

captured_requests = []
captured_ads = []


async def main():
    print("=" * 60)
    print("NEWGARMENTS - PiPiAds Research v3")
    print("Targets: US, UK, DE, NL, FR only")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})

        if COOKIES.exists():
            try:
                cookies = json.loads(COOKIES.read_text())
                await context.add_cookies(cookies)
                print("[+] Loaded cookies")
            except:
                pass

        page = await context.new_page()

        # Intercept REQUESTS (not just responses) to capture the payload format
        async def on_request(request):
            if "search4/at/video/search" in request.url:
                try:
                    post = request.post_data
                    if post:
                        captured_requests.append({
                            "url": request.url,
                            "method": request.method,
                            "payload": json.loads(post) if post else None,
                            "headers": dict(request.headers),
                        })
                        print(f"  [REQ] Captured search request payload")
                except:
                    pass

        async def on_response(response):
            if "search4/at/video/search" in response.url and response.status == 200:
                try:
                    body = await response.json()
                    result = body.get("result", {})
                    items = result.get("list", []) if isinstance(result, dict) else []
                    if items:
                        for item in items:
                            regions = re.findall(r"'(\w{2})'", str(item.get("fetch_region", "")))
                            if not regions:
                                try:
                                    regions = item.get("fetch_region", [])
                                except:
                                    regions = []
                            # Filter: only keep ads targeting our regions
                            if any(r in TARGET_REGIONS for r in regions):
                                captured_ads.append(item)
                        matched_count = 0
                        for item in items:
                            rr = re.findall(r"'(\w{2})'", str(item.get("fetch_region", "")))
                            if any(r in TARGET_REGIONS for r in rr):
                                matched_count += 1
                        print(f"  [API] +{len(items)} total, {matched_count} matched US/UK/DE/NL/FR")
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        print("[+] Opening PiPiAds...")
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        if "login" in page.url.lower():
            print("[!] LOGIN REQUIRED")
            await page.wait_for_url("**/ad-search**", timeout=120000)
            await page.wait_for_timeout(3000)

        cookies = await context.cookies()
        COOKIES.write_text(json.dumps(cookies, default=str))
        print("[+] Logged in!")

        # Do one manual search to capture the request format
        print("\n[STEP 1] Capturing API request format...")
        search_input = page.locator('input[placeholder*="Search by any ad keyword"]')
        await search_input.click(click_count=3)
        await search_input.fill("streetwear")
        search_btn = page.locator('button.btn-search, .search-btn button').first
        await search_btn.click()
        await page.wait_for_timeout(5000)

        if not captured_requests:
            print("[!] No request captured. Trying again...")
            await search_input.click(click_count=3)
            await search_input.fill("hoodie")
            await search_btn.click()
            await page.wait_for_timeout(5000)

        if captured_requests:
            req = captured_requests[0]
            print(f"\n[+] Captured API format!")
            print(f"    URL: {req['url']}")
            print(f"    Method: {req['method']}")
            print(f"    Payload keys: {list(req['payload'].keys()) if req['payload'] else 'none'}")

            # Save for debugging
            with open(DATA_DIR / "api_request_format.json", "w") as f:
                json.dump(req, f, indent=2, default=str)

            payload = req["payload"]
            headers = req["headers"]

            print(f"\n    Full payload:")
            print(json.dumps(payload, indent=2))

            # Now replay with modified payload for each keyword + country filter
            print(f"\n[STEP 2] Running searches with country filter...")

            import aiohttp

            # Get cookies as string for requests
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies if "pipiads" in c.get("domain", "")])

            req_headers = {
                "Content-Type": "application/json",
                "Cookie": cookie_str,
                "Origin": "https://www.pipiads.com",
                "Referer": "https://www.pipiads.com/ad-search",
                "User-Agent": headers.get("user-agent", ""),
            }
            # Copy auth headers
            for k, v in headers.items():
                if k.lower() in ["authorization", "token", "x-token", "x-auth", "x-csrf"]:
                    req_headers[k] = v

            # Use page.evaluate to make fetch requests from the browser context
            for i, keyword in enumerate(KEYWORDS, 1):
                print(f"\n[SEARCH {i}/{len(KEYWORDS)}] '{keyword}' — US,UK,DE,NL,FR")

                # Modify payload
                search_payload = dict(payload)
                search_payload["keyword"] = keyword
                # Try setting region/country filter
                search_payload["fetch_region"] = TARGET_REGIONS
                search_payload["region"] = TARGET_REGIONS
                search_payload["country"] = TARGET_REGIONS
                # Sort by ad spend if there's a sort field
                if "sort" in search_payload:
                    search_payload["sort"] = "ad_spend"
                if "sort_by" in search_payload:
                    search_payload["sort_by"] = "ad_spend"
                if "order_by" in search_payload:
                    search_payload["order_by"] = "cost"

                # Fetch page 1 and 2
                for pg in [1, 2]:
                    search_payload["page"] = pg
                    try:
                        result = await page.evaluate("""async (payload) => {
                            try {
                                const resp = await fetch('https://www.pipiads.com/v3/api/search4/at/video/search', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify(payload),
                                    credentials: 'include'
                                });
                                return await resp.json();
                            } catch(e) {
                                return {error: e.message};
                            }
                        }""", search_payload)

                        if result and "result" in result:
                            items = result["result"].get("list", [])
                            matched = 0
                            for item in items:
                                regions = re.findall(r"'(\w{2})'", str(item.get("fetch_region", "")))
                                if isinstance(item.get("fetch_region"), list):
                                    regions = item["fetch_region"]
                                if any(r in TARGET_REGIONS for r in regions):
                                    captured_ads.append(item)
                                    matched += 1
                            print(f"  Page {pg}: {len(items)} results, {matched} in target regions")
                        elif result and "error" in result:
                            print(f"  Page {pg}: Error - {result['error']}")
                        else:
                            print(f"  Page {pg}: Unexpected response")
                    except Exception as e:
                        print(f"  Page {pg}: Failed - {str(e)[:80]}")

                    await page.wait_for_timeout(1500)

        else:
            print("[!] Could not capture API format. Falling back to UI scraping with region filter...")
            # Fallback: do UI searches and filter results by region
            for i, keyword in enumerate(KEYWORDS, 1):
                print(f"\n[SEARCH {i}/{len(KEYWORDS)}] '{keyword}'")
                await search_input.click(click_count=3)
                await search_input.fill(keyword)
                await search_btn.click()
                await page.wait_for_timeout(5000)
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 600)")
                    await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollTo(0, 0)")
                await page.wait_for_timeout(1000)

        # Deduplicate
        seen = set()
        unique_ads = []
        for ad in captured_ads:
            aid = ad.get("ad_id")
            if aid and aid not in seen:
                seen.add(aid)
                unique_ads.append(ad)

        print(f"\n{'='*60}")
        print(f"RESEARCH COMPLETE")
        print(f"{'='*60}")
        print(f"Total captured (target regions): {len(unique_ads)}")
        print(f"Regions: {TARGET_REGIONS}")

        # Save
        final_path = DATA_DIR / f"pipiads_v3_FILTERED_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump({
                "ads": unique_ads,
                "total": len(unique_ads),
                "filters": {
                    "regions": TARGET_REGIONS,
                    "keywords": KEYWORDS,
                },
                "api_format": captured_requests[0]["payload"] if captured_requests else None,
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=True, default=str)
        print(f"Saved to: {final_path.name}")

        await page.wait_for_timeout(5000)
        await browser.close()

    print("[+] Done!")

if __name__ == "__main__":
    asyncio.run(main())
