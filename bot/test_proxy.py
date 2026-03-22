"""Test Oxylabs Web Unblocker with non-headless Chromium."""
import asyncio
from playwright.async_api import async_playwright

PROXY = {
    "server": "https://unblock.oxylabs.io:60000",
    "username": "claude_Jp3lk",
    "password": "qxEfW4BnzPI8TO=D",
}


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            proxy=PROXY,
            args=["--ignore-certificate-errors"],
        )
        page = await browser.new_page(ignore_https_errors=True)

        # Test 1: Google search
        print("=== TEST 1: Google Search ===")
        try:
            await page.goto(
                "https://www.google.com/search?q=streetwear+brand+limited+drops+heavyweight+hoodie&hl=en&gl=us",
                timeout=60000,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(5000)

            title = await page.title()
            print(f"Page title: {title}")

            # Extract results
            results = await page.evaluate(
                """() => {
                    const items = [];
                    document.querySelectorAll('div.g').forEach(el => {
                        const link = el.querySelector('a[href^="http"]');
                        const h3 = el.querySelector('h3');
                        if (link && h3) {
                            items.push({url: link.href, title: h3.innerText});
                        }
                    });
                    if (items.length === 0) {
                        document.querySelectorAll('h3').forEach(h3 => {
                            const a = h3.closest('a');
                            if (a && a.href && a.href.startsWith('http') && !a.href.includes('google.com')) {
                                items.push({url: a.href, title: h3.innerText});
                            }
                        });
                    }
                    return items;
                }"""
            )
            print(f"Results: {len(results)}")
            for r in results[:5]:
                print(f"  {r['title'][:55]}")
                print(f"    -> {r['url'][:80]}")
        except Exception as e:
            print(f"Google FAILED: {e}")

        await page.wait_for_timeout(2000)

        # Test 2: Competitor website
        print("\n=== TEST 2: Competitor Website ===")
        try:
            await page.goto(
                "https://vicinityclo.de",
                timeout=60000,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(3000)
            title = await page.title()
            print(f"Vicinity title: {title}")
            print("Website access: OK")
        except Exception as e:
            print(f"Website FAILED: {e}")

        # Test 3: Meta Ad Library
        print("\n=== TEST 3: Meta Ad Library ===")
        try:
            await page.goto(
                "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q=Trapstar&media_type=all",
                timeout=60000,
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(5000)
            title = await page.title()
            body_len = await page.evaluate("() => document.body.innerText.length")
            print(f"Ad Library title: {title}")
            print(f"Body text length: {body_len}")
            print("Ad Library access: OK")
        except Exception as e:
            print(f"Ad Library FAILED: {e}")

        await browser.close()
        print("\n=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(test())
