"""Step 1: Open PiPiAds, let user login, screenshot the ad search page."""
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path

SCREENSHOTS = Path(__file__).parent / "pipiads_screenshots"
SCREENSHOTS.mkdir(exist_ok=True)
COOKIES = Path(__file__).parent / "pipiads_data" / "pipiads_cookies.json"
COOKIES.parent.mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080}, no_viewport=False)

        # Load cookies if available
        import json
        if COOKIES.exists():
            try:
                cookies = json.loads(COOKIES.read_text())
                await context.add_cookies(cookies)
                print("[+] Loaded saved cookies")
            except: pass

        page = await context.new_page()
        await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=60000)
        await page.screenshot(path=str(SCREENSHOTS / "step1_initial_load.png"), full_page=False)
        print("[+] Screenshot: step1_initial_load.png")

        # Check if we need login
        if "login" in page.url.lower() or await page.locator("text=Log in").count() > 0 or await page.locator("text=Sign in").count() > 0:
            print("[!] LOGIN REQUIRED - Please log in in the browser window")
            print("[!] Waiting up to 120 seconds for login...")
            # Wait for navigation away from login
            try:
                await page.wait_for_url("**/ad-search**", timeout=120000)
                print("[+] Login detected!")
            except:
                print("[!] Checking current URL:", page.url)

            await page.wait_for_timeout(3000)

        # Save cookies
        cookies = await context.cookies()
        import json
        COOKIES.write_text(json.dumps(cookies, default=str))
        print("[+] Cookies saved")

        # Navigate to ad search
        if "ad-search" not in page.url:
            await page.goto("https://www.pipiads.com/ad-search", wait_until="networkidle", timeout=30000)

        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(SCREENSHOTS / "step1_logged_in.png"), full_page=False)
        print("[+] Screenshot: step1_logged_in.png")

        # Take a full page screenshot to see all filters
        await page.screenshot(path=str(SCREENSHOTS / "step1_full_page.png"), full_page=True)
        print("[+] Screenshot: step1_full_page.png")

        # Dump the page structure to understand the UI
        # Get all visible buttons, inputs, selects, dropdowns
        elements = await page.evaluate("""() => {
            const results = [];
            // All clickable/interactive elements
            const selectors = ['button', 'input', 'select', '[role="button"]', '[class*="filter"]', '[class*="select"]', '[class*="dropdown"]', '[class*="search"]', '[class*="sort"]', '[placeholder]'];
            for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({
                            tag: el.tagName,
                            type: el.type || '',
                            text: (el.textContent || '').trim().substring(0, 80),
                            placeholder: el.placeholder || '',
                            className: (el.className || '').toString().substring(0, 100),
                            id: el.id || '',
                            role: el.getAttribute('role') || '',
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            w: Math.round(rect.width),
                            h: Math.round(rect.height),
                        });
                    }
                });
            }
            return results;
        }""")

        # Save element map
        with open(str(SCREENSHOTS / "step1_elements.json"), "w") as f:
            json.dump(elements, f, indent=2)
        print(f"[+] Found {len(elements)} interactive elements - saved to step1_elements.json")

        # Print key elements
        print("\n=== KEY UI ELEMENTS ===")
        for el in elements:
            if any(k in (el.get('text','') + el.get('placeholder','') + el.get('className','')).lower()
                   for k in ['search', 'filter', 'country', 'sort', 'platform', 'shop', 'date', 'last seen', 'keyword']):
                print(f"  [{el['tag']}] text='{el['text'][:50]}' placeholder='{el['placeholder']}' class='{el['className'][:60]}' @ ({el['x']},{el['y']})")

        print("\n[+] Done! Check pipiads_screenshots/ folder")
        print("[+] Keeping browser open for 10 seconds...")
        await page.wait_for_timeout(10000)

        await browser.close()

asyncio.run(main())
