"""Oxylabs Web Unblocker proxy configuration."""

OXYLABS_PROXY = {
    "server": "https://unblock.oxylabs.io:60000",
    "username": "claude_Jp3lk",
    "password": "qxEfW4BnzPI8TO=D",
}

# Browser launch args for proxy usage
BROWSER_ARGS = ["--ignore-certificate-errors"]

# Longer timeouts for proxy connections
PROXY_TIMEOUT = 90000  # 90 seconds
PROXY_WAIT = 5000  # 5 seconds after page load


async def launch_browser(playwright, headless=False, use_proxy=True):
    """Launch Chromium, optionally with Oxylabs proxy."""
    kwargs = {
        "headless": headless,
        "args": BROWSER_ARGS if use_proxy else [],
    }
    if use_proxy:
        kwargs["proxy"] = OXYLABS_PROXY
    browser = await playwright.chromium.launch(**kwargs)
    return browser


async def new_page(browser):
    """Create a new page with proxy-compatible settings."""
    context = await browser.new_context(
        ignore_https_errors=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = await context.new_page()
    return page
