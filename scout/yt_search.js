// YouTube search scraper - extracts video URLs from multiple search queries
// Run with: node scout/yt_search.js

const { chromium } = require('playwright');

const SEARCHES = [
  // Core workflow matches
  "n8n apify facebook ad library scraper automation",
  "automate competitor ad creative remake AI",
  "fal.ai nano banana image generation ads",
  "scrape pinterest pins automation workflow",
  "tiktok carousel ad automation scraping",
  // Dropshipping/ecom ad automation
  "dropshipping facebook ad creative automation 2025",
  "automated ad creation shopify product images",
  "AI remake competitor ads ecommerce",
  // Specific tech
  "oxylabs web scraper ecommerce",
  "meta ad library API scraping python",
  "github pages dashboard automation ecommerce",
  // Strategy
  "winning ad creative strategy dropshipping scaling",
  "how to find competitor ads pinterest tiktok",
  "automated creative testing facebook ads",
  "AI product photography ecommerce automation"
];

async function scrapeSearch(page, query) {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}&sp=EgIQAQ%3D%3D`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);

  const videos = await page.evaluate(() => {
    const results = [];
    document.querySelectorAll('ytd-video-renderer').forEach(el => {
      const titleEl = el.querySelector('#video-title');
      const href = titleEl?.getAttribute('href');
      const title = titleEl?.textContent?.trim();
      const metaEl = el.querySelector('#metadata-line');
      const spans = metaEl?.querySelectorAll('span') || [];
      const views = spans[0]?.textContent?.trim() || '';
      const age = spans[1]?.textContent?.trim() || '';
      if (href && title && href.startsWith('/watch')) {
        results.push({
          url: 'https://www.youtube.com' + href.split('&pp=')[0],
          title,
          views,
          age
        });
      }
    });
    return results.slice(0, 5); // top 5 per search
  });

  return videos;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const allVideos = new Map(); // deduplicate by URL

  for (const query of SEARCHES) {
    console.error(`Searching: ${query}`);
    try {
      const videos = await scrapeSearch(page, query);
      for (const v of videos) {
        if (!allVideos.has(v.url)) {
          allVideos.set(v.url, { ...v, query });
        }
      }
    } catch (e) {
      console.error(`  Error: ${e.message}`);
    }
  }

  await browser.close();

  // Output as JSON
  const results = [...allVideos.values()];
  console.log(JSON.stringify(results, null, 2));
})();
