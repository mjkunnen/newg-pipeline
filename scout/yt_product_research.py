"""YouTube search scraper - finds videos about AI automated product/brand research pipelines.
Searches diverse queries, deduplicates, outputs JSON with top results."""

import asyncio
import json
import sys
from playwright.async_api import async_playwright

SEARCHES = [
    # AI product research automation
    "AI automated product research pipeline ecommerce 2025",
    "build automated product discovery system with AI",
    "n8n automated market research workflow tutorial",
    # Trend discovery & validation
    "automated trend discovery AI dropshipping winning products",
    "how to find trending products automatically with AI agents",
    "AI product validation pipeline before launching",
    # Data scraping for product research
    "scrape amazon best sellers automated product research",
    "google trends API automated niche research python",
    "reddit scraping product ideas automation AI",
    # Brand research automation
    "automated competitor brand analysis AI tools 2025",
    "AI brand research automation workflow no code",
    "how to automate brand discovery ecommerce scaling",
    # Specific tools & platforms
    "apify web scraping product research automation tutorial",
    "make.com automated product research workflow ecommerce",
    "clay.com AI enrichment product market research",
    # AI agents for research
    "AI agent autonomous product research GPT",
    "build AI research agent that finds products automatically",
    "autonomous AI agent market analysis ecommerce",
    # Cross-platform product intelligence
    "tiktok shop trending products scraper automation",
    "amazon to shopify automated product pipeline",
    "alibaba product research automation AI workflow",
    # Niche/market analysis
    "automated niche analysis AI ecommerce 2025 2026",
    "AI market gap analysis find untapped products",
    "data driven product selection automation",
    # Advanced strategies
    "full stack automated ecommerce product research system",
    "AI supply chain product sourcing automation",
    "automated competitive intelligence ecommerce pipeline",
    # Emerging approaches
    "perplexity AI product research automation workflow",
    "ChatGPT deep research product discovery ecommerce",
    "AI web research agent product opportunities 2025",
]

async def scrape_search(page, query, max_results=5):
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}&sp=EgIQAQ%3D%3D"
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3500)

    # Scroll down to load more results
    await page.evaluate("window.scrollBy(0, 1000)")
    await page.wait_for_timeout(1500)

    videos = await page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('ytd-video-renderer').forEach(el => {
            const titleEl = el.querySelector('#video-title');
            const href = titleEl?.getAttribute('href');
            const title = titleEl?.textContent?.trim();
            const metaEl = el.querySelector('#metadata-line');
            const spans = metaEl?.querySelectorAll('span') || [];
            const views = spans[0]?.textContent?.trim() || '';
            const age = spans[1]?.textContent?.trim() || '';
            const channelEl = el.querySelector('#channel-name a, ytd-channel-name a');
            const channel = channelEl?.textContent?.trim() || '';
            if (href && title && href.startsWith('/watch')) {
                results.push({
                    url: 'https://www.youtube.com' + href.split('&pp=')[0],
                    title,
                    views,
                    age,
                    channel
                });
            }
        });
        return results;
    }""")

    return videos[:max_results]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        all_videos = {}  # deduplicate by URL
        query_counts = {}

        for i, query in enumerate(SEARCHES):
            print(f"[{i+1}/{len(SEARCHES)}] Searching: {query}", file=sys.stderr)
            try:
                videos = await scrape_search(page, query)
                added = 0
                for v in videos:
                    if v["url"] not in all_videos:
                        all_videos[v["url"]] = {**v, "query": query}
                        added += 1
                query_counts[query] = {"found": len(videos), "new": added}
                print(f"  Found {len(videos)}, {added} new (total: {len(all_videos)})", file=sys.stderr)
            except Exception as e:
                print(f"  Error: {e}", file=sys.stderr)
                query_counts[query] = {"found": 0, "new": 0, "error": str(e)}

        await browser.close()

        results = list(all_videos.values())
        print(f"\nTotal unique videos: {len(results)}", file=sys.stderr)
        print(f"From {len(SEARCHES)} searches", file=sys.stderr)
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
